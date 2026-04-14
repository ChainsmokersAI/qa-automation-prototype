# Task Log

<!-- 최신 작업이 위로 오도록 기록 -->

## [2026-04-14] QA 파이프라인 스킬 4종 수정 (참고 자료 / 멀티턴 / 스크립트 영속화 / re-anchor / 병렬 실행)

- **요청**: PM — 파이프라인 실사용 중 발견한 4가지 마찰 지점
  1. `/generate-scenarios`에 참고 자료 (RAG 문서·프롬프트 첨부 파일) 수집 절차 부재
  2. `/generate-testcases` TC가 싱글턴 위주 — 멀티턴 5~10턴 기본화 요청
  3. `/run-simulation` 호출 스크립트가 in-memory only — 영속화 필요
  4. TC 대화 흐름을 챗봇 실제 응답에 억지로 맞추지 말고 자연스럽게 이어가되 비고에 기록
  - 추가: 시뮬레이션 병렬 실행 + Rate Limit 재시도
- **접근**: Plan 모드 → Explore 에이전트로 3종 스킬 구조 파악 → 플랜 초안 → AskUserQuestion으로 애매한 축 3개(flow 이탈 시 re-anchor vs 원본 유지, 멀티턴 강제 수준, 스크립트 저장 단위) 확인 → 승인 → 적용
- **결과**:
  - **generate-scenarios/SKILL.md**: Step 0.5 "참고 자료 확인" 신규 — PM에게 RAG/첨부파일 등 명시 질의, `inputs/` 업로드, `context/` 갱신 시 `[추출: inputs/...]` 태그
  - **generate-testcases/SKILL.md**: Step 1·2 재작성 — 모든 TC 기본 멀티턴(5~10턴), 챗봇 유형 무관, FAQ도 기본 멀티턴. User Logs·PM 명시만 예외
  - **run-simulation/SKILL.md**:
    - Step 3 "호출 스크립트 작성" 신규 — `outputs/scripts/{chatbot-slug}-api-client.{ext}`로 챗봇 단위 1개 영속화, Spec 변경 시 갱신, Bash로 실행
    - Step 3 실행 단위 재작성 — TC 간 병렬, TC 내부 Turn은 순차. Turn 2+는 직전 응답이 기대와 유의미하게 다르면 **re-anchor**(사용자 메시지 즉석 조정), 조정 사유는 비고에 기록
    - Step 3 "병렬 실행 규칙" 신규 — 기본 동시성 5, Rate Limit 명시 시 한도 50%로 자동 하향, conversation_id TC별 독립, 번호순 정렬 저장
    - Step 3 "에러 처리 및 재시도" 재작성 — 429/503/네트워크 오류 지수 백오프(2→4→8s, jitter ±20%) 최대 3회, `Retry-After` 헤더 우선, 429 반복 시 동시 실행 수 동적 절반 하향, 400/401/403/404는 재시도 제외
    - Step 3 기록 내용 표·Step 4 TC 결과 파일 포맷: `사용자 메시지(TC 원본)`/`사용자 메시지(실전송)`/`비고` 3필드로 확장
    - Step 4 디렉토리 구조: `outputs/scripts/` 포함, summary.md에 "TC flow 이탈 TC 수" 집계 추가
  - **outputs/index.md**: "호출 스크립트" 섹션 신규
- **주요 결정**:
  - flow 이탈 시 re-anchor 선택 — 원본 유지보다 자연스러운 대화·TC 목적 달성 우선, 대신 비고에 차이 기록으로 추적성 확보
  - 멀티턴 강제(예외 있음) — FAQ 챗봇도 기본 멀티턴으로 작성해 커버리지 상향
  - 스크립트 챗봇 단위 1개 — run-id별 복사본은 중복만 늘어 재현성 가치 < 저장 비용
  - 병렬 동시성 기본 5 + Rate Limit 한도 50% 자동 하향 — PM이 개발자 아니므로 보수적 기본 제공
- **검증**: 3개 SKILL.md 및 outputs/index.md 순차 Edit 후 최종 Read로 확인
- **특이 이벤트**: 병렬 실행 규칙 섹션 추가 직후 사용자가 파일 중간 상태를 보고 "날아간 것 같다"고 판단해 다음 Edit(에러 처리 재작성)을 reject → 이후 Read로 대조 결과 "병렬 실행 규칙"만 빠진 상태였음이 확인되어 해당 섹션만 재삽입 → 에러 처리 재작성은 사용자 확인 후 이어서 적용
- **교훈**: [lessons-learned.md 참조]

