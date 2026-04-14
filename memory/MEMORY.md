# Memory

@lessons-learned.md
@user-preferences.md

## 프로젝트 현황

- 상태: Learn + Generate + Run 단계 구현 완료
- QA 대상 챗봇: 미정
- 구현 완료: scaffold 구조, CLAUDE.md, `/learn-context`, `/generate-scenarios`, `/generate-testcases`, `/run-simulation` skills
- 최근 변경: 파이프라인 스킬 4종 동시 수정 — (1) `/generate-scenarios`에 Step 0.5 "참고 자료 확인" 추가로 RAG·프롬프트 첨부 파일을 inputs/에 수집·context/ 갱신, (2) `/generate-testcases` TC 기본을 멀티턴(5~10턴)으로 전환(FAQ 포함, PM 명시·User Logs 예외), (3) `/run-simulation`에 `outputs/scripts/` 호출 스크립트 영속화 + TC flow 이탈 시 re-anchor 규칙(원본/실전송/비고 3필드) + TC 간 병렬 실행(기본 5, Rate Limit 한도 50% 자동 하향) + 429/503 지수 백오프 재시도(2→4→8s, `Retry-After` 우선) 추가. 직전: knowledge/ 제거 및 raw URL 직접 인용 구조 전환
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
- **CLAUDE.md는 200줄 이내 엄수** — 핵심 판정 기준만 남기고 부연설명·중복 예시는 SKILL.md로 이관

## 사용자 핵심 선호

- "묻지 말고, 먼저 제안하라" — 정보 부족해도 가안을 먼저 작성하여 확인받기
- 사용자와의 대화 최소화 (온보딩 마찰 최소화)
- [추측] 항목은 반드시 웹 검색 근거 필요, PM 확인 필수

## 작업 이력

상세 이력은 [task-log.md](task-log.md) 참조 — 이전 작업의 맥락이 필요할 때 직접 읽어서 확인할 것
