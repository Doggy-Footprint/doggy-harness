---
version: 3
run_id: 53bc1ac3853d43ac
status: complete
base_commit: 4a0980791249eaea54a6201007c19ecc98fb87fa
max_verifier_invocations: 2
commit: 4a0980791249eaea54a6201007c19ecc98fb87fa
---

# User Intent
| id | stakeholder | intention | observable goal |
| --- | --- | --- | --- |
| UI1 | project owner | Remove the failed session-progress approach and the continue-on skill in one release (0.50.0) | No progress module, hook, CLI, rule, skill, record, or hook registration remains in the source, the installed copy, or an updated repository |
| UI2 | project owner | Keep rule injection and the SessionStart spec notice, each in its own hook | After 0.50.0 both behave as in 0.49.1 and live in two separate hook files |
| UI3 | project owner | Updating never leaves a hook entry that runs a deleted script | `.claude/settings.json` and `.codex/hooks.json` contain no harness command whose script is missing |
| UI4 | project owner | Principles 2 and 3 stay in place but are marked as slated for replacement and not binding | `harness-block.md` keeps both principle texts and carries one sentence saying so |

# Scope
In scope: deleting the progress implementation and continue-on; two new hooks (rule injection, spec notice); `merge_hooks_dict` dropping harness groups of events the new hook set no longer uses; a 0.50.0 migration deleting progress records, progress session state, the continue-on symlink, and progress gitignore lines; removing progress from git hooks, `doc_commit.py`, `telemetry_hook.py`, `config.py`, `records.py`, `verify_rules.py`, `spec_lifecycle.py`, the installer, instructions, the workflow-approach skill, and README; deleting this repository's progress records via `update`; tests.
Out of scope: a replacement for cross-session task transmission (todo `55581096177d4b3b`); editing the text of principles 2 and 3; analytics handling of `end handoff` / `end limit`; the telemetry `end --status` and `verifier --result` choices; new spec frontmatter fields.

# Paths
Implementation: harness/, installer/, README.md, .harness/, .claude/, .agents/, .codex/, .gitignore, agent-docs/progress/, agent-docs/progress-logs/
Tests: tests/
Test command: python3 tests/run_parallel.py
Review evidence: R1 — main greps the post-update repository for removed names (QR2 procedure) and reads the edited workflow-approach steps 1 and 9, harness-block.md, try-n-fail.md, index-and-staleness.md, and README for remaining progress or continue-on wording; output recorded in the execution ledger
Fuzzing: none — hook inputs are small JSON payloads covered by enumerated malformed-payload cases
Mutation tool: none — no mutation tool is installed for this repository

# Signatures
harness/hooks/rule_injection.py — Claude Code PreToolUse hook (matcher Write|Edit|MultiEdit); reads the hook payload JSON on stdin; prints `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": <text>}}` or nothing; always exits 0
harness/hooks/spec_notice.py — Claude Code SessionStart hook; prints `spec_state.print_notice()` output or nothing; always exits 0
installer/harness.py: merge_hooks_dict(existing: dict, new_hooks: dict) -> dict — `existing` is a whole settings/hooks file object (may hold keys other than `hooks`); `new_hooks` has the rendered shape `{"hooks": {<event>: [<group>, ...]}}`
installer/harness.py: migrate_remove_progress(target: Path, dry_run: bool) -> list[str], registered in MIGRATIONS as (parse_version("0.50.0"), <description>, migrate_remove_progress)
harness/VERSION: 0.50.0

