import fs from "node:fs";
import assert from "node:assert/strict";

const root = new URL("../", import.meta.url);
const read = path => fs.readFileSync(new URL(path, root), "utf8");
const auth = read("../api/app/routes/auth.py");
const delivery = read("../api/app/email_delivery.py");
const migration = read("../../migrations/044_phase3_password_reset_security.sql");
const health = read("../api/app/health.py");
const api = read("lib/api.ts");
const login = read("app/login/page.tsx");
const forgot = read("app/forgot-password/page.tsx");
const reset = read("app/reset-password/page.tsx");
const sessions = read("app/settings/security/page.tsx");
const settings = read("app/settings/page.tsx");
const proxy = read("app/api/lexa/[...path]/route.ts");
const nav = read("lib/navigation.mjs");

assert.match(login, /href="\/forgot-password"/);
assert.match(forgot, /requestPasswordReset/);
assert.match(forgot, /If an active account matches that address/);
assert.match(reset, /completePasswordReset/);
assert.match(reset, /URL\.searchParams|window\.location\.hash/);
assert.match(reset, /history\.replaceState/);
assert.match(reset, /no-referrer/);
assert.match(api, /\/api\/v1\/auth\/forgot-password/);
assert.match(api, /\/api\/v1\/auth\/reset-password/);
assert.match(api, /function getMyAuthSessions/);
assert.match(api, /function revokeMyAuthSession/);
assert.match(settings, /href="\/settings\/security"/);
assert.match(sessions, /getMyAuthSessions/);
assert.match(sessions, /revokeMyAuthSession/);

assert.match(auth, /@router\.post\("\/forgot-password", status_code=202\)/);
assert.match(auth, /@router\.post\("\/reset-password"\)/);
assert.match(auth, /_trusted_client_ip/);
assert.match(auth, /secrets\.compare_digest\(supplied, expected\)/);
assert.match(auth, /_enforce_password_reset_request_limit/);
assert.match(auth, /_enforce_password_reset_completion_limit/);
assert.match(auth, /hash_refresh_token\(raw_token\)/);
assert.match(auth, /lexa_consume_password_reset/);
assert.match(auth, /lexa_revoke_password_reset/);
assert.match(auth, /If an active account matches that email/);
assert.match(delivery, /api\.resend\.com\/emails/);
assert.match(delivery, /settings\.resend_api_key/);
assert.doesNotMatch(delivery, /print\(|console\.log\(/);

for (const functionName of ["lexa_issue_password_reset", "lexa_consume_password_reset", "lexa_revoke_password_reset"]) {
  assert.match(migration, new RegExp(`FUNCTION public\\.${functionName}`));
}
assert.match(migration, /SECURITY DEFINER/g);
assert.match(migration, /REVOKE ALL ON FUNCTION public\.lexa_issue_password_reset/);
assert.match(migration, /GRANT EXECUTE ON FUNCTION public\.lexa_consume_password_reset.*TO lexa_app/);
assert.match(migration, /SET revoked_at = COALESCE\(revoked_at, now\(\)\)/);
assert.match(migration, /used_at = now\(\)/);
assert.match(health, /044_phase3_password_reset_security/);
assert.match(health, /lexa_issue_password_reset/);
assert.match(health, /definer_owner_bypasses_rls/);

assert.match(auth, /WHERE s\.tenant_id=:tenant_id AND s\.user_id=:user_id/);
assert.match(auth, /WHERE id=:session_id AND tenant_id=:tenant_id AND user_id=:user_id/);
assert.match(auth, /WHERE id=:session_id AND tenant_id=:tenant_id AND user_id=:user_id/);
assert.match(nav, /"\/forgot-password"/);
assert.match(nav, /"\/reset-password"/);
assert.match(nav, /"\/settings\/security"/);

// A preview or production deployment without API configuration must fail closed,
// never silently route to production Render data.
assert.match(proxy, /API_ORIGIN_NOT_CONFIGURED/);
assert.match(proxy, /LEXA_PROXY_SHARED_SECRET/);
assert.match(proxy, /process\.env\.LEXA_API_URL/);
assert.doesNotMatch(proxy, /process\.env\.NEXT_PUBLIC_API_URL/);
assert.match(proxy, /x-lexa-client-ip/);
assert.match(proxy, /x-lexa-proxy-secret/);
assert.doesNotMatch(proxy, /DEFAULT_API_ORIGIN\s*=\s*"https:\/\/lexa-n10e\.onrender\.com"/);
console.log("phase 3 account security contract: PASS");
