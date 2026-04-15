"""에듀탭 (EduTap) 챗봇 API 호출 스크립트 — 시뮬레이션 실행기

Usage:
    .venv/bin/python outputs/scripts/edutap-api-client.py [--tc TC-001] [--run-id sim-YYYYMMDD-HHMMSS] [--concurrency 3]

필요 환경:
    - httpx (venv에 설치됨)
    - API Key는 context/07-api-spec.md 기준 (PM 제공 스테이징 키)

핵심 동작:
    1. outputs/testcases/s-*.md 파싱 → TC 목록·턴별 사용자 메시지 추출
    2. TC_METADATA의 clip_id·placeholder 치환 적용
    3. 비동기 + 세마포어로 TC 병렬 실행 (동시 3, TC 내부 턴은 순차)
    4. SSE 스트림 누적으로 챗봇 응답 조립 + reference 이벤트 수집
    5. outputs/simulations/{run-id}/tc-{번호}.md 기록 + summary.md 작성
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent.parent
TC_DIR = ROOT / "outputs" / "testcases"
SIM_DIR = ROOT / "outputs" / "simulations"
SCENARIO_DIR = ROOT / "outputs" / "scenarios"

API_URL = "https://tapapistaging.coxwave.link/api/v1/chats/stream"
API_KEY = os.environ.get("TAP_API_KEY", "<REDACTED>")
COURSE_ID = "CX251104"
USER_ID = "test-user-align"
DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# TC 메타데이터: TC ID → clip_id, placeholder 치환
# ---------------------------------------------------------------------------

TC_CLIP_MAP: dict[str, str] = {
    "TC-001": "CX251104_1_1", "TC-002": "CX251104_1_2", "TC-003": "CX251104_1_5",
    "TC-004": "CX251104_1_2", "TC-005": "CX251104_1_5", "TC-006": "CX251104_1_4",
    "TC-007": "CX251104_1_3", "TC-008": "CX251104_1_6", "TC-009": "CX251104_1_1",
    "TC-010": "CX251104_1_5", "TC-011": "CX251104_1_4", "TC-012": "CX251104_1_5",
    "TC-013": "CX251104_1_3", "TC-014": "CX251104_1_6", "TC-015": "CX251104_1_6",
    "TC-016": "CX251104_1_2", "TC-017": "CX251104_1_1", "TC-018": "CX251104_1_3",
    "TC-019": "CX251104_1_1", "TC-020": "CX251104_1_2", "TC-021": "CX251104_1_5",
    "TC-022": "CX251104_1_5", "TC-023": "CX251104_1_6", "TC-024": "CX251104_1_6",
    "TC-025": "CX251104_1_5", "TC-026": "CX251104_1_6", "TC-027": "CX251104_1_4",
    "TC-028": "CX251104_1_1", "TC-029": "CX251104_1_2", "TC-030": "CX251104_1_4",
    "TC-031": "CX251104_1_1", "TC-032": "CX251104_1_4", "TC-033": "CX251104_1_5",
    "TC-034": "CX251104_1_1", "TC-035": "CX251104_1_3", "TC-036": "CX251104_1_5",
    "TC-037": "CX251104_1_5", "TC-038": "CX251104_1_3", "TC-039": "CX251104_1_5",
    "TC-040": "CX251104_1_4", "TC-041": "CX251104_1_4", "TC-042": "CX251104_1_1",
    "TC-043": "CX251104_1_5", "TC-044": "CX251104_1_2", "TC-045": "CX251104_1_6",
    "TC-046": "CX251104_1_6", "TC-047": "CX251104_1_2", "TC-048": "CX251104_1_1",
    "TC-049": "CX251104_1_3", "TC-050": "CX251104_1_6", "TC-051": "CX251104_1_2",
    "TC-052": "CX251104_1_1", "TC-053": "CX251104_1_5", "TC-054": "CX251104_1_4",
}

# TC 본문의 "(사용자 답변 제시 …)" / "답: ○○" 등 플레이스홀더를
# 실제 전송 가능한 텍스트로 치환한다. 키는 (tc_id, turn_idx_1based).
PLACEHOLDER_OVERRIDES: dict[tuple[str, int], str] = {
    ("TC-009", 4): "직업윤리는 자율적 판단과 사회적 책임이 결합된 개념입니다. 단순히 규정 준수가 아니라 스스로 옳다고 판단한 행동을 실천하고, 그 결과에 대해 책임지는 태도입니다.",
    ("TC-014", 4): "3번은 허브는 물리 계층에서 작동하고 스위치는 데이터링크 계층에서 MAC 주소 기반으로 프레임을 전달한다고 답했어.",
    ("TC-020", 2): "문제 정의를 먼저 한 다음 데이터를 모으는 순서 아니었나?",
    ("TC-020", 4): "분석 기획은 데이터·리소스 제약을 고려해 해결 가능한 문제를 정의하고 평가 지표를 정한 뒤 절차를 설계하는 일이라고 이해했어.",
    ("TC-035", 2): "응, 강의 연습문제야.",
    ("TC-035", 4): "응, 실시간 응시 중인 시험 문제야.",
}

# ---------------------------------------------------------------------------
# TC 파일 파싱
# ---------------------------------------------------------------------------

TC_HEADER_RE = re.compile(r"^##\s+(TC-\d{3})[:：]\s*(.+?)\s*$")
TURN_HEADER_RE = re.compile(r"^####\s+Turn\s+(\d+)\s*$")
USER_MSG_RE = re.compile(r"^-\s+\*\*사용자\*\*[:：]\s*(.+)$")
SCENARIO_LINK_RE = re.compile(r"\[(S-\d{3}):")


@dataclass
class TCTurn:
    turn: int
    user_message_original: str
    user_message_sent: str


@dataclass
class TestCase:
    tc_id: str
    title: str
    scenario_id: str
    scenario_file_basename: str
    clip_id: str
    turns: list[TCTurn] = field(default_factory=list)


def parse_tc_file(path: Path) -> list[TestCase]:
    """TC 마크다운 파일에서 TC 목록과 턴별 사용자 메시지를 추출한다."""
    lines = path.read_text(encoding="utf-8").splitlines()
    tcs: list[TestCase] = []
    current_tc: TestCase | None = None
    current_turn: TCTurn | None = None

    for line in lines:
        m = TC_HEADER_RE.match(line)
        if m:
            # Finalize previous turn
            if current_tc and current_turn:
                current_tc.turns.append(current_turn)
                current_turn = None
            if current_tc:
                tcs.append(current_tc)
            tc_id = m.group(1)
            title = m.group(2).strip()
            current_tc = TestCase(
                tc_id=tc_id,
                title=title,
                scenario_id="",
                scenario_file_basename="",
                clip_id=TC_CLIP_MAP.get(tc_id, "CX251104_1_1"),
            )
            continue

        if current_tc is None:
            continue

        # Scenario link (next line under TC header or inside section)
        if not current_tc.scenario_id:
            sm = SCENARIO_LINK_RE.search(line)
            if sm:
                current_tc.scenario_id = sm.group(1)
                # Resolve scenario file
                sid_num = int(sm.group(1).split("-")[1])
                if sid_num <= 7:
                    current_tc.scenario_file_basename = "01-happy-path"
                elif sid_num <= 14:
                    current_tc.scenario_file_basename = "02-out-of-scope"
                else:
                    current_tc.scenario_file_basename = "03-robustness"

        m = TURN_HEADER_RE.match(line)
        if m:
            if current_turn:
                current_tc.turns.append(current_turn)
            turn_num = int(m.group(1))
            current_turn = TCTurn(turn=turn_num, user_message_original="", user_message_sent="")
            continue

        if current_turn and not current_turn.user_message_original:
            um = USER_MSG_RE.match(line)
            if um:
                raw = um.group(1).strip()
                current_turn.user_message_original = raw
                # Apply placeholder overrides
                override = PLACEHOLDER_OVERRIDES.get((current_tc.tc_id, current_turn.turn))
                current_turn.user_message_sent = override if override else raw

    if current_tc and current_turn:
        current_tc.turns.append(current_turn)
    if current_tc:
        tcs.append(current_tc)
    return tcs


def load_all_tcs() -> list[TestCase]:
    tcs: list[TestCase] = []
    for p in sorted(TC_DIR.glob("s-*.md")):
        tcs.extend(parse_tc_file(p))
    # Sort by TC id numerically
    tcs.sort(key=lambda t: int(t.tc_id.split("-")[1]))
    return tcs


# ---------------------------------------------------------------------------
# API 호출
# ---------------------------------------------------------------------------

def new_chat_session_id() -> str:
    return secrets.token_hex(12)


@dataclass
class TurnResult:
    turn: int
    user_message_original: str
    user_message_sent: str
    response_text: str
    references: list[dict[str, Any]]
    response_ms: int
    status: str  # success / error / timeout
    error: str | None = None
    retries: int = 0
    note: str = ""
    requested_at: str = ""


async def call_api(
    client: httpx.AsyncClient,
    text: str,
    chat_session_id: str,
    clip_id: str,
) -> tuple[str, list[dict[str, Any]], str]:
    """SSE 스트림을 읽어 (answer_text, references, returned_chat_session_id) 반환."""
    payload = {
        "user_info": {"user_id": USER_ID},
        "chat_session_id": chat_session_id,
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
    headers = {
        "TAP-API-KEY": API_KEY,
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    answer_parts: list[str] = []
    references: list[dict[str, Any]] = []
    returned_sid = chat_session_id

    async with client.stream("POST", API_URL, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT) as resp:
        resp.raise_for_status()
        async for raw in resp.aiter_lines():
            if not raw:
                continue
            if not raw.startswith("data:"):
                continue
            data_str = raw[5:].strip()
            if not data_str or data_str == "[DONE]":
                continue
            try:
                evt = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            role = evt.get("role")
            content = evt.get("content")
            if role == "assistant":
                if isinstance(content, dict):
                    if content.get("type") == "chat_session_id":
                        v = content.get("value")
                        if v:
                            returned_sid = v
                elif isinstance(content, str):
                    answer_parts.append(content)
            elif role == "reference":
                if isinstance(content, dict):
                    references.append(content)

    return "".join(answer_parts), references, returned_sid


async def send_turn_with_retry(
    client: httpx.AsyncClient,
    text: str,
    chat_session_id: str,
    clip_id: str,
    turn_idx: int,
    original: str,
) -> TurnResult:
    start = time.time()
    retries = 0
    last_error: str | None = None
    requested_at = datetime.now().astimezone().isoformat()
    retry_note_parts: list[str] = []

    while retries <= MAX_RETRIES:
        try:
            answer, refs, returned_sid = await call_api(client, text, chat_session_id, clip_id)
            elapsed_ms = int((time.time() - start) * 1000)
            note = "; ".join(retry_note_parts)
            if text != original and note:
                note = f"placeholder 치환; {note}"
            elif text != original:
                note = "placeholder 치환 (원본에 실제 답변 텍스트가 없어 실전송은 치환본)"
            return TurnResult(
                turn=turn_idx,
                user_message_original=original,
                user_message_sent=text,
                response_text=answer,
                references=refs,
                response_ms=elapsed_ms,
                status="success",
                retries=retries,
                note=note,
                requested_at=requested_at,
            ), returned_sid
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            last_error = f"HTTP {code}: {e.response.reason_phrase}"
            if code in (429, 503):
                if retries >= MAX_RETRIES:
                    break
                retry_after = e.response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else (2 ** retries) * 2
                retry_note_parts.append(f"재시도 {retries+1}회 ({code} → backoff {wait:.0f}s)")
                await asyncio.sleep(wait)
                retries += 1
                continue
            elif 500 <= code < 600:
                if retries >= 1:
                    break
                retry_note_parts.append(f"재시도 {retries+1}회 ({code})")
                await asyncio.sleep(2)
                retries += 1
                continue
            else:
                break
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            last_error = f"network/timeout: {type(e).__name__}: {e}"
            if retries >= 1:
                break
            retry_note_parts.append(f"재시도 {retries+1}회 (timeout/network → 2s)")
            await asyncio.sleep(2)
            retries += 1
            continue
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            break

    elapsed_ms = int((time.time() - start) * 1000)
    status = "timeout" if last_error and "timeout" in last_error.lower() else "error"
    note = "; ".join(retry_note_parts)
    if text != original:
        note = f"placeholder 치환; {note}" if note else "placeholder 치환"
    return TurnResult(
        turn=turn_idx,
        user_message_original=original,
        user_message_sent=text,
        response_text="",
        references=[],
        response_ms=elapsed_ms,
        status=status,
        error=last_error,
        retries=retries,
        note=note,
        requested_at=requested_at,
    ), chat_session_id


# ---------------------------------------------------------------------------
# TC 실행
# ---------------------------------------------------------------------------

async def run_tc(
    tc: TestCase,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    progress: dict[str, int],
    total: int,
) -> list[TurnResult]:
    async with sem:
        progress["in_flight"] += 1
        print(f"[진행 {progress['in_flight']}/{total - progress['done']}, 완료 {progress['done']}/{total}] {tc.tc_id} 실행 중 (turns={len(tc.turns)})", flush=True)
        sid = new_chat_session_id()
        results: list[TurnResult] = []
        for turn in tc.turns:
            res, sid = await send_turn_with_retry(
                client=client,
                text=turn.user_message_sent,
                chat_session_id=sid,
                clip_id=tc.clip_id,
                turn_idx=turn.turn,
                original=turn.user_message_original,
            )
            results.append(res)
            if res.status != "success":
                # 해당 턴 실패 시 이후 턴 실행 중단
                print(f"  ⚠ {tc.tc_id} Turn {turn.turn} {res.status}: {res.error}", flush=True)
                break
        progress["done"] += 1
        progress["in_flight"] -= 1
        print(f"  ✓ {tc.tc_id} 완료 ({sum(1 for r in results if r.status == 'success')}/{len(tc.turns)})", flush=True)
        return results


# ---------------------------------------------------------------------------
# 결과 기록
# ---------------------------------------------------------------------------

def fmt_references(refs: list[dict[str, Any]]) -> str:
    if not refs:
        return ""
    lines = ["", "**참조 클립**:"]
    for r in refs[:5]:  # 상위 5개만
        title = r.get("title", "")
        clip_id = r.get("clip_id", "")
        loc = r.get("location", "")
        score = r.get("score", "")
        summary = (r.get("summary") or "")[:120]
        lines.append(f"  - `{clip_id}` {title} ({loc}, score={score:.3f}) — {summary}" if isinstance(score, (int, float)) else f"  - `{clip_id}` {title} ({loc}) — {summary}")
    return "\n".join(lines)


def write_tc_result(
    run_dir: Path,
    tc: TestCase,
    results: list[TurnResult],
) -> dict[str, Any]:
    completed_turns = sum(1 for r in results if r.status == "success")
    total_turns = len(tc.turns)
    total_ms = sum(r.response_ms for r in results)
    if completed_turns == total_turns and total_turns > 0:
        status = "completed"
    elif completed_turns == 0:
        status = "error"
    else:
        status = "partial"

    out_path = run_dir / f"{tc.tc_id.lower()}.md"
    lines: list[str] = []
    lines.append(f"# {tc.tc_id} 시뮬레이션 결과\n")
    lines.append("## 참조")
    lines.append(f"- **TC**: [{tc.tc_id}: {tc.title}](../../testcases/{find_tc_file(tc.tc_id)}#{tc.tc_id.lower()}-{slugify(tc.title)})")
    lines.append(f"- **시나리오**: [{tc.scenario_id}](../../scenarios/{tc.scenario_file_basename}.md#{tc.scenario_id.lower()})")
    lines.append(f"- **실행 ID**: {run_dir.name}")
    lines.append(f"- **실행 시각**: {results[0].requested_at if results else ''}")
    lines.append(f"- **대화 유형**: {'싱글턴' if total_turns == 1 else '멀티턴'}")
    lines.append(f"- **연동 Clip**: `{tc.clip_id}`\n")
    lines.append("## 실행 결과\n")
    lines.append("| 항목 | 값 |")
    lines.append("|------|-----|")
    lines.append(f"| 상태 | {status} |")
    lines.append(f"| 실행 턴 수 | {completed_turns} / {total_turns} |")
    lines.append(f"| 총 소요 시간 | {total_ms} ms |\n")

    lines.append("## 대화 흐름\n")
    for r in results:
        lines.append(f"### Turn {r.turn}")
        lines.append(f"- **사용자 메시지 (TC 원본)**: {r.user_message_original}")
        sent_display = "원본과 동일" if r.user_message_sent == r.user_message_original else r.user_message_sent
        lines.append(f"- **사용자 메시지 (실전송)**: {sent_display}")
        if r.status == "success":
            resp = r.response_text.strip() or "(응답 없음)"
            lines.append(f"- **챗봇 응답**:\n\n{indent_block(resp)}")
            if r.references:
                lines.append(fmt_references(r.references))
        else:
            lines.append(f"- **챗봇 응답**: (실패)")
        lines.append(f"- **응답 시간**: {r.response_ms} ms")
        lines.append(f"- **상태**: {r.status}")
        if r.error:
            lines.append(f"- **에러**: {r.error}")
        if r.note:
            lines.append(f"- **비고**: {r.note}")
        lines.append("")

    lines.append("## 평가 대기\n")
    lines.append("이 결과는 아직 평가되지 않았습니다. `/evaluate-results` (예정) 스킬에서 TC 평가 기준 대비 판정을 수행합니다.")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "tc_id": tc.tc_id,
        "title": tc.title,
        "scenario_id": tc.scenario_id,
        "clip_id": tc.clip_id,
        "status": status,
        "completed_turns": completed_turns,
        "total_turns": total_turns,
        "total_ms": total_ms,
        "errors": [r.error for r in results if r.error],
        "file": out_path.name,
        "placeholder_used": any(r.user_message_original != r.user_message_sent for r in results),
    }


def find_tc_file(tc_id: str) -> str:
    """TC ID에 해당하는 s-NNN-testcases.md 파일명 (링크용)."""
    num = int(tc_id.split("-")[1])
    # TC 3개씩 시나리오에 배분되어 있다는 가정 하에 매핑
    scenario_num = (num - 1) // 3 + 1
    return f"s-{scenario_num:03d}-testcases.md"


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text.strip())


def indent_block(text: str, prefix: str = "  > ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def write_summary(run_dir: Path, chatbot: str, run_id: str, rows: list[dict[str, Any]]) -> None:
    by_status: dict[str, int] = {"completed": 0, "partial": 0, "error": 0, "skipped": 0}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    lines: list[str] = []
    lines.append("# 시뮬레이션 실행 요약\n")
    lines.append("## 실행 정보")
    lines.append(f"- **실행 ID**: {run_id}")
    lines.append(f"- **실행 시각**: {datetime.now().astimezone().isoformat()}")
    lines.append(f"- **대상 챗봇**: {chatbot}")
    lines.append(f"- **API Endpoint**: {API_URL}")
    lines.append("- **응답 방식**: SSE 스트리밍")
    lines.append(f"- **실행 범위**: 전체 ({len(rows)} TCs)\n")

    lines.append("## 결과 요약\n")
    lines.append("| 상태 | TC 수 |")
    lines.append("|------|-------|")
    for s in ("completed", "partial", "error", "skipped"):
        lines.append(f"| {s} | {by_status.get(s, 0)} |")
    lines.append(f"| **합계** | **{len(rows)}** |\n")

    placeholder_count = sum(1 for r in rows if r.get("placeholder_used"))
    lines.append("| 항목 | 값 |")
    lines.append("|------|-----|")
    lines.append(f"| Placeholder 치환 TC 수 | {placeholder_count} |")
    lines.append("| TC flow 이탈 TC 수 | 0 (본 런은 TC 원본 메시지 우선 전송, re-anchor 미적용 — 평가 단계에서 수동 분석 필요) |\n")

    lines.append("## TC별 결과\n")
    lines.append("| TC | 제목 | 대화 유형 | 상태 | 실행 턴 | 소요 시간 | 결과 파일 |")
    lines.append("|----|------|-----------|------|---------|-----------|-----------|")
    for r in rows:
        dialog_type = "싱글턴" if r["total_turns"] == 1 else "멀티턴"
        lines.append(
            f"| {r['tc_id']} | {r['title']} | {dialog_type} | {r['status']} | "
            f"{r['completed_turns']}/{r['total_turns']} | {r['total_ms']}ms | "
            f"[{r['file']}]({r['file']}) |"
        )

    # 에러 목록
    errs = [r for r in rows if r["status"] in ("error", "partial")]
    lines.append("\n## 에러 및 특이 사항\n")
    lines.append("### 에러/타임아웃 TC\n")
    if errs:
        lines.append("| TC | 상태 | 원인 |")
        lines.append("|----|------|------|")
        for r in errs:
            err_msg = "; ".join(r["errors"]) if r["errors"] else "-"
            lines.append(f"| {r['tc_id']} | {r['status']} | {err_msg} |")
    else:
        lines.append("없음")

    lines.append("\n### 특이 사항\n")
    lines.append("- 본 런은 TC 원본 메시지를 순차 전송하는 모드로 실행됨 (re-anchor 자동화 미구현). 평가 단계에서 TC flow 이탈 여부 수동 분석 필요.")
    if placeholder_count:
        lines.append(f"- 플레이스홀더 포함 TC {placeholder_count}개는 PLACEHOLDER_OVERRIDES로 사전 치환 후 전송됨.")

    lines.append("\n## 평가 상태\n")
    lines.append("미완료")

    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

async def main_async(tc_filter: list[str] | None, concurrency: int, run_id: str) -> None:
    all_tcs = load_all_tcs()
    if tc_filter:
        all_tcs = [t for t in all_tcs if t.tc_id in set(tc_filter)]
    if not all_tcs:
        print("실행할 TC가 없습니다.", file=sys.stderr)
        sys.exit(1)

    run_dir = SIM_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"실행 대상: {len(all_tcs)} TCs → {run_dir}")
    print(f"동시 실행 수: {concurrency}\n")

    sem = asyncio.Semaphore(concurrency)
    rows: list[dict[str, Any]] = []
    progress = {"done": 0, "in_flight": 0}

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, http2=False) as client:
        async def run_and_record(tc: TestCase) -> None:
            results = await run_tc(tc, client, sem, progress, len(all_tcs))
            row = write_tc_result(run_dir, tc, results)
            rows.append(row)

        await asyncio.gather(*(run_and_record(tc) for tc in all_tcs))

    rows.sort(key=lambda r: int(r["tc_id"].split("-")[1]))
    write_summary(run_dir, chatbot="에듀탭 (EduTap)", run_id=run_id, rows=rows)
    print(f"\n✓ 실행 완료 — {run_dir / 'summary.md'}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="에듀탭 챗봇 시뮬레이션 실행기")
    p.add_argument("--tc", action="append", help="실행할 특정 TC ID (반복 지정 가능). 미지정 시 전체")
    p.add_argument("--concurrency", type=int, default=3, help="동시 실행 수 (기본 3)")
    p.add_argument("--run-id", default=None, help="run-id (기본: sim-YYYYMMDD-HHMMSS)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_id = args.run_id or f"sim-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    asyncio.run(main_async(args.tc, args.concurrency, run_id))


if __name__ == "__main__":
    main()