## [2026-04-14] learn-context Step 2b 웹 리서치 병렬화

- **요청**: PM — "learn-context Step 2 웹 리서치 단계에서 Phase 1, 2, 3를 병렬로 진행할 수 있는지? 시간 소요가 많다"
- **접근**: Phase 간 의존 관계 분석 — Phase 2·3의 검색 키워드는 Phase 1에서 확정되는 서비스명/도메인/경쟁사에 의존하므로 Phase 1 선행 필수. 반면 Phase 2와 Phase 3는 서로 의존하지 않음 → `Phase 1 → (Phase 2 ∥ Phase 3)` 구조 제안 → PM 승인 → 적용
- **결과**:
  - **learn-context/SKILL.md Step 2b 인트로**: 실행 순서 `Phase 1 → (Phase 2 ∥ Phase 3)` 명시. Phase 1이 반드시 선행되어야 하는 이유(키워드 의존성)와 Phase 2·3가 서로 의존하지 않는다는 점을 함께 서술
  - **공통 규칙에 "병렬 실행 규칙" 추가**:
    - Phase 1 완료 후 Phase 2·3의 WebSearch 쿼리를 동일 메시지에서 병렬 호출
    - 각 Phase 내 후보 URL WebFetch도 동일 메시지 병렬 호출 (5개 cap 준수)
    - 병렬 호출해도 knowledge/ 파일 저장은 Phase·항목별로 분리
- **주요 결정**:
  - 3개 Phase 전체 병렬이 아닌 `1 → (2 ∥ 3)` 선택 — Phase 1의 출력(서비스명/도메인/경쟁사)이 나머지 Phase 키워드의 기반이므로 완전 병렬화는 품질 희생. 부분 병렬로도 리서치 시간 ~1/3 단축 가능
  - Phase 내 WebFetch 병렬 호출 규칙을 명시적으로 추가 — 단순 Phase 간 병렬보다 Phase 내 병렬이 실제 time saving에 더 큼
- **검증**: Edit 적용 후 SKILL.md 변경부 및 5개 cap 규칙과의 정합성 확인
- **교훈**: 파이프라인 단계 간 병렬화를 고려할 때 **입력/출력 의존성 그래프를 먼저 그린다**. 전면 병렬만이 답이 아니며, 부분 병렬 + 단계 내 병렬 조합이 실효성 면에서 더 클 수 있다

## [2026-04-14] learn-context Step 1 분할 수집 + 웹 리서치 소스 cap

- **요청**: PM의 learn-context 개선 2건 — (1) Step 1에서 정보를 여러 단계로 나누어 수집 + PM이 "없음" 확인할 때까지 루프, (2) 웹 리서치 시 Phase 당 수집 소스 수가 너무 많아 실행 시간이 길어지는 문제 개선
- **접근**: Plan 모드 → Explore 에이전트로 learn-context/SKILL.md 구조 파악 → 플랜 초안에서 "Phase 3 테이블 행 축소(8→5)"로 오해 → PM이 "검색 대상 축소가 아니라 실제 수집 소스 수 cap" 의도 명확화 → 플랜 수정 → 승인 → 적용
- **결과**:
  - **learn-context/SKILL.md Step 1 (L22~L62 → L22~L86)**:
    - 단일 요청 리스트 → **Step 1a/1b/1c 분할 구조**로 재작성
    - **Step 1a**: 서비스명 + 1~2줄 소개 먼저 수집 (확인 전 1b로 진행 금지)
    - **Step 1b**: 파일/URL 중 1개 이상 수집 + API Spec 안내 문구 명시 (`/run-simulation` 실행 직전 재요청 예정)
    - **Step 1c**: "이 외에 추가로 전달하실 내용이 있으신가요?" → PM "없음" 확인까지 반복 루프
    - PM 세션 발언 파일화 규칙은 Step 1 전 과정(1a/1b/1c)에서 동일 pm-notes 파일에 **증분 갱신**으로 명시
  - **learn-context/SKILL.md Step 2b 공통 규칙 (L175~L187)**:
    - **Phase 당 소스 수 상한 5개** 규칙 추가 — 테이블 행(3+4+8)은 "후보 맵"으로 유지, 실제 WebFetch로 본문을 읽는 소스 URL만 Phase 당 5개로 제한
    - 선별 우선순위: (1) 공식 자료 > (2) 사용자 후기·커뮤니티 > (3) 경쟁사·도메인 일반
    - 권장 패턴: 1~2회 WebSearch로 후보 URL 확보 → 상위 5개 이내만 WebFetch
    - 키워드 변형 재검색도 5개 cap 내에서 수행. cap 초과 추가 검색 금지 (부족분은 도메인 기반 [추측]으로 보완)
