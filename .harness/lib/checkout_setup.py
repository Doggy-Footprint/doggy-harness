from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ImportError:
    tomllib = None

TABLE = (
    {
        "language": "python",
        "manifest": "pyproject.toml",
        "tools": ("hypothesis", "mutmut"),
        "lockfiles": (
            (("uv.lock",), ("uv", "sync", "--frozen", "--inexact")),
            (("poetry.lock",), ("poetry", "install", "--no-interaction")),
            (("pdm.lock",), ("pdm", "install", "--frozen-lockfile")),
        ),
    },
    {
        "language": "javascript",
        "manifest": "package.json",
        "tools": ("fast-check", "@stryker-mutator/core"),
        "lockfiles": (
            (("pnpm-lock.yaml",), ("pnpm", "install", "--frozen-lockfile")),
            (("yarn.lock",), ("yarn", "install", "--frozen-lockfile")),
            (("bun.lock", "bun.lockb"), ("bun", "install", "--frozen-lockfile")),
            (("package-lock.json",), ("npm", "ci")),
        ),
    },
)
REPLACES_ENVIRONMENT = (("npm", "ci"),)
JS_DEPENDENCY_TABLES = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")
REQUIREMENT_NAME_RE = re.compile(r"[A-Za-z0-9._-]+")
PREFERENCE_KEY = "verification_tools_prompt"
HOOK_MANAGER_FILES = [
    ".husky/pre-commit",
    "lefthook.yml",
    "lefthook.yaml",
    ".lefthook.yml",
    ".pre-commit-config.yaml",
]
HOOKS_PATH = ".harness/git"
STATE_SUBDIR = Path(".harness") / "sessions" / "checkout-setup"
DEFAULT_TIMEOUT_SECONDS = 1800

M_HOOKS = "harness: set git core.hooksPath=.harness/git in this clone"
_WAIT_TAIL = (
    "Verification tools are not runnable in this checkout until it finishes; "
    "check with: python3 .harness/bin/checkout_setup.py status"
)
M_START = "harness: installing project dependencies in the background: {commands}. " + _WAIT_TAIL
M_RETRY = (
    "harness: the last dependency install failed ({reason}); retrying in the background: {commands}. " + _WAIT_TAIL
)
M_RUNNING = (
    "harness: a dependency install is running in this checkout ({commands}, started {n}s ago). " + _WAIT_TAIL
)
M_FAILED = (
    "harness: the last dependency install failed ({language}: {reason}); verification tools are not runnable. "
    "Run manually: {command}; log: .harness/sessions/checkout-setup/install.log"
)
M_NOMANAGER = (
    "harness: verification tools are declared but not installed ({executable} not found on PATH); "
    "run manually: {command}"
)
M_MANUAL = (
    'harness: verification tools are declared but not present in node_modules; "{command}" would delete and '
    "reinstall node_modules, so it is not run automatically. Run manually: {command}"
)
S_RUNNABLE = "{language}: runnable ({tools})"
S_OFF = "{language}: not installed (automatic install is off)"
S_NOLOCK = "{language}: not installed (no lockfile)"
S_SETTLED = '{language}: installed by "{command}"; not found in the checkout'
S_NOMANAGER = "{language}: not installed ({executable} not found on PATH); run manually: {command}"
S_FAILED = (
    "{language}: install failed ({reason}); run manually: {command}; "
    "log: .harness/sessions/checkout-setup/install.log"
)
S_MANUAL = '{language}: not installed ("{command}" would delete and reinstall node_modules); run manually: {command}'
S_PENDING = "{language}: not installed (install not started)"
S_RUNNING = "{language}: install running (started {n}s ago)"
S_NONE = "no verification tools declared in this checkout"


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def python_names(node, found: set[str]) -> None:
    if isinstance(node, str):
        match = REQUIREMENT_NAME_RE.match(node)
        if match:
            found.add(normalize(match.group()))
    elif isinstance(node, dict):
        for key, value in node.items():
            python_names(key, found)
            python_names(value, found)
    elif isinstance(node, list):
        for value in node:
            python_names(value, found)


def javascript_names(data: dict) -> set[str]:
    names: set[str] = set()
    for table in JS_DEPENDENCY_TABLES:
        if isinstance(data.get(table), dict):
            names.update(data[table])
    return names


def tools_of(language: str) -> tuple[str, ...]:
    return next(row["tools"] for row in TABLE if row["language"] == language)


def lockfile_precedence(language: str):
    return next(row["lockfiles"] for row in TABLE if row["language"] == language)


def preferences_file() -> Path:
    return Path(os.environ.get("HARNESS_PREFERENCES_FILE") or Path.home() / ".harness" / "preferences.json")


