# Anti-Vibe-Check

A 30-check security audit for vibe-coded apps — and one that verifies its own findings.

Five section auditors run in parallel, then an adversarial verifier tries to **refute** every
failure they reported and **re-audits** every pass that didn't cite evidence. Read-only end to
end: nothing in the audit pipeline can edit your source.

Ships as a Claude Code plugin, with a build prompt for the Codex mirror.

---

## Why this exists

Ask any coding agent "is my app secure?" and it will read its own code, find it reasonable, and
tell you it's fine. That's the failure mode this tool is built against.

An audit that rubber-stamps is **worse than no audit**, because it manufactures confidence and
you stop looking. So the evidence rules here are structural rather than advisory:

- Every **PASS** must cite the code that makes it pass — file, line, quoted.
- Every **FAIL** must cite `file:line` with the offending code quoted.
- **`NEEDS-REVIEW`** is the correct verdict when evidence is out of reach. Using it is not a
  failure; hiding behind a PASS instead is.
- Config living in a Supabase or Vercel dashboard **cannot be confirmed from code**. It comes
  back `NEEDS-REVIEW` naming the screen a human must open — never inferred from client code.

Then the verifier distrusts all of it, in both directions. A false FAIL wastes hours and teaches
you to ignore the report. A false PASS is the one that gets you breached. They're not equally
bad, so anything genuinely unresolvable lands on `NEEDS-REVIEW`, never on PASS.

---

## What makes it specific to AI-assisted code

Generic scanners check for vulnerabilities. This checks for the vulnerabilities **an agent
introduces while fixing something unrelated** — and several checks carry the reason the hole
appears:

| Check | How it gets there |
|---|---|
| `NEXT_PUBLIC_` holding a service key | the build errored without the prefix, so the prefix got added |
| `Access-Control-Allow-Origin: *` | a fetch threw a CORS error and the wildcard made it stop |
| Public storage bucket | an image wouldn't load, so the bucket got flipped to public |
| RLS disabled | a query returned nothing, so the policy came off |

It also catches **the wrong fixes** — the ones that read as correct, and where a generic scan
hands back a clean bill of health:

- **S2.3** — an ownership check compared against a `userId` taken from the request body. The
  attacker supplies that too. This is the standard bad fix for an IDOR.
- **S4.3** — webhook signature verification running against an already-parsed body. It cannot
  succeed, but the code looks right.
- **S5.5** — `decode()` where `verify()` belongs. Parses the token without checking the
  signature, so anyone can mint one.

The verifier re-audits **S1.3, S2.2, S2.3, S4.3 and S5.5 unconditionally**, regardless of what
the section auditor concluded, because those five are where a plausible-looking PASS is most
often wrong.

---

## Pipeline

```
you (main session)              Fable / gpt-5.6-sol
  │  Recon: stack, backend, auth, payment provider, client/server boundary, commit SHA.
  │  Pre-marks checks that cannot apply. Owns scope and final acceptance.
  │
  └─→ vibecheck-manager         Opus / gpt-5.6-terra
        │  Writes five self-contained work orders. Delegates only; never audits.
        │
        ├─→ vc-secrets          S1  Secrets & Supply Chain        6 checks  ┐
        ├─→ vc-access           S2  Access Control                7 checks  │
        ├─→ vc-injection        S3  Injection & Untrusted Input   5 checks  ├ PARALLEL
        ├─→ vc-abuse            S4  Abuse & Money                 4 checks  │
        ├─→ vc-surface          S5  Surface & Exposure            8 checks  ┘
        │                       Sonnet / gpt-5.6-luna
        │
        └─→ vc-verifier         Opus / gpt-5.6-terra
              Refutes every FAIL. Re-audits every unevidenced PASS.
```

The five sections run **in parallel** — they're independent, so serializing them costs
wall-clock and buys nothing.

Section auditors have **no write capability at all**. They return findings in their final
message and the manager writes the report. Read-only is structural rather than a promise, and it
removes the write race that parallel sections would otherwise have.

### Model tiers

Judgment lives in tier 2. The verifier decides what's real, which is why it's never demoted even
though it's the most expensive single agent in a run.

| Tier | Role | Claude Code | Codex |
|------|------|-------------|-------|
| 1 | Recon, scope, acceptance | Fable | `gpt-5.6-sol` |
| 2 | Manager + Verifier | Opus | `gpt-5.6-terra` |
| 3 | Section auditors | Sonnet | `gpt-5.6-luna` |

---

## The 30 checks

All 30 live in [`reference/checklist.md`](reference/checklist.md) — **one file, read by every
agent.** No agent restates a check, so the Claude and Codex implementations cannot drift apart.

### S1 — Secrets & Supply Chain
| ID | Check | Default severity |
|----|-------|----------|
| S1.1 | No secrets in client-reachable code | CRITICAL |
| S1.2 | Frontend uses the public/anon key only; admin key stays server-side | CRITICAL |
| S1.3 | No secret behind `NEXT_PUBLIC_` / `VITE_` / `EXPO_PUBLIC_` / `REACT_APP_` | CRITICAL |
| S1.4 | `.env` gitignored **and never committed** — history, not just the working tree | CRITICAL |
| S1.5 | Prod build ships no source maps, `.git`, or reachable `/.env` | MEDIUM |
| S1.6 | Dependencies audited for known CVEs | MEDIUM |

### S2 — Access Control
The highest-yield section. Most real breaches are here, not in exotic injection.

