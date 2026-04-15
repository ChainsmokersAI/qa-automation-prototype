from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CATEGORY_ROOTS: dict[str, Path] = {
    "inputs": REPO_ROOT / "inputs",
    "context": REPO_ROOT / "context",
    "scenarios": REPO_ROOT / "outputs" / "scenarios",
    "testcases": REPO_ROOT / "outputs" / "testcases",
    "simulations": REPO_ROOT / "outputs" / "simulations",
}


class PathError(Exception):
    pass


def safe_resolve(rel: str) -> Path:
    if not rel:
        raise PathError("empty path")
    candidate = (REPO_ROOT / rel).resolve(strict=False)
    for root in CATEGORY_ROOTS.values():
        try:
            candidate.relative_to(root)
            return candidate
        except ValueError:
            continue
    raise PathError(f"path not in whitelist: {rel}")


def category_of(abs_path: Path) -> str | None:
    for name, root in CATEGORY_ROOTS.items():
        try:
            abs_path.relative_to(root)
            return name
        except ValueError:
            continue
    return None


def to_repo_rel(abs_path: Path) -> str:
    return abs_path.relative_to(REPO_ROOT).as_posix()


def resolve_relative_link(current_file_abs: Path, link: str) -> Path | None:
    target = (current_file_abs.parent / link).resolve(strict=False)
    if category_of(target) is None:
        return None
    return target