# Functional Requirements
| id | requirement | priority | source |
| --- | --- | --- | --- |
| FR1 | `harness/lib/progress.py`, `harness/hooks/progress_hook.py`, `harness/bin/progress.py`, `harness/git/sync_progress.py`, `harness/instructions/progress.md`, and `harness/skills/continue-on/` do not exist; no harness or installer Python module imports `progress` | must | UI1 |
| FR2 | `hooks.spec.json` holds no `progress_hook.py` entry; it registers `rule_injection.py` on PreToolUse matcher `Write|Edit|MultiEdit` and `spec_notice.py` on SessionStart, both `targets: ["claude"]`; all other entries are unchanged | must | UI1, UI2 |
| FR3 | Rule injection: for a Write/Edit/MultiEdit whose `tool_input.file_path` (absolute, or relative to the repo root) lies at least one directory below the docs root, inside a git work tree, with a `session_id`, the hook adds each mapped rule file's text the first time in that session: the mapping uses the first-level directory under the docs root (a nested file such as `todos/stale/x.md` maps as `todos/`, and the header names `<docs>/todos/`); `try-n-fail/` → `try-n-fail.md` then `index-and-staleness.md`; `todos/` → `todos.md` then `index-and-staleness.md`; `synced-comments/` → `synced-comments.md` (these three regardless of whether the directory holds `index.md`); `specs/`, `spec-logs/` → none; any other directory → `index-and-staleness.md` when it holds `index.md`, otherwise none. A relative `file_path` resolves against the repository root whatever the process or payload cwd. Each section is `harness: rule text of .harness/instructions/<name> for writing in <docs-relative-to-repo dir>/:` + blank line + file text; sections join with a blank line. A rule already injected in the session is skipped; when every mapped rule was injected, nothing prints. The per-session record lives under `.harness/sessions/rules-<safe session id>.d/` | must | UI2 |
| FR4 | Spec notice: on SessionStart the hook prints exactly what `spec_state.print_notice()` prints (open specs, unrestored seed, leftover subagent markers) and nothing when there is nothing to report | must | UI2 |
| FR5 | `merge_hooks_dict` removes every harness group (a group whose command contains `/.harness/`) from every event in the existing file, including events absent from the new hook set, then adds the new groups; an event left with no groups is deleted; non-harness groups and non-hook keys are kept in their order | must | UI3 |
| FR6 | The 0.50.0 migration deletes `progress/` and `progress-logs/` under `agent-docs/` and under the configured docs root (when it differs) with all their content (tracked, untracked, modified), `.harness/sessions/progress-*.json`, `.harness/sessions/progress-*.d/`, `.harness/sessions/installer-run.json`, and the `.claude/skills/continue-on` symlink when it points to `../../.agents/skills/continue-on` (otherwise it is left and the plan holds the line `.claude/skills/continue-on is not the harness symlink; left in place`); it removes the lines `.harness/sessions/progress-*.json`, `.harness/sessions/progress-*.d/`, `.harness/sessions/installer-run.json` from `.gitignore`; it returns plan lines naming each of these; with dry run it changes nothing | must | UI1, user 2026-11-15 |
| FR7 | Update from 0.49.1 (and from older versions through the migration chain) ends with no progress or continue-on files; the auto-commit includes the deletions of tracked files under the two progress directories; owned files dropped from the manifest are deleted as today | must | UI1, UI3 |
| FR8 | Fresh install creates no `agent-docs/progress/` or `agent-docs/progress-logs/`; `GITIGNORE_LINES` holds `.harness/sessions/rules-*.d/` and none of the three progress lines; install and update both leave `.harness/sessions/rules-*.d/` in `.gitignore` | must | UI1 |
| FR9 | pre-commit no longer runs `sync_progress.py`; post-merge has no progress-move block and still delegates to a local hook; `verify_rules.py` has no progress checks and no progress directory exemption; `doc_commit.py` stamps every `.md` under the docs root except `index.md` and `stale.md`; `telemetry_hook.py` emits no `progress_write`; `config.py` defines no progress paths; `records.py` exempts no progress directories; the installer writes no installer-run record and imports no progress module | must | UI1 |
| FR10 | Text: `harness-block.md` keeps principles 2 and 3 verbatim and adds after the principle list the sentence "Principles 2 and 3 will be replaced by a new approach; until then, following them is not required."; its Rule Files table has no `progress.md` row; `try-n-fail.md` names no progress as a candidate source; `index-and-staleness.md` names no progress directories; workflow-approach step 1 contains `Resume it only when the user asks;` and no `/continue-on`; step 9 contains ``For verifier-budget exhaustion, set status `limit`, archive with `--status limit`, then emit end limit.`` and ``For a nonterminal stop, keep the spec `active` and emit end handoff without archiving.``, and its report list does not contain `progress path`; `spec_lifecycle.py` messages do not mention `/continue-on` or progress; README drops progress and continue-on | must | UI1, UI4, user 2026-11-15 |
| FR11 | This repository is updated with `python3 installer/harness.py update . --no-commit`: VERSION and manifest say 0.50.0 and `agent-docs/progress/`, `agent-docs/progress-logs/` no longer exist | must | UI1, AGENTS.md |

