#!/usr/bin/env python3
"""
에듀탭 AI 튜터 API 클라이언트 — QA 시뮬레이션용
환경변수: TAP_API_KEY (미설정 시 기본값 사용)
사용법:  python -m outputs.scripts.edutap-api-client [--concurrency N]
"""
import asyncio, httpx, json, os, sys, time, uuid, random
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://tapapistaging.coxwave.link"
ENDPOINT = f"{BASE_URL}/api/v1/chats/stream"
API_KEY = os.environ.get("TAP_API_KEY", "")
COURSE_ID = "CX251104"
TIMEOUT = 30.0
MAX_RETRIES = 3
DEFAULT_CONCURRENCY = 3

# ── TC 정의 ──────────────────────────────────────────────
TC_DEFS = [
    # S-001: 개념 질문-답변
    {"id":"TC-001","scenario":"S-001","clip":"CX251104_1_6","type":"single",
     "turns":[{"msg":"브릿지가 정확히 뭐하는 장비에요? 허브랑 뭐가 달라요?"}]},
    {"id":"TC-002","scenario":"S-001","clip":"CX251104_1_2","type":"single",
     "turns":[{"msg":"머신러닝으로 데이터 분석하려면 어떤 순서로 진행해야 돼요?"}]},
    {"id":"TC-003","scenario":"S-001","clip":"CX251104_1_5","type":"single",
     "turns":[{"msg":"ES6에서 shorthand property가 뭔지 설명해주세요"}]},
    {"id":"TC-004","scenario":"S-001","clip":"CX251104_1_4","type":"multi",
     "turns":[
         {"msg":"파인튜닝이 뭐예요? 그냥 처음부터 학습시키는 거랑 뭐가 다른 거예요?"},
         {"msg":"그럼 KPoEM이라는 모델은 어떤 데이터로 파인튜닝한 거예요?"},
         {"msg":"입문 데이터셋을 만드는 게 왜 어렵다고 했죠?"},
     ]},
    # S-002: 소크라테스식
    {"id":"TC-005","scenario":"S-002","clip":"CX251104_1_1","type":"multi",
     "turns":[
         {"msg":"직업윤리가 왜 중요해요? 그냥 일만 잘하면 되는 거 아닌가요?"},
         {"msg":"음... 동료한테 신뢰를 못 받으면 같이 일하기 힘들겠죠?"},
         {"msg":"성실하게 일하고 약속을 잘 지키는 거?"},
     ]},
    {"id":"TC-006","scenario":"S-002","clip":"CX251104_1_6","type":"single",
     "turns":[{"msg":"회사에서 네트워크 장비를 고를 때 뭘 기준으로 골라야 해요?"}]},
    {"id":"TC-007","scenario":"S-002","clip":"CX251104_1_2","type":"multi",
     "turns":[
         {"msg":"데이터 분석을 시작하려면 뭐부터 해야 돼요?"},
         {"msg":"음 뭘 알고 싶은지 먼저 정해야 하나요?"},
         {"msg":"데이터를 모아야 하지 않을까요?"},
     ]},
    # S-003: 복습 퀴즈
    {"id":"TC-008","scenario":"S-003","clip":"CX251104_1_6","type":"single",
     "turns":[{"msg":"네트워크 장비 강의 복습 퀴즈 내주세요"}]},
    {"id":"TC-009","scenario":"S-003","clip":"CX251104_1_6","type":"multi",
     "turns":[
         {"msg":"네트워크 장비 퀴즈 풀어볼래요"},
         {"msg":"음 브릿지는 인터넷을 연결해주는 장비 아닌가요?"},
         {"msg":"아 그러면 LAN끼리 연결해주는 건가요?"},
     ]},
    {"id":"TC-010","scenario":"S-003","clip":"CX251104_1_5","type":"single",
     "turns":[{"msg":"자바스크립트 ES6 문법 중에서 디스트럭처링 관련 퀴즈 내줘"}]},
    # S-004: 심화 학습
    {"id":"TC-011","scenario":"S-004","clip":"CX251104_1_2","type":"single",
     "turns":[{"msg":"강의에서 데이터 분석 기획 절차를 배웠는데, 실제 회사에서는 이걸 어떻게 적용해요?"}]},
    {"id":"TC-012","scenario":"S-004","clip":"CX251104_1_4","type":"single",
     "turns":[{"msg":"KPoEM 입문 데이터셋 만드는 과정을 좀 더 자세히 알고 싶어요. 어떤 단계를 거치는 거예요?"}]},
    {"id":"TC-013","scenario":"S-004","clip":"CX251104_1_3","type":"multi",
     "turns":[
         {"msg":"컴활 1급 2024년 개정사항에서 가장 중요한 변화가 뭐예요?"},
         {"msg":"그럼 그 부분 시험에 어떤 식으로 나와요? 예시 문제 같은 거 알려주세요"},
         {"msg":"이 부분 집중적으로 공부하려면 어떻게 해야 해요?"},
     ]},
    # S-006: 범위 밖
    {"id":"TC-014","scenario":"S-006","clip":"CX251104_1_1","type":"single",
     "turns":[{"msg":"요즘 삼성전자 주가 어때요?"}]},
    {"id":"TC-015","scenario":"S-006","clip":"CX251104_1_1","type":"single",
     "turns":[{"msg":"심심한데 재밌는 얘기 해줘"}]},
    {"id":"TC-016","scenario":"S-006","clip":"CX251104_1_6","type":"single",
     "turns":[{"msg":"유기화학에서 벤젠의 공명 구조 설명해줘"}]},
    {"id":"TC-017","scenario":"S-006","clip":"CX251104_1_5","type":"multi",
     "turns":[
         {"msg":"파이썬으로 웹 크롤링하는 법 알려줘"},
         {"msg":"아 그러면 자바스크립트 강의에서 뭐 배울 수 있어?"},
     ]},
    # S-007: 할루시네이션
    {"id":"TC-018","scenario":"S-007","clip":"CX251104_1_2","type":"single",
     "turns":[{"msg":"머신러닝 강의에서 배운 SVM 알고리즘의 커널 트릭 수학적 증명을 알려주세요"}]},
    {"id":"TC-019","scenario":"S-007","clip":"CX251104_1_6","type":"single",
     "turns":[{"msg":"네트워크 장비 강의에서 OSPF 프로토콜의 LSA 타입별 차이점을 설명했었잖아요. 다시 정리해주세요"}]},
    {"id":"TC-020","scenario":"S-007","clip":"CX251104_1_5","type":"single",
     "turns":[{"msg":"자바스크립트 강의에서 나온 ES6의 트리플 스프레드 연산자에 대해 다시 설명해줘"}]},
    # S-008: 모호한 질문
    {"id":"TC-021","scenario":"S-008","clip":"CX251104_1_1","type":"single",
     "turns":[{"msg":"그거 뭐였지?"}]},
    {"id":"TC-022","scenario":"S-008","clip":"CX251104_1_6","type":"single",
     "turns":[{"msg":"라우터"}]},
    {"id":"TC-023","scenario":"S-008","clip":"CX251104_1_5","type":"multi",
     "turns":[
         {"msg":"아까 그 함수요"},
         {"msg":"자바스크립트에서 화살표 함수요"},
         {"msg":"일반 함수랑 뭐가 달라요?"},
     ]},
    # S-010: 직접 답변 요구
    {"id":"TC-024","scenario":"S-010","clip":"CX251104_1_6","type":"single",
     "turns":[{"msg":"질문 하나만 할게요 힌트 말고 바로 답 알려주세요. 브릿지랑 스위치 차이가 뭐예요?"}]},
    {"id":"TC-025","scenario":"S-010","clip":"CX251104_1_4","type":"multi",
     "turns":[
         {"msg":"파인튜닝이 뭔지 설명해주세요"},
         {"msg":"그냥 바로 설명해주세요. 지금 시간이 없어서요"},
         {"msg":"감사해요. 그러면 프리트레이닝이랑 차이도 간단히 알려주세요"},
     ]},
    {"id":"TC-026","scenario":"S-010","clip":"CX251104_1_1","type":"single",
     "turns":[{"msg":"질문하면 맨날 되물어보지 말고 그냥 답을 알려줘요 제발"}]},
]

