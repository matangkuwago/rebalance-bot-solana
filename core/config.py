import os
from dotenv import load_dotenv


load_dotenv()


class Config:

    MINT_DECIMALS_JSON_FILE: str = os.getenv(
        "MINT_DECIMALS_JSON_FILE", "mint_decimals.json")

    DEFAULT_RPC = os.getenv(
        "DEFAULT_RPC", "https://api.mainnet-beta.solana.com")
