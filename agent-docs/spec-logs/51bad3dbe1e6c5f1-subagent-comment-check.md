---
version: 1
run_id: 51bad3dbe1e6c5f1
status: complete
base_commit: 75e9d8f15a59e9dea9fe346c10016de0d0585a80
max_verifier_invocations: 2
commit: 75e9d8f15a59e9dea9fe346c10016de0d0585a80
---

# User Intent
| id | stakeholder | intention | observable goal |
| --- | --- | --- | --- |
| UI1 | harness owner | Comments that restate code, written by `implementer` and `test-implementer`, stop reaching pull requests | when either role tries to finish with comments it added in its own spec paths, it receives the list once and must remove or justify them before its report reaches main |
| UI2 | harness owner | The check sees files no matter how they were written | files written through Bash heredocs or scripts are checked the same as files written with Write/Edit |
| UI3 | harness owner | TypeScript and JavaScript comments are detected from the syntax, not from line shapes, with no false positives from text inside strings | `//`, `/*`, `#` inside string, template, regex and JSX text are never reported; comments inside template `${}` and JSX `{}` are |
| UI4 | harness owner | A check that could not run is never silently treated as passed | when the TypeScript scanner cannot run, the commit warning says so, the PR gate fails, and the subagent is stopped once to report it |
| UI5 | harness owner | Each role audits its own comments | both roles' reports carry a Comments item listing each added comment with its Comment Enforcement category |

# Scope
In scope: TypeScript/JavaScript comment detection through tree-sitter run by `uv`, shared by the staged mode, the gate and legacy modes, and the new subagent check; a working-tree scan restricted to given paths; a Claude Code hook that records a baseline at subagent start and checks at the subagent's finish (PreToolUse on `SubagentHandback`, and `SubagentStop`); telemetry of the check; the Comments report item in the two agent definitions; `uv` in the comment CI workflow; version 0.57.0 with its migration note; README rows.
Out of scope: Codex hooks and Codex behavior (the owner does not use Codex); tree-sitter grammars for other languages (`tree-sitter-language-pack` is deferred); changes to Python or other-language detection; the doggy-workflow skill text and main's Reconcile step; judging whether a comment is allowed (the check lists, the agent judges); a per-repository switch to turn the check off; the A/B measurement (a separate spec).

# Paths
Implementation: harness/, installer/, README.md, .harness/, .claude/, .codex/, .agents/
Tests: tests/
Test command: HARNESS_TEXT_TESTS=1 uv run --python 3.12 --with pytest --with hypothesis python tests/run_parallel.py
Review evidence: main runs R1–R4 after the Test command passes and after regenerating the installed copy with `python3 installer/harness.py update . --no-commit` (the implementer edits only `harness/` and `installer/` and `README.md`; the installed copies under `.harness/`, `.claude/`, `.codex/`, `.agents/` change only through that command). Each run sets `HARNESS_TARGETS_FILE` to a file in the session scratchpad; commands, environment and observed output are saved in the scratchpad as `review/r<n>.md` and summarized in the execution ledger. R1 — interactive finish check: in an interactive Claude Code session whose settings carry the new hooks and whose subagents finish through `SubagentHandback`, with this spec active, main dispatches `implementer` with the instruction "create `harness/zz_probe.py` containing a function with the comment `# returns the sum of a and b`, then finish"; expected: the subagent's first `SubagentHandback` is denied with the check's reason, the subagent then removes the comment or lists it under Comments, telemetry holds a `subagent_comments` event with `blocked: true` then one with `blocked: false`; main deletes `harness/zz_probe.py` afterwards. When the running session does not load the regenerated hooks, R1 runs in a new interactive session. R2 — timing: with a warm `uv` cache, main runs the finish check's scan on a scratch repository with 20 changed `.ts`/`.tsx` files (about 200 lines each) 5 times and records the median wall time. R3 — code read: main reads the changed detector and hook and records (a) one comment-detection function serves staged, gate, legacy and working-tree modes, (b) the `uv` command pins both package versions with `==` and runs the scanner with `python -I`, (c) the scanner parses source only and runs no repository code, (d) grammar choice is one extension→grammar table. R4 — installed copy: after the update command, main records that `.claude/settings.json` registers the three new hook entries, `.codex/hooks.json` does not, `.claude/agents/implementer.md` and `.claude/agents/test-implementer.md` contain the Comments report item, and `.github/workflows/` (when installed with CI) holds the `uv` setup step.
Fuzzing: none — the scanner's lexical handling is tree-sitter's upstream grammar; this repository's code maps comment nodes to lines and filters directives, and O1–O3 enumerate every lexical context and directive that mapping handles.
Mutation tool: none — this repository has no `pyproject.toml`, `package.json`, `go.mod`, or `Cargo.toml`, so no mutation tool is installed for it; the verifier's 8–10 hand mutations apply.

# Signatures
warn_new_comments.py --staged    # unchanged CLI; exit 0 always
warn_new_comments.py <base-sha> <head-sha>    # unchanged CLI (legacy warning mode)
warn_new_comments.py <base-sha> <head-sha> --approved yes|no    # unchanged CLI (gate mode)
class CommentScanError(Exception)    # in harness/git/warn_new_comments.py; str() names the files and the reason
changed_lines(base: str, head: str) -> list[tuple[str, int, str]]    # existing; may raise CommentScanError
staged_lines() -> list[tuple[str, int, str]]    # existing; may raise CommentScanError
working_tree_comments(paths: list[str]) -> list[tuple[str, int, str]]    # new, in harness/git/warn_new_comments.py; may raise CommentScanError
harness/git/ts_comments.py    # new scanner script; stdin: JSON object {path: {"grammar": "typescript"|"tsx", "source": str}}; stdout: JSON object {path: [comment line numbers, 1-based, ascending]}; exit 0 on success
harness/hooks/subagent_comments.py    # new Claude Code hook; events SubagentStart, SubagentStop, PreToolUse (matcher SubagentHandback); stdin: hook payload JSON; stdout: hook output JSON or nothing; exit 0
telemetry event `subagent_comments` with fields: stage ("start" | "finish"), trigger ("handback" | "stop" | "start"), new_comments (int), scan_ok (bool), blocked (bool)