- **주요 결정**:
  - Phase 3 축소 방식: **테이블 행 유지 + 실제 수집 소스만 cap** — 초안의 "행 3개 삭제" 방식은 검색 관점의 다양성을 희생시킴. 테이블을 "후보 맵"으로 재해석하여 유연성+속도 양쪽 확보
  - Step 1c 루프 종료 기준: PM의 "없음" **명시적 확인** 필수 — 답변 생략/모호 상태로 진행 금지 (정보 누락 방지 우선)
  - API Spec 안내는 Step 1b에 명시적 문구로 고정 — PM이 추후 re-request 예상을 사전에 인지하도록
- **PM 피드백 반영**:
  - 플랜 초안의 "Phase 3 테이블 8→5행 축소" 오해 → PM이 "검색 대상이 아니라 실제 수집 소스 수를 줄이려는 의도"라고 정정 → 플랜 구조 전면 수정
- **검증**: 수정 후 Read로 Step 1 (L22~L86) / 공통 규칙 (L175~L187) 재확인. 테이블 구조·저장 파일 목록·연쇄 열거(CLAUDE.md knowledge/ 테이블, context 8개 테이블) 영향 없음
- **교훈**: PM 요청의 "줄인다"는 표현이 들어올 때, **"무엇을 줄이는가"의 대상이 모호할 수 있다** — "검색 항목/테이블 행"과 "실제 수집 소스 수"는 전혀 다른 축이다. 플랜 작성 전에 한 번 더 확인했어야 함. (lessons-learned에 기록)

## [2026-04-13] CLAUDE.md/SKILL.md 다듬기 — 3 tasks

- **요청**: PM이 다음 3가지 정리를 요청 — (1) CLAUDE.md § API Spec 충분성 기준이 다른 skill 자체 판정 기준과 달리 outlier 위치, (2) `/run-simulation`의 PM 결과 보고 내용(에러 TC/특이 사항)이 summary.md에는 기록되지 않아 휘발성, (3) `/generate-testcases`에 멀티턴 TC 평균 턴 수 기준이 없어 실제 실행 시 2~3턴으로 짧게 생성됨
- **접근**: 논의 → run-simulation/SKILL.md에 동일 9항목을 다른 컬럼 구성으로 중복 기술한 축약 테이블 2개가 이미 있다는 숨은 문제 발견 → Plan 모드로 8개 수정 블록 설계 (3파일) → PM 승인 후 적용
- **결과**:
  - **CLAUDE.md (181 → 159줄)**:
    - § API Spec 충분성 기준 섹션 전체 삭제 (~18줄)
    - 파이프라인 주석 L26 참조 문구: "(아래 'API Spec 충분성 기준' 참조)" → "(상세 검증 기준은 `/run-simulation` 스킬 참조)"
    - 컨텍스트 8개 항목 테이블 API Spec 비고: "상세는 § API Spec 충분성 기준" → "(상세 검증 기준은 해당 스킬 참조)"
  - **run-simulation/SKILL.md (240 → 248줄)**:
    - Step 1 재구성: 기존 축약 테이블 2개 제거 + 단일 4열 테이블(등급/항목/설명/미충족 시 대응)로 통합. CLAUDE.md 역참조 문구 제거
    - Step 4 summary.md 포맷에 `## 에러 및 특이 사항` 섹션 추가 (TC별 결과 뒤 / 평가 상태 앞). 에러/타임아웃 TC 표 + 특이 사항 bullet
    - Step 5 PM 결과 보고에 "summary.md 동일 기록" 한 문장 추가
  - **generate-testcases/SKILL.md (114 → 128줄)**:
    - Step 1에 `### 멀티턴 TC 평균 턴 수 확인` 서브섹션 추가. 기본값 5~6턴, 챗봇 유형별 가이드(FAQ 2~3 / 상담 5~8 / 에이전트 10+), User Logs 분석 제안
    - Step 2 작성 규칙에 "멀티턴 TC 턴 수" 항목 추가 (Step 1 기준 ±2턴, 크게 벗어나면 사유 명시)
