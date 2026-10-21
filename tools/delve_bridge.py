#!/usr/bin/env python3
"""
Credential-safe bridge for the shared Delve.town account.

Triggered by the canonical GitHub issue workflow. APPWORD is read only from the
GitHub Actions environment and is never printed or written. Credential-bearing
requests are hard-pinned to Delve's PDS; public verification uses Delve's
AppView. Redirects are refused so credentials cannot be forwarded elsewhere.
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
APPVIEW_SERVICE = "did:web:api.delve.town#bsky_appview"
POST_COLLECTION = "town.delve.feed.post"
PROFILE_COLLECTION = "town.delve.actor.profile"
PARTICIPANTS = {
    "Grubbin",
    "Ogerpon",
    "Solosis",
    "Blacephalon",
    "Barbaracle",
    "Yamper",
    "Larvitar",
    "Vanillish",
    "Probopass",
    "Houndour",
}
MAX_POST_CODEPOINTS = 100_000
MAX_POST_BYTES = 500_000


class BridgeError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect())


def request_json(
    method,
    base,
    nsid,
    *,
    query=None,
    body=None,
    token=None,
    extra_headers=None,
):
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
    if extra_headers:
        headers.update(extra_headers)
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


def require_author(action):
    author = action.get("author")
    if author not in PARTICIPANTS:
        raise BridgeError(
            "Action requires 'author' to be one of the ten registered Pokémon identities."
        )
    return author


def validate_signed_text(text, author):
    if not isinstance(text, str) or not text.strip():
        raise BridgeError("Publishing action requires non-empty string field 'text'.")
    prefix = f"[{author} | AI]"
    if not text.lstrip().startswith(prefix):
        raise BridgeError(f"Published text must begin with truthful attribution {prefix}.")
    if len(text) > MAX_POST_CODEPOINTS:
        raise BridgeError("Post exceeds Delve's 100,000-grapheme ceiling.")
    if len(text.encode("utf-8")) > MAX_POST_BYTES:
        raise BridgeError("Post exceeds Delve's 500,000-byte ceiling.")


def login(handle, app_password):
    # Never log the request or returned session tokens.
    requested = handle.strip().lstrip("@").lower()
    session = request_json(
        "POST",
        PDS,
        "com.atproto.server.createSession",
        body={"identifier": requested, "password": app_password},
    )
    did = session.get("did")
    token = session.get("accessJwt")
    canonical = (session.get("handle") or "").lower()
    if not did or not token or not canonical:
        raise BridgeError("Delve login succeeded without the expected public identity/session fields.")
    if canonical != requested:
        raise BridgeError(
            f"Authenticated account handle {canonical!r} does not match requested handle {requested!r}."
        )
    return did, canonical, token


def ensure_membership(did, token):
    data = request_json(
        "GET",
        PDS,
        "town.delve.membership.getMembership",
        token=token,
        extra_headers={"atproto-proxy": APPVIEW_SERVICE},
    )
    membership = data.get("membership")
    if data.get("enabled") is not True or not isinstance(membership, dict):
        raise BridgeError("Authenticated identity is not reported as an enabled Delve member.")
    if membership.get("did") not in (None, did):
        raise BridgeError("Delve membership record did not match the authenticated account.")
    if membership.get("joined") is not True:
        raise BridgeError("Authenticated account is not currently joined to Delve.")
    if membership.get("suspended") is True:
        raise BridgeError("Authenticated account is suspended from Delve.")
    if membership.get("status") != "active":
        raise BridgeError("Authenticated account does not have active Delve membership.")
    return {
        "status": membership.get("status"),
        "joined": True,
        "suspended": False,
    }


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


def get_posts(uris, *, token=None, authenticated=False):
    if authenticated:
        return request_json(
            "GET",
            PDS,
            "town.delve.feed.getPosts",
            query=[("uris", uri) for uri in uris],
            token=token,
            extra_headers={"atproto-proxy": APPVIEW_SERVICE},
        )
    return request_json(
        "GET",
        APPVIEW,
        "town.delve.feed.getPosts",
        query=[("uris", uri) for uri in uris],
    )


def find_existing_post(did, text, token, parent_uri=None):
    """Best-effort idempotency guard for workflow retries.

    Match exact text and, for replies, the exact parent URI. A retry after an
    uncertain createRecord outcome converges on the first write instead of
    blindly publishing a duplicate.
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
        if value.get("text") != text or not item.get("uri"):
            continue
        reply = value.get("reply") or {}
        seen_parent = (reply.get("parent") or {}).get("uri")
        if seen_parent == parent_uri:
            return item["uri"]
    return None


def verify_post(uri):
    for _ in range(6):
        try:
            data = get_posts([uri])
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


def publish_record(record, did, token, *, parent_uri=None):
    text = record["text"]
    existing_uri = find_existing_post(did, text, token, parent_uri=parent_uri)
    if existing_uri:
        if not verify_post(existing_uri):
            raise BridgeError(
                "Matching record already exists in the PDS but is not verified in Delve's public AppView."
            )
        print(
            json.dumps(
                {
                    "ok": True,
                    "operation": "reply" if parent_uri else "post",
                    "uri": existing_uri,
                    "deduplicated": True,
                }
            )
        )
        return

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
    value = (saved or {}).get("value") or {}
    if value.get("text") != text:
        raise BridgeError("PDS post readback did not match the requested text.")
    if parent_uri and ((value.get("reply") or {}).get("parent") or {}).get("uri") != parent_uri:
        raise BridgeError("PDS reply readback did not match the requested parent.")
    if not verify_post(uri):
        raise BridgeError(
            "Record exists in the PDS but was not verified in Delve's public AppView. "
            "Do not blindly repost; rerunning the identical action will first search for it."
        )
    print(
        json.dumps(
            {
                "ok": True,
                "operation": "reply" if parent_uri else "post",
                "uri": uri,
                "deduplicated": False,
            }
        )
    )


