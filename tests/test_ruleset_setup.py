import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "installer" / "harness.py"
PAYLOAD = REPO_ROOT / "harness" / "ci" / "harness-ruleset.json"
WORKFLOWS = [REPO_ROOT / "harness" / "ci" / name for name in ("harness-comment-warning.yml", "harness-facts-approval.yml")]
MANUAL = "gh api -X POST repos/{owner}/{repo}/rulesets --input .harness/ci/harness-ruleset.json"
_TARGETS_DIR = tempfile.TemporaryDirectory()
os.environ["HARNESS_TARGETS_FILE"] = str(Path(_TARGETS_DIR.name) / "targets.json")

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
payload = sys.stdin.read() if "--input" in args else ""
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps({"args": args, "payload": payload}) + "\n")
if args[:1] != ["api"]:
    sys.exit(0)
if "-X" in args:
    if os.environ.get("FAKE_APPLY_ERR"):
        print(os.environ["FAKE_APPLY_ERR"], file=sys.stderr)
    sys.exit(int(os.environ.get("FAKE_APPLY_EXIT", "0")))
path = args[-1]
if path.endswith("/rulesets"):
    if os.environ.get("FAKE_LIST_EXIT", "0") != "0":
        print("HTTP 403: Resource not accessible", file=sys.stderr)
        sys.exit(1)
    print(os.environ.get("FAKE_LIST", "[]"))
elif "/rulesets/" in path:
    print(os.environ["FAKE_DETAIL"])
