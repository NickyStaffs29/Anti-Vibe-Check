---
name: vibecheck
description: Run a 30-point security audit targeting the failure modes common to AI-assisted and rapidly-built apps — leaked keys and public build prefixes, RLS gaps, IDOR, client-supplied identity, mass assignment, injection, XSS, SSRF, unverified webhooks, client-trusted prices, public buckets, CORS, CSRF, JWT handling, error leakage. Use when the user asks to audit or review security, check for vulnerabilities, asks "is my app secure", "did I leak any keys", "can someone see other users' data", or wants a pre-launch security check on a vibe-coded app. Read-only.
---

# vibecheck

A 30-check security audit: five section auditors in parallel, then an adversarial verification
pass. Read-only end to end — nothing in this pipeline edits source.

Arguments (all optional): a path to audit (default: cwd) · `--deep` to run the section auditors
on Opus instead of Sonnet · `--section S2` to run one section plus verification.

## Pipeline

| Piece | Model | Effort | Scope |
|---|---|---|---|
| you (main session) | Fable | high | Recon and scope, final acceptance |
| `vibecheck-manager` | Opus | `max` | Delegates, collects, assembles the report |
| `vc-secrets` | Sonnet | `max` | S1 Secrets & Supply Chain — 6 checks |
| `vc-access` | Sonnet | `max` | S2 Access Control — 7 checks |
| `vc-injection` | Sonnet | `max` | S3 Injection & Untrusted Input — 5 checks |
| `vc-abuse` | Sonnet | `max` | S4 Abuse & Money — 4 checks |
| `vc-surface` | Sonnet | `max` | S5 Surface & Exposure — 8 checks |
| `vc-verifier` | Opus (fresh) | `high` | Refutes every FAIL, re-audits every unevidenced PASS |

**The effort column is not decoration.** Max reasoning is off by default, and a cheap model at
max reasoning substantially outperforms the same model at its default — that trade is what makes
five parallel auditors cheaper and more thorough than one expensive pass. Section auditing is
mechanical evidence-gathering, where thoroughness beats sophistication.

Each agent pins its own tier with an `effort` key in its frontmatter, which overrides the
session's effort level for as long as that agent runs. That's the actual mechanism — nothing
needs to be passed at spawn time.

The 30 checks live in `${CLAUDE_PLUGIN_ROOT}/reference/checklist.md` — one file, read by every
agent. No agent restates a check, so the Claude and Codex implementations cannot drift apart.

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


**2. Spawn `vibecheck-manager`**, with a self-contained work order: repo path, your recon
findings, pre-marked N/A checks with reasons, and any `--deep` / `--section` flag. Its
frontmatter pins Opus at `max` effort. It spawns the five section auditors in parallel, then
`vc-verifier`, then assembles `VIBECHECK_REPORT.md` and adds it to `.gitignore`.

**3. Accept the result.** Report to the user: counts by verdict across all 30, every CRITICAL in
one line each with its `file:line`, the single highest-priority fix and why it is first, and any
coverage gaps needing a human to check a dashboard.

Then stop. Do not begin fixing — `/vibecheck-fix` is separate and explicitly invoked, so an audit
never silently rewrites auth code.

## What makes it worth running

Every check traces to a real failure mode in AI-assisted code, and several carry the *reason* the
hole appears — the build errored so `NEXT_PUBLIC_` got added, a fetch threw CORS so the wildcard
went in, an image wouldn't load so the bucket went public.

It also catches the wrong fixes, which is where a generic scan gives a clean bill of health: an
ownership check compared against a client-supplied user ID (S2.3), webhook verification running
against an already-parsed body (S4.3), `decode()` where `verify()` belongs (S5.5). Each of those
reads as correct.

The verifier re-audits S1.3, S2.2, S2.3, S4.3 and S5.5 unconditionally, because those are where a
plausible-looking PASS is most often wrong.

## Non-negotiables

- **Evidence or it doesn't count.** Every PASS cites the code that makes it pass; every FAIL cites
  `file:line` with the code quoted. An audit that rubber-stamps is worse than no audit — it
  manufactures confidence and the user stops looking.
- **`NEEDS-REVIEW` is a real verdict.** Config living in a Supabase or Vercel dashboard cannot be
  confirmed from code. Name the screen a human must check; never infer it from client code.
- **`VIBECHECK_REPORT.md` goes in `.gitignore` on every run.** It is a written map of the app's
  live vulnerabilities.
- **Leaked credentials are fixed by rotation, not deletion.** Removing the line leaves the key
  live and still in git history.
- If the target isn't a git repo, say so — S1.4 (git history) becomes `NEEDS-REVIEW` and the
  report header has no SHA.

## Codex

Native Codex agents live in `${CLAUDE_PLUGIN_ROOT}/codex/agents/`. Setup is in
`${CLAUDE_PLUGIN_ROOT}/reference/CODEX_SETUP.md`.
