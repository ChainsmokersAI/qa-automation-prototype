# Task Log

<!-- 최신 작업이 위로 오도록 기록 -->

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
