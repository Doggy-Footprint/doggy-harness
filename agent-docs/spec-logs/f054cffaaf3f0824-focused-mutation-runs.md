---
version: 1
run_id: f054cffaaf3f0824
status: complete
base_commit: d1bf17ddab0037590d1d8f0d4b1e69ad69eefad0
max_verifier_invocations: 2
---

# User Intent
| id | stakeholder | intention | observable goal |
| --- | --- | --- | --- |
| I1 | project owner | Hand mutations in the Triage and mutate step take less wall-clock time, in this repository and in every repository that installs the harness | Each hand mutation runs only the tests that hold its intended assertion first; the full Test command runs only for a mutation those tests do not detect |
| I2 | project owner | A slow Test command is diagnosed from measurements before anyone adds workers | When a Test command run exceeds two minutes, main records its slowest single tests and proposes splitting them in the closing report |

# Scope
In scope: the doggy-workflow rule text for running hand mutations (focused run first, full Test command for undetected mutations), the rule text for diagnosing a slow Test command and reporting it in the closing report, the release bump to 0.58.0 with its migration notice, and the installed copy of the harness in this repository.
Out of scope: running mutations in parallel copies of the working tree (rejected by the user after measurement: three concurrent focused runs took 69 s against 32 s for one, at most 1.4x); changing seed.py; changing how the declared mutation tool runs; changing this repository's test runner or tests for speed (both attempts were measured without gain and reverted); splitting the test-implementer or lowering subagent effort.

# Paths
Implementation: harness/skills/doggy-workflow/phases/workflow-6-triage.md, harness/skills/doggy-workflow/phases/workflow-4-reconcile.md, harness/skills/doggy-workflow/phases/closing-report.md, harness/VERSION, installer/harness.py, .harness/, .agents/skills/doggy-workflow/
Tests: tests/
Test command: HARNESS_TEXT_TESTS=1 uv run --python 3.12 --with pytest --with hypothesis python tests/run_parallel.py
Review evidence: RV1 — main records, in the execution ledger of this run's Triage and mutate step, the wall-clock time of each hand mutation's focused run and of one full Test command run.
Fuzzing: none — the change is rule text and a version table; no parser or input surface.
Mutation tool: none

# Signatures
S1 — workflow-6-triage.md, sub-step 2 of the mutation list, replaced in full by: "2. Inject the violating behavior and run the focused run with a finite timeout suited to its expected runtime: the Test command narrowed to the tests that hold the intended assertion, with the Test command's environment and options kept. When the focused run passes, run the full Test command before recording the mutation as undetected. When the Test command cannot be narrowed, run it whole."
S2 — workflow-4-reconcile.md, appended as the last sentences of item 4: "When a Test command run takes longer than two minutes, record its wall-clock time and its slowest single tests in the execution ledger. The slowest single test bounds the run, and more workers can make it slower when tests contend for processes or the file system, so measure before adding workers. Propose splitting the slowest tests, with the measurements, in the closing report; do not change the test runner or tests outside the spec's paths for it."
S3 — closing-report.md, in the *Numbers* bullet, after "mutation, fuzz, and mutation-tool outcomes,": " the longest Test command run's wall-clock time and, when it took longer than two minutes, its slowest single tests and the proposal to speed it up,"
S4 — harness/VERSION is `0.58.0`; installer/harness.py MIGRATIONS ends with an entry for 0.58.0 whose summary is "hand mutations run a focused run of the tests holding the intended assertion first; a Test command slower than two minutes is diagnosed and reported" and whose migration function returns notes ending with "no data is migrated".

# Functional Requirements
| id | requirement | priority | source |
| --- | --- | --- | --- |
| R1 | The Triage and mutate rule tells main to run, for each hand mutation, the focused run defined in S1 before any full Test command run, and to run the full Test command only when the focused run passes | must | user, 2026-11-27 (proposal 1) |
| R2 | The rule keeps "one mutation at a time", the seed backup and restore sub-steps, and the sentence "failure rejects a finding only when the intended assertion detects the violation" unchanged | must | brief v1; inherited rule |
| R3 | The rule falls back to the whole Test command when it cannot be narrowed (S1 last sentence) | must | brief v1 — approved |
| R4 | The Reconcile rule carries S2 verbatim | must | user, 2026-11-27 (proposal 3, revised after measurement) |
| R5 | The closing report's *Numbers* bullet carries S3 verbatim | must | brief v1 — approved |
| R6 | The release is 0.58.0 with the S4 migration entry; `harness.py update` from 0.57.0 announces 0.58.0 | must | project convention (each skill change ships a version and migration notice) |
| R7 | The phase command prints S1 in the `verify` phase, S2 in the `implement_test` phase, and S3 in the `close` phase, from the installed skill | must | SKILL.md phase table |
| R8 | This repository's installed copy (.harness/, .agents/skills/doggy-workflow/) matches the source after `python3 installer/harness.py update .` | must | project convention |

