# vibecheck — canonical security checklist

30 checks across 5 sections. This file is the single source of truth for both the
Claude Code and Codex implementations. Agents read it and filter to their own section.
Never restate checks inside an agent file — drift between the two is how audits go stale.

---

## Evidence rules — binding on every agent

An audit that rubber-stamps is worse than no audit, because it manufactures confidence.
These rules exist to make a lazy PASS structurally impossible.

1. **Every FAIL** cites `path/to/file.ts:LINE` and quotes the offending code.
2. **Every PASS** cites the code that makes it pass — file, line, and the quoted line(s).
   "I reviewed this and it looks fine" is not a PASS. It is a `NEEDS-REVIEW`.
3. **`NO-MATCH` is a valid PASS only for absence-shaped checks** (e.g. "no `dangerouslySetInnerHTML`
   anywhere"). State the exact search you ran. An absence claim without a shown search is `NEEDS-REVIEW`.
4. **`N/A` is valid and expected.** No payments means most of S4 is N/A. State *why* it doesn't
   apply. A truthful N/A is worth more than an invented PASS.
5. **`NEEDS-REVIEW`** is the honest verdict when you cannot reach evidence — code you couldn't
   find, config that lives in a hosting dashboard, a runtime behaviour you can't observe statically.
   Use it freely. It is not a failure to use it; it is a failure to hide behind a PASS instead.
6. **Never edit a source file during an audit.** Audit agents are read-only. Fixes are a
   separate, opt-in command.
7. **Config that lives outside the repo** (Supabase dashboard RLS toggles, S3 bucket policy,
   Vercel env vars, Cloudflare WAF) cannot be confirmed from code alone. Mark it `NEEDS-REVIEW`
   and state the exact dashboard screen the human must check. Do not infer it from client code.
8. **Cite only paths you actually opened.** Before writing any `file.ts:LINE` reference, confirm
   the file exists at that path and the line says what you claim. Never reconstruct a path from
   a symbol name, an import statement, or where a file "should" live — `auth/foo.service.ts` and
   `services/foo.service.ts` are both plausible and only one is real. A finding whose citation
   does not resolve cannot be acted on, and it costs the reader more trust than the finding was
   worth. If you can name the defect but not locate it, say exactly that.

### Verdicts
`PASS` · `FAIL` · `N/A` · `NEEDS-REVIEW`

**Split a check that has both a provable half and an unverifiable half.** Report the repo-side
half on its own evidence and the environment-side half as `NEEDS-REVIEW` — e.g. "FAIL: no rate
limiter on any authenticated route (`index.ts:121-146`); NEEDS-REVIEW: whether an ingress/WAF
layer limits ahead of the app." Filing the whole check as `NEEDS-REVIEW` because one half is
unknowable buries a defect you proved. Filing it wholly as `FAIL` ignores a control that may
exist. Neither is honest when you know one half for certain.

### Severity (assign to every FAIL)
- **CRITICAL** — remote attacker reaches user data, money, or admin with no credentials.
- **HIGH** — an authenticated user reaches another user's data, or cost/abuse is unbounded.
- **MEDIUM** — needs chaining with another flaw, or leaks information that assists an attack.
- **LOW** — defence in depth; real but not directly exploitable today.

Each check lists a **default severity**. Raise or lower it based on what you actually find,
and say why you moved it.

**Bound the blast radius before you rate an unknown.** Severity describes what an attacker
actually gets, not the worst thing the check's category could theoretically mean. Rating a
`NEEDS-REVIEW` at its worst conceivable case is the most common calibration error, and it is
always avoidable with one search:

- Before rating unread config, enumerate what config actually exists. "A `VITE_*` var might hold
  a server secret" is CRITICAL in the abstract; if the repo defines exactly one such var and it
  is a Sentry DSN — a public ingest endpoint by design — the real ceiling is LOW.
- Before rating an unverifiable value, audit the code that consumes it. An allowlist read from
  an env var is a very different risk when the implementation is an exact-match `Set.has()` than
  when it reflects the request origin. Verify the mechanism even when you can't see the value,
  and say which one you checked.
- State the ceiling you found and how you bounded it, in one line.

Inflated severities are not a safe default. They train the reader to skim, and the finding that
gets skimmed is the real CRITICAL sitting underneath.

---

## S1 — Secrets & Supply Chain
Agent: `vc-secrets` · Default tier: section auditor

### S1.1 — No secrets in client-reachable code · CRITICAL
Hunt: API keys, tokens, passwords, connection strings, private keys hardcoded in any file
that ships to the browser or the app bundle. Search for `sk-`, `sk_live`, `service_role`,
`-----BEGIN`, `Bearer `, `password =`, `apiKey`, `secret` across client dirs.
Fail when: any credential is literal in client-reachable source.

### S1.2 — Frontend uses the public/anon key only · CRITICAL
Hunt: the admin / service-role / secret key must never appear in client code, a client
bundle, or a client-side SDK init. Supabase `service_role`, Firebase Admin SDK, Stripe
`sk_live`, any key documented as "server-side only".
Fail when: a privileged key is initialised anywhere the browser can reach.
Note: this check makes or breaks S2.1 — a leaked admin key bypasses RLS entirely.

### S1.3 — No secret behind a public build prefix · CRITICAL
Hunt: `NEXT_PUBLIC_*`, `VITE_*`, `EXPO_PUBLIC_*`, `REACT_APP_*`, `PUBLIC_*`, `GATSBY_*`.
Every one of these is inlined into the client bundle at build time and is readable by anyone.
Enumerate all of them and judge each on what it holds, not on its name.
Fail when: any prefixed var holds a service key, admin token, DB URL, or third-party secret.
Why it happens: the build errored without the prefix, so the prefix got added.

### S1.4 — `.env` gitignored and never committed · CRITICAL
Hunt: `.gitignore` covers `.env*`. Then check history, not just the working tree:
`git log --all --full-history --diff-filter=A -- '*.env*'` and
`git log -p --all -S 'service_role' -S 'sk_live' -S 'BEGIN RSA' --oneline`.
Fail when: any secret was ever committed — even if later deleted. Git keeps it.
If found: the fix is rotating the key, not deleting the file. Say so.

### S1.5 — Production build ships no source maps, `.git`, or reachable `/.env` · MEDIUM
Hunt: build config emitting `.map` files to a public dir; `.git` or `.env` inside a served
static root (`public/`, `dist/`, `build/`, `static/`); Dockerfile `COPY . .` with no `.dockerignore`.
Fail when: server-side logic or secrets are recoverable from published artifacts.

### S1.6 — Dependencies audited for known CVEs · MEDIUM
Hunt: run the ecosystem's own auditor read-only — `npm audit --omit=dev`, `pnpm audit`,
`pip-audit`, `bundle audit`, `cargo audit`. Report criticals and highs with the package name.
Fail when: a critical/high CVE is present in a dependency that is actually reachable at runtime.
Do not install anything. Do not run `--fix`.

---

## S2 — Access Control
Agent: `vc-access` · Default tier: section auditor
The highest-yield section. Most vibe-coded breaches are here, not in exotic injection.

### S2.1 — Row Level Security on every table · CRITICAL
Hunt: migrations and schema for `ENABLE ROW LEVEL SECURITY` on each table, plus an actual
policy per table (RLS enabled with no policy denies all; RLS disabled allows all).
Firebase equivalent: `firestore.rules` / `storage.rules` not in test mode
(`allow read, write: if true`).
Fail when: any table holding user data has RLS off, or on with no policy, or a policy of `true`.
Dashboard-only config → `NEEDS-REVIEW` naming the screen to check.

### S2.2 — Ownership verified before returning data (IDOR) · CRITICAL
Hunt: every handler that reads or mutates a record by ID. Does it constrain the query to the
current user (`.eq('user_id', session.user.id)`, `WHERE owner = $1`) or check ownership after fetch?
Fail when: a record is returned or mutated based only on an ID the client supplied.
Concrete test to name in the finding: "user A changes the ID in the URL/body and gets user B's row."

### S2.3 — User identity comes from the verified session, never the client · CRITICAL
Hunt: `userId` / `user_id` / `email` / `role` / `orgId` read out of `req.body`, `req.query`,
`req.params`, or a custom header and then trusted. It must come from a verified session or a
`verify()`-ed JWT, server-side.
Fail when: any authorization decision reads identity from client-controlled input.
This is the single most common wrong "fix" for S2.2 — the ownership check gets added, but
against an ID the attacker also supplies.

### S2.4 — Auth enforced on every protected route, server-side · CRITICAL
Hunt: each API route / server action / RPC. Is there a session check before any data access?
Enumerate every endpoint and mark which ones check.
Fail when: any endpoint returning or mutating user data has no server-side auth check.

### S2.5 — Route protection is not client-side only · HIGH
Hunt: `useEffect` redirects, conditional rendering, hidden nav links, middleware that only
guards page routes and not `/api`. The page being protected says nothing about the data.
Fail when: the UI hides a route but the underlying endpoint answers an unauthenticated request.

### S2.6 — No mass assignment · HIGH
Hunt: `.update(req.body)`, `{...req.body}` spread into an insert/update, ORM `create(body)`,
`Object.assign(user, body)`. There must be an explicit allowlist of writable fields.
Fail when: a user can set a field they shouldn't own.
Concrete test to name: "POST `{"role":"admin"}` or `{"credits":99999}` to your own profile update."

### S2.7 — No privilege-escalation path · HIGH
Hunt: first-user-becomes-admin logic, seeded/demo admin accounts with known passwords,
a `/api/make-admin` or role-setting endpoint reachable by a normal user, role stored in a
client-readable cookie or localStorage and trusted server-side.
Fail when: a normal signup can reach elevated privileges.

---

## S3 — Injection & Untrusted Input
Agent: `vc-injection` · Default tier: section auditor
Common shape: untrusted data reaches a dangerous sink. Trace source → sink.

### S3.1 — Queries are parameterized · CRITICAL
Hunt: string-concatenated or template-literal SQL, `${}` inside a query string, `.raw(`,
`query(\`SELECT ... ${x}\`)`, dynamic `ORDER BY`/table names from input, NoSQL operator
injection (`{$gt: ''}` reaching a Mongo filter).
Fail when: any user-controlled value is concatenated into a query instead of bound as a parameter.

### S3.2 — Input validated and sanitized server-side · HIGH
Hunt: a schema validator (zod, yup, pydantic, joi) applied at the server boundary — not only
in the form component. Client validation is UX; it is not a control.
Fail when: an endpoint accepts and uses an unvalidated body.

### S3.3 — No XSS sinks on user content · HIGH
Hunt: `dangerouslySetInnerHTML`, `innerHTML`, `outerHTML`, `v-html`, `document.write`,
`eval`, unsanitized markdown/HTML rendering, user-controlled `href`/`src` accepting
`javascript:` or `data:`.
Fail when: user content reaches a sink without sanitization (DOMPurify or equivalent).

### S3.4 — File uploads are constrained · HIGH
Hunt: server-side type and size limits (not just the `accept` attribute); stored filename
generated server-side rather than reusing the user's (path traversal via `../`); user files
served from a separate origin or with `Content-Disposition: attachment` so an uploaded
`.html`/`.svg` can't execute as your site.
Fail when: any of the three is missing on an upload path.

### S3.5 — Server-side fetches of user-supplied URLs are allowlisted (SSRF) · HIGH
Hunt: anywhere the server fetches a URL the user provided — avatar import, link preview,
webhook config, PDF/image from URL, proxy endpoints.
Fail when: no allowlist, no scheme restriction, no block on private ranges
(`127.0.0.1`, `10.x`, `192.168.x`, `169.254.169.254` cloud metadata).

---

## S4 — Abuse & Money
Agent: `vc-abuse` · Default tier: section auditor
Frequently all-N/A on a pre-revenue app. Say so rather than inventing findings.

### S4.1 — Rate limiting on the API · HIGH
Hunt: middleware or gateway rate limits, especially on auth, signup, password reset, search,
and anything expensive. Platform-level limits (Vercel, Cloudflare) count — name them if used.
Fail when: auth and expensive endpoints have no limit at any layer.

### S4.2 — Prices and entitlements come from the server · CRITICAL
Hunt: checkout/order handlers taking `amount`, `price`, `currency`, `quantity`, `plan`, or
`tier` from the request and passing them to the payment provider or the DB.
Fail when: the client can influence what it is charged or what it is granted.

### S4.3 — Webhook signatures verified · CRITICAL
Hunt: every webhook receiver (Stripe, Clerk, Supabase, GitHub, Twilio, Shopify). It must
verify the signature against the raw body *before* acting. Note that many frameworks parse
the body and break signature verification — check for a raw-body carve-out.
Fail when: a receiver acts on an unverified payload.
Impact to state plainly: anyone on the internet can POST "payment succeeded."

### S4.4 — Paid/LLM endpoints require auth and have a per-user cap · HIGH
Hunt: any route calling an LLM, image generator, SMS/email sender, or other metered API.
It needs auth, a per-user quota, and a bounded max token/size parameter.
Fail when: an unauthenticated or uncapped route spends money.
Impact to state plainly: an open one is your bill, and it is discovered by scanners quickly.

---

## S5 — Surface & Exposure
Agent: `vc-surface` · Default tier: section auditor

### S5.1 — Admin and debug endpoints locked or removed in production · CRITICAL
Hunt: `/debug`, `/admin`, `/test`, `/seed`, `/reset`, `/__`, GraphQL introspection or
playground enabled in prod, framework debug mode (`DEBUG=True`, `NODE_ENV` not production),
DB admin UIs (Adminer, pgweb) exposed.
Fail when: any of these is reachable in production without auth.

### S5.2 — Storage buckets are not public · CRITICAL
Hunt: the bucket policy itself — Supabase Storage policies, S3 block-public-access and
bucket policy, Firebase Storage rules, GCS ACLs. Check the policy, not the upload code.
Fail when: a bucket holding user content is world-readable or world-writable.
Why it happens: an image wouldn't load, so the bucket got flipped to public.
Dashboard-only → `NEEDS-REVIEW` naming the exact screen.

### S5.3 — CORS restricted to your own origins · HIGH
Hunt: `Access-Control-Allow-Origin: *`, origin reflection (echoing `req.headers.origin`),
`Allow-Credentials: true` combined with a wildcard or reflected origin, overly broad
regex origin matching.
Fail when: any untrusted origin can make credentialed requests.
Why it happens: a fetch threw a CORS error and the wildcard made it go away.

### S5.4 — CSRF protection on cookie-authenticated state changes · HIGH
Hunt: `SameSite=Lax|Strict` on session cookies, or CSRF tokens, on every state-changing route.
N/A if auth is purely a `Authorization: Bearer` header with no cookie fallback — say so.
Fail when: cookie auth + state-changing route + no SameSite and no token.

### S5.5 — Session and token handling · HIGH
Hunt: tokens in `localStorage` (XSS-readable) vs `httpOnly` cookies; token expiry set;
logout actually invalidates server-side rather than just clearing the client; JWTs verified
with `verify()` and a pinned algorithm — never `decode()`, never `algorithms: ['none']`;
secrets not defaulted to a literal like `"secret"` or `"changeme"`.
Fail when: any of these is wrong.

### S5.6 — Security headers set · LOW
Hunt: `Content-Security-Policy`, `Strict-Transport-Security`,
`X-Frame-Options`/`frame-ancestors` (clickjacking), `X-Content-Type-Options: nosniff`.
Fail when: absent on an app handling auth or payments.

### S5.7 — Errors don't leak internals · MEDIUM
Hunt: stack traces, SQL error text, ORM errors, file paths, or raw upstream responses
returned to the client; verbose error pages in prod; `console.error(err)` echoed into a
response body.
Fail when: a client-visible error reveals internal structure.

### S5.8 — Logging exists for security-relevant events · MEDIUM
Hunt: auth failures, permission denials, admin actions, 4xx/5xx rates, webhook failures —
recorded somewhere durable and reviewable.
Fail when: an attack in progress would leave no trace you could find afterwards.
Also flag the inverse: logs writing full request bodies, tokens, or passwords in plaintext.

---

## Report contract

Every run writes `VIBECHECK_REPORT.md` to the repo root, in this order:

1. **Header** — date, stack detected, commit SHA audited, model tier used per section.
2. **Summary table** — all 30: `ID | Check | Verdict | Severity | Location`.
3. **Findings** — every FAIL and NEEDS-REVIEW in severity order: what, where (`file:line`),
   the quoted code, the concrete exploit path in one sentence, and the fix.
4. **Fix order** — a numbered list, most-exploitable first, noting which fixes are one-line
   config changes versus real refactors.
5. **Coverage note** — what was NOT audited and why (dashboard config, no repo access to
   infra, generated code excluded).

`VIBECHECK_REPORT.md` must be added to `.gitignore` on every run. It is a written map of the
app's live vulnerabilities; committing it to a public repo is worse than any single finding in it.
