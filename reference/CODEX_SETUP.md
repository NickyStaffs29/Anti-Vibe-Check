# Codex setup

The Codex agents are already built — [`codex/agents/*.toml`](../codex/agents). This is the
install, plus what to check if something doesn't fire.

## Install

```bash
codex plugin marketplace add https://github.com/NickyStaffs29/Anti-Vibe-Check
codex plugin add vibecheck@vibecheck

git clone https://github.com/NickyStaffs29/Anti-Vibe-Check ~/src/anti-vibe-check
mkdir -p ~/.codex/vibecheck ~/.codex/agents ~/.codex/skills/vibecheck
cp ~/src/anti-vibe-check/codex/agents/*.toml ~/.codex/agents/
ln -sfn ~/src/anti-vibe-check/reference/checklist.md ~/.codex/vibecheck/checklist.md
ln -sfn ~/src/anti-vibe-check/codex/SKILL.md ~/.codex/skills/vibecheck/SKILL.md
cp ~/src/anti-vibe-check/codex/profiles/*.config.toml ~/.codex/
```

That last pair is what gives you `/vibecheck` in Codex. The plugin install alone does not — the
root `SKILL.md` is written for Claude Code and uses `${CLAUDE_PLUGIN_ROOT}`, which Codex does not
expand. `codex/SKILL.md` is the Codex-native entry point, pointing at the Codex agents, the
Codex checklist path, and the tier profiles.

The profile files are copied as `~/.codex/<profile>.config.toml`. Current Codex does not load
legacy `[profiles.<name>]` tables appended to `~/.codex/config.toml`. If you ran an older version
of these instructions, remove those legacy profile tables before running this block; do not
append `codex/profiles.toml` again.

Symlink the checklist rather than copying it. One file, both stacks — that's the property that
keeps the Claude and Codex audits identical, and a copy silently breaks it the first time either
side is edited.

## Run

```bash
codex --profile vibecheck "Run a vibecheck security audit on this repo."
```

The `vibecheck` profile puts the orchestrator on `gpt-5.6-sol` at high reasoning. It recons the
stack, pre-marks checks that can't apply, and hands a scoped work order to `vibecheck-manager`.

## Tiers

| Agent | Model | Effort | Codex default |
|---|---|---|---|
| orchestrator (your session) | `gpt-5.6-sol` | high | low |
| `vibecheck-manager` | `gpt-5.6-terra` | `max` | medium |
| `vc-secrets` `vc-access` `vc-injection` `vc-abuse` `vc-surface` | `gpt-5.6-luna` | `max` | medium |
| `vc-verifier` — fresh instance | `gpt-5.6-sol` | `max` | low |

The "Codex default" column is the point. Every one of these ships below the effort this pipeline
wants, so an install that skips `codex/profiles/*.config.toml` runs the whole audit underpowered — and it will
still produce a confident-looking report, which is the exact failure mode the tool exists to
prevent.

Each agent's `developer_instructions` opens by naming its required model and effort. That header
states the requirement for whoever reads the file — it doesn't enforce anything at runtime, and a
model can't reliably report its own reasoning-effort setting, so it isn't asked to. Enforcement is
`codex/profiles/*.config.toml`, below.

Verified against `~/.codex/models_cache.json`: sol and terra support up to `ultra`, luna up to
`max`.

## Sandbox mode on the auditor and verifier profiles

`vibecheck-auditor` and `vibecheck-verifier` in `codex/profiles/vibecheck-auditor.config.toml` and
`codex/profiles/vibecheck-verifier.config.toml` set `sandbox_mode =
"read-only"`. That's Codex's own OS-enforced sandbox, not an instruction — a command run under it
is blocked from writing regardless of what the agent's prompt says, which is a stronger guarantee
than "Bash is told not to mutate anything."

Verified against the current Codex CLI config reference
(`developers.openai.com/codex/config-reference`, which redirects to
`learn.chatgpt.com/docs/config-file/config-reference`) and its companion sample config
(`.../config-sample`): `sandbox_mode` accepts `read-only | workspace-write |
danger-full-access`, and profile files use the same fields as `config.toml` — the sample's
example CI profile sets `sandbox_mode = "read-only"` directly alongside `model` and
`approval_policy`. The security reference (`.../docs/agent-approvals-security`) confirms
`read-only` also turns network access off, same as the default.

One operational caveat:

- **Network access.** S1.6's dependency-CVE check runs the ecosystem's own auditor (`npm audit`,
  `pip-audit`, etc.), and some of those need to reach a registry. If `sandbox_mode = "read-only"`
  blocks that, S1.6 degrades to `NEEDS-REVIEW` under the sandboxed profile instead of running.
  Not verified either way here.

The profile files use the current format: `~/.codex/vibecheck.config.toml`,
`~/.codex/vibecheck-manager.config.toml`, `~/.codex/vibecheck-auditor.config.toml`, and
`~/.codex/vibecheck-verifier.config.toml` each contain top-level keys. Do not append them to
`config.toml` or convert them back into `[profiles.<name>]` tables. If an old install already
has those tables in `config.toml`, remove the legacy sections before launching with `--profile`.

## Fix flow is Claude-first

`vc-fixer` is generated into `codex/agents/vc-fixer.toml` like every other agent, but Codex has
no `/vibecheck-fix` entry point yet — there is no Codex-native command that spawns
`vibecheck-manager` in fix mode the way `codex/SKILL.md` does for the audit. Run `/vibecheck-fix`
from Claude Code until that gap is closed; this is a known leftover, not an intentional
difference between the two stacks.

## Keeping the two stacks in sync

`codex/agents/*.toml` are **generated** from the Claude agents in `agents/*.md`:

```bash
python3 codex/build-agents.py
```

Edit `agents/*.md`, regenerate, commit both. Don't hand-edit the TOMLs — the next regeneration
overwrites them, and the drift between stacks is exactly what this design prevents everywhere
else.

The generator swaps the Claude tier line for the Codex one, repoints the checklist path, and
carries the section-specific method guidance across untouched — the sink-first tracing in S3, the
three-question endpoint procedure in S2, the raw-body subtlety in S4.3. That guidance is where
the audit quality lives.

## Reasoning effort comes from profiles, not the manifest

Codex's agent schema accepts `model` but **not** `reasoning_effort`. An unknown field is not
ignored — Codex discards the entire agent file with `Ignoring malformed agent role definition`.
Verified with `codex doctor` on codex-cli 0.144.1.

So the TOMLs set `model` only, and effort is carried by **`codex/profiles/*.config.toml`** — the real
mechanism. `model_reasoning_effort` is a valid config key, so launching under a tier profile pins
it. The instruction header in every agent also names the required model and effort, but that's
documentation for whoever reads the file, not a check the agent can run on itself.

If you ever add a field to these TOMLs, run `codex doctor` afterward and check the startup
warnings. A rejected agent file fails silently at run time — the agent simply doesn't exist, and
the orchestrator will improvise around the gap rather than error.
