# Memory

@lessons-learned.md
@user-preferences.md

## 프로젝트 현황

- 상태: Learn + Generate 단계 구현 완료, learn-context 웹 리서치 확장 완료
- QA 대상 챗봇: 미정
- 구현 완료: scaffold 구조, CLAUDE.md, `/learn-context`, `/generate-scenarios`, `/generate-testcases` skills
- 최근 변경: learn-context Step 2b 웹 리서치를 3-Phase 구조로 확장 (Issues만 → context 전 항목 커버), Step 1에 서비스명/소개 요청 추가, CLAUDE.md knowledge/ 섹션 연동 업데이트, knowledge/index.md Phase별 카테고리화
- 미구현: 서브에이전트 (TC 리뷰 등)

## 다음 세션 할 일

- 서브에이전트 구성 (TC 리뷰 등)
- (낮음) 웹 리서치 전용 서브에이전트 정의
  - 목적: 검색 노하우(도메인별 유용한 사이트, 효과적인 키워드 조합, 출처 신뢰도 등)를 축적하여 리서치 품질을 지속적으로 개선
  - 구현 방안: memory: user-scope는 auto-memory off 환경에서 동작 불확실하므로, knowledge/ 및 서브에이전트 정의 파일(.claude/agents/) 자체에 노하우를 명시하는 방식으로 구현
- (낮음) Build → Production 전환 작업
  - 목적: 현재 Build 단계의 내용(설계 논의 이력, 구현 교훈 등)을 정리하고, 실제 사용자(PM)가 사용할 수 있는 상태로 전환
  - 범위: memory/ 초기화, context/ 표시 방식 재설계 (예: [추출]/[추측] 태깅을 사용자에게 그대로 노출할지), knowledge/ 초기 데이터 정리
  - 시점: Build 완료 후 진행

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
