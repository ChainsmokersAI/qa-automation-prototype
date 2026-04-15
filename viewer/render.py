from __future__ import annotations

import html
import json
import mimetypes
import re
import zipfile
from pathlib import Path
from urllib.parse import quote, urlparse

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

    def fence_render(tokens, idx, options, env):
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
    if not bare:
        return url
    target = resolve_relative_link(current_file, bare)
    if target is None or not target.exists():
        return url
    rel = to_repo_rel(target)
    encoded = quote(rel, safe="/")
    if target.suffix.lower() in {".md", ".markdown"}:
        cat = category_of(target) or ""
        return f"#/view?cat={cat}&path={encoded}"
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
        rendered = MD.render(text)
        rendered = _rewrite_links(rendered, abs_path)
        if truncated:
            rendered = _truncate_notice(rel) + rendered
        return {**meta, "kind": "markdown", "html": f'<div class="md-body">{rendered}</div>'}

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
