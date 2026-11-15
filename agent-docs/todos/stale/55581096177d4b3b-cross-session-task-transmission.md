---
commit: 4a0980791249eaea54a6201007c19ecc98fb87fa
---

# Cross-session task transmission

## Goal
Carry an unfinished task's state from one Claude Code session to a later one.

## User Request
- "최근 (2026, 11) 커뮤티니 의견과 연구 결과를 바탕으로 방향성을 정할 것" (project owner, 2026-11-15)

## Observation
- On 2026-11-15 the project owner stated that the progress-based approach (`agent-docs/progress/`, `agent-docs/progress-logs/`, `harness/hooks/progress_hook.py`, the `continue-on` skill) failed and asked for it to be removed.
- The removed implementation stays readable in git history at commit 4a0980791249eaea54a6201007c19ecc98fb87fa.

## Next Step
- Survey community opinions and research results published around 2026-11 on carrying agent task state across sessions, report them to the project owner, and agree on a direction before writing a spec.

## Related
- Implementation removed after commit 4a0980791249eaea54a6201007c19ecc98fb87fa: harness/lib/progress.py, harness/hooks/progress_hook.py, harness/bin/progress.py, harness/git/sync_progress.py, harness/instructions/progress.md, harness/skills/continue-on/SKILL.md
