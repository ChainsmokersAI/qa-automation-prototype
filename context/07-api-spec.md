# API Spec

**상태**: 수집 완료 (2026-04-15 테크리드 제공) [추출: inputs/pm-notes-20260415.md]

## Endpoint
- **Staging URL**: `POST https://tapapistaging.coxwave.link/api/v1/chats/stream` [추출: inputs/pm-notes-20260415.md]
- **Demo site**: https://demo-edutap-staging.vercel.app/ [추출: inputs/pm-notes-20260415.md]

## 인증
- Header: `TAP-API-KEY: <REDACTED>` [추출: inputs/pm-notes-20260415.md]

## 요청 (JSON body)

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `user_info.user_id` | string | 필수 | 사용자 식별자. 본 QA에서는 `test-user-align` 고정 |
| `chat_session_id` | string | 필수 | 대화 세션 ID (MongoDB ObjectId 형식 24 hex). 멀티턴 TC는 동일 ID로 전송, 새 TC마다 신규 생성 |
| `text` | string | 필수 | 사용자 질의 원문 |
| `answer_style` | string | 필수 | `concise` 사용 |
| `command_id` | string | 필수 | 빈 문자열 `""` |
| `course_id` | string | 필수 | `CX251104` 고정 (본 QA 대상 과정) |
| `course_name` | string | 필수 | 빈 문자열 `""` |
| `course_category` | string | 필수 | 빈 문자열 `""` |
| `course_sub_category` | string | 필수 | 빈 문자열 `""` |
| `clip_id` | string | 필수 | 현재 시청 중 클립 (`CX251104_1_1` ~ `CX251104_1_6`) |
| `clip_play_head` | integer | 필수 | 재생 시점(초). QA에서는 `0` |
| `is_retry` | boolean | 필수 | `false` |

[추출: inputs/pm-notes-20260415.md]

## 응답 (SSE 스트림)

- `Content-Type: text/event-stream`
- 각 이벤트는 `data: {json}` 라인 형식
- **주요 이벤트 유형**:
  - `{"role":"assistant","content":{"type":"chat_session_id","value":"..."}}` — 세션 ID 확인 이벤트
  - `{"role":"assistant","content":"텍스트","content_type":"default"}` — 본문 텍스트 청크. 모든 청크를 순서대로 이어붙이면 챗봇 답변 전문
  - `{"role":"reference","content":{"type":"script","clip_id":"...","location":"0:26:39-0:27:39","summary":"...","score":0.60}}` — RAG 참조 클립 메타데이터 (여러 개 가능)
- 스트림 종료는 연결 종료로 판단

[추출: inputs/pm-notes-20260415.md]

## Clip ID 매핑 (본 QA 대상)

| Clip ID | 강의 제목 |
|---|---|
| CX251104_1_1 | [NCS 직업기초능력] 직업윤리 |
| CX251104_1_2 | [빅데이터 분석] 머신러닝 기반 데이터 분석 기획 |
| CX251104_1_3 | [EBS] 컴활 1급 2024 최신 개정 사항 특강 |
| CX251104_1_4 | [인공지능] 파인튜닝을 통한 KPoEM 모델 구현 |
| CX251104_1_5 | [자바스크립트] 최신 문법 (ES6, ES11) 모르면 후회하는 최신 문법과 사용법 정리 |
| CX251104_1_6 | [정보처리기사] 네트워크 관련 장비 |

[추출: inputs/pm-notes-20260415.md]

## 운영 상 주의

- Rate Limit 미명시 → 동시 실행 수 기본 3 유지
- `chat_session_id` 생성 규칙: MongoDB ObjectId 형식 (24 hex chars). 새 TC마다 `secrets.token_hex(12)`로 생성
- 응답 방식: SSE 스트리밍. 본문 청크를 누적해 완성된 답변 추출 후 기록
- 파일 업로드 지원 여부: 미명시 (QA 범위에 파일 첨부 TC 없음)