# Errors
none — the change adds rule text; no code path gains a failure mode. A missing or reworded phrase is caught by the text tests (O1–O3), not signalled at runtime.

# Cases
| id | level | input / state | expected result |
| --- | --- | --- | --- |
| C1 | normal | `phase --phase verify` on an installed repository with a plain spec | output contains S1 sub-step 2 verbatim and still contains "one mutation at a time" and the seed backup and restore sub-steps |
| C2 | normal | `phase --phase implement_test` | output contains S2 verbatim |
| C3 | normal | `phase --phase close` | output's *Numbers* bullet contains S3 verbatim |
| C4 | boundary | the installed skill's whole text | the old sub-step 2 sentence "Inject the violating behavior and run the Test command with a finite timeout suited to its expected runtime." no longer appears; "failure rejects a finding only when the intended assertion detects the violation" appears once |
| C5 | normal | `harness.py update` of a repository installed at 0.57.0 | announces 0.58.0 with the S4 summary and "no data is migrated"; the manifest version is 0.58.0 |
| C6 | edge | fresh `harness.py install` | installed VERSION is 0.58.0 and the installed skill files equal the source files byte for byte |
| C7 | error | none — no runtime failure path (see Errors) | none |

# Quality Applicability
| ISO/IEC 25010:2023 characteristic | applicable | rationale |
| --- | --- | --- |
| Functional suitability | yes | the rule text must state the focused-run order and the slow-run diagnosis exactly |
| Performance efficiency | yes | the purpose is less wall-clock time for hand mutations |
| Compatibility | yes | installed repositories update from 0.57.0; existing specs need no new field |
| Interaction capability | no | no user interface; the closing report wording is covered by functional suitability |
| Reliability | no | no runtime component changes |
| Security | no | no boundary, input, or secret changes |
| Maintainability | yes | the text is guarded by automated text tests so a later edit cannot drop it silently |
| Flexibility | yes | the rule must apply to any project's Test command, including ones that cannot be narrowed |
| Safety | no | no physical or data-loss effect |

# Quality Requirements
| id | characteristic / subcharacteristic | target and context | measure method / inputs / unit | threshold and direction | evidence: automated, review, mutation | source |
| --- | --- | --- | --- | --- | --- | --- |
| QR1 | Performance efficiency / time behaviour | this run's hand mutations on this repository, on the owner's Mac | wall-clock seconds of each focused run against one full Test command run, from RV1 | every focused run takes less time than the full Test command run | review RV1 | user, 2026-11-27 |
| QR2 | Compatibility / co-existence | update of a 0.57.0 install | O4 | update succeeds and announces 0.58.0 | automated O4 | project convention |
| QR3 | Maintainability / modifiability | the source and installed skill | O1–O3, O5 | each signature phrase asserted by at least one test | automated | brief v1 — approved |
| QR4 | Flexibility / adaptability | a Test command that cannot be narrowed | O1 coverage item P3 | the fallback sentence is present | automated O1 | brief v1 — approved |

# Verification Obligations
| id | parent requirement/Case ids | variant and target surface | test layer and selection policy | ISO/IEC/IEEE 29119-4 technique | coverage items | coverage target | observation and expected result | evidence procedure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| O1 | R1, R3, C1, QR4 | `phase --phase verify` output of an installed repository | integration; each listed phrase | syntax testing | P1 "run the focused run with a finite timeout suited to its expected runtime", P2 "When the focused run passes, run the full Test command before recording the mutation as undetected.", P3 "When the Test command cannot be narrowed, run it whole.", P4 "the Test command narrowed to the tests that hold the intended assertion, with the Test command's environment and options kept" | 100% | each phrase appears in the printed output | automated |
| O2 | R2, C1, C4 | installed skill whole text and `verify` output | integration; each listed item | equivalence partitioning (kept text / removed text) | K1 "one mutation at a time" present, K2 seed backup sub-step 1 present, K3 seed restore sub-step 3 present, K4 "failure rejects a finding only when the intended assertion detects the violation" present exactly once, X1 old sub-step 2 sentence absent | 100% | kept items present, removed item absent | automated |
| O3 | R4, R5, C2, C3 | `implement_test` and `close` phase outputs | integration; each phrase | syntax testing | Q1 S2 sentence 1, Q2 S2 sentence 2, Q3 S2 sentence 3, N1 S3 phrase inside the *Numbers* bullet | 100% | each phrase appears in the named phase output; N1 appears in the line that starts the *Numbers* bullet | automated |
| O4 | R6, C5, C6, QR2 | `harness.py update` from 0.57.0 and fresh install | integration; both transitions | state transition | T1 0.57.0 → 0.58.0 update announces the S4 summary and "no data is migrated", T2 fresh install writes VERSION 0.58.0, T3 MIGRATIONS last entry is 0.58.0 | 100% | announced versions and manifest version as stated | automated |
| O5 | R7, R8, C6 | installed copy in this repository and a fresh install | integration; the three edited phase files | equivalence partitioning | E1 workflow-6-triage.md, E2 workflow-4-reconcile.md, E3 closing-report.md: installed file equals source file | 100% | byte equality | automated |
| O6 | QR1 | this run's hand mutations | review; every hand mutation of this run | experience-based (error guessing) | G1 a focused run that silently runs no test, G2 a focused run slower than the full run | none — experience-based | RV1 times recorded; each focused run reports a nonzero test count and is faster than the full run | review RV1 |

# Assumptions and Defaults
| id | decision | evidence and uncertainty | brief v<n> — approved / vetoed → <answer> / user answer / user decision (main: <own option>) / facts.md: <first words of the entry> |
| --- | --- | --- | --- |
| A1 | Parallel mutation copies are out of scope | three concurrent focused runs 69 s vs 32 s alone, single run at 10 workers 24 s; suite bound by OS process and file-system throughput (sys 402–438 s per full run) | user decision (main: drop) |
| A2 | The runner change and the slow-test split are reverted | full suite 253–273 s after vs 260–282 s before | user decision (main: revert both) |
| A3 | Undetected focused-run mutations get one full Test command run | user accepted proposal 1 as worded ("살아남은 변이만 전체 suite") | user answer |
| A4 | No new spec field for the focused command; main derives it per mutation from the Test command and records it in the ledger | a field would add a line to every spec; the Test command already names the runner | brief v1 — approved |
| A5 | Slow-run threshold is two minutes | today's other projects run in 5–10 s; this repository's full run is about 4 min | brief v1 — approved |
| A6 | A slow Test command is proposed in the closing report, not changed in the run | Implementer principle "Keep changes within assigned paths"; today's two runner changes did not help, so a measured proposal precedes any change | brief v1 — approved |
| A7 | Release 0.58.0 with a migration notice that migrates no data | every prior skill change shipped a version and notice (installer MIGRATIONS) | brief v1 — approved |
| A8 | Text obligations at 100% coverage of listed phrases; installed roles keep their models | the phrases are the whole contract | brief v1 — approved |
| A9 | Hand mutations of this run already use the focused-run order | user: "이번부터 적용해서 빨리 진행해보자" | user answer |

# Alternatives
| decision id | option not taken | what it gains and what it costs | reversal condition: the state of the world in which it wins |
| --- | --- | --- | --- |
| A1 | run each mutation in its own worktree copy, several at once | gains up to 1.4x here; costs copy creation, dependency installs per copy, and shared-resource collisions | a machine or suite where concurrent runs scale near-linearly (CPU-bound tests) and focused runs still take minutes |
| A3 | stop at the focused run; never run the full Test command for mutations | saves one full run per undetected mutation; loses whether another test catches it | undetected mutations become common enough that full runs dominate the step again |
| A4 | a `Focused test command:` line in the spec's Paths | the user approves how narrowing works; costs a line in every spec and a format change | main narrows wrongly in practice (a focused run that misses the intended assertion) |
| A6 | main changes the test runner during the run | faster adoption; costs scope creep and unmeasured changes, as today's reverted attempt showed | the project states that main may change its test infrastructure inside any spec |

# Open Questions
none

# Completion Questions
| id | question | expected answer | what it tests: trade-off / engineer call (decision id) / final shape | built by: step id, or `all` | asked: no / closing <YYYY-MM-DD> | valid / invalid v<n> — <reason> |
| --- | --- | --- | --- | --- | --- | --- |
| CQ1 | A hand mutation in a project is detected by its intended assertion in the focused run. What runs next for that mutation, and what would differ if the focused run had passed? | nothing more for it: it is restored and the next one starts; had it passed, the full Test command would run once before it is recorded as undetected | final shape | all | closing 2026-11-27 | valid |
| CQ2 | What does the workflow give up by not running mutations in parallel copies, and on what kind of machine or suite would that choice be wrong? | at most about 1.4x on this Mac; it would be wrong where concurrent runs scale near-linearly, such as CPU-bound tests, while focused runs still take minutes | trade-off | all | closing 2026-11-27 | valid |
| CQ3 | If a project's Test command is one opaque script that cannot select tests, what happens to its mutations? | each runs the whole Test command, as before | engineer call (S1 fallback) | all | no | valid |
| CQ4 | A Test command in another project takes five minutes. What does main do during the run, and what does the user see? | records the wall-clock time and slowest single tests in the ledger, changes nothing outside the paths, and the closing report proposes splitting the slowest tests with the measurements | engineer call (A6) | all | closing 2026-11-27 | valid |

