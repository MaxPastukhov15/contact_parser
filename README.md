# Contact Parser 2GIS

Universal contact parser for 2GIS. Parses any 2GIS search result URL, extracts company contacts (name, phone, email, website, address) and exports to CSV/XLSX/JSON.

## Features

- Parse any 2GIS search URL (any city, category, query)
- Headless Chrome for anti-bot bypass
- CSV / XLSX / JSON export (with --pipe work only with csv)
- Optional contact enrichment pipeline (filters, dedup, normalization)
- Scrapy spider for company website scraping

## Installation

```bash
git clone <repo> contact_parser
cd contact_parser

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # Linux/Mac

pip install -e .
```

## Usage

### Parse 2GIS

```bash
# Any 2GIS search URL works
terra-dok scrape-2gis -u "https://2gis.ru/moscow/search/коттеджи" --headless
terra-dok scrape-2gis -u "https://2gis.ru/Novosibirsk/search/строительные компании" -f csv -o output/

# Custom output filename
terra-dok scrape-2gis -u "https://2gis.ru/novosibirsk/search/стройка" --headless -n novosibirsk_stroika
```

### Parse + Enrichment Pipeline

```bash
# Parse 2GIS and run contact enrichment (filters, dedup, normalization)
terra-dok scrape-2gis -u "https://2gis.ru/moscow/search/коттеджи" --headless --pipe
```

### Scrape Company Websites

```bash
# Run Scrapy spider on company websites
terra-dok run-scraper --file path/to/contacts.csv
```

## CLI Reference

### `terra-dok scrape-2gis`

| Flag | Description | Default |
|------|-------------|---------|
| `-u, --urls` | 2GIS search URLs (one or more) | *required* |
| `-o, --output-dir` | Output directory for CSV | `maps_data/parsed_2gis/` |
| `-f, --format` | Output format: csv, xlsx, json | `csv` |
| `-n, --name` | Output filename without extension | `result` |
| `--headless` | Run Chrome in headless mode | off |
| `--max-records` | Max records per URL | `1000` |
| `--pipe` | Run enrichment pipeline after parsing | off |

### `terra-dok run-scraper`

| Flag | Description | Default |
|------|-------------|---------|
| `--file` | Path to contacts CSV | `maps_data/contacts/final_2gis.csv` |

## Project Structure

```
contact_parser/
├── src/
│   ├── cli/
│   │   ├── app.py                  # Unified CLI (terra-dok)
│   │   ├── scrape_2gis.py          # 2GIS parser command
│   │   └── run_scraper_cmd.py      # Scrapy spider command
│   ├── vendor/
│   │   └── parser2gis/             # Embedded 2GIS parser (pydantic v2)
│   │       ├── main.py             # CLI entry, argparse
│   │       ├── config.py           # Configuration model
│   │       ├── cli/app.py          # CLI app wrapper
│   │       ├── runner/cli.py       # CLIRunner
│   │       ├── parser/             # Page parsers (main, firm, in_building)
│   │       ├── chrome/             # Chrome DevTools Protocol
│   │       ├── writer/             # CSV/XLSX/JSON writers
│   │       └── logger/             # Logging setup
│   ├── pipelines/
│   │   └── parser2gis_pipe.py      # Contact enrichment pipeline
│   ├── companies_website/
│   │   ├── run_scraper.py          # Scrapy runner
│   │   └── core/website_scraper.py # CompanyWebsiteSpider
│   ├── imitators/                  # B2B catalog spiders
│   ├── api_parser/                 # 2GIS API parser
│   └── configs/                    # Settings, scraper config
└── pyproject.toml
```

## Output Format

| Column | Description |
|--------|-------------|
| Company name | Legal or trade name |
| Description | Brief company description |
| Category | Construction / Architecture / Design / Restoration |
| Rubric | Source rubric |
| Email | Corporate email (info@, sales@ preferred) |
| Phone | Format `7-xxx-xxx-xx-xx` |
| Website | Main page URL |
| Region | City / region |
| Address | Physical address |

## Credits

2GIS parser core based on [interlark/parser-2gis](https://github.com/interlark/parser-2gis) by Andy Trofimov.
