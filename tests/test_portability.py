import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.aggregate_benchmark import generate_benchmark
from scripts.improve_description import improve_description
from scripts.quick_validate import validate_skill
from scripts.run_eval import run_eval
from scripts.runner import generate_runner, trigger_runner


FAKE_RUNNER = """\
import json, sys
request = json.load(sys.stdin)
if request["operation"] == "trigger":
    if "adapter-error" in request["query"]:
        print("simulated failure", file=sys.stderr)
        raise SystemExit(1)
    response = {"triggered": "activate" in request["query"]}
elif request["operation"] == "generate":
    response = {"text": "<new_description>portable result</new_description>"}
else:
    raise SystemExit(2)
json.dump(response, sys.stdout)
"""


class RunnerProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        runner_path = Path(self.temp_dir.name) / "fake runner.py"
        runner_path.write_text(FAKE_RUNNER)
        self.command = shlex.join([sys.executable, str(runner_path)])

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_trigger_and_generate_protocol(self):
        self.assertTrue(
            trigger_runner(self.command, {"query": "please activate"}, timeout=5)
        )
        self.assertFalse(
            trigger_runner(self.command, {"query": "ordinary task"}, timeout=5)
        )
        self.assertIn(
            "portable result",
            generate_runner(self.command, "prompt", model=None, timeout=5),
        )

    def test_description_improvement_uses_generate_protocol(self):
        description = improve_description(
            skill_name="test-skill",
            skill_content="# Test",
            current_description="Old description",
            eval_results={"results": [], "summary": {"passed": 1, "total": 1}},
            history=[],
            model=None,
            runner_command=self.command,
        )
        self.assertEqual(description, "portable result")

    def test_eval_preserves_duplicate_queries(self):
        result = run_eval(
            eval_set=[
                {"query": "activate this", "should_trigger": True},
                {"query": "activate this", "should_trigger": False},
            ],
            skill_name="test-skill",
            description="Test description",
            num_workers=2,
            timeout=5,
            project_root=Path(self.temp_dir.name),
            runner_command=self.command,
            runs_per_query=2,
        )
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["results"][0]["triggers"], 2)
        self.assertEqual(result["results"][1]["triggers"], 2)
        self.assertTrue(result["results"][0]["pass"])
        self.assertFalse(result["results"][1]["pass"])

    def test_adapter_error_never_counts_as_negative_pass(self):
        result = run_eval(
            eval_set=[{"query": "adapter-error", "should_trigger": False}],
            skill_name="test-skill",
            description="Test description",
            num_workers=1,
            timeout=5,
            project_root=Path(self.temp_dir.name),
            runner_command=self.command,
            runs_per_query=1,
        )
        self.assertEqual(result["results"][0]["errors"], 1)
        self.assertFalse(result["results"][0]["pass"])


class BenchmarkTests(unittest.TestCase):
    def test_reports_actual_runs_per_configuration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run = Path(temp_dir) / "eval-1" / "with_skill" / "run-1"
            run.mkdir(parents=True)
            (run / "grading.json").write_text(
                json.dumps(
                    {
                        "summary": {"pass_rate": 1, "passed": 1, "failed": 0, "total": 1},
                        "expectations": [],
                    }
                )
            )

            benchmark = generate_benchmark(Path(temp_dir))

            self.assertEqual(benchmark["metadata"]["runs_per_configuration"], 1)


class FrontmatterValidationTests(unittest.TestCase):
    def test_valid_standard_frontmatter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill = Path(temp_dir) / "sample-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: sample-skill\n"
                "description: Use this skill for a sample task.\n"
                "license: Apache-2.0\n"
                "compatibility: Python 3 for scripts.\n"
                "metadata:\n  author: test\n"
                "---\n\n# Sample\n"
            )
            self.assertEqual(validate_skill(skill), (True, "Skill is valid!"))

    def test_name_must_match_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill = Path(temp_dir) / "sample-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: another-skill\ndescription: A description.\n---\n"
            )
            valid, message = validate_skill(skill)
            self.assertFalse(valid)
            self.assertIn("must match", message)


if __name__ == "__main__":
    unittest.main()
