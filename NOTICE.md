# Notice

This repository is a modified derivative of **skill-creator** from Anthropic's `skills` repository:

- Upstream project: <https://github.com/anthropics/skills/tree/main/skills/skill-creator>
- Upstream copyright: Copyright 2025 Anthropic, PBC
- Upstream license: Apache License 2.0
- Upstream revision inspected during this derivative's creation: `b29e7cf65e5cb78a5ac33d582270551bc74a14eb`

The original Apache License 2.0 text is preserved in `LICENSE.txt`.

## Modifications

The derivative was renamed to `create-agent-skill` and modified to:

- target the Agent Skills standard instead of one agent product;
- describe capability detection and fallbacks for harnesses including Pi, Claude Code, Codex, and Hermes;
- avoid assuming subagents, a browser, artifact-presentation tools, or a particular agent CLI;
- replace hard-coded description-evaluation execution with a configurable runner protocol;
- retain Claude Code behavior as an explicitly optional adapter;
- improve package exclusions and portability-focused validation/tests; and
- update user-facing labels and examples accordingly.

This derivative is maintained independently and is not endorsed by or affiliated with Anthropic.
