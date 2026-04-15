from __future__ import annotations

import html
import json
import mimetypes
import re
import zipfile
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename
from pygments.util import ClassNotFound

from .paths import REPO_ROOT, category_of, resolve_relative_link, to_repo_rel

PYGMENTS_FORMATTER = HtmlFormatter(nowrap=False, cssclass="codehl")
PYGMENTS_CSS = PYGMENTS_FORMATTER.get_style_defs(".codehl")

TEXT_SIZE_LIMIT = 5 * 1024 * 1024
ZIP_ENTRY_LIMIT = 500
ZIP_HARD_LIMIT = 1000

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
TEXT_EXTS = {".md", ".markdown", ".txt", ".srt", ".log", ".csv", ".tsv"}
CODE_LEXER_BY_EXT = {
    ".py": "python",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".js": "javascript",
    ".ts": "typescript",
    ".html": "html",
    ".css": "css",
    ".sh": "bash",
    ".sql": "sql",
    ".xml": "xml",
}


def _highlight_code(code: str, lang: str | None, filename: str | None = None) -> str:
    lexer = None
    if lang:
        try:
            lexer = get_lexer_by_name(lang, stripall=False)
        except ClassNotFound:
            pass
    if lexer is None and filename:
        try:
            lexer = guess_lexer_for_filename(filename, code)
        except ClassNotFound:
            pass
    if lexer is None:
        escaped = html.escape(code)
        return f'<pre class="codehl"><code>{escaped}</code></pre>'
    return highlight(code, lexer, PYGMENTS_FORMATTER)


def _build_md() -> MarkdownIt:
    md = (
        MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": False})
        .enable(["table", "strikethrough"])
        .use(footnote_plugin)
        .use(deflist_plugin)
        .use(tasklists_plugin, enabled=True)
        .use(anchors_plugin, max_level=4, slug_func=lambda s: re.sub(r"\s+", "-", s.strip().lower()))
    )

    def fence_render(self, tokens, idx, options, env):
        token = tokens[idx]
        return _highlight_code(token.content, token.info.strip() or None)

    md.add_render_rule("fence", fence_render)
    return md


MD = _build_md()

_LINK_RE = re.compile(r'(<(?:a|img)\b[^>]*?\b(?:href|src)=")([^"]+)(")', re.IGNORECASE)


def _is_external(url: str) -> bool:
    if url.startswith("#") or url.startswith("mailto:") or url.startswith("javascript:"):
        return True
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)


def _rewrite_url(current_file: Path, url: str) -> str:
    if _is_external(url):
        return url
    if url.startswith("/"):
        return url
    bare = url.split("#", 1)[0].split("?", 1)[0]
    fragment = ""
    if "#" in url:
        fragment = url.split("#", 1)[1]
    if not bare:
        return url
    target = resolve_relative_link(current_file, bare)
    if target is None or not target.exists():
        return url
    rel = to_repo_rel(target)
    encoded = quote(rel, safe="/")
    if target.suffix.lower() in {".md", ".markdown"}:
        cat = category_of(target) or ""
        anchor = f"&anchor={quote(unquote(fragment), safe='')}" if fragment else ""
        return f"#/view?cat={cat}&path={encoded}{anchor}"
    return f"/raw?path={encoded}"


def _rewrite_links(html_text: str, current_file: Path) -> str:
    def repl(match: re.Match[str]) -> str:
        prefix, url, suffix = match.group(1), match.group(2), match.group(3)
        return f"{prefix}{_rewrite_url(current_file, url)}{suffix}"

    return _LINK_RE.sub(repl, html_text)


def _read_text(path: Path) -> tuple[str, bool]:
    size = path.stat().st_size
    truncated = False
    if size > TEXT_SIZE_LIMIT:
        with path.open("rb") as f:
            raw = f.read(TEXT_SIZE_LIMIT)
        truncated = True
    else:
        raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    return text, truncated


def _truncate_notice(rel: str) -> str:
    encoded = quote(rel, safe="/")
    return (
        f'<div class="notice">파일이 5MB를 초과하여 잘려서 표시되었습니다. '
        f'<a href="/raw?path={encoded}">전체 다운로드</a></div>'
    )