sys.exit(0)
'''


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True)


class RulesetCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.bindir = root / "bin"
        self.bindir.mkdir()
        gh = self.bindir / "gh"
        gh.write_text(FAKE_GH.replace("/usr/bin/env python3", sys.executable, 1))
        gh.chmod(0o755)
        self.log = root / "gh.log"
        self.root = root
        self.fresh_repo()
        self.payload = json.loads(PAYLOAD.read_text())

    def fresh_repo(self):
        self.repo = Path(tempfile.mkdtemp(dir=self.root))
        git(self.repo, "init", "-q")
        git(self.repo, "remote", "add", "origin", "https://github.com/example/project.git")
        self.log.unlink(missing_ok=True)

    def install(self, *flags, input="", command="install", path=None, **fake_env):
        env = dict(os.environ, FAKE_GH_LOG=str(self.log), **fake_env)
        env["PATH"] = path if path is not None else f"{self.bindir}{os.pathsep}{os.environ['PATH']}"
        result = subprocess.run([sys.executable, str(INSTALLER), command, str(self.repo), *flags],
                                env=env, input=input, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def calls(self):
        lines = self.log.read_text().splitlines() if self.log.exists() else []
        return [json.loads(line) for line in lines]

    def ruleset_calls(self):
        return [call for call in self.calls() if any("rulesets" in arg for arg in call["args"])]

    def writes(self):
        return [call for call in self.ruleset_calls() if "-X" in call["args"]]

    def section(self, stdout, name):
        if f"== {name} ==\n" not in stdout:
            return ""
        return stdout.split(f"== {name} ==\n", 1)[1].split("\n== ", 1)[0]

    def existing(self, **changes):
        detail = {"id": 7, **json.loads(json.dumps(self.payload)), **changes}
        listing = [{"id": 3, "name": "other"}, {"id": 9, "name": "harness-old"}, {"id": 5, "name": "Harness"},
                   {"id": 7, "name": "harness"}]
        return {"FAKE_LIST": json.dumps(listing), "FAKE_DETAIL": json.dumps(detail)}

    def drifted(self):
        weaker = json.loads(json.dumps(self.payload))
        weaker["rules"][0]["parameters"]["required_status_checks"] = [{"context": "require-comment-approval"}]
        only_facts = json.loads(json.dumps(self.payload))
        only_facts["rules"][0]["parameters"]["required_status_checks"] = [{"context": "require-facts-approval"}]
        return {
            "bypass": {"bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]},
            "disabled": {"enforcement": "evaluate"},
            "tag target": {"target": "tag"},
            "other branch": {"conditions": {"ref_name": {"include": ["refs/heads/dev"], "exclude": []}}},
            "extra include": {"conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH", "refs/heads/dev"], "exclude": []}}},
            "all branches": {"conditions": {"ref_name": {"include": ["~ALL"], "exclude": []}}},
            "default excluded": {"conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": ["~DEFAULT_BRANCH"]}}},
            "missing facts check": {"rules": weaker["rules"]},
            "missing comment check": {"rules": only_facts["rules"]},
            "no rules": {"rules": []},
        }


class PayloadTests(unittest.TestCase):
    def test_payload_requires_every_harness_job_on_the_default_branch_without_bypass(self):
        payload = json.loads(PAYLOAD.read_text())
        self.assertEqual((payload["name"], payload["target"], payload["enforcement"]), ("harness", "branch", "active"))
        self.assertEqual(payload["bypass_actors"], [])
        self.assertEqual(payload["conditions"]["ref_name"], {"include": ["~DEFAULT_BRANCH"], "exclude": []})
        (rule,) = payload["rules"]
        self.assertEqual(rule["type"], "required_status_checks")
        contexts = sorted(check["context"] for check in rule["parameters"]["required_status_checks"])
        jobs = sorted(job for path in WORKFLOWS
                      for job in re.findall(r"^  ([\w-]+):\s*$", path.read_text().split("\njobs:\n", 1)[1], re.MULTILINE))
        self.assertEqual(contexts, jobs)


class SetupTests(RulesetCase):
    def test_missing_ruleset_is_created_after_yes_with_the_shipped_payload(self):
        result = self.install(input="y\n")
        (write,) = self.writes()
        self.assertEqual(write["args"][:4], ["api", "-X", "POST", "repos/{owner}/{repo}/rulesets"])
        self.assertEqual(json.loads(write["payload"]), self.payload)
        self.assertIn("no bypass", result.stdout)
        self.assertIn("GitHub ruleset harness (created)", self.section(result.stdout, "write"))

    def test_no_answer_or_no_creates_nothing_and_lists_the_command(self):
        for answer in ("", "n\n", "never\n"):
            with self.subTest(answer=answer):
                self.fresh_repo()
                result = self.install(input=answer)
                self.assertEqual(self.writes(), [])
                self.assertIn(MANUAL, self.section(result.stdout, "manual review"))

    def test_matching_ruleset_is_left_alone_without_asking(self):
        result = self.install(input="", **self.existing())
        self.assertEqual(self.writes(), [])
        self.assertNotIn("[y/N]", result.stdout)
        self.assertIn("GitHub ruleset harness already requires", self.section(result.stdout, "skip"))
        self.assertIn(["api", "repos/{owner}/{repo}/rulesets/7"], [call["args"] for call in self.calls()])

    def test_ruleset_with_extra_checks_still_matches(self):
        detail = json.loads(json.dumps(self.payload))
        detail["rules"][0]["parameters"]["required_status_checks"].append({"context": "build"})
        result = self.install(input="", **self.existing(rules=detail["rules"]))
        self.assertEqual(self.writes(), [])
        self.assertNotIn("[y/N]", result.stdout)
        self.assertIn("GitHub ruleset harness already requires", self.section(result.stdout, "skip"))

    def test_drifted_ruleset_is_updated_in_place_after_yes(self):
        for name, changes in self.drifted().items():
            with self.subTest(case=name):
                self.fresh_repo()
                result = self.install(input="y\n", **self.existing(**changes))
                (write,) = self.writes()
                self.assertEqual(write["args"], ["api", "-X", "PUT", "repos/{owner}/{repo}/rulesets/7", "--input", "-"])
                self.assertEqual(json.loads(write["payload"]), self.payload)
                self.assertIn(["api", "repos/{owner}/{repo}/rulesets/7"], [call["args"] for call in self.calls()])
                self.assertIn("Update the GitHub ruleset", result.stdout)
                self.assertIn("GitHub ruleset harness (updated)", self.section(result.stdout, "write"))

    def test_drifted_ruleset_is_not_written_without_yes(self):
        for answer in ("", "n\n"):
            with self.subTest(answer=answer):
                self.fresh_repo()
                result = self.install(input=answer, **self.existing(enforcement="disabled"))
                self.assertIn("Update the GitHub ruleset", result.stdout)
                self.assertEqual(self.writes(), [])
                self.assertIn(MANUAL, self.section(result.stdout, "manual review"))

    def test_only_an_exact_harness_name_counts_as_existing(self):
        listing = [{"id": 3, "name": "other"}, {"id": 9, "name": "harness-old"}, {"id": 5, "name": "Harness"}]
        self.install(input="y\n", FAKE_LIST=json.dumps(listing), FAKE_DETAIL="{}")
        (write,) = self.writes()
        self.assertEqual(write["args"], ["api", "-X", "POST", "repos/{owner}/{repo}/rulesets", "--input", "-"])
        self.assertFalse(any("/rulesets/" in arg for call in self.calls() for arg in call["args"]))

    def test_only_y_or_yes_in_any_case_confirms(self):
        for answer, confirmed in (("yes\n", True), ("Y\n", True), ("YES\n", True), (" y \n", True),
                                  ("yeah\n", False), ("ye\n", False), (" \n", False)):
            with self.subTest(answer=answer):
                self.fresh_repo()
                self.install(input=answer)
                self.assertEqual(len(self.writes()), 1 if confirmed else 0)

    def test_update_sets_up_the_ruleset_and_respects_no_ci_and_dry_run(self):
        self.install("--no-ci")
        self.assertEqual(self.ruleset_calls(), [])
        for flags, writes in ((("--no-ci",), None), (("--dry-run",), None), ((), 1)):
            with self.subTest(flags=flags):
                self.log.unlink(missing_ok=True)
                result = self.install(*flags, "--no-commit", command="update", input="y\n")
                if writes is None:
                    self.assertEqual(self.ruleset_calls(), [])
                else:
                    (write,) = self.writes()
                    self.assertEqual(json.loads(write["payload"]), self.payload)
                    order = [call["args"][1] for call in self.calls() if call["args"][:1] == ["api"]]
                    self.assertEqual(order[-1:], ["-X"])
                    self.assertTrue(any("labels/facts-approved" in arg for arg in order[:-2]), order)
                    self.assertIn("GitHub ruleset harness (created)", self.section(result.stdout, "write"))

    def test_installed_payload_matches_the_shipped_one(self):
        self.install()
        self.assertEqual((self.repo / ".harness" / "ci" / "harness-ruleset.json").read_bytes(), PAYLOAD.read_bytes())

    def test_unreadable_rulesets_are_reported_without_asking(self):
        result = self.install(input="y\n", FAKE_LIST_EXIT="1")
        self.assertEqual(self.writes(), [])
        manual = self.section(result.stdout, "manual review")
        self.assertIn("could not read GitHub rulesets (HTTP 403", manual)
        self.assertIn(MANUAL, manual)

    def test_malformed_listing_is_reported_not_raised(self):
        result = self.install(input="y\n", FAKE_LIST="not json")
        self.assertEqual(self.writes(), [])
        self.assertIn(MANUAL, self.section(result.stdout, "manual review"))

    def test_rejected_write_is_reported_with_its_reason(self):
        result = self.install(input="y\n", FAKE_APPLY_EXIT="1", FAKE_APPLY_ERR="HTTP 403: Upgrade to GitHub Pro")
        manual = self.section(result.stdout, "manual review")
        self.assertIn("gh ruleset create failed (HTTP 403: Upgrade to GitHub Pro)", manual)
        self.assertIn(MANUAL, manual)
        self.assertNotIn("GitHub ruleset harness", self.section(result.stdout, "write"))
        self.fresh_repo()
        result = self.install(input="y\n", FAKE_APPLY_EXIT="1", FAKE_APPLY_ERR="HTTP 422: Validation Failed",
                              **self.existing(enforcement="disabled"))
        manual = self.section(result.stdout, "manual review")
        self.assertIn("gh ruleset update failed (HTTP 422: Validation Failed)", manual)
        self.assertIn(MANUAL, manual)
        self.assertNotIn("GitHub ruleset harness", self.section(result.stdout, "write"))

    def test_unreadable_or_malformed_detail_is_reported_without_writing(self):
        for detail in ("not json", "[]"):
            with self.subTest(detail=detail):
                self.fresh_repo()
                env = self.existing()
                env["FAKE_DETAIL"] = detail
                result = self.install(input="y\n", **env)
                self.assertEqual(self.writes(), [])
                self.assertIn(MANUAL, self.section(result.stdout, "manual review"))

    def test_without_gh_the_command_is_listed(self):
        bindir = Path(tempfile.mkdtemp(dir=self.root))
        for tool in ("git",):
            os.symlink(shutil.which(tool), bindir / tool)
        result = self.install(input="y\n", path=str(bindir))
        self.assertEqual(self.calls(), [])
        self.assertIn(f"gh CLI not found; create the `harness` ruleset", result.stdout)

    def test_no_ci_and_dry_run_call_no_ruleset_api(self):
        result = self.install("--no-ci", input="y\n")
        self.assertEqual(self.ruleset_calls(), [])
        self.assertNotIn("GitHub ruleset", result.stdout)
        self.fresh_repo()
        result = self.install("--dry-run", input="y\n")
        self.assertEqual(self.ruleset_calls(), [])
        self.assertIn("GitHub ruleset harness (asks first", self.section(result.stdout, "write"))

    def test_without_a_remote_the_command_is_listed(self):
        git(self.repo, "remote", "remove", "origin")
        result = self.install(input="y\n")
        self.assertEqual(self.ruleset_calls(), [])
        self.assertIn(f"no git remote configured; create the `harness` ruleset", result.stdout)


if __name__ == "__main__":
    unittest.main()
