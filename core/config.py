import os
from dotenv import load_dotenv


load_dotenv()


class Config:

    SOL_MINT = "So11111111111111111111111111111111111111112"

    MINT_DECIMALS_JSON_FILE: str = os.getenv(
        "MINT_DECIMALS_JSON_FILE", "mint_decimals.json")

    DEFAULT_RPC = os.getenv(
        "DEFAULT_RPC", "https://api.mainnet-beta.solana.com")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    MIN_REBALANCE_SOL_VALUE: float = float(
        os.getenv("MIN_REBALANCE_SOL_VALUE", 0.12))

    TRADE_TAX_PERCENTAGE: float = float(
        os.getenv("TRADE_TAX_PERCENTAGE", 0))
