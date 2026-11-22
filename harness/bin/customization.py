#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import customization  # noqa: E402

USAGE = "usage: customization.py status | confirm PATH..."


def main(argv: list[str]) -> int:
    if argv == ["status"]:
        print("\n".join(customization.status_lines(customization.analyze())))
        return 0
    if len(argv) >= 2 and argv[0] == "confirm":
        lines, code = customization.confirm(None, argv[1:])
        print("\n".join(lines))
        return code
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