def render_file(abs_path: Path) -> dict:
    if not abs_path.exists() or not abs_path.is_file():
        raise FileNotFoundError(str(abs_path))

    rel = to_repo_rel(abs_path)
    encoded = quote(rel, safe="/")
    suffix = abs_path.suffix.lower()
    stat = abs_path.stat()
    meta = {
        "kind": "unknown",
        "title": abs_path.name,
        "mtime": stat.st_mtime,
        "size": stat.st_size,
        "path": rel,
    }

    if suffix in {".md", ".markdown"}:
        text, truncated = _read_text(abs_path)
        try:
            body = render_typed_markdown(text, abs_path)
        except Exception:
            import logging
            logging.getLogger("viewer.render").exception(
                "typed markdown render failed, falling back to raw text: %s", abs_path
            )
            body = _raw_text_html(text)
        if truncated:
            body = _truncate_notice(rel) + body
        return {**meta, "kind": "markdown", "html": body}

    if suffix == ".pdf":
        return {
            **meta,
            "kind": "pdf",
            "html": f'<iframe class="pdf-frame" src="/raw?path={encoded}"></iframe>',
        }

    if suffix in IMAGE_EXTS:
        return {
            **meta,
            "kind": "image",
            "html": f'<div class="img-wrap"><img src="/raw?path={encoded}" alt="{html.escape(abs_path.name)}"></div>',
        }

    if suffix == ".zip":
        try:
            with zipfile.ZipFile(abs_path) as zf:
                names = zf.namelist()
        except zipfile.BadZipFile:
            return {**meta, "kind": "binary", "html": _binary_html(rel, "손상된 zip 파일")}
        total = len(names)
        shown = names[:ZIP_ENTRY_LIMIT] if total > ZIP_HARD_LIMIT else names
        items = "".join(f"<li>{html.escape(n)}</li>" for n in shown)
        truncated_msg = (
            f"<p class='notice'>총 {total}개 항목 중 처음 {ZIP_ENTRY_LIMIT}개만 표시</p>"
            if total > ZIP_HARD_LIMIT
            else ""
        )
        return {
            **meta,
            "kind": "zip",
            "html": (
                f'<div class="zip-body">'
                f'<p><a class="download" href="/raw?path={encoded}">다운로드</a> · 총 {total}개 항목</p>'
                f"{truncated_msg}<ul class='zip-list'>{items}</ul></div>"
            ),
        }

    if suffix == ".json":
        text, truncated = _read_text(abs_path)
        try:
            parsed = json.loads(text)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            pretty = text
        body = _highlight_code(pretty, "json", abs_path.name)
        if truncated:
            body = _truncate_notice(rel) + body
        return {**meta, "kind": "code", "html": body}

    if suffix in CODE_LEXER_BY_EXT or suffix in TEXT_EXTS:
        text, truncated = _read_text(abs_path)
        lang = CODE_LEXER_BY_EXT.get(suffix)
        if suffix == ".srt":
            body = f'<pre class="codehl"><code>{html.escape(text)}</code></pre>'
        else:
            body = _highlight_code(text, lang, abs_path.name)
        if truncated:
            body = _truncate_notice(rel) + body
        return {**meta, "kind": "code", "html": body}

    mime, _ = mimetypes.guess_type(abs_path.name)
    if mime and mime.startswith("text/"):
        text, truncated = _read_text(abs_path)
        body = f'<pre class="codehl"><code>{html.escape(text)}</code></pre>'
        if truncated:
            body = _truncate_notice(rel) + body
        return {**meta, "kind": "code", "html": body}

    return {**meta, "kind": "binary", "html": _binary_html(rel)}


def _binary_html(rel: str, note: str = "") -> str:
    encoded = quote(rel, safe="/")
    note_html = f"<p class='notice'>{html.escape(note)}</p>" if note else ""
    return (
        f'<div class="binary-body">{note_html}'
        f'<p>바이너리 파일입니다. <a class="download" href="/raw?path={encoded}">다운로드</a></p>'
        f"</div>"
    )


# ---------- Typed markdown renderers ----------

def _raw_text_html(text: str) -> str:
    return f'<pre class="codehl raw-fallback"><code>{html.escape(text)}</code></pre>'


def _render_md_html(text: str, abs_path: Path) -> str:
    if not text or not text.strip():
        return ""
    try:
        rendered = MD.render(text)
        return _rewrite_links(rendered, abs_path)
    except Exception:
        import logging
        logging.getLogger("viewer.render").exception(
            "markdown render failed, falling back to raw text: %s", abs_path
        )
        return _raw_text_html(text)


_S_HEADER_RE = re.compile(r"^## (S-\d+)(?::\s*(.+?))?\s*$", re.MULTILINE)
_TC_HEADER_RE = re.compile(r"^## (TC-\d+)(?::\s*(.+?))?\s*$", re.MULTILINE)
_TURN_HEADER_RE = re.compile(r"^### Turn (\d+)\s*$", re.MULTILINE)
_HR_TAIL_RE = re.compile(r"\n+---\s*$")


