import subprocess
import tempfile
from pathlib import Path

from test_installer import REPO_ROOT

BASE_0420 = "611e1f635fe547798a5a24512249cb2f0743f156"
BASE_0491 = "4a0980791249eaea54a6201007c19ecc98fb87fa"
BASE_0470 = "7c1e04db4e55af0c0ea24e6460b3f385fcd1bd8e"
BASE_0551 = "5cba48cb0dfa923b19e9e808ca5cb63cb3c3ab3a"
_SOURCES = {}


def release_source(commit):
    if commit not in _SOURCES:
        exists = subprocess.run(["git", "-C", str(REPO_ROOT), "cat-file", "-e", f"{commit}^{{commit}}"],
                                capture_output=True, text=True)
        if exists.returncode != 0:
            raise RuntimeError(f"commit {commit} is not available in this checkout")
        tmp = tempfile.TemporaryDirectory()
        source = Path(tmp.name)
        archive = subprocess.run(["git", "-C", str(REPO_ROOT), "archive", commit, "installer", "harness"],
                                 capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(source)], input=archive, check=True)
        _SOURCES[commit] = (tmp, source)
    return _SOURCES[commit][1]


def old_release_source():
    return release_source(BASE_0420)


def base_file(commit, rel):
    return subprocess.run(["git", "-C", str(REPO_ROOT), "show", f"{commit}:{rel}"],
                          capture_output=True, text=True, check=True).stdout
