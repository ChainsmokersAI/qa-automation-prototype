from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import quote

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from viewer.fswatch import EventHub
    from viewer.paths import CATEGORY_ROOTS, PathError, REPO_ROOT, safe_resolve, to_repo_rel
    from viewer.render import PYGMENTS_CSS, render_file
else:
    from .fswatch import EventHub
    from .paths import CATEGORY_ROOTS, PathError, REPO_ROOT, safe_resolve, to_repo_rel
    from .render import PYGMENTS_CSS, render_file

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

log = logging.getLogger("viewer.server")

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"
INPUTS_ROOT = CATEGORY_ROOTS["inputs"]
UPLOAD_CHUNK = 1024 * 1024

hub = EventHub()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    loop = asyncio.get_running_loop()
    hub.attach_loop(loop)
    hub.start()
    heartbeat_task = asyncio.create_task(hub.heartbeat())
    try:
        yield
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        hub.stop()


app = FastAPI(lifespan=lifespan, title="QA Document Viewer")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


@app.get("/assets/pygments.css")
async def pygments_css() -> Response:
    return Response(content=PYGMENTS_CSS, media_type="text/css")


@app.get("/api/categories")
async def categories() -> JSONResponse:
    return JSONResponse({"categories": list(CATEGORY_ROOTS.keys())})


def _build_tree(root: Path) -> dict:
    if not root.exists():
        return {
            "name": root.name,
            "type": "dir",
            "path": to_repo_rel(root) if root.is_absolute() else "",
            "children": [],
        }
    return _walk(root)


def _walk(path: Path) -> dict:
    rel = to_repo_rel(path.resolve(strict=False))
    if path.is_file():
        try:
            stat = path.stat()
        except OSError:
            return {"name": path.name, "type": "file", "path": rel, "size": 0, "mtime": 0}
        return {
            "name": path.name,
            "type": "file",
            "path": rel,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        }
    children: list[dict] = []
    try:
        entries = sorted(
            path.iterdir(),
            key=lambda p: (p.is_file(), p.name.lower()),
        )
    except OSError:
        entries = []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        try:
            children.append(_walk(entry))
        except OSError:
            continue
    return {"name": path.name, "type": "dir", "path": rel, "children": children}


@app.get("/api/tree")
async def tree(category: str = Query(...)) -> JSONResponse:
    if category not in CATEGORY_ROOTS:
        raise HTTPException(400, "unknown category")
    return JSONResponse(_build_tree(CATEGORY_ROOTS[category]))


@app.get("/api/render")
async def render(path: str = Query(...)) -> JSONResponse:
    try:
        abs_path = safe_resolve(path)
    except PathError as e:
        raise HTTPException(400, str(e))
    if not abs_path.exists() or not abs_path.is_file():
        raise HTTPException(404, "file not found")
    try:
        result = render_file(abs_path)
    except Exception as e:
        log.exception("render failed: %s", path)
        raise HTTPException(500, f"render failed: {e}")
    return JSONResponse(result)


@app.get("/raw")
async def raw(path: str = Query(...)) -> FileResponse:
    try:
        abs_path = safe_resolve(path)
    except PathError as e:
        raise HTTPException(400, str(e))
    if not abs_path.exists() or not abs_path.is_file():
        raise HTTPException(404, "file not found")
    filename_quoted = quote(abs_path.name)
    headers = {
        "Content-Disposition": f"inline; filename*=UTF-8''{filename_quoted}",
    }
    return FileResponse(str(abs_path), headers=headers)


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)) -> JSONResponse:
    INPUTS_ROOT.mkdir(parents=True, exist_ok=True)
    saved: list[dict] = []
    renamed: list[dict] = []
    for f in files:
        original = (f.filename or "unnamed").replace("\\", "/").split("/")[-1].strip()
        if not original or original in {".", ".."}:
            original = "unnamed"
        target = INPUTS_ROOT / original
        was_renamed = False
        if target.exists():
            stem = target.stem
            suffix = target.suffix
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            target = INPUTS_ROOT / f"{stem}-{ts}{suffix}"
            was_renamed = True
        try:
            with target.open("xb") as out:
                while True:
                    chunk = await f.read(UPLOAD_CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
        except FileExistsError:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            target = INPUTS_ROOT / f"{target.stem}-{ts}{target.suffix}"
            with target.open("xb") as out:
                while True:
                    chunk = await f.read(UPLOAD_CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
            was_renamed = True
        finally:
            await f.close()
        info = {
            "path": to_repo_rel(target),
            "size": target.stat().st_size,
            "original": original,
        }
        if was_renamed:
            renamed.append(info)
        saved.append(info)
    return JSONResponse({"saved": saved, "renamed": renamed})


@app.get("/api/events")
async def events() -> StreamingResponse:
    queue = await hub.subscribe()

    async def gen() -> AsyncIterator[bytes]:
        try:
            yield b"event: hello\ndata: {}\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield b": ping\n\n"
                    continue
                data = json.dumps(payload, ensure_ascii=False)
                yield f"event: tree-changed\ndata: {data}\n\n".encode("utf-8")
        except asyncio.CancelledError:
            raise
        finally:
            hub.unsubscribe(queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="QA Document Viewer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    import uvicorn

    uvicorn.run(
        "viewer.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
