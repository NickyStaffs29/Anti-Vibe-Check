---
name: vibecheck
description: Run a 30-point security audit targeting the failure modes common to AI-assisted and rapidly-built apps — leaked keys and public build prefixes, RLS gaps, IDOR, client-supplied identity, mass assignment, injection, XSS, SSRF, unverified webhooks, client-trusted prices, public buckets, CORS, CSRF, JWT handling, error leakage. Use when the user says "vibecheck", asks to audit or review security, check for vulnerabilities, asks "is my app secure", "did I leak any keys", "can someone see other users' data", or wants a pre-launch security check on a vibe-coded app. Read-only.
---

# vibecheck

A 30-check security audit: five section auditors in parallel, then an adversarial verification
pass. No agent in this pipeline holds `Write` or `Edit` — Bash stays instruction-bound to
inspection, not sandboxed out of writing. (`vibecheck-auditor` and `vibecheck-verifier` do add a
`sandbox_mode = "read-only"` platform constraint — see `codex/profiles.toml`.)

This is the **Codex** entry point. The Claude Code equivalent is `SKILL.md` at the repo root;
both read the same checklist so the two stacks stay identical.

Arguments (all optional): a path to audit (default: cwd) · `--deep` to run the section auditors
on `gpt-5.6-terra` instead of `gpt-5.6-luna` · `--section S2` for one section plus verification.

## Pipeline

| Piece | Model | Effort | Scope |
|---|---|---|---|
| you (this session) | `gpt-5.6-sol` | high | Recon and scope, final acceptance |
| `vibecheck-manager` | `gpt-5.6-terra` | `max` | Delegates, collects, assembles the report |
| `vc-secrets` | `gpt-5.6-luna` | `max` | S1 Secrets & Supply Chain — 6 checks |
| `vc-access` | `gpt-5.6-luna` | `max` | S2 Access Control — 7 checks |
| `vc-injection` | `gpt-5.6-luna` | `max` | S3 Injection & Untrusted Input — 5 checks |
| `vc-abuse` | `gpt-5.6-luna` | `max` | S4 Abuse & Money — 4 checks |
| `vc-surface` | `gpt-5.6-luna` | `max` | S5 Surface & Exposure — 8 checks |
| `vc-verifier` | `gpt-5.6-sol` **fresh** | `max` | Refutes every FAIL, re-audits every unevidenced PASS |

**Effort is the load-bearing column.** Codex defaults are `sol=low`, `terra=medium`,
`luna=medium` — max reasoning is off unless something turns it on. A cheap model at max reasoning
substantially outperforms the same model at its default, which is what makes five parallel
auditors cheaper and more thorough than one expensive pass.

The 30 checks live in `~/.codex/vibecheck/checklist.md` — one file, read by every agent. No agent
restates a check.

## Procedure

**1. Recon the target yourself.** Establish: language and framework, backend (Supabase /
Firebase / custom API / none), auth mechanism, payment provider if any, the client/server
boundary, and the current commit SHA. Read the checklist so you know what the 30 checks are
before you scope them.

Determine which checks cannot apply — no payment provider means most of S4 is N/A, a static site
with no backend means most of S2 is N/A. Pre-marking these stops auditors from inventing findings
to look useful.

**1a. Abort before spawning anything if there is nothing to audit.** Cheap check, done first:

- Does the target contain application source at all? (`rg --files` / `find . -type f`)
- Is it a git repo? (`git rev-parse HEAD`)
- Are there dependency manifests, routes, schema — any of the surfaces the 30 checks describe?

If the answer is no, **stop and say so.** Do not spawn the manager. Do not spawn five auditors at
max effort to rediscover an empty directory — that costs a full pipeline run and returns
30 × NEEDS-REVIEW, which is correct but worthless.

Report what you found (empty directory, no repo, docs-only, wrong path) and ask for the real
target. Name the most likely cause: an invocation with no path argument audits the current
working directory, and in Codex that is often the session scratch directory rather than a project.

An INCONCLUSIVE result is honest and it is not a clean bill of health — but catching it here costs
one `ls` instead of seven agents.


**2. Spawn `vibecheck-manager`** with a self-contained work order: repo path, your recon
findings, pre-marked N/A checks with reasons, and any `--deep` / `--section` flag. It spawns the
five section auditors in parallel, then `vc-verifier`, then assembles `VIBECHECK_REPORT.md` and
adds it to `.gitignore`.

**3. Accept the result.** Report: counts by verdict across all 30, every CRITICAL in one line
each with its `file:line`, the single highest-priority fix and why it is first, and any coverage
gaps needing a human to check a hosting dashboard.

Then stop. Do not begin fixing — fixes are a separate, explicitly-invoked step, so an audit never
silently rewrites auth code.

## Non-negotiables

- **Evidence or it doesn't count.** Every PASS cites the code that makes it pass; every FAIL
  cites `file:line` with the code quoted. An audit that rubber-stamps is worse than no audit —
  it manufactures confidence and the user stops looking.
- **`NEEDS-REVIEW` is a real verdict.** Config living in a Supabase or Vercel dashboard cannot be
  confirmed from code. Name the screen a human must check; never infer it from client code.
- **`VIBECHECK_REPORT.md` goes in `.gitignore` on every run.** It is a written map of the app's
  live vulnerabilities.
- **Leaked credentials are fixed by rotation, not deletion.** Removing the line leaves the key
  live and still in git history.
- **Effort is enforced by `codex/profiles.toml`, not by an agent noticing its own setting.** A
  model can't reliably report its own reasoning-effort level. If a run looks underpowered, check
  that the profile loaded — don't expect an agent to flag it.
