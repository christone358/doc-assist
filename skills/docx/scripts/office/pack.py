#!/usr/bin/env python3
"""Pack an unpacked DOCX directory back into a DOCX file.

- Repairs xml:space for text nodes with edge whitespace.
- Repairs oversized durableId values.
- Optionally validates the result.
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
MAX_DURABLE_ID = 0x7FFFFFFE


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def repair_xml(path: Path) -> None:
    root = ET.parse(path).getroot()
    changed = False

    for el in root.iter():
        if local_name(el.tag) in {"t", "instrText", "delText", "delInstrText"}:
            text = el.text or ""
            if text[:1].isspace() or text[-1:].isspace():
                if el.get(f"{{{XML_NS}}}space") != "preserve":
                    el.set(f"{{{XML_NS}}}space", "preserve")
                    changed = True

        for attr_name, attr_value in list(el.attrib.items()):
            if local_name(attr_name) != "durableId":
                continue
            try:
                numeric = int(attr_value)
            except ValueError:
                numeric = MAX_DURABLE_ID + 1
            if numeric > MAX_DURABLE_ID:
                el.set(attr_name, str(random.randint(1, MAX_DURABLE_ID)))
                changed = True

    if changed:
        path.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))


def validate_unpacked_dir(root_dir: Path) -> list[str]:
    required = [
        root_dir / "[Content_Types].xml",
        root_dir / "_rels" / ".rels",
        root_dir / "word" / "document.xml",
    ]
    issues: list[str] = []
    for path in required:
        if not path.exists():
            issues.append(f"Missing required file: {path}")

    for xml_path in sorted(root_dir.rglob("*.xml")):
        try:
            ET.parse(xml_path)
        except ET.ParseError as exc:
            issues.append(f"Invalid XML in {xml_path}: {exc}")
    return issues


def zip_dir(root_dir: Path, output_path: Path) -> None:
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root_dir.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, path.relative_to(root_dir).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack an unpacked DOCX directory.")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_docx", type=Path)
    parser.add_argument("--original", type=Path, default=None)
    parser.add_argument("--validate", default="true", choices={"true", "false"})
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    output_docx = args.output_docx.expanduser().resolve()
    do_validate = args.validate.lower() == "true"

    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    temp_dir = Path(tempfile.mkdtemp(prefix="docx-pack-"))
    try:
        working = temp_dir / "package"
        shutil.copytree(input_dir, working)
        for xml_path in sorted(working.rglob("*.xml")):
            repair_xml(xml_path)

        issues = validate_unpacked_dir(working) if do_validate else []
        if issues:
            for issue in issues:
                print(issue, file=sys.stderr)
            return 1

        output_docx.parent.mkdir(parents=True, exist_ok=True)
        zip_dir(working, output_docx)
        print(f"Packed {input_dir} -> {output_docx}")
        return 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