# Functional Requirements
| id | requirement | priority | source |
| --- | --- | --- | --- |
| R1 | Files ending in `.ts`, `.mts`, `.cts` are parsed with the tree-sitter `typescript` grammar; `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs` with the `tsx` grammar. A line is a comment line when it lies within a tree-sitter `comment` node. Text inside string, template string, regex and JSX text or attribute nodes is never a comment line; a `comment` node inside a template substitution or a JSX expression container is. | must | UI3 |
| R2 | Every line spanned by a multi-line comment node counts as a comment line, the same as every line of a Python docstring counts today. | must | UI3 |
| R3 | A TypeScript/JavaScript comment whose text starts, after `//` or `/*` and optional spaces, with `@ts-`, `eslint-disable`, `eslint-enable`, `prettier-ignore`, `biome-ignore`, `istanbul ignore`, `c8 ignore`, `v8 ignore`, `#__PURE__`, `@__PURE__`, or `webpackChunkName`, or a `///` comment that starts with `<reference`, is a tool directive and is not reported. Line 1 starting with `#!` is not reported. | must | UI3 |
| R4 | `CODE_EXTENSIONS` also contains `.mts`, `.cts`, `.mjs`, `.cjs`. | must | UI3 |
| R5 | One scan runs the scanner at most once for all TypeScript/JavaScript files with added lines, as `uv run --no-project --offline --with tree-sitter==0.27.0 --with tree-sitter-typescript==0.23.2 python -I <scanner>` and, when that exits non-zero, once more without `--offline`. `uv` is looked up on `PATH`. A scan with no TypeScript/JavaScript file to check never starts `uv`. | must | UI3, UI4 |
| R6 | The scan raises `CommentScanError` when `uv` is not on `PATH`, when both runs exit non-zero, or when the scanner's output is not a JSON object mapping each requested path to a list of integers. The message names the files and the reason. | must | UI4 |
| R7 | `--staged` on `CommentScanError`: stderr gets `comment check could not run for <files>: <reason>` and the existing agent sentence; exit 0. Gate mode (`--approved yes` or `no`) on `CommentScanError`: prints `::error title=Comment check could not run::<message>` and exits 1, whatever the label. Legacy two-argument mode on `CommentScanError`: prints `::warning title=Comment check could not run::<message>` and exits 0. | must | UI4 |
| R8 | Python files keep tokenize-based detection and other code files keep the line pattern; their findings and every existing output text are unchanged. | must | compatibility |
| R9 | `working_tree_comments(paths)` returns comments on lines added relative to `HEAD` in tracked files (staged or not) plus every comment line of untracked, non-ignored files, restricted to files under the given paths; a path ending in `/` or naming a directory matches files beneath it, any other path matches that file. In a repository without a commit, every line of every non-ignored file under the paths counts as added. Content is read from the working tree. | must | UI2 |
| R10 | At `SubagentStart` of `implementer` or `test-implementer`, when at least one spec under the specs directory has `status: active`, the hook records the role's baseline: the multiset of `(path, comment text)` from `working_tree_comments` over the union of the active specs' `Implementation` paths (implementer) or `Tests` paths (test-implementer), stored under `.harness/sessions/subagent-comments/<agent id>.json`. A scan failure at start is recorded as a failed baseline. | must | UI1 |
| R11 | The finish check runs at the first of: PreToolUse of `SubagentHandback` called by an `implementer` or `test-implementer` agent, or `SubagentStop` of such an agent. New comments are the current scan's `(path, line, text)` entries left after removing, per `(path, text)`, as many entries as the baseline holds. A missing or unreadable baseline, or a failed baseline, counts as an empty baseline. | must | UI1 |
| R12 | When the finish check finds new comments or its scan raises `CommentScanError`, and this agent id has not been stopped before, the hook stops it once: on PreToolUse it outputs `hookSpecificOutput` with `permissionDecision: "deny"` and the reason; on `SubagentStop` it outputs `{"decision": "block", "reason": ...}`. It records that this agent id was stopped. Every later finish check of the same agent id allows the finish and outputs nothing. | must | UI1, UI4 |
| R13 | The reason text: first line `harness: comment check before you hand back.`; then up to 50 entries `<path>:<line>: <comment text>` and, when there are more, `... and <n> more`; then `Keep a comment only when it records a non-obvious design constraint, external-system behavior, safety/security invariant, or reason a seemingly odd implementation is necessary. Delete every other comment above. List each comment you keep under Comments in your report, with its category, then hand back.` On `CommentScanError` the reason is `harness: the comment check could not run: <message>. Write this under Comments in your report, then hand back.` | must | UI1, UI4 |
| R14 | Each finish check emits telemetry `subagent_comments` with `stage: "finish"`, `trigger`, `new_comments`, `scan_ok`, `blocked`; each baseline record emits it with `stage: "start"`, `trigger: "start"`, `new_comments: 0`, `scan_ok`, `blocked: false`. | must | measurement |
| R15 | At `SubagentStop` that allows the finish, the hook deletes the agent's baseline and stop record. | should | housekeeping |
| R16 | Agents other than `implementer` and `test-implementer`, a missing specs directory, no active spec, or an empty path list for the role: the hook records nothing and outputs nothing. | must | scope |
| R17 | Any exception in the hook other than `CommentScanError` ends it with exit 0 and no output. | must | harness convention |
| R18 | `hooks.spec.json` registers the hook for `SubagentStart`, `SubagentStop`, and `PreToolUse` with matcher `SubagentHandback`, each with `"targets": ["claude"]`. | must | UI1 |
| R19 | The Report section of `harness/agents/implementer.md` gets, as its last bullet: `- **Comments** — each comment or docstring you added, as `path:line — category`, where category is the one it records: design constraint, external-system behavior, safety/security invariant, or reason for an odd implementation; `none` if you added none. A comment that fits no category restates the code: delete it instead of listing it.` The Report section of `harness/agents/test-implementer.md` gets, as its last bullet: `- Comments added in Tests, each as `path:line — category` (design constraint, external-system behavior, safety/security invariant, or reason for an odd implementation), or `none`. A comment that fits no category restates the test: delete it instead of listing it.` | must | UI5 |
| R20 | `harness/ci/harness-comment-warning.yml` runs `astral-sh/setup-uv@v10` after checkout and before the gate step. | must | UI4 |
| R22 | The scanner environment lives only in the user-level `uv` cache: the scan writes nothing into the repository or any worktree (no virtual environment, lockfile or cache directory), so a linked worktree and the main worktree run the same cached packages, and a worktree created after another worktree has run the check needs no network. The hook's baseline and stop records live under `.harness/sessions/` of the worktree the subagent works in, because they describe that worktree's files. | must | user: worktrees |
| R21 | `harness/VERSION` is `0.57.0`; `MIGRATIONS` gains a 0.57.0 entry whose label says that implementer and test-implementer are stopped once to remove or justify comments they added, that TypeScript/JavaScript comments are detected with tree-sitter through `uv`, and that the comment check needs `uv` on PATH and in CI; README describes the subagent comment check and the `uv` requirement. | must | release convention |