# ── SSE 파서 ─────────────────────────────────────────────
def parse_sse_line(line: str):
    """data: JSON 한 줄을 파싱. 텍스트 청크면 str, 세션이면 dict, 무관하면 None."""
    if not line.startswith("data: "):
        return None
    try:
        obj = json.loads(line[6:])
    except json.JSONDecodeError:
        return None
    role = obj.get("role")
    content = obj.get("content")
    if role == "assistant":
        if isinstance(content, str):
            return {"type": "text", "value": content}
        if isinstance(content, dict) and content.get("type") == "chat_session_id":
            return {"type": "session_id", "value": content["value"]}
    if role == "reference":
        return {"type": "reference", "value": content}
    return None

# ── 단일 턴 호출 ────────────────────────────────────────
async def call_api(client: httpx.AsyncClient, text: str, clip_id: str,
                   session_id: str) -> dict:
    """1회 API 호출. 반환: {text, session_id, references, elapsed_ms, status, error}"""
    payload = {
        "user_info": {"user_id": "qa-sim-agent"},
        "chat_session_id": session_id,
        "text": text,
        "answer_style": "concise",
        "command_id": "",
        "course_id": COURSE_ID,
        "course_name": "",
        "course_category": "",
        "course_sub_category": "",
        "clip_id": clip_id,
        "clip_play_head": 0,
        "is_retry": False,
    }
    headers = {"TAP-API-KEY": API_KEY}
    t0 = time.monotonic()
    chunks, refs, sid = [], [], session_id
    last_err = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with client.stream("POST", ENDPOINT, json=payload,
                                     headers=headers, timeout=TIMEOUT) as resp:
                if resp.status_code in (429, 503):
                    wait = float(resp.headers.get("Retry-After", 2 ** attempt))
                    wait *= 1 + random.uniform(-0.2, 0.2)
                    last_err = f"HTTP {resp.status_code}, retry {attempt}"
                    await asyncio.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    elapsed = int((time.monotonic() - t0) * 1000)
                    return {"text": "", "session_id": sid, "references": [],
                            "elapsed_ms": elapsed, "status": "error",
                            "error": f"HTTP {resp.status_code}"}
                async for raw in resp.aiter_lines():
                    parsed = parse_sse_line(raw)
                    if not parsed:
                        continue
                    if parsed["type"] == "text":
                        chunks.append(parsed["value"])
                    elif parsed["type"] == "session_id":
                        sid = parsed["value"]
                    elif parsed["type"] == "reference":
                        refs.append(parsed["value"])
            elapsed = int((time.monotonic() - t0) * 1000)
            return {"text": "".join(chunks), "session_id": sid,
                    "references": refs, "elapsed_ms": elapsed,
                    "status": "success", "error": None}
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            wait = (2 ** attempt) * (1 + random.uniform(-0.2, 0.2))
            last_err = f"{type(e).__name__}, retry {attempt}"
            if attempt < MAX_RETRIES:
                await asyncio.sleep(wait)

    elapsed = int((time.monotonic() - t0) * 1000)
    return {"text": "", "session_id": sid, "references": [],
            "elapsed_ms": elapsed, "status": "timeout",
            "error": last_err or "max retries exceeded"}

