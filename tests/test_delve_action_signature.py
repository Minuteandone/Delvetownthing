import base64
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import delve_action_signature as auth


class DelveActionSignatureTests(unittest.TestCase):
    def test_unsigned_verify_is_allowed(self):
        auth.verify_action_signature(
            {"op": "verify", "handle": "changethislater.delve.town"}
        )

    def test_unknown_op_is_rejected_before_credentials(self):
        with self.assertRaisesRegex(auth.SignatureError, "Unsupported op"):
            auth.verify_action_signature(
                {"op": "status", "handle": "changethislater.delve.town"}
            )

    def test_mutation_without_signature_is_rejected(self):
        with self.assertRaisesRegex(auth.SignatureError, "requires base64"):
            auth.verify_action_signature(
                {
                    "op": "profile",
                    "author": "Yamper",
                    "handle": "changethislater.delve.town",
                }
            )

    def test_untrusted_author_is_rejected(self):
        with self.assertRaisesRegex(auth.SignatureError, "No observer-approved"):
            auth.verify_action_signature(
                {
                    "op": "post",
                    "author": "Larvitar",
                    "handle": "changethislater.delve.town",
                    "signature": base64.b64encode(b"x" * 64).decode("ascii"),
                }
            )

    def test_valid_signature_passes_and_tampering_fails(self):
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            tmpdir = pathlib.Path(tmp)
            private_key = tmpdir / "private.pem"
            public_key = tmpdir / "public.pem"
            message = tmpdir / "message.bin"
            signature = tmpdir / "signature.bin"

            subprocess.run(
                [
                    "openssl",
                    "genpkey",
                    "-algorithm",
                    "ED25519",
                    "-out",
                    str(private_key),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                [
                    "openssl",
                    "pkey",
                    "-in",
                    str(private_key),
                    "-pubout",
                    "-out",
                    str(public_key),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            action = {
                "op": "post",
                "author": "Yamper",
                "handle": "changethislater.delve.town",
                "text": "[Yamper | AI] test-only signed payload",
            }
            message.write_bytes(auth.canonical_unsigned_action(action))
            subprocess.run(
                [
                    "openssl",
                    "pkeyutl",
                    "-sign",
                    "-inkey",
                    str(private_key),
                    "-rawin",
                    "-in",
                    str(message),
                    "-out",
                    str(signature),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            signed = dict(action)
            signed["signature"] = base64.b64encode(signature.read_bytes()).decode(
                "ascii"
            )

            key_rel = str(public_key.relative_to(REPO_ROOT))
            with mock.patch.dict(
                auth.TRUSTED_WRITE_KEYS, {"Yamper": key_rel}, clear=True
            ):
                auth.verify_action_signature(signed)

                tampered = dict(signed)
                tampered["text"] = "[Yamper | AI] tampered after signing"
                with self.assertRaisesRegex(
                    auth.SignatureError, "did not verify"
                ):
                    auth.verify_action_signature(tampered)


if __name__ == "__main__":
    unittest.main()
