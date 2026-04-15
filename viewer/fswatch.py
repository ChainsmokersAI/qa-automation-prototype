from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .paths import CATEGORY_ROOTS, REPO_ROOT, category_of, to_repo_rel

log = logging.getLogger("viewer.fswatch")

DEBOUNCE_SECONDS = 0.4
HEARTBEAT_SECONDS = 30.0


class _Handler(FileSystemEventHandler):
    def __init__(self, hub: "EventHub") -> None:
        self.hub = hub

    def _emit(self, src_path: str) -> None:
        try:
            abs_path = Path(src_path).resolve(strict=False)
        except OSError:
            return
        cat = category_of(abs_path)
        if cat is None:
            return
        rel = to_repo_rel(abs_path) if abs_path.exists() else None
        self.hub.submit(cat, rel)

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            self._emit(event.src_path)
            return
        self._emit(event.src_path)
        if hasattr(event, "dest_path") and event.dest_path:
            self._emit(event.dest_path)


class EventHub:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending: dict[tuple[str, str | None], float] = {}
        self._observer: Observer | None = None
        self._snapshot: dict[str, dict[str, float]] = {cat: {} for cat in CATEGORY_ROOTS}
        self._lock = asyncio.Lock()

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(q)

    def submit(self, category: str, path: str | None) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._enqueue, category, path)

    def _enqueue(self, category: str, path: str | None) -> None:
        key = (category, path)
        now = time.monotonic()
        first_time = key not in self._pending
        self._pending[key] = now
        if first_time and self._loop is not None:
            self._loop.call_later(DEBOUNCE_SECONDS, self._flush, key)

    def _flush(self, key: tuple[str, str | None]) -> None:
        last = self._pending.get(key)
        if last is None:
            return
        if time.monotonic() - last < DEBOUNCE_SECONDS - 0.05:
            if self._loop is not None:
                self._loop.call_later(DEBOUNCE_SECONDS, self._flush, key)
            return
        self._pending.pop(key, None)
        category, path = key
        payload = {"category": category, "path": path}
        for q in list(self._subscribers):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def start(self) -> None:
        observer = Observer()
        handler = _Handler(self)
        for root in CATEGORY_ROOTS.values():
            try:
                root.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                log.warning("could not create %s: %s", root, e)
                continue
            observer.schedule(handler, str(root), recursive=True)
        observer.daemon = True
        observer.start()
        self._observer = observer
        self._snapshot = {cat: _scan(root) for cat, root in CATEGORY_ROOTS.items()}

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    async def heartbeat(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            try:
                await self._heartbeat_tick()
            except Exception:
                log.exception("heartbeat tick failed")

    async def _heartbeat_tick(self) -> None:
        async with self._lock:
            for cat, root in CATEGORY_ROOTS.items():
                fresh = _scan(root)
                old = self._snapshot.get(cat, {})
                changed_paths: set[str] = set()
                for p, mtime in fresh.items():
                    if old.get(p) != mtime:
                        changed_paths.add(p)
                for p in old.keys() - fresh.keys():
                    changed_paths.add(p)
                if changed_paths or (not old and fresh) or (old and not fresh):
                    self._snapshot[cat] = fresh
                    if not changed_paths:
                        self._enqueue(cat, None)
                    else:
                        for p in changed_paths:
                            self._enqueue(cat, p)


def _scan(root: Path) -> dict[str, float]:
    result: dict[str, float] = {}
    if not root.exists():
        return result
    try:
        for p in root.rglob("*"):
            try:
                if p.is_file():
                    result[to_repo_rel(p.resolve(strict=False))] = p.stat().st_mtime
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return result
