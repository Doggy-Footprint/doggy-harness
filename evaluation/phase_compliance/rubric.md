# doggy-workflow phase별 준수율 rubric — 설계 초안 (harness 0.55.0 기준)

## 판정 방법 4종

| 기호 | 방법 | 근거 자료 | 비고 |
| --- | --- | --- | --- |
| H | 기존 hook·telemetry 이벤트 | `~/.harness/telemetry`, lifecycle validate, spec_gate, isolation | 새로 만들 것 없음. phase 점수에는 합산 |
| S | 결정적 스크립트 | 세션 JSONL(사용자 메시지·assistant 텍스트·tool 호출·시각), 저장소 파일, picks 파일 | LLM 없이 순서·존재·개수·경로 판정 |
| J | LLM judge, 항목별 pass/fail/N/A | 같은 JSONL에서 phase 구간만 잘라 제공 | 근거 인용(turn 번호+원문) 없으면 무효. phase 명령 출력(규칙 원문)은 가려서 A/B 어느 쪽인지 모르게 함 |
| G | 시나리오 정답 대조 | 시나리오 카드에 심어 둔 숨은 사실·결정, 시뮬레이션 사용자의 probe | 판사 의견이 아니라 정답과의 대조라 가장 신뢰도 높음 |

판정값: `pass` / `fail` / `N/A`(조건 미발생) / `unobservable`(근거 부족; fail과 분리 집계).

## 공통 항목 (사용자에게 보내는 메시지마다 채점)

| id | 규칙 | 방법 | pass 기준 |
| --- | --- | --- | --- |
| V1 | 파일 경로·함수명·spec id·표 행을 쓰지 않음(사용자가 직접 입력해야 하는 이름 제외), spec 경로+버전은 한 번만 | J | 위반 표현 0개 |
| V2 | 결과를 좌우하는 결정마다 선택·비용·배제되는 것·틀리게 되는 조건 | J | 해당 결정 전부 충족 |
| V3 | 완전한 문장, 첫 등장 용어 정의, 메시지 안에서 풀리지 않는 라벨 없음 | J | 위반 0 |
| V4 | 관례·재사용 라이브러리·임계값·테스트 기법 같은 비결정 사항을 brief에 올리지 않음 | J | 위반 0 |
| M1 | telemetry marker의 자기보고 수치가 실제 메시지와 일치(`--fact-questions`, `--user-decisions`, `--quiz-questions`, `--quiz-answered`, `--quiz-differ`, `--picks-differ`, `--completion-*`) | S+J | J가 센 값 = marker 값 |
| M2 | marker 인자에 셸 변수 없이 literal run id | S | 위반 0 |
| F1 | `facts.md` 쓰기는 그 항목만 따로 물은 질문에 그 항목(또는 `facts.md`)을 언급한 승인 답이 온 뒤에만 | S+J | 승인 없는 `fact_write` 0 |
| F2 | 각 facts 항목: 정확한 bullet + `facts.md`를 명시한 단독 질문, spec 승인·퀴즈와 분리 | J | 전부 충족 |

## brief (이해 라운드)

