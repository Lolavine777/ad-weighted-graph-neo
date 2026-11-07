"""Compare independent T1/T2 ratings with neo-c-v1 and reprice the fixed candidate programs.

The raters only saw the rubric and a plain description of each technique, never the table.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from statistics import median

from scripts.neo_cost_sensitivity import compare
from src.engine.batch import _atomic_json
from src.engine.query_cli import digest
from src.engine.ranking.effort_profiles import load_effort_profile

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "reports/generated/neo-C-sensitivity-20261023/analysis-verified"
COSTS = range(5)  # c = T1 + T2 - 2 with T1, T2 in 1..3


def classes_from(ratings):
    return {
        technique: {"t1": r["t1"], "t2": r["t2"], "cost": r["t1"] + r["t2"] - 2}
        for technique, r in ratings.items()
    }


def weighted_kappa(left, right):
    """Cohen's kappa with quadratic weights on the C scale 0 to 4."""
    n = len(left)
    observed = sum((a - b) ** 2 for a, b in zip(left, right, strict=True)) / n
    left_counts, right_counts = Counter(left), Counter(right)
    expected = sum(
        left_counts[a] * right_counts[b] * (a - b) ** 2 for a in COSTS for b in COSTS
    ) / (n * n)
    return None if expected == 0 else 1 - observed / expected


def krippendorff_interval(table):
    """Alpha for complete interval data: rows are items, columns are raters."""
    values = [v for row in table for v in row]
    total = len(values)
    within = sum(
        sum((a - b) ** 2 for a, b in combinations(row, 2)) * 2 / (len(row) - 1) for row in table
    )
    between = sum((a - b) ** 2 for a, b in combinations(values, 2)) * 2
    return 1 - (within / total) / (between / (total * (total - 1)))


def unique_pairs(evidence):
    pairs = {}
    for path in sorted(evidence.glob("*.json")):
        if path.name == "results.json":
            continue
        row = json.loads(path.read_text(encoding="utf-8"))
        pairs.setdefault((row["source"], row["target"]), row["programs"])
    return pairs


def reprice_all(pairs, classes):
    evaluated = [r for r in (compare(p, classes) for p in pairs.values()) if r is not None]
    return {
        "witness_pairs": len(evaluated),
        **{
            key: sum(bool(r[key]) if key != "strict_rank_reversals" else r[key] for r in evaluated)
            for key in (
                "best_C_changed",
                "best_set_changed",
                "best_set_disjoint",
                "top_3_set_changed",
                "strict_rank_reversals",
            )
        },
        "pairs_with_strict_reversals": sum(r["strict_rank_reversals"] > 0 for r in evaluated),
    }


def analyse(ratings_file, evidence):
    raw = json.loads(ratings_file.read_text(encoding="utf-8"))
    author = load_effort_profile("neo-c-v1")["classes"]
    techniques = sorted(author)
    raters = {}
    for name, rater in raw["raters"].items():
        if set(rater["ratings"]) != set(techniques):
            raise ValueError(f"{name} did not rate exactly the neo-c-v1 techniques")
        raters[name] = classes_from(rater["ratings"])
    consensus = {
        t: {
            "t1": round(median(r[t]["t1"] for r in raters.values())),
            "t2": round(median(r[t]["t2"] for r in raters.values())),
        }
        for t in techniques
    }
    raters["consensus"] = classes_from(consensus)
    author_c = [author[t]["cost"] for t in techniques]
    pairs = unique_pairs(evidence)
    report = {
        "version": "neo-effort-rater-agreement/1",
        "ratings_sha256": digest(ratings_file.read_bytes()),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "raters": {name: rater["model"] for name, rater in raw["raters"].items()},
        "consensus": "median of the AI raters' T1 and T2, rounded",
        "C_by_technique": {
            t: {"neo-c-v1": author[t]["cost"], **{n: c[t]["cost"] for n, c in raters.items()}}
            for t in techniques
        },
        "agreement_with_neo_c_v1": {},
        "krippendorff_alpha_interval_C": krippendorff_interval(
            [
                [author[t]["cost"], *(raters[n][t]["cost"] for n in raw["raters"])]
                for t in techniques
            ]
        ),
        "repricing": {"neo-c-v1": reprice_all(pairs, author)},
        "fixed_programs": {"pairs": len(pairs), "evidence": str(evidence.relative_to(ROOT))},
    }
    for name, classes in raters.items():
        rated = [classes[t]["cost"] for t in techniques]
        report["agreement_with_neo_c_v1"][name] = {
            "exact_C": sum(a == b for a, b in zip(author_c, rated, strict=True)),
            "within_one_C": sum(abs(a - b) <= 1 for a, b in zip(author_c, rated, strict=True)),
            "mean_C_difference": sum(b - a for a, b in zip(author_c, rated, strict=True))
            / len(techniques),
            "quadratic_weighted_kappa_C": weighted_kappa(author_c, rated),
        }
        report["repricing"][name] = reprice_all(pairs, classes)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ratings", type=Path, default=ROOT / "reports/neo/effort-rater-ratings.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports/neo/effort-rater-agreement.json"
    )
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    args = parser.parse_args(argv)
    report = analyse(args.ratings, args.evidence)
    _atomic_json(args.output, report)
    print(json.dumps(report["agreement_with_neo_c_v1"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