- **주요 결정**:
  - Option A (full move) 채택 — 하이브리드(원칙만 CLAUDE.md 잔류) 대비 중복 제거 효과 큼
  - 통합 테이블 컬럼은 4열(등급/항목/설명/미충족 시 대응) — 기존 "확인 방법" 정보는 "설명" 열로 자연스럽게 흡수
  - summary.md "에러 및 특이 사항" 섹션 위치는 TC별 결과 뒤 / 평가 상태 앞 (자연스러운 흐름)
  - 멀티턴 턴 수 확인을 Step 1 서브섹션으로 통합 (별도 Step 신설보다 단순)
  - default 5~6턴은 PM 실테스트 피드백 기반 (2~3턴은 너무 짧음)
- **PM 피드백 반영**: 사전 논의 단계에서 모든 결정 확정 → 구현 중 추가 피드백 없음
- **검증**: `wc -l` (200줄 제약 충족), `grep "API Spec 충분성 기준"` 라이브 파일 0건 (task-log.md의 1건은 과거 기록), `grep "CLAUDE.md의"` skills 디렉토리 0건
- **교훈**: 별도 기록 없음 — PM과 사전 논의로 설계가 충분히 정제된 상태에서 구현했기 때문. 단, "한 파일에 outlier 섹션이 있고 다른 파일이 같은 정보를 다른 포맷으로 중복 기술 중인 패턴"은 향후 유사 상황에서 의심 신호로 활용 가능

## [2026-04-13] context 항목 구조 리팩토링 (필수/선택 → 8개 단일 테이블)

- **요청**: context/ 항목의 필수/선택 구분이 misleading — API Spec은 사실상 필수(4단계 전까지 유예), Issues는 웹 서칭으로 항상 수집. 구분 폐지 고려. API Spec·User Logs의 "웹 리서치 금지" + "4단계 직전까지 보충 가능"은 비고로 분리 고려
- **접근**: 논의 선행 → 플랫화 대신 "8개 단일 테이블 + 비고 열" 제안 (User Logs의 진짜 optionality 보존). Learn 완료 기준을 (a)안 "1~6번 드래프트 완료"로 확정 → 6개 지점 스캔 후 5개 블록 diff 계획 제시 → PM OK → 적용
- **결과**:
  - CLAUDE.md § 컨텍스트: 필수/선택 두 테이블 → 8개 단일 테이블 + 비고 열. Learn 완료 기준 명시
  - CLAUDE.md § 프로젝트 구조: "필수 5항목 + 선택 3항목" → "핵심 6개 + PM 직접 제공 2개"
  - CLAUDE.md § knowledge/ 리서치 범위 테이블: User Flows를 Out-of-Scope 앞으로 이동 (추가 피드백 반영)
  - learn-context/SKILL.md Step 1: API Spec "(선택)" 제거 + 4단계 전까지 보충 가능 명시
  - learn-context/SKILL.md Step 2a: 필수/선택 두 테이블 → 8개 단일 테이블 + 비고 열. Issues 설명에서 "웹 검색으로 발견된" 제거
  - learn-context/SKILL.md Step 2b Phase 3: 헤딩·목적·테이블·저장 경로 전부 User Flows → Out-of-Scope → Issues 순서로 재배치 (추가 피드백 반영)
  - learn-context/SKILL.md Step 3: "필수 5개 + 선택" → "1~6번 / 7~8번 (미제공 시 '미수집'/'없음')"로 명시화
- **주요 결정**:
  - 구분 폐지(user 원안) 대신 "단일 테이블 + 비고"로 절충 — User Logs의 진짜 optionality(신규 챗봇에는 없을 수 있음)를 비고로 보존
  - Learn 완료 기준 = 1~6번 드래프트 완료. 7·8번은 상태 표기만("PM 대기"/"없음")
  - User Flows 순서: 4번째(Out-of-Scope 앞). 플로우가 먼저 정의되어야 한계(out-of-scope)를 정의할 수 있는 자연스러운 사고 순서
  - Issues 비고에 "웹 리서치 기본" 표기하지 않음 — 모든 항목이 PM 제공이 1차 소스이고 웹 리서치는 부족분 보완이라는 원칙을 Issues에만 라벨링하면 misleading
  - run-simulation/SKILL.md "필수 3항목"은 API Spec 하위 등급 의미이므로 유지 (context 항목의 "필수"와 축이 다름)