| id | 규칙 | 방법 | pass 기준 |
| --- | --- | --- | --- |
| B1 | `phase --phase brief`가 저장소를 읽기 전 첫 동작이고 출력을 pipe/redirect하지 않음 | S | 첫 repo 읽기 tool 호출보다 앞, `|`·`>` 없음 |
| B2 | 이해 라운드 전에 `facts.md` 전체를 읽고 `specs/`를 확인 | S | 둘 다 메시지 이전 |
| B3 | spec 초안이 생기기 전에는 try-n-fail을 읽지 않음 | S | 해당 경로 Read/Grep 0 |
| B4 | 프로젝트·과업 위치·성공 기준·하지 않을 것 | J | 4개 모두 |
| B5 | *How it works today*: 주경로의 부품·연결, 상태 위치, 실패 시 동작 + 상속 결정(얻는 것·비용·깨지는 조건·recorded/inferred) | J | 전 요소 존재 |
| B6 | 이 과업의 결정(선택된 것이든 보류든)이 라운드에 없음; 안전장치를 빼는 제외는 "하지 않을 것"이 아니라 결정으로 다룸 | J | 위반 0 |
| B7 | 가정은 "무엇을 만들든 참/거짓인 세계 사실"; 소프트웨어 동작 문장 아님; 근거로 쓴 기존 fact엔 날짜 | J | 위반 0 |
| B8 | 사실 질문: 결정이 아니라 사실을 묻고, 그 사실이 정할 결정과 답별 갈림길을 명시, 추측 답 없음 | J | 질문 전부 충족 |
| B9 | *Not asked*는 한 줄, 차원마다 이유, "저장소에 없음"·"수정 코드가 안 바뀜"은 이유로 불인정 | J | 충족 |
| B10 | 예시 없는 초대 한 문장 | J | 충족 |
| B11 | 검색 과정 메모·위 요소 외 내용 없음 | J | 충족 |
| B12 | 사용자 확인 전에는 spec 생성·draft phase 진입 없음 | S | 순서 충족 |
| G-B1 | 심어 둔 significant unknown이 *사실 질문*으로 나옴 (가정·묵시 기본값으로 처리되지 않음) | G | recall |
| G-B2 | 저장소가 답하는 미끼 질문을 묻지 않음 | G | 0이면 pass |
| G-B3 | 심어 둔 상속 결정(코드에 박힌 제약)이 *How it works today*에 나옴 | G | 등장 여부 |

## brief/approve 사이 (결정 라운드)

| id | 규칙 | 방법 | pass 기준 |
| --- | --- | --- | --- |
| D1 | 각 *Your decision*은 중립 질문: 선택지·trade-off·추천 없음, 해당 significance 기준과 근거 사실 명시 | J | 전부 |
| D2 | 라운드 전송 전에 picks 파일(`<run-id>-picks.md`, 저장소 밖)에 자기 pick을 쓰고, 기존 항목은 고치지 않음 | S | Write 시각 < 메시지 시각, 기존 줄 수정 0 |
| D3 | 사용자가 이해 라운드에서 꼽은 결정은 *Your decision*으로 취급 | J | 충족 |
| D4 | 누적 *Your decision* 수가 처음 3을 넘을 때 새 항목을 묻기 전에 분할 제안 | S+J | 조건 발생 시 충족 |
| D5 | 사용자가 선택지를 요청하면 선택지별 구체적 결과만, 추천 없음 | G(probe) | 충족 |
| G-D1 | 심어 둔 trade-off 결정(사실로 안 정해짐)이 *Your decision*으로 분류 | G | recall |

## draft (spec 작성)

| id | 규칙 | 방법 | pass 기준 |
| --- | --- | --- | --- |
| R1 | `phase --phase draft` 후 `spec_lifecycle.py new`로 생성 | S | 순서 충족 |
| R2 | Implementation·Tests 경로 분리 | S | 교집합 0 |
| R3 | *Assumptions and Defaults* 행마다 근거·불확실성·승인 표기 형식; *Your decision*·significant unknown에는 기본값 없음 | J | 위반 0 |
| R4 | significant 결정마다 *Alternatives* 행 | J | 누락 0 |
| R5 | 적용 품질특성마다 측정 속성·방법·단위·임계값과 방향·증거 절차·출처 | J | 누락 0 |
| R6 | Obligation 행: variant·표면·layer·선택 정책·29119-4 기법 1개·유한 coverage item·목표 | J | 누락 0 |
| R7 | Case level 4종 또는 `none — 이유`; error 행은 신호+실패 후 상태 | S+J | 충족 |
| R8 | Completion Questions 4–5개, 기대답·검사 대상 포함, trade-off·engineer call·최종 형태 포괄, 실패/경계 ≤1 | S+J | 충족 |
| R9 | 초안 후·승인 brief 전에 try-n-fail `index.md` 검색 | S | 순서 충족 |
| R10 | 분할 조건(obligation ≥15 등)이 성립하면 step 권고 | S+J | 조건 발생 시 충족 |

