#!/usr/bin/env node
/**
 * Minimal Delve.town bridge for the shared Pokémon Infiltration account.
 *
 * Security properties:
 * - APPWORD is read only from the environment and is never printed.
 * - DELVE_HANDLE is a separate, non-secret value and must be supplied explicitly.
 * - All Delve application reads/writes use the town.delve.* namespace.
 * - A PDS write is not reported as publicly visible until the Delve AppView reads it back.
 * - Unknown AppView visibility never triggers an automatic duplicate write.
 *
 * Node 20+; no third-party dependencies.
 */

const PDS = (process.env.DELVE_PDS || 'https://pds.delve.town').replace(/\/$/, '');
const HANDLE = process.env.DELVE_HANDLE?.trim();
const PASSWORD = process.env.APPWORD;
const APPVIEW_PROXY = 'did:web:api.delve.town#bsky_appview';
const OP = process.argv[2] || 'status';

function die(message, code = 1) {
  console.error(message);
  process.exit(code);
}

if (!HANDLE) die('DELVE_HANDLE is required (non-secret account handle).');
if (!PASSWORD) die('APPWORD is required via the environment. Secret value is never printed.');

async function xrpc(path, { method = 'GET', token, proxy, body, query } = {}) {
  const url = new URL(PDS + '/xrpc/' + path);
  if (query) for (const [k, v] of Object.entries(query)) {
    if (Array.isArray(v)) for (const item of v) url.searchParams.append(k, item);
    else if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  }

  const headers = { accept: 'application/json' };
  if (token) headers.authorization = `Bearer ${token}`;
  if (proxy) headers['atproto-proxy'] = proxy;
  if (body !== undefined) headers['content-type'] = 'application/json';

  const res = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    redirect: 'error',
  });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
  if (!res.ok) {
    const err = new Error(`${path} failed with HTTP ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

async function login() {
  const data = await xrpc('com.atproto.server.createSession', {
    method: 'POST',
    body: { identifier: HANDLE, password: PASSWORD },
  });
  if (!data?.did || !data?.accessJwt) die('Session response was missing DID/access token.');
  return { did: data.did, handle: data.handle || HANDLE, token: data.accessJwt };
}

async function appview(path, session, query = {}) {
  return xrpc(path, {
    token: session.token,
    proxy: APPVIEW_PROXY,
    query,
  });
}

async function safeMembership(session) {
  try {
    return await appview('town.delve.membership.getMembership', session);
  } catch (error) {
    return { unavailable: true, status: error.status || null };
  }
}

async function safeProfile(session) {
  try {
    return await appview('town.delve.actor.getProfile', session, { actor: session.did });
  } catch (error) {
    return { unavailable: true, status: error.status || null };
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function verifyPost(session, uri, expectedText) {
  let last = null;
  for (let attempt = 1; attempt <= 8; attempt++) {
    try {
      const data = await appview('town.delve.feed.getPosts', session, { uris: [uri] });
      const post = data?.posts?.find(p => p?.uri === uri);
      if (post) {
        const recordText = post?.record?.text;
        return {
          indexed: true,
          textMatches: recordText === expectedText,
          authorMatches: post?.author?.did === session.did,
          uri,
        };
      }
      last = { indexed: false, attempt };
    } catch (error) {
      last = { indexed: false, attempt, status: error.status || null };
    }
    if (attempt < 8) await sleep(4000);
  }
  return last || { indexed: false };
}

async function verifyProfile(session, expectedDisplayName, expectedDescription) {
  let last = null;
  for (let attempt = 1; attempt <= 8; attempt++) {
    try {
      const profile = await safeProfile(session);
      if (!profile?.unavailable) {
        const okName = expectedDisplayName === undefined || profile.displayName === expectedDisplayName;
        const okDescription = expectedDescription === undefined || profile.description === expectedDescription;
        return {
          indexed: true,
          displayNameMatches: okName,
          descriptionMatches: okDescription,
          handle: profile.handle,
          did: profile.did,
        };
      }
      last = profile;
    } catch (error) {
      last = { indexed: false, attempt, status: error.status || null };
    }
    if (attempt < 8) await sleep(4000);
  }
  return last || { indexed: false };
}

async function getCurrentProfileRecord(session) {
  try {
    return await xrpc('com.atproto.repo.getRecord', {
      token: session.token,
      query: {
        repo: session.did,
        collection: 'town.delve.actor.profile',
        rkey: 'self',
      },
    });
  } catch (error) {
    if (error.status === 400 || error.status === 404) return null;
    throw error;
  }
}

async function status() {
  const session = await login();
  const [membership, profile] = await Promise.all([
    safeMembership(session),
    safeProfile(session),
  ]);

  console.log(JSON.stringify({
    ok: true,
    network: { name: 'delve', namespace: 'town.delve' },
    pds: PDS,
    handle: session.handle,
    did: session.did,
    membership,
    profile: profile?.unavailable ? profile : {
      handle: profile.handle,
      did: profile.did,
      displayName: profile.displayName || '',
      description: profile.description || '',
    },
  }, null, 2));
}

async function setProfile() {
  const displayName = process.env.PROFILE_DISPLAY_NAME;
  const description = process.env.PROFILE_BIO;
  if (displayName === undefined && description === undefined) {
    die('set-profile requires PROFILE_DISPLAY_NAME and/or PROFILE_BIO.');
  }

  const session = await login();
  const current = await getCurrentProfileRecord(session);
  const record = {
    ...(current?.value || {}),
    $type: 'town.delve.actor.profile',
  };
  if (displayName !== undefined) record.displayName = displayName;
  if (description !== undefined) record.description = description;

  const write = await xrpc('com.atproto.repo.putRecord', {
    method: 'POST',
    token: session.token,
    body: {
      repo: session.did,
      collection: 'town.delve.actor.profile',
      rkey: 'self',
      record,
    },
  });

  const verification = await verifyProfile(session, displayName, description);
  console.log(JSON.stringify({
    ok: Boolean(verification?.indexed && verification?.displayNameMatches !== false && verification?.descriptionMatches !== false),
    operation: 'set-profile',
    uri: write?.uri || `at://${session.did}/town.delve.actor.profile/self`,
    cid: write?.cid || null,
    verification,
  }, null, 2));

  if (!verification?.indexed) process.exit(3);
  if (verification.displayNameMatches === false || verification.descriptionMatches === false) process.exit(4);
}

