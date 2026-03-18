#!/usr/bin/env python3
"""Extract image/video payloads from RunPod handler JSON responses."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
from pathlib import Path
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract media files from a RunPod JSON response."
    )
    parser.add_argument("input_json", type=Path, help="Path to the RunPod JSON response")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Directory for extracted files. Defaults to the JSON file's directory.",
    )
    return parser.parse_args()


def ensure_text_payload(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Media payload is missing or empty.")
    return value.strip()


def split_data_uri(payload: str) -> tuple[str | None, str]:
    if payload.startswith("data:") and "," in payload:
        header, encoded = payload.split(",", 1)
        mime_type = header[5:].split(";", 1)[0] or None
        return mime_type, encoded
    return None, payload


def extension_from_mime(mime_type: str | None, fallback_name: str | None) -> str:
    if fallback_name:
        suffix = Path(fallback_name).suffix
        if suffix:
            return suffix
    if mime_type:
        guessed = mimetypes.guess_extension(mime_type, strict=False)
        if guessed:
            return guessed
        if mime_type == "video/h264-mp4":
            return ".mp4"
    return ".bin"


def iter_media_items(response: dict) -> Iterable[dict]:
    output = response.get("output")

    if isinstance(output, dict):
        images = output.get("images")
        if isinstance(images, list):
            for item in images:
                if isinstance(item, dict) and "data" in item:
                    yield item
        return

    if isinstance(output, list):
        for item in output:
            if isinstance(item, dict) and "base64" in item:
                yield {"data": item["base64"], "filename": item.get("filename")}


def main() -> int:
    args = parse_args()
    input_path = args.input_json.resolve()
    output_dir = (args.output_dir or input_path.parent).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8") as fh:
        response = json.load(fh)

    saved_files: list[Path] = []

    for index, item in enumerate(iter_media_items(response), start=1):
        payload = ensure_text_payload(item.get("data"))
        mime_type, encoded = split_data_uri(payload)
        raw = base64.b64decode(encoded)

        original_name = item.get("filename")
        extension = extension_from_mime(mime_type, original_name)
        output_name = original_name or f"runpod-output-{index}{extension}"
        output_path = output_dir / output_name
        output_path.write_bytes(raw)
        saved_files.append(output_path)

    if not saved_files:
        raise SystemExit("No extractable media payloads found in the response JSON.")

    for path in saved_files:
        print(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
