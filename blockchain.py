import hashlib
import json
import time
import requests
from typing import List, Optional


# ─────────────────────────────────────────────
#  Block
# ─────────────────────────────────────────────
class Block:

    def __init__(
        self,
        index: int,
        previous_hash: str,
        timestamp: float,
        data: dict,
        nonce: int = 0,
    ):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.data = data
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        """SHA-256 hash of all block fields."""
        block_string = json.dumps(
            {
                "index": self.index,
                "previous_hash": self.previous_hash,
                "timestamp": self.timestamp,
                "data": self.data,
                "nonce": self.nonce,
            },
            sort_keys=True,
        ).encode()

        return hashlib.sha256(block_string).hexdigest()

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "data": self.data,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    def __repr__(self):
        return (
            f"Block(index={self.index}, "
            f"hash={self.hash[:12]}..., "
            f"nonce={self.nonce})"
        )


# ─────────────────────────────────────────────
#  Blockchain
# ─────────────────────────────────────────────
class Blockchain:

    DIFFICULTY = 4

    def __init__(self):
        self.chain: List[Block] = []
        self.nodes = set()
        self._create_genesis_block()

    def _create_genesis_block(self):
        genesis = Block(
            index=0,
            previous_hash="0" * 64,
            timestamp=1700000000.0,
            data={
                "message": "Genesis Block — HealthCare Innovations Ltd."
            },
            nonce=0,
        )

        self.chain.append(genesis)

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, block):
        target = "0" * self.DIFFICULTY

        block.nonce = 0
        block.hash = block.calculate_hash()

        while not block.hash.startswith(target):
            block.nonce += 1
            block.hash = block.calculate_hash()

        return block

    def add_block(self, data):
        new_block = Block(
            index=len(self.chain),
            previous_hash=self.last_block.hash,
            timestamp=time.time(),
            data=data,
        )

        self.proof_of_work(new_block)
        self.chain.append(new_block)

        return new_block

    def is_valid_chain(self, chain):
        target = "0" * self.DIFFICULTY

        for i in range(1, len(chain)):
            current = chain[i]
            previous = chain[i - 1]

            if current.hash != current.calculate_hash():
                return False

            if current.previous_hash != previous.hash:
                return False

            if not current.hash.startswith(target):
                return False

        return True

    def register_node(self, address):
        self.nodes.add(address.rstrip("/"))

    def resolve_conflicts(self):
        longest_chain = None
        max_length = len(self.chain)

        for node in self.nodes:
            try:
                response = requests.get(
                    f"{node}/chain",
                    timeout=5
                )

                if response.status_code != 200:
                    continue

                payload = response.json()
                length = payload["length"]
                raw_chain = payload["chain"]

                peer_chain = [
                    Block(
                        index=b["index"],
                        previous_hash=b["previous_hash"],
                        timestamp=b["timestamp"],
                        data=b["data"],
                        nonce=b["nonce"],
                    )
                    for b in raw_chain
                ]

                for b, raw in zip(peer_chain, raw_chain):
                    b.hash = raw["hash"]

                if (
                    length > max_length
                    and self.is_valid_chain(peer_chain)
                ):
                    max_length = length
                    longest_chain = peer_chain

            except Exception as e:
                print(f"Could not reach node {node}: {e}")

        if longest_chain:
            self.chain = longest_chain
            return True

        return False

    def to_dict(self):
        return {
            "length": len(self.chain),
            "chain": [b.to_dict() for b in self.chain],
        }


# ─────────────────────────────────────────────
#  MAIN PROGRAM
# ─────────────────────────────────────────────
if __name__ == "__main__":

    print("\nCreating Blockchain...\n")

    blockchain = Blockchain()

    print("Mining Block 1...")
    blockchain.add_block(
        {
            "patient_id": "P001",
            "patient_name": "Haku Kim",
            "diagnosis": "Hypertension",
            "doctor": "Dr. Ming",
        }
    )

    print("Mining Block 2...")
    blockchain.add_block(
        {
            "patient_id": "P002",
            "patient_name": "Sarah Cheng",
            "diagnosis": "Diabetes",
            "doctor": "Dr. Taylor",
        }
    )

    print("Mining Block 3...")
    blockchain.add_block(
        {
            "patient_id": "P003",
            "patient_name": "Michael Lee",
            "diagnosis": "Asthma",
            "doctor": "Dr. Johnson",
        }
    )

    print("\n" + "=" * 100)
    print("PYTHON BLOCKCHAIN OUTPUT — BLOCK HASHES PRINTED TO TERMINAL")
    print("=" * 100)

    for block in blockchain.chain:
        print(f"\nBlock Index      : {block.index}")
        print(f"Timestamp        : {block.timestamp}")
        print(f"Nonce            : {block.nonce}")
        print(f"Previous Hash    : {block.previous_hash}")
        print(f"Current Hash     : {block.hash}")
        print(f"Data             : {json.dumps(block.data, indent=4)}")
        print("-" * 100)

    print("\nBlockchain Valid:", blockchain.is_valid_chain(blockchain.chain))