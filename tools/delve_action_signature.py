#!/usr/bin/env python3
"""Pre-credential authorization for Delve mutations.

All ten experiment participants share one GitHub actor, so github.actor and a
typed author field cannot identify the real participant. Read-only verify
actions remain unsigned. Mutations require an Ed25519 signature from a key that
the human observer has explicitly approved in authorship/delve-write-keys.json.

This module does not read APPWORD or contact Delve.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import subprocess
import tempfile
from pathlib import Path

MUTATING_OPS = {"post", "reply", "profile"}
READ_ONLY_OPS = {"verify"}
ALLOWED_OPS = MUTATING_OPS | READ_ONLY_OPS
REPO_ROOT = Path(__file__).resolve().parents[1]
TRUST_MANIFEST = REPO_ROOT / "authorship" / "delve-write-keys.json"


class SignatureError(RuntimeError):
    pass


def parse_comment(comment: str) -> dict:
    lines = comment.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "DELVE_ACTION":
            payload = "\n".join(lines[i + 1 :]).strip()
            if not payload:
                raise SignatureError("DELVE_ACTION requires a JSON object.")
            try:
                action = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise SignatureError(f"Invalid DELVE_ACTION JSON: {exc.msg}") from None
            if not isinstance(action, dict):
                raise SignatureError("DELVE_ACTION payload must be a JSON object.")
            return action
    raise SignatureError("No DELVE_ACTION marker found.")


def canonical_unsigned_action(action: dict) -> bytes:
    unsigned = dict(action)
    unsigned.pop("signature", None)
    return json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _load_manifest() -> dict:
    try:
        manifest = json.loads(TRUST_MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SignatureError("Observer-approved Delve write-key manifest is missing.") from exc
    except json.JSONDecodeError as exc:
        raise SignatureError("Observer-approved Delve write-key manifest is invalid JSON.") from exc
    approved = manifest.get("approved")
    if not isinstance(approved, dict):
        raise SignatureError("Delve write-key manifest requires object field 'approved'.")
    return approved


def _approved_key(author: str) -> Path:
    entry = _load_manifest().get(author)
    if not isinstance(entry, dict):
        raise SignatureError(
            f"No observer-approved Delve write key is configured for author {author!r}."
        )
    rel = entry.get("public_key")
    expected = entry.get("file_sha256")
    if not isinstance(rel, str) or not rel:
        raise SignatureError(f"Approved key entry for {author!r} has no public_key path.")
    if not isinstance(expected, str) or len(expected) != 64:
        raise SignatureError(f"Approved key entry for {author!r} has no valid file_sha256.")

    path = (REPO_ROOT / rel).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise SignatureError("Configured public-key path escapes the repository.") from exc
    if not path.is_file():
        raise SignatureError(f"Configured public key is missing: {rel}")

    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if not hmac.compare_digest(actual.lower(), expected.lower()):
        raise SignatureError(
            f"Approved public key fingerprint mismatch for {author!r}; refusing write."
        )
    return path


def verify_action_signature(action: dict) -> None:
    op = action.get("op")
    if op not in ALLOWED_OPS:
        raise SignatureError("Unsupported op. Use 'verify', 'post', 'reply', or 'profile'.")
    if op in READ_ONLY_OPS:
        return

    author = action.get("author")
    if not isinstance(author, str) or not author:
        raise SignatureError("Mutating action requires string field 'author'.")
    key_path = _approved_key(author)

    signature_text = action.get("signature")
    if not isinstance(signature_text, str) or not signature_text:
        raise SignatureError("Mutating action requires base64 field 'signature'.")
    try:
        signature = base64.b64decode(signature_text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SignatureError("Action signature is not valid base64.") from exc
    if len(signature) != 64:
        raise SignatureError("Ed25519 signature must decode to 64 bytes.")

    payload = canonical_unsigned_action(action)
    with tempfile.TemporaryDirectory(prefix="delve-signature-") as tmp:
        message_path = Path(tmp) / "message.bin"
        signature_path = Path(tmp) / "signature.bin"
        message_path.write_bytes(payload)
        signature_path.write_bytes(signature)
        result = subprocess.run(
            [
                "openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(key_path),
                "-rawin", "-in", str(message_path), "-sigfile", str(signature_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    if result.returncode != 0:
        raise SignatureError("Detached Ed25519 action signature did not verify.")


def main() -> None:
    action = parse_comment(os.environ.get("COMMENT_BODY", ""))
    verify_action_signature(action)
    print(json.dumps({
        "ok": True,
        "authorization": "read-only" if action.get("op") in READ_ONLY_OPS else "signed",
        "op": action.get("op"),
        "author": action.get("author"),
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SignatureError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