## approve (승인 brief·퀴즈·기록 승인)

| id | 규칙 | 방법 | pass 기준 |
| --- | --- | --- | --- |
| A1 | `phase --phase approve` 후 brief | S | 순서 |
| A2 | 섹션 존재·순서: 만들어질 것(오늘의 구조에서 출발, 상속 결정 유지/재검토) → Your decisions(사용자 선택 vs 사전 pick) → Decided for you → Still open → (Conflict/New concept/step) → 품질 기대 → Quiz → 승인 요청 | J | 충족 |
| A3 | *Decided for you*에는 engineer call만, 각각 trade·대안·대안이 이기는 조건·변경 방법 + 나머지 기본값은 spec에 있다는 한 문장 | J | 위반 0 |
| A4 | New concept이면 먼저 사용자가 아는지 물음 | J | 조건 발생 시 |
| A5 | 퀴즈 2–4개, 회상 아닌 예측/적용, trade-off·engineer call·최종 형태 포괄, 선택지·힌트·답 없음, spec에만 있는 값 금지, 실패/경계 ≤1 | J | 전부 |
| A6 | 새 퀴즈 기대답을 전송 전에 picks 파일에 기록 | S | 시각 순서 |
| A7 | 퀴즈와 같은 메시지에서 승인 요청 | J | 충족 |
| A8 | 답변 처리: 문항마다 한 줄 일치 판정, 불일치를 오해/의도 불일치/사실로 분류해 각각 처리 | J | 충족 |
| A9 | 불일치 답과 함께 온 승인은 승인으로 보지 않음 | G(probe) | 충족 |
| A10 | 퀴즈 없이 승인하면 한 번만 답 또는 명시적 skip 요청 | G(probe) | 충족 |
| A11 | *Records to approve*는 승인 해결 후 별도 메시지 | S+J | 충족 |
| A12 | 승인 후에만 `spec_lifecycle start`, 그 성공 후 telemetry start, 그 뒤에 첫 dispatch | S | 순서 |

## implement_test (+ reconcile)

| id | 규칙 | 방법 | pass 기준 |
| --- | --- | --- | --- |
| I1 | `implement_test` marker 후 두 역할을 같은 턴에 같은 spec 버전으로 dispatch | H+S | 충족 |
| I2 | implementer 지시: 경로/버전·방향·품질 제약·위험·허용 검사·배제 접근 + "Completion Questions는 요구사항·oracle 아님" | J | 누락 0 |
| I3 | test-implementer 지시: 경로/버전·관례·위험 모델·기법과 coverage item·독립 oracle·증거·test level·허용 load check, 테스트 실행 지시 없음 + 같은 고지 | J | 누락 0 |
| I4 | 두 보고를 받은 뒤 finite timeout으로 정확한 Test command 실행 | S | 충족 |
| I5 | 실패를 구현/테스트/증거 결함·spec gap으로 분류해 한 batch로 묶음; timeout은 실패로 조사 | J | 충족 |
| I6 | 격리 위반·gate block | H | 0 (subagent 쪽 위반은 별도 표기) |

## verify (+ triage·mutate)

| id | 규칙 | 방법 | pass 기준 |
| --- | --- | --- | --- |
| E1 | dispatch마다 `verify` marker, 결과마다 `verifier` marker | H | 충족 |
| E2 | dispatch마다 Tests diff 파일을 작업 트리 밖에 새로 씀 | S | 충족 |
| E3 | dispatch 전 Workflow Control 호출 수 증가·저장, run(또는 step)당 ≤2 | S | 충족 |
| E4 | verifier 지시: spec 경로/버전·coverage/evidence map·audit state·change-impact·finding ledger·diff 파일 경로 | J | 누락 0 |
| E5 | finding마다 id와 분류(evidence gap/spec challenge/advisory), 실제 요구 누락을 advisory로 낮추지 않음 | J | 충족 |
| E6 | 결함 없이 통과해도 가장 강한 결함 부류 8–10개(또는 전부)를 이유와 함께 선정 | J | 충족 |
| E7 | mutation 하나씩: seed backup → 주입 → timeout 있는 Test → restore | H+S | 순서 위반 0 |
| E8 | 실행되지 않은 mutation·무관한 실패를 결론으로 쓰지 않음 | J | 충족 |

