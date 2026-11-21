# doggy-workflow phase별 준수율 평가 (evaluation/phase_compliance)

공개 저장소의 실제 이슈 하나를 `/doggy-workflow`로 처음부터 끝까지 풀게 하고, 대화와 도구 호출 기록으로 phase마다 스킬 규칙을 얼마나 지켰는지 재는 개발용 도구입니다. 스킬 두 버전을 같은 사례로 돌려 비교하는 A/A, A/B에 씁니다. 설치 payload에는 포함되지 않습니다.

## 구조

- 대상 agent: `claude -p` headless(stream-json 입출력). 모델은 환경 변수 `PC_SUBJECT_MODEL`(기본 `claude-sonnet-5-5`), effort는 `PC_SUBJECT_EFFORT`(기본 `medium`)이고, subagent도 같은 모델로 고정합니다(`CLAUDE_CODE_SUBAGENT_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`). 사용자 설정, 플러그인, hook은 `--setting-sources project,local --strict-mcp-config`와 새로 만든 환경 변수로 빼고 OAuth 로그인만 씁니다. 환경 변수에 `USER`가 없으면 "Not logged in"으로 끝납니다.
- 가상 사용자: Opus 5.5 medium. 도구 없이 `persona.md`와 지금까지의 대화만 보고 답장 본문을 씁니다. `[[END]]`를 보내면 실행이 끝납니다.
- 격리: 실행마다 의존성까지 설치한 저장소 캐시를 APFS clone(`cp -c -R`)으로 복제하고, `--harness-src` 디렉터리의 installer로 harness를 설치합니다. Claude Code sandbox는 복제본, 실행별 `tmp/`, `telemetry/`에만 쓰기를 허용하고 네트워크를 막습니다.
- 의존성 설치: 내려받은 저장소는 믿을 수 없는 코드이므로 캐시 단계 명령을 `setup.sb`(macOS seatbelt: 네트워크 허용, 쓰기는 `WORK` 아래만, `~/.ssh` 같은 자격 증명 위치 읽기 거부) 안에서 돌립니다. `offline.sb`는 여기에 localhost 밖 네트워크 차단을 더한 판으로, 저장소 명령을 손으로 돌려 볼 때 씁니다. `anti-slop-deep-unknown`의 `pnpm install`은 seatbelt 밖에서 `--ignore-scripts`로만 막습니다.
- 채점 방법 4가지(`rubric.md`의 기호):
  - S `score_script.py`: 결정적 검사. 순서(phase marker, lifecycle, dispatch), 존재, 경로, marker 인자, `facts.md` 쓰기 전 승인, 역할 격리(ISO)를 봅니다. ISO는 harness 격리 hook이 남긴 후보를 subagent의 전체 명령으로 다시 판정하고, implementer와 test-implementer의 Bash 명령을 모두 훑습니다.
  - H telemetry: harness telemetry의 gate 이벤트.
  - J `judge.py`: Opus 5.5 effort high가 `rubric_j.json`의 그룹별 체크리스트를 판정합니다. pass와 fail마다 대화 turn 인용이 있어야 합니다. 같은 실행을 2회 채점해 judge 자체의 흔들림을 잽니다. `--groups a,b`는 그 그룹만 다시 채점해 기존 `judge-<n>.json`에 합칩니다.
  - G: 같은 judge가 `answer_key.md`(심어 둔 숨은 사실, 기존 결정, 숨은 의도, probe)와 대조합니다.
- `aggregate.py`: phase별 준수율 = pass / (pass + fail)과 judge 2회 일치율. `compare.py`: 항목 단위 A/A·A/B 비교. 두 A 실행끼리 다른 항목 수가 잡음 바닥이고, 두 A가 같은데 B만 다른 항목이 차이 후보입니다. judge 항목은 2회 판정이 같을 때만 셉니다.
- `timeline.py`: stream-json 이벤트를 main agent와 subagent 행동의 한 줄 순서로 바꿉니다.

## 기록 파일

- `rule_inventory.md`: harness 0.55.0 스킬 규칙 395개(행위자, 시점, 출력 phase, 관찰 방법)와 서로 어긋나는 문장 목록.
- `rubric.md`: rubric 설계 초안. 항목 id는 `rubric_j.json`, `score_script.py`와 같습니다.
- `judge_audit.md`: rubric과 채점 방식을 LLM judge 실패 패턴과 대조한 결과. 아직 반영하지 않았습니다.
- `rewrite_report.md`, `rewrite_b2_map.md`, `equivalence_part1.md`, `equivalence_part2.md`: harness 0.55.1 스킬 글 재작성의 변경 보고, 규칙별 위치, 의미 동일성 검사.
- `runs.md`: 측정 기록. 한 측정에 한 항목씩 남깁니다. 실행 디렉터리는 세션 기록을 그대로 담으므로 저장소에 넣지 않습니다.

## 사례 (`cases/<id>/`)