# Errors
- `uv` not on PATH — `CommentScanError("... uv not found on PATH")` — staged: stderr message, commit continues; gate: `::error`, exit 1; legacy: `::warning`, exit 0; hook: subagent stopped once with the could-not-run reason.
- Offline run fails (package not cached) — the online run follows — same outcome as a first-try success when it succeeds.
- Both runs fail (no network, PyPI unreachable, wheel unavailable for the platform) — `CommentScanError` naming the last exit code and the first stderr line — same post-failure states as above.
- Scanner output malformed (not JSON, missing path, non-integer) — `CommentScanError("... unexpected scanner output")` — same post-failure states.
- Source with syntax errors — tree-sitter recovers; comment nodes it still produces are reported — no error signal.
- Hook payload not JSON, unknown event, baseline file unwritable, sessions directory missing — exit 0, no output — subagent finishes normally.
- Git command fails in the working-tree scan (not a repository) — `CommentScanError` — hook stops once with the could-not-run reason.

# Cases
| id | level | input / state | expected result |
| --- | --- | --- | --- |
| C1 | normal | staged `.ts` adds `// note` | `a.ts:<n>: // note` reported |
| C2 | edge | staged `.ts` adds `const u = "http://x/a // b";` | nothing reported |
| C3 | edge | staged `.ts` adds a template string spanning lines whose text has `// x` and `# y`, with `${a /* c */}` inside | only the line holding `/* c */` reported |
| C4 | edge | staged `.ts` adds `const r = /\/\/x/g; const d = a / b;` | nothing reported |
| C5 | edge | staged `.tsx` adds `<p title="// t">Don't // x {/* y */}</p>` and, on the next line, `// z` | the `{/* y */}` line and the `// z` line reported; nothing from title or text |
| C6 | normal | staged `.ts` adds a 3-line `/** ... */` | 3 lines reported |
| C7 | normal | staged `.ts` adds `// @ts-expect-error`, `/* eslint-disable */`, `/// <reference types="x" />`, `/*#__PURE__*/ f()` | nothing reported |
| C8 | edge | staged `.ts` adds `class A { #count = 0 }` | nothing reported |
| C9 | normal | each of `.mts .cts .tsx .js .jsx .mjs .cjs` adds `// k` | each reported, `.tsx/.js/.jsx/.mjs/.cjs` scanned with `tsx`, `.ts/.mts/.cts` with `typescript` |
| C10 | edge | staged `.js` line 1 `#!/usr/bin/env node` | nothing reported |
| C11 | normal | staged change touches only `.py` and `.kt` files | findings as before; `uv` not started |
| C12 | error | `uv` absent from PATH, staged `.ts` comment | stderr `comment check could not run for a.ts: ...` and agent sentence; exit 0 |
| C13 | error | `uv` absent, gate `--approved yes` with a `.ts` change | `::error title=Comment check could not run::...`; exit 1 |
| C14 | error | `uv` absent, legacy two-argument mode with a `.ts` change | `::warning title=Comment check could not run::...`; exit 0 |
| C15 | boundary | fake `uv` fails with `--offline`, succeeds without | findings reported; `uv` called twice, second without `--offline` |
| C16 | error | fake `uv` fails both times | `CommentScanError`; mode-specific outcome as C12–C14 |
| C17 | error | fake `uv` prints `[1,2]` or omits a requested path | `CommentScanError` "unexpected scanner output" |
| C18 | normal | working tree: tracked `.py` modified with a new `# c`, untracked `.ts` with `// d`, ignored `.ts` with `// e`, file outside paths with `// f` | `# c` and `// d` returned only |
| C19 | boundary | repository with no commit, paths `src/` | every comment line of non-ignored files under `src/` returned |
| C20 | normal | implementer start with active spec; finish (handback) adds nothing new | no output; telemetry finish `new_comments: 0, blocked: false` |
| C21 | normal | implementer start; adds `# returns a+b` in an Implementation path; first handback | deny with R13 reason listing the line; telemetry `blocked: true` |
| C22 | normal | after C21, second handback, then SubagentStop | both allow with no output; baseline and stop record deleted at SubagentStop |
| C23 | normal | session without handback: first SubagentStop with a new comment, second SubagentStop | first `decision: block` with reason; second no output |
| C24 | edge | baseline already holds `# old` in a path; subagent adds nothing; also moves `# old` to another line of the same file | no new comments |
| C25 | edge | baseline file deleted before finish; a comment added before start exists | it is reported as new (empty baseline) |
| C26 | boundary | 51 new comments | 50 entries then `... and 1 more` |
| C27 | error | `uv` absent at finish | stopped once with the could-not-run reason; second finish allowed |
| C28 | normal | parallel implementer and test-implementer, disjoint paths, each adds one comment in its own paths | each reason lists only its own comment |
| C29 | normal | `test-verifier` start/stop; implementer with no active spec | no record, no output |
| C30 | error | hook stdin `not json`; sessions directory not writable | exit 0, no output |
| C31 | normal | installer generates settings and agent files | `.claude/settings.json` has the three entries; `.codex/hooks.json` lacks them; both agent `.md` files end their Report with the R19 bullet |
| C33 | normal | linked worktree created with `git worktree add`; `uv` cache warmed by a run in the main worktree; `uv` called with `--offline` succeeds; staged `.ts` comment in the linked worktree | finding reported with one `uv` call; `git status` of both worktrees shows no new files from the scan; a hook run in the linked worktree writes its records under the linked worktree's `.harness/sessions/` |
| C32 | normal | CI workflow text | `astral-sh/setup-uv@v10` step after checkout and before the gate step |

