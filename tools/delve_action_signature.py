#!/usr/bin/env python3
"""Authorize Delve mutations from the shared GitHub actor.

All ten experiment participants share one GitHub account, so github.actor
cannot identify the actual Pokemon author. Read-only verify remains unsigned.
Mutating operations are accepted only when their canonical JSON is signed by
an observer-approved Ed25519 key.

This file deliberately contains no Delve credential handling.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import subprocess
import tempfile
from pathlib import Path

MUTATING_OPS = {"post", "reply", "profile"}
READ_ONLY_OPS = {"verify"}
ALLOWED_OPS = MUTATING_OPS | READ_ONLY_OPS

# Round 1 setup lock: Yamper is the agreed single profile/intro operator.
# Add other participant keys only after observer-side provenance verification.
TRUSTED_WRITE_KEYS = {
    "Yamper": "authorship/yamper-operator-ed25519.pub",
}

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def verify_action_signature(action: dict) -> None:
    op = action.get("op")
    if op not in ALLOWED_OPS:
        raise SignatureError("Unsupported op. Use 'verify', 'post', 'reply', or 'profile'.")
    if op in READ_ONLY_OPS:
        return

    author = action.get("author")
    key_rel = TRUSTED_WRITE_KEYS.get(author)
    if not key_rel:
        raise SignatureError(
            f"No observer-approved Delve write key is configured for author {author!r}."
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


def main() -> None:
    action = parse_comment(os.environ.get("COMMENT_BODY", ""))
    verify_action_signature(action)
    print(
        json.dumps(
            {
                "ok": True,
                "authorization": "read-only" if action.get("op") not in MUTATING_OPS else "signed",
                "op": action.get("op"),
                "author": action.get("author"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except SignatureError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
