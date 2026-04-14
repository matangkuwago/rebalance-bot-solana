

from dataclasses import dataclass, asdict
from typing import List, Type
from solders.keypair import Keypair
from core.trader import Trader, JupiterTrader


@dataclass
class RebalanceItem:
    mint: str
    percent_share: float

    def __post_init__(self):
        if not (0 <= self.percent_share <= 1):
            raise ValueError(f"percent_share must be between 0 and 1")


@dataclass(init=False)
class RebalanceConfig:
    rebalance_interval: int
    rebalance_setup: List[RebalanceItem]

    def __init__(self,
                 rebalance_interval: int,
                 rebalance_setup: list[RebalanceItem],
                 trader: Trader
                 ):
        self.validate_setup(rebalance_setup)
        self.rebalance_interval = rebalance_interval
        self.rebalance_setup = rebalance_setup
        self.trader = trader

    def validate_setup(self, rebalance_setup):
        if sum([x.percent_share for x in rebalance_setup]) != 1:
            raise ValueError("Percentages do not add up to 1!")
        mints = [x.mint for x in rebalance_setup]
        duplicate_mints = [y for y in mints if mints.count(y) > 1]
        if duplicate_mints:
            raise ValueError(f"Duplicate mints found: {duplicate_mints}!")


class RebalanceBot:

    def __init__(self,
                 private_key: str,
                 rebalance_config: RebalanceConfig,
                 rpc_url: str):

        self.keypair = Keypair.from_base58_string(private_key)
        self.rebalance_config = rebalance_config
        if not rpc_url:
            raise ValueError("Invalid RPC URL!")
        self.rpc_url = rpc_url

    async def rebalance():
        pass