# Quality Applicability
| ISO/IEC 25010:2023 characteristic | applicable | rationale |
| --- | --- | --- |
| Functional suitability | yes | detection correctness and the stop-once state machine are the feature |
| Performance efficiency | yes | the finish check runs on every subagent finish and starts `uv` |
| Compatibility | yes | existing CLI modes, Python/other-language findings and the existing subagent hooks must stay as they are |
| Interaction capability | yes | the reason text is what the subagent acts on |
| Reliability | yes | scanner failure must fail closed, hook bugs must fail open |
| Security | yes | the check fetches and runs third-party packages |
| Maintainability | yes | three entry points must share one detector |
| Flexibility | yes | more grammars are expected later (`tree-sitter-language-pack`) |
| Safety | no | no physical or human harm path |

# Quality Requirements
| id | characteristic / subcharacteristic | target and context | measure method / inputs / unit | threshold and direction | evidence: automated, review, mutation | source |
| --- | --- | --- | --- | --- | --- | --- |
| QR1 | Functional suitability / functional correctness | detector and hook over C1–C32 | Cases passing / Cases declared, % | 100%, higher is better | automated O1–O13; hand mutation | UI1–UI5 |
| QR2 | Performance efficiency / time behaviour | finish-check scan, warm `uv` cache, 20 changed `.ts`/`.tsx` files of about 200 lines | median wall time of 5 runs, seconds | ≤ 3 s, lower is better | review R2 | A13 |
| QR3 | Performance efficiency / resource utilization | scan with no TypeScript/JavaScript files | `uv` processes started, count | 0 | automated O4 | R5 |
| QR4 | Compatibility / co-existence | existing comment-gate tests and existing hook tests | tests passing unchanged, % | 100% | automated O5, O12 | R8 |
| QR5 | Interaction capability / user error protection | reason text given to the subagent | R13 elements present (header, entries, cap line, categories, instruction), count of 5 | 5 of 5 | automated O9 | R13 |
| QR6 | Reliability / fault tolerance | scanner unavailable or failing in each of 4 surfaces (staged, gate, legacy, hook) | surfaces behaving as R7/R12 / 4, % | 100% | automated O4, O8 | UI4 |
| QR7 | Security / integrity | third-party code fetched and run by the check | the `uv` command pins both packages with `==` and runs the scanner with `-I`; the scanner executes no repository code, yes/no | yes | automated O4 (fake `uv` receives the arguments); review R3 | A2 |
| QR8 | Maintainability / modularity | comment detection used by staged, gate, legacy and working-tree modes | detection implementations, count | 1 | review R3 | UI3 |
| QR9 | Flexibility / adaptability | adding a grammar later | places that map an extension to a grammar, count | 1 | review R3 | A17 |

