"""Read-only SEAMLESS evidence probe for research #200, not attack-path search.

Fixed record locators require the pinned snapshot. Membership combines Members
and PrimaryGroupSid, including duplicate records, and is checked against the
canonical parser. Being outside six role groups does not prove low privilege.
Output uses locators/roles only; no names, SIDs, DN, SPNs or secret material.
Runtime access checks, recovery and attack success are not observed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.manifest import load_manifest, verify_manifest  # noqa: E402
from src.parser import ErrorPolicy, IdentityNormalizer, ManifestRawDataLoader  # noqa: E402
from src.parser.adapters import adapt_bloodhound_v3_records  # noqa: E402
from src.parser.cli import load_time_policy  # noqa: E402
from src.parser.well_known_principals import boundary_group  # noqa: E402

KINDS = ("users", "groups", "computers", "domains", "ous", "gpos")
SNAPSHOT_ID = "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"


def analyze(raw_dir: Path, manifest_path: Path, graph_path: Path) -> dict:
    manifest = load_manifest(manifest_path)
    if manifest["snapshot_id"] != SNAPSHOT_ID:
        raise ValueError("Fixed locators require pinned SEAMLESS")
    if verify_manifest(raw_dir, manifest):
        raise ValueError("Raw does not match manifest")
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    if graph["metadata"]["snapshot_id"] != SNAPSHOT_ID:
        raise ValueError("Graph snapshot differs from raw")
    data = {}
    for entry in manifest["files"]:
        envelope = json.loads((raw_dir / entry["relative_path"]).read_text(encoding="utf-8-sig"))
        kind = next(k for k in KINDS if k in envelope)
        data[kind] = envelope[kind]
    if set(data) != set(KINDS):
        raise ValueError("Expected all six collections")

    objects, locators, aliases = {}, {}, {}
    identity_locators = defaultdict(list)
    rows = []
    for kind, records in data.items():
        for i, row in enumerate(records):
            key = row["ObjectIdentifier"].casefold()
            locator = f"{kind}#/{kind}/{i}"
            if key in objects and not locators[key].startswith(kind + "#/"):
                raise ValueError("Conflicting raw kinds")
            objects.setdefault(key, row)
            locators.setdefault(key, locator)
            identity_locators[key].append(locator)
            rows.append((key, locator, row))
            for value in (row["ObjectIdentifier"], row.get("Properties", {}).get("objectid")):
                if value:
                    token = value.casefold()
                    if token in aliases and aliases[token] != key:
                        raise ValueError("Ambiguous raw alias")
                    aliases[token] = key
    loader = ManifestRawDataLoader(
        manifest_path,
        time_policy=load_time_policy(ROOT / "tests/fixtures/ranking/seamless_time_policy.json"),
    )
    normalized = IdentityNormalizer().normalize_records(
        adapt_bloodhound_v3_records(loader.load(raw_dir, error_policy=ErrorPolicy.FAIL_FAST)),
        error_policy=ErrorPolicy.FAIL_FAST,
    )
    for record in normalized:
        key = record.raw.provenance["record_id"].casefold()
        if key in objects:
            token = record.id.casefold()
            if token in aliases and aliases[token] != key:
                raise ValueError("Ambiguous canonical binding")
            aliases[token] = key

    def resolve(value):
        if isinstance(value, dict):
            for field in ("MemberId", "ObjectIdentifier", "ObjectId", "Guid"):
                if field in value:
                    return resolve(value[field])
            raise ValueError("Unsupported reference")
        if not isinstance(value, str):
            raise ValueError("Unsupported reference type")
        token = value.casefold()
        if token in aliases:
            return aliases[token]
        boundary = boundary_group(value)
        return boundary[0].casefold() if boundary else token

    membership, member_evidence = defaultdict(set), defaultdict(list)
    for i, group in enumerate(data["groups"]):
        parent = resolve(group["ObjectIdentifier"])
        for j, member in enumerate(group.get("Members", [])):
            child = resolve(member)
            membership[child].add(parent)
            member_evidence[child, parent].append(f"groups#/groups/{i}/Members/{j}")
    for kind in ("users", "computers"):
        for i, row in enumerate(data[kind]):
            if row.get("PrimaryGroupSid"):
                child, parent = resolve(row["ObjectIdentifier"]), resolve(row["PrimaryGroupSid"])
                membership[child].add(parent)
                member_evidence[child, parent].append(f"{kind}#/{kind}/{i}/PrimaryGroupSid")
    raw_pairs = {(s, t) for s, targets in membership.items() for t in targets}
    canonical_pairs = {
        (resolve(e["source"]), resolve(e["target"]))
        for e in graph["edges"]
        if e["kind"] == "MemberOf"
    }
    if raw_pairs != canonical_pairs:
        raise ValueError("Raw membership union differs from canonical")
    pair_kinds = defaultdict(set)
    for edge in graph["edges"]:
        pair_kinds[resolve(edge["source"]), resolve(edge["target"])].add(edge["kind"])
    closures = {}

    def closure(key):
        if key not in closures:
            seen, queue = {key}, deque([key])
            while queue:
                for parent in membership[queue.popleft()] - seen:
                    seen.add(parent)
                    queue.append(parent)
            closures[key] = seen
        return closures[key]

    def path(start, goal):
        queue, previous = deque([start]), {start: None}
        while queue:
            current = queue.popleft()
            if current == goal:
                result = []
                while previous[current] is not None:
                    source = previous[current]
                    result.append(
                        {
                            "source": locators.get(source, "unresolved"),
                            "target": locators.get(current, "unresolved"),
                            "evidence": sorted(member_evidence[source, current]),
                        }
                    )
                    current = source
                return list(reversed(result))
            for parent in sorted(membership[current]):
                if parent not in previous:
                    previous[parent] = current
                    queue.append(parent)
        return None

    domain = resolve(data["domains"][0]["ObjectIdentifier"])
    role_ids = {
        domain + "-512": "DA",
        domain + "-519": "EA",
        domain + "-516": "DC",
        domain + "-521": "RODC",
        "s-1-5-9": "EnterpriseDC",
        "s-1-5-32-544": "Administrators",
    }
    roles = {}
    for key in objects:
        match = re.search(r"s-\d(?:-\d+)+$", key)
        if locators[key].startswith("groups#/") and match and match.group() in role_ids:
            roles[key] = role_ids[match.group()]

    def describe(key):
        key = resolve(key)
        return {
            "locator": locators.get(key, "unresolved"),
            "resolved": key in objects,
            "enabled": objects.get(key, {}).get("Properties", {}).get("enabled"),
            "membership_roles": sorted({roles[g] for g in closure(key) if g in roles}),
        }

    acl = [
        {
            "target": key,
            "holder": resolve(a["PrincipalSID"]),
            "right": a["RightName"],
            "ace_type": a.get("AceType"),
            "locator": f"{locator}/Aces/{i}",
        }
        for key, locator, row in rows
        for i, a in enumerate(row.get("Aces", []))
    ]
    write_pairs = {(a["holder"], a["target"]) for a in acl if a["right"] == "WriteDacl"}
    generic_pairs = {(a["holder"], a["target"]) for a in acl if a["right"] == "GenericAll"}

    def ace_summary(a):
        return {
            "target": locators[a["target"]],
            "ace": a["locator"],
            "right": a["right"],
            "holder": describe(a["holder"]),
        }

    extra = {}
    for right in ("Owner", "WriteOwner", "GenericWrite"):
        matches = [a for a in acl if a["right"] == right]
        extra[right] = {
            "ace_count": len(matches),
            "same_pair_WriteDacl_aces": sum(
                (a["holder"], a["target"]) in write_pairs for a in matches
            ),
            "holders": [describe(k) for k in sorted({a["holder"] for a in matches})],
            "unresolved_holders": sum(a["holder"] not in objects for a in matches),
            "outside_six_roles": [
                ace_summary(a)
                for a in matches
                if a["holder"] in objects and not describe(a["holder"])["membership_roles"]
            ],
        }

    def contained(start):
        seen, queue, computers = set(), deque([start]), set()
        while queue:
            key = queue.popleft()
            if key in seen:
                continue
            seen.add(key)
            row = objects.get(key, {})
            computers.update(resolve(x) for x in row.get("Computers", []))
            queue.extend(resolve(x) for x in row.get("ChildOus", []))
        return sorted(locators.get(k, "unresolved") for k in computers)

    links = [
        {
            "container": f"{kind}#/{kind}/{i}",
            "locator": f"{kind}#/{kind}/{i}/Links/{j}",
            "gpo": describe(link["Guid"]),
            "is_enforced": link.get("IsEnforced"),
            "raw_containment_computers": contained(resolve(row["ObjectIdentifier"])),
        }
        for kind in ("domains", "ous")
        for i, row in enumerate(data[kind])
        for j, link in enumerate(row.get("Links", []))
    ]
    dcom = [
        {
            "target": describe(row["ObjectIdentifier"]),
            "holder": describe(member),
            "locator": f"computers#/computers/{i}/DcomUsers/{j}",
            "same_pair_canonical_kinds": sorted(
                pair_kinds[resolve(member), resolve(row["ObjectIdentifier"])]
            ),
        }
        for i, row in enumerate(data["computers"])
        for j, member in enumerate(row.get("DcomUsers", []))
    ]
    users = data["users"]
    da = next(k for k, role in roles.items() if role == "DA")
    preauth = [i for i, r in enumerate(users) if r["Properties"].get("dontreqpreauth") is True]
    spn = [i for i, r in enumerate(users) if r["Properties"].get("serviceprincipalnames")]
    selected = {}
    for label, i in {
        "ASREP": 1700,
        "Kerberoasting": 11,
        "KerberosResetTarget": 917,
        "RBCDActor": 1580,
    }.items():
        key = resolve(users[i]["ObjectIdentifier"])
        selected[label] = {
            **describe(key),
            "preauth_off": users[i]["Properties"].get("dontreqpreauth"),
            "has_spn": bool(users[i]["Properties"].get("serviceprincipalnames")),
            "member_path_to_DA": path(key, da),
        }
    kerb, reset = resolve(users[11]["ObjectIdentifier"]), resolve(users[917]["ObjectIdentifier"])
    reset_aces = [
        a
        for a in acl
        if a["target"] == reset and a["right"] == "GenericAll" and a["holder"] in closure(kerb)
    ]
    holders = {a["holder"] for a in reset_aces}
    selected["Kerberoasting"]["reset_routes"] = [
        {**ace_summary(a), "membership_prefix": path(kerb, a["holder"])} for a in reset_aces
    ]
    selected["Kerberoasting"]["enabled_users_sharing_reset_holder"] = sum(
        r["Properties"].get("enabled") is True
        and bool(holders & closure(resolve(r["ObjectIdentifier"])))
        for r in users
    )
    selected["Kerberoasting"]["other_initial_users_sharing_reset_prefix"] = [
        {
            "actor": describe(users[i]["ObjectIdentifier"]),
            "prefix_to_holder": path(resolve(users[i]["ObjectIdentifier"]), h),
        }
        for i in (1580, 2201)
        for h in sorted(holders)
        if h in closure(resolve(users[i]["ObjectIdentifier"]))
    ]
    rbcd, target = (
        resolve(users[1580]["ObjectIdentifier"]),
        resolve(data["computers"][27]["ObjectIdentifier"]),
    )
    selected["RBCDActor"].update(
        {
            "target": describe(target),
            "canonical_target_kinds": sorted(pair_kinds[rbcd, target]),
            "direct_GenericAll": [
                a["locator"]
                for a in acl
                if a["holder"] == rbcd and a["target"] == target and a["right"] == "GenericAll"
            ],
            "service_account_takeover_candidates": [
                {
                    **ace_summary(a),
                    "target": describe(a["target"]),
                    "membership_prefix": path(rbcd, a["holder"]),
                    "canonical_holder_target_kinds": sorted(pair_kinds[a["holder"], a["target"]]),
                }
                for a in acl
                if a["right"] == "GenericAll"
                and a["holder"] in closure(rbcd)
                and locators[a["target"]].startswith("users#/")
                and objects[a["target"]]["Properties"].get("enabled") is True
                and objects[a["target"]]["Properties"].get("serviceprincipalnames")
            ],
        }
    )
    replication = [
        a
        for a in acl
        if a["target"] == domain
        and a["right"] == "ExtendedRight"
        and a["ace_type"] in {"GetChanges", "GetChangesAll", "GetChangesInFilteredSet"}
    ]
    combined = [
        k
        for k in objects
        if {"GetChanges", "GetChangesAll"}
        <= {a["ace_type"] for a in replication if a["holder"] in closure(k)}
    ]
    all_extended = [
        a
        for a in acl
        if a["right"] == "ExtendedRight"
        and a["ace_type"] == "All"
        and locators[a["target"]].startswith("users#/")
    ]
    c0 = resolve(data["computers"][0]["ObjectIdentifier"])
    return {
        "snapshot_id": SNAPSHOT_ID,
        "manifest_verified": True,
        "probe_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "graph_sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
        "graph_metadata": graph["metadata"],
        "counts": {k: len(v) for k, v in data.items()},
        "canonical_membership_union_match": True,
        "membership_filter": "DA/EA/Administrators/DC/RODC/EnterpriseDC; not token access check",
        "role_groups": [
            {"role": role, "locator": locators[k]} for k, role in sorted(roles.items())
        ],
        "duplicate_identity_records": [v for v in identity_locators.values() if len(v) > 1],
        "raw_ace_counts": dict(sorted(Counter(a["right"] for a in acl).items())),
        "additional_rights": extra,
        "gpo_rights": [ace_summary(a) for a in acl if locators[a["target"]].startswith("gpos#/")],
        "gpo_links": links,
        "dcom": dcom,
        "user_ExtendedRight_All": {
            "ace_count": len(all_extended),
            "holders": [describe(k) for k in sorted({a["holder"] for a in all_extended})],
            "same_pair_GenericAll_aces": sum(
                (a["holder"], a["target"]) in generic_pairs for a in all_extended
            ),
        },
        "computer_haslaps_counts": dict(
            Counter(str(r["Properties"].get("haslaps")) for r in data["computers"])
        ),
        "replication": {
            "aces": [{**ace_summary(a), "permission": a["ace_type"]} for a in replication],
            "same_actor_membership_holders": [describe(k) for k in combined],
            "outside_six_roles": [
                describe(k) for k in combined if not describe(k)["membership_roles"]
            ],
        },
        "roasting": {
            "preauth_off": len(preauth),
            "spn_nonempty": len(spn),
            "intersection": len(set(preauth) & set(spn)),
            "preauth_off_enabled_DA_members": [
                f"users#/users/{i}"
                for i in preauth
                if users[i]["Properties"].get("enabled") is True
                and da in closure(resolve(users[i]["ObjectIdentifier"]))
            ],
            "passwordnotreqd_true": sum(
                r["Properties"].get("passwordnotreqd") is True for r in users
            ),
        },
        "selected_prior_candidates": selected,
        "empty_fields": {
            f"{k}.{f}": {
                "missing": sum(f not in r for r in data[k]),
                "nonempty": sum(bool(r.get(f)) for r in data[k]),
            }
            for k, f in (
                ("users", "AllowedToDelegate"),
                ("users", "HasSIDHistory"),
                ("computers", "AllowedToDelegate"),
                ("computers", "AllowedToAct"),
                ("computers", "Sessions"),
                ("domains", "Trusts"),
            )
        },
        "unconstrained_receivers": [
            describe(r["ObjectIdentifier"])
            for r in data["computers"]
            if r["Properties"].get("unconstraineddelegation") is True
        ],
        "canonical_C0_AdminTo": [
            {
                "holder": describe(e["source"]),
                "provenance_attributes": sorted({p["attribute"] for p in e.get("provenance", [])}),
                "derivation_version": e.get("derivation", {}).get("version"),
                "derivation_operations": sorted(
                    {
                        s["operation"]
                        for p in e.get("derivation", {}).get("paths", [])
                        for s in p.get("steps", [])
                    }
                ),
            }
            for e in graph["edges"]
            if e["kind"] == "AdminTo" and resolve(e["target"]) == c0
        ],
        "canonical_fact_projection": {
            f: sum(f in n for n in graph["nodes"])
            for f in ("dontreqpreauth", "serviceprincipalnames", "hasspn")
        },
        "scope": (
            "Raw/reference screening; no runtime access check, "
            "new engine actions or success measurement"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw/SEAMLESS")
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "data/samples/manifests/seamless-raw-v1.json"
    )
    parser.add_argument(
        "--graph", type=Path, default=ROOT / "reports/generated/week4-200/canonical.json"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/generated/week4-200/field-screening-probe.json",
    )
    args = parser.parse_args()
    try:
        report = analyze(args.raw_dir, args.manifest, args.graph)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (ValueError, KeyError, OSError, StopIteration) as error:
        print(f"Probe failed: {type(error).__name__}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {"status": "verified", "snapshot": SNAPSHOT_ID, "dcom_records": len(report["dcom"])}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
