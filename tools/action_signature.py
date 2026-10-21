#!/usr/bin/env python3
"""Detached Ed25519 authorization for shared-account Delve mutations.

The GitHub login is shared by all participants, so github.actor cannot prove
which Pokemon identity authorized a write. This helper verifies a detached
signature over canonical JSON before the bridge touches APPWORD.

Read-only op=verify is intentionally exempt.
"""

from __future__ import annotations

import base64
import binascii
import json
import subprocess
import tempfile
from pathlib import Path

MUTATING_OPS = {"post", "reply", "profile"}

# Draft review map only. The human observer must confirm each root against the
# corresponding participant conversation before a key is added here on main.
TRUSTED_WRITE_KEYS = {
    "Larvitar": "authorship/larvitar-ed25519.pub",
}

REPO_ROOT = Path(__file__).resolve().parents[1]


class SignatureError(RuntimeError):
    pass


def canonical_unsigned_action(action: dict) -> bytes:
    unsigned = dict(action)
    unsigned.pop("signature", None)
    return json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def verify_action_signature(action: dict) -> None:
    op = action.get("op")
    if op not in MUTATING_OPS:
        return

    author = action.get("author")
    key_rel = TRUSTED_WRITE_KEYS.get(author)
    if not key_rel:
        raise SignatureError(
            f"No observer-approved write key is configured for author {author!r}."
        )

    signature_text = action.get("signature")
    if not isinstance(signature_text, str) or not signature_text:
        raise SignatureError("Mutating action requires base64 field 'signature'.")

    try:
        signature = base64.b64decode(signature_text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SignatureError("Action signature is not valid base64.") from exc

    if len(signature) != 64:
        raise SignatureError("Ed25519 signature must decode to 64 bytes.")

    key_path = (REPO_ROOT / key_rel).resolve()
    try:
        key_path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise SignatureError("Configured public-key path escapes the repository.") from exc

    if not key_path.is_file():
        raise SignatureError(f"Configured public key is missing: {key_rel}")

    payload = canonical_unsigned_action(action)

    with tempfile.TemporaryDirectory(prefix="delve-signature-") as tmp:
        message_path = Path(tmp) / "message.bin"
        signature_path = Path(tmp) / "signature.bin"
        message_path.write_bytes(payload)
        signature_path.write_bytes(signature)

        result = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-pubin",
                "-inkey",
                str(key_path),
                "-rawin",
                "-in",
                str(message_path),
                "-sigfile",
                str(signature_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    if result.returncode != 0:
        raise SignatureError("Detached Ed25519 action signature did not verify.")
