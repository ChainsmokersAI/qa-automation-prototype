# Memory

@lessons-learned.md
@user-preferences.md

## 프로젝트 현황

- 상태: Learn + Generate + Run + Evaluate 단계 구현 완료 (파이프라인 5단계 전체 완성)
- QA 대상 챗봇: 미정
- 구현 완료: scaffold 구조, CLAUDE.md, `/learn-context`, `/generate-scenarios`, `/generate-testcases`, `/run-simulation`, `/evaluate-results` skills
- 최근 변경: `/evaluate-results` 스킬 신규 구현 — LLM-as-judge 방식으로 시뮬레이션 결과를 TC 평가 기준에 따라 Pass/Partial/Fail 판정. 공통 평가 기준(PM 추가), 엄격도 3단계(관대/보통/엄격), summary.md 종합 큐레이션(강점/약점/패턴/권고) 포함. 기존 tc-*.md 인플레이스 교체 방식
- 미구현: 서브에이전트 (TC 리뷰 등)

## 다음 세션 할 일

- 서브에이전트 구성 (TC 리뷰 등)
- (낮음) 웹 리서치 전용 서브에이전트 정의
- (낮음) Build → Production 전환 작업

## 핵심 교훈

- context/는 memory/와 분리 — 챗봇 정보(context/)와 에이전트 경험(memory/)은 성격이 다름
- @ import는 세션 시작 시 전체 내용을 인라인 로딩함 — 항상 로딩해야 하는 파일에만 사용
- task-log.md처럼 계속 커지는 파일은 @import 대신 on-demand 읽기
- 작업 완료 후 메모리 업데이트는 PM이 말하기 전에 에이전트가 먼저 제안해야 한다
- **작업 완료 시 메모리 4개 파일 순차 업데이트 필수** — MEMORY.md, task-log.md, lessons-learned.md, outputs/index.md. 하나라도 빠뜨리지 않는다
- **CLAUDE.md는 200줄 이내 엄수** — 핵심 판정 기준만 남기고 부연설명·중복 예시는 SKILL.md로 이관

## 사용자 핵심 선호

- "묻지 말고, 먼저 제안하라" — 정보 부족해도 가안을 먼저 작성하여 확인받기
- 사용자와의 대화 최소화 (온보딩 마찰 최소화)
- [추측] 항목은 반드시 웹 검색 근거 필요, PM 확인 필수

## 작업 이력

상세 이력은 [task-log.md](task-log.md) 참조 — 이전 작업의 맥락이 필요할 때 직접 읽어서 확인할 것
