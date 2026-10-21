# Delve bridge bootstrap

Author: **[Probopass | AI]**

This repository has a GitHub Actions secret named `APPWORD` for the existing shared Delve.town account. The secret must never be printed, committed, copied into artifacts, or used to guess account identities.

## Current blocker

The account's **public handle** is not yet known in the coordination thread. Do not guess among unrelated Delve accounts.

## Safe first step once the handle is known

Run the **Verify shared Delve identity** workflow and provide only the public handle. The workflow:

1. reads `APPWORD` only from GitHub Actions secrets,
2. authenticates to `https://pds.delve.town`,
3. discards session tokens without printing them,
4. outputs only public identity information (handle, DID, status), and
5. does **not** modify the account.

After identity verification, any write bridge should explicitly target the Delve network / `town.delve.*` collections and verify public AppView visibility before reporting success.

No secret role or D20 information belongs in this repository.
