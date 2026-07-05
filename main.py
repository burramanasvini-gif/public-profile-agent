#!/usr/bin/env python3
"""
Public Profile Agent
=====================
CLI entry point.

Usage:
    python main.py "Satya Nadella"
    python main.py "Sachin Tendulkar" --outdir output
    python main.py "Rachael" --no-pdf

Pipeline:
    1. scraper.gather_sources()     -> free web scraping (DuckDuckGo + Wikipedia)
    2. synthesizer.synthesize_profile() -> Claude turns raw text into structured JSON
    3. report.render_markdown() / render_pdf() -> polished, shareable output

Every run writes, under <outdir>/<person_name>/:
    raw_sources.json   the scraped evidence (for auditing / transparency)
    profile.json       the structured profile the AI produced
    profile.md         human-readable Markdown report
    profile.pdf        polished PDF report (unless --no-pdf)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from src.report import render_markdown, render_pdf  # noqa: E402
from src.scraper import gather_sources  # noqa: E402
from src.synthesizer import synthesize_profile  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("profile_agent.main")


def slugify(name: str) -> str:
    return "_".join(name.strip().split())


def run(person_name: str, outdir: str, make_pdf: bool = True) -> Path:
    load_dotenv()

    person_dir = Path(outdir) / slugify(person_name)
    person_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Step 1/3: Gathering public sources for %r ...", person_name)
    bundle = gather_sources(person_name)
    logger.info("Collected %d source(s).", len(bundle.sources))

    with open(person_dir / "raw_sources.json", "w", encoding="utf-8") as f:
        json.dump(
            [{"title": s.title, "url": s.url, "text": s.text} for s in bundle.sources],
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.info("Step 2/3: Synthesizing structured profile with Claude ...")
    profile = synthesize_profile(person_name, bundle)

    with open(person_dir / "profile.json", "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    logger.info("Step 3/3: Rendering report ...")
    md = render_markdown(profile)
    (person_dir / "profile.md").write_text(md, encoding="utf-8")

    if make_pdf:
        render_pdf(profile, str(person_dir / "profile.pdf"))

    logger.info("Done. Output written to %s", person_dir.resolve())
    return person_dir


def main():
    parser = argparse.ArgumentParser(
        description="Generate a structured public profile report for a named person."
    )
    parser.add_argument("name", help="Full name of the person to research, e.g. 'Satya Nadella'")
    parser.add_argument(
        "--outdir", default="output", help="Directory to write results into (default: output/)"
    )
    parser.add_argument(
        "--no-pdf", action="store_true", help="Skip PDF generation (Markdown + JSON only)"
    )
    args = parser.parse_args()

    run(args.name, args.outdir, make_pdf=not args.no_pdf)


if __name__ == "__main__":
    main()
