import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from hook_case import SESSION_ENV, HookCase
from test_installer import run_git

MANAGERS = ("uv", "poetry", "pdm", "pnpm", "yarn", "bun", "npm")
UV = "uv sync --frozen --inexact"
POETRY = "poetry install --no-interaction"
PDM = "pdm install --frozen-lockfile"
PNPM = "pnpm install --frozen-lockfile"
YARN = "yarn install --frozen-lockfile"
BUN = "bun install --frozen-lockfile"
NPM = "npm ci"
PY_TOOLS = ("hypothesis", "mutmut")
JS_TOOLS = ("fast-check", "@stryker-mutator/core")
STATE_REL = Path(".harness") / "sessions" / "checkout-setup"
LOG_REL = ".harness/sessions/checkout-setup/install.log"
HEADER = "harness: "
TAIL = ("Verification tools are not runnable in this checkout until it finishes; "
        "check with: python3 .harness/bin/checkout_setup.py status")
M_HOOKS = "harness: set git core.hooksPath=.harness/git in this clone"
HOOK_PAYLOAD = {"hook_event_name": "SessionStart"}

PY_CREATE = {
    "dirs": [".venv/lib/python3.12/site-packages/hypothesis", ".venv/lib/python3.12/site-packages/mutmut"],
    "files": {".venv/.gitignore": "*\n"},
}
JS_CREATE = {
    "files": {
        "node_modules/fast-check/package.json": "{}\n",
        "node_modules/@stryker-mutator/core/package.json": "{}\n",
    },
}


def m_start(commands):
    return f"harness: installing project dependencies in the background: {' && '.join(commands)}. {TAIL}"


def m_retry(reason, commands):
    return (f"harness: the last dependency install failed ({reason}); retrying in the background: "
            f"{' && '.join(commands)}. {TAIL}")


def m_running_pattern(commands):
    return re.compile(re.escape(f"harness: a dependency install is running in this checkout "
                                f"({' && '.join(commands)}, started ") + r"(\d+)" + re.escape(f"s ago). {TAIL}"))


def m_failed(language, reason, command):
    return (f"harness: the last dependency install failed ({language}: {reason}); verification tools are not "
            f"runnable. Run manually: {command}; log: {LOG_REL}")


def m_nomanager(executable, command):
    return (f"harness: verification tools are declared but not installed ({executable} not found on PATH); "
            f"run manually: {command}")


def m_manual(command):
    return (f'harness: verification tools are declared but not present in node_modules; "{command}" would '
            f"delete and reinstall node_modules, so it is not run automatically. Run manually: {command}")


def s_runnable(language, tools):
    return f"{language}: runnable ({', '.join(tools)})"


def s_off(language):
    return f"{language}: not installed (automatic install is off)"


def s_nolock(language):
    return f"{language}: not installed (no lockfile)"


def s_settled(language, command):
    return f'{language}: installed by "{command}"; not found in the checkout'


def s_nomanager(language, executable, command):
    return f"{language}: not installed ({executable} not found on PATH); run manually: {command}"


def s_failed(language, reason, command):
    return f"{language}: install failed ({reason}); run manually: {command}; log: {LOG_REL}"


def s_manual(language, command):
    return f'{language}: not installed ("{command}" would delete and reinstall node_modules); run manually: {command}'


def s_pending(language):
    return f"{language}: not installed (install not started)"


def s_running_pattern(language):
    return re.compile(re.escape(f"{language}: install running (started ") + r"(\d+)" + re.escape("s ago)"))


S_NONE = "no verification tools declared in this checkout"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pyproject_text(kind):
    names = {"both": PY_TOOLS, "mutmut": ("mutmut",), "hypothesis": ("hypothesis",), "none": ("pytest",)}[kind]
    deps = ", ".join(f'"{name}>=1"' for name in names)
    return f'[project]\nname = "demo"\nversion = "0"\n\n[dependency-groups]\ndev = [{deps}]\n'


def package_json_text(kind):
    names = JS_TOOLS if kind == "both" else ("left-pad",)
    return json.dumps({"name": "demo", "devDependencies": {name: "^1.0.0" for name in names}}) + "\n"


def call(command, repo):
    name, _, args = command.partition(" ")
    return (name, str(Path(repo).resolve()), args)