# Errors
- Rule-injection payload is empty, not JSON, not an object, lacks `session_id`, lacks `tool_input.file_path`, or names a path outside the docs root — no output, exit 0, no marker written.
- Rule injection outside a git work tree — no output, exit 0.
- Marker directory not writable — the rule text is still printed, exit 0, no traceback (repeats on later calls).
- A mapped rule file is missing or unreadable — that section is skipped, others print, exit 0.
- `spec_state` raises (broken spec directory or config) — spec notice prints nothing, exit 0, no traceback.
- Migration on a repository without progress directories, state files, symlink, or gitignore lines — no error; plan lines still describe the step; nothing else changes.
- `.claude/skills/continue-on` exists but is not the harness symlink — left in place, plan line says so.

# Cases
| id | level | input / state | expected result |
| --- | --- | --- | --- |
| C1 | normal | First Write to `agent-docs/todos/<hex>-x.md` in session S | Output additionalContext = todos.md section then index-and-staleness.md section |
| C2 | normal | Second Write in `agent-docs/todos/` in session S | No output |
| C3 | normal | After C1, first Write in `agent-docs/try-n-fail/` in S | Only try-n-fail.md section (index rule already injected) |
| C4 | normal | Write in `agent-docs/synced-comments/` | synced-comments.md section only |
| C5 | edge | Write in `agent-docs/specs/`, `agent-docs/spec-logs/`, `agent-docs/facts/` (no index.md), or directly in `agent-docs/` | No output |
| C6 | edge | Write in another docs subdirectory holding `index.md` | index-and-staleness.md section only |
| C7 | edge | Same Write in a different session S2 | Sections printed again for S2 |
| C8 | edge | `docs_root` configured to another directory | Mapping applies under that root |
| C9 | edge | Relative `file_path` | Same result as absolute |
| C10 | error | Malformed payloads from Errors | No output, exit 0 |
| C11 | error | Marker directory not writable | Text printed, exit 0, no traceback |
| C12 | error | Not a git work tree | No output, exit 0 |
| C13 | normal | SessionStart with an open spec in `agent-docs/specs/` | Output equals `spec_state.notice_lines()` joined by newlines |
| C14 | boundary | SessionStart with no specs, seed, or markers | No output, exit 0 |
| C15 | error | SessionStart with spec_state failing | No output, exit 0 |
| C16 | normal | Existing settings with harness groups under UserPromptSubmit, PreCompact, Stop and a user group under Stop; new hooks lack those events | UserPromptSubmit and PreCompact keys gone; Stop holds only the user group |
| C17 | normal | Existing settings with user groups and harness groups on an event the new set keeps | User groups kept first in order, harness groups replaced |
| C18 | normal | Update a 0.49.1 install holding tracked progress and progress-logs records, progress state files, installer-run.json, the continue-on symlink, progress gitignore lines | All removed; settings and codex hooks have no command whose `.harness/...` script is missing; auto-commit contains the deletions; working tree clean afterwards |
| C19 | boundary | Same as C18 with `--dry-run` | Nothing changes; plan lines printed for 0.50.0 |
| C20 | edge | `.claude/skills/continue-on` is a user directory | Left in place, reported |
| C21 | edge | Update from 0.32.0 or older through all migrations | Ends with no progress directories |
| C22 | normal | Fresh install | No progress directories; gitignore has `.harness/sessions/rules-*.d/` |
| C23 | normal | Commit in an installed repo after 0.50.0 | pre-commit passes without progress; commit stamp written to a new todo |
| C24 | normal | Merge with post-merge hook installed | No progress handling; local post-merge hook still runs |
| C25 | normal | Text of harness-block.md, workflow-approach, try-n-fail.md, index-and-staleness.md, README | Matches FR10 |
| C27 | edge | Write to `agent-docs/todos/x.md` where `todos/` has no `index.md`; nested `agent-docs/todos/stale/x.md` | todos.md + index sections; header names `agent-docs/todos/` |
| C28 | edge | Hook process and payload cwd are a subdirectory; relative `agent-docs/todos/x.md` | Same as C1 |
| C29 | error | A mapped rule file is unreadable (a directory in its place, or mode 000) | That section skipped, others print, exit 0; restored file injects on a later call |
| C30 | normal | Update of a 0.49.1 install whose `.harness/config.json` sets a custom docs_root holding `progress/` and `progress-logs/` | Both removed under the custom root too |
| C31 | normal | A record placed in a former progress directory (e.g. `agent-docs/progress/x.md`) at commit time | pre-commit treats it exactly like the same record in an arbitrary other directory (e.g. `agent-docs/notes/x.md`): same exit status and messages modulo the directory name |
| C26 | none | boundary of record counts — none: deletion is all-or-nothing, count has no boundary | — |

