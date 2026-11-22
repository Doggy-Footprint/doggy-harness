#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

PREFIX = "harness customization: "


def main() -> int:
    import customization

    lines = customization.notice_lines(customization.analyze())
    if lines:
        sys.stdout.write("".join(f"{PREFIX}{line}\n" for line in lines))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    # A hook must never fail the session: any internal error prints nothing and exits 0.
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
