#!/usr/bin/env python3
"""SEAMLESS raw-path research probe, 2026-09-28. Python 3.10+, stdlib only.

Run from the repository root:
  python scripts/research/raw_path_probe.py --raw-dir data/raw/SEAMLESS \
    --manifest data/samples/manifests/seamless-raw-v1.json \
    --discover

Output includes raw identities: redirect to ignored reports/generated/.
Discovery selects the unique domain group with RID 512 and orders candidate
computer IDs lexicographically: Source A, Source B, then Source 3 and so on.
Ambiguous/missing target requires --target; explicit --source/--target still work.
Enabled facts for both endpoints are reported separately, never used to prune.

PHƯƠNG PHÁP VÀ VỊ TRÍ TRONG FLOW E2E
1. Week 1 manifest/EDA: read_verified() checks byte count and SHA-256 of three
   required raw files before json.loads(...decode('utf-8-sig')).
   It does not validate all six files or recompute the whole snapshot identity.
2. Data exploration: build_projection() indexes raw IDs and extracts references.
   Group.Members means member -> parent group, not the other way around.
   An ACE on object T means PrincipalSID -> T; the ACE belongs to T's record.
3. Discovery: find_direct_candidates() joins Computer IDs, GenericAll on Users,
   and direct members of the selected group, regardless of enabled state.
4. Exploration: shortest_hops() is breadth-first search (BFS), not Dijkstra.
   Every retained structural relation counts as one hop, including MemberOf.
   A visited set prevents cycles. Sorted edges make tie-breaking reproducible.
5. Alternative: rerun BFS while ignoring only the first edge of the first path.
   This finds one alternative avoiding that edge, not Top-K or all alternatives.
   It is NOT a remediation experiment: raw evidence/derived effects are not rebuilt.
6. Week 2 semantics: a human/research rule must still identify action, requirements
   and effect. This script does not evaluate runtime predicates or produce effects.
7. Week 3 weighting: use these candidates to define scenarios and compare cost
   models. Numeric production cost and validity of complete attack chains remain open.
8. Week 4/5: production search, performance, BloodHound parity and remediation
   evaluation belong to the repository pipeline/engine, not this probe.

RESEARCH BOUNDARY
This is a deliberately limited raw projection, NOT the canonical parser.
Retains User/Group/Computer nodes, MemberOf, and GenericAll/WriteDacl targeting
User or Group. Computer-target ACLs and all other relation kinds are excluded.
No SID normalization, effective group policy, account takeover, inheritance access
checks, credential replay, assumed runtime truth, action cost or goal evaluation.
Same raw node IDs are grouped, with conflicting kind/name rejected; this is not
the repository's full reconciliation contract. Repeated edges retain all locators.
Only endpoints found in the three inputs enter the projection; omissions are counted.
Positive references are candidates under the snapshot SoT policy, not proof of an
executed attack. Group names (including DISTLIST/ADMINGROUP) do not prove groupType.
Raw locators are JSON Pointers into the hash-checked input files.
The snapshot_id in output is a manifest declaration, not independently recomputed.

CONNECTION TO THE EARLIER PROTOTYPE
semantics_probe.py used synthetic facts/actions and invented integer costs.
Its 15 cases test model behavior, not SEAMLESS. This script instead discovers
actual raw paths and evidence without deciding that those paths are executable.
Keep these two types of evidence separate when writing #42 or presenting to mentor.

"""

import argparse
import hashlib
import json
import re
from collections import defaultdict, deque
from pathlib import Path

FILENAMES = {kind: f"20210920185958_{kind}.json" for kind in ("computers", "groups", "users")}


