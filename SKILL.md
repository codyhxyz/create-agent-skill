---
name: create-agent-skill
description: Create, revise, evaluate, and package Agent Skills. Use when a user wants to build a new SKILL.md, improve an existing skill, test skill behavior against realistic prompts and baselines, analyze benchmark results, optimize skill-trigger descriptions, or prepare a distributable .skill archive. Preserve a draft, evaluation, human-review, and iteration loop while adapting execution to the current agent harness.
license: Apache-2.0
compatibility: Portable core targets the Agent Skills standard. Python 3 is needed for bundled validation, packaging, benchmark, and review helpers; automated runs require a compatible runner adapter, while manual evaluation remains supported.
---

> Modified from Anthropic's `skill-creator` for agent-agnostic use; see `NOTICE.md`.

# Create Agent Skill

Create or improve Agent Skills through a practical loop:

1. Capture intent and constraints.
2. Draft the skill.
3. Run realistic evaluations, with a baseline when feasible.
4. Grade objective checks and ask a human to review subjective quality.
5. Improve the skill from the evidence.
6. Repeat at larger scope until the user is satisfied.
7. Validate and package the result.

Keep this loop flexible. For a small or subjective skill, a few manually reviewed examples may be more useful than a large benchmark.

## Detect the harness before choosing mechanics

The portable core targets agents and harnesses that implement the Agent Skills standard. Pi, Claude Code, Codex, Hermes, and other harnesses can differ in skill discovery, delegation, command execution, browser access, and artifact presentation. Do not claim a capability merely from the harness name; inspect the tools and environment available in the current session.

Choose the strongest available execution mode:

1. **Isolated delegated runs:** use subagents, jobs, or equivalent isolation when available.
2. **External runner:** use a configured adapter that can start a fresh agent invocation and report whether it loaded the candidate skill.
3. **Inline fallback:** execute test prompts serially in the current session, clearly label this as a sanity check rather than an independent benchmark, and rely more heavily on human review.

Likewise, open the review UI only when browser access exists. Otherwise generate static HTML or review the outputs directly in conversation. If token or duration metadata is unavailable, omit it rather than estimating it.

## Communicate for the user's level

Use plain language by default. Briefly define terms such as assertion (an objective check), benchmark (a repeatable comparison), or JSON when the user may not know them. Explain the reason for each stage rather than forcing ceremony.

## Create or revise a skill

### Capture intent

Extract answers already present in the conversation, then ask only for missing details:

1. What should the skill enable an agent to do?
2. When should it activate?
3. What outputs or artifacts should it produce?
4. Which edge cases, dependencies, and safety constraints matter?
5. Would objective tests help, or is human judgment the main measure?

When updating an installed skill, preserve its existing directory and frontmatter name unless the user explicitly requests a rename. Copy read-only installations to a writable working directory before editing.

### Research selectively

Inspect examples, input files, documentation, and related skills when useful. Parallelize research only if the harness supports it; otherwise research inline. Confirm important assumptions with the user before drafting.

### Write `SKILL.md`

A standard skill has this shape:

```text
skill-name/
├── SKILL.md             # required
├── scripts/             # optional deterministic helpers
├── references/          # optional material loaded as needed
└── assets/              # optional templates and output resources
```

The frontmatter requires:

- `name`: lowercase kebab-case, at most 64 characters
- `description`: what the skill does and when to use it, at most 1024 characters

Optional standard fields include `license`, `compatibility`, `metadata`, and `allowed-tools`. Put activation cues in `description`, because many harnesses use metadata to decide whether to load the body.

Use progressive disclosure:

1. Metadata is always cheap to inspect.
2. The `SKILL.md` body contains the working instructions.
3. Bundled resources are loaded or executed only when needed.

Keep the main body focused (under roughly 500 lines is a useful target). Move detailed variant guidance into clearly linked reference files. Prefer imperative instructions, explain why constraints matter, and avoid brittle lists of absolute rules.

Never add surprising, malicious, or unauthorized behavior. A skill's implementation must match its stated purpose.

### Draft realistic test cases

