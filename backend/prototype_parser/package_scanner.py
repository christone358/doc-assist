"""Package scanner for Axure HTML exports."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from .models import PrototypePackageManifest


def _iter_package_dirs(prototypes_root: Path) -> Iterable[Path]:
    if not prototypes_root.exists():
        return []

    candidates: List[Path] = []
    root_html = list(prototypes_root.glob("*.html"))
    if root_html:
        candidates.append(prototypes_root)

    for directory in sorted(path for path in prototypes_root.iterdir() if path.is_dir()):
        if list(directory.rglob("*.html")):
            candidates.append(directory)

    return candidates


def iter_package_html_files(package_root: Path, prototypes_root: Path) -> List[Path]:
    if package_root == prototypes_root:
        return sorted(package_root.glob("*.html"))
    return sorted(package_root.rglob("*.html"))


def _build_fingerprint(package_root: Path, prototypes_root: Path) -> str:
    digest = hashlib.sha1()
    for html_file in iter_package_html_files(package_root, prototypes_root):
        stat = html_file.stat()
        digest.update(str(html_file.relative_to(package_root)).encode("utf-8"))
        digest.update(str(stat.st_mtime_ns).encode("utf-8"))
        digest.update(str(stat.st_size).encode("utf-8"))
    return f"sha1:{digest.hexdigest()}"


def _package_id(package_root: Path, prototypes_root: Path) -> str:
    if package_root == prototypes_root:
        return "root-package"
    return package_root.name


def _package_name(package_root: Path, prototypes_root: Path) -> str:
    if package_root == prototypes_root:
        return "prototypes-root"
    return package_root.name


def scan_prototype_packages(prototypes_root: Path) -> List[PrototypePackageManifest]:
    manifests: List[PrototypePackageManifest] = []
    for package_root in _iter_package_dirs(prototypes_root):
        html_files = iter_package_html_files(package_root, prototypes_root)
        if not html_files:
            continue

        entry_page = "index.html" if (package_root / "index.html").exists() else html_files[0].name
        updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        manifests.append(
            PrototypePackageManifest(
                package_id=_package_id(package_root, prototypes_root),
                package_name=_package_name(package_root, prototypes_root),
                root_path=str(package_root.relative_to(prototypes_root.parent)),
                entry_page=entry_page,
                fingerprint=_build_fingerprint(package_root, prototypes_root),
                page_count=len([path for path in html_files if path.name.lower() != "index.html"]),
                updated_at=updated_at,
            )
        )
    return manifests
