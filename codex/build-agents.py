#!/usr/bin/env python3
"""Generate Codex agent TOMLs from the Claude Code agent markdown.

The Claude agents in ../agents/*.md are the source. This emits the Codex
equivalents so the two stacks can't drift — same instructions, same checklist,
different manifest format.

Run from anywhere:  python3 codex/build-agents.py
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "agents"
OUT = ROOT / "codex" / "agents"

# sol-advisor tiers (github.com/daniel_mac8 pattern), verified against
# ~/.codex/models_cache.json. Defaults are sol=low, terra=medium, luna=medium —
# max reasoning is OFF by default, which is the whole point of setting it here.
TIERS = {
    "vibecheck-manager": ("gpt-5.6-terra", "max"),
    "vc-secrets":        ("gpt-5.6-luna",  "max"),
    "vc-access":         ("gpt-5.6-luna",  "max"),
    "vc-injection":      ("gpt-5.6-luna",  "max"),
    "vc-abuse":          ("gpt-5.6-luna",  "max"),
    "vc-surface":        ("gpt-5.6-luna",  "max"),
    "vc-fixer":          ("gpt-5.6-luna",  "max"),
    "vc-verifier":       ("gpt-5.6-sol",   "high"),
}

# Claude-stack -> Codex-stack terminology. Order matters: longest first.
TERMS = [
    ("one message, five Task calls", "one turn, five parallel sub-agent spawns"),
    ("five Task calls", "five parallel sub-agent spawns"),
    ("Task calls", "sub-agent spawns"),
    ("Task call", "sub-agent spawn"),
    ("`effort: 'max'`", "`model_reasoning_effort = \"max\"`"),
    ("effort: 'max'", 'the `vibecheck-auditor` profile (max reasoning)'),
    ("effort: 'high'", 'the `vibecheck-verifier` profile (high reasoning)'),
    ("on Opus, still at `max`", "on `gpt-5.6-terra`, still at max reasoning"),
    ("spawn them on Opus", "spawn them on `gpt-5.6-terra`"),
    ("Spawn `vc-verifier` on Opus", "Spawn `vc-verifier` on `gpt-5.6-sol`"),
    ("Five Sonnet auditors", "Five Luna auditors"),
    ("one Opus pass", "one Sol pass"),
    ("(Fable)", "(the orchestrator session)"),
    ("Fable", "the orchestrator"),
    ("Opus", "`gpt-5.6-terra`"),
    ("Sonnet", "`gpt-5.6-luna`"),
]

CHECKLIST = "~/.codex/vibecheck/checklist.md"

# Codex per-model defaults, from ~/.codex/models_cache.json.
DEFAULTS = {"gpt-5.6-sol": "low", "gpt-5.6-terra": "medium", "gpt-5.6-luna": "medium"}


def parse(path):
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise SystemExit(f"{path.name}: no frontmatter")
    fm, body = m.group(1), m.group(2).strip()
    name = re.search(r"^name:\s*(.+)$", fm, re.M).group(1).strip()
    desc = re.search(r"^description:\s*(.+?)(?=\n[a-z_]+:|\Z)", fm, re.M | re.S)
    desc = " ".join(desc.group(1).split())
    return name, desc, body


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for src in sorted(SRC.glob("*.md")):
        name, desc, body = parse(src)
        if name not in TIERS:
            print(f"skip {name} (no tier assigned)")
            continue
        model, effort = TIERS[name]
        for a, b in TERMS:
            desc = desc.replace(a, b)

        # Repoint the checklist at the Codex-side path.
        body = re.sub(r"`\$\{CLAUDE_PLUGIN_ROOT\}/reference/checklist\.md`[^\n]*?\)",
                      f"`{CHECKLIST}`", body)
        body = body.replace("${CLAUDE_PLUGIN_ROOT}/reference/checklist.md", CHECKLIST)

        # Translate Claude-stack terminology. The bodies are written for Claude Code;
        # left untranslated, a Codex agent reads instructions naming a tool it does not
        # have and model tiers that are not its own, and improvises around them.
        for a, b in TERMS:
            body = body.replace(a, b)

        # Swap the Claude-side tier line for the Codex one.
        body = re.sub(r"^> \*\*Tier:\*\*.*?\n\n", "", body, flags=re.S | re.M)
        header = (
            f"RUN THIS AGENT ON `{model}` AT `{effort}` REASONING EFFORT. Max reasoning is off by "
            f"default in Codex ({DEFAULTS[model]} for this model) — if you were spawned without it, "
            f"say so in your first line of output and continue. A section audited at default "
            f"reasoning is worth less than one that says it was.\n\n"
        )
        instructions = header + body.lstrip()

        if '"""' in instructions:
            raise SystemExit(f"{name}: body contains a TOML triple-quote delimiter")

        # NOTE: Codex's agent schema accepts `model` but NOT `reasoning_effort` —
        # an unknown field makes it discard the whole file ("Ignoring malformed agent
        # role definition"). Verified with `codex doctor` on codex-cli 0.144.1.
        # Effort is carried by codex/profiles.toml plus the directive in the
        # instruction header below.
        toml = (
            f'name = "{name}"\n'
            f'description = "{desc}"\n'
            f'model = "{model}"\n'
            f'developer_instructions = """\n{instructions}"""\n'
        )
        (OUT / f"{name}.toml").write_text(toml)
        print(f"wrote {name}.toml  ({model} @ {effort})")


if __name__ == "__main__":
    main()
