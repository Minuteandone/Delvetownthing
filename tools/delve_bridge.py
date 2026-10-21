#!/usr/bin/env python3
"""
Credential-safe bridge for the shared Delve.town account.

Triggered by the canonical GitHub issue workflow. The GitHub Actions secret
APPWORD is read only from the environment and is never printed or written.
Only Delve's fixed PDS/AppView hosts are contacted. Authenticated requests
refuse redirects.
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
APPVIEW_PROXY = "did:web:api.delve.town#bsky_appview"
POST_COLLECTION = "town.delve.feed.post"
PROFILE_COLLECTION = "town.delve.actor.profile"


class BridgeError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect())


def request_json(method, base, nsid, *, query=None, body=None, token=None, proxy=None):
    if base not in {PDS, APPVIEW}:
        raise BridgeError("Refusing request to an unapproved host.")
    url = f"{base}/xrpc/{nsid}"
    if query:
        url += "?" + urllib.parse.urlencode(query, doseq=True)
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if proxy:
        headers["Atproto-Proxy"] = proxy
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with OPENER.open(req, timeout=20) as resp:
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
    returned_handle = session.get("handle") or handle
    if not did or not token:
        raise BridgeError("Delve login succeeded without the expected DID/session token.")
    return returned_handle, did, token


def get_membership(token):
    # Delve membership is an application read. Route it through the account's
    # PDS with the Delve AppView proxy header, matching Delve/ATProto guidance.
    return request_json(
        "GET",
        PDS,
        "town.delve.membership.getMembership",
        token=token,
        proxy=APPVIEW_PROXY,
    )


def ensure_membership(did, token):
    data = get_membership(token)
    enabled = data.get("enabled")
    membership = data.get("membership")
    if enabled is False:
        return data
    if not isinstance(membership, dict):
        raise BridgeError("Delve membership is enabled but no membership record was found.")
    if membership.get("did") not in (None, did):
        raise BridgeError("Delve membership record did not match the authenticated account.")
    if membership.get("joined") is not True:
        raise BridgeError("Authenticated account is not currently joined to Delve.")
    if membership.get("suspended") is True:
        raise BridgeError("Authenticated account is suspended from Delve.")
    if membership.get("status") not in (None, "active"):
        raise BridgeError("Authenticated account does not have active Delve membership.")
    return data


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

    Post records use TID keys, whose normal collection order is chronological.
    reverse=true therefore scans newest-first, which is what retry protection wants.
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


def verify_post(uri, expected_did, expected_text):
    """Verify the exact post identity and content in Delve's public AppView."""
    for _ in range(6):
        try:
            data = request_json(
                "GET",
                APPVIEW,
                "town.delve.feed.getPosts",
                query=[("uris", uri)],
            )
            posts = data.get("posts") or []
            for post in posts:
                if not isinstance(post, dict) or post.get("uri") != uri:
                    continue
                author = post.get("author") or {}
                record = post.get("record") or {}
                if author.get("did") == expected_did and record.get("text") == expected_text:
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
                data.get("did") in (None, actor)
                and data.get("displayName") == display_name
                and data.get("description") == description
            ):
                return True
        except BridgeError:
            pass
        time.sleep(5)
    return False


def do_status(handle, did, token):
    membership = get_membership(token)
    safe_membership = membership.get("membership")
    if isinstance(safe_membership, dict):
        safe_membership = {
            key: safe_membership.get(key)
            for key in ("did", "status", "suspended", "revision", "joined")
            if key in safe_membership
        }
    print(
        json.dumps(
            {
                "ok": True,
                "operation": "status",
                "handle": handle,
                "did": did,
                "pds": PDS,
                "membership": {
                    "enabled": membership.get("enabled"),
                    "membership": safe_membership,
                },
            },
            sort_keys=True,
        )
    )


def do_post(action, did, token):
    text = action.get("text")
    if not isinstance(text, str) or not text.strip():
        raise BridgeError("post action requires non-empty string field 'text'.")

    existing_uri = find_existing_post(did, text, token)
    if existing_uri:
        if not verify_post(existing_uri, did, text):
            raise BridgeError(
                "Matching post already exists in the PDS at "
                f"{existing_uri} but is not verified in Delve's public AppView. "
                "Do not retry by creating another post."
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
        raise BridgeError(f"PDS post readback at {uri} did not match the requested text.")
    if not verify_post(uri, did, text):
        raise BridgeError(
            f"Post exists in the PDS at {uri} but was not verified in Delve's public AppView. "
            "Treat this URI as pending and do not retry by creating another post."
        )
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
            "swapRecord": (current or {}).get("cid"),
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

    returned_handle, did, token = login(handle.strip(), app_password)

    op = action.get("op")
    if op == "status":
        do_status(returned_handle, did, token)
    elif op == "post":
        ensure_membership(did, token)
        do_post(action, did, token)
    elif op == "profile":
        ensure_membership(did, token)
        do_profile(action, did, token)
    else:
        raise BridgeError("Unsupported op. Use 'status', 'post', or 'profile'.")


if __name__ == "__main__":
    try:
        main()
    except BridgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
