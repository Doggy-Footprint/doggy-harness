#!/usr/bin/env python3
# Runs under `uv run --no-project --with ... python -I`: no harness imports are available, and it must only parse
# the given source text, never import or execute repository code.
import json
import re
import sys

import tree_sitter
import tree_sitter_kotlin
import tree_sitter_typescript

GRAMMARS = {
    "typescript": tree_sitter_typescript.language_typescript,
    "tsx": tree_sitter_typescript.language_tsx,
    "kotlin": tree_sitter_kotlin.language,
}
COMMENT_NODE_TYPES = {
    "typescript": {"comment"},
    "tsx": {"comment"},
    "kotlin": {"line_comment", "block_comment"},
}
TYPESCRIPT_DIRECTIVES = (
    re.compile(
        r"(?://|/\*)\s*(?:@ts-|eslint-disable|eslint-enable|prettier-ignore|biome-ignore|istanbul ignore|c8 ignore"
        r"|v8 ignore|#__PURE__|@__PURE__|webpackChunkName)"
    ),
    re.compile(r"///\s*<reference"),
)
KOTLIN_DIRECTIVES = (
    re.compile(
        r"(?://|/\*) *(?:ktlint-disable|ktlint-enable|noinspection|@formatter:off|@formatter:on"
        r"|spotless:off|spotless:on|language=)"
    ),
)
DIRECTIVES = {"typescript": TYPESCRIPT_DIRECTIVES, "tsx": TYPESCRIPT_DIRECTIVES, "kotlin": KOTLIN_DIRECTIVES}


def comment_lines(parser: tree_sitter.Parser, grammar: str, source: str) -> list[int]:
    tree = parser.parse(source.encode("utf-8"))
    lines = set()
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in COMMENT_NODE_TYPES[grammar]:
            text = source_text(node)
            if any(pattern.match(text) for pattern in DIRECTIVES[grammar]):
                continue
            if node.start_point[0] == 0 and text.startswith("#!"):
                continue
            lines.update(range(node.start_point[0] + 1, node.end_point[0] + 2))
        else:
            stack.extend(node.children)
    return sorted(lines)


def source_text(node: tree_sitter.Node) -> str:
    return node.text.decode("utf-8", errors="replace")


def main() -> int:
    request = json.load(sys.stdin)
    parsers = {}
    result = {}
    for path, item in request.items():
        grammar = item["grammar"]
        if grammar not in parsers:
            parsers[grammar] = tree_sitter.Parser(tree_sitter.Language(GRAMMARS[grammar]()))
        result[path] = comment_lines(parsers[grammar], grammar, item["source"])
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
