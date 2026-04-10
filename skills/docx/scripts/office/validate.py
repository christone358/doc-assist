#!/usr/bin/env python3
"""Validate basic DOCX package structure and XML well-formedness."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

REQUIRED_ENTRIES = {
    "[Content_Types].xml",
    "_rels/.rels",
    "word/document.xml",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a DOCX package.")
    parser.add_argument("docx", type=Path)
    args = parser.parse_args()

    docx_path = args.docx.expanduser().resolve()
    if not docx_path.exists():
        print(f"Missing file: {docx_path}", file=sys.stderr)
        return 1

    issues: list[str] = []
    with zipfile.ZipFile(docx_path) as zf:
        names = set(zf.namelist())
        for required in sorted(REQUIRED_ENTRIES):
            if required not in names:
                issues.append(f"Missing required package entry: {required}")

        for name in sorted(names):
            if not name.endswith(".xml"):
                continue
            try:
                ET.fromstring(zf.read(name))
            except ET.ParseError as exc:
                issues.append(f"Invalid XML in {name}: {exc}")

    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1

    print(f"Validation passed: {docx_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