class CheckoutCase(HookCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.box = Path(tmp.name).resolve()
        self.stand = self.box / "standins"
        self.stand.mkdir()
        self.record = self.box / "record.tsv"
        self.record.write_text("")
        self.prefs = self.box / "preferences.json"
        self.home = self.box / "home"
        self.home.mkdir()
        (self.home / "gitconfig").write_text("")
        self.search_path = self.build_path()
        self.repos = []
        self.manual_locks = set()
        self.addCleanup(self.drain)

    def build_path(self):
        keep = "/usr/bin:/bin"
        if shutil.which("git", path=keep) is None:
            real = shutil.which("git")
            self.assertIsNotNone(real, "git is required")
            system = self.box / "system"
            system.mkdir()
            (system / "git").symlink_to(real)
            keep = f"{system}:{keep}"
        for name in MANAGERS:
            self.assertIsNone(shutil.which(name, path=keep), f"a real {name} is reachable on {keep}")
        return f"{self.stand}:{keep}"

    def sandbox_env(self, **extra):
        env = {k: v for k, v in os.environ.items()
               if k not in SESSION_ENV and not k.startswith("HARNESS_CHECKOUT")}
        env.update({
            "PATH": self.search_path,
            "HOME": str(self.home),
            "HARNESS_PREFERENCES_FILE": str(self.prefs),
            "HARNESS_TARGETS_FILE": str(self.box / "targets.json"),
            "HARNESS_TELEMETRY_DIR": str(self.box / "telemetry"),
            "GIT_CONFIG_GLOBAL": str(self.home / "gitconfig"),
            "GIT_CONFIG_NOSYSTEM": "1",
        })
        env.update(extra)
        return env

    def standin(self, name, dirs=(), files=None, sleep=0, code=0, stdout="", stderr="", exec_sleep=False,
                pidfile=None, stdin_record=None):
        quote = shlex.quote
        lines = ["#!/bin/sh",
                 f'printf "%s\\t%s\\t%s\\n" "$(basename "$0")" "$(pwd -P)" "$*" >> {quote(str(self.record))}']
        if pidfile:
            lines.append(f"echo $$ > {quote(str(pidfile))}")
        if stdin_record:
            lines.append(f"if read -r _line; then echo data > {quote(str(stdin_record))}; "
                         f"else echo eof > {quote(str(stdin_record))}; fi")
        if exec_sleep:
            lines.append(f"exec sleep {sleep}")
        elif sleep:
            lines.append(f"sleep {sleep}")
        for directory in dirs:
            lines.append(f"mkdir -p {quote(directory)}")
        for path, content in (files or {}).items():
            lines.append(f"mkdir -p {quote(os.path.dirname(path) or '.')}")
            lines.append(f"printf '%s' {quote(content)} > {quote(path)}")
        if stdout:
            lines.append(f"printf '%s\\n' {quote(stdout)}")
        if stderr:
            lines.append(f"printf '%s\\n' {quote(stderr)} >&2")
        lines.append(f"exit {code}")
        path = self.stand / name
        path.write_text("\n".join(lines) + "\n")
        path.chmod(0o755)

    def remove_standin(self, name):
        (self.stand / name).unlink()

    def calls(self):
        rows = [line.split("\t") for line in self.record.read_text().splitlines() if line]
        return [tuple(row) for row in rows]

    def settle(self, seconds=0.8):
        time.sleep(seconds)

    def checkout(self, python=None, js=None, locks=()):
        repo = self.new_repo()
        run_git(repo, "config", "core.hooksPath", ".harness/git")
        pre_commit = repo / ".harness" / "git" / "pre-commit"
        if not pre_commit.is_file():
            pre_commit.parent.mkdir(parents=True, exist_ok=True)
            pre_commit.write_text("#!/bin/sh\nexit 0\n")
        (repo / ".harness" / "config.json").unlink(missing_ok=True)
        if python is not None:
            (repo / "pyproject.toml").write_text(pyproject_text(python))
        if js is not None:
            (repo / "package.json").write_text(package_json_text(js))
        for name in locks:
            (repo / name).write_text(f"{name} v1\n")
        run_git(repo, "add", "-A")
        self.commit(repo, "fixture")
        self.repos.append(repo)
        return repo

    def add_worktree(self, repo, name="wt"):
        path = self.box / name
        run_git(repo, "worktree", "add", "-q", "-b", name, str(path))
        manifest = path / ".harness" / "manifest.json"
        if not manifest.is_file():
            manifest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(repo / ".harness" / "manifest.json", manifest)
        for sub in ("bin", "lib"):
            if not (path / ".harness" / sub).is_dir() and (repo / ".harness" / sub).is_dir():
                shutil.copytree(repo / ".harness" / sub, path / ".harness" / sub)
        self.repos.append(path)
        return path

    def script(self, repo, name="checkout_setup.py"):
        return str(Path(repo) / ".harness" / "bin" / name)

    def session_start(self, repo, payload=None, raw=None, cwd=None, script_repo=None, env=None, timeout=90):
        if raw is None:
            raw = json.dumps(payload if payload is not None else {**HOOK_PAYLOAD, "cwd": str(repo)})
        return subprocess.run([sys.executable, self.script(script_repo or repo), "hook"], input=raw,
                              capture_output=True, text=True, cwd=cwd or repo,
                              env=env or self.sandbox_env(), timeout=timeout)

    def status(self, repo, *args, env=None, cwd=None):
        return subprocess.run([sys.executable, self.script(repo), "status", *args], input="",
                              capture_output=True, text=True, cwd=cwd or repo,
                              env=env or self.sandbox_env(), timeout=120)

    def phase(self, repo, *args, env=None):
        return subprocess.run([sys.executable, self.script(repo, "workflow_marker.py"), "phase", *args],
                              input="", capture_output=True, text=True, cwd=repo,
                              env=env or self.sandbox_env(), timeout=120)

    def worker(self, repo, *args, env=None):
        return subprocess.run([sys.executable, self.script(repo), "run", "--checkout", str(repo), *args],
                              input="", capture_output=True, text=True, cwd=repo,
                              env=env or self.sandbox_env(), timeout=120)

    def lines(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        return result.stdout.splitlines()

    def state_dir(self, repo):
        return Path(repo) / STATE_REL

    def read_state(self, repo):
        try:
            return json.loads((self.state_dir(repo) / "state.json").read_text())
        except (OSError, ValueError):
            return None

    def entry(self, repo, language):
        return self.read_state(repo)["languages"][language]

    def write_state(self, repo, languages):
        self.state_dir(repo).mkdir(parents=True, exist_ok=True)
        (self.state_dir(repo) / "state.json").write_text(json.dumps({"languages": languages}))

    def ok_entry(self, repo, lockfile, command, verified):
        return {"result": "ok", "verified": verified, "lock_sha": sha(Path(repo) / lockfile),
                "command": command, "finished": int(time.time())}

    def failed_entry(self, repo, lockfile, command, reason):
        return {"result": "failed", "reason": reason, "lock_sha": sha(Path(repo) / lockfile),
                "command": command, "finished": int(time.time())}

    def write_lock(self, repo, pid, started, commands):
        self.state_dir(repo).mkdir(parents=True, exist_ok=True)
        (self.state_dir(repo) / "lock").write_text(json.dumps({"pid": pid, "started": started, "commands": commands}))
        self.manual_locks.add(Path(repo))

    def wait_until(self, predicate, timeout=40.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.05)
        return False

    def wait_done(self, repo, *languages, check=None, timeout=40.0):
        def done():
            if (self.state_dir(repo) / "lock").exists():
                return False
            state = self.read_state(repo)
            if not isinstance(state, dict):
                return False
            entries = state.get("languages", {})
            if not all(language in entries for language in languages):
                return False
            return check(entries) if check else True
        self.assertTrue(self.wait_until(done, timeout), f"worker did not finish: {self.read_state(repo)}")

    def wait_lock(self, repo, timeout=15.0):
        self.assertTrue(self.wait_until(lambda: (self.state_dir(repo) / "lock").exists(), timeout),
                        "the worker never took the lock")

    def drain(self):
        pending = [r for r in self.repos if Path(r) not in self.manual_locks]
        self.wait_until(lambda: all(not (self.state_dir(r) / "lock").exists() for r in pending), 25.0)

    def timed(self, function):
        started = time.monotonic()
        result = function()
        return result, time.monotonic() - started

    def hooks_path(self, repo):
        result = subprocess.run(["git", "-C", str(repo), "config", "--get", "core.hooksPath"],
                                capture_output=True, text=True)
        return result.stdout.strip()

    def snapshot(self, repo):
        return {k: v for k, v in super().snapshot(repo).items() if "__pycache__" not in Path(k).parts}

    def tracked_snapshot(self, repo):
        skipped = (".venv/", "node_modules/", ".harness/sessions/checkout-setup/")
        return {k: v for k, v in self.snapshot(repo).items() if not k.startswith(skipped)}

    def expect_running(self, line, commands, low=0, high=120):
        match = m_running_pattern(commands).fullmatch(line)
        self.assertIsNotNone(match, line)
        self.assertTrue(low <= int(match.group(1)) <= high, line)
