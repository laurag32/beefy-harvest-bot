# beefy-harvest-bot
Keeper’s bot 
# Beefy Harvest Keeper Bot (Polygon)

Monitors Beefy vaults on Polygon and triggers `harvest()` when profitable.

## Rules built into the bot
- Only Polygon vaults.
- Skip vaults with TVL > `MAX_TVL` (default $5,000,000).
- Skip vaults harvested less than `MIN_IDLE_HOURS` (default 3 hours).
- Skip if reward < `MIN_PROFIT_USD` (default $3).
- Skip if gas cost > reward.
- `DRY_RUN=true` prevents real txs while testing.

## Environment variables (Railway variables)
- `PRIVATE_KEY` (required) — wallet private key (0x...)
- `PUBLIC_ADDRESS` (required) — wallet address (0x...)
- `RPC_POLYGON` (optional) — e.g. https://polygon-rpc.com
- `MIN_PROFIT_USD` (default 3)
- `DRY_RUN` (true/false) — test mode default true
- `NATIVE_TOKEN_PRICE_USD` (e.g. 0.5)
- `POLL_INTERVAL` (seconds; default 30)
- `MAX_TVL` (default 5000000)
- `MIN_IDLE_HOURS` (default 3)
