from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path


MAX_EVIDENCE_FILE_BYTES = 50 * 1024 * 1024


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^\w\-.\u4e00-\u9fff]+", "-", value, flags=re.UNICODE).strip(".-")
    return (cleaned or "evidence")[:80]


def copy_evidence_file(data_root: Path, evidence_id: int, title: str, source_path: str) -> tuple[str, int, str]:
    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if not source.is_file():
        raise IsADirectoryError(source)
    size_bytes = source.stat().st_size
    if size_bytes > MAX_EVIDENCE_FILE_BYTES:
        raise ValueError(f"文件超过 {MAX_EVIDENCE_FILE_BYTES // (1024 * 1024)} MB 限制")
    evidence_dir = data_root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    target = evidence_dir / f"{evidence_id}-{_safe_name(title)}{source.suffix[:20]}"
    shutil.copy2(source, target)
    digest = hashlib.sha256()
    with target.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return str(target), size_bytes, digest.hexdigest()