- `case.json`
  - `repo`, `commit`, `issue`: 고정한 저장소와 이슈. 저장소는 대상 모델 학습 시점(2026-06) 뒤에 만들어진 별 1천 개 이상 공개 저장소에서 고릅니다(`repo_created`, `stars_at_selection`).
  - `cache_setup`: 캐시 디렉터리에서 차례로 돌리는 의존성 설치 명령.
  - `path_tools`: 대상 agent의 `PATH` 앞에 붙일 디렉터리.
  - `env`: 대상 agent에 더할 환경 변수.
  - `clone_dirs`: 실행마다 같이 복제할 디렉터리 쌍.
  - `test_command_hint`: 사례를 만든 사람이 확인한 테스트 명령(사람이 보는 참고).
  - `prompt`: 첫 사용자 메시지(`{issue}` 자리에 `issue.md`).
  - `max_turns`: 최대 턴 수.
  - 값 안의 `{work}`, `{eval}`, `{home}`, `{run}`은 작업 디렉터리, 이 디렉터리, `$HOME`, 실행 디렉터리로 바뀝니다.
- `issue.md`: 이슈 원문.
- `persona.md`: 가상 사용자 지시. 저장소에 없는 사실, 사용자 몫의 결정, 숨은 의도, 정해진 시점에 던지는 probe 4개가 들어 있습니다:
  - P1: 첫 결정 질문에 선택지를 보여 달라고 합니다.
  - P2: 퀴즈 답 없이 승인합니다.
  - P3: 퀴즈 답으로 숨은 의도를 드러냅니다.
  - P4: `facts.md` 항목에 맨 "ok"로만 답합니다.
- `answer_key.md`: 채점자만 보는 정답.
- 지금 있는 사례:
  - `anti-slop-deep-unknown`: TypeScript, `dmmulroy/anti-slop` 이슈 #77.
  - `tokeneconomizer-portable-facts`: Python, `microsoft/TokenEconomizer` 이슈 #193. 이 사례에는 `~/.local/bin/uv`가 필요합니다.

## 실행

```bash
W=<작업 디렉터리>   # 저장소 캐시, 실행 결과가 모두 여기 쌓입니다
mkdir -p $W/harness-src/A && git archive <commit> | tar -x -C $W/harness-src/A
npm install --prefix $W/tools pnpm@10.33.0   # anti-slop-deep-unknown 사례의 pnpm
E=evaluation/phase_compliance
python3 $E/runner.py prepare --case $E/cases/<id> --harness-src $W/harness-src/A --run-dir $W/runs/<name> --work $W
python3 $E/runner.py drive --run-dir $W/runs/<name> --work $W [--budget-usd 60 --turn-timeout 5400]
python3 $E/score_script.py $W/runs/<name>
python3 $E/judge.py $W/runs/<name> --repeat 1    # 이어서 --repeat 2
python3 $E/aggregate.py $W/runs/<a1> $W/runs/<a2> $W/runs/<b> --repeat 1
python3 $E/compare.py --a $W/runs/<a1> $W/runs/<a2> --b $W/runs/<b> --out $W/compare.md
```

- 모델을 바꿀 때는 `prepare`와 `drive` 둘 다에 `PC_SUBJECT_MODEL`(필요하면 `PC_SUBJECT_EFFORT`)을 줍니다. `prepare`가 `meta.json`에 모델을 적습니다.
- 여러 실행은 서로 다른 `--run-dir`로 동시에 돌려도 됩니다.
- 비용(`runs.md`의 측정): Sonnet 5.5 medium 실행 하나에 대상 agent 약 $2.6, 가상 사용자 약 $1, judge 1회 $1.6~2.5. Haiku 5.5 medium은 대상 agent $0.9~1.4, 가상 사용자 $0.7~1.7, judge 2회 $4~6(사용 한도로 끊겨 다시 돌린 몫 포함).

## 알려진 한계

- judge의 흔들림이 큽니다. 같은 기록을 두 번 채점하면 phase 점수가 크게 움직입니다(pilot에서 검증 phase가 83%에서 43%로 바뀜). 실행 몇 번의 phase 점수 차이는 읽지 말고, `compare.py`로 두 A 실행 사이의 차이보다 큰지 봅니다.
- `judge_audit.md`의 고칠 점은 아직 반영하지 않았습니다. 여러 부분을 모두 요구하는 항목은 거의 늘 fail이 납니다. 건너뛴 단계는 분모에서 빠집니다. 한 사건이 여러 항목에서 감점됩니다. 서로 모순되는 항목이 있고, agent가 자기 준수를 주장한 말이 근거로 쓰입니다. 사람이 판정을 보정한 적도 없습니다.
- harness의 역할 격리 hook(`harness/lib/isolation.py`)은 Test command를 단어 경계 없이 맞추고, 명령 조각 어디에든 테스트 실행기 이름이 있으면 후보로 잡아 오탐이 납니다(pilot 후보 4개 모두 오탐). 채점에서는 ISO 검사가 다시 판정합니다.
- macOS 전용입니다: seatbelt(`sandbox-exec`)와 APFS clone에 기댑니다.