# Traceability
| requirement id | Case ids | obligation ids | evidence procedure |
| --- | --- | --- | --- |
| R1 | C1 | O1 | automated |
| R2 | C1, C4 | O2 | automated |
| R3 | C1 | O1 | automated |
| R4 | C2 | O3 | automated |
| R5 | C3 | O3 | automated |
| R6 | C5, C6 | O4 | automated |
| R7 | C1, C2, C3 | O1, O3 | automated |
| R8 | C6 | O5 | automated |
| QR1 | — | O6 | review RV1 |

# Workflow Control
| item | value |
| --- | --- |
| correction batches used | 1 |
| verifier invocations | 1 |
| open finding ids | none |

Audit state (one entry per obligation; retain prior decisions in the execution ledger):
| obligation id | spec version | evidence references and revision | accepted / open / invalidated / pending | rationale and mutation outcome | dependencies and reopening evidence |
| --- | --- | --- | --- | --- | --- |
| O1 | 1 | tests/test_focused_mutation_rules.py verify_prints_* (5 tests) | accepted | accepted by verifier 1; M2, M3, M4 detected by the intended P-tests | none |
| O2 | 1 | verify_keeps_*, *_old_whole_run_sub_step_*, rejection_sentence_* (9 tests) | accepted | accepted by verifier 1; M1, M5, M6 detected; ADV-1 advisory | none |
| O3 | 1 | implement_test_prints_* (3), close_numbers_bullet_* (batch 1 helper fix) | accepted | accepted by verifier 1; M7, M8, M9 detected; ADV-3 advisory | none |
| O4 | 1 | update_from_0570_*, fresh_install_writes_version_0580, source_version_file_is_0580, migrations_end_with_* | accepted | accepted by verifier 1; M10, M11 detected; ADV-2 advisory | none |
| O5 | 1 | this_repository_installed_copies_*, a_fresh_install_equals_* | accepted | accepted by verifier 1; M12 detected | none |
| O6 | 1 | RV1 in execution ledger attempt 3 | accepted | accepted by main: 12 focused runs 1.6–2.2 s, 24 tests each, vs full runs 210 s and 212 s | none |

Execution ledger (append attempts; preserve failed approaches):
| attempt | finding / failure signature | cause hypothesis | changed approach / new evidence | result / disposition |
| --- | --- | --- | --- | --- |
| 0 | before the spec: runner packing by recorded durations, then splitting the two combinatorial hook tests | full suite bound by its slowest tests | measured: 260–282 s before, 273 s and 230 s (20 workers) after packing, 253–255 s after the split; slowest units fell 212 s → 72 s | no gain; suite bound by OS throughput (sys 402–438 s); both reverted (A2) |
| 1 | Test command run 1 (210 s): 5 installed-copy comparisons fail; O3 N1 test finds 2 lines containing `*Numbers*` | installed copy refreshed only after the run started; test selects every line mentioning *Numbers* instead of the bullet's line | rerun after update; test-implementer selects the line starting with "- *Numbers*" | focused rerun of the 4 failing modules: 126 tests OK in 17 s; full run 2 (212 s): all pass except test_checkout_setup T5 timeout test |
| 2 | full run 2: T5 timeout test errors under full-suite load | pre-existing, load-sensitive: it errored the same way on base_commit d1bf17d (clean tree, first measurement) and in run 51bad3dbe1e6c5f1; this run changed only version pins in that file | ran it alone twice: OK both | pre-existing, out of scope; not blocking |
| 3 | hand mutations M1–M12 (focused run `HARNESS_TEXT_TESTS=1 uv run -q --python 3.12 --with pytest --with hypothesis python tests/run_parallel.py test_focused_mutation_rules`) | RV1 / QR1 | focused-first order of S1 applied in this run | 12/12 detected by the intended assertions in the focused run (no full run needed); focused 1.6–2.2 s each, 24 tests reported each, 22 s total; comparator full Test command 210 s / 212 s; seed status none and file checksums unchanged after restore |
| 4 | verifier 1: pass, advisory ADV-1 (K1 not anchored to the mutation list), ADV-2 (summary not tied to the `migration 0.58.0:` line), ADV-3 (S2 sentence order not pinned) | optional strengthening | none required | advisory, left open |

# Version Log
## v1
- Initial draft from the understanding round and two measurements (A1, A2).
