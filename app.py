"""Command-line entry point for the enterprise match-engine demo."""

import argparse

from demo_mode import run_demo_seed
from pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enterprise match-engine demo")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Initialize a local SQLite database with synthetic seed data and skip live integrations.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.demo:
        run_demo_seed()
    else:
        run_pipeline()


if __name__ == "__main__":
    main()
