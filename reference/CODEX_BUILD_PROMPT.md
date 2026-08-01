# Codex build prompt — vibecheck mirror

Paste everything below the line into a **fresh Codex session**. It is self-contained.

---

Build the Codex-side mirror of a security audit pipeline called **vibecheck**. The Claude Code
side already exists and works; you are building the equivalent for Codex so the same audit runs
in either stack, from any session, with identical checks and identical output.

## What already exists (read these first, don't recreate them)

- `~/.claude/plugins/marketplaces/vibecheck/reference/checklist.md` — **the canonical checklist.** 30 security checks
  across 5 sections, plus binding evidence rules and the report contract. This file is the single
  source of truth for BOTH stacks. Do not copy its contents into any agent file, and do not
  rewrite or "improve" the checks — divergence between the two implementations is the specific
  failure this design exists to prevent.
- `~/.claude/plugins/marketplaces/vibecheck/agents/vibecheck-manager.md`, `vc-secrets.md`, `vc-access.md`,
  `vc-injection.md`, `vc-abuse.md`, `vc-surface.md`, `vc-verifier.md` — the Claude agents.
  Read all seven. Your `.toml` agents are ports of these, not new designs.
- `~/.claude/plugins/marketplaces/vibecheck/SKILL.md` — the Claude entry point (recon → delegate →
  accept), and `~/.claude/plugins/marketplaces/vibecheck/commands/vibecheck-fix.md` — the fix command.

Read the checklist and all seven agent files before writing anything.

If the plugin isn't installed locally, clone the repo instead and read from there:
`git clone https://github.com/NickyStaffs29/Anti-Vibe-Check` — same files, same layout.

## Architecture

```
Codex main session (gpt-5.6-sol) — PM
   │  Recons the target: stack, backend, auth, payment provider, client/server boundary,
   │  commit SHA. Pre-marks checks that cannot apply. Owns scope and final acceptance.
   │
   └─→ vibecheck-manager (gpt-5.6-terra)
          │  Converts the PM's scope into five self-contained work orders. Delegates only.
          │
          ├─→ vc-secrets    (gpt-5.6-luna) — S1 Secrets & Supply Chain    (6 checks)
          ├─→ vc-access     (gpt-5.6-luna) — S2 Access Control            (7 checks)
          ├─→ vc-injection  (gpt-5.6-luna) — S3 Injection & Input         (5 checks)   ← PARALLEL
          ├─→ vc-abuse      (gpt-5.6-luna) — S4 Abuse & Money             (4 checks)
          ├─→ vc-surface    (gpt-5.6-luna) — S5 Surface & Exposure        (8 checks)
          │
          └─→ vc-verifier   (gpt-5.6-terra) — adversarial pass over all 30
```

The five section auditors run **in parallel**. The sections are independent, so serializing
them costs wall-clock and buys nothing. (This differs from the existing Compute Squad agents in
`~/.codex/agents/`, which are strictly sequential because each stage consumes the previous
stage's output. Don't copy that pattern here.)

## Model tier mapping

These are verified from `~/.codex/models_cache.json` — use them exactly.

| Tier | Role | Claude side | Codex side | Codex's own description |
|------|------|-------------|------------|--------------------------|
| 1 | PM / orchestrator | Fable | `gpt-5.6-sol` | "Latest frontier agentic coding model" |
| 2 | Manager + Verifier | Opus | `gpt-5.6-terra` | "Balanced agentic coding model for everyday work" |
| 3 | Section auditors | Sonnet | `gpt-5.6-luna` | "Fast and affordable agentic coding model" |

Tier 2 holds the judgment: the manager scopes the work, and the verifier decides what is real.
Tier 3 does mechanical evidence-gathering. The audit's correctness rests on tier 2, which is why
the verifier is never demoted to Luna even though it is the most expensive single agent in the run.

