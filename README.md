# create-agent-skill

An agent-agnostic skill for creating, testing, reviewing, improving, and packaging [Agent Skills](https://agentskills.io/).

The portable workflow targets the Agent Skills standard and adapts to the capabilities a harness actually exposes. It can be used from Pi, Claude Code, Codex, Hermes, and other compatible harnesses, but does not assume that every harness provides subagents, browser access, artifact presentation, or a noninteractive CLI.

## Install

Clone or copy this repository into the skills directory recognized by your agent harness. The repository root is the skill directory and contains `SKILL.md`.

## What it includes

- A draft → eval → human review → iterate workflow
- Baseline, grading, benchmark, and static-review fallbacks
- Agent Skills frontmatter validation and `.skill` packaging
- An optional runner protocol for automated trigger-description evaluation
- An optional Claude Code runner adapter; other harnesses can provide adapters for their own documented interfaces

## Validate and package

Requires Python 3 and PyYAML.

```bash
python scripts/quick_validate.py .
python -m compileall -q scripts eval-viewer
python -m scripts.package_skill . /tmp/create-agent-skill-dist
```

Trigger optimization is optional. See `SKILL.md` for the runner JSON protocol and usage.

## Attribution and license

> **Modified derivative:** This project is derived from Anthropic's `skill-creator` and has been modified for agent-agnostic use. It is not an official Anthropic project.

The upstream work is available at <https://github.com/anthropics/skills/tree/main/skills/skill-creator>. This derivative preserves the Apache License 2.0 in `LICENSE.txt`; see `NOTICE.md` for modification details.
