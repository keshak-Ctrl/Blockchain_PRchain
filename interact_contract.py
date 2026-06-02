"""
interact_contract.py
PRChain Solutions Ltd. — HealthCare Innovations Ltd.

Interact with the deployed PatientRecordContract on the Sepolia testnet
using web3.py.

Prerequisites
─────────────
    pip install web3 python-dotenv

Environment variables (create a .env file or export in your shell):
    WEB3_PROVIDER_URL   – Sepolia RPC endpoint
                          e.g. https://sepolia.infura.io/v3/<PROJECT_ID>
                          or   https://eth-sepolia.g.alchemy.com/v2/<API_KEY>
    DEPLOYER_PRIVATE_KEY – hex private key of the deploying account (owner)
    PROVIDER_B_PRIVATE_KEY – hex private key of a second provider account
    CONTRACT_ADDRESS     – address of the deployed PatientRecordContract

Usage
─────
    python interact_contract.py
"""

import os
import sys
import json
from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

load_dotenv()

# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
RPC_URL          = os.getenv("WEB3_PROVIDER_URL", "")
DEPLOYER_KEY     = os.getenv("DEPLOYER_PRIVATE_KEY", "")
PROVIDER_B_KEY   = os.getenv("PROVIDER_B_PRIVATE_KEY", "")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")

# ABI — generated after compiling PatientRecordContract.sol
# (paste the full ABI from your build artefact here, or load from a JSON file)
CONTRACT_ABI = json.loads("""
[
  {"inputs":[],"stateMutability":"nonpayable","type":"constructor"},
  {"anonymous":false,"inputs":[{"indexed":true,"name":"provider","type":"address"},{"indexed":false,"name":"status","type":"bool"}],"name":"ProviderAuthorised","type":"event"},
  {"anonymous":false,"inputs":[{"indexed":true,"name":"recordId","type":"uint256"},{"indexed":false,"name":"patientName","type":"string"},{"indexed":true,"name":"addedBy","type":"address"}],"name":"RecordAdded","type":"event"},
  {"anonymous":false,"inputs":[{"indexed":true,"name":"recordId","type":"uint256"},{"indexed":true,"name":"fromProvider","type":"address"},{"indexed":true,"name":"toProvider","type":"address"}],"name":"RecordTransferred","type":"event"},
  {"inputs":[{"name":"patientName","type":"string"},{"name":"dateOfBirth","type":"uint256"},{"name":"diagnosis","type":"string"},{"name":"treatment","type":"string"}],"name":"addRecord","outputs":[{"name":"recordId","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"name":"recordId","type":"uint256"}],"name":"getRecord","outputs":[{"components":[{"name":"id","type":"uint256"},{"name":"patientName","type":"string"},{"name":"dateOfBirth","type":"uint256"},{"name":"diagnosis","type":"string"},{"name":"treatment","type":"string"},{"name":"currentProvider","type":"address"},{"name":"createdAt","type":"uint256"},{"name":"exists","type":"bool"}],"name":"","type":"tuple"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"provider","type":"address"}],"name":"isAuthorised","outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"owner","outputs":[{"name":"","type":"address"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"provider","type":"address"},{"name":"status","type":"bool"}],"name":"setProviderAuthorisation","outputs":[],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[{"name":"recordId","type":"uint256"},{"name":"toProvider","type":"address"}],"name":"transferRecord","outputs":[],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[],"name":"totalRecords","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"name":"","type":"address"}],"name":"authorisedProviders","outputs":[{"name":"","type":"bool"}],"stateMutability":"view","type":"function"}
]
""")


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def connect() -> Web3:
    if not RPC_URL:
        sys.exit("ERROR: WEB3_PROVIDER_URL is not set.")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    # Inject middleware for PoA networks (Sepolia uses PoA headers)
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    if not w3.is_connected():
        sys.exit("ERROR: Cannot connect to RPC endpoint.")
    print(f" Connected to Sepolia  |  Chain ID: {w3.eth.chain_id}")
    return w3


