# Anti-Vibe-Check

A 30-check security audit for vibe-coded apps — and one that verifies its own findings.

Five section auditors run in parallel, then an adversarial verifier tries to **refute** every
failure they reported and **re-audits** every pass that didn't cite evidence. Read-only end to
end: nothing in the audit pipeline can edit your source.

Ships as a Claude Code plugin and as native Codex agents — one shared checklist, so the two
stacks can't drift apart.

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
you (main session)              Fable / gpt-5.6-sol          @ high
  │  Recon: stack, backend, auth, payment provider, client/server boundary, commit SHA.
  │  Pre-marks checks that cannot apply. Owns scope and final acceptance.
  │
  └─→ vibecheck-manager         Opus / gpt-5.6-terra         @ max
        │  Writes five self-contained work orders. Delegates only; never audits.
        │
        ├─→ vc-secrets          S1  Secrets & Supply Chain        6 checks  ┐
        ├─→ vc-access           S2  Access Control                7 checks  │
        ├─→ vc-injection        S3  Injection & Untrusted Input   5 checks  ├ PARALLEL
        ├─→ vc-abuse            S4  Abuse & Money                 4 checks  │
        ├─→ vc-surface          S5  Surface & Exposure            8 checks  ┘
        │                       Sonnet / gpt-5.6-luna        @ max
        │
        └─→ vc-verifier         Opus / gpt-5.6-sol  FRESH   @ high
              Refutes every FAIL. Re-audits every unevidenced PASS.
```

The five sections run **in parallel** — they're independent, so serializing them costs
wall-clock and buys nothing.

Section auditors hold **no `Write` or `Edit` tools**. They return findings in their final message
and the manager writes the report, which removes the write race that parallel sections would
otherwise have. Bash stays available — S1.4's git-history check and S1.6's dependency audit both
run through it — and it's kept to inspection **by instruction, not by sandbox**: nothing stops a
Bash call from mutating the repo except the agent's own instructions. A `PreToolUse` hook could
enforce that boundary at the platform level instead; that's a future hardening step, not something
this pass builds.

### Model tiers

Two knobs matter here, and the second one is the one people miss.

| Role | Claude Code | Codex | Effort |
|------|-------------|-------|--------|
| Orchestrator — recon, scope, acceptance | Fable | `gpt-5.6-sol` | high |
| Manager — scoping and routing | Opus | `gpt-5.6-terra` | `max` |
| Section auditors ×5 | Sonnet | `gpt-5.6-luna` | `max` |
| Verifier — **fresh instance** | Opus | `gpt-5.6-sol` | high |

**Max reasoning effort is off by default in both stacks.** Codex ships `sol=low`, `terra=medium`,
`luna=medium`. On the Claude Code side, each agent pins its own tier with an `effort` key in its
frontmatter, which overrides the session's effort level for as long as that agent runs — that's
the mechanism, not a parameter anyone passes at spawn time. An audit run on an agent file missing
that key is running below its capability.

This matters more than the model choice. A cheap model at max reasoning substantially outperforms
the same model at its default, which is the entire economic argument for this pipeline: five
parallel auditors at max effort cost a fraction of one top-tier pass and cover more ground,
because section auditing is mechanical evidence-gathering where thoroughness beats sophistication.

The verifier is deliberately a **fresh top-tier instance** — never a reused auditor. Its value
comes from not having been in the room when the findings were formed. A reviewer that inherits
the auditor's framing just re-derives the auditor's conclusions.

Tiering follows [@daniel_mac8's `sol-advisor` pattern](https://x.com/daniel_mac8/status/2083607027813662810):
frontier model orchestrates, cheap model at max reasoning implements routine work, mid model at
max handles the complex parts, and a fresh frontier instance reviews.

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

### Claude Code

```bash
claude plugin marketplace add NickyStaffs29/Anti-Vibe-Check
claude plugin install vibecheck@vibecheck
```

Restart Claude Code, or run `/reload-plugins`.

### Codex

Codex reads Claude Code plugin marketplaces natively, so the same repo installs directly:

```bash
codex plugin marketplace add https://github.com/NickyStaffs29/Anti-Vibe-Check
codex plugin add vibecheck@vibecheck
```

Then set up the native Codex agents, which run the tiers at pinned reasoning effort:

```bash
mkdir -p ~/.codex/vibecheck
git clone https://github.com/NickyStaffs29/Anti-Vibe-Check /tmp/avc
cp /tmp/avc/codex/agents/*.toml ~/.codex/agents/
ln -s /tmp/avc/reference/checklist.md ~/.codex/vibecheck/checklist.md
cat /tmp/avc/codex/profiles.toml >> ~/.codex/config.toml

mkdir -p ~/.codex/skills/vibecheck
ln -s /tmp/avc/codex/SKILL.md ~/.codex/skills/vibecheck/SKILL.md
```

The last two lines register `/vibecheck` as a Codex skill. The plugin install alone won't — the
root `SKILL.md` targets Claude Code and uses `${CLAUDE_PLUGIN_ROOT}`, which Codex doesn't expand.

Run it with the orchestrator profile:

```bash
codex --profile vibecheck "Run a vibecheck security audit on this repo."
```

`codex/agents/*.toml` are generated from the Claude agents by `codex/build-agents.py`, so the two
stacks can't drift. Regenerate after editing anything in `agents/`.

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

The seven agents are built and committed at [`codex/agents/`](codex/agents), generated from the
Claude agents by [`codex/build-agents.py`](codex/build-agents.py). Tier profiles are in
[`codex/profiles.toml`](codex/profiles.toml); full setup in
[`reference/CODEX_SETUP.md`](reference/CODEX_SETUP.md).

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