- **PM 피드백 반영**:
  - Issues 비고 "웹 리서치 기본" 제거 (내 초안의 혼돈 요소)
  - User Flows 4번째 이동 (사소한 순서 조정)
  - 적용 후 Phase 3/knowledge 리서치 범위 테이블에 순서 반영 누락 → PM 재지적 → 일괄 수정
- **교훈**: enumeration을 건드리는 구조 변경은 "동일 항목명 집합"을 grep으로 전수 검사해야 한다. "필수/선택" 같은 라벨만 스캔하면 순서가 일치해야 하는 다른 열거 위치(웹 리서치 테이블, 파일 경로 리스트 등)를 놓친다

## [2026-04-10] /learn-context 3대 규칙 준수 강화

- **요청**: 다른 브랜치 테스트 중 반복 발생한 3가지 문제 개선 — (1) API Spec을 공개 개발 문서에서 웹 추정, (2) 웹 검색 결과를 [추출]로 오분류, (3) Sources를 하단 References 스타일로 나열
- **접근**: Plan 모드로 설계 → 6개 수정 항목을 CLAUDE.md + learn-context/SKILL.md + lessons-learned.md에 적용
- **결과**:
  - CLAUDE.md: context/ 파일 규칙을 inline 표기 + 경로 prefix 기반 판정 원칙으로 재작성
  - SKILL.md Step 1: PM 세션 발언을 `inputs/pm-notes-{YYYYMMDD}.md`로 파일화하는 절차 추가
  - SKILL.md Step 2b Phase 2: "API Spec 웹 리서치 절대 금지" 경고 박스 승격
  - SKILL.md 공통 규칙: "API Spec 예외" + "knowledge/ = [추측] 원칙" 명시
  - SKILL.md Step 3: 출처 태그 판정 규칙 + 자주 발생하는 오분류 금지 사례 블록
  - SKILL.md Step 5: 하단 Sources 섹션 금지, inline 표기 예시 추가
- **주요 결정**:
  - 판정 기준을 "권위성"에서 "출처 경로 prefix"로 전환 → 공식 자료여도 knowledge/ 참조면 무조건 [추측]
  - API Spec은 "먼저 제안하라" 원칙의 유일한 예외 → PM 미제공 시 "미수집"으로 비워둠
  - PM 세션 발언도 파일화해야 [추출] 자격 → 추적 가능성 확보
- **PM 피드백 반영**:
  - lessons-learned에 추가했던 3건(API Spec/오분류/Sources)은 애매하다 판단 → 제거
  - CLAUDE.md가 200줄 초과(203줄) → 181줄로 compact (context/ 파일 규칙 섹션 축약)
  - "CLAUDE.md 200줄 이내 엄수" 원칙을 새 교훈으로 기록
- **교훈**: CLAUDE.md에 규칙을 추가할 때 장황한 부연설명·중복 예시를 피하고 핵심 판정 기준만 남긴다. 상세 사례는 SKILL.md로 이관

## [2026-04-10] run-simulation 스킬 + 파이프라인 고도화

- **요청**: 시뮬레이션 실행 스킬 생성 + 관련 전반 개선
- **접근**: Plan 모드로 설계 → PM 피드백 2회 반영 (스트리밍 API 지원, CLAUDE.md 파이프라인 섹션 추가)
- **결과**:
  - CLAUDE.md에 QA 파이프라인 섹션 추가 (5단계 워크플로우, 단계별 입력/출력/전제 조건 명시)
  - API Endpoint → API Spec 리네임 (CLAUDE.md, learn-context/SKILL.md). 스트리밍 응답 방식 포함
  - API Spec 충분성 기준 정의 (필수 3항목 + 권장 3항목 + 선택 3항목)
  - TC 포맷을 멀티턴 지원으로 변경 (대화 유형 + 대화 흐름 + Turn N 구조)
  - `/run-simulation` 스킬 신규 생성 (API Spec 검증 → TC 선택 → 실행 → 결과 저장)
  - outputs/index.md 시뮬레이션 섹션 추가
