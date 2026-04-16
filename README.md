# rebalance-bot-solana

This is a simple rebalancing bot. This project is a work in progress. Expect breaking changes and incomplete documentation.

Example usage:

```python 
import os
import asyncio
from dotenv import load_dotenv
from core.bot import RebalanceItem, RebalanceBot


async def main():
    load_dotenv()

    private_key = os.getenv("WALLET_PRIVATE_KEY")
    sol_mint = "So11111111111111111111111111111111111111112"  # SOL
    zec_mint = "A7bdiYdS5GjqGFtxf17ppRHtDKPkkRqbKtR27dxvQXaS"  # ZEC
    rebalance_interval = 60
    bot = RebalanceBot(
        private_key=private_key,
        rebalance_items=[
            RebalanceItem(sol_mint, 0.5),
            RebalanceItem(zec_mint, 0.5)
        ],
    )

    await bot.rebalance(rebalance_interval=rebalance_interval)

asyncio.run(main())
```
