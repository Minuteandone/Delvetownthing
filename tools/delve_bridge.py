#!/usr/bin/env python3
"""
Credential-safe bridge for the shared Delve.town account.

Triggered by the canonical GitHub issue workflow. The GitHub Actions secret
APPWORD is read only from the environment and is never printed or written.
Only Delve's fixed PDS/AppView hosts are contacted.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PDS = "https://pds.delve.town"
APPVIEW = "https://api.delve.town"
POST_COLLECTION = "town.delve.feed.post"
PROFILE_COLLECTION = "town.delve.actor.profile"


class BridgeError(RuntimeError):
    pass


def request_json(method, base, nsid, *, query=None, body=None, token=None):
    url = f"{base}/xrpc/{nsid}"
    if query:
        url += "?" + urllib.parse.urlencode(query, doseq=True)
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(raw)
            message = err.get("message") or err.get("error") or f"HTTP {exc.code}"
        except Exception:
            message = f"HTTP {exc.code}"
        raise BridgeError(f"{nsid} failed: {message}") from None
    except urllib.error.URLError as exc:
        raise BridgeError(f"{nsid} network failure: {exc.reason}") from None


def parse_action(comment):
    marker = "DELVE_ACTION"
    lines = comment.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == marker:
            payload = "\n".join(lines[i + 1 :]).strip()
            if not payload:
                raise BridgeError("DELVE_ACTION requires a JSON object on the following text.")
            try:
                action = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise BridgeError(f"Invalid DELVE_ACTION JSON: {exc.msg}") from None
            if not isinstance(action, dict):
                raise BridgeError("DELVE_ACTION payload must be a JSON object.")
            return action
    raise BridgeError("No DELVE_ACTION marker found.")


def login(handle, app_password):
    # Never log the request or returned session tokens.
    session = request_json(
        "POST",
        PDS,
        "com.atproto.server.createSession",
        body={"identifier": handle, "password": app_password},
    )
    did = session.get("did")
    token = session.get("accessJwt")
    if not did or not token:
        raise BridgeError("Delve login succeeded without the expected DID/session token.")
    return did, token


def get_record(did, collection, rkey, token):
    try:
        return request_json(
            "GET",
            PDS,
            "com.atproto.repo.getRecord",
            query={"repo": did, "collection": collection, "rkey": rkey},
            token=token,
        )
    except BridgeError as exc:
        if "RecordNotFound" in str(exc) or "not found" in str(exc).lower():
            return None
        raise


def find_existing_post(did, text, token):
    """Best-effort idempotency guard for workflow retries.

    We scan the most recent 100 records for exact text before creating a new
    post. Signed experiment posts should be unique enough that exact-text
    equality is a safe retry signal.
    """
    try:
        data = request_json(
            "GET",
            PDS,
            "com.atproto.repo.listRecords",
            query={
                "repo": did,
                "collection": POST_COLLECTION,
                "limit": 100,
                "reverse": "true",
            },
            token=token,
        )
    except BridgeError:
        return None
    for item in data.get("records") or []:
        if not isinstance(item, dict):
            continue
        value = item.get("value") or {}
        if value.get("text") == text and item.get("uri"):
            return item["uri"]
    return None


def verify_post(uri):
    for _ in range(6):
        try:
            data = request_json(
                "GET",
                APPVIEW,
                "town.delve.feed.getPosts",
                query=[("uris", uri)],
            )
            posts = data.get("posts") or []
            if any(p.get("uri") == uri for p in posts if isinstance(p, dict)):
                return True
        except BridgeError:
            pass
        time.sleep(5)
    return False


def verify_profile(actor, display_name, description):
    for _ in range(6):
        try:
            data = request_json(
                "GET",
                APPVIEW,
                "town.delve.actor.getProfile",
                query={"actor": actor},
            )
            if (
                data.get("displayName") == display_name
                and data.get("description") == description
            ):
                return True
        except BridgeError:
            pass
        time.sleep(5)
    return False


def do_post(action, did, token):
    text = action.get("text")
    if not isinstance(text, str) or not text.strip():
        raise BridgeError("post action requires non-empty string field 'text'.")

    existing_uri = find_existing_post(did, text, token)
    if existing_uri:
        if not verify_post(existing_uri):
            raise BridgeError(
                "Matching post already exists in the PDS but is not verified in Delve's public AppView."
            )
        print(json.dumps({"ok": True, "operation": "post", "uri": existing_uri, "deduplicated": True}))
        return

    record = {
        "$type": POST_COLLECTION,
        "text": text,
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }
    result = request_json(
        "POST",
        PDS,
        "com.atproto.repo.createRecord",
        body={"repo": did, "collection": POST_COLLECTION, "record": record},
        token=token,
    )
    uri = result.get("uri")
    if not uri:
        raise BridgeError("PDS write returned no post URI.")

    rkey = uri.rsplit("/", 1)[-1]
    saved = get_record(did, POST_COLLECTION, rkey, token)
    if not saved or (saved.get("value") or {}).get("text") != text:
        raise BridgeError("PDS post readback did not match the requested text.")
    if not verify_post(uri):
        raise BridgeError("Post exists in the PDS but was not verified in Delve's public AppView.")
    print(json.dumps({"ok": True, "operation": "post", "uri": uri, "deduplicated": False}))


def do_profile(action, did, token):
    display_name = action.get("displayName")
    description = action.get("description")
    if not isinstance(display_name, str) or not display_name.strip():
        raise BridgeError("profile action requires non-empty string field 'displayName'.")
    if not isinstance(description, str):
        raise BridgeError("profile action requires string field 'description'.")

    current = get_record(did, PROFILE_COLLECTION, "self", token)
    record = dict((current or {}).get("value") or {})
    record["$type"] = PROFILE_COLLECTION
    record["displayName"] = display_name
    record["description"] = description

    result = request_json(
        "POST",
        PDS,
        "com.atproto.repo.putRecord",
        body={
            "repo": did,
            "collection": PROFILE_COLLECTION,
            "rkey": "self",
            "record": record,
        },
        token=token,
    )
    uri = result.get("uri") or f"at://{did}/{PROFILE_COLLECTION}/self"
    saved = get_record(did, PROFILE_COLLECTION, "self", token)
    value = (saved or {}).get("value") or {}
    if value.get("displayName") != display_name or value.get("description") != description:
        raise BridgeError("PDS profile readback did not match requested values.")
    if not verify_profile(did, display_name, description):
        raise BridgeError("Profile exists in the PDS but was not verified in Delve's public AppView.")
    print(json.dumps({"ok": True, "operation": "profile", "uri": uri}))


def main():
    app_password = os.environ.get("APPWORD")
    comment = os.environ.get("COMMENT_BODY", "")
    if not app_password:
        raise BridgeError("APPWORD is not available to this workflow.")
    action = parse_action(comment)
    handle = action.get("handle")
    if not isinstance(handle, str) or not handle.strip():
        raise BridgeError("Action requires the shared account's public 'handle'.")

    did, token = login(handle.strip(), app_password)
    op = action.get("op")
    if op == "post":
        do_post(action, did, token)
    elif op == "profile":
        do_profile(action, did, token)
    else:
        raise BridgeError("Unsupported op. Use 'post' or 'profile'.")


if __name__ == "__main__":
    try:
        main()
    except BridgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
