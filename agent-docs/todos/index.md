File: ea9e5b18dd5975cb-dashboard-skill-partial-use.md
Summary: From issue #7, dashboard partial-use classification should also count harness Skill invocations; not started
Related Files: analytics/app.py, analytics/transcripts.py, analytics/usage.py
Related Symbols: _classify_sessions, _has_harness_evidence, _collect_turn
---
File: 7c41e9b2d05af386-test-implementer-isolation-violation.md
Summary: Evaluation pending: whether the 0.31.0 dispatch wording stopped main from telling test-implementer to run tests, measured by 0.32.0 dispatch_run_instruction telemetry against the 0.28.0 pilot (3/3)
Related Files: harness/skills/doggy-workflow/SKILL.md, harness/lib/isolation.py, harness/hooks/telemetry_hook.py, analytics/app.py
Related Symbols: detect, _dispatch, _harness_hacking, migrate_isolation_telemetry
---
File: d706c17a1d003208-speed-up-test-suite.md
Summary: Full test suite takes about 457 s single-core for 1219 tests; git hook commits are only ~10% of it; try per-file parallel runs, then measure hook payload subprocesses
Related Files: tests/test_installer.py, tests/test_progress.py, tests/test_hook_owned_progress.py, tests/test_doc_records.py, tests/test_message_nudge.py, tests/legacy_migrations.py
Related Symbols: run_installer, skip_legacy_update, DocRecordsTestCase.commit_all
---
File: 92b5be21b6ef9b80-multi-person-telemetry-digest.md
Summary: Planned future work to combine several people's telemetry and digest it; collection method and questions not decided; not started
Related Files: analytics/importer.py, analytics/app.py, harness/lib/telemetry.py
Related Symbols: import_pending, emit
---
File: c9b24d7c9344d59c-brief-dialogue-eval-facts-md.md
Summary: evaluation/brief_facts dialogue grading still assumes one file per fact under agent-docs/facts/ found by grep; align seeding and fact criteria with facts.md and re-measure the 0.51.0 skill; not started
Related Files: evaluation/brief_facts/run_dialogue.py, evaluation/brief_facts/grade_dialogue.py, evaluation/brief_facts/dialogue_grader.md, evaluation/brief_facts/README.md, evaluation/brief_facts/cases/mail-backfill-facts.json, harness/skills/doggy-workflow/SKILL.md
Related Symbols: copy_written, file_checks, FACT_NAME, FACT_KEYS
---
File: 44ec20b03e6a0185-defect-correction-telemetry.md
Summary: Telemetry should record errors corrected by test-verifier findings (test vs implementation defect) and by mutations; marker design and the meaning of mutation-corrected not decided; not started
Related Files: harness/bin/workflow_marker.py, harness/lib/telemetry.py, harness/skills/doggy-workflow/SKILL.md, analytics/importer.py
Related Symbols: verifier_result, verification_result, workflow_phase
---
File: 31b266665f55f0b4-zero-kill-test-check.md
Summary: Owner proposed an LLM check of tests that kill zero mutants, to report removal candidates and bound test count; measure-first vs rule-first not chosen; not started
Related Files: harness/skills/doggy-workflow/phases/workflow-6-triage.md, harness/skills/doggy-workflow/phases/verification-mutation-tool.md, harness/agents/mutant-triager.md, harness/agents/test-verifier.md, harness/bin/seed.py
Related Symbols: mutant-triager, seed
---
File: 8f0d4c2a6b1e9a37-share-node-modules-across-worktrees.md
Summary: Owner asked whether a local worktree can reuse the main checkout node_modules instead of an 811 MB copy per worktree; split from the checkout-setup spec; symlink behavior of Stryker and vitest not checked; not started
Related Files: installer/verification_tools.py, agent-docs/spec-logs/37f43a7fb2bc2bcf-checkout-setup-at-session-start.md
Related Symbols: checkout_setup, LANGUAGES
