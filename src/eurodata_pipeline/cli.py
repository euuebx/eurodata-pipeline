"""Command-line entry point for running the ingestion pipeline."""
import argparse
import json
import logging

from .config import settings
from .db import SessionLocal, create_tables
from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest ECB exchange-rate data into the configured database.")
    parser.add_argument("--start-date", default=settings.ecb_start_date, help="Start date YYYY-MM-DD (default from ECB_START_DATE)")
    parser.add_argument("--end-date", default=None, help="Optional end date YYYY-MM-DD")
    parser.add_argument("--timeout", type=int, default=settings.ecb_timeout_seconds, help="HTTP timeout in seconds")
    parser.add_argument("--verbose", action="store_true", help="Enable informational logs")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    create_tables()
    with SessionLocal() as db:
        result = run_pipeline(db, start_date=args.start_date, end_date=args.end_date, timeout=args.timeout)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
