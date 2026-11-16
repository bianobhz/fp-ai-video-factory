#!/usr/bin/env python3
"""Create a Brazilian Portuguese neural narration track from a story JSON."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import edge_tts


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("story", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--voice", default="pt-BR-FranciscaNeural")
    parser.add_argument("--rate", default="-4%")
    args = parser.parse_args()

    story = json.loads(args.story.read_text(encoding="utf-8"))
    narration = (story.get("narration") or "").strip()
    if not narration:
        parser.error("O arquivo de história não contém o campo narration.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    await edge_tts.Communicate(
        narration,
        voice=args.voice,
        rate=args.rate,
        volume="+0%",
    ).save(str(args.output))
    print(f"Locução PT-BR salva em: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
