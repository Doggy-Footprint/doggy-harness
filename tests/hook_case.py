import json
import os
import subprocess
import sys
import tempfile

from test_installer import InstallerTestCase, run_git

SESSION_ENV = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID")


def out(result):
    return result.stdout + result.stderr


class HookCase(InstallerTestCase):
    def new_repo(self):
        repo = self.installed_copy("--no-ci")[0]
        (repo / "src").mkdir(exist_ok=True)
        (repo / "src" / "a.py").write_text("a = 1\n")
        run_git(repo, "add", "-A")
        self.commit(repo, "base")
        return repo

    def commit(self, repo, message):
        run_git(repo, "commit", "-q", "--no-verify", "--allow-empty", "-m", message)
        return self.head(repo)

    def commit_with_hooks(self, repo, message="work"):
        return subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", message],
                              capture_output=True, text=True, env=self.env())

    def head(self, repo):
        return run_git(repo, "rev-parse", "HEAD").stdout.strip()

    def branch(self, repo):
        return run_git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items() if k not in SESSION_ENV}
        env.update(extra)
        return env

    def sessions_dir(self, repo):
        return repo / ".harness" / "sessions"

    def empty_path_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name

    def run_script(self, repo, script, payload=None, raw=None, env=None, cwd=None):
        text = raw if raw is not None else json.dumps(payload)
        return subprocess.run(
            [sys.executable, str(repo / ".harness" / "hooks" / script)],
            input=text, capture_output=True, text=True, cwd=cwd or repo,
            env=env if env is not None else self.env(),
        )
