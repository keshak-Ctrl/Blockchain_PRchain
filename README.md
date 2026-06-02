# HealthCare Innovations Ltd. — Blockchain Patient Record System
### Designed & implemented by PRChain Solutions Ltd.

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Repository Structure](#2-repository-structure)
3. [Design Choices](#3-design-choices)
4. [Proof-of-Work Explained](#4-proof-of-work-explained)
5. [Consensus Mechanism Explained](#5-consensus-mechanism-explained)
6. [Smart Contract Reference](#6-smart-contract-reference)
7. [Compiling & Deploying the Contract](#7-compiling--deploying-the-contract)
8. [Running the Python Interaction Script](#8-running-the-python-interaction-script)
9. [Running the Test Suite](#9-running-the-test-suite)
10. [Security Considerations](#10-security-considerations)

---

## 1. Project Overview

This system provides HealthCare Innovations Ltd. with a dual-layer blockchain solution:

| Layer | Technology | Purpose |
|---|---|---|
| **Off-chain audit chain** | Python (`blockchain.py`) | Immutable local ledger of all record events, tamper-evident log |
| **On-chain smart contract** | Solidity (`PatientRecordContract.sol`) | Authoritative ownership & access-control layer on Ethereum Sepolia |

Together these ensure **transparency** (every action is logged), **security** (only authorised providers can read/write), and **efficiency** (automated access control replaces manual paperwork).

---

## 2. Repository Structure

```
.
├── blockchain.py              # Python blockchain (Block + Blockchain classes)
├── PatientRecordContract.sol  # Solidity smart contract
├── interact_contract.py       # Python web3.py interaction script
├── test_suite.py              # 29 unit tests (pytest)
└── README.md                  # This document
```

---

## 3. Design Choices

### 3.1 Python Blockchain

| Choice | Rationale |
|---|---|
| **SHA-256** hashing | Industry-standard, collision-resistant, deterministic |
| **JSON-serialised block body** with `sort_keys=True` | Ensures identical hash regardless of dict insertion order |
| **Fixed genesis timestamp** (1 700 000 000) | Reproducible genesis hash; nodes can verify it independently |
| **Difficulty = 4 leading zeros** | Balances demonstration speed (~seconds per block) with meaningful work |
| **Set for peer nodes** | Automatic deduplication of registered peers |
| **`requests` library for consensus** | Lightweight HTTP; production would use async I/O (aiohttp) |

### 3.2 Solidity Smart Contract

| Choice | Rationale |
|---|---|
| **`mapping(uint256 => PatientRecord)`** | O(1) look-up; avoids unbounded array iteration |
| **Auto-incrementing `totalRecords` as ID** | Simple, predictable, gas-cheap |
| **`onlyAuthorised` modifier** | DRY access control — defined once, applied everywhere |
| **Owner-gated `setProviderAuthorisation`** | Centralised trust root; suitable for a regulated healthcare body |
| **Events for every state change** | Enables off-chain indexing (The Graph, ethers.js listeners) and full audit trail at near-zero cost |
| **`bool exists` flag** | Distinguishes a never-created record from a zero-value struct |
| **Solidity ^0.8.20** | Built-in overflow protection; latest stable compiler features |

---

## 4. Proof-of-Work Explained

### What is it?
Proof-of-Work (PoW) is a computational puzzle that a miner must solve before a block is accepted by the network.

### How it works in this implementation

```
Target: hash must begin with N zeros  (N = Blockchain.DIFFICULTY = 4)

Block fields: index + previous_hash + timestamp + data + nonce
                                                           ▲
                                                  The only mutable field

Loop:
  nonce = 0
  while SHA-256(block_fields) does NOT start with "0000":
      nonce += 1
  block.hash = SHA-256(block_fields)   ← accepted!
```

### Why does it provide security?
- **Asymmetry**: Finding the nonce is expensive (CPU/GPU); *verifying* it is instant (single hash).
- **Tamper resistance**: If an attacker changes any field in block *k*, its hash changes, which invalidates block *k+1* (whose `previous_hash` now mismatches), cascading to all subsequent blocks. They must redo PoW for every block *from k onwards* — faster than the honest network.
- **Difficulty adjustment**: In production, difficulty is adjusted every N blocks so that the average mining time remains constant (~10 min for Bitcoin). This implementation uses a fixed difficulty=4 for clarity.

### Example output
```
Nonce=0   → hash=a3f8c...  (no leading zeros)
Nonce=1   → hash=02b4d...  (1 zero — not enough)
...
Nonce=7832 → hash=0000e1a2...  ✓ (4 leading zeros — accepted!)
```

---

## 5. Consensus Mechanism Explained

### What is it?
When multiple blockchain nodes exist, they may temporarily have different chains (network latency, forks). The **Nakamoto consensus rule** resolves disagreements: **the longest valid chain wins**.

### How it works in this implementation

```
resolve_conflicts():
  max_length = len(our_chain)
  best_chain = None

  for each registered peer:
      GET /chain  →  {length, chain}
      if length > max_length AND is_valid_chain(chain):
          max_length = length
          best_chain = chain

  if best_chain:
      our_chain = best_chain   ← we were behind; adopt the longer chain
      return True              ← chain was replaced
  return False                 ← we already have the longest valid chain
```

### Chain validation rules (`is_valid_chain`)
1. **Hash integrity** — each block's stored hash equals its recalculated hash.
2. **Chain linkage** — each `previous_hash` equals the prior block's `hash`.
3. **PoW target** — each hash starts with `DIFFICULTY` zeros.

### Why does this work?
- An attacker controlling < 50 % of the network's compute power cannot outpace the honest majority.
- Longer chains represent more cumulative work → greater economic investment → higher trust.
- Invalid chains are always rejected regardless of length, preventing trivially forged "long" chains.

---

## 6. Smart Contract Reference

### State Variables

| Variable | Type | Description |
|---|---|---|
| `totalRecords` | `uint256` | Count of records ever added (never decrements) |
| `owner` | `address` | Deployer; can authorise/revoke providers |
| `records` | `mapping(uint256 => PatientRecord)` | All patient records, keyed by ID |
| `authorisedProviders` | `mapping(address => bool)` | Access-control whitelist |

### Functions

| Function | Access | Description |
|---|---|---|
| `setProviderAuthorisation(address, bool)` | Owner only | Grant or revoke provider access |
| `addRecord(name, dob, diagnosis, treatment)` | Authorised providers | Mint a new patient record; returns its ID |
| `transferRecord(recordId, toProvider)` | Current holder | Move custody to another authorised provider |
| `getRecord(recordId)` | Authorised providers | Read full record struct |
| `isAuthorised(address)` | Public | Check if an address is a provider |

### Events

| Event | Emitted when |
|---|---|
| `ProviderAuthorised(provider, status)` | Provider whitelist changes |
| `RecordAdded(recordId, patientName, addedBy)` | New record created |
| `RecordTransferred(recordId, from, to)` | Record custody transferred |

---

## 7. Compiling & Deploying the Contract

### Option A — Remix IDE (recommended for Sepolia testnet)

1. Open **https://remix.ethereum.org**
2. Create a new file `PatientRecordContract.sol` and paste the contract code.
3. Go to **Solidity Compiler** tab:
   - Compiler version: `0.8.20` (or latest 0.8.x)
   - Click **Compile PatientRecordContract.sol**
4. Go to **Deploy & Run Transactions** tab:
   - Environment: **Injected Provider – MetaMask**
   - Switch MetaMask to **Sepolia** network
   - Ensure your wallet has Sepolia ETH (faucet: https://sepoliafaucet.com)
   - Select `PatientRecordContract` in the contract dropdown
   - Click **Deploy** → confirm in MetaMask
5. Copy the deployed **contract address** from the Deployed Contracts panel.
6. You can verify on **https://sepolia.etherscan.io** by searching the address.

### Option B — Hardhat (CI/CD friendly)

```bash
# 1. Initialise project
npm init -y
npm install --save-dev hardhat @nomicfoundation/hardhat-toolbox

# 2. Initialise Hardhat
npx hardhat init          # choose "Create a JavaScript project"

# 3. Copy contract
cp PatientRecordContract.sol contracts/

# 4. Write deployment script  scripts/deploy.js
cat > scripts/deploy.js << 'EOF'
const hre = require("hardhat");
async function main() {
  const Contract = await hre.ethers.getContractFactory("PatientRecordContract");
  const contract = await Contract.deploy();
  await contract.waitForDeployment();
  console.log("Deployed to:", await contract.getAddress());
}
main().catch(console.error);
EOF

# 5. Configure hardhat.config.js with your Sepolia RPC URL + private key
# 6. Deploy
npx hardhat run scripts/deploy.js --network sepolia
```

### Option C — Foundry

```bash
forge create --rpc-url $WEB3_PROVIDER_URL \
             --private-key $DEPLOYER_PRIVATE_KEY \
             PatientRecordContract.sol:PatientRecordContract
```

---

## 8. Running the Python Interaction Script

### Prerequisites

```bash
pip install web3 python-dotenv
```

### Environment setup

Create a `.env` file in the project root:

```ini
WEB3_PROVIDER_URL=https://sepolia.infura.io/v3/<YOUR_PROJECT_ID>
DEPLOYER_PRIVATE_KEY=0xabc123...     # owner / Provider A
PROVIDER_B_PRIVATE_KEY=0xdef456...  # second provider
CONTRACT_ADDRESS=0xYourDeployedAddress
```

> **Security**: Never commit `.env` to version control. Add it to `.gitignore`.

### Run

```bash
python interact_contract.py
```

### Expected output

```
✓ Connected to Sepolia  |  Chain ID: 11155111

Deployer   : 0xAAA...
Provider B : 0xBBB...
Contract   : 0xCCC...

[1] Current totalRecords = 0

[2] Authorising Provider B …
  → tx sent: 0x111...
  → mined in block 5432100  [✓ success]

[3] Adding patient record (Provider A) …
  → tx sent: 0x222...
  → mined in block 5432101  [✓ success]
  → New record ID: 1

[4] Reading record 1 …
  patientName    : Alice Wonderland
  dateOfBirth    : 631152000
  diagnosis      : Hypertension
  treatment      : Lisinopril 10mg
  currentProvider: 0xAAA...
  createdAt      : 1700000050

[5] Transferring record 1 to Provider B …
  → tx sent: 0x333...
  → mined in block 5432102  [✓ success]

[6] Verifying record 1 after transfer …
  currentProvider: 0xBBB...  (should be Provider B)

[7] Final totalRecords = 1

✓ Interaction complete.
```

---

## 9. Running the Test Suite

### Requirements

```bash
pip install pytest requests
```

### Run all tests

```bash
python -m pytest test_suite.py -v
```

### Test coverage overview

| Test class | Tests | What is covered |
|---|---|---|
| `TestBlock` | 7 | Hash determinism, sensitivity to inputs, `to_dict` keys/values |
| `TestBlockchain` | 22 | Genesis, PoW correctness, chain linking, index increment, validity rules (tampered data, broken link, invalid PoW), node registration, deduplication, consensus (accept longer, reject shorter, reject tampered, handle network errors), serialisation, `last_block` property |

All 29 tests pass in ~13 seconds (dominated by PoW mining).

---

## 10. Security Considerations

| Risk | Mitigation |
|---|---|
| Private key exposure | Use environment variables / `.env`; never hardcode keys |
| Unauthorised record access | `onlyAuthorised` modifier on all sensitive functions |
| Re-entrancy | No ETH transfers; no external calls within state-changing functions |
| Integer overflow | Solidity ^0.8 built-in checked arithmetic |
| 51 % attack (Python chain) | Longest-chain consensus + PoW difficulty; rotate nodes regularly |
| Smart contract upgradeability | Deploy a new contract and migrate records if upgrades needed; consider OpenZeppelin's `TransparentUpgradeableProxy` for production |
| Sensitive PHI on-chain | In production, store only a hash/IPFS CID on-chain; keep PII in an encrypted off-chain store (HIPAA/GDPR compliance) |
