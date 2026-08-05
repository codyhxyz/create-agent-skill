#!/usr/bin/env python3
"""Evaluate whether a skill description triggers through a configured runner.

Modified from Anthropic's skill-creator for agent-agnostic use; see NOTICE.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from scripts.runner import resolve_runner, trigger_runner
from scripts.utils import parse_skill_md


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str,
    runner_command: str,
    model: str | None = None,
) -> bool:
    """Run one query and return the adapter's observed trigger decision."""
    return trigger_runner(
        runner_command,
        {
            "query": query,
            "skill_name": skill_name,
            "skill_description": skill_description,
            "model": model,
            "project_root": project_root,
            "timeout": timeout,
        },
        timeout + 5,
    )


def run_eval(
    eval_set: list[dict[str, Any]],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    project_root: Path,
    runner_command: str,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
) -> dict[str, Any]:
    """Run the full eval set and return results in input order."""
    if runs_per_query < 1:
        raise ValueError("runs_per_query must be at least 1")
    if not 0 <= trigger_threshold <= 1:
        raise ValueError("trigger_threshold must be between 0 and 1")

    triggers_by_index: list[list[bool]] = [[] for _ in eval_set]
    errors_by_index = [0 for _ in eval_set]
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {}
        for item_index, item in enumerate(eval_set):
            if not isinstance(item.get("query"), str) or not isinstance(
                item.get("should_trigger"), bool
            ):
                raise ValueError(
                    "Each eval item requires string 'query' and boolean 'should_trigger'"
                )
            for _ in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    str(project_root),
                    runner_command,
                    model,
                )
                futures[future] = item_index

        for future in as_completed(futures):
            item_index = futures[future]
            try:
                triggers_by_index[item_index].append(future.result())
            except Exception as exc:
                print(f"Warning: query failed: {exc}", file=sys.stderr)
                triggers_by_index[item_index].append(False)
                errors_by_index[item_index] += 1

    results = []
    for item, triggers, error_count in zip(
        eval_set, triggers_by_index, errors_by_index
    ):
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        passed = error_count == 0 and (
            trigger_rate >= trigger_threshold
            if should_trigger
            else trigger_rate < trigger_threshold
        )
        results.append(
            {
                "query": item["query"],
                "should_trigger": should_trigger,
                "trigger_rate": trigger_rate,
                "triggers": sum(triggers),
                "runs": len(triggers),
                "errors": error_count,
                "pass": passed,
            }
        )

    passed_count = sum(1 for result in results if result["pass"])
    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run trigger evaluation through an Agent Skill runner adapter"
    )
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", help="Override description to test")
    parser.add_argument(
        "--runner",
        help="Runner command (default: AGENT_SKILL_RUNNER environment variable)",
    )
    parser.add_argument("--num-workers", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=30, help="Seconds per query")
    parser.add_argument("--runs-per-query", type=int, default=3)
    parser.add_argument("--trigger-threshold", type=float, default=0.5)
    parser.add_argument("--model", help="Optional model identifier passed to the runner")
    parser.add_argument("--project-root", default=".", help="Harness project root")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    eval_set = json.loads(Path(args.eval_set).read_text())
    if not isinstance(eval_set, list):
        raise ValueError("Eval set must be a JSON array")
    skill_path = Path(args.skill_path)
    if not (skill_path / "SKILL.md").exists():
        parser.error(f"No SKILL.md found at {skill_path}")

    name, original_description, _ = parse_skill_md(skill_path)
    description = args.description or original_description
    runner_command = resolve_runner(args.runner)
    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        project_root=Path(args.project_root).resolve(),
        runner_command=runner_command,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
    )

    if args.verbose:
        summary = output["summary"]
        print(f"Results: {summary['passed']}/{summary['total']} passed", file=sys.stderr)
        for result in output["results"]:
            status = "PASS" if result["pass"] else "FAIL"
            print(
                f"  [{status}] rate={result['triggers']}/{result['runs']} "
                f"expected={result['should_trigger']}: {result['query'][:70]}",
                file=sys.stderr,
            )
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
