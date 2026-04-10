#!/usr/bin/env python3
"""Accept all tracked changes in a DOCX document.

Strategy:
1. On Windows, try Microsoft Word COM automation.
2. On macOS, try Microsoft Word AppleScript automation.
3. On all platforms, fall back to pure OpenXML acceptance so Linux servers can run it too.

The XML fallback accepts the most common tracked-change structures used in DOCX:
- keep inserted content (`w:ins`, `w:moveTo`)
- remove deleted content (`w:del`, `w:moveFrom`)
- remove revision metadata containers such as `*PrChange`
- disable tracking in settings.xml
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}

KEEP_WRAPPERS = {"ins", "moveTo"}
DROP_WRAPPERS = {"del", "moveFrom"}
DROP_SINGLETONS = {
    "del",
    "delInstrText",
    "delText",
    "moveFromRangeStart",
    "moveFromRangeEnd",
    "moveToRangeStart",
    "moveToRangeEnd",
    "commentRangeStart",
    "commentRangeEnd",
}
DROP_CHANGE_TAGS = {
    "pPrChange",
    "rPrChange",
    "tblPrChange",
    "tblGridChange",
    "trPrChange",
    "tcPrChange",
    "sectPrChange",
    "numPrChange",
}
TEXT_TAGS = {"t", "instrText", "delText", "delInstrText"}
XML_NS = "http://www.w3.org/XML/1998/namespace"


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def apple_quote(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def accept_with_word_macos(src: Path, dest: Path) -> None:
    script = f"""
tell application "Microsoft Word"
  activate
  open POSIX file "{apple_quote(str(src.resolve()))}"
  accept all revisions in active document
  save as active document file name POSIX file "{apple_quote(str(dest.resolve()))}" file format format document default
  close active document saving no
end tell
"""
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or "Failed to accept revisions with Microsoft Word on macOS")


def accept_with_word_windows(src: Path, dest: Path) -> None:
    script = f"""
$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$doc = $word.Documents.Open("{str(src.resolve())}")
$doc.Revisions.AcceptAll()
$doc.SaveAs([ref] "{str(dest.resolve())}")
$doc.Close()
$word.Quit()
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or "Failed to accept revisions with Microsoft Word on Windows")


def insert_children(parent: ET.Element, index: int, wrapper: ET.Element) -> int:
    children = list(wrapper)
    for child in children:
        wrapper.remove(child)
        parent.insert(index, child)
        index += 1
    return index


def transform_element(parent: ET.Element) -> None:
    i = 0
    while i < len(parent):
        child = parent[i]
        name = local_name(child.tag)

        if name in KEEP_WRAPPERS:
            insert_children(parent, i, child)
            parent.remove(child)
            continue

        if name in DROP_WRAPPERS or name in DROP_SINGLETONS or name in DROP_CHANGE_TAGS:
            parent.remove(child)
            continue

        transform_element(child)
        i += 1


def normalize_spaces(root: ET.Element) -> None:
    for node in root.iter():
        if local_name(node.tag) in TEXT_TAGS:
            text = node.text or ""
            if text[:1].isspace() or text[-1:].isspace():
                node.set(f"{{{XML_NS}}}space", "preserve")


def accept_changes_in_xml_bytes(data: bytes, entry_name: str) -> bytes:
    root = ET.fromstring(data)
    transform_element(root)
    normalize_spaces(root)

    if entry_name.endswith("settings.xml"):
        for child in list(root):
            if local_name(child.tag) in {"trackRevisions", "doNotTrackMoves"}:
                root.remove(child)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def accept_with_xml_fallback(src: Path, dest: Path) -> None:
    xml_targets = {
        "word/document.xml",
        "word/footnotes.xml",
        "word/endnotes.xml",
        "word/settings.xml",
    }

    with tempfile.TemporaryDirectory(prefix="docx-accept-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        unpacked = temp_dir / "unpacked"
        unpacked.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(src) as zf:
            zf.extractall(unpacked)

        for xml_path in sorted((unpacked / "word").glob("header*.xml")):
            xml_targets.add(str(xml_path.relative_to(unpacked)).replace("\\", "/"))
        for xml_path in sorted((unpacked / "word").glob("footer*.xml")):
            xml_targets.add(str(xml_path.relative_to(unpacked)).replace("\\", "/"))

        for relative in sorted(xml_targets):
            path = unpacked / relative
            if not path.exists():
                continue
            path.write_bytes(accept_changes_in_xml_bytes(path.read_bytes(), relative))

        dest.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(unpacked.rglob("*")):
                if path.is_dir():
                    continue
                zf.write(path, path.relative_to(unpacked).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description="Accept all tracked changes in a DOCX.")
    parser.add_argument("input_docx", type=Path)
    parser.add_argument("output_docx", type=Path)
    parser.add_argument(
        "--method",
        choices=("auto", "xml", "word-win", "word-mac"),
        default="auto",
        help="Acceptance method. auto prefers native Word automation, then falls back to XML.",
    )
    args = parser.parse_args()

    input_docx = args.input_docx.expanduser().resolve()
    output_docx = args.output_docx.expanduser().resolve()
    output_docx.parent.mkdir(parents=True, exist_ok=True)

    if not input_docx.exists():
        print(f"Input DOCX not found: {input_docx}", file=sys.stderr)
        return 1

    methods: list[str]
    if args.method == "auto":
        methods = []
        if sys.platform == "win32":
            methods.append("word-win")
        if sys.platform == "darwin":
            methods.append("word-mac")
        methods.append("xml")
    else:
        methods = [args.method]

    errors: list[str] = []
    for method in methods:
        try:
            if method == "word-win":
                if sys.platform != "win32":
                    raise RuntimeError("word-win method requires Windows.")
                accept_with_word_windows(input_docx, output_docx)
            elif method == "word-mac":
                if sys.platform != "darwin":
                    raise RuntimeError("word-mac method requires macOS.")
                accept_with_word_macos(input_docx, output_docx)
            elif method == "xml":
                accept_with_xml_fallback(input_docx, output_docx)
            else:
                raise RuntimeError(f"Unknown method: {method}")

            print(output_docx)
            return 0
        except Exception as exc:
            errors.append(f"{method}: {exc}")

    for error in errors:
        print(error, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
