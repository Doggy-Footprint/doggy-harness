import json
from pathlib import Path

_HARNESS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = _HARNESS_DIR.parent


def read_override(path: Path) -> tuple[dict | None, str | None]:
    if not path.is_file():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return None, f"invalid JSON: {error}"
    if not isinstance(data, dict):
        return None, f"found JSON {type(data).__name__} instead of an object"
    return data, None


def load_config() -> dict:
    config = json.loads((_HARNESS_DIR / "config.default.json").read_text(encoding="utf-8"))
    # A broken override falls back to the defaults so a hook never crashes on it; the customization notice reports it.
    override, _problem = read_override(_HARNESS_DIR / "config.json")
    if override is not None:
        config.update(override)
    return config


class Paths:
    def __init__(self, config: dict):
        self.docs_root = REPO_ROOT / config["docs_root"]
        self.exclude_dirs = set(config["exclude_dirs"])
        self.try_n_fail = self.docs_root / "try-n-fail"
        self.todos = self.docs_root / "todos"
        self.synced_comments = self.docs_root / "synced-comments"
        self.specs = self.docs_root / "specs"
        self.spec_logs = self.docs_root / "spec-logs"
        self.facts = self.docs_root / "facts.md"


def load_paths() -> Paths:
    return Paths(load_config())
