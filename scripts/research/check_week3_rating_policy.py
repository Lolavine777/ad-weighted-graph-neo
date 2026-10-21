"""Check the declared Week 3 execution policy before sheet reconciliation.

This is a policy/provenance preflight, not authentication of human confirmation.
The existing reconciler validates the full record bindings and numeric ratings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "docs/research/ratings/week3-2026-10-02"


def check(directory: Path) -> None:
    policy_path = directory / "execution-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    reference = {
        "policy_id": policy["policy_id"],
        "version": policy["version"],
        "path": "execution-policy.json",
        "sha256": digest,
    }
    confirmation = json.loads(
        (directory / "shared-review-confirmation.json").read_text(encoding="utf-8")
    )
    if confirmation["execution_policy"] != {
        "path": "execution-policy.json",
        "sha256": digest,
    }:
        raise ValueError("Confirmation does not bind the current policy bytes")
    archive = directory / confirmation["original_inputs"]["B"]["path"]
    archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if archive_digest != confirmation["original_inputs"]["B"]["sha256"]:
        raise ValueError("Original B AI archive digest differs")
    sheets = [
        json.loads((directory / name).read_text(encoding="utf-8"))
        for name in ("rater-A.json", "rater-B.json")
    ]
    policies = []
    for sheet in sheets:
        if sheet.get("execution_policy_reference") != reference:
            raise ValueError("Sheet does not bind the current policy bytes")
        mapped = {}
        for row in sheet["likelihood_ratings"]:
            question = row["question_id"]
            if question in mapped:
                raise ValueError(f"Duplicate question: {question}")
            expected = policy["by_mechanism"][row["outcome_work_unit_id"].split(":", 1)[0]]
            actual = row.get("execution_policy", {})
            if (
                actual != expected
                or any(type(v) is not int for v in actual.values())
                or row.get("execution_policy_reference") != reference
                or row["operational_horizon"] != policy["operational_horizon"]
            ):
                raise ValueError(f"Policy mismatch: {question}")
            mapped[question] = actual
        if len(mapped) != 11:
            raise ValueError("Expected 11 conditional-likelihood questions per sheet")
        policies.append(mapped)
    if policies[0] != policies[1]:
        raise ValueError("A/B question policies differ")
    print("PASS: 11 A/B question policies aligned; policy and B archive digests match.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT)
    args = parser.parse_args()
    check(args.directory)


if __name__ == "__main__":
    main()