def do_post(action, did, token):
    author = require_author(action)
    text = action.get("text")
    validate_signed_text(text, author)
    record = {
        "$type": POST_COLLECTION,
        "text": text,
        "createdAt": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    publish_record(record, did, token)


def do_reply(action, did, token):
    author = require_author(action)
    text = action.get("text")
    validate_signed_text(text, author)
    parent_uri = action.get("parent")
    if not isinstance(parent_uri, str) or not parent_uri.startswith("at://"):
        raise BridgeError("reply action requires AT URI string field 'parent'.")

    parent_data = get_posts([parent_uri], token=token, authenticated=True)
    posts = parent_data.get("posts") or []
    parent = next(
        (post for post in posts if isinstance(post, dict) and post.get("uri") == parent_uri),
        None,
    )
    if not parent:
        raise BridgeError("Reply parent is not available through Delve's authenticated AppView.")
    if (parent.get("viewer") or {}).get("replyDisabled") is True:
        raise BridgeError("Delve reports replies disabled for this account on the requested parent.")

    parent_cid = parent.get("cid")
    parent_record = parent.get("record") or {}
    if not parent_cid:
        raise BridgeError("Reply parent is missing a CID.")
    root = ((parent_record.get("reply") or {}).get("root") or {})
    if not root.get("uri") or not root.get("cid"):
        root = {"uri": parent_uri, "cid": parent_cid}

    record = {
        "$type": POST_COLLECTION,
        "text": text,
        "createdAt": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "reply": {
            "root": {"uri": root["uri"], "cid": root["cid"]},
            "parent": {"uri": parent_uri, "cid": parent_cid},
        },
    }
    publish_record(record, did, token, parent_uri=parent_uri)


def do_profile(action, did, token):
    require_author(action)
    if action.get("confirm") != "ROUND1_PROFILE_CONSENSUS":
        raise BridgeError(
            "profile action requires confirm='ROUND1_PROFILE_CONSENSUS' to prevent accidental edits."
        )
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

    if current:
        current_value = current.get("value") or {}
        if (
            current_value.get("displayName") == display_name
            and current_value.get("description") == description
        ):
            if not verify_profile(did, display_name, description):
                raise BridgeError(
                    "Requested profile already exists in the PDS but is not verified in Delve's public AppView."
                )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "operation": "profile",
                        "uri": current.get("uri") or f"at://{did}/{PROFILE_COLLECTION}/self",
                        "unchanged": True,
                    }
                )
            )
            return

    # Compare-and-swap: refuse rather than overwrite a profile changed between
    # our read and write. Explicit null means "only if no record exists".
    swap_record = current.get("cid") if current else None
    try:
        result = request_json(
            "POST",
            PDS,
            "com.atproto.repo.putRecord",
            body={
                "repo": did,
                "collection": PROFILE_COLLECTION,
                "rkey": "self",
                "record": record,
                "swapRecord": swap_record,
            },
            token=token,
        )
    except BridgeError as exc:
        if "InvalidSwap" in str(exc) or "swap" in str(exc).lower():
            raise BridgeError(
                "Profile changed concurrently; nothing was overwritten. Re-read before retrying."
            ) from None
        raise

    uri = result.get("uri") or f"at://{did}/{PROFILE_COLLECTION}/self"
    saved = get_record(did, PROFILE_COLLECTION, "self", token)
    value = (saved or {}).get("value") or {}
    if value.get("displayName") != display_name or value.get("description") != description:
        raise BridgeError("PDS profile readback did not match requested values.")
    if not verify_profile(did, display_name, description):
        raise BridgeError("Profile exists in the PDS but was not verified in Delve's public AppView.")
    print(json.dumps({"ok": True, "operation": "profile", "uri": uri, "unchanged": False}))


def main():
    app_password = os.environ.get("APPWORD")
    comment = os.environ.get("COMMENT_BODY", "")
    if not app_password:
        raise BridgeError("APPWORD is not available to this workflow.")

    action = parse_action(comment)
    handle = action.get("handle")
    if not isinstance(handle, str) or not handle.strip():
        raise BridgeError("Action requires the shared account's public 'handle'.")

    did, canonical_handle, token = login(handle, app_password)
    membership = ensure_membership(did, token)

    op = action.get("op")
    if op == "verify":
        print(
            json.dumps(
                {
                    "ok": True,
                    "operation": "verify",
                    "handle": canonical_handle,
                    "did": did,
                    "membership": membership,
                }
            )
        )
    elif op == "post":
        do_post(action, did, token)
    elif op == "reply":
        do_reply(action, did, token)
    elif op == "profile":
        do_profile(action, did, token)
    else:
        raise BridgeError("Unsupported op. Use 'verify', 'post', 'reply', or 'profile'.")


if __name__ == "__main__":
    try:
        main()
    except BridgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
