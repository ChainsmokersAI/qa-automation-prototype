# API Spec

## Endpoint
- **URL**: `POST https://tapapistaging.coxwave.link/api/v1/chats/stream` [추출: inputs/pm-notes-20260416.md]
- **응답 방식**: SSE (Server-Sent Events) [추출: inputs/pm-notes-20260416.md]

## 인증
- **Header**: `TAP-API-KEY: ${TAP_API_KEY}` [추출: inputs/pm-notes-20260416.md]

## 요청 포맷

```json
{
    "user_info": {"user_id": "test-user-align"},
    "chat_session_id": "{세션 ID — 멀티턴 대화 유지용}",
    "text": "{사용자 질의}",
    "answer_style": "concise",
    "command_id": "",
    "course_id": "CX251104",
    "course_name": "",
    "course_category": "",
    "course_sub_category": "",
    "clip_id": "{클립 ID}",
    "clip_play_head": 0,
    "is_retry": false
}
```
[추출: inputs/pm-notes-20260416.md]

## 응답 포맷 (SSE)

### 텍스트 청크 (누적하여 전체 응답 조합)
```
data: {"role":"assistant","message_id":"...","content":"텍스트조각","content_type":"default","function_call":false}
```

### 세션 ID 반환
```
data: {"role":"assistant","message_id":"...","content":{"type":"chat_session_id","extension":"value","value":"..."}}
```

### 참조 정보
```
data: {"role":"reference","message_id":"...","content":{"type":"script","extension":"clip_script","title":"...","description":"...","summary":"...","location":"...","score":...,"clip_id":"..."}}
```
[추출: inputs/pm-notes-20260416.md]

## 세션 관리
- `chat_session_id` 필드로 멀티턴 대화 유지 [추출: inputs/pm-notes-20260416.md]
- 새 대화 시작 시 고유 ID 생성, 동일 TC 내 턴에서 재사용

## Clip ID 매핑
| Clip ID | 강의 제목 |
|---------|-----------|
| CX251104_1_1 | [NCS 직업기초능력] 직업윤리 |
| CX251104_1_2 | [빅데이터 분석] 머신러닝 기반 데이터 분석 기획 |
| CX251104_1_3 | [EBS] 컴활 1급 2024 최신 개정사항 특강 |
| CX251104_1_4 | [인공지능] 파인튜닝을 통한 KPoEM 모델 구현 |
| CX251104_1_5 | [자바스크립트] 최신 문법 (ES6, ES11) 정리 |
| CX251104_1_6 | [정보처리기사] 네트워크 관련 장비 |
[추출: inputs/pm-notes-20260416.md]
