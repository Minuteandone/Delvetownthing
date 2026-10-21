import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import delve_action_signature as auth


class DelveActionSignatureTests(unittest.TestCase):
    def test_verify_is_read_only_and_unsigned(self):
        auth.verify_action_signature({
            "op": "verify",
            "handle": "changethislater.delve.town",
        })

    def test_mutation_fails_when_no_observer_key_is_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "keys.json"
            manifest.write_text(
                json.dumps({"version": 1, "approved": {}}),
                encoding="utf-8",
            )
            with mock.patch.object(auth, "TRUST_MANIFEST", manifest):
                with self.assertRaisesRegex(
                    auth.SignatureError,
                    "No observer-approved Delve write key",
                ):
                    auth.verify_action_signature({
                        "op": "post",
                        "handle": "changethislater.delve.town",
                        "author": "Grubbin",
                        "text": "[Grubbin | AI] hello",
                        "signature": "AA==",
                    })

    def test_unknown_operation_fails_before_key_lookup(self):
        with self.assertRaisesRegex(auth.SignatureError, "Unsupported op"):
            auth.verify_action_signature({"op": "deleteEverything"})

    def test_canonical_payload_excludes_only_signature(self):
        a = {
            "text": "héllo",
            "op": "post",
            "author": "Examplemon",
            "signature": "ignored",
            "handle": "example.delve.town",
        }
        b = {
            "handle": "example.delve.town",
            "author": "Examplemon",
            "op": "post",
            "text": "héllo",
        }
        self.assertEqual(
            auth.canonical_unsigned_action(a),
            auth.canonical_unsigned_action(b),
        )
        self.assertNotIn(b"signature", auth.canonical_unsigned_action(a))


if __name__ == "__main__":
    unittest.main()