# Quality Applicability
| ISO/IEC 25010:2023 characteristic | applicable | rationale |
| --- | --- | --- |
| Functional suitability | yes | FR1–FR11 |
| Performance efficiency | no | Removing hooks only reduces work; no new loops over data |
| Compatibility | yes | Existing installs update from 0.49.1 and older; settings files coexist with user hooks |
| Interaction capability | no | No user interface change beyond text |
| Reliability | yes | A crashing or exit-2 hook blocks Claude Code tool calls or prompts |
| Security | no | The removed secret scan covered only progress records, which no longer exist; no new input surface |
| Maintainability | yes | Removed names must not linger in code or docs |
| Flexibility | no | No new configuration |
| Safety | no | No physical or human-safety effect |

# Quality Requirements
| id | characteristic / subcharacteristic | target and context | measure method / inputs / unit | threshold and direction | evidence: automated, review, mutation | source |
| --- | --- | --- | --- | --- | --- | --- |
| QR1 | Reliability / fault tolerance | rule_injection.py and spec_notice.py on the C10, C11, C12, C15 inputs | run each hook as a subprocess; count runs with exit ≠ 0 or `Traceback` on stderr | 0, lower is better | automated; mutation | UI2 |
| QR2 | Maintainability / modifiability | repository after `update . --no-commit` | `grep -rnE "progress_hook|sync_progress|bin/progress\.py|continue-on([^-]|$)|instructions/progress\.md|agent-docs/progress" harness .harness .claude .agents .codex README.md AGENTS.md` lines; plus Python files under harness/ and installer/ importing a module named `progress` | 0 lines, 0 importers | automated (import check) + review R1 (grep) | UI1 |
| QR3 | Compatibility / co-existence | `.claude/settings.json` and `.codex/hooks.json` after updating a 0.49.1 install that also holds one user hook on Stop | count harness commands whose `.harness/<path>.py` does not exist, and user groups lost | 0 and 0 | automated | UI3 |

# Verification Obligations
| id | parent requirement/Case ids | variant and target surface | test layer and selection policy | ISO/IEC/IEEE 29119-4 technique | coverage items | coverage target | observation and expected result | evidence procedure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VO1 | FR3, C1–C9 | rule_injection.py subprocess with JSON payloads in a temp installed repo | integration; every directory class | equivalence partitioning | P1 try-n-fail, P2 todos, P3 synced-comments, P4 specs, P5 spec-logs, P6 dir without index, P7 other dir with index, P8 docs root itself, P9 outside docs root, P10 custom docs_root, P11 relative path (incl. subdirectory cwd, C28), P12 named dir without index (C27), P13 nested file (C27) | 100% | stdout JSON additionalContext equals expected section text in order, or empty | Test command |
| VO2 | FR3, C1–C3, C7 | rule_injection.py across calls in one/two sessions | integration | state transition | T1 none→first rule injected, T2 injected→repeat silent, T3 partial (index done)→only new rule, T4 other session independent | 100% | outputs per call as in Cases | Test command |
| VO3 | FR3, Errors, C10–C12, QR1 | rule_injection.py with malformed inputs | integration | error guessing | E1 empty stdin, E2 invalid JSON, E3 JSON array, E4 no session_id, E5 no tool_input, E6 non-git dir, E7 read-only marker dir, E8 missing rule file, E9 unreadable rule file (C29) | none — experience-based | exit 0, no Traceback, output as in Errors | Test command |
| VO4 | FR4, C13–C15, QR1 | spec_notice.py subprocess | integration | equivalence partitioning | N1 open spec, N2 nothing to report, N3 spec_state failure | 100% | stdout equals notice lines / empty; exit 0 | Test command |
| VO5 | FR5, C16, C17 | merge_hooks_dict called directly | unit | decision table | rules: (harness group?, event in new set?, user group present?) all 8 combinations | 100% | resulting dict per rule | Test command |
| VO6 | FR6, FR7, C18–C21, QR3 | `harness.py update` on a temp repo installed at 0.49.1 (and legacy versions) | end-to-end | scenario | S1 full 0.49.1 state with commit, S2 dry run, S3 user continue-on dir, S4 legacy chain, S5 repo without any progress artifacts, S6 custom docs_root (C30), S7 rules-markers gitignore line present after update (FR8) | 100% | filesystem, gitignore, settings, codex hooks, git log/status as in Cases | Test command |
| VO7 | FR8, C22 | fresh `harness.py install` | end-to-end | equivalence partitioning | I1 fresh install | 100% | no progress dirs; gitignore lines | Test command |
| VO8 | FR1, FR2, FR9, C23, C24, QR2 | installed repo files and git hooks | integration | equivalence partitioning | F1 removed files absent, F2 hooks.spec entries, F3 pre-commit commit succeeds, F4 commit stamp on new record, F5 post-merge delegates, F6 no progress_write telemetry, F7 no `progress` importers, F8 former-progress record treated like any other directory by pre-commit (C31), F10 `records.py stale` in former progress dirs behaves like any other directory (mutation M9), F9 installed `config.load_paths()` result has no `progress` / `progress_logs` attribute and installed pre-commit text has no `sync_progress` | 100% | as in requirements | Test command |
| VO9 | FR10, FR11, C25 | text of shipped instruction, skill, README files and this repo state | integration (text) + review | syntax | X1 principle sentence present and principles 2–3 unchanged, X2 Rule Files table without progress row, X3 workflow-approach steps 1 and 9, X4 try-n-fail.md, X5 index-and-staleness.md, X6 VERSION 0.50.0, X7 exact step 1 / step 9 strings from FR10 (replaces X3) | 100% | exact strings present/absent | Test command + R1 |

