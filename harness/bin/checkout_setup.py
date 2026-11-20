#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import checkout_setup  # noqa: E402
import config  # noqa: E402


class _QuietParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)

    def exit(self, status=0, message=None):
        raise ValueError(message or str(status))


def _non_negative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise ValueError(value)
    return number


def _parser() -> argparse.ArgumentParser:
    parser = _QuietParser(add_help=False)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("hook", add_help=False)
    status = commands.add_parser("status", add_help=False)
    status.add_argument("--wait", type=_non_negative, default=0)
    run = commands.add_parser("run", add_help=False)
    run.add_argument("--checkout", required=True)
    run.add_argument("--retry-failed", action="store_true")
    return parser


def _hook_directory() -> str:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        payload = None
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    return cwd if isinstance(cwd, str) and cwd else os.getcwd()


def _hook() -> list[str]:
    checkout = checkout_setup.checkout_of(_hook_directory())
    if checkout is None or not checkout_setup.is_installed(checkout):
        return []
    lines = checkout_setup.restore_hooks_path(checkout)
    try:
        lines += checkout_setup.ensure(checkout, retry_failed=True)
    except Exception:
        pass
    return lines


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
        if args.command == "run":
            checkout_setup.run_worker(Path(args.checkout), args.retry_failed)
            return 0
        if args.command == "hook":
            lines = _hook()
        else:
            lines = checkout_setup.status_lines(config.REPO_ROOT, args.wait)
        if lines:
            sys.stdout.write("\n".join(lines) + "\n")
            sys.stdout.flush()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException:
        sys.exit(0)
