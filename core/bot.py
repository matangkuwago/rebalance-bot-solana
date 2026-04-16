import json
from dataclasses import dataclass, asdict
from typing import List, Type
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from spl.token.instructions import get_associated_token_address
from core.trader import Trader, JupiterTrader
from core.config import Config
from core.utilities import (
    get_sol_balance,
    get_mint_info,
    get_token_account,
    raw_amount_to_amount,
    setup_logging
)


@dataclass
class RebalanceItem:
    mint: str
    target_percent_share: float
    current_balance: float | None = None
    current_sol_value: float | None = None
    current_percent_share: float | None = None
    rebalance_action: dict | None = None

    def __post_init__(self):
        if not (0 <= self.target_percent_share <= 1):
            raise ValueError(f"percent_share must be between 0 and 1")

    async def update_current_balance_from_wallet(self, wallet: Pubkey, rpc_url: str = Config.DEFAULT_RPC):
        if self.mint == Config.SOL_MINT:
            self.current_balance = await get_sol_balance(wallet, rpc_url)
            return

        mint_pubkey = Pubkey.from_string(self.mint)
        mint_info = await get_mint_info(self.mint, rpc_url)
        token_program_id = mint_info.token_program_id
        token_account_address = get_associated_token_address(
            owner=wallet,
            mint=mint_pubkey,
            token_program_id=token_program_id
        )
        rpc = AsyncClient(rpc_url)
        async with rpc:
            try:
                response = await rpc.get_token_account_balance(token_account_address)
                balance_data = response.value
                self.current_balance = balance_data.ui_amount
            except Exception as e:
                raise RuntimeError(f"Error getting token balance: {e}. "
                                   f"This might be because the account doesn't exist or isn't a token account.")


class RebalanceBot:

    def __init__(self,
                 private_key: str,
                 rebalance_items: list[RebalanceItem],
                 trader: Trader = None,
                 rpc_url: str = Config.DEFAULT_RPC,
                 min_rebalance_sol_value: float = Config.MIN_REBALANCE_SOL_VALUE):

        self.validate_setup(rebalance_items)
        self.wallet = Keypair.from_base58_string(private_key)
        self.rebalance_items = rebalance_items
        self.trader = trader if trader else JupiterTrader()
        self.rpc_url = rpc_url
        self.min_rebalance_sol_value = min_rebalance_sol_value
        self.logger = setup_logging(
            "RebalanceBot", "rebalance_bot.log", Config.LOG_LEVEL)

    def validate_setup(self, rebalance_items):
        if sum([x.target_percent_share for x in rebalance_items]) != 1:
            raise ValueError("Percentages do not add up to 1!")
        mints = [x.mint for x in rebalance_items]
        duplicate_mints = [y for y in mints if mints.count(y) > 1]
        if duplicate_mints:
            raise ValueError(f"Duplicate mints found: {duplicate_mints}!")

    async def update_rebalance_items(self):

        total_sol_value = 0
        for item in self.rebalance_items:
            if item.current_balance is None:
                await item.update_current_balance_from_wallet(
                    self.wallet.pubkey(), self.rpc_url)

            if item.mint == Config.SOL_MINT:
                item.current_sol_value = item.current_balance
            else:
                quote = await self.trader.get_quote(item.mint,
                                                    Config.SOL_MINT,
                                                    item.current_balance,
                                                    self.wallet)
                output_amount_raw = int(quote["otherAmountThreshold"])
                output_amount = await raw_amount_to_amount(Config.SOL_MINT, output_amount_raw, self.rpc_url)
                item.current_sol_value = output_amount

            total_sol_value += item.current_sol_value

        for item in self.rebalance_items:
            item.current_percent_share = item.current_sol_value / total_sol_value
            self.logger.info(f"update_rebalance_items: "
                             f"mint: {item.mint}, "
                             f"current_percent_share {item.current_percent_share}, "
                             f"target_percent_share {item.target_percent_share}")

    async def get_price(self, mint: str):
        sol_value = 1
        quote = await self.trader.get_quote(Config.SOL_MINT,
                                            mint,
                                            sol_value)
        output_amount_raw = int(quote["otherAmountThreshold"])
        output_amount = await raw_amount_to_amount(mint, output_amount_raw, self.rpc_url)
        if output_amount:
            return sol_value / output_amount

        raise RuntimeError(f"Unable to get price quote for mint {mint}")

    def get_rebalance_actions(self):
        total_sol_value = sum(
            item.current_sol_value for item in self.rebalance_items)

        for item in self.rebalance_items:
            diff = item.current_percent_share - item.target_percent_share
            price = (item.current_sol_value /
                     item.current_balance) if item.current_balance > 0 else self.get_price(item.mint)
            sol_value = abs(diff*total_sol_value)
            quantity = sol_value / price
            action = {
                "mint": item.mint,
                "sol_value": sol_value,
                "quantity": quantity,
                "diff": diff,
            }
            item.rebalance_action = action
            self.logger.info(f"rebalance action added: "
                             f"{json.dumps(action, indent=4)}")

    async def execute_rebalance_actions(self):
        invalid_rebalance_actions = [item.rebalance_action
                                     for item in self.rebalance_items
                                     if item.rebalance_action["sol_value"] < self.min_rebalance_sol_value]
        if invalid_rebalance_actions:
            self.logger.info(f"Unable to rebalance since these actions doesn't meet "
                             f"the min_rebalance_sol_value ({self.min_rebalance_sol_value}): "
                             f"{json.dumps(invalid_rebalance_actions, indent=4)}")
            return

        sell_actions = [
            item.rebalance_action for item in self.rebalance_items if item.rebalance_action and item.rebalance_action["diff"] > 0]
        buy_actions = [
            item.rebalance_action for item in self.rebalance_items if item.rebalance_action and item.rebalance_action["diff"] < 0]

        available_sol = 0
        for action in sell_actions:
            mint = action["mint"]
            quantity = action["quantity"]
            input_mint = mint
            output_mint = Config.SOL_MINT
            if input_mint == output_mint:
                available_sol += quantity
            else:
                result = await self.trader.swap(input_mint, output_mint, quantity, self.wallet)
                if result:
                    input_amount = result["input_amount"]
                    output_amount = result["output_amount"]
                    self.logger.info(f"execute_rebalance_actions: "
                                     f"{mint}: sold {input_amount}, "
                                     f"bought {output_amount} SOL")
                    available_sol += output_amount

        for action in buy_actions:
            mint = action["mint"]
            quantity = action["quantity"]
            if available_sol <= 0:
                self.logger.info(f"execute_rebalance_actions: "
                                 f"{mint}: no more available SOL to buy {quantity} of {mint}")
                continue
            sol_value = action["sol_value"]
            sol_budget = sol_value if sol_value <= available_sol else available_sol
            input_mint = Config.SOL_MINT
            output_mint = mint
            if input_mint == output_mint:
                available_sol -= sol_budget
            else:
                result = await self.trader.swap(input_mint, output_mint, sol_budget, self.wallet)
                if result:
                    input_amount = result["input_amount"]
                    output_amount = result["output_amount"]
                    available_sol -= sol_budget
                    self.logger.info(f"{mint}: sold {input_amount} SOL, "
                                     f"bought {output_amount} {mint}")

    async def rebalance(self, rebalance_interval: int | None = None):
        await self.update_rebalance_items()
        self.get_rebalance_actions()
        await self.execute_rebalance_actions()