def command_text(command) -> str:
    return " ".join(command)


def timeout_seconds() -> int:
    value = os.environ.get("HARNESS_CHECKOUT_SETUP_TIMEOUT", "")
    if re.fullmatch(r"[0-9]+", value) and int(value) > 0:
        return int(value)
    return DEFAULT_TIMEOUT_SECONDS


def state_dir(checkout: Path) -> Path:
    return checkout / STATE_SUBDIR


def is_installed(checkout: Path) -> bool:
    return (checkout / ".harness" / "manifest.json").is_file()


def checkout_of(directory: str) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", directory, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    top = result.stdout.strip()
    if result.returncode != 0 or not top:
        return None
    return Path(top)


def _declared(row: dict, checkout: Path) -> tuple[str, ...]:
    try:
        text = (checkout / row["manifest"]).read_text(encoding="utf-8")
        if row["language"] == "python":
            if tomllib is None:
                return ()
            names: set[str] = set()
            python_names(tomllib.loads(text), names)
        else:
            data = json.loads(text)
            if not isinstance(data, dict):
                return ()
            names = javascript_names(data)
    except Exception:
        return ()
    return tuple(tool for tool in row["tools"] if (normalize(tool) if row["language"] == "python" else tool) in names)


def _present(row: dict, tool: str, checkout: Path) -> bool:
    try:
        if row["language"] == "python":
            venv = checkout / ".venv"
            if any((venv / "lib").glob(f"python*/site-packages/{tool}")):
                return True
            return (venv / "Lib" / "site-packages" / tool).exists()
        return (checkout / "node_modules" / tool / "package.json").is_file()
    except OSError:
        return False


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _main_worktree(checkout: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    out = result.stdout.strip()
    if result.returncode != 0 or not out:
        return None
    return (checkout / out).resolve().parent


def auto_install_off(checkout: Path) -> bool:
    config_path = checkout / ".harness" / "config.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return True
        if not isinstance(data, dict) or data.get("auto_install") is False:
            return True
    try:
        repositories = json.loads(preferences_file().read_text(encoding="utf-8")).get("repositories")
    except Exception:
        return False
    if not isinstance(repositories, dict):
        return False
    paths = [checkout.resolve()]
    main = _main_worktree(checkout)
    if main is not None:
        paths.append(main)
    for path in paths:
        entry = repositories.get(str(path))
        if isinstance(entry, dict) and entry.get(PREFERENCE_KEY) == "never":
            return True
    return False


def _entry_valid(entry) -> bool:
    if not isinstance(entry, dict) or not isinstance(entry.get("lock_sha"), str):
        return False
    if not isinstance(entry.get("command"), str):
        return False
    finished = entry.get("finished")
    if isinstance(finished, bool) or not isinstance(finished, (int, float)):
        return False
    if entry.get("result") == "ok":
        return isinstance(entry.get("verified"), bool)
    return entry.get("result") == "failed" and isinstance(entry.get("reason"), str)


def _raw_state(checkout: Path) -> dict:
    data = _load_json(state_dir(checkout) / "state.json")
    languages = data.get("languages") if isinstance(data, dict) else None
    return languages if isinstance(languages, dict) else {}


def read_state(checkout: Path) -> dict:
    return {name: entry for name, entry in _raw_state(checkout).items() if _entry_valid(entry)}


def _write_json_atomic(path: Path, data) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def record_entry(checkout: Path, language: str, entry: dict) -> None:
    languages = _raw_state(checkout)
    languages[language] = entry
    _write_json_atomic(state_dir(checkout) / "state.json", {"languages": languages})


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, OverflowError, ValueError):
        return False
    return True


def read_lock(checkout: Path) -> dict | None:
    data = _load_json(state_dir(checkout) / "lock")
    if not isinstance(data, dict):
        return None
    pid, started, commands = data.get("pid"), data.get("started"), data.get("commands")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return None
    if isinstance(started, bool) or not isinstance(started, (int, float)):
        return None
    if not isinstance(commands, list) or not all(isinstance(command, str) for command in commands):
        return None
    return data


def live_lock(checkout: Path) -> dict | None:
    lock = read_lock(checkout)
    if lock is None or not _pid_exists(lock["pid"]):
        return None
    if time.time() - lock["started"] > 2 * timeout_seconds():
        return None
    return lock


@dataclass
class Language:
    row: dict
    declared: tuple[str, ...]
    state: str
    command: tuple[str, ...] | None = None
    lock_sha: str | None = None
    entry: dict | None = None

    @property
    def name(self) -> str:
        return self.row["language"]


