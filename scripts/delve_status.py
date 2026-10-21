#!/usr/bin/env python3
"""Authenticate to the shared Delve PDS without exposing session credentials.

This helper is deliberately read-only. It accepts a public account handle,
uses the app password from DELVE_APP_PASSWORD, and prints only a safe subset
of the AT Protocol session response.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

PDS = os.environ.get("DELVE_PDS", "https://pds.delve.town").rstrip("/")
PASSWORD = os.environ.get("DELVE_APP_PASSWORD", "")

HANDLE_RE = re.compile(r"^[A-Za-z0-9._:-]{3,253}$")


def fail(message: str, code: int = 1) -> None:
    print(json.dumps({"ok": False, "error": message}))
    raise SystemExit(code)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: delve_status.py <public-handle>", 2)

    handle = sys.argv[1].strip()
    if not HANDLE_RE.fullmatch(handle):
        fail("invalid handle syntax", 2)

    if not PASSWORD:
        fail("DELVE_APP_PASSWORD is not set")

    payload = json.dumps(
        {"identifier": handle, "password": PASSWORD}
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{PDS}/xrpc/com.atproto.server.createSession",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "delvetownthing-status-bridge/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        # Never print the response body: authentication failures can include
        # implementation details we do not want copied into public logs.
        fail(f"PDS authentication failed with HTTP {exc.code}")
    except urllib.error.URLError as exc:
        fail(f"PDS connection failed: {exc.reason}")
    except TimeoutError:
        fail("PDS connection timed out")

    safe = {
        "ok": True,
        "handle": data.get("handle"),
        "did": data.get("did"),
        "active": data.get("active"),
        "status": data.get("status"),
        "pds": PDS,
    }
    print(json.dumps(safe, sort_keys=True))


if __name__ == "__main__":
    main()
