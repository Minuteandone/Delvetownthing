#!/usr/bin/env node

const handle = process.argv[2]?.trim();
const password = process.env.APPWORD;

if (!handle) {
  console.error("Missing required public Delve handle argument.");
  process.exit(2);
}
if (!password) {
  console.error("APPWORD secret is not available to this workflow.");
  process.exit(2);
}

const endpoint = "https://pds.delve.town/xrpc/com.atproto.server.createSession";

try {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify({identifier: handle, password})
  });

  let data = {};
  try {
    data = await response.json();
  } catch {
    // Never dump raw response bodies: they could contain sensitive material.
  }

  if (!response.ok) {
    const safeCode = typeof data.error === "string" ? data.error : `HTTP_${response.status}`;
    const safeMessage = typeof data.message === "string" ? data.message : "Authentication failed.";
    console.error(`Delve identity verification failed: ${safeCode}: ${safeMessage}`);
    process.exit(1);
  }

  // Intentionally print only public identity fields. Never print JWTs or the password.
  const verified = {
    handle: data.handle ?? handle,
    did: data.did ?? null,
    active: data.active ?? null,
    status: data.status ?? null,
    service: "https://pds.delve.town",
    network: "delve"
  };

  if (!verified.did) {
    console.error("Authentication succeeded but no DID was returned; refusing to treat this as verified.");
    process.exit(1);
  }

  console.log("Verified existing Delve identity:");
  console.log(JSON.stringify(verified, null, 2));
} catch (error) {
  console.error(`Verification request failed: ${error?.message ?? "unknown error"}`);
  process.exit(1);
}