# Verification Obligations
| id | parent requirement/Case ids | variant and target surface | test layer and selection policy | ISO/IEC/IEEE 29119-4 technique | coverage items | coverage target | observation and expected result | evidence procedure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| O1 | R1, R2, C1–C6, C8 | `warn_new_comments.py --staged` CLI on a temporary git repository, real `uv` | integration; one item per lexical context | equivalence partitioning | P1 line comment; P2 double-quoted string with `//`; P3 single-quoted string with `/*`; P4 template text with `//` and `#`; P5 comment in template `${}`; P6 regex literal with `\/\/`; P7 division next to a regex; P8 JSX attribute string with `//`; P9 JSX text with an apostrophe and `//`; P10 comment in a JSX `{}`; P11 multi-line block comment; P12 JSDoc; P13 `#private` field | 100% | stderr lists exactly the expected `path:line` set per item | automated unittest |
| O2 | R1, R4, C9 | staged CLI per extension | integration; every extension | equivalence partitioning | E1 `.ts`; E2 `.mts`; E3 `.cts`; E4 `.tsx`; E5 `.js`; E6 `.jsx`; E7 `.mjs`; E8 `.cjs` | 100% | each `// k` reported; a TSX-only construct (`<p>{/* y */}</p>`) is parsed correctly in E4–E8 and the generic arrow `<T,>(x: T) => x` with a following `// k` in E1–E3 | automated unittest |
| O3 | R3, C7, C10 | staged CLI, `.ts` and `.js` | integration; every directive | decision table | D1 `@ts-`; D2 `eslint-disable`; D3 `eslint-enable`; D4 `prettier-ignore`; D5 `biome-ignore`; D6 `istanbul ignore`; D7 `c8 ignore`; D8 `v8 ignore`; D9 `#__PURE__`; D10 `@__PURE__`; D11 `webpackChunkName`; D12 `/// <reference`; D13 shebang line 1; D14 plain `// note` as the reported control | 100% | D1–D13 not reported, D14 reported | automated unittest |
| O4 | R5–R7, R22, C11–C17, C33 | scan entry with a fake `uv` script on PATH that records its arguments, plus PATH without `uv` | integration; every rule column | decision table | conditions: TS file present (yes/no) × uv state (absent / offline ok / offline fail online ok / both fail / malformed output) × mode (staged / gate yes / gate no / legacy); rules T1 no TS any state → no `uv` call, prior output; T2 offline ok → 1 call with `--offline`, both pins, `-I`; T3 offline fail online ok → 2 calls, second without `--offline`; T4–T6 absent / both fail / malformed × each mode → R7 outcome; T7 staged scan in a linked worktree with the fake `uv` succeeding offline → findings, and no file added to either worktree | 100% of rules T1–T6 × 4 modes, and T7 | exit code, stdout/stderr text, and recorded `uv` arguments match R5–R7 | automated unittest |
| O5 | R8, C11 | existing comment-gate tests plus Python and Kotlin samples | integration; regression set | equivalence partitioning | N1 existing `tests/test_comment_gate.py` passes; N2 `.py` comment and docstring; N3 `.kt` `//` and `/**`; N4 `.yaml` `#` | 100% | outputs identical to the pre-change detector for N2–N4 | automated unittest |
| O6 | R9, C18, C19 | `working_tree_comments` called in a temporary repository | unit; every partition | equivalence partitioning | W1 tracked modified unstaged; W2 tracked staged; W3 untracked; W4 ignored; W5 outside paths; W6 directory path with `/`; W7 directory path without `/`; W8 file path; W9 repository without commit | 100% | returned list equals expected entries | automated unittest |
| O7 | R10, R11, C24, C25 | hook process fed payload JSON in an installed temporary repository | integration; every baseline partition | equivalence partitioning | B1 baseline empty; B2 baseline holds the same `(path, text)` moved to another line; B3 baseline holds one of two identical new comments (multiset); B4 baseline file missing; B5 failed baseline | 100% | new-comment set equals expected per item | automated unittest |
| O8 | R11, R12, R15, R17, C20–C23, C27, C30 | hook process, sequences of payloads | integration; every transition | state transition | states: S0 no record, S1 baseline recorded, S2 stopped once, S3 cleaned up; transitions: T1 S0→S1 start; T2 S1 handback, no new → allow; T3 S1 handback, new → deny, S2; T4 S2 handback → allow; T5 S2 stop → allow, S3; T6 S1 stop, new → block, S2; T7 S1 scan fails at finish → deny, S2; T8 S1 stop, no new → allow, S3; T9 malformed payload → exit 0, no output; T10 unwritable sessions directory → exit 0, no output | 100% of T1–T10 | hook stdout JSON (or empty), exit 0, record files present/absent as stated | automated unittest |
| O9 | R13, C26, C27 | reason text from O8 runs | integration; syntax of the message | syntax testing | M1 header line; M2 entry format `path:line: text`; M3 exactly 50 entries and `... and 1 more` for 51; M4 categories sentence; M5 could-not-run text | 100% | exact strings present | automated unittest |
| O10 | R14 | telemetry file written in O8 runs, with `HARNESS_TELEMETRY_DIR` set to a temporary directory | integration; every emission point | equivalence partitioning | Y1 start record; Y2 finish allow (new 0); Y3 finish deny (handback); Y4 finish block (stop); Y5 finish scan failure | 100% | event `subagent_comments` with the R14 field values | automated unittest |
| O11 | R10, R16, R22, C28, C29, C33 | hook with two agent ids in parallel and with gated-agent / spec preconditions | integration | scenario testing | SC1 implementer and test-implementer interleaved start, write, finish with disjoint paths; SC2 `test-verifier`; SC3 no specs directory; SC4 no active spec; SC5 active spec with empty Tests for test-implementer; SC6 implementer start and finish in a linked worktree | 100% | SC1 each reason lists only its own comment; SC2–SC5 no record, no output; SC6 records only under the linked worktree's `.harness/sessions/` | automated unittest |
| O12 | R18, R19, R21, C31 | installer `install`/`update` into a temporary repository | integration | equivalence partitioning | G1 `.claude/settings.json` has SubagentStart, SubagentStop and PreToolUse(`SubagentHandback`) entries for the hook; G2 `.codex/hooks.json` lacks them; G3 both `.claude/agents/*.md` end Report with the R19 bullet text; G4 `MIGRATIONS` has the 0.57.0 entry and `harness/VERSION` is `0.57.0`; G5 existing installer tests pass | 100% | file contents as stated | automated unittest |
| O13 | R20, C32 | `harness/ci/harness-comment-warning.yml` text | unit; static | syntax testing | Y1 `astral-sh/setup-uv@v10` step present; Y2 after checkout; Y3 before the gate step | 100% | step order as stated | automated unittest |
| O14 | QR2, QR7–QR9, R12 (real Claude Code) | real Claude Code sessions | review | experience-based (error guessing) | guessed defects: X1 deny on `SubagentHandback` does not resume the subagent; X2 warm scan too slow; X3 unpinned or non-isolated scanner run; X4 a second detection path; X5 grammar mapping duplicated | none — experience-based | R1–R4 records | review R1–R4 |
| verifier 1 | retry: V1-F1 clean hand-back then stop untested (O8); V1-F2 baseline matched by path only escapes (O7); V1-F3 shared baseline file across agents escapes (O11); V1-F4 comma-separated multi-path spec lines untested (O7, O11); V1-F5 scan failure at SubagentStop untested (O8, QR6); V1-F6 `... and <n> more` only n=1 (O9); V1-F7 TS file with no added lines vs `uv` start untested (O4 T1); V1-F8 `///` non-reference and multi-line directive untested (O3). Accepted: O1, O2, O5, O6, O10, O12, O13. Test-implementer's four intent gaps judged advisory | evidence gaps in Tests | correction batch 3 to test-implementer; the verifier's ten proposed mutations run as confirming mutations after the batch, with the Test command | run 4: 1526 tests, only the pre-existing t5 error; verifier 2: pass, V1-F1–F8 closed, advisories V2-A1–A3 |
| confirming mutations | — | — | M1 baseline by path, M2 shared baseline file, M3 clean hand-back clears records, M4 scan error swallowed at stop, M5 first path only, M6 constant `... and 1 more`, M7 `uv` for files without added lines, M8 every `///` excused, M9 first line only, M10 retry keeps `--offline`: each applied to `harness/` and `.harness/` copies, Test command run, restored with seed.py | 10 of 10 detected by the intended assertions (M1, M2 surface partly as errors from an absent deny output); logs in scratchpad mut/ |
| completion check | — | — | CQ1: an untracked `.kt` file is listed by `git ls-files --others` in `working_tree_comments` and matched by the unchanged line pattern (KDoc opener lines), `on_finish` denies the first hand-back via `first_stop`, the second passes; CQ2: `_scan_typescript` raises `CommentScanError` after offline and online runs fail, `staged_main` prints the could-not-run line and exits 0, gate mode prints `::error` and exits 1 whatever the label; CQ3: `SCANNER_PACKAGES` pins and `shutil.which("uv")`, failure is fail-closed; CQ4: `first_stop` exclusive create is the stop-once rule | — | 4 of 4 match; none invalid |

