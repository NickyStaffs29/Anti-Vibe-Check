# Codex setup

The Codex agents are already built — [`codex/agents/*.toml`](../codex/agents). This is the
install, plus what to check if something doesn't fire.

## Install

```bash
codex plugin marketplace add https://github.com/NickyStaffs29/Anti-Vibe-Check
codex plugin add vibecheck@vibecheck

git clone https://github.com/NickyStaffs29/Anti-Vibe-Check ~/src/anti-vibe-check
mkdir -p ~/.codex/vibecheck
cp ~/src/anti-vibe-check/codex/agents/*.toml ~/.codex/agents/
ln -s ~/src/anti-vibe-check/reference/checklist.md ~/.codex/vibecheck/checklist.md
cat ~/src/anti-vibe-check/codex/profiles.toml >> ~/.codex/config.toml
```

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
| `vc-verifier` — fresh instance | `gpt-5.6-sol` | high | low |

The "Codex default" column is the point. Every one of these ships below the effort this pipeline
wants, so an install that skips `profiles.toml` runs the whole audit underpowered — and it will
still produce a confident-looking report, which is the exact failure mode the tool exists to
prevent.

Each agent's `developer_instructions` opens by naming its required model and effort, and tells it
to say so in its first line of output if it was spawned on anything else. That way a
misconfigured run announces itself instead of quietly degrading.

Verified against `~/.codex/models_cache.json`: sol and terra support up to `ultra`, luna up to
`max`.

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

## If the per-agent model key isn't honored

The TOMLs set `model` and `reasoning_effort` per agent. Codex's agent schema is not formally
documented for these keys, and the bundled example agents use only `name`, `description`, and
`developer_instructions`.

If your Codex build ignores them, nothing breaks — the requirement is also stated in plain text
at the top of every agent's instructions, and the agent will report the mismatch in its first
line. To pin it properly in that case, launch each tier under its profile
(`vibecheck-manager`, `vibecheck-auditor`, `vibecheck-verifier` in `profiles.toml`) rather than
relying on the manifest.
