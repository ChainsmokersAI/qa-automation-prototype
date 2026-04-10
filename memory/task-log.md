# Task Log

<!-- 최신 작업이 위로 오도록 기록 -->

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