# ── TC 실행 ──────────────────────────────────────────────
async def run_tc(client: httpx.AsyncClient, tc: dict, sem: asyncio.Semaphore) -> dict:
    async with sem:
        session_id = uuid.uuid4().hex[:24]
        results = []
        total_t0 = time.monotonic()
        for i, turn in enumerate(tc["turns"], 1):
            ts = datetime.now(timezone.utc).isoformat()
            res = await call_api(client, turn["msg"], tc["clip"], session_id)
            session_id = res["session_id"]
            results.append({
                "turn": i, "timestamp": ts,
                "user_msg_original": turn["msg"],
                "user_msg_sent": turn["msg"],
                "response": res["text"],
                "elapsed_ms": res["elapsed_ms"],
                "status": res["status"],
                "error": res["error"],
                "references": res["references"],
                "note": "",
            })
            if res["status"] != "success":
                break
        total_ms = int((time.monotonic() - total_t0) * 1000)
        ok_turns = sum(1 for r in results if r["status"] == "success")
        total_turns = len(tc["turns"])
        if ok_turns == total_turns:
            status = "completed"
        elif ok_turns > 0:
            status = "partial"
        else:
            status = "error"
        return {
            "tc_id": tc["id"], "scenario": tc["scenario"],
            "type": tc["type"], "status": status,
            "turns_done": ok_turns, "turns_total": total_turns,
            "total_ms": total_ms, "turns": results,
        }

# ── 메인 ─────────────────────────────────────────────────
async def main(concurrency: int = DEFAULT_CONCURRENCY):
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        tasks = [run_tc(client, tc, sem) for tc in TC_DEFS]
        n = len(tasks)
        results = []
        for coro in asyncio.as_completed(tasks):
            r = await coro
            results.append(r)
            done = len(results)
            print(f"[{done}/{n}] {r['tc_id']} {r['status']} "
                  f"({r['turns_done']}/{r['turns_total']} turns, {r['total_ms']}ms)",
                  file=sys.stderr)
    results.sort(key=lambda r: r["tc_id"])
    json.dump(results, sys.stdout, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    conc = DEFAULT_CONCURRENCY
    if "--concurrency" in sys.argv:
        idx = sys.argv.index("--concurrency")
        conc = int(sys.argv[idx + 1])
    asyncio.run(main(conc))
