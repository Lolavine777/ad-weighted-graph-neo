"""Command-Line Interface (CLI) for reproducible path ranking evaluation.

Allows running:
    wire JSON -> validation -> replay -> assessment -> ranking -> result JSON
without requiring BloodHound runtime, Neo4j, or live telemetry.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.engine.ranking import (
    PathRankingEngine,
    RankingEngineError,
)
from src.engine.ranking.orchestration import evaluate_search_candidates


def run_ranking_cli(argv: list[str] | None = None) -> int:
    """CLI entry point for running whole-path evaluation and ranking."""
    parser = argparse.ArgumentParser(
        description="Path Ranking Engine CLI - Specification v1.0.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using separate query and candidates files:
  python -m src.engine.ranking.cli --query path/to/query.json --candidates path/to/candidates.json

  # Using a combined payload containing both "query" and "candidates":
  python -m src.engine.ranking.cli --input path/to/combined.json --output result.json

  # Processing from stdin:
  cat combined.json | python -m src.engine.ranking.cli --input -
""",
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        help="Path to JSON file containing PathRankingQuery payload (or '-' for stdin).",
    )
    parser.add_argument(
        "--candidates",
        "-c",
        type=str,
        help="Path to JSON file containing list of candidate envelopes.",
    )
    parser.add_argument(
        "--search-candidates",
        type=str,
        help="Path to JSON array of #145 PathResult records and explicit target/action bindings.",
    )
    parser.add_argument(
        "--graph",
        type=str,
        help="Optional canonical Graph JSON file used to resolve exact edge IDs and provenance.",
    )
    parser.add_argument(
        "--action-mapping",
        type=str,
        help="JSON object for unique techniques or ordered JSON array of action IDs per step.",
    )
    parser.add_argument(
        "--coverage",
        type=str,
        help="JSON search coverage metadata from the candidate generator.",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        help="Path to combined JSON file with keys 'query' (or query fields) and 'candidates'.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Path to output JSON file (defaults to stdout).",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indentation for JSON output (default: 2).",
    )

    args = parser.parse_args(argv)

    def read_json_file(path: str) -> Any:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    try:
        if args.search_candidates:
            if args.input or args.candidates or not args.query:
                sys.stderr.write(
                    "Error: --search-candidates requires --query and cannot be combined with "
                    "--input or --candidates.\n"
                )
                return 1
            query_data = read_json_file(args.query)
            if isinstance(query_data, dict) and isinstance(query_data.get("query"), dict):
                query_data = query_data["query"]
            candidates_data = read_json_file(args.search_candidates)
            if not isinstance(candidates_data, list):
                sys.stderr.write("Error: search candidates file must contain a JSON array.\n")
                return 1
            graph_data = read_json_file(args.graph) if args.graph else None
            mapping_data = read_json_file(args.action_mapping) if args.action_mapping else None
            if mapping_data is not None and not isinstance(mapping_data, (dict, list)):
                sys.stderr.write(
                    "Error: action mapping file must contain a JSON object or ordered JSON array.\n"
                )
                return 1
            coverage_data = read_json_file(args.coverage) if args.coverage else None
            if coverage_data is not None and not isinstance(coverage_data, dict):
                sys.stderr.write("Error: coverage file must contain a JSON object.\n")
                return 1
            result = evaluate_search_candidates(
                query_data,
                candidates_data,
                action_mapping=mapping_data,
                canonical_graph=graph_data,
                coverage=coverage_data,
            )
            output_str = result["encoded_json"]
            if args.output:
                Path(args.output).write_text(output_str, encoding="utf-8")
            else:
                sys.stdout.write(output_str + "\n")
            return 0

        query_data: Any = None
        candidates_data: list[Any] = []
        coverage_data: Any = None

        if args.input:
            if args.input == "-":
                raw_input = sys.stdin.read()
            else:
                raw_input = Path(args.input).read_text(encoding="utf-8")
            combined = json.loads(raw_input)
            if not isinstance(combined, dict):
                sys.stderr.write("Error: combined input must be a JSON object.\n")
                return 1

            if "query" in combined and "candidates" in combined:
                query_data = combined["query"]
                candidates_data = combined["candidates"]
                coverage_data = combined.get("coverage")
            elif "query_metadata" in combined and "candidates" in combined:
                candidates_data = combined["candidates"]
                coverage_data = combined.get("coverage")
                query_data = {k: v for k, v in combined.items() if k != "candidates"}
            else:
                sys.stderr.write(
                    "Error: combined input must contain 'candidates' and query components.\n"
                )
                return 1

        elif args.query:
            if args.query == "-":
                raw_query = sys.stdin.read()
            else:
                raw_query = Path(args.query).read_text(encoding="utf-8")
            parsed_query = json.loads(raw_query)

            if isinstance(parsed_query, dict) and "candidates" in parsed_query:
                candidates_data = parsed_query["candidates"]
                coverage_data = parsed_query.get("coverage")
                query_data = {k: v for k, v in parsed_query.items() if k != "candidates"}
            else:
                query_data = parsed_query

            if args.candidates:
                raw_cand = Path(args.candidates).read_text(encoding="utf-8")
                candidates_data = json.loads(raw_cand)
                if not isinstance(candidates_data, list):
                    sys.stderr.write("Error: candidates file must contain a JSON array.\n")
                    return 1
        else:
            parser.print_help()
            return 1

        engine = PathRankingEngine(version="1.0.0")
        result = engine.evaluate(
            query_payload=query_data,
            candidates=candidates_data,
            upstream_coverage=coverage_data,
        )

        output_str = result["encoded_json"]

        if args.output:
            Path(args.output).write_text(output_str, encoding="utf-8")
        else:
            sys.stdout.write(output_str + "\n")

        return 0

    except RankingEngineError as err:
        sys.stderr.write(f"Validation/Ranking Error: {err}\n")
        return 2
    except Exception as err:
        sys.stderr.write(f"System Error: {err}\n")
        return 3


if __name__ == "__main__":
    sys.exit(run_ranking_cli())