def render_typed_markdown(text: str, abs_path: Path) -> str:
    cat = category_of(abs_path)
    name = abs_path.name
    if cat == "scenarios":
        return render_scenarios(text, abs_path)
    if cat == "testcases":
        return render_testcases(text, abs_path)
    if cat == "simulations":
        if name.startswith("tc-") and name.endswith(".md"):
            return render_simulation_tc(text, abs_path)
        return render_simulation_summary(text, abs_path)
    return f'<div class="md-body">{_render_md_html(text, abs_path)}</div>'


def render_scenarios(text: str, abs_path: Path) -> str:
    matches = list(_S_HEADER_RE.finditer(text))
    if not matches:
        return f'<div class="md-body">{_render_md_html(text, abs_path)}</div>'
    out: list[str] = []
    intro = text[: matches[0].start()].strip()
    if intro:
        out.append(f'<div class="md-body sc-intro">{_render_md_html(intro, abs_path)}</div>')
    out.append('<div class="sc-list">')
    for i, m in enumerate(matches):
        sid = m.group(1)
        title = (m.group(2) or "").strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        body = _HR_TAIL_RE.sub("", body)
        body_html = _render_md_html(body, abs_path)
        out.append(
            '<details class="sc-block" id="{slug}">'
            '<summary class="sc-summary">'
            '<span class="sc-id">{sid}</span>'
            '<span class="sc-title">{title}</span>'
            '</summary>'
            '<div class="sc-body md-body">{body}</div>'
            '</details>'.format(
                slug=html.escape(sid.lower()),
                sid=html.escape(sid),
                title=html.escape(title),
                body=body_html,
            )
        )
    out.append("</div>")
    return "".join(out)


def render_testcases(text: str, abs_path: Path) -> str:
    matches = list(_TC_HEADER_RE.finditer(text))
    if not matches:
        return f'<div class="md-body">{_render_md_html(text, abs_path)}</div>'
    out: list[str] = []
    intro = text[: matches[0].start()].strip()
    if intro:
        out.append(f'<div class="md-body tc-intro">{_render_md_html(intro, abs_path)}</div>')
    out.append('<div class="tc-list">')
    for i, m in enumerate(matches):
        tcid = m.group(1)
        title = (m.group(2) or "").strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        body = _HR_TAIL_RE.sub("", body)
        body_html = _render_testcase_body(body, abs_path)
        out.append(
            '<details class="tc-block" id="{slug}">'
            '<summary class="tc-summary">'
            '<span class="tc-id">{tcid}</span>'
            '<span class="tc-title">{title}</span>'
            '</summary>'
            '<div class="tc-body md-body">{body}</div>'
            '</details>'.format(
                slug=html.escape(tcid.lower()),
                tcid=html.escape(tcid),
                title=html.escape(title),
                body=body_html,
            )
        )
    out.append("</div>")
    return "".join(out)


_TC_HIGHLIGHT_HEADERS = ("### 평가 기준", "### 목적", "### 테스트 목적")


def _render_testcase_body(body: str, abs_path: Path) -> str:
    parts = re.split(r"(?=^### )", body, flags=re.MULTILINE)
    out: list[str] = []
    for part in parts:
        if not part.strip():
            continue
        part_html = _render_md_html(part, abs_path)
        if any(part.startswith(h) for h in _TC_HIGHLIGHT_HEADERS):
            out.append(f'<div class="tc-eval-box">{part_html}</div>')
        else:
            out.append(part_html)
    return "".join(out)


def render_simulation_summary(text: str, abs_path: Path) -> str:
    return f'<div class="md-body sim-summary">{_render_md_html(text, abs_path)}</div>'


def render_simulation_tc(text: str, abs_path: Path) -> str:
    matches = list(_TURN_HEADER_RE.finditer(text))
    if not matches:
        return f'<div class="md-body">{_render_md_html(text, abs_path)}</div>'

    intro = text[: matches[0].start()].strip()
    intro_html = _render_md_html(intro, abs_path) if intro else ""

    last_end = matches[-1].end()
    trailing_h2 = re.search(r"^## ", text[last_end:], re.MULTILINE)
    if trailing_h2:
        trailing_start = last_end + trailing_h2.start()
        trailing = text[trailing_start:].strip()
    else:
        trailing_start = len(text)
        trailing = ""

    turn_blocks: list[str] = []
    for i, m in enumerate(matches):
        turn_num = m.group(1)
        body_start = m.end()
        if i + 1 < len(matches):
            body_end = matches[i + 1].start()
        else:
            body_end = trailing_start
        body = text[body_start:body_end]
        mid_h2 = re.search(r"^## ", body, re.MULTILINE)
        if mid_h2:
            body = body[: mid_h2.start()]
        turn_blocks.append(_render_turn_block(turn_num, body, abs_path))

    trailing_html = ""
    if trailing:
        trailing_html = (
            '<details class="sim-trailing">'
            '<summary>부가 섹션 (평가 대기 등)</summary>'
            f'<div class="md-body">{_render_md_html(trailing, abs_path)}</div>'
            "</details>"
        )

    intro_block = f'<div class="sim-intro md-body">{intro_html}</div>' if intro_html else ""
    return (
        '<div class="sim-tc">'
        f"{intro_block}"
        f'<div class="sim-turns">{"".join(turn_blocks)}</div>'
        f"{trailing_html}"
        "</div>"
    )


