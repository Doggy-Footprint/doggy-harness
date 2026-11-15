#!/usr/bin/env python3
import sys
from pathlib import Path


def main() -> int:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
        import spec_state

        spec_state.print_notice()
        sys.stdout.flush()
    except Exception:
        # A broken spec directory or config must not fail session start.
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
