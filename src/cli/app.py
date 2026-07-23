"""Unified CLI for lead generation.

Provides two commands:
- ``scrape-2gis`` — parse 2GIS search results via Chrome, export to CSV/XLSX/JSON.
- ``run-scraper``  — run Scrapy spider to scrape company websites.

Entry point is registered in pyproject.toml as ``terra-dok``.
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="terra-dok",
        description="Contact parser for B2B lead generation",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ── scrape-2gis ────────────────────────────────────────
    p2gis = sub.add_parser(
        "scrape-2gis",
        help="Parse 2GIS via Chrome → CSV → (optional) contacts pipeline",
    )
    p2gis.add_argument(
        "-u", "--urls",
        nargs="+", required=True,
        help="2GIS search result URL(s)",
    )
    p2gis.add_argument(
        "-o", "--output-dir", default=None,
        help="Output directory for CSV (default: maps_data/parsed_2gis/)",
    )
    p2gis.add_argument(
        "-f", "--format",
        choices=["csv", "xlsx", "json"], default="csv",
        help="Output file format (default: csv)",
    )
    p2gis.add_argument(
        "-n", "--name", default=None,
        help="Output filename without extension (default: result)",
    )
    p2gis.add_argument(
        "--headless", action="store_true",
        help="Run Chrome in headless mode",
    )
    p2gis.add_argument(
        "--max-records", type=int, default=1000,
        help="Max records per URL (default: 1000)",
    )
    p2gis.add_argument(
        "--pipe", action="store_true",
        help="Run contact enrichment pipeline after parsing",
    )

    # ── run-scraper ────────────────────────────────────────
    p_scraper = sub.add_parser(
        "run-scraper",
        help="Scrapy spider for company websites",
    )
    p_scraper.add_argument(
        "--file", default=None,
        help="Path to contacts CSV (default: maps_data/contacts/final_2gis.csv)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "scrape-2gis":
        from src.cli.scrape_2gis import run_scrape_2gis
        run_scrape_2gis(args)

    elif args.command == "run-scraper":
        from src.cli.run_scraper_cmd import run_scraper_cmd
        run_scraper_cmd(args)
