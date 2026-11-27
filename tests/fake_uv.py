import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

SCRIPT = """#!{python}
import json, os, sys
argv = sys.argv[1:]
stdin = sys.stdin.read()
with open(os.environ["FAKE_UV_LOG"], "a") as fh:
    fh.write(json.dumps({{"argv": argv, "stdin": stdin, "cwd": os.getcwd()}}) + "\\n")
mode = os.environ.get("FAKE_UV_MODE", "ok")
offline = "--offline" in argv
try:
    requested = json.loads(stdin)
except ValueError:
    requested = {{}}


def ok():
    out = {{}}
    for path, item in requested.items():
        out[path] = [n for n, line in enumerate(item["source"].splitlines(), 1) if line.lstrip().startswith("//")]
    print(json.dumps(out))


if mode == "ok":
    ok()
elif mode == "offline_fail":
    if offline:
        sys.stderr.write("offline cache miss\\n")
        sys.exit(3)
    ok()
elif mode == "both_fail":
    if offline:
        sys.stderr.write("offline cache miss\\n")
        sys.exit(3)
    sys.stderr.write("network down\\nsecond line\\n")
    sys.exit(7)
elif mode == "list":
    print("[1,2]")
elif mode == "missing":
    print("{{}}")
elif mode == "nonint":
    print(json.dumps({{p: ["x"] for p in requested}}))
elif mode == "notjson":
    print("not json")
"""


def tool_dir(test, with_uv):
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    directory = Path(tmp.name)
    os.symlink(shutil.which("git"), directory / "git")
    if with_uv:
        uv = directory / "uv"
        uv.write_text(SCRIPT.format(python=sys.executable))
        uv.chmod(uv.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    elif shutil.which("uv", path=str(directory)):
        raise AssertionError("uv resolvable in the uv-free directory")
    return directory


def calls(log):
    log = Path(log)
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
