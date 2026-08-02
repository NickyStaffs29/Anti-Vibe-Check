---
description: Apply fixes from a VIBECHECK_REPORT.md, most-exploitable first, one severity tier at a time with a stop between tiers.
argument-hint: [--tier CRITICAL|HIGH|MEDIUM|LOW] [--only S2.3,S4.1]
allowed-tools: Task, Read, Write, Edit, Grep, Glob, Bash
---

Apply fixes from an existing `VIBECHECK_REPORT.md`.

Arguments: `$ARGUMENTS` (may be empty)
- `--tier CRITICAL` → fix only that severity tier. Default: CRITICAL only.
- `--only S2.3,S4.1` → fix exactly these check IDs.

## Procedure

**1. Read the report.** If `VIBECHECK_REPORT.md` doesn't exist, stop and tell the user to run `/vibecheck` first. Do not audit from scratch here — this command applies known findings.

**2. Check the report is current.** Compare the commit SHA in the report header against `HEAD`.
If they differ, say so and ask whether to proceed or re-audit. Fixing against a stale report
wastes work and can reintroduce a resolved issue.

**3. Confirm scope before touching anything.** List what you are about to change: the check IDs,
the files, and a one-line description of each fix. Get the user's go-ahead. Security fixes
change authorization behaviour — a wrong one locks out real users or silently opens a path.

**4. Fix one severity tier at a time**, most-exploitable first. Spawn `vibecheck-manager` with
the fix scope; it routes per-section work to `vc-fixer`. Never mix tiers in one pass.

**5. Stop at the tier boundary.** When a tier is complete, report what changed and wait. Do not
self-sequence into the next tier.

## Rules
- **Rotation, not deletion.** A leaked credential (S1.1–S1.4) is fixed by rotating the key at
  the provider. Removing the line from the code does not un-leak it — it is still in git
  history and still valid. Never mark a leaked secret fixed on a code change alone; tell the
  user which key to rotate where, and leave the finding open until they confirm.
- **Never weaken a control to make something work.** If a fix breaks a feature, report the
  conflict — do not resolve it by loosening CORS, disabling RLS, or removing a check.
- Each fix keeps to its finding. No opportunistic refactoring inside a security change; it
  makes the diff unreviewable, which is the last thing you want in an auth change.
- Re-run `vc-verifier` on the diff when the tier is done, and report anything it overturns.
- If a fix needs a dashboard change (bucket policy, RLS toggle, env var, WAF rule), you cannot
  make it. Name the exact screen and leave the finding open.
