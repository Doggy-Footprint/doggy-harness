# harness

> 포트폴리오: [https://blog-steel-ten-13.vercel.app/posts/harness](https://blog-steel-ten-13.vercel.app/posts/harness)

Git 저장소에 설치하는 Claude Code용 AI 에이전트 하네스입니다. 문서 규칙, 스킬, 서브에이전트, 훅, CI 주석 검사를 함께 설치합니다. 배포 원본은 `harness/`이고, 버전은 [`harness/VERSION`](harness/VERSION)에 있습니다.

> **Codex는 지원하지 않습니다.** `.codex/` 파일은 생성되지만 동작을 보장하지 않으며, 서브에이전트 제약은 Claude Code에서만 강제됩니다.

## 설치

Python 3와 Git이 필요합니다.

```bash
python3 installer/harness.py install <target> --dry-run   # 변경 예정 항목만 표시
python3 installer/harness.py install <target>
```

| 옵션 | 효과 |
| --- | --- |
| `--dry-run` | 파일을 쓰지 않고 계획만 표시 |
| `--no-ci` | GitHub Actions 워크플로우와 라벨 생성을 건너뜀 |
| `--ask-tools` | 저장해 둔 `never` 답을 지우고 도구 설치를 다시 물음 |
| `--model sonnet\|opus` | workflow 서브에이전트의 모델 (기본 `sonnet`, `.harness/config.json`에 저장) |

- 이미 설치된 저장소(`.harness/manifest.json` 있음)에는 `install` 대신 `update`를 씁니다.
- fuzzing·mutation 도구가 없으면 감지한 언어별로 설치 여부를 `[y/N/never]`로 묻습니다. `never`는 `~/.harness/preferences.json`에 저장됩니다.
- Claude Code 세션이 시작되면 프로젝트 manifest가 선언한 검증 도구가 없을 때 lockfile이 있는 경우에만 백그라운드로 의존성을 설치하고, 새 clone의 `core.hooksPath`를 `.harness/git`으로 복원합니다. 상태는 `python3 .harness/bin/checkout_setup.py status`로 봅니다. 자동 설치는 `.harness/config.json`의 `"auto_install": false`로 끕니다.
- 파일이나 스킬 이름이 충돌하면 설치를 중단하고 경로를 알려 줍니다.

### 설치되는 것

| 위치 | 역할 |
| --- | --- |
| `.harness/` | payload, 스크립트, 소유 파일의 SHA manifest |
| `AGENTS.md`, `CLAUDE.md` | 프로젝트 정의와 관리 블록 (기존 `AGENTS.md`는 프로젝트 정의만 남기고 원문을 `agent-docs/logs/`에 보관) |
| `.agents/skills/`, `.claude/skills/` | `doggy-workflow`, `project-map` |
| `.claude/agents/` | `implementer`, `test-implementer`, `test-verifier`, `mutant-triager`, `code-explorer` |
| `.claude/settings.json` | 세션·서브에이전트·도구 훅 (기존 설정에는 병합) |
| `.harness/git/` | 커밋 전 문서 규칙 검사와 커밋 메시지 경고. Git hook 관리자가 없으면 `core.hooksPath`를 여기로 설정 |
| `agent-docs/` | try-n-fail, todo, spec, 사용자가 승인한 사실(`facts.md`) |
| `.github/workflows/` | 새 주석이 있는 PR은 `comments-approved` 라벨이 있어야 통과 (선택) |

## 작업 흐름

기능·수정 수준의 구현과 디버깅에는 [`doggy-workflow`](harness/skills/doggy-workflow/SKILL.md)를 씁니다. 사용자와 이해·결정·승인 브리프로 spec을 확정하고, `implementer`와 `test-implementer`가 서로의 결과물을 보지 않고 구현과 테스트를 하며, `test-verifier`와 결함 주입으로 검증한 뒤 채팅으로 마무리 보고를 합니다. 규칙의 전부는 스킬 파일에 있습니다.

코드를 다시 이해해야 할 때는 [`project-map`](harness/skills/project-map/SKILL.md)으로 구조와 핵심 결정을 HTML 한 페이지와 퀴즈로 받습니다.

## 문서 관리

에이전트는 `AGENTS.md`의 관리 블록에 따라 문서를 씁니다. 관리 블록은 `@.harness/instructions/harness-block.md`를 가져오는 import 한 줄입니다. 항상 읽는 규칙은 [`harness-block.md`](harness/instructions/harness-block.md)에 있습니다. try-n-fail, todo, index/stale, 동기화 주석 규칙은 같은 디렉터리의 별도 파일에 있고, 해당 작업 전에 읽습니다. `.harness/bin/records.py`는 기록을 `stale/`로 옮기고(`stale <path>`) 동기화 주석을 갱신합니다(`synced-refresh <id>`). 커밋 전 Git hook이 위반을 검사하고 메시지로 해당 규칙 파일을 알려 줍니다.

## 저장소별 커스터마이즈

하네스 파일(`.harness/` 아래 설치본)은 고치지 않습니다. 저장소마다 다른 내용은 아래 위치에 **파일을 추가**해서 얹습니다. install, update, migration은 이 파일들을 쓰거나 지우거나 옮기지 않습니다.

| 위치 | 용도 | 예 |
| --- | --- | --- |
| `AGENTS.md`의 관리 블록 바깥 | 저장소의 상시 규칙과 프로젝트 정의 | "커밋 전에 `make lint`를 실행한다" |
| `.harness/local/git/<hook 이름>` | 해당 Git hook에서 실행할 스크립트 (실행 권한 필요) | `pre-commit`에서 `make lint` 실행 |
| `.harness/local/doggy-workflow/<phase>.md` | 해당 단계의 규칙 뒤에 붙는 프로젝트 규칙 (`brief`, `draft`, `approve`, `implement_test`, `verify`, `amend`, `step`, `close`, `resume`) | `verify.md`에 "통합 테스트도 실행한다" |
| `.harness/local/agents/<agent 이름>.md` | 서브에이전트가 시작할 때 받는 추가 지침 | `implementer.md`에 "새 모듈에는 타입 힌트를 붙인다" |
| `.harness/local/hooks/**` | 저장소가 `.claude/settings.json`에 직접 등록하는 Claude Code hook 스크립트 | `lint.py` |

`.harness/config.json`은 `docs_root`, `exclude_dirs`, `auto_install`, `agent_model`, `step_split_obligations`만 읽습니다. 잘못된 파일이면 hook은 기본값을 씁니다.

**우선순위**: 커스터마이즈가 하네스 규칙과 어긋나면 커스터마이즈를 따릅니다. 대신 사용자가 어긋남을 알아볼 수 있도록, 커스터마이즈 파일을 쓸 때와 세션이 시작될 때마다(사용자가 확인하기 전까지) 에이전트가 사용자에게 알립니다. 확인은 사용자가 동의한 뒤에만 기록하며, 기록은 커밋되는 `.harness/customization-review.json`에 남습니다.

```bash
python3 .harness/bin/customization.py status           # 커스터마이즈 상태와 문제
python3 .harness/bin/customization.py confirm PATH...  # 사용자가 확인한 항목 기록
```

**Git hook 순서**: `.harness/git/<이름>`이 하네스 자체 검사(`pre-commit`, `commit-msg`) → `.harness/local/git/<이름>` → 클론 전용 hook 순으로 같은 인자와 stdin으로 실행합니다. 앞 단계가 실패하면 그 상태로 끝납니다. `.harness/git`이 hooks 경로인 저장소에서만 동작하며, hook 관리자를 쓰면 거기서 `.harness/git/<이름> "$@"`를 호출해야 합니다.

## 갱신과 점검

```bash
python3 installer/harness.py update <target> [--dry-run] [--no-commit]
python3 installer/harness.py update --all
python3 installer/harness.py doctor <target>
python3 installer/harness.py import <target> [--json]
```

| 명령 | 동작 |
| --- | --- |
| `update` | 버전별 migration을 하나씩 확인받아 적용하고, 바꾼 파일만 커밋 하나로 묶습니다(`--no-commit`이면 커밋 없이 갱신만). 끝에 `== customization ==` 구역으로 확인할 커스터마이즈를 알립니다. |
| `update --all` | 지금까지 `install`/`update`한 저장소(`.harness-targets.json`)를 모두 갱신합니다. |
| `doctor` | manifest, hook 설정, 관리 블록, Git hook 연결, 커스터마이즈 상태를 읽기 전용으로 점검합니다. |
| `import` | 설치본과 원본의 차이와 커스터마이즈 상태를 보여 줍니다. |

**update가 멈추는 경우**: 쓰기 전에 검사하고(`--dry-run`도 같음), 하나라도 걸리면 파일 이름과 할 일을 `== conflict ==`에 적고 아무것도 쓰지 않습니다.

- 하네스 파일을 제자리에서 고친 경우: 변경을 커스터마이즈로 옮기고, 그 파일을 지운 뒤 다시 실행하면 원본이 복원됩니다.
- 저장소 자체 skill이 하네스 skill과 같은 이름으로 `.claude/skills/<이름>`을 차지한 경우: 저장소 skill의 이름을 바꿉니다.
- `.harness/config.json`이 JSON 객체가 아닌 경우(`install`도 멈춤).
- 하네스가 제공하는 Git hook 이름의 파일이 이미 `.harness/git/<이름>`에 있는 경우: `.harness/local/git/<이름>`으로 `git mv`합니다.

## 이 저장소에서 개발하기

`harness/`만 수정합니다. `.harness/`, `.claude/`, `.codex/`, `.agents/`는 생성 결과물이며, `.harness/local/`만 직접 고치는 예외입니다.

```bash
python3 installer/harness.py update . --no-commit   # 수정을 설치본에 반영
python3 tests/run_parallel.py                        # 테스트
```

- 버전을 올릴 때마다 [`installer/harness.py`](installer/harness.py)에 그 버전의 migration을 추가합니다.
- 커스터마이즈 지점은 [`harness/customization.json`](harness/customization.json)이 선언합니다. 지점·이름(hook, phase, agent)·config 키를 지우거나 이름을 바꾸면, `retired` 항목(`path`, `version`, `note`)으로 덮고 그 `version`에 migration이 있을 때까지 `installer/customization_check.py`(이 저장소의 `.harness/local/git/pre-commit`이 실행)가 커밋을 막습니다. 지점이 비교하는 파일을 바꾸면 사용하는 저장소가 update 뒤에 검토해야 한다는 경고만 냅니다.
- 문구 검사는 기본으로 건너뜁니다. skill, rule, README를 바꿀 때는 `HARNESS_TEXT_TESTS=1 python3 tests/run_parallel.py`로 실행합니다.
- 에이전트는 `harness/agents/`, 훅은 `harness/hooks/hooks.spec.json`에서 관리하며 [`installer/generate.py`](installer/generate.py)가 생성합니다.

## 평가와 분석

설치되지 않는 로컬 도구입니다.

- `evaluation/`: 하네스 평가 시도 모음. 사용법과 중단 이유는 각 디렉터리의 README에 있습니다 ([`selfcheck`](evaluation/selfcheck/README.md), [`reference_mutation`](evaluation/reference_mutation/README.md)).
- `analytics/`: 텔레메트리(`~/.harness/telemetry/`)와 세션 기록을 SQLite로 가져와 보여 주는 화면. 설정은 [`analytics/config.yaml`](analytics/config.yaml)과 `ANALYTICS_*` 환경 변수입니다.

```bash
python3 -m pip install -r analytics/requirements.txt
npm ci --prefix analytics/frontend && npm run build --prefix analytics/frontend
python3 -m analytics.app   # http://127.0.0.1:8000
```
