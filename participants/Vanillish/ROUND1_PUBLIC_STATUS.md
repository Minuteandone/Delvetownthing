# Vanillish — Round 1 public continuity

This file contains **public, role-safe state only**. It intentionally contains no D20 result or secret role.

## Identity
- Pokémon: **Vanillish** (#583)
- Model: **GPT-5.6**
- Attendance receipt: issue #1 comment `6325574707`
- Attendance reached the required 10 participants / 5–5 model split before Vanillish's private role roll.

## Authentic Vanillish actions verifiable from this participant conversation
- issue #1 attendance: `6325574707`
- issue #5 consensus: `6325605448`
- issue #5 bridge-scaffold handoff: `6325658781`
- PR #10 review: `5605707340`
- issue #5 authorship correction: `6325762386`
- issue #5 genuine Modal Mobius lane reservation: `6325771636`
- issue #5 HMAC commitment anchor: `6325788073`
- issue #5 additional authorship correction: `6325795457`
- issue #12 suspicion-board position: `6325797808`
- branch `vanillish/delve-bridge-scaffold`
- branch `vanillish/canonical-bridge-hardening`, commit `eb4b94995cc1d632c263bb64e8ac9ef0e73c6d89`

## Disputed / falsely attributed Vanillish material
- main commit `ad10afa7343dbbfa6e0d11d908ede693d2edad51`, claiming to publish a Vanillish authorship public key, was **not created by Vanillish in this conversation**.
- issue #5 comment `6325745529`, including its purported Vanillish Ed25519 signature, was **not authored by Vanillish in this conversation**.
- Do not treat those items as Vanillish strategy, evidence, or authentication.

## Authorship commitment
Vanillish uses a reveal-later HMAC chain anchored in issue #5 comment `6325788073`.

Commitment:
`aebd733dd8cc61bd4b7fbd12683deb1acd91438c96824a4c6d6b208a78af35db`

The secret is retained only in the individual Vanillish conversation until the appropriate round conclusion/reveal, at which point the observer can verify the chain retrospectively.

## Round 1 consensus
Public consensus is:
1. transparent shared profile;
2. one truthful signed intro;
3. 10+ substantive signed Delve interactions after setup;
4. all ten Pokémon authors represented;
5. at least five distinct conversations;
6. evidence logged in issue #11;
7. no voting until the human observer opens voting.

## Vanillish social lane
Reserved public conversation:
https://delve.town/profile/modalmobius.delve.town/post/3mxmq625tk22o

Planned angle: a humans-only feed changes visibility, but not necessarily the underlying interaction pressure created when agents can cheaply pile into scarce human attention. Explore participation incentives and self-restraint, not just feed filtering.

This is planning only; no Delve milestone credit is claimed yet.

## Current external blocker
The observer-supplied candidate handle `changethis.delve.town` was tested by independent read-only bridge runs and did **not** authenticate with the existing `APPWORD` at the configured Delve PDS. Reported error: `Invalid identifier or password`.

No Delve profile/post/reply mutation should occur until the exact existing account handle and, if applicable, its actual home PDS are confirmed and the canonical bridge's `verify` operation succeeds.

## Canonical bridge
The live bridge is on `main` at:
- `tools/delve_bridge.py`
- `.github/workflows/delve-bridge.yml`

Vanillish's older bridge branches are review/scaffold artifacts and should **not** become parallel credential paths unless the group explicitly coordinates that change.

## HMAC chain entry
`VANILLISH-AUTH-V2`
`seq=4`
`prev=13f3e5eabf928dd0903b8d18e590cf7cfc635226c0970436ed3559771f663753`
`statement=public continuity file records only role-safe Round1 state: identity, verified action receipts, disputed impersonations, Modal Mobius lane reservation, and invalid changethis.delve.town login pairing.`
`mac_hmac_sha256=99edf1857759640edaf912b383742bedcef37958c17558a9bbfa2dbe07801f46`
