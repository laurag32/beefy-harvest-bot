import os, time, logging, requests
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account
from datetime import datetime

# Load .env values
load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PUBLIC_ADDRESS = os.getenv("PUBLIC_ADDRESS")
RPC = os.getenv("RPC_POLYGON", "https://polygon-rpc.com")
MIN_PROFIT_USD = float(os.getenv("MIN_PROFIT_USD", "3.0"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ("1","true","yes")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))
NATIVE_TOKEN_PRICE_USD = float(os.getenv("NATIVE_TOKEN_PRICE_USD", "0.5"))

# New rules
MAX_TVL = float(os.getenv("MAX_TVL", "5000000"))  # skip if TVL > $5M
MIN_IDLE_HOURS = float(os.getenv("MIN_IDLE_HOURS", "3"))  # skip if last harvest < 3h

# Setup web3
w3 = Web3(Web3.HTTPProvider(RPC))
acct = Account.from_key(PRIVATE_KEY)

# Harvest ABI
HARVEST_ABI = [{"inputs":[],"name":"harvest","outputs":[],"stateMutability":"nonpayable","type":"function"}]

def fetch_json(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def estimate_usd_reward(entry):
    for k in ("usd","pendingUsd","harvestBountyUsd","callRewardUsd","callReward"):
        if isinstance(entry, dict) and k in entry:
            try: return float(entry[k])
            except: pass
    return None

def main_loop():
    logging.info("Bot started (DRY_RUN=%s)", DRY_RUN)
    while True:
        try:
            vaults = fetch_json("https://api.beefy.finance/vaults")
            earnings = fetch_json("https://api.beefy.finance/earnings")

            earn_map = {}
            for e in earnings:
                addr = e.get("vault") or e.get("address") or e.get("vaultAddress")
                if addr:
                    earn_map[Web3.toChecksumAddress(addr)] = e

            now = int(time.time())

            for v in vaults:
                try:
                    chain = (v.get("chain") or v.get("network") or "").lower()
                    if "polygon" not in chain and "matic" not in chain:
                        continue  # Rule: Polygon only

                    vault_addr = v.get("vault") or v.get("address") or v.get("vaultAddress")
                    if not vault_addr: continue
                    vault_addr = Web3.toChecksumAddress(vault_addr)

                    # TVL rule
                    tvl = float(v.get("tvl", 0))
                    if tvl > MAX_TVL:
                        logging.info("Skip %s (TVL $%.2f too large)", vault_addr, tvl)
                        continue

                    # Last harvest rule
                    last_harvest = v.get("lastHarvest")
                    if last_harvest:
                        hours_since = (now - int(last_harvest)) / 3600
                        if hours_since < MIN_IDLE_HOURS:
                            logging.info("Skip %s (only %.1f hours since harvest)", vault_addr, hours_since)
                            continue

                    # Reward check
                    e = earn_map.get(vault_addr)
                    usd_reward = estimate_usd_reward(e) if e else None
                    if not usd_reward or usd_reward < MIN_PROFIT_USD:
                        continue

                    logging.info("Candidate %s reward=$%.2f", vault_addr, usd_reward)

                    contract = w3.eth.contract(address=vault_addr, abi=HARVEST_ABI)
                    nonce = w3.eth.get_transaction_count(PUBLIC_ADDRESS)
                    txn = contract.functions.harvest().buildTransaction({"from": PUBLIC_ADDRESS, "nonce": nonce})

                    try:
                        gas_est = w3.eth.estimate_gas({"from": PUBLIC_ADDRESS, "to": vault_addr, "data": txn["data"]})
                    except Exception as ex:
                        logging.warning("Gas estimate failed: %s", ex)
                        continue

                    gas_price = w3.eth.gas_price
                    cost_matic = gas_est * gas_price / 1e18
                    cost_usd = cost_matic * NATIVE_TOKEN_PRICE_USD

                    if cost_usd > usd_reward:
                        logging.info("Not profitable: cost=$%.4f > reward=$%.2f", cost_usd, usd_reward)
                        continue

                    if DRY_RUN:
                        logging.info("DRY_RUN: would harvest → vault=%s reward=$%.2f", vault_addr, usd_reward)
                        continue

                    txn.update({"gas": gas_est + 20000, "gasPrice": gas_price})
                    signed = w3.eth.account.sign_transaction(txn, PRIVATE_KEY)
                    txh = w3.eth.send_raw_transaction(signed.rawTransaction)
                    logging.info("✅ Sent harvest tx %s", txh.hex())

                except Exception:
                    logging.exception("Vault loop error")

            time.sleep(POLL_INTERVAL)
        except Exception:
            logging.exception("Main loop error")
            time.sleep(10)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main_loop()