def read_verified(raw_dir, manifest):
    entries = {entry["relative_path"]: entry for entry in manifest["files"]}
    records, verification = {}, []
    for kind, filename in FILENAMES.items():
        expected = entries[filename]
        payload = (raw_dir / filename).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if len(payload) != expected["size_bytes"] or digest != expected["sha256"]:
            raise ValueError(f"Input does not match manifest: {filename}")
        envelope = json.loads(payload.decode("utf-8-sig"))
        records[kind] = envelope[kind]
        verification.append(
            {
                "file": filename,
                "sha256": digest,
                "bytes": len(payload),
                "records": len(records[kind]),
            }
        )
    return records, verification


def build_projection(records):
    nodes = {}
    for plural, kind in (("computers", "Computer"), ("groups", "Group"), ("users", "User")):
        for record in records[plural]:
            sid = record["ObjectIdentifier"]
            node = {"id": sid, "kind": kind, "name": record["Properties"].get("name", sid)}
            if sid in nodes and nodes[sid] != node:
                raise ValueError(f"Conflicting raw identity labels: {sid}")
            nodes[sid] = node
    evidence = defaultdict(list)
    omitted = 0

    def add(source, target, kind, file, pointer):
        nonlocal omitted
        if source not in nodes or target not in nodes:
            omitted += 1
            return
        evidence[source, kind, target].append({"file": file, "pointer": pointer})

    for plural in ("groups", "users"):
        for i, record in enumerate(records[plural]):
            target = record["ObjectIdentifier"]
            if plural == "groups":
                for j, member in enumerate(record.get("Members", [])):
                    add(
                        member["MemberId"],
                        target,
                        "MemberOf",
                        FILENAMES[plural],
                        f"#/{plural}/{i}/Members/{j}",
                    )
            for j, ace in enumerate(record.get("Aces", [])):
                if ace["RightName"] in {"GenericAll", "WriteDacl"}:
                    add(
                        ace["PrincipalSID"],
                        target,
                        ace["RightName"],
                        FILENAMES[plural],
                        f"#/{plural}/{i}/Aces/{j}",
                    )
    adjacency = defaultdict(list)
    for edge in sorted(evidence, key=lambda e: (e[0], e[1], e[2])):
        adjacency[edge[0]].append(edge)
    return nodes, evidence, adjacency, omitted


def find_direct_candidates(nodes, evidence, target):
    """Pure structural join; enabled facts and runtime applicability stay separate."""
    members = {
        source
        for source, kind, destination in evidence
        if kind == "MemberOf" and destination == target
    }
    return [
        edge
        for edge in sorted(evidence)
        if edge[1] == "GenericAll"
        and nodes[edge[0]]["kind"] == "Computer"
        and nodes[edge[2]]["kind"] == "User"
        and edge[2] in members
    ]


def shortest_hops(adjacency, source, target, forbidden=None):
    queue = deque([source])
    parent = {source: None}
    while queue:
        node = queue.popleft()
        if node == target:
            path = []
            while parent[node] is not None:
                edge = parent[node]
                path.append(edge)
                node = edge[0]
            return list(reversed(path))
        for edge in adjacency.get(node, ()):
            if edge == forbidden or edge[2] in parent:
                continue
            parent[edge[2]] = edge
            queue.append(edge[2])
    return None


def collect_enabled_facts(records):
    """Preserve all observations; absent/invalid/conflicting values are not True."""
    facts = defaultdict(list)
    for plural in ("computers", "users"):
        for i, record in enumerate(records[plural]):
            value = record["Properties"].get("enabled")
            facts[record["ObjectIdentifier"]].append(
                {
                    "value": value if type(value) is bool else None,
                    "present": "enabled" in record["Properties"],
                    "file": FILENAMES[plural],
                    "pointer": f"#/{plural}/{i}/Properties",
                    "field": "enabled",
                }
            )
    result = {}
    for identifier, observations in facts.items():
        values = {item["value"] for item in observations}
        if True in values and False in values:
            status = "conflicting"
        elif None in values:
            status = "unknown"
        else:
            status = "true" if True in values else "false"
        result[identifier] = {"status": status, "observations": observations}
    return result


