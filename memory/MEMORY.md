# Memory

@lessons-learned.md
@user-preferences.md

## 프로젝트 현황

- 상태: Learn + Generate + Run 단계 구현 완료
- QA 대상 챗봇: 미정
- 구현 완료: scaffold 구조, CLAUDE.md, `/learn-context`, `/generate-scenarios`, `/generate-testcases`, `/run-simulation` skills
- 최근 변경: CLAUDE.md에 QA 파이프라인 섹션 추가, API Endpoint → API Spec 리네임 + 충분성 기준 정의, TC 포맷 멀티턴 지원, `/run-simulation` 스킬 신규 생성, outputs/index.md 시뮬레이션 섹션 추가
- 미구현: `/evaluate-results` 스킬, 서브에이전트 (TC 리뷰 등)

## 다음 세션 할 일

- `/evaluate-results` 스킬 구현 (별도 feature 브랜치)
  - 시뮬레이션 결과를 TC 평가 기준에 따라 판정 (LLM-as-judge)
  - 시뮬레이션 결과 파일의 `## 평가 대기` 섹션에 hookpoint 이미 설계됨
- 서브에이전트 구성 (TC 리뷰 등)
- (낮음) 웹 리서치 전용 서브에이전트 정의
- (낮음) Build → Production 전환 작업

## 핵심 교훈

- context/는 memory/와 분리 — 챗봇 정보(context/)와 에이전트 경험(memory/)은 성격이 다름
- @ import는 세션 시작 시 전체 내용을 인라인 로딩함 — 항상 로딩해야 하는 파일에만 사용
- task-log.md처럼 계속 커지는 파일은 @import 대신 on-demand 읽기
- 작업 완료 후 메모리 업데이트는 PM이 말하기 전에 에이전트가 먼저 제안해야 한다

## 사용자 핵심 선호

- "묻지 말고, 먼저 제안하라" — 정보 부족해도 가안을 먼저 작성하여 확인받기
- 사용자와의 대화 최소화 (온보딩 마찰 최소화)
- [추측] 항목은 반드시 웹 검색 근거 필요, PM 확인 필수

## 작업 이력

상세 이력은 [task-log.md](task-log.md) 참조 — 이전 작업의 맥락이 필요할 때 직접 읽어서 확인할 것