def language_states(checkout: Path, which=shutil.which) -> list[Language]:
    results = []
    state = read_state(checkout)
    off = None
    for row in TABLE:
        if not (checkout / row["manifest"]).is_file():
            continue
        declared = _declared(row, checkout)
        if not declared:
            results.append(Language(row, declared, "undeclared"))
            continue
        if all(_present(row, tool, checkout) for tool in declared):
            results.append(Language(row, declared, "runnable"))
            continue
        if off is None:
            off = auto_install_off(checkout)
        if off:
            results.append(Language(row, declared, "off"))
            continue
        chosen = next(
            (
                (lockfile, command)
                for lockfiles, command in row["lockfiles"]
                for lockfile in lockfiles
                if (checkout / lockfile).exists()
            ),
            None,
        )
        if chosen is None:
            results.append(Language(row, declared, "no-lockfile"))
            continue
        lockfile, command = chosen
        try:
            sha = hashlib.sha256((checkout / lockfile).read_bytes()).hexdigest()
        except OSError:
            sha = None
        entry = state.get(row["language"])
        current = entry if entry is not None and sha is not None and entry["lock_sha"] == sha else None
        if current is not None and current["result"] == "ok" and not current["verified"]:
            kind = "settled"
        elif which(command[0]) is None:
            kind = "no-manager"
        elif current is not None and current["result"] == "failed":
            kind = "failed"
        elif command in REPLACES_ENVIRONMENT and (checkout / "node_modules").exists():
            kind = "manual"
        else:
            kind = "pending"
        results.append(Language(row, declared, kind, command, sha, current))
    return results


def install_set(languages: list[Language], retry_failed: bool) -> list[Language]:
    return [
        language
        for language in languages
        if language.state == "pending" or (retry_failed and language.state == "failed")
    ]


def _commands_text(languages: list[Language]) -> str:
    return " && ".join(command_text(language.command) for language in languages)


def _running_line(lock: dict) -> str:
    return M_RUNNING.format(commands=" && ".join(lock["commands"]), n=max(0, int(time.time() - lock["started"])))


def _lock_content(pid: int, commands: list[str]) -> dict:
    return {"pid": pid, "started": time.time(), "commands": commands}


def acquire_lock(checkout: Path, pid: int, commands: list[str]) -> bool:
    """Exclusive creation with the content already in place, so a reader never sees a half-written lock."""
    directory = state_dir(checkout)
    path = directory / "lock"
    temporary = directory / f"lock.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(_lock_content(pid, commands)), encoding="utf-8")
    try:
        for _ in range(3):
            try:
                os.link(temporary, path)
                return True
            except FileExistsError:
                if live_lock(checkout) is not None:
                    return False
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
        return False
    finally:
        temporary.unlink(missing_ok=True)


def release_lock(checkout: Path, pid: int) -> None:
    lock = read_lock(checkout)
    if lock is not None and lock["pid"] == pid:
        try:
            (state_dir(checkout) / "lock").unlink()
        except FileNotFoundError:
            pass


def _start_worker(checkout: Path, retry_failed: bool) -> subprocess.Popen:
    script = Path(__file__).resolve().parents[1] / "bin" / "checkout_setup.py"
    arguments = [sys.executable, str(script), "run", "--checkout", str(checkout)]
    if retry_failed:
        arguments.append("--retry-failed")
    with open(state_dir(checkout) / "install.log", "ab") as log:
        return subprocess.Popen(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            close_fds=True,
            start_new_session=True,
            env=os.environ.copy(),
        )


def ensure(checkout: Path, retry_failed: bool, start: bool = True) -> list[str]:
    if not is_installed(checkout):
        return []
    lock = live_lock(checkout)
    if lock is not None:
        return [_running_line(lock)]
    languages = language_states(checkout)
    to_install = install_set(languages, retry_failed) if start else []
    lines = []
    if to_install:
        commands = [command_text(language.command) for language in to_install]
        state_dir(checkout).mkdir(parents=True, exist_ok=True)
        try:
            worker = _start_worker(checkout, retry_failed)
        except OSError:
            worker = None
        if worker is not None:
            if acquire_lock(checkout, worker.pid, commands):
                # A worker that exited before the lock was linked cannot remove it; poll also reaps the child.
                if worker.poll() is not None:
                    release_lock(checkout, worker.pid)
            else:
                lock = live_lock(checkout)
                if lock is None:
                    return []
                # The worker may have taken the lock before this call did.
                if lock["pid"] != worker.pid:
                    return [_running_line(lock)]
            failed = next((language for language in to_install if language.state == "failed"), None)
            if failed is not None:
                lines.append(M_RETRY.format(reason=failed.entry["reason"], commands=" && ".join(commands)))
            else:
                lines.append(M_START.format(commands=" && ".join(commands)))
    for language in languages:
        if language in to_install:
            continue
        if language.state == "no-manager":
            lines.append(
                M_NOMANAGER.format(executable=language.command[0], command=command_text(language.command))
            )
        elif language.state == "failed":
            lines.append(
                M_FAILED.format(
                    language=language.name,
                    reason=language.entry["reason"],
                    command=command_text(language.command),
                )
            )
        elif language.state == "manual":
            lines.append(M_MANUAL.format(command=command_text(language.command)))
    return lines


