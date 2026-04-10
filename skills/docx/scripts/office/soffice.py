#!/usr/bin/env python3
"""Small compatibility wrapper for office conversions.

Prefers LibreOffice (`soffice` / `libreoffice`). On macOS, falls back to
Microsoft Word automation for `.doc` -> `.docx` and `.docx` -> `.pdf`.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def find_office_binary() -> str | None:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    return None


def apple_quote(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def convert_with_word(src: Path, fmt: str, outdir: Path | None) -> Path:
    if sys.platform != "darwin":
        raise RuntimeError("Microsoft Word fallback is only supported on macOS.")

    dest_dir = outdir or src.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{src.stem}.{fmt}"

    if fmt == "docx":
        file_format = "format document default"
    elif fmt == "pdf":
        file_format = "format PDF"
    else:
        raise RuntimeError(f"Unsupported Word fallback conversion: {fmt}")

    script = f"""
tell application "Microsoft Word"
  activate
  open POSIX file "{apple_quote(str(src.resolve()))}"
  save as active document file name POSIX file "{apple_quote(str(dest.resolve()))}" file format {file_format}
  close active document saving no
end tell
"""
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or "Microsoft Word conversion failed")
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="Office conversion wrapper.")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--convert-to", required=True)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--outdir", type=Path, default=None)
    args = parser.parse_args()

    fmt = args.convert_to.lower()
    office_binary = find_office_binary()
    if office_binary:
        cmd = [office_binary]
        if args.headless:
            cmd.append("--headless")
        cmd.extend(["--convert-to", fmt])
        if args.outdir:
            cmd.extend(["--outdir", str(args.outdir)])
        cmd.extend(str(p) for p in args.inputs)
        result = subprocess.run(cmd)
        return result.returncode

    failures = 0
    for input_path in args.inputs:
        try:
            output = convert_with_word(input_path.expanduser().resolve(), fmt, args.outdir)
            print(output)
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
