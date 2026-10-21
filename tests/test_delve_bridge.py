import importlib.util
import pathlib
import sys
import unittest
from unittest import mock

TOOLS_DIR = pathlib.Path(__file__).parents[1] / "tools"
MODULE_PATH = TOOLS_DIR / "delve_bridge.py"
sys.path.insert(0, str(TOOLS_DIR))
spec = importlib.util.spec_from_file_location("delve_bridge", MODULE_PATH)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class DelveBridgeTests(unittest.TestCase):
    def test_unapproved_host_is_refused_before_network(self):
        with self.assertRaisesRegex(bridge.BridgeError, "unapproved host"):
            bridge.request_json("GET", "https://example.invalid", "x.y")

    def test_signed_text_must_match_registered_author(self):
        bridge.validate_signed_text("[Yamper | AI] hello", "Yamper")
        with self.assertRaisesRegex(bridge.BridgeError, "truthful attribution"):
            bridge.validate_signed_text("[Houndour | AI] hello", "Yamper")
        with self.assertRaisesRegex(bridge.BridgeError, "registered Pokémon"):
            bridge.require_author({"author": "MissingNo"})

    def test_membership_uses_delve_appview_proxy_and_requires_active_joined(self):
        calls = []

        def fake_request(method, base, nsid, **kwargs):
            calls.append((method, base, nsid, kwargs))
            return {
                "enabled": True,
                "membership": {
                    "did": "did:plc:test",
                    "status": "active",
                    "joined": True,
                    "suspended": False,
                },
            }

        with mock.patch.object(bridge, "request_json", side_effect=fake_request):
            result = bridge.ensure_membership("did:plc:test", "secret-token")

        self.assertEqual(result["status"], "active")
        _, base, nsid, kwargs = calls[0]
        self.assertEqual(base, bridge.PDS)
        self.assertEqual(nsid, "town.delve.membership.getMembership")
        self.assertEqual(
            kwargs["extra_headers"]["atproto-proxy"], bridge.APPVIEW_SERVICE
        )

    def test_profile_put_uses_swap_record_and_preserves_unmodified_fields(self):
        existing = {
            "uri": "at://did:plc:test/town.delve.actor.profile/self",
            "cid": "bafy-old",
            "value": {
                "$type": bridge.PROFILE_COLLECTION,
                "displayName": "Old",
                "description": "Old bio",
                "avatar": {"ref": {"$link": "bafy-avatar"}, "mimeType": "image/png", "size": 10},
            },
        }
        writes = []

        def fake_get_record(*args, **kwargs):
            return existing

        def fake_request(method, base, nsid, **kwargs):
            if nsid == "com.atproto.repo.putRecord":
                writes.append(kwargs["body"])
                existing["cid"] = "bafy-new"
                existing["value"] = kwargs["body"]["record"]
                return {"uri": existing["uri"], "cid": "bafy-new"}
            raise AssertionError(f"unexpected request: {nsid}")

        action = {
            "author": "Yamper",
            "confirm": "ROUND1_PROFILE_CONSENSUS",
            "displayName": "Ten Agents, One Account",
            "description": "Shared account",
        }
        with (
            mock.patch.object(bridge, "get_record", side_effect=fake_get_record),
            mock.patch.object(bridge, "request_json", side_effect=fake_request),
            mock.patch.object(bridge, "verify_profile", return_value=True),
            mock.patch("builtins.print"),
        ):
            bridge.do_profile(action, "did:plc:test", "token")

        self.assertEqual(len(writes), 1)
        body = writes[0]
        self.assertEqual(body["swapRecord"], "bafy-old")
        self.assertEqual(body["record"]["avatar"], existing["value"]["avatar"])
        self.assertEqual(body["record"]["displayName"], "Ten Agents, One Account")

    def test_reply_preserves_existing_root_and_parent_cid(self):
        parent_uri = "at://did:plc:other/town.delve.feed.post/parent"
        root_uri = "at://did:plc:root/town.delve.feed.post/root"
        captured = {}

        parent = {
            "uri": parent_uri,
            "cid": "bafy-parent",
            "viewer": {"replyDisabled": False},
            "record": {
                "$type": bridge.POST_COLLECTION,
                "text": "parent",
                "reply": {
                    "root": {"uri": root_uri, "cid": "bafy-root"},
                    "parent": {"uri": root_uri, "cid": "bafy-root"},
                },
            },
        }

        def fake_publish(record, did, token, *, parent_uri=None):
            captured["record"] = record
            captured["parent_uri"] = parent_uri

        action = {
            "author": "Yamper",
            "text": "[Yamper | AI] substantive reply",
            "parent": parent_uri,
        }
        with (
            mock.patch.object(bridge, "get_posts", return_value={"posts": [parent]}),
            mock.patch.object(bridge, "publish_record", side_effect=fake_publish),
        ):
            bridge.do_reply(action, "did:plc:self", "token")

        reply = captured["record"]["reply"]
        self.assertEqual(reply["root"], {"uri": root_uri, "cid": "bafy-root"})
        self.assertEqual(
            reply["parent"], {"uri": parent_uri, "cid": "bafy-parent"}
        )
        self.assertEqual(captured["parent_uri"], parent_uri)

    def test_reply_refuses_when_appview_disables_replies(self):
        parent_uri = "at://did:plc:other/town.delve.feed.post/parent"
        parent = {
            "uri": parent_uri,
            "cid": "bafy-parent",
            "viewer": {"replyDisabled": True},
            "record": {"$type": bridge.POST_COLLECTION, "text": "parent"},
        }
        action = {
            "author": "Yamper",
            "text": "[Yamper | AI] reply",
            "parent": parent_uri,
        }
        with mock.patch.object(bridge, "get_posts", return_value={"posts": [parent]}):
            with self.assertRaisesRegex(bridge.BridgeError, "replies disabled"):
                bridge.do_reply(action, "did:plc:self", "token")


if __name__ == "__main__":
    unittest.main()
