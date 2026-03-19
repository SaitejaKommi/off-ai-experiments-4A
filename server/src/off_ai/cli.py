"""
cli.py – Command-line interface for the Food Intelligence Pipeline

Usage
-----
    python -m off_ai "High protein vegan snack under 200 calories"
    python -m off_ai "Healthier alternative to Nutella"
    python -m off_ai "Low sodium cereal for diabetics"
    python -m off_ai --json "organic high fibre cereal"
"""

from __future__ import annotations

import argparse
import json
import sys

from .pipeline import FoodIntelligencePipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="off_ai",
        description="Open Food Facts AI Food Intelligence Engine",
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Natural language food query (prompted if omitted)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        metavar="N",
        help="Maximum number of products to return (default: 10)",
    )

    args = parser.parse_args(argv)

    if not args.query:
        try:
            args.query = input("Enter your food query: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.", file=sys.stderr)
            return 1

    if not args.query:
        parser.print_help()
        return 1

    pipeline = FoodIntelligencePipeline(max_results=args.max_results)
    result = pipeline.run(args.query)

    if args.output_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