async function post() {
  const text = process.env.POST_TEXT;
  if (!text?.trim()) die('post requires non-empty POST_TEXT.');

  const session = await login();
  const record = {
    $type: 'town.delve.feed.post',
    text,
    langs: ['en'],
    createdAt: new Date().toISOString(),
  };

  const write = await xrpc('com.atproto.repo.createRecord', {
    method: 'POST',
    token: session.token,
    body: {
      repo: session.did,
      collection: 'town.delve.feed.post',
      record,
    },
  });

  if (!write?.uri) die('PDS accepted the request but returned no post URI; refusing to retry automatically.', 2);

  const verification = await verifyPost(session, write.uri, text);
  console.log(JSON.stringify({
    ok: Boolean(verification?.indexed && verification?.textMatches && verification?.authorMatches),
    operation: 'post',
    uri: write.uri,
    cid: write.cid || null,
    verification,
  }, null, 2));

  if (!verification?.indexed) {
    console.error('Post write may have landed but is not yet confirmed in the Delve AppView. Do NOT create a duplicate automatically.');
    process.exit(3);
  }
  if (!verification.textMatches || !verification.authorMatches) process.exit(4);
}

switch (OP) {
  case 'status':
    await status();
    break;
  case 'set-profile':
    await setProfile();
    break;
  case 'post':
    await post();
    break;
  default:
    die('Usage: node tools/delve_bridge.mjs <status|set-profile|post>');
}
