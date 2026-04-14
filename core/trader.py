import base64
import requests
import logging
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from core.utilities import setup_logging
from core.config import Config
from core.utilities import amount_to_raw_amount, raw_amount_to_amount


class Trader:

    def get_quote(self, input_mint: str, output_mint: str, amount: float):
        raise NotImplementedError(
            "Subclasses must implement the get_quote() method")

    def swap(self, input_mint: str, output_mint: str, amount: float):
        raise NotImplementedError(
            "Subclasses must implement the swap() method")


class JupiterTrader(Trader):

    DEFAULT_BASE_URL = "https://api.jup.ag/swap/v2"

    def __init__(self, api_key: str = None, base_url: str = None, rpc_url: str = None, logger: logging.Logger = None):
        self.api_key = api_key
        self.base_url = base_url if base_url else self.DEFAULT_BASE_URL
        self.rpc_url = rpc_url if rpc_url else Config.DEFAULT_RPC
        self.logger = (logger if logger
                       else setup_logging("JupiterTrader", "JupiterTrader.log"))

    async def get_quote(self, input_mint: str, output_mint: str, input_amount: int, wallet: Keypair = None):
        headers = {"x-api-key": self.api_key} if self.api_key else {}
        endpoint = f"{self.base_url}/order"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": await amount_to_raw_amount(input_mint, input_amount, self.rpc_url),
            "taker": wallet.pubkey() if wallet else None
        }
        response = requests.get(endpoint, params=params, headers=headers)
        if response.status_code != 200:
            try:
                log_message = f"Error fetching quote: {response.json()}"
            except requests.exceptions.JSONDecodeError:
                log_message = f"Error fetching quote: {response.text}"
            self.logger.error(log_message)
            raise RuntimeError(log_message)

        return response.json()

    async def swap(self, input_mint: str, output_mint: str, input_amount: float, wallet: Keypair):
        quote = await self.get_quote(input_mint, output_mint, input_amount, wallet)
        if not ("transaction" in quote and quote["transaction"]):
            error_code = quote["errorCode"]
            error_message = quote["errorMessage"]
            log_message = f"transaction not found in jupiter quote: error_code {error_code}, error_message {error_message}"
            self.logger.error(log_message)
            raise RuntimeError(log_message)

        # get raw transaction
        transaction = quote["transaction"]
        transaction_bytes = base64.b64decode(transaction)
        raw_transaction = VersionedTransaction.from_bytes(transaction_bytes)

        # sign transaction
        account_keys = raw_transaction.message.account_keys
        wallet_index = account_keys.index(wallet.pubkey())
        signers = list(raw_transaction.signatures)
        signers[wallet_index] = wallet
        signed_transaction = VersionedTransaction(
            raw_transaction.message,
            signers
        )
        signed_tx_bytes = bytes(signed_transaction)
        encoded_tx = base64.b64encode(signed_tx_bytes).decode('utf-8')

        # send transaction
        headers = {"x-api-key": self.api_key} if self.api_key else {}
        request_id = quote["requestId"]
        endpoint = f"{self.base_url}/execute"
        payload = {
            "signedTransaction": encoded_tx,
            "requestId": request_id,
        }
        response = requests.post(endpoint, json=payload, headers=headers)
        if response.status_code != 200:
            try:
                log_message = f"Error executing swap: {response.json()}"
            except requests.exceptions.JSONDecodeError:
                log_message = f"Error executing swap: {response.text}"
            self.logger.error(log_message)
            raise RuntimeError(log_message)

        # parse response
        response_json = response.json()
        status = response_json['status']
        if status != 'Success':
            code = response_json["code"]
            error = response_json["error"]
            log_message = f"Unable to execute swap: code {code}, error {error}"
            self.logger.error(log_message)
            raise RuntimeError(log_message)

        input_amount = int(response_json["inputAmountResult"])
        output_amount = int(response_json["outputAmountResult"])
        result = {
            "input_amount": await raw_amount_to_amount(input_mint, input_amount, self.rpc_url),
            "output_amount": await raw_amount_to_amount(output_mint, output_amount, self.rpc_url),
        }
        return result