def load_account(w3: Web3, private_key: str):
    if not private_key:
        sys.exit("ERROR: Private key is not set.")
    return w3.eth.account.from_key(private_key)


def send_tx(w3: Web3, account, fn_call) -> dict:
    """Build, sign, broadcast, and wait for a transaction receipt."""
    tx = fn_call.build_transaction(
        {
            "from":  account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  → tx sent: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    status = "success" if receipt.status == 1 else " reverted"
    print(f"  → mined in block {receipt.blockNumber}  [{status}]")
    return receipt


# ─────────────────────────────────────────────
#  Main interaction flow
# ─────────────────────────────────────────────
def main():
    w3 = connect()

    deployer   = load_account(w3, DEPLOYER_KEY)
    provider_b = load_account(w3, PROVIDER_B_KEY)

    if not CONTRACT_ADDRESS:
        sys.exit("ERROR: CONTRACT_ADDRESS is not set.")

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=CONTRACT_ABI,
    )

    print(f"\nDeployer   : {deployer.address}")
    print(f"Provider B : {provider_b.address}")
    print(f"Contract   : {contract.address}\n")

    # ── 1. Read current state ──────────────────────────────────────────
    total = contract.functions.totalRecords().call()
    print(f"[1] Current totalRecords = {total}")

    # ── 2. Authorise provider B ────────────────────────────────────────
    print("\n[2] Authorising Provider B …")
    is_auth = contract.functions.isAuthorised(provider_b.address).call()
    if not is_auth:
        receipt = send_tx(
            w3,
            deployer,
            contract.functions.setProviderAuthorisation(provider_b.address, True),
        )
    else:
        print("  → Provider B already authorised, skipping.")

    # ── 3. Add a patient record (deployer / Provider A) ────────────────
    print("\n[3] Adding patient record (Provider A) …")
    receipt = send_tx(
        w3,
        deployer,
        contract.functions.addRecord(
            "Kiko Pun",   # patientName
            27112002,            # dateOfBirth  (1990-01-01 UTC)
            "Hypertension",       # diagnosis
            "Lisinopril 10mg",    # treatment
        ),
    )

    # Parse RecordAdded event to get the new record ID
    logs = contract.events.RecordAdded().process_receipt(receipt)
    record_id = logs[0]["args"]["recordId"] if logs else None
    print(f"  → New record ID: {record_id}")

    # ── 4. Read the record back ────────────────────────────────────────
    if record_id:
        print(f"\n[4] Reading record {record_id} …")
        rec = contract.functions.getRecord(record_id).call(
            {"from": deployer.address}
        )
        print(
            f"  patientName    : {rec[1]}\n"
            f"  dateOfBirth    : {rec[2]}\n"
            f"  diagnosis      : {rec[3]}\n"
            f"  treatment      : {rec[4]}\n"
            f"  currentProvider: {rec[5]}\n"
            f"  createdAt      : {rec[6]}\n"
        )

    # ── 5. Transfer record to Provider B ──────────────────────────────
    if record_id:
        print(f"\n[5] Transferring record {record_id} to Provider B …")
        receipt = send_tx(
            w3,
            deployer,
            contract.functions.transferRecord(record_id, provider_b.address),
        )

    # ── 6. Verify transfer ────────────────────────────────────────────
    if record_id:
        print(f"\n[6] Verifying record {record_id} after transfer …")
        rec = contract.functions.getRecord(record_id).call(
            {"from": provider_b.address}
        )
        print(f"  currentProvider: {rec[5]}  (should be Provider B)")

    # ── 7. Final totalRecords ─────────────────────────────────────────
    total = contract.functions.totalRecords().call()
    print(f"\n[7] Final totalRecords = {total}")
    print("\n Interaction complete.")


if __name__ == "__main__":
    main()