**Check whether Codex agent `.toml` files support a per-agent model key** — inspect the current
schema for codex-cli 0.144.1 rather than assuming. The existing agents in `~/.codex/agents/` use
only `name`, `description`, and `developer_instructions`, which may mean the key is unsupported
or merely unused. If a model key exists, set it per the table. If it does not, state the required
tier explicitly at the top of each agent's `developer_instructions` and have the manager select
the model when it spawns each worker. Tell me which of the two you found.

## What to build

**1. Shared checklist, not a copy.**
```
mkdir -p ~/.codex/vibecheck
ln -s ~/.claude/plugins/marketplaces/vibecheck/reference/checklist.md ~/.codex/vibecheck/checklist.md
```
Symlink so there is exactly one source of truth. If your sandbox blocks reading through the
symlink, copy the file instead and add a header line to both copies naming the other path as a
mirror that must be updated in lockstep — but try the symlink first, and tell me which you used.

Every agent you write references `~/.codex/vibecheck/checklist.md` and reads it in full before
starting.

**2. Seven agents in `~/.codex/agents/`** — global, so they work from any Codex session:
`vibecheck-manager.toml`, `vc-secrets.toml`, `vc-access.toml`, `vc-injection.toml`,
`vc-abuse.toml`, `vc-surface.toml`, `vc-verifier.toml`.

Port the corresponding Claude agent's instructions into `developer_instructions`, matching the
existing `.toml` style in `~/.codex/agents/`. Keep the section-specific method guidance intact —
the sink-first tracing in S3, the three-question endpoint procedure in S2, the raw-body subtlety
in S4.3. That guidance is where the audit quality lives; a generic "audit section S2" prompt
produces a generic audit.

**3. An entry point.** Determine where custom slash commands live for codex-cli 0.144.1 —
check `~/.codex/prompts/`, `~/.codex/skills/` (which already exists and has entries), and the
current docs. Create a `vibecheck` entry point there porting `~/.claude/skills/vibecheck/SKILL.md`,
and a `vibecheck-fix` entry point porting `~/.claude/skills/vibecheck/commands/vibecheck-fix.md`. It must be
invocable from any session in any directory. Tell me the exact invocation.

## Design constraints — do not relax these

- **The audit is read-only end to end.** Section auditors get no write capability. Bash/shell is
  for inspection only: no installs, no `--fix`, no lockfile changes, no live requests against a
  running app. Fixing is a separate, explicitly-invoked command.
- **The evidence rules in the checklist are binding.** Every PASS cites the code that makes it
  pass; every FAIL cites `file:line` with the code quoted; `NEEDS-REVIEW` is the correct verdict
  when evidence is out of reach. An audit that rubber-stamps is worse than no audit, because it
  manufactures confidence and the user stops looking.
- **The verifier is adversarial in both directions.** It tries to refute every FAIL, and it
  re-audits every PASS that lacks cited evidence — plus S1.3, S2.2, S2.3, S4.3 and S5.5
  unconditionally, because those five are where a plausible-looking PASS is most often wrong.
  Unresolvable checks land on `NEEDS-REVIEW`, never on PASS.
- **`VIBECHECK_REPORT.md` goes in `.gitignore` on every run.** It is a written map of the app's
  live vulnerabilities; committing it to a public repo is worse than any single finding in it.
- **Config that lives in a hosting dashboard** (Supabase RLS toggles, S3 bucket policy, Vercel
  env vars) cannot be confirmed from code. It is `NEEDS-REVIEW` naming the exact screen a human
  must check — never inferred from how the client happens to query.
- Output format must match the Claude side exactly, so a report is stack-agnostic and two runs
  are diffable.

## Done means

Report back with: the file paths you created, whether the symlink or the copy was used, whether
per-agent model keys are supported in this Codex version, the exact command to invoke the audit,
and the result of one real end-to-end run against a repo of your choosing (or a clear statement
that you had no suitable repo to test against — do not claim a run you didn't do).
