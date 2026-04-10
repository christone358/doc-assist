#!/usr/bin/env python3
"""Unpack a DOCX into a working directory.

- Extracts the zip package.
- Pretty prints XML files.
- Optionally merges adjacent simple runs.
- Replaces smart quotes with numeric XML entities so edits survive round-trips.
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W_NS}


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def canonical_xml(el: ET.Element | None) -> bytes:
    if el is None:
        return b""
    return ET.tostring(el, encoding="utf-8")


def merge_adjacent_runs(root: ET.Element) -> None:
    for parent in root.iter():
        children = list(parent)
        i = 0
        while i < len(children) - 1:
            left = children[i]
            right = children[i + 1]
            if local_name(left.tag) != "r" or local_name(right.tag) != "r":
                i += 1
                continue

            left_rpr = left.find(f"{{{W_NS}}}rPr")
            right_rpr = right.find(f"{{{W_NS}}}rPr")
            if canonical_xml(left_rpr) != canonical_xml(right_rpr):
                i += 1
                continue

            left_payload = [c for c in list(left) if local_name(c.tag) != "rPr"]
            right_payload = [c for c in list(right) if local_name(c.tag) != "rPr"]
            if len(left_payload) != 1 or len(right_payload) != 1:
                i += 1
                continue

            left_node = left_payload[0]
            right_node = right_payload[0]
            if local_name(left_node.tag) != local_name(right_node.tag):
                i += 1
                continue

            if local_name(left_node.tag) not in {"t", "instrText", "delText", "delInstrText"}:
                i += 1
                continue

            left_text = left_node.text or ""
            right_text = right_node.text or ""
            left_node.text = left_text + right_text
            if (
                left_node.get(f"{{{XML_NS}}}space") == "preserve"
                or right_node.get(f"{{{XML_NS}}}space") == "preserve"
                or left_node.text[:1].isspace()
                or left_node.text[-1:].isspace()
            ):
                left_node.set(f"{{{XML_NS}}}space", "preserve")

            parent.remove(right)
            children.pop(i + 1)


def normalize_text_nodes(root: ET.Element) -> None:
    for node in root.iter():
        if local_name(node.tag) in {"t", "instrText", "delText", "delInstrText"}:
            text = node.text or ""
            if text[:1].isspace() or text[-1:].isspace():
                node.set(f"{{{XML_NS}}}space", "preserve")


def prettify_xml(xml_text: str) -> str:
    parsed = minidom.parseString(xml_text.encode("utf-8"))
    pretty = parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
    lines = [line for line in pretty.splitlines() if line.strip()]
    return "\n".join(lines) + "\n"


def encode_smart_quotes(text: str) -> str:
    replacements = {
        "\u2018": "&#x2018;",
        "\u2019": "&#x2019;",
        "\u201c": "&#x201C;",
        "\u201d": "&#x201D;",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def process_xml_file(path: Path, merge_runs: bool) -> None:
    root = ET.parse(path).getroot()
    if merge_runs:
        merge_adjacent_runs(root)
    normalize_text_nodes(root)
    xml_text = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    pretty = prettify_xml(xml_text)
    path.write_text(encode_smart_quotes(pretty), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Unpack a DOCX for XML editing.")
    parser.add_argument("docx", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--merge-runs", default="true", choices={"true", "false"})
    args = parser.parse_args()

    docx_path = args.docx.expanduser().resolve()
    out_dir = args.output_dir.expanduser().resolve()
    merge_runs = args.merge_runs.lower() == "true"

    if not docx_path.exists():
        raise SystemExit(f"Input DOCX not found: {docx_path}")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(docx_path) as zf:
        zf.extractall(out_dir)

    for xml_path in sorted(out_dir.rglob("*.xml")):
        process_xml_file(xml_path, merge_runs=merge_runs)

    print(f"Unpacked {docx_path} -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