def select_target(nodes, target=None):
    """RID selection is identity selection only, never security-group usability."""
    if target is not None:
        if target not in nodes or nodes[target]["kind"] != "Group":
            raise ValueError("Target must be an observed Group ID")
        return target
    matches = sorted(
        identifier
        for identifier, node in nodes.items()
        if node["kind"] == "Group"
        and re.fullmatch(r"S-1-5-21-[0-9]+-[0-9]+-[0-9]+-512", identifier)
    )
    if len(matches) != 1:
        raise ValueError(
            f"Expected one domain RID-512 Group, found {len(matches)}; supply --target"
        )
    return matches[0]


def analyze(raw_dir, manifest, source=None, target=None, *, discover=False):
    records, verified = read_verified(raw_dir, manifest)
    nodes, evidence, adjacency, omitted = build_projection(records)
    supplied_target = target is not None
    if not discover and (source is None or target is None):
        raise ValueError("Explicit mode requires --source and --target")
    if discover and source is not None:
        raise ValueError("--discover cannot be combined with --source")
    target = select_target(nodes, target)
    enabled = collect_enabled_facts(records)

    def describe(edge):
        s, k, t = edge
        return {
            "source": nodes[s],
            "relationship": k,
            "target": nodes[t],
            "raw_evidence": evidence[edge],
        }

    def describe_source(identifier):
        if identifier not in nodes or nodes[identifier]["kind"] != "Computer":
            raise ValueError("Source must be an observed Computer ID")
        first = shortest_hops(adjacency, identifier, target)
        second = shortest_hops(adjacency, identifier, target, first[0]) if first else None
        return {
            "source": nodes[identifier],
            "shortest_structural_path": None if first is None else [describe(e) for e in first],
            "alternative_avoiding_first_edge": None
            if second is None
            else [describe(e) for e in second],
        }

    candidates = find_direct_candidates(nodes, evidence, target)
    report = {
        "format_version": 2,
        "scope": "raw structural candidates, NOT executable attack paths",
        "declared_snapshot_id": manifest["snapshot_id"],
        "verified_inputs": verified,
        "projection": {
            "nodes": len(nodes),
            "edges": len(evidence),
            "unresolved_reference_occurrences_omitted": omitted,
        },
        "direct_computer_to_target_member_count": len(candidates),
        "direct_candidates": [
            {
                "acl": describe(e),
                "membership": describe((e[2], "MemberOf", target)),
                "enabled_facts": {"source": enabled[e[0]], "target_user": enabled[e[2]]},
            }
            for e in candidates
        ],
        "target": nodes[target],
        "alternative_method": "BFS excluding first path's first edge; not Top-K or remediation",
    }
    if discover:
        sources = sorted({edge[0] for edge in candidates})
        report["selection"] = {
            "target_rule": "explicit --target"
            if supplied_target
            else "unique domain SID RID-512 Group",
            "source_rule": "all direct structural candidate Computer IDs, lexicographic ascending",
            "alias_rule": "first Source A, second Source B, then Source 3, Source 4, ...",
            "enabled_filter": False,
        }
        report["sources"] = [
            {
                "alias": ("Source A", "Source B")[i] if i < 2 else f"Source {i + 1}",
                "source_rank": i + 1,
                **describe_source(identifier),
            }
            for i, identifier in enumerate(sources)
        ]
    else:
        report.update(describe_source(source))
    return report


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--discover", action="store_true", help="Derive target and all source aliases"
    )
    parser.add_argument("--source")
    parser.add_argument("--target", help="Explicit target, also resolves discovery ambiguity")
    args = parser.parse_args()
    if args.discover and args.source is not None:
        parser.error("--discover cannot be combined with --source")
    if not args.discover and (args.source is None or args.target is None):
        parser.error("use --discover or supply both --source and --target")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    try:
        report = analyze(args.raw_dir, manifest, args.source, args.target, discover=args.discover)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
