#!/usr/bin/env python3
"""Add a basic comment record to an unpacked DOCX package.

This script creates or updates `word/comments.xml` and wires up the package
relationships. It does not insert range markers into `document.xml`; that part
remains a deliberate manual edit, matching the skill instructions.

Replies are accepted as metadata but are recorded as ordinary comments unless
the document already contains the newer comments extension parts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def q(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"


def ensure_comments_xml(path: Path) -> ET.ElementTree:
    if path.exists():
        return ET.parse(path)
    root = ET.Element(q(W_NS, "comments"))
    tree = ET.ElementTree(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return tree


def ensure_content_type(content_types: Path) -> None:
    tree = ET.parse(content_types)
    root = tree.getroot()
    override_part = "/word/comments.xml"
    for override in root.findall(q(CT_NS, "Override")):
        if override.get("PartName") == override_part:
            return
    ET.SubElement(
        root,
        q(CT_NS, "Override"),
        {
            "PartName": override_part,
            "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
        },
    )
    tree.write(content_types, encoding="utf-8", xml_declaration=True)


def ensure_relationship(rels_path: Path) -> None:
    if rels_path.exists():
        tree = ET.parse(rels_path)
        root = tree.getroot()
    else:
        root = ET.Element(q(PKG_NS, "Relationships"))
        tree = ET.ElementTree(root)

    target = "comments.xml"
    rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
    for rel in root.findall(q(PKG_NS, "Relationship")):
        if rel.get("Type") == rel_type and rel.get("Target") == target:
            tree.write(rels_path, encoding="utf-8", xml_declaration=True)
            return

    next_id = 1
    while any(rel.get("Id") == f"rId{next_id}" for rel in root.findall(q(PKG_NS, "Relationship"))):
        next_id += 1

    ET.SubElement(
        root,
        q(PKG_NS, "Relationship"),
        {
            "Id": f"rId{next_id}",
            "Type": rel_type,
            "Target": target,
        },
    )
    rels_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(rels_path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Add a comment to an unpacked DOCX package.")
    parser.add_argument("unpacked_dir", type=Path)
    parser.add_argument("comment_id", type=int)
    parser.add_argument("text")
    parser.add_argument("--parent", type=int, default=None)
    parser.add_argument("--author", default="Claude")
    args = parser.parse_args()

    root_dir = args.unpacked_dir.expanduser().resolve()
    comments_path = root_dir / "word" / "comments.xml"
    content_types = root_dir / "[Content_Types].xml"
    rels_path = root_dir / "word" / "_rels" / "document.xml.rels"

    tree = ensure_comments_xml(comments_path)
    root = tree.getroot()

    comment = ET.SubElement(
        root,
        q(W_NS, "comment"),
        {
            q(W_NS, "id"): str(args.comment_id),
            q(W_NS, "author"): args.author,
            q(W_NS, "date"): datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            q(W_NS, "initials"): "".join(part[:1] for part in args.author.split()).upper()[:4],
        },
    )
    p = ET.SubElement(comment, q(W_NS, "p"))
    if args.parent is not None:
        # Keep parent context visible even when the extension parts are not present.
        parent_run = ET.SubElement(p, q(W_NS, "r"))
        parent_text = ET.SubElement(parent_run, q(W_NS, "t"))
        parent_text.text = f"[reply to comment {args.parent}] "
    r = ET.SubElement(p, q(W_NS, "r"))
    t = ET.SubElement(r, q(W_NS, "t"))
    t.text = args.text

    tree.write(comments_path, encoding="utf-8", xml_declaration=True)
    ensure_content_type(content_types)
    ensure_relationship(rels_path)
    print(f"Comment {args.comment_id} recorded in {comments_path}")
    print("Next step: add comment range markers to word/document.xml manually.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
