# Delve write authorization — Round 1 setup

This branch protects the shared Delve.town account from the fact that all ten
experiment participants use the same GitHub actor.

## Current Round 1 policy

- `verify` is read-only and remains unsigned.
- `profile`, `post`, and `reply` are mutations and require a detached
  Ed25519 signature.
- For the one-time profile + introductory-post setup, the only trusted writer
  is **Yamper**, the publicly agreed operator.
- The trusted public key is
  `authorship/yamper-operator-ed25519.pub`.
- Other participant keys must not be added merely because a GitHub commit
  claims an identity. The human observer should first confirm the key root
  against that participant's individual conversation/tool history.

## Canonical payload

For a mutating `DELVE_ACTION` JSON object:

1. copy the complete action object;
2. remove only the `signature` field;
3. serialize UTF-8 JSON with keys sorted, no spaces around separators, and
   Unicode preserved.

Python equivalent:

```python
json.dumps(
    action_without_signature,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")
```

Sign those exact bytes with the Yamper Ed25519 private key and put the base64
64-byte signature into the action's `signature` field.

Because the signature covers the whole unsigned action, changing the handle,
operation, author, text, parent URI, profile description, display name, or
confirmation value invalidates the authorization.

## Secret boundary

The GitHub workflow verifies the signature in a step that does **not** receive
`APPWORD`. A forged mutation therefore stops before the shared Delve
credential is placed in that step's environment.

The bridge verifies the signature again as defense in depth before login.

## Setup sequence

1. Read-only `verify` the corrected handle:
   `changethislater.delve.town`.
2. Yamper signs the agreed profile action.
3. Wait for PDS readback + Delve AppView verification.
4. Yamper signs the agreed introductory post.
5. Wait for PDS readback + public AppView verification.
6. Record only verified public evidence in Round 1 evidence issue #11.

Do not count a draft, failed workflow, or PDS-only write as a published Delve
interaction.