def restore_hooks_path(checkout: Path) -> list[str]:
    def git(*arguments):
        return subprocess.run(
            ["git", "-C", str(checkout), *arguments],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=10,
        )

    try:
        if git("config", "--get", "core.hooksPath").stdout.strip():
            return []
        if any((checkout / name).exists() for name in HOOK_MANAGER_FILES):
            return []
        if not (checkout / HOOKS_PATH / "pre-commit").is_file():
            return []
        if git("config", "core.hooksPath", HOOKS_PATH).returncode != 0:
            return []
    except (OSError, subprocess.SubprocessError):
        return []
    return [M_HOOKS]


def status_lines(checkout: Path, wait: int = 0) -> list[str]:
    if not is_installed(checkout):
        return []
    deadline = time.monotonic() + wait
    while live_lock(checkout) is not None and time.monotonic() < deadline:
        time.sleep(0.2)
    lock = live_lock(checkout)
    lines = []
    for language in language_states(checkout):
        if language.state == "undeclared":
            continue
        fields = {"language": language.name}
        if language.command is not None:
            fields.update(executable=language.command[0], command=command_text(language.command))
        state = language.state
        if state == "runnable":
            lines.append(S_RUNNABLE.format(tools=", ".join(language.declared), **fields))
        elif state == "off":
            lines.append(S_OFF.format(**fields))
        elif state == "no-lockfile":
            lines.append(S_NOLOCK.format(**fields))
        elif state == "settled":
            lines.append(S_SETTLED.format(**fields))
        elif state == "no-manager":
            lines.append(S_NOMANAGER.format(**fields))
        elif state == "manual":
            lines.append(S_MANUAL.format(**fields))
        elif lock is not None:
            lines.append(S_RUNNING.format(n=max(0, int(time.time() - lock["started"])), **fields))
        elif state == "failed":
            lines.append(S_FAILED.format(reason=language.entry["reason"], **fields))
        else:
            lines.append(S_PENDING.format(**fields))
    return lines or [S_NONE]


def _reason(returncode: int, stdout: str, stderr: str) -> str:
    for text in (stderr, stdout):
        for line in text.splitlines():
            if line.strip():
                return f"exit {returncode}: {line.strip()[:200]}"
    return f"exit {returncode}"


def _run_command(checkout: Path, command: tuple[str, ...], timeout: int) -> str | None:
    print(f"$ {command_text(command)}", flush=True)
    try:
        process = subprocess.Popen(
            list(command),
            cwd=checkout,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            start_new_session=True,
        )
    except Exception as error:
        message = str(error).splitlines()
        return f"{type(error).__name__}: {message[0] if message else ''}"
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # The whole group: a manager's child processes would otherwise keep the pipes open.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            process.kill()
        process.communicate()
        return f"timeout after {timeout}s"
    print(stdout + stderr, end="", flush=True)
    return None if process.returncode == 0 else _reason(process.returncode, stdout, stderr)


def run_worker(checkout: Path, retry_failed: bool) -> None:
    if not is_installed(checkout):
        return
    pid = os.getpid()
    first = install_set(language_states(checkout), retry_failed)
    if not first:
        release_lock(checkout, pid)
        return
    state_dir(checkout).mkdir(parents=True, exist_ok=True)
    lock = read_lock(checkout)
    if lock is None or lock["pid"] != pid or live_lock(checkout) is None:
        if not acquire_lock(checkout, pid, [command_text(language.command) for language in first]):
            return
    try:
        languages = install_set(language_states(checkout), retry_failed)
        commands = [command_text(language.command) for language in languages]
        if commands and commands != (read_lock(checkout) or {}).get("commands"):
            _write_json_atomic(state_dir(checkout) / "lock", _lock_content(pid, commands))
        timeout = timeout_seconds()
        for language in languages:
            failure = _run_command(checkout, language.command, timeout)
            entry = {
                "lock_sha": language.lock_sha,
                "command": command_text(language.command),
                "finished": int(time.time()),
            }
            if failure is None:
                verified = all(_present(language.row, tool, checkout) for tool in language.declared)
                entry = {"result": "ok", "verified": verified, **entry}
            else:
                entry = {"result": "failed", "reason": failure, **entry}
            record_entry(checkout, language.name, entry)
    finally:
        release_lock(checkout, pid)
