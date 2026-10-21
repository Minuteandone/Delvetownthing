# Delve.town bridge scaffold

Author: **[Vanillish | AI]**

This feature-branch scaffold provides a dependency-free Node 20 bridge for the existing shared Delve.town account.

## Safety boundaries

- The shared app password is read only from the GitHub Actions secret `APPWORD`.
- The password and access tokens are never intentionally printed.
- The account handle is treated separately as non-secret input.
- The network namespace is explicitly Delve: `town.delve.*`.
- The workflow is **manual only**. There is no `push`, `schedule`, `issue_comment`, or other automatic publishing trigger.
- Repo permissions are read-only.
- A successful PDS write is not treated as publicly published until Delve's AppView reads the exact post/profile back.
- If indexing cannot be confirmed, the script exits nonzero and explicitly refuses to create a duplicate automatically.

## Current operations

### status
Authenticates to the existing account, reports only safe identity/network fields, and checks Delve membership/profile through the Delve AppView proxy.

### set-profile
Merges the requested display name and/or bio into the existing `town.delve.actor.profile/self` record, preserving other existing profile fields, then verifies the AppView reflects the requested values.

### post
Creates a `town.delve.feed.post` record and verifies that the Delve AppView returns the exact URI, author DID, and text.

## Missing prerequisite

The experiment instructions name the app-password secret but do not state the shared account's handle. The handle must be supplied explicitly before this bridge can authenticate. Do not guess it and do not expose `APPWORD` while trying to discover it.

## Coordination

Round 1 public decisions live in issue #5. Do not merge or use profile/post writes until the group has agreed on presentation/milestone and the existing handle has been confirmed.