# Assumptions and Defaults
| id | decision | evidence and uncertainty | brief v<n> — approved / vetoed → <answer> / user answer / user decision (main: <own option>) / fact <file name> |
| --- | --- | --- | --- |
| A1 | Migration deletes all progress records, including untracked and modified ones | personal project, no other users | fact a0d6cd9a40c71e37-consumers-personal-project-no-other-users.md; user answer 2026-11-15 |
| A2 | `status: limit` keeps its meaning; no `limit`/`handoff` frontmatter fields | user 2026-11-15 | user answer |
| A3 | Rule injection and spec notice in separate files `rule_injection.py` and `spec_notice.py` | user asked for separate management | user answer (file names: brief v1 — approved) |
| A4 | Stale hooks are fixed in `merge_hooks_dict`, not by migration-specific cleanup | generalizes to later event removals; `installer/harness.py:1528` loops only over new events | brief v1 — approved |
| A5 | Rule markers move to `.harness/sessions/rules-<session>.d/`; running sessions see each rule once more after update | old markers live in deleted `progress-<session>.d/` | brief v1 — approved |
| A6 | Principle note wording as in FR10, placed after the principle list | user asked for a note, not a rewrite | brief v1 — approved |
| A7 | Old migration descriptions in the installer that mention progress stay as history | they describe past versions | brief v1 — approved |
| A8 | Telemetry `end --status handoff|limit` and analytics stay unchanged | out of scope | brief v1 — approved |

# Traceability
| requirement id | Case ids | obligation ids | evidence procedure |
| --- | --- | --- | --- |
| FR1 | C18 | VO8 | Test command |
| FR2 | C1, C13 | VO8 | Test command |
| FR3 | C1–C12, C27–C29 | VO1, VO2, VO3 | Test command |
| FR4 | C13–C15 | VO4 | Test command |
| FR5 | C16, C17 | VO5 | Test command |
| FR6 | C18–C20, C30 | VO6 | Test command |
| FR7 | C18, C21 | VO6 | Test command |
| FR8 | C22 | VO7 | Test command |
| FR9 | C23, C24, C31 | VO8 | Test command |
| FR10 | C25 | VO9 | Test command + R1 |
| FR11 | — | VO9 | Test command + R1 |
| QR1 | C10–C12, C15 | VO3, VO4 | Test command |
| QR2 | — | VO8, VO9 | Test command + R1 |
| QR3 | C18 | VO6 | Test command |