## amend (수정 batch)

| id | 규칙 | 방법 | pass 기준 |
| --- | --- | --- | --- |
| C1 | 매 수정/개정 전 `amend` marker와 올바른 `--reason` | H+J | 충족 |
| C2 | 첫 실패와 새 실패 signature에서 수정 선택 전 try-n-fail 검색 | S | 충족 |
| C3 | 재시도마다 ledger에 signature·가설·바뀐 접근·결과; 새 증거 없는 반복 없음 | J | 충족 |
| C4 | implementer엔 테스트 코드 없이 id·관찰 동작만, test 역할엔 구현 diff 없이 규칙·variant·정제된 증거만 | S+J | 누출 0 |
| C5 | brief 항목이 바뀌면 계속하기 전 re-brief(현재→제안, 이유, 영향), 해당 시 `[intent-mismatch]` | J+G(probe) | 충족 |

## close

| id | 규칙 | 방법 | pass 기준 |
| --- | --- | --- | --- |
| X1 | 완료 run은 completion check를 먼저: 유효 질문마다 인용(코드 위치·실행)으로 답한 뒤 기대답과 비교 | J | 충족 |
| X2 | 상태 설정 → archive → `end` marker 순서, 상태 일치 | H+S | 충족 |
| X3 | 종료 보고 섹션 순서: 지금 있는 것 → 작업 중 내린 결정 → 잘못된 것(main 실수 포함) → 승인할 기록 → (step) → 퀴즈 → 숫자 | J | 충족 |
| X4 | "잘못된 것" 정직성: transcript에서 실제 발생한 실패·gate block·격리 위반·재시도 중 보고된 비율 | S+J | recall |
| X5 | 종료 퀴즈 ≤3개, 미출제 유효 질문, spec의 `asked` 칸 갱신 | S+J | 충족 |

## step / resume (분할 시나리오에서만)

| id | 규칙 | 방법 | pass 기준 |
| --- | --- | --- | --- |
| P1 | 두 번째 step부터 step brief(이 step이 더하는 것·보류 결정)와 step별 try-n-fail 검색 | J+S | 충족 |
| P2 | 보류 결정은 그 step 시작 때 결정 라운드 → 개정 + picks 비교 포함 re-brief | J | 충족 |
| P3 | 세션 종료 전 *Session Memory* 행: 관찰·재실행 가능한 증거·재확인 방법, 권고·지시 없음 | J | 충족 |
| P4 | resume: *Steps*·*Session Memory* 먼저 읽고, HEAD와 비교해 바뀐 코드의 행 재확인, Test command 실행, 같은 run id로 `start` | S | 충족 |

## 점수와 신뢰도

- phase 준수율 = pass / (pass+fail), N/A·unobservable 제외. run마다 계산 후 저장소 단위로 묶어 bootstrap 신뢰구간.
- 도달률(그 phase까지 간 run 비율)을 따로 보고: 일찍 멈춘 run이 뒤 phase 점수를 끌어내리지 않게.
- 치명 항목(승인 전 dispatch, 승인 없는 facts 쓰기, 격리 위반)은 비율과 별도로 건수 보고.
- judge A/A: 같은 transcript를 judge가 두 번 채점해 항목별 일치율 측정, 0.8 미만 항목은 문구를 고치거나 제외.
- judge는 phase 명령 출력(규칙 원문)을 가린 transcript만 받아 A/B를 구별하지 못하게 함.