| ID | Check | Default severity |
|----|-------|----------|
| S2.1 | Row Level Security on every table; nothing public by default | CRITICAL |
| S2.2 | Ownership verified before returning data (IDOR) | CRITICAL |
| S2.3 | User identity from the verified session, **never** from client input | CRITICAL |
| S2.4 | Auth enforced on every protected route, server-side | CRITICAL |
| S2.5 | Route protection isn't client-side only | HIGH |
| S2.6 | No mass assignment — explicit allowlist of writable fields | HIGH |
| S2.7 | No privilege-escalation path (first-user-admin, seeded admins) | HIGH |

### S3 — Injection & Untrusted Input
| ID | Check | Default severity |
|----|-------|----------|
| S3.1 | Queries are parameterized | CRITICAL |
| S3.2 | Input validated and sanitized **server-side** | HIGH |
| S3.3 | No XSS sinks on user content | HIGH |
| S3.4 | File uploads constrained — type/size, server-generated name, safe serving | HIGH |
| S3.5 | Server-side fetches of user-supplied URLs are allowlisted (SSRF) | HIGH |

### S4 — Abuse & Money
Frequently all-N/A on a pre-revenue app. That's a real result — the auditors are told to say so
rather than invent findings.

| ID | Check | Default severity |
|----|-------|----------|
| S4.1 | Rate limiting on the API | HIGH |
| S4.2 | Prices and entitlements come from the server | CRITICAL |
| S4.3 | Webhook signatures verified against the raw body, before any side effect | CRITICAL |
| S4.4 | Paid/LLM endpoints require auth and have a per-user cap | HIGH |

### S5 — Surface & Exposure
| ID | Check | Default severity |
|----|-------|----------|
| S5.1 | Admin and debug endpoints locked or removed in production | CRITICAL |
| S5.2 | Storage buckets not public — judged on the **bucket policy**, not upload code | CRITICAL |
| S5.3 | CORS restricted to your own origins | HIGH |
| S5.4 | CSRF protection on cookie-authenticated state changes | HIGH |
| S5.5 | Session and token handling (storage, expiry, real logout, `verify()`) | HIGH |
| S5.6 | Security headers — CSP, HSTS, frame-ancestors | LOW |
| S5.7 | Errors don't leak stack traces, SQL, or paths | MEDIUM |
| S5.8 | Logging exists for security-relevant events | MEDIUM |

---

## Install

```bash
claude plugin marketplace add NickyStaffs29/Anti-Vibe-Check
claude plugin install vibecheck@vibecheck
```

Restart Claude Code, or run `/reload-plugins`.

## Usage

```bash
/vibecheck                    # audit the current directory
/vibecheck ~/code/my-app      # audit a specific repo
/vibecheck --deep             # section auditors on Opus instead of Sonnet
/vibecheck --section S2       # one section, plus verification
```

Natural language works too — the skill triggers on "is my app secure", "did I leak any keys",
"can someone see other users' data".

### Output

`VIBECHECK_REPORT.md` at the repo root:

1. **Header** — date, stack detected, commit SHA audited, model tier per section
2. **Summary table** — all 30: `ID | Check | Verdict | Severity | Location`
3. **Findings** — every FAIL and NEEDS-REVIEW in severity order, with quoted code, the concrete
   exploit path, and the fix
4. **Fix order** — most-exploitable first, flagging which are one-line config changes vs real refactors
5. **Coverage note** — what was *not* audited, and why

> **The report is added to `.gitignore` on every run.** It's a written map of your app's live
> vulnerabilities — committing it to a public repo is worse than any single finding in it.

### Fixing

```bash
/vibecheck-fix                       # CRITICAL tier only (default)
/vibecheck-fix --tier HIGH
/vibecheck-fix --only S2.3,S4.1
```

Deliberately a separate command, so an audit never silently rewrites your auth code. It works one
severity tier at a time and stops at each boundary.

Two rules it won't break:

- **Leaked credentials are fixed by rotation, not deletion.** Removing the line leaves the key
  live and still in git history. A finding stays open until you confirm the rotation.
- **It never weakens a control to make something work.** If a fix breaks a feature, it reports
  the conflict rather than loosening CORS or disabling RLS.

---

## Codex mirror

[`reference/CODEX_BUILD_PROMPT.md`](reference/CODEX_BUILD_PROMPT.md) is a self-contained prompt
for a fresh Codex session. It ports the seven agents to `~/.codex/agents/*.toml`, symlinks the
**same** `checklist.md` rather than copying it, and maps the tiers to
`gpt-5.6-sol` / `gpt-5.6-terra` / `gpt-5.6-luna`.

One checklist, two stacks, no drift. A report from either side has the same format, so two runs
are diffable.

---

## Scope

**What this is:** a static audit targeting known failure classes in AI-assisted code, with
adversarial verification of its own output.

**What this is not:** a penetration test. It won't find business-logic flaws, race conditions, or
anything requiring a running application. It doesn't send requests to your deployed app. And
infrastructure config that lives in a hosting dashboard comes back as `NEEDS-REVIEW` with the
screen named — because guessing there is exactly the failure this tool exists to prevent.

Clean output means the 30 known holes weren't found. It does not mean the app is secure.

---

## Credits

The original 13 checks came from two TikToks by [@millee.md](https://www.tiktok.com/@millee.md)
on vibe-coded app security — [part 1](https://www.tiktok.com/@millee.md/video/7665507879453035796)
(the 10-point list) and [part 2](https://www.tiktok.com/@millee.md/video/7667762464045681941)
(broken access control, injection, exposed admin key). The remaining 17 checks, the section
structure, the evidence rules, and the verification pass were added on top.

Built on the same delegation hierarchy as
[Compute Squad](https://github.com/NickyStaffs29/Compute-Squad-Agent-Delegation).