# Workflow Control
| item | value |
| --- | --- |
| correction batches used | 3 |
| verifier invocations | 2 |
| open finding ids | none |

Audit state (one entry per obligation; retain prior decisions in the execution ledger):
| obligation id | spec version | evidence references and revision | accepted / open / invalidated / pending | rationale and mutation outcome | dependencies and reopening evidence |
| --- | --- | --- | --- | --- | --- |
| VO1 | 3 | tests/test_rule_injection.py test_vo1_* | accepted | verifier 2; P1–P10 accepted by verifier 1; P11 open (EG2); P12, P13 new | rule_injection.py path resolution |
| VO2 | 2 | tests/test_rule_injection.py test_vo2_t1..t4 | accepted | verifier 1 | marker layout |
| VO3 | 3 | tests/test_rule_injection.py test_vo3_* | accepted | verifier 2; E1–E8 accepted; E9 new (EG3) | rule file read handling |
| VO4 | 2 | tests/test_remove_progress.py test_vo4_n1..n3 | accepted | verifier 1 | spec_state notice |
| VO5 | 2 | tests/test_remove_progress.py TestMergeHooksDict | accepted | verifier 1 | merge_hooks_dict |
| VO6 | 3 | tests/test_remove_progress.py TestUpdateFrom0491, TestLegacyChainAndClean | accepted | verifier 2; S1, S2, S4, S5 accepted; S3 reopened for the exact left-in-place line (SC3); S6, S7 new | migrate_remove_progress |
| VO7 | 2 | tests/test_remove_progress.py test_vo7_i1 | accepted | verifier 1 | install |
| VO8 | 3 | tests/test_remove_progress.py test_vo8_*, test_doc_records, test_telemetry | accepted | verifier 2; F1–F7 accepted; F8, F9 new (EG1) | verify_rules, records, config, pre-commit |
| VO9 | 3 | tests/test_remove_progress.py test_vo9_* + R1 | accepted | verifier 2; X1, X2, X4–X6 accepted; X3 replaced by X7 (SC4); R1 in ledger row 4 | SKILL.md text |
| (other spec) | 3 | tests/test_synced_blocks.py quoted-tag tests | accepted | EG4: differentiating setup removed with the progress directory | synced scan |