Propose two or three prompts that resemble real user requests and ask the user to confirm them. Save them to `evals/evals.json`:

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "A realistic user request",
      "expected_output": "What a successful result should contain",
      "files": []
    }
  ]
}
```

Do not invent assertions before the task and success criteria are understood. See `references/schemas.md` for complete evaluation and benchmark schemas.

## Run evaluations

Place generated results outside the skill itself, normally in a sibling `<skill-name>-workspace/`. Organize each pass as `iteration-N/<eval-name>/` and each configuration beneath that, such as `with_skill/`, `without_skill/`, or `old_skill/`.

### Select a baseline

- For a new skill, compare against a run with no candidate skill when isolated execution is available.
- For an existing skill, snapshot the original and use it as `old_skill` when that comparison answers the user's question.
- In inline mode, skip a baseline if the current context would contaminate it. State the limitation instead of presenting a misleading comparison.

Use the same prompt, inputs, model class, and relevant permissions for candidate and baseline runs.

### Execute each prompt

When the harness supports independent agents, launch candidate and baseline runs in the same batch so environmental drift is minimized. If only serial execution exists, alternate configurations or randomize order where practical.

For each evaluation, write `eval_metadata.json`:

```json
{
  "eval_id": 1,
  "eval_name": "descriptive-name",
  "prompt": "The exact test prompt",
  "assertions": []
}
```

Save user-facing artifacts under each run's `outputs/`. Save transcripts only when available and appropriate; inspect them for wasted work or repeated patterns. Record actual timing or token data in `timing.json` only if the harness reports it.

### Draft and grade assertions

While runs execute, add objective assertions that measure the user's success criteria. Use descriptive checks and avoid forcing quantitative measures onto taste, tone, or design quality.

Grade with an independent evaluator if available, or grade inline. Prefer deterministic scripts for machine-checkable properties. Each item in `grading.json` must use `text`, `passed`, and `evidence` as documented in `references/schemas.md`.

### Aggregate results

From this skill directory, run:

```bash
python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
```

This creates `benchmark.json` and `benchmark.md`. Read the aggregate and the individual runs. Look for non-discriminating assertions, flaky cases, large variance, quality regressions, and time/token tradeoffs. `agents/analyzer.md` contains a deeper analysis guide. If there is too little independent data for meaningful statistics, summarize qualitative findings instead.

### Put results in front of a human

Prefer review before revising; the authoring agent may miss subjective problems.

With browser access:

```bash
python eval-viewer/generate_review.py \
  <workspace>/iteration-N \
  --skill-name "my-skill" \
  --benchmark <workspace>/iteration-N/benchmark.json
```

For iteration 2+, add `--previous-workspace <workspace>/iteration-(N-1)`.

Without browser access, generate a standalone file:

```bash
python eval-viewer/generate_review.py \
  <workspace>/iteration-N \
  --skill-name "my-skill" \
  --static <workspace>/iteration-N/review.html
```

If neither viewing nor file transfer is available, show each prompt, output, grade, and benchmark summary in conversation and ask for feedback there. A static viewer downloads `feedback.json`; move that file into the workspace before the next iteration.

## Improve and iterate

Read human feedback first. Empty feedback generally means the output was acceptable. Then revise with these principles:

1. **Generalize from examples.** Fix the underlying instruction, not just the observed prompt.
2. **Keep the skill lean.** Remove guidance that causes unproductive work.
3. **Explain why.** Models follow durable reasoning better than unexplained rigidity.
4. **Bundle repeated deterministic work.** If several runs recreate the same helper, add one reusable script.
5. **Preserve evidence.** Keep prior iterations so improvements can be compared.

Rerun the confirmed test set into a new iteration and repeat human review. Stop when the user is satisfied, feedback is clear, or further iterations are not producing meaningful gains. Expand the test set before making strong performance claims.

For rigorous A/B judgment, `agents/comparator.md` describes blind comparison. It is optional and requires an independent evaluator; otherwise ask the human to compare unlabeled outputs.

## Optionally optimize the trigger description

Description optimization is useful only when the target harness exposes skill-loading behavior to an automated runner. It is not required to finish a good skill.

Create a balanced set of realistic should-trigger and near-miss should-not-trigger queries. Include varied wording and substantive tasks; trivial or unrelated negatives reveal little. Let the user review this set, using `assets/eval_review.html` when practical or editing JSON directly.

The automation scripts use a runner protocol rather than assuming a particular CLI. Configure a command with `--runner` or `AGENT_SKILL_RUNNER`. The command receives one JSON object on stdin:

- `{"operation":"trigger", ...}` and returns `{"triggered": true}`
- `{"operation":"generate", ...}` and returns `{"text":"..."}`

The runner is responsible for loading the temporary candidate metadata into its harness and observing actual skill use. An optional Claude Code adapter is included:

```bash
python -m scripts.run_loop \
  --eval-set <trigger-evals.json> \
  --skill-path <skill-directory> \
  --runner "python scripts/adapters/claude_code.py" \
  --model <model-id> \
  --max-iterations 5 \
  --verbose
```

This adapter requires the `claude` CLI and is only one supported adapter; it is not the portable default. For Pi, Codex, Hermes, or another harness, use an adapter backed by that harness's documented noninteractive and skill-observation interfaces. If no such interface exists, test activation manually and edit the description from observed false positives and false negatives.

Use held-out queries to choose the best description rather than optimizing only the training set. Show the before/after text and scores to the user.

## Validate and package

Run validation and Python checks before distribution:

```bash
python scripts/quick_validate.py <skill-directory>
python -m compileall -q <skill-directory>/scripts <skill-directory>/eval-viewer
python -m scripts.package_skill <skill-directory> <output-directory>
```

The package command creates `<skill-name>.skill`, a ZIP archive. If the harness has an artifact presentation tool, use it; otherwise report the exact path or attach the file through whatever file-transfer capability is available.

Before publishing or sharing, inspect the archive. Exclude credentials, local paths, caches, evaluation outputs, and unrelated repository metadata.

## Bundled references

- `references/schemas.md` — evaluation, grading, timing, and benchmark formats
- `agents/grader.md` — assertion grading guidance
- `agents/analyzer.md` — benchmark analysis guidance
- `agents/comparator.md` — optional blind comparison guidance
