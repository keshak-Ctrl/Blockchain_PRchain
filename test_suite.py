"""

Test cases for:
  1. Block class (hash calculation, serialisation)
  2. Blockchain class (genesis, mining, PoW, chain validity, consensus)

Run with:
    python -m pytest test_suite.py -v
    # or simply:
    python test_suite.py
"""

import hashlib
import json
import time
import unittest
from unittest.mock import MagicMock, patch

from blockchain import Block, Blockchain


# ─────────────────────────────────────────────
#  Block Tests
# ─────────────────────────────────────────────
class TestBlock(unittest.TestCase):

    def _make_block(self, index=1, prev="0" * 64, data=None, nonce=0):
        return Block(
            index=index,
            previous_hash=prev,
            timestamp=1_700_000_001.0,
            data=data or {"msg": "test"},
            nonce=nonce,
        )

    # ── hash calculation ───────────────────────────────────────────────
    def test_hash_is_sha256_hex(self):
        block = self._make_block()
        self.assertEqual(len(block.hash), 64)
        # Must be valid hex
        int(block.hash, 16)

    def test_same_input_same_hash(self):
        b1 = self._make_block()
        b2 = self._make_block()
        self.assertEqual(b1.hash, b2.hash)

    def test_different_nonce_different_hash(self):
        b1 = self._make_block(nonce=0)
        b2 = self._make_block(nonce=1)
        self.assertNotEqual(b1.hash, b2.hash)

    def test_different_data_different_hash(self):
        b1 = self._make_block(data={"a": 1})
        b2 = self._make_block(data={"a": 2})
        self.assertNotEqual(b1.hash, b2.hash)

    def test_calculate_hash_matches_stored_hash(self):
        block = self._make_block()
        self.assertEqual(block.hash, block.calculate_hash())

    # ── serialisation ─────────────────────────────────────────────────
    def test_to_dict_keys(self):
        block = self._make_block()
        d = block.to_dict()
        self.assertSetEqual(
            set(d.keys()),
            {"index", "previous_hash", "timestamp", "data", "nonce", "hash"},
        )

    def test_to_dict_values(self):
        block = self._make_block(index=3)
        d = block.to_dict()
        self.assertEqual(d["index"], 3)
        self.assertEqual(d["hash"], block.hash)