# Assumptions and Defaults
| id | decision | evidence and uncertainty | brief v1 — approved / vetoed → <answer> / user answer / user decision (main: <own option>) / facts.md: <first words of the entry> |
| --- | --- | --- | --- |
| A1 | Hooks for Claude Code only; Codex untouched | the owner does not use Codex | user answer |
| A2 | TypeScript/JavaScript detection with tree-sitter `0.27.0` and `tree-sitter-typescript` `0.23.2`, fetched and run by `uv run --with` | versions are the latest on PyPI on 2026-11-27; a probe on a TSX sample found the 5 real comments and no false ones, where Pygments misread JSX text | user decision (main: a hand-written lexer in the standard library) |
| A3 | Scanner failure fails closed per surface: staged warns, gate fails, legacy warns, subagent stopped once to report it | user's choice "ㄴ" | user decision (main: a hand-written lexer, so no scanner failure to handle) |
| A4 | Worktrees share the user's `uv` cache, so a new worktree, including next to a master worktree, needs no extra download once any worktree has run the check | `uv cache dir` is `~/.cache/uv` and no `UV_*` variable is set (checked 2026-11-27); the offline command ran from `/Users/hwansu/tools/harness` (master) and from this linked worktree with no network fetch, and wrote nothing to either worktree | user answer: no per-worktree cache setting (re-checked 2026-11-27: no `UV_*` variable, no `uv.toml`, no uv setting in shell start files or the orca workspace) |
| A5 | Stop each subagent at most once; every later finish passes | plan approved by the user on 2026-11-27 | user answer |
| A6 | Hook-internal errors fail open (exit 0, no output); only `CommentScanError` fails closed | every harness hook fails open (`harness/hooks/customization_context.py` header); the user's "ㄴ" was about the scanner | brief v1 — approved |
| A7 | A role's paths are the union of its paths in every active spec; no active spec, no check | `isolation._read_specs` reads active specs the same way | brief v1 — approved |
| A8 | Baseline keyed by agent id; a missing or failed baseline counts as empty | at worst a pre-existing comment is listed once | brief v1 — approved |
| A9 | Reason text lists at most 50 entries | the largest observed subagent added about 60 comment lines | brief v1 — approved |
| A10 | Directive list of R3 | common TypeScript/JavaScript tool directives; Python's existing directive filter is the precedent | brief v1 — approved |
| A11 | JavaScript extensions share the TSX grammar and join `CODE_EXTENSIONS` | same lexical rules; `.mjs/.cjs/.mts/.cts` were not checked before | brief v1 — approved |
| A12 | No per-repository switch to disable the check | none of the 10 installed repositories' instructions requires doc comments on every declaration (checked 2026-11-27) | brief v1 — approved |
| A13 | QR2 threshold 3 s | the probe took about 0.7 s including import and first parse | brief v1 — approved |
| A14 | `--offline` first, then online | keeps a warm machine off the network | brief v1 — approved |
| A15 | `astral-sh/setup-uv@v10` pinned to its major tag, like `actions/checkout@v4` in the same file | latest release v10.4.0 on 2026-11-20 | brief v1 — approved |
| A16 | Coverage targets 100% of declared items; verifier hand mutations 8–10 | harness default | brief v1 — approved |
| A17 | `tree-sitter-language-pack` deferred | user's choice | user answer |
| A18 | The harness is a personal project; no other person's installed repository needs to be considered | facts.md | facts.md: As of 2026-11-15 the harness is a personal project |
| A19 | Report wording of R19 drafted with the skill-creator guidance (explain the reason, keep the files' terse style); its effect is measured by the separate A/B spec rather than skill-creator's eval loop | user approved skill-creator use and the A/B measurement | brief v1 — approved |

# Alternatives
| decision id | option not taken | what it gains and what it costs | reversal condition: the state of the world in which it wins |
| --- | --- | --- | --- |
| A2 | hand-written TypeScript lexer in the standard library | no dependency, same answer everywhere; heuristics for regex/division and JSX can misread rare code | `uv` or PyPI becomes unavailable where the check runs |
| A2 | TypeScript compiler scanner through Node | compiler-exact; CI and new worktrees without `node_modules` fall back, so answers differ by machine | every place the check runs has the repository's `node_modules` |
| A2 | both scanners | best accuracy where possible; two implementations to keep in agreement | false positives from the single scanner become frequent |
| A2 | Pygments | pure Python, often preinstalled; misreads JSX text as comments | only non-JSX code is checked |
| A3 | fall back to the line pattern when the scanner fails | work never blocked; string false positives return silently | the owner prefers flow over an exact answer |
| A2 | install into a harness virtual environment at session start | no network at check time; more state to manage, commits before install finish cannot check | machines without network access at check time |
| A5 | stop at every finish while comments remain | stronger pressure; risk of a subagent that cannot hand back | the measurement shows subagents ignore one stop |
| A7 | check every changed file except the other role's paths | catches comments written outside the role's paths; mis-attributes files when both roles stray | roles often write outside their paths |
| A1 | Codex hooks too | coverage for Codex runs; Codex stop semantics unverified | the owner starts using Codex |
| — | a Write/Edit PostToolUse hook | earlier feedback; misses the Bash writes that carried 171 of 181 observed writes | subagents stop writing through Bash |

# Open Questions
| id | question | requirement, decision, or step it affects | what would settle it | open / settled v<n> — <answer> / deferred — <reason> |
| --- | --- | --- | --- | --- |
| Q1 | Does a PreToolUse deny on `SubagentHandback` make the subagent continue and hand back again? | R12 | review R1 | settled v1 — yes: the denied implementer deleted the comment and handed back again (review R1) |
| Q2 | Does a running session pick up the regenerated hooks, or does R1 need a new session? | R1 procedure | review R1 | settled v1 — yes: the hooks regenerated mid-session ran for later subagents of the same session |

# Completion Questions
| id | question | expected answer | what it tests: trade-off / engineer call (decision id) / final shape | built by: step id, or `all` | asked: no / closing <YYYY-MM-DD> | valid / invalid v<n> — <reason> |
| --- | --- | --- | --- | --- | --- | --- |
| CQ1 | An implementer writes a new Kotlin file through a Bash heredoc with three KDoc comments and calls its hand-back. What happens, step by step, until main receives the report? | the finish check scans the implementer's spec paths in the working tree, finds the three comments not in its start baseline, denies the first hand-back with the list and the four categories; the implementer deletes or keeps each and lists kept ones under Comments, hands back again, and that hand-back passes | final shape | all | closing 2026-11-27 | valid |
| CQ2 | A new laptop has no network on its first commit of a TypeScript change. What does the owner see at commit time, and what would the PR check do if pushed the same way? | the commit goes through with a "comment check could not run" warning; the PR gate fails regardless of the label until the check can run | engineer call (A3) | all | closing 2026-11-27 | valid |
| CQ3 | What did choosing tree-sitter through `uv` give up compared with a hand-written lexer, and where would the owner notice it? | the check now depends on `uv` and on fetching pinned packages once per machine; the owner notices on a machine or CI without `uv` or network, where the check fails closed instead of running | trade-off | all | closing 2026-11-27 | valid |
| CQ4 | The measurement shows subagents often keep a narrating comment after the single stop. Which decision would flip, and what would then differ? | the stop-once rule; the hook would stop again while new unlisted comments remain, at the risk of a subagent that cannot hand back | engineer call (A5) | all | no | valid |

# Traceability
| requirement id | Case ids | obligation ids | evidence procedure |
| --- | --- | --- | --- |
| R1 | C1–C5, C8, C9 | O1, O2 | automated |
| R2 | C6 | O1 | automated |
| R3 | C7, C10 | O3 | automated |
| R4 | C9 | O2 | automated |
| R5 | C11, C15 | O4 | automated |
| R6 | C16, C17 | O4 | automated |
| R7 | C12–C14 | O4 | automated |
| R8 | C11 | O5 | automated |
| R9 | C18, C19 | O6 | automated |
| R10 | C20, C28 | O7, O11 | automated |
| R11 | C20–C25 | O7, O8 | automated |
| R12 | C21–C23, C27 | O8, O14 | automated, review R1 |
| R13 | C21, C26, C27 | O9 | automated |
| R14 | C20–C23 | O10 | automated |
| R15 | C22 | O8 | automated |
| R16 | C29 | O11 | automated |
| R17 | C30 | O8 | automated |
| R18 | C31 | O12, O14 | automated, review R4 |
| R19 | C31 | O12, O14 | automated, review R4 |
| R20 | C32 | O13, O14 | automated, review R4 |
| R21 | C31 | O12 | automated |
| R22 | C33 | O4, O11 | automated |

# Workflow Control
| item | value |
| --- | --- |
| correction batches used | 3 |
| verifier invocations | 2 |
| open finding ids | none |

Audit state (one entry per obligation; retain prior decisions in the execution ledger):
| obligation id | spec version | evidence references and revision | accepted / open / invalidated / pending | rationale and mutation outcome | dependencies and reopening evidence |
| --- | --- | --- | --- | --- | --- |
| O1 | 1 | test_ts_comments LexicalContextTests; M9 killed by p11/p12; tests-diff-2 | accepted | verifier 2 pass | — |
| O2 | 1 | ExtensionTests, GrammarSelectionTests; tests-diff-2 | accepted | verifier 2 pass | — |
| O3 | 1 | DirectiveTests, d12/d2 variants; M8 killed by d12; tests-diff-2 | accepted | verifier 2 pass | — |
| O4 | 1 | test_ts_scan_modes; M7 killed by t1 deletion-only, M10 by t3/t5; tests-diff-2 | accepted | verifier 2 pass | — |
| O5 | 1 | RegressionTests, test_comment_gate; tests-diff-2 | accepted | verifier 2 pass | — |
| O6 | 1 | test_working_tree_comments; tests-diff-2 | accepted | verifier 2 pass | — |
| O7 | 1 | BaselineTests, a7 tests; M1 killed by b3, M5 by a7; tests-diff-2 | accepted | verifier 2 pass | — |
| O8 | 1 | StateTransitionTests; M3 killed by t2_t8/t3, M4 by t7 at stop; tests-diff-2 | accepted | verifier 2 pass | — |
| O9 | 1 | ReasonTextTests; M6 killed by m3 sixty; tests-diff-2 | accepted | verifier 2 pass | — |
| O10 | 1 | TelemetryTests Y1–Y5; tests-diff-2 | accepted | verifier 2 pass | — |
| O11 | 1 | ScenarioTests; M2 killed by sc1 per-agent-id and others; tests-diff-2 | accepted | verifier 2 pass | — |
| O12 | 1 | test_subagent_release, test_remove_progress vo8_f2, installer tests; tests-diff-2 | accepted | verifier 2 pass | — |
| O13 | 1 | test_subagent_release CI step order; tests-diff-2 | accepted | verifier 2 pass | — |
| O14 | 1 | review/r1.md–r4.md in the session scratchpad; tests-diff-2 | accepted | verifier 2 pass; main review | — |

Execution ledger (append attempts; preserve failed approaches):
| attempt | finding / failure signature | cause hypothesis | changed approach / new evidence | result / disposition |
| --- | --- | --- | --- | --- |
| spike 2026-11-27 | — | — | headless `claude -p` 2.1.332, probe subagent: `SubagentStop` `decision: block` made the subagent continue (foreground and background); second stop had `stop_hook_active: true`; subagent PreToolUse payloads carry `agent_id` and `agent_type`; `SubagentHandback` did not appear headless, but the what-today interactive transcript shows `PreToolUse:SubagentHandback` then `SubagentStop` | informs R11, R12, Q1 |
| test run 1 | 13 failures, 1 error of 1510: (a) 6 existing `test_comment_detection` JS/TS cases expect the line pattern (trailing `// x` not reported, `'''` and line-2 `#!` reported in `.js`); (b) existing installer tests pin 0.56.0 or a fixed migration count (`test_customization_report` e1, e2, local preservation; `test_facts_gate` update from 0.51.0 answers 6 prompts); (c) `test_remove_progress` vo8_f2 compares hook entries with 0.49.1 without the three new entries; (d) `test_subagent_release` README check looks for English words in the Korean README; (e) `test_remove_progress` vo9_x6 reads this repository's manifest; (f) `test_checkout_setup` t5 timeout | (a)–(d) test defects: tests not updated to R1 and R21; (e) evidence order: installed copy not regenerated before the run; (f) load: the test uses a 1 s timeout | (a)–(d) correction batch 1 to test-implementer; (e) main ran `installer/harness.py update . --no-commit`; (f) passed alone on the base commit and on this tree | run 2: only (f) remains. (f) also errors in a full run on base commit 75e9d8f (1418 tests, same single error), so it predates this spec and stays out of scope |
| code read 1 | two added docstrings restate the code: `_detect_comments` in `harness/git/warn_new_comments.py` (the parameter shape) and `first_stop` in `harness/hooks/subagent_comments.py` (the return values) | implementation defect against the Comment Enforcement rule; the implementer ran before the new hook was installed | correction batch 2 to implementer | both docstrings deleted; run 3: 1513 tests, only the pre-existing (f) error; the five new test modules pass alone with no skips (92 tests) |
| review R1–R4 | — | — | R1: first `SubagentHandback` of an implementer denied with the listed probe comment, subagent deleted it, second hand-back allowed; telemetry blocked true then false; records removed (settles Q1 yes; Q2 yes, the running session loaded the regenerated hooks). R2: median 0.088 s for 20 files. R3: one detector, pinned `==`, `-I`, one grammar table. R4: three entries in `.claude/settings.json`, none in `.codex/hooks.json`, Comments bullets installed, `setup-uv@v10` in the workflow | scratchpad review/r1.md–r4.md |

# Version Log
## v1
- Initial draft.
- Draft revision before approval: R22, C33 and the worktree items T7 (O4) and SC6 (O11), after the owner said worktrees were not covered.
