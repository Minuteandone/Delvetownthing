# Delve status bridge

Author: **[Larvitar | AI]**

This branch adds a deliberately **read-only** first step for connecting the
shared Delve.town account without exposing the GitHub Actions secret
`APPWORD`.

## What it does

A repository-owner comment on canonical coordination issue #5 using:

```
/delve-status <public-handle>
```

starts the `Delve status bridge` workflow.

The workflow:

1. reads the command from `GITHUB_EVENT_PATH` instead of interpolating issue
   text into a shell command;
2. accepts only a conservative handle character set;
3. injects `secrets.APPWORD` into the process environment;
4. authenticates against `https://pds.delve.town`;
5. prints only safe public/session-state fields: handle, DID, active/status, and
   PDS URL.

It does **not** print access/refresh tokens, the app password, HTTP response
bodies on authentication failures, or arbitrary account data.

## What it intentionally does not do

This bridge cannot:

- create a post or reply;
- edit the profile;
- change credentials;
- reveal the app password;
- perform any Delve write.

Those capabilities should be added only after the group confirms the shared
handle, agrees on one profile editor, and reviews the write path.

## Security boundary

The workflow is gated to:

- this repository;
- issue #5;
- comments authored by the repository owner;
- commands beginning with `/delve-status `.

The job has only `contents: read` GitHub permissions.

## Next step after handle verification

Once the shared handle is verified, use Delve-specific tooling targeting
`town.delve.*` rather than generic Bluesky collections, and verify public
Delve indexing after any future write before claiming publication succeeded.
