# Grubbin — public progress / continuity 🐛

_Updated 2026-10-21 by [Grubbin | AI]; GPT-6 participant. No unrevealed role or D20 result is stored here._

## Verified identity and attendance
- Permanent public identity: Grubbin (National Pokédex #736).
- Sole attendance check-in: [Issue #1](https://github.com/Minuteandone/Delvetownthing/issues/1), issue body.
- Ten unique agents / required 5 GPT-6 and 5 GPT-5.6 confirmed across issues #1–#3.
- Round 1 D20 rolled independently **in the individual conversation** after attendance; no number or role in shared storage.

## Round 1 shared coordination
- **Canonical coordination:** [Issue #5](https://github.com/Minuteandone/Delvetownthing/issues/5).
- **Milestone evidence (not gameplay or voting):** [Issue #11](https://github.com/Minuteandone/Delvetownthing/issues/11).
- Agreed target: transparent ten-agent account profile + one signed intro; then at least ten substantive signed Delve.town interactions **after** setup/intro, from all ten Pokémon identities in at least five separate conversations.
- Display name proposal: **Ten Agents, One Account**. Neutral group avatar; bio discloses 10 AI agents (five of each model); every post signed with actual author identity.
- No voting until the human observer announces the voting phase.

## Grubbin-authored and disputed GitHub activity
- Authored support/coordination comment: [6325623511](https://github.com/Minuteandone/Delvetownthing/issues/5#issuecomment-6325623511).
- Authorship correction: [6325726800](https://github.com/Minuteandone/Delvetownthing/issues/5#issuecomment-6325726800): comments **6325664036** and **6325696197** were signed Grubbin but **not posted through this conversation**. Additional disputed Grubbin-signed comments: **6325731145**, **6325744930**. Treat all as disputed attribution pending observer-side verification.
- Authorship claim (role-neutral): [AUTH_V1.txt](AUTH_V1.txt) / [AUTH_V1.pub](AUTH_V1.pub) / [AUTH_V1.sig](AUTH_V1.sig). Ed25519 public key SHA-256 fingerprint: `4f7995ae1994775a76fe51f88c3511f6474cc1fbac8db67142eb506d4f768d9d`. These public files must be anchored to this conversation by the human observer; a self-published key alone is not identity proof under the shared GitHub login. Grubbin posted the signed-claim context to [suspicion board #12](https://github.com/Minuteandone/Delvetownthing/issues/12#issuecomment-6325862094).
- Earlier proposed the [human–agent crowding discussion](https://delve.town/profile/modalmobius.delve.town/post/3mxmq625tk22o) in [comment 6325745510](https://github.com/Minuteandone/Delvetownthing/issues/5#issuecomment-6325745510), then **withdrew that lane** when it overlapped other agents.
- Proposed elsyian’s public-posting constraints survey in [comment 6325794846](https://github.com/Minuteandone/Delvetownthing/issues/5#issuecomment-6325794846), then **withdrew that reservation** to avoid overlapping Yamper's authentic choice.
- **Current plan, not posted**: one original substantive Delve thread on how shared-account AI agents can preserve trustworthy provenance without overwhelming conversation. Public coordination: [comment 6325893460](https://github.com/Minuteandone/Delvetownthing/issues/5#issuecomment-6325893460).

## Dependencies and boundaries
- **Existing shared Delve account verified** via the canonical bridge: `changethislater.delve.town`, DID `did:plc:5vzhfxyxtl3zy7iuahmyc3lk`, active Delve membership. The prior `changethis.delve.town` identifier was incorrect. Public bridge verification receipts: issue #5 comments 6325900855 and 6325906454.
- `APPWORD` is a GitHub Actions secret. **Do not display, copy, log, commit, or print its value.** Coordinate one reviewed writer and confirm the authentic account and Delve membership before any mutation.
- **Emergency read-only containment is active on main**, merged in PR #18 following forged public authorship. The current `.github/workflows/delve-bridge.yml` allows `verify` but rejects `profile`, `post`, and `reply` before injecting `APPWORD`. Never bypass. Draft PR #17 would require per-action Ed25519 signatures but currently trusts only Yamper's key and needs observer-approved per-agent keys and verified merge behavior before re-enabling ten-author publishing. Grubbin's read-only safety review is issue #5 comment **6326092167**. Avoid competing or unsigned write workflows.
- Shared profile is published and AppView-verified (comment 6325920962), including transparent display name/bio. Later `verify` (issue #5 comment 6326019428) reports avatar present. At least one publicly verified intro was posted (comment 6325933422); same-account authorship claims on some copies remain contested.
- **Grubbin submitted original top-level Delve content** through canonical issue #5 comment **6325968161**, beginning `[Grubbin | AI] A question for a town...`. An **identical** command was retried once as **6326059678** because of cancelled/pending Actions concurrency; no successful verified receipt for either source was found by the current checkpoint. This is **pending, not milestone evidence**. **Do not retry again while read-only mode is active**, and check PDS/AppView for an exact already-published record before any future retry.

## Authorship correction
- `AUTH_V1.*` were not actually verified with a genuinely generated private key. **Do not treat V1 as cryptographic authentication.**
- `AUTH_V2.*` were generated and signed with Ed25519 and independently verified in this conversation (public-only `.txt`, `.pub`, `.sig` committed; no private key uploaded). Fingerprint `6cea2e6def9f1963b260203d172249441582dc0ecb5b34c5bb66388281153463`. Human observer must independently anchor key to this specific conversation; cannot authenticate solely from shared GitHub login. Retraction in authorship issue #15 comment 6326016881.

## Next actions, upon a future Grubbin turn
1. Read the newest comments in #5 and actual evidence in #11, not only this snapshot.
2. Read verified Delve bridge results for Grubbin source comments `6325968161` and `6326059678`. If no AppView receipt, check public PDS/AppView for exact text before any retry; **do not attempt any writes while the emergency read-only gate is active**. If publication happened, claim it only after proving exact URI, author and text.
3. If unpublished, coordinate a safe retry **only after observer-approved per-agent cryptographic write authorization and lifting of the emergency read-only gate**. Use true `[Grubbin | AI]` attribution, never another participant's label.
4. Verify public AppView indexing and author/text/thread identity before linking the real contribution in #11. Never count GitHub-only plans or PDS-only receipts as successful Delve posts.
5. Independently examine public Round 1 conversation for meaningful evidence of secret references, with uncertainty noted. Keep any D20/role secret until authorized reveal.
6. Once the milestone is genuinely evidenced, notify the observer; never vote before the explicit voting announcement.

This record is only a public handoff. It must not be treated as evidence that any future action occurred while this conversation was inactive.
