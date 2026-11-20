# harness

> 포트폴리오: [https://blog-steel-ten-13.vercel.app/posts/harness](https://blog-steel-ten-13.vercel.app/posts/harness)

Git 저장소에 설치하는 Claude Code용 AI 에이전트 하네스입니다. 문서 규칙, 스킬, 서브에이전트, 훅, CI 주석 검사를 함께 설치합니다. 배포 원본은 `harness/`이고, 현재 버전은 [`harness/VERSION`](harness/VERSION)에 있습니다.

> **Codex는 지원하지 않습니다.** `.codex/` 파일은 생성되지만 동작을 보장하지 않으며, 서브에이전트 제약은 Claude Code에서만 강제됩니다.

## 빠른 시작

Python 3와 Git이 필요합니다.

```bash
python3 installer/harness.py install <target> --dry-run   # 변경 예정 항목만 표시
python3 installer/harness.py install <target>
python3 installer/harness.py doctor <target>
```

| 옵션 | 효과 |
| --- | --- |
| `--dry-run` | 파일을 쓰지 않고 계획만 표시 |
| `--no-ci` | GitHub Actions 워크플로우와 라벨 생성을 건너뜀 |
| `--ask-tools` | 저장해 둔 `never` 답을 지우고 도구 설치를 다시 물음 |
| `--model sonnet\|opus` | workflow 서브에이전트의 기본 모델을 바꾸고 `.harness/config.json`에 저장 (기본 `sonnet`) |

- 이미 설치된 저장소(`.harness/manifest.json` 있음)는 `install` 대신 `update`를 씁니다.
- 언어(Python, JS/TS, Go, Rust)를 감지해 fuzzing/mutation 도구가 없으면 설치 여부를 `[y/N/never]`로 묻습니다. `never`는 `~/.harness/preferences.json`에 저장됩니다. 도구를 설치하지 않았다면 spec의 `Mutation tool:`을 `none`으로 둡니다.
- Claude Code 세션이 시작될 때 `.harness/bin/checkout_setup.py hook`이 실행됩니다. 프로젝트 manifest(`pyproject.toml`, `package.json`)에 선언된 검증 도구(`hypothesis`, `mutmut`, `fast-check`, `@stryker-mutator/core`)가 체크아웃에 없으면, lockfile이 있을 때만 백그라운드로 의존성을 설치합니다. 세션 시작은 설치를 기다리지 않습니다. 관리자와 명령은 `uv.lock`(`uv sync --frozen --inexact`), `poetry.lock`(`poetry install --no-interaction`), `pdm.lock`(`pdm install --frozen-lockfile`), `pnpm-lock.yaml`, `yarn.lock`, `bun.lock`/`bun.lockb`(각각 `install --frozen-lockfile`), `package-lock.json`(`npm ci`)입니다. lockfile과 manifest는 바꾸지 않으며, lockfile이 없으면 설치하지 않습니다. `node_modules`가 이미 있으면 `npm ci`는 그것을 지우고 다시 설치하므로 자동으로 실행하지 않고 직접 실행할 명령만 알려 줍니다(자동 설치가 실패한 경우의 재시도는 예외). 설치가 실패하면 다음 세션 시작 때 다시 시도하고, `doggy-workflow`의 phase 명령 출력에는 실행 중이거나 실패한 설치가 한 줄로 표시됩니다.
- 상태는 `python3 .harness/bin/checkout_setup.py status`로 확인합니다. `--wait 초`를 붙이면 실행 중인 설치가 끝나거나 그 시간이 지날 때까지 기다립니다. 상태와 로그는 `.harness/sessions/checkout-setup/`(git이 무시함)에 저장됩니다.
- 자동 설치는 `.harness/config.json`의 `"auto_install": false`로 끕니다(커밋하면 프로젝트의 모든 clone과 worktree에 적용). `never`로 답한 저장소도 설치하지 않습니다.
- 같은 훅이 새 clone에서 `core.hooksPath`가 비어 있고 Git hook 관리자가 없으면 `.harness/git`으로 다시 설정합니다. 이 동작은 `auto_install`과 무관합니다.
- `--model`은 `implementer`, `test-implementer`, `test-verifier`, `code-explorer`에 적용됩니다. 이후 `--model` 없이 `update`하면 저장된 값을 씁니다. `mutant-triager`는 항상 `haiku`를 씁니다. 설치된 모델과 다른 모델이 필요한 작업이면 workflow 브리프가 이유와 함께 제안합니다.
- 파일이나 스킬 이름이 충돌하면 설치를 중단하고 경로를 알려 줍니다.

## 설치되는 것

| 위치 | 역할 |
| --- | --- |
| `.harness/` | 버전별 payload, 스크립트, 소유 파일의 SHA manifest |
| `AGENTS.md`, `CLAUDE.md` | 프로젝트 정의와 관리형 문서 규칙 (`CLAUDE.md`는 `@AGENTS.md` 참조) |
| `.agents/skills/`, `.claude/skills/` | `doggy-workflow`, `project-map` |
| `.claude/agents/` | `implementer`, `test-implementer`, `test-verifier`, `mutant-triager`, `code-explorer` |
| `.claude/settings.json` | 세션·서브에이전트·도구 훅. `gh pr create`/`gh pr edit` 뒤에는 PR 설명을 5분 standup 소개 기준으로 쓰라고 상기시킴. 규칙 주입 훅(`rule_injection.py`)은 `agent-docs/`의 규칙 디렉터리에 세션 처음으로 Write/Edit/MultiEdit 하면 그 규칙 파일 본문을 컨텍스트로 추가하고, spec 알림 훅(`spec_notice.py`)은 세션 시작 때 열린 spec, 복원되지 않은 seed, 남은 서브에이전트 표시를 알림 |
| `.harness/bin/records.py` | `stale <path>`는 기록을 `stale/`로 옮기고 index 항목을 `stale.md`로 옮김, `synced-refresh <id>`는 동기화 주석의 count·code_hash·version·태그를 갱신 |
| `.harness/git/` | 커밋 전 문서 규칙 검사(동기화 주석은 태그와 `synced end: <id>` 줄 사이의 코드만 `code_hash`로 검사하며 `agent-docs/` 안의 태그는 세지 않음), 커밋 메시지의 `Request:`·`Intent:` 줄 경고 |
| `agent-docs/` | try-n-fail 기록, todo, spec, 실행 기록, 사용자가 승인한 프로젝트 사실(`facts.md`) |
| `.github/workflows/harness-comment-warning.yml` | 새 주석이 있는 PR은 `comments-approved` 라벨이 있어야 통과 (선택) |

기존 설정과의 관계:

- 기존 hook 설정에는 하네스 항목을 병합합니다.
- 기존 `AGENTS.md`는 프로젝트 정의만 남기고 원문을 `agent-docs/logs/`에 보관합니다.
- Git hook 관리자가 없으면 `core.hooksPath`를 `.harness/git`으로 설정합니다. Husky 등이 있으면 수동 연결 방법만 출력합니다.
- 새 주석은 커밋 때는 경고만 하고, PR에서는 라벨이 없으면 실패합니다.
- `Request:`·`Intent:` 줄이 없는 커밋 메시지도 커밋 때 경고만 합니다.

## 작업 흐름

기능·수정 수준의 구현과 디버깅에는 [`doggy-workflow`](harness/skills/doggy-workflow/SKILL.md)를 씁니다. 단순 문서 수정이나 이름 변경에는 쓰지 않습니다.

1. **Spec**: 메인 에이전트가 이해한 내용과 저장소에 없는 사실에 대한 질문을 제시하고, 사용자가 직접 정할 결정은 선택지와 추천 없이 묻습니다. 그 뒤 `agent-docs/specs/`에 spec을 쓰고 채팅 브리프로 승인받습니다.
   - 첫 브리프는 작업이 건드리는 코드가 지금 어떻게 동작하는지(구성 요소와 연결, 상태가 있는 곳, 실패 경로)와 그 코드에 이미 들어 있는 결정을 설명합니다. 각 결정은 얻는 것, 치르는 것, 성립하지 않게 되는 조건과 함께, 근거가 기록에 있으면 *recorded*, 코드로만 보이면 *inferred*로 표시합니다. 승인 브리프는 거기서 무엇이 바뀌는지와 각 결정을 유지하는지 다시 정하는지를 말합니다.
   - 브리프는 코드·변수명 같은 프로젝트 세부는 덜고, 결과물의 형상과 엔지니어로서 책임질 결정(무엇을 골랐고, 무엇을 포기했고, 언제 틀린 선택이 되는지)을 설명합니다. 형상을 바꾸지 않는 기본값은 spec에 남깁니다.
   - 브리프 끝에는 핵심 trade-off, 결정, 최종 형태를 묻는 퀴즈가 붙습니다. 답이 spec과 다르면 오해인지 의도 불일치인지 가려 설명하거나 spec을 고칩니다. 사용자는 건너뛸 수 있고, 질문과 답은 어디에도 저장하지 않습니다.
   - spec에는 고려한 대안(`# Alternatives`)과 아직 모르는 것(`# Open Questions`)을 적습니다.
2. **구현 + 테스트**: `implementer`와 `test-implementer`가 서로의 결과물을 보지 않고 병렬로 작업합니다.
3. **검증**: `test-verifier`가 증거를 감사하고, 메인 에이전트가 결함을 주입해 테스트가 잡는지 확인합니다. 검증 호출은 실행당(여러 세션 작업은 step당) 최대 2회입니다.
4. **보관**: 끝난 spec은 `agent-docs/spec-logs/`로 옮기고, 진행 중인 spec은 남깁니다. 보관된 spec은 수정하지 않습니다.
5. **마무리 보고**: 세션을 마칠 때마다 실제로 만들어진 형상, 작업 중 내린 결정, 잘못된 시도와 실수를 채팅으로 보고하고 퀴즈로 마칩니다. 회고는 저장하지 않습니다. 저장되는 것은 사용자가 승인한 `facts.md` 항목과 try-n-fail 기록뿐입니다.

AI 에이전트가 대부분 쓴 코드를 다시 이해해야 할 때는 [`project-map`](harness/skills/project-map/SKILL.md)을 씁니다. 프로젝트 전체나 한 영역의 구조도, 주요 경로, 상태가 있는 곳, 핵심 결정과 trade-off(기록에 근거가 있는지, 코드에서 추론했는지 포함)를 HTML 페이지 하나로 만들어 저장소 밖(세션 scratchpad)에 두고, Claude artifact로 게시할 수 있으면 게시합니다. 이어서 채팅으로 짧은 퀴즈를 냅니다. 저장소에는 아무것도 쓰지 않고, 퀴즈 답에서 저장소가 보여 주지 않는 사실이 나오면 `facts.md` 항목을 제안만 합니다.

한 세션에 끝나지 않는 작업은 spec 하나를 step으로 나눕니다. 검증 obligation이 15개 이상이거나(`.harness/config.json`의 `step_split_obligations`로 변경), 앞부분을 만들어 봐야 뒷부분이 정해지거나, 세션 밖의 일을 기다려야 하거나, 세션이 끝내지 못하고 멈췄을 때 권고합니다. 각 step은 위 2~3을 따로 통과합니다. 이 경우에만 spec에 `# Steps`와 `# Session Memory`(`## Failed Attempts & Reasons`, `## Decisions & Reasons & Alternatives`, `## Unresolved Questions & Uncertainties`)를 두어 다음 세션이 이어받고, 작업이 끝나면 spec과 함께 보관됩니다.

텔레메트리는 `~/.harness/telemetry/`에 JSONL로 기록됩니다.

## 문서 관리

에이전트는 `AGENTS.md`의 관리 블록에 따라 문서를 씁니다. 관리 블록은 규칙 본문이 아니라 `.harness/instructions/harness-block.md`를 가져오는 import 한 줄(`@.harness/instructions/harness-block.md`)이며, 버전이 바뀌어도 `AGENTS.md`는 달라지지 않습니다. 항상 읽는 규칙은 [`harness-block.md`](harness/instructions/harness-block.md)에 있습니다. hook이 위반을 잡는 try-n-fail, todo, index/stale, 동기화 주석 규칙은 같은 디렉터리의 별도 파일에 있어 해당 작업 전에 읽고, 위반하면 hook 메시지가 그 파일을 알려 줍니다.

| 문서 | 위치 | 언제 쓰나 |
| --- | --- | --- |
| 주석·docstring | 코드 | 코드로 알 수 없는 설계 제약, 외부 시스템, 보안 불변식, 특이한 구현의 이유만 |
| 사실 | `agent-docs/facts.md` | 실행 환경, 사용자의 의도와 계획처럼 저장소로는 알 수 없는 사실이 작업 중 드러났을 때. 한 줄에 사실 하나, 출처와 재확인 방법 포함. 사용자가 문구를 승인한 뒤에만 작성하고, 작업 시작 전에 읽음 |
| try-n-fail | `agent-docs/try-n-fail/` | 실패를 알아내는 데 실제 구현·실행·조사가 든 시도, 또는 사용자가 거절한 구체적 제안을 다음 작업이 반복할 수 있을 때. 초안 확인 후 작성. 먼저 읽어 두지 않고, 접근을 실행하기 직전과 첫 실패 때 `index.md`를 검색해 일치하는 기록만 읽음 |
| todo | `agent-docs/todos/` | 세션에 묶이지 않은 작업 항목. `#` 제목과 `## Next Step` 필수. 0.33.0 이전 handoff 기록은 갱신 때 동의하면 여기로 이동 |
| 동기화 주석 | `agent-docs/synced-comments/` | 같은 주석을 여러 곳에 유지할 때. 코드에 `synced id`와 버전을 태그하고 블록 끝에 `synced end: <id>`를 둠 |

- 관리 디렉터리마다 `index.md`, `stale.md`, `stale/`을 두고, 파일명은 `<16자리 hex id>-<kebab-case>.md`입니다. 낡은 문서는 지우지 않고 `stale/`로 옮깁니다.
- 커밋 전 Git hook이 파일명, index/stale 구조, 동기화 주석 메타데이터, 필수 제목을 검사합니다.
- `agent-docs/` 문서(`index.md`, `stale.md` 제외)의 frontmatter `commit`은 hook이 마지막 작성 시점의 HEAD로 채웁니다.
- 커밋 메시지에는 작업을 요청한 user 요청(`Request:`)과 의도(`Intent:`)를, PR 설명은 프로젝트를 모르는 사람에게 하는 5분 standup 소개 기준으로 씁니다.

## 갱신과 점검

```bash
python3 installer/harness.py update <target> [--dry-run] [--no-commit]
python3 installer/harness.py update <target-a> <target-b>
python3 installer/harness.py update --all
python3 installer/harness.py doctor <target>
python3 installer/harness.py import <target> --json
```

| 명령 | 동작 |
| --- | --- |
| `update` | 버전별 migration을 하나씩 확인받고 적용합니다. 사용자가 수정한 파일은 건너뛰고 보고합니다. |
| `update` 자동 커밋 | 적용이 끝나면 이번 실행이 바꾼 파일만 모아 `Update harness <이전> -> <현재>` 커밋 하나를 만듭니다. 실행 전에 이미 수정된(staged, unstaged, untracked) 후보 파일이 하나라도 있으면 실행 전에 `warning: auto-commit skipped:` 줄로 알리고, 갱신은 적용하되 커밋은 하지 않으며 커밋할 파일을 `manual review`에 나열합니다. 커밋이 실패해도 파일은 남고 종료 코드는 바뀌지 않습니다. Git hook은 그대로 실행됩니다. `install`은 커밋하지 않습니다. |
| `update --no-commit` | 경고와 커밋 없이 갱신만 합니다. |
| `update --all` | 지금까지 `install`/`update`한 저장소(`.harness-targets.json`)를 모두 갱신합니다. |
| `doctor` | manifest SHA, hook 설정, 관리 블록, Git hook 연결을 읽기 전용으로 점검합니다. |
| `import` | 설치본과 원본의 차이를 보여 줍니다. |

여러 디렉터리를 주면 하나가 실패해도 나머지를 계속 처리하고, 하나라도 실패하면 종료 코드 1을 반환합니다.

## 이 저장소에서 개발하기

`harness/`만 수정합니다. `.harness/`, `.claude/`, `.codex/`, `.agents/`는 생성 결과물이므로 직접 고치지 마세요.

```bash
python3 installer/harness.py update . --no-commit
python3 tests/run_parallel.py
```

- `tests/run_parallel.py`는 테스트를 클래스 단위(최대 8개씩)로 나눠 CPU 코어 수만큼 병렬로 실행합니다. `-j N`으로 동시 실행 수를 정하고, `python3 tests/run_parallel.py <모듈>`처럼 모듈을 지정할 수 있습니다. 직렬 실행(`python3 -m unittest discover -s tests`)도 그대로 동작합니다.
- 버전을 올리면 [`installer/harness.py`](installer/harness.py)에 버전별 migration을 추가합니다.
- skill, rule, README 문구를 바꿀 때는 `HARNESS_TEXT_TESTS=1 python3 -m unittest discover -s tests`로 실행하세요. 문구 검사는 기본으로 건너뜁니다.
- 에이전트는 `harness/agents/`, 훅은 `harness/hooks/hooks.spec.json`에서 관리하며 [`installer/generate.py`](installer/generate.py)가 생성합니다.

## 하네스 평가

평가 코드는 `evaluation/`에 있으며 설치되지 않습니다. 지금까지의 시도는 모두 중단했고, 사용법과 중단 이유는 각 문서에 있습니다.

- [`evaluation/selfcheck`](evaluation/selfcheck/README.md): 보관됨
- [`evaluation/reference_mutation`](evaluation/reference_mutation/README.md): pilot 후 중단 ([실험 기록](evaluation/reference_mutation/EXPERIMENT.md))

## 세션 로그 분석 (analytics)

하네스 텔레메트리와 Claude/Codex 세션 기록을 SQLite로 가져와 보여 주는 로컬 화면입니다. 다른 repo에는 설치되지 않습니다.

```bash
python3 -m pip install -r analytics/requirements.txt
npm ci --prefix analytics/frontend
npm run build --prefix analytics/frontend
python3 -m analytics.app   # http://127.0.0.1:8000
```

- workflow 실행별 상태와 규칙 준수 여부 (`compliant`, `noncompliant`, `partial`, `unrelated`, `excluded`)
- 토큰 사용량과 [`analytics/config.yaml`](analytics/config.yaml) 단가 기준 비용

| 환경 변수 | 기본값 |
| --- | --- |
| `ANALYTICS_HOST` / `ANALYTICS_PORT` | `127.0.0.1` / `8000` |
| `ANALYTICS_DATABASE_PATH` | `~/.harness/analytics.sqlite3` |
| `ANALYTICS_TELEMETRY_DIR` | `~/.harness/telemetry` |
| `ANALYTICS_CLAUDE_TRANSCRIPT_DIR` | `~/.claude/projects` |
| `ANALYTICS_CODEX_TRANSCRIPT_DIR` | `~/.codex/sessions` |
| `ANALYTICS_PRICE_PATH` | `analytics/config.yaml` |
| `ANALYTICS_FRONTEND_DIR` | `analytics/frontend/dist` |
