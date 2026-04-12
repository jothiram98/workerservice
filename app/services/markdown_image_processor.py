from __future__ import annotations

import base64
import binascii
import re
from pathlib import Path


_DATA_IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<dataurl>data:image/(?P<fmt>[a-zA-Z0-9.+-]+);base64,(?P<b64>[^)]+))\)"
)


def _normalize_ext(fmt: str) -> str:
    fmt = fmt.lower()
    if fmt == "jpeg":
        return "jpg"
    return fmt


def extract_and_rewrite_markdown_images(
    md_content: str,
    images_dir: str,
    image_prefix: str = "img",
) -> tuple[str, list[str]]:
    output_dir = Path(images_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_paths: list[str] = []
    image_counter = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal image_counter
        alt = match.group("alt") or "Image"
        fmt = _normalize_ext(match.group("fmt"))
        b64_data = match.group("b64")
        image_counter += 1
        image_name = f"{image_prefix}_{image_counter:04d}.{fmt}"
        image_path = output_dir / image_name

        try:
            raw = base64.b64decode(b64_data, validate=True)
        except (binascii.Error, ValueError):
            return match.group(0)

        image_path.write_bytes(raw)
        image_paths.append(str(image_path.resolve()))
        # Use POSIX-style path for markdown link portability.
        md_path = image_path.as_posix()
        return f"![{alt}]({md_path})"

    rewritten = _DATA_IMAGE_RE.sub(repl, md_content)
    return rewritten, image_paths