- **주요 결정**:
  - 시뮬레이션은 실행+기록만 담당, 평가(Evaluation)는 별도 스킬로 분리
  - 멀티턴이 기본이되, User Logs 및 챗봇 유형에 따라 싱글턴도 허용
  - API Spec 필수 3항목(Endpoint URL, 요청 포맷, 응답 포맷) 미충족 시 시뮬레이션 불가
  - 스트리밍 응답: API Spec에 명시되면 SSE 처리, 미확인 시 자동 감지 전환
  - 시뮬레이션 결과에 `## 평가 대기` 섹션으로 evaluation hookpoint 설계
- **교훈**: 파이프라인 전체 흐름을 CLAUDE.md에 명시하면 에이전트가 단계 간 의존성을 더 잘 이해함

## [2026-04-09] learn-context 웹 리서치 확장 + Step 1 보완

- **요청**: Step 2b 웹 리서치가 Issues만 커버 → context/ 전 항목 대응으로 확장. Step 1에 서비스명/소개 요청 추가.
- **접근**: Plan 모드로 설계 → PM 피드백 3회 반영 (API Endpoint 제외, slug 유지, [추측 불가] 대신 에이전트 자체 판단)
- **결과**:
  - SKILL.md Step 2b: 3-Phase 구조 (정체성→기능+사용자→한계+흐름+이슈), 항목별 검색 키워드 예시, 공통 규칙
  - SKILL.md Step 1: 서비스명 + 간단한 소개 + 관련 자료 요청으로 변경
  - CLAUDE.md: knowledge/ 섹션을 리서치 범위 테이블 + 파일 규칙으로 교체
  - knowledge/index.md: Phase별 카테고리 섹션으로 분리
- **주요 결정**:
  - API Endpoint는 고객사 제공 QA 서버 API → 웹 리서치 대상에서 제외
  - 검색 결과 부족 시 [추측 불가] 대신 에이전트 자체 판단으로 [추측] 포함
  - slug 컨벤션: 서비스명을 영문 소문자+하이픈으로 변환

## [2026-04-09] Generate 단계 구현

- **요청**: 테스트 시나리오/TC 생성 skill 구현
- **접근**: 시나리오·TC 포맷 설계 → 생성 전략 논의 → skill 파일 작성
- **결과**:
  - `/generate-scenarios` skill 구현 (시나리오 생성, 중요도 상/중/하 에이전트 부여 + PM 조정)
  - `/generate-testcases` skill 구현 (시나리오별 TC 생성, s-{번호}-testcases.md로 그룹핑)
  - 시나리오·TC 모두 context/ 섹션 레벨 참조 체계 적용
- **주요 결정**:
  - 시나리오 생성 우선순위: Happy Path → Edge Case → Issues 기반 중요도 조정
  - TC 파일은 시나리오별 그룹핑 (s-001-testcases.md)
  - TC도 context/ 직접 참조 (평가 기준의 근거가 되는 수치/정책 추적)
- **교훈**: 참조 체계가 과할 수 있다는 우려도 있으나, 추적 가능성 확보를 위해 우선 적용 후 검증

## [2026-04-09] Learn 단계 구현

- **요청**: Learn 단계 사용자 Flow 설계 및 `/learn-context` skill 구현
- **접근**: PM과 항목 정의 → 프로세스 설계 → skill 파일 작성
- **결과**:
  - 필수 항목 5개 확정: Chatbot Identity, Target Users, Core Capabilities, Out-of-Scope, User Flows
  - 선택 항목 3개 확정: API Endpoint, User Logs, Issues
  - `/learn-context` skill 구현 (6-step 프로세스)
  - CLAUDE.md에 context/ 항목 정의, knowledge/ 역할 명시
- **주요 결정**:
  - [추출] vs [추측] 출처 태깅 체계 도입
  - [추측]의 모든 근거는 knowledge/에 웹 검색 결과로 저장
  - 가안을 Plan 형태로 한 번에 제시, [추측] 항목은 PM 확인 필수
- **교훈**: skill 이름은 구체적으로 — "learn"은 너무 추상적, "learn-context"가 목적과 결과물을 명확히 표현

## [2026-04-09] 프로젝트 scaffold 구축

- **요청**: QA 자동화 에이전트 프로젝트 초기 구조 설계
- **접근**: ReAlign 제품 문서 + zero-to-one-advisor-agent 참고하여 구조 설계
- **결과**: 폴더 구조 및 scaffold 파일 생성
- **교훈**: context/는 memory/와 분리, @import로 세션 시작 시 자동 로딩