# ─────────────────────────────────────────────
#  Blockchain Tests
# ─────────────────────────────────────────────
class TestBlockchain(unittest.TestCase):

    def setUp(self):
        self.bc = Blockchain()

    # ── genesis ────────────────────────────────────────────────────────
    def test_genesis_block_exists(self):
        self.assertEqual(len(self.bc.chain), 1)

    def test_genesis_index_zero(self):
        self.assertEqual(self.bc.chain[0].index, 0)

    def test_genesis_prev_hash_is_zeros(self):
        self.assertEqual(self.bc.chain[0].previous_hash, "0" * 64)

    def test_genesis_data_contains_message(self):
        self.assertIn("message", self.bc.chain[0].data)

    # ── proof-of-work ──────────────────────────────────────────────────
    def test_mined_block_has_valid_pow(self):
        new_block = self.bc.add_block({"record": "test"})
        target = "0" * Blockchain.DIFFICULTY
        self.assertTrue(
            new_block.hash.startswith(target),
            f"Hash {new_block.hash} does not start with '{target}'",
        )

    def test_pow_hash_is_consistent_with_nonce(self):
        block = self.bc.add_block({"x": 1})
        self.assertEqual(block.hash, block.calculate_hash())

    # ── add_block ──────────────────────────────────────────────────────
    def test_add_block_increments_chain(self):
        self.bc.add_block({"a": 1})
        self.bc.add_block({"b": 2})
        self.assertEqual(len(self.bc.chain), 3)  # genesis + 2

    def test_new_block_links_to_previous(self):
        b1 = self.bc.add_block({"n": 1})
        b2 = self.bc.add_block({"n": 2})
        self.assertEqual(b2.previous_hash, b1.hash)

    def test_block_index_increments(self):
        b1 = self.bc.add_block({})
        b2 = self.bc.add_block({})
        self.assertEqual(b1.index, 1)
        self.assertEqual(b2.index, 2)

    # ── is_valid_chain ─────────────────────────────────────────────────
    def test_fresh_chain_is_valid(self):
        self.bc.add_block({"r": 1})
        self.assertTrue(self.bc.is_valid_chain(self.bc.chain))

    def test_tampered_data_invalidates_chain(self):
        self.bc.add_block({"record": "original"})
        # Tamper silently (don't recalculate hash)
        self.bc.chain[1].data = {"record": "tampered"}
        self.assertFalse(self.bc.is_valid_chain(self.bc.chain))

    def test_tampered_prev_hash_invalidates_chain(self):
        self.bc.add_block({})
        self.bc.add_block({})
        # Break the linkage
        self.bc.chain[2].previous_hash = "deadbeef" * 8
        self.assertFalse(self.bc.is_valid_chain(self.bc.chain))

    def test_invalid_pow_invalidates_chain(self):
        self.bc.add_block({})
        block = self.bc.chain[1]
        # Force a hash that doesn't meet PoW target
        block.nonce = 999_999_999
        block.hash = block.calculate_hash()
        # The hash won't start with DIFFICULTY zeros with overwhelming probability
        result = self.bc.is_valid_chain(self.bc.chain)
        target = "0" * Blockchain.DIFFICULTY
        if not block.hash.startswith(target):
            self.assertFalse(result)

    # ── node registration ──────────────────────────────────────────────
    def test_register_node(self):
        self.bc.register_node("http://127.0.0.1:5001")
        self.assertIn("http://127.0.0.1:5001", self.bc.nodes)

    def test_register_node_strips_trailing_slash(self):
        self.bc.register_node("http://127.0.0.1:5001/")
        self.assertIn("http://127.0.0.1:5001", self.bc.nodes)

    def test_duplicate_nodes_deduplicated(self):
        self.bc.register_node("http://127.0.0.1:5001")
        self.bc.register_node("http://127.0.0.1:5001")
        self.assertEqual(len(self.bc.nodes), 1)

    # ── consensus ──────────────────────────────────────────────────────
    def test_resolve_conflicts_accepts_longer_valid_chain(self):
        """
        Simulate a peer that has a longer valid chain; our node should adopt it.
        """
        # Build a longer chain using a separate Blockchain instance
        peer_bc = Blockchain()
        peer_bc.add_block({"r": 1})
        peer_bc.add_block({"r": 2})
        peer_bc.add_block({"r": 3})

        peer_payload = peer_bc.to_dict()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = peer_payload

        self.bc.register_node("http://peer:5000")
        with patch("requests.get", return_value=mock_response):
            replaced = self.bc.resolve_conflicts()

        self.assertTrue(replaced)
        self.assertEqual(len(self.bc.chain), len(peer_bc.chain))

    def test_resolve_conflicts_rejects_shorter_chain(self):
        """Our chain is already longer; it should NOT be replaced."""
        self.bc.add_block({"r": 1})
        self.bc.add_block({"r": 2})

        # Peer has only genesis
        short_bc = Blockchain()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = short_bc.to_dict()

        self.bc.register_node("http://peer:5000")
        with patch("requests.get", return_value=mock_response):
            replaced = self.bc.resolve_conflicts()

        self.assertFalse(replaced)

    def test_resolve_conflicts_rejects_tampered_chain(self):
        """A longer but invalid chain from a peer must be rejected."""
        peer_bc = Blockchain()
        peer_bc.add_block({"r": 1})
        # Tamper with a block
        peer_bc.chain[1].data = {"r": "evil"}   # hash now invalid

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = peer_bc.to_dict()

        self.bc.register_node("http://evil-peer:5000")
        with patch("requests.get", return_value=mock_response):
            replaced = self.bc.resolve_conflicts()

        self.assertFalse(replaced)

    def test_resolve_conflicts_handles_network_error(self):
        """Network errors from peers must not crash the node."""
        import requests as req
        self.bc.register_node("http://unreachable:5000")
        with patch("requests.get", side_effect=req.exceptions.ConnectionError):
            replaced = self.bc.resolve_conflicts()
        self.assertFalse(replaced)

    # ── serialisation ─────────────────────────────────────────────────
    def test_to_dict_structure(self):
        self.bc.add_block({"x": 42})
        d = self.bc.to_dict()
        self.assertIn("length", d)
        self.assertIn("chain", d)
        self.assertEqual(d["length"], 2)

    # ── last_block property ────────────────────────────────────────────
    def test_last_block_is_most_recent(self):
        b = self.bc.add_block({"last": True})
        self.assertEqual(self.bc.last_block.hash, b.hash)


# ─────────────────────────────────────────────
#  Entry-point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestBlock))
    suite.addTests(loader.loadTestsFromTestCase(TestBlockchain))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    exit(0 if result.wasSuccessful() else 1)