def _render_turn_block(turn_num: str, body: str, abs_path: Path) -> str:
    lines = body.split("\n")
    header_lines: list[str] = []
    response_lines: list[str] = []
    ref_lines: list[str] = []
    state = "header"
    for line in lines:
        if state == "header":
            if line.strip() == "- **챗봇 응답**:":
                state = "response"
            elif line.strip().startswith("- **reference"):
                state = "ref"
                ref_lines.append(line)
            else:
                header_lines.append(line)
        elif state == "response":
            if line.startswith("    "):
                response_lines.append(line[4:])
            elif line.strip() == "":
                response_lines.append("")
            elif line.strip().startswith("- **reference"):
                state = "ref"
                ref_lines.append(line)
            else:
                state = "ref"
                ref_lines.append(line)
        else:
            ref_lines.append(line)

    fields: dict[str, str] = {}
    user_orig: str | None = None
    user_sent: str | None = None
    for line in header_lines:
        mm = re.match(r"^- \*\*요청 시각\*\*:\s*(.+?)\s*$", line)
        if mm:
            fields["time"] = mm.group(1)
            continue
        mm = re.match(r"^- \*\*사용자 메시지 \(TC 원본\)\*\*:\s*(.+?)\s*$", line)
        if mm:
            user_orig = mm.group(1)
            continue
        mm = re.match(r"^- \*\*사용자 메시지 \(실전송\)\*\*:\s*(.+?)\s*$", line)
        if mm:
            user_sent = mm.group(1)
            continue
        mm = re.match(r"^- \*\*응답 시간\*\*:\s*(.+?)\s*$", line)
        if mm:
            fields["rt"] = mm.group(1)
            continue
        mm = re.match(r"^- \*\*상태\*\*:\s*(.+?)\s*$", line)
        if mm:
            fields["status"] = mm.group(1)
            continue
        mm = re.match(r"^- \*\*비고\*\*:\s*(.+?)\s*$", line)
        if mm:
            fields["note"] = mm.group(1)
            continue

    if user_sent and user_sent != "원본과 동일":
        user_msg = user_sent
        user_orig_diff = user_orig
    else:
        user_msg = user_orig or user_sent or ""
        user_orig_diff = None

    response_text = "\n".join(response_lines).strip()
    response_html = (
        _render_md_html(response_text, abs_path)
        if response_text
        else "<em class='muted'>(응답 없음)</em>"
    )

    ref_text = "\n".join(ref_lines).strip()
    ref_html = _render_md_html(ref_text, abs_path) if ref_text else ""

    meta_parts: list[str] = []
    if fields.get("time"):
        meta_parts.append(f'<span class="meta-pill">{html.escape(fields["time"])}</span>')
    if fields.get("rt"):
        meta_parts.append(f'<span class="meta-pill">{html.escape(fields["rt"])}</span>')
    if fields.get("status"):
        st = fields["status"]
        cls = "status-ok" if st == "success" else "status-fail"
        meta_parts.append(f'<span class="meta-pill {cls}">{html.escape(st)}</span>')
    if fields.get("note"):
        meta_parts.append(f'<span class="meta-pill note">{html.escape(fields["note"])}</span>')
    meta_row = "".join(meta_parts)

    orig_diff_html = ""
    if user_orig_diff:
        orig_diff_html = (
            f'<div class="user-orig-diff">원본: {html.escape(user_orig_diff)}</div>'
        )

    refs_block = ""
    if ref_html:
        refs_block = (
            '<details class="refs">'
            '<summary>reference</summary>'
            f'<div class="md-body">{ref_html}</div>'
            "</details>"
        )

    return (
        '<div class="sim-turn">'
        '<div class="turn-header">'
        f'<span class="turn-num">Turn {html.escape(turn_num)}</span>'
        f'<span class="turn-meta">{meta_row}</span>'
        "</div>"
        '<div class="chat user">'
        f'<div class="bubble">{html.escape(user_msg)}</div>'
        f"{orig_diff_html}"
        "</div>"
        '<div class="chat bot">'
        f'<div class="bubble md-body">{response_html}</div>'
        "</div>"
        f"{refs_block}"
        "</div>"
    )
