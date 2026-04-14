import json
import logging
import sys
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from spl.token.core import MintInfo
from spl.token._layouts import MINT_LAYOUT
from core.config import Config


class MintInfoWithProgramID(MintInfo):
    token_program_id = None

    def __new__(cls, *args, **kwargs):
        token_id = kwargs.pop('token_program_id', None)
        self = super().__new__(cls, *args, **kwargs)
        object.__setattr__(self, 'token_program_id', token_id)
        return self


def load_json_file(file_path, ignore_error=True):
    try:
        with open(file_path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        if ignore_error:
            return {}
        raise e


def save_json_file(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f)


async def get_mint_info(mint, rpc_url):
    mint_address = Pubkey.from_string(mint)
    rpc = AsyncClient(rpc_url)
    async with rpc:
        # Get account info
        account_info = await rpc.get_account_info(mint_address)

        # Parse mint data using layout
        mint_data = MINT_LAYOUT.parse(account_info.value.data)

        # Create MintInfo object
        mint_info = MintInfoWithProgramID(
            mint_authority=mint_data.mint_authority,
            supply=mint_data.supply,
            decimals=mint_data.decimals,
            is_initialized=mint_data.is_initialized,
            freeze_authority=mint_data.freeze_authority,
            token_program_id=account_info.value.owner
        )

        return mint_info


async def get_mint_decimals(mint: str, rpc_url: str, mint_decimal_file: str = Config.MINT_DECIMALS_JSON_FILE):
    mint_decimals_json = load_json_file(mint_decimal_file)
    if mint_decimals_json and mint in mint_decimals_json and mint_decimals_json[mint]:
        return mint_decimals_json[mint]

    input_mint_info = await get_mint_info(mint, rpc_url)
    decimals = input_mint_info.decimals
    mint_decimals_json[mint] = decimals

    save_json_file(mint_decimal_file, mint_decimals_json)

    return decimals


async def amount_to_raw_amount(mint: str, amount: float, rpc_url: str) -> int:
    mint_decimals = await get_mint_decimals(mint, rpc_url)
    raw_amount = int(amount*(10**mint_decimals))
    return raw_amount


async def raw_amount_to_amount(mint: str, raw_amount: int, rpc_url: str) -> float:
    mint_decimals = await get_mint_decimals(mint, rpc_url)
    amount = raw_amount / (10**mint_decimals)
    return amount


def setup_logging(logger_name: str, log_file: str = None, log_level: int = logging.INFO):
    # 1. Create a custom logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    # 2. Define a format for the logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 3. Create a console handler (StreamHandler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 4. Create a file handler (FileHandler)
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