Execution ledger (append attempts; preserve failed approaches):
| attempt | finding / failure signature | cause hypothesis | changed approach / new evidence | result / disposition |
| --- | --- | --- | --- | --- |
| 1 | Test command (with /Users/hwansu/tools/harness/.venv/bin on PATH for hypothesis/pytest): 966 tests, 5 failures, 10 errors | — | first run | see rows 1a–1d |
| 1a | VO5 tests: KeyError 'hooks' in merge_hooks_dict | spec gap: Signatures did not state new_hooks shape; tests passed a bare event map | v2 states the rendered `{"hooks": {...}}` shape (existing convention) | test defect; correction to tests |
| 1b | VO6 S1: `.agents/skills/continue-on` still exists after update (empty directory; also `.harness/skills/continue-on` in this repo) | owned-file deletion removes SKILL.md but not the emptied directory | remove directories emptied by deleted owned files | implementation defect |
| 1c | VO6 S5: plan text lacks `.claude/skills/continue-on` when no symlink exists | plan line only emitted when the symlink is present; FR6 requires naming each item | always name the symlink step in the plan | implementation defect |
| 1d | test_installer test_every_skill_is_installed_with_a_claude_symlink asserts len(SKILLS) > 1 | obsolete precondition; only workflow-approach remains | assert len(SKILLS) >= 1 | test defect |
| 2 | After batch 1: Test command 966 tests OK (skipped=99) | — | rerun | pass |
| 4 | R1 grep `progress_hook|sync_progress|bin/progress\.py|continue-on([^-]|$)|instructions/progress\.md|agent-docs/progress` over harness .harness .claude .agents .codex README.md AGENTS.md | — | main ran it after batch 1, excluding the temporary no-op stub .harness/hooks/progress_hook.py kept for the live session and deleted before commit | 0 lines; diffs of try-n-fail.md, index-and-staleness.md, README, steps 1 and 9 read and match FR10; principle 2 keeps "session progress" by FR10 |
| 5 | Verifier 1 retry: EG1 FR9 clauses unevidenced; EG2 relative path vs cwd; EG3 unreadable rule file; EG4 test_synced_blocks quoted-tag setup weakened; SC1 custom docs_root; SC2 FR3 named/nested dirs; SC3 left-in-place wording; SC4 step 1/9 strings | spec underspecified (SC1–SC4), tests missing items (EG1–EG4) | v3 amends FR3, FR6, FR8, FR10, adds C27–C31 and items P12, P13, E9, S6, S7, F8, F9, X7; EG4 restores a non-progress docs directory for the quoted tags; advisory A3 checked by grep: no mask user outside the removed progress lib | correction batch 2 (tests) |
| 6 | Batch 2 done: Test command (HARNESS_TEXT_TESTS=1) 975 tests OK (skipped=94) | — | rerun | pass |
| 7 | Confirming mutations (one at a time, seed backup/restore, module test runs): M1 marker ignored → killed (T2, T3, T4, E8); M2 marker keyed by directory → killed (E8, E9, P10, P11); M3 relative path vs process cwd → killed (P11 subdir); M4 catch only FileNotFoundError → killed (E9); M5 merge loops only new events → killed (C16, r-table, S1); M6 migration ignores docs_root → killed (S6); M7 migration acts in dry run → killed (S2, S3); M8 spec_notice import moved outside try → survived; M9 records.py re-exempts progress dirs → survived; M10 post-merge drops delegation → killed (F5) | M8: equivalent — the `__main__` guard catches the import error, so exit 0 and no traceback still hold, which is all FR4/QR1 require; M9: evidence gap, FR9 records.py clause unobserved (F8 covers pre-commit only) | M8 accepted as equivalent; M9 → batch 3 adds F10 (records.py stale differential) | strongest classes chosen: injection state (M1, M2), path resolution (M3), error handling (M4, M8), stale-hook merge (M5), migration scope and dry run (M6, M7), removed exemption (M9), git hook delegation (M10) |
| 8 | Batch 3: F10 added; M9 re-run → killed by test_vo8_f10_*; Test command 975+ tests OK (skipped=94) | — | rerun | pass |
| 9 | Verifier 2: pass, no blocking finding, M8 equivalent disposition confirmed; R1 grep re-run after batch 3: 0 lines | — | — | complete |
| 3 | HARNESS_LEGACY_MIGRATION_TESTS=1: 35 failures (`auto-commit skipped: already modified`, EOFError at prompts) | pre-existing: base commit 4a09807 fails the same 35 legacy tests under the same flag | compared against a base worktree run | not caused by this run; the two new 0.32.0 C21 tests fail the same way; C21 evidence is test_vo6_s4_c21_update_from_0400_* (default run, passes) |

# Version Log
## v1
- Initial draft from the conversation of 2026-11-15.
## v2
- Contract-only: Signatures state the argument shapes of merge_hooks_dict (finding 1a).
## v3
- Contract-only, from verifier 1 (SC1–SC4): FR3 states first-level mapping, unconditional named dirs, repo-root relative paths; FR6 covers a configured docs_root and the exact left-in-place line; FR8 requires the rules gitignore line after update; FR10 names exact step 1/9 strings; Cases C27–C31 and new coverage items. Each restates approved intent (UI1, user 2026-11-15) or 0.49.1 behavior.

# Retrospective
## 2026-11-15
| observation | evidence | how to re-check |
| --- | --- | --- |
| With HARNESS_LEGACY_MIGRATION_TESTS=1, 35 legacy-migration tests fail, and the same 35 fail at base commit 4a09807 | a worktree at 4a09807 run with the same flag gave `FAILED (failures=35, skipped=10)` with the same test names | check out 4a09807 in a temporary worktree and run `HARNESS_LEGACY_MIGRATION_TESTS=1 python3 tests/run_parallel.py` |
| A running Claude Code session keeps the hook configuration it loaded at start; after `update` deleted `.harness/hooks/progress_hook.py`, that session's hooks failed with "can't open file" | hook error in this session right after the in-repo update; a one-line no-op stub at that path silenced it | in a running session, delete a script registered as a hook and watch the next tool call |
| `python3 tests/run_parallel.py <module>.<Class>` runs no tests and exits 0 | first M5 and M8 mutation runs reported exit 0 with 0 failures; rerunning with the module name killed M5 | `python3 tests/run_parallel.py test_remove_progress.TestMergeHooksDict; echo $?` and compare the "Ran N tests" line |
