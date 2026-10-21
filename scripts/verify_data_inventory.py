"""Script to verify and reproduce data inventory statistics for Dataset A and Dataset B.

This script parses raw JSON files from:
- Dataset A (NORTH SharpHound and BloodHound-Python)
- Dataset B (Enterprise ad_sampledata: PHANTOM, GHOST, WRAITH)

It computes deterministic counts for raw occurrences and unique relation pairs
for all core M1 entities and edges, verifies duplicate IDs, dangling references,
and effective access rights.
"""

import glob
import json
import os
from collections import Counter

from scripts.eda_dataset_analysis import classify_canrdp_evidence

M1_NODE_KINDS = {
    "user",
    "users",
    "computer",
    "computers",
    "group",
    "groups",
    "domain",
    "domains",
    "gpo",
    "gpos",
    "ou",
    "ous",
}

ACE_NAMES = [
    "GenericAll",
    "WriteDacl",
    "WriteOwner",
    "GenericWrite",
    "Owns",
    "ForceChangePassword",
]


def detect_domain_from_path(file_path: str) -> str:
    """Identify domain group from filename timestamp prefix or content."""
    base = os.path.basename(file_path)
    if base.startswith("20240305110018"):
        return "PHANTOM.CORP"
    if base.startswith("20240305110427"):
        return "GHOST.CORP"
    if base.startswith("20240305111414"):
        return "WRAITH.CORP"
    if "NORTH" in base or "north" in base:
        return "NORTH.SEVENKINGDOMS.LOCAL"
    return "UNKNOWN"


def analyze_dataset(path: str) -> dict:
    """Analyze all JSON files in the given directory path."""
    files = sorted(glob.glob(os.path.join(path, "**/*.json"), recursive=True))
    total_records = 0
    all_unique_ids: set[str] = set()
    m1_unique_ids: set[str] = set()
    file_stats = []

    # Duplicates tracking
    file_duplicate_counts: dict[str, int] = {}
    duplicate_ids_per_domain: dict[str, dict[str, list[str]]] = {}

    # Edge counters overall
    raw_members = 0
    unique_members: set[tuple[str, str]] = set()

    raw_aces = {k: 0 for k in ACE_NAMES}
    unique_aces: dict[str, set[tuple[str, str]]] = {k: set() for k in ACE_NAMES}

    admin_to: list[tuple[str, str]] = []
    rdu_raw_memberships: list[tuple[str, str]] = []
    can_rdp_effective: list[tuple[str, str]] = []
    can_psremote: list[tuple[str, str]] = []

    raw_sessions = 0
    unique_sessions: set[tuple[str, str]] = set()

    # Per-domain breakdown tracking
    domain_edge_stats: dict[str, dict[str, tuple[int, int]]] = {}
    domain_data: dict[str, dict] = {}

    trusts = []
    all_referenced_principals: set[tuple[str, str]] = set()

    # First pass: collect all defined object identifiers and detect duplicate IDs
    for f in files:
        b = os.path.basename(f)
        domain = detect_domain_from_path(f)
        kind = b.split("_")[-1].replace(".json", "")

        if domain not in duplicate_ids_per_domain:
            duplicate_ids_per_domain[domain] = {}
        if kind not in duplicate_ids_per_domain[domain]:
            duplicate_ids_per_domain[domain][kind] = []

        with open(f, encoding="utf-8") as fp:
            try:
                content = json.load(fp)
            except Exception as exc:
                raise RuntimeError(f"Failed to load JSON from {f}: {exc}") from exc

        meta_count = content.get("meta", {}).get("count", 0)
        data = content.get("data", [])
        total_records += len(data)

        # Detect duplicates in this file
        id_counter = Counter()
        for item in data:
            oid = item.get("ObjectIdentifier")
            if oid:
                id_counter[oid] += 1
                all_unique_ids.add(oid)
                if kind.lower() in M1_NODE_KINDS:
                    m1_unique_ids.add(oid)

        dup_ids = [oid for oid, cnt in id_counter.items() if cnt > 1]
        if dup_ids:
            file_duplicate_counts[b] = len(dup_ids)
            duplicate_ids_per_domain[domain][kind].extend(dup_ids)

        file_stats.append(
            {
                "file": b,
                "domain": domain,
                "kind": kind,
                "records": len(data),
                "meta_count": meta_count,
                "diff": len(data) - meta_count,
                "duplicates": len(dup_ids),
            }
        )

    # Second pass: process relations, effective rights, and dangling references
    for f in files:
        b = os.path.basename(f)
        domain = detect_domain_from_path(f)
        kind = b.split("_")[-1].replace(".json", "")

        if domain not in domain_data:
            domain_data[domain] = {
                "members": [],
                "aces": {k: [] for k in ACE_NAMES},
                "admin_to": [],
                "rdu_raw_memberships": [],
                "can_rdp_effective": [],
                "sessions": [],
            }

        with open(f, encoding="utf-8") as fp:
            try:
                content = json.load(fp)
            except Exception as exc:
                raise RuntimeError(f"Failed to load JSON from {f}: {exc}") from exc

        data = content.get("data", [])

        for item in data:
            oid = item.get("ObjectIdentifier")
            if not oid:
                continue

            # Members
            if "Members" in item:
                for m in item.get("Members", []):
                    raw_members += 1
                    mid = m.get("ObjectIdentifier")
                    if mid:
                        unique_members.add((mid, oid))
                        domain_data[domain]["members"].append((mid, oid))
                        if mid not in all_unique_ids:
                            all_referenced_principals.add(("Member", mid))

            # Aces
            if "Aces" in item:
                for ace in item.get("Aces", []):
                    rn = ace.get("RightName")
                    psid = ace.get("PrincipalSID")
                    if rn in raw_aces:
                        raw_aces[rn] += 1
                        if psid:
                            unique_aces[rn].add((psid, oid))
                            domain_data[domain]["aces"][rn].append((psid, oid))
                            if psid not in all_unique_ids:
                                all_referenced_principals.add(("AcePrincipal", psid))

            # Host-bound access: LocalAdmins flat array
            for la in item.get("LocalAdmins", []):
                mid = la.get("ObjectIdentifier")
                if mid:
                    admin_to.append((mid, oid))
                    domain_data[domain]["admin_to"].append((mid, oid))
                    if mid not in all_unique_ids:
                        all_referenced_principals.add(("LocalAdmin", mid))

            # Host-bound access: LocalGroups and UserRights
            user_rights = item.get("UserRights", [])
            rdp_allowed_sids = set()
            rdp_denied_sids = set()
            allow_right_collected = False
            deny_right_collected = False

            for ur in user_rights:
                priv = ur.get("Privilege", "")
                is_collected = ur.get("Collected", False)
                if priv == "SeRemoteInteractiveLogonRight" and is_collected:
                    allow_right_collected = True
                    for r in ur.get("Results", []):
                        rid = r.get("ObjectIdentifier")
                        if rid:
                            rdp_allowed_sids.add(rid)
                elif priv == "SeDenyRemoteInteractiveLogonRight":
                    if is_collected:
                        deny_right_collected = True
                        for r in ur.get("Results", []):
                            rid = r.get("ObjectIdentifier")
                            if rid:
                                rdp_denied_sids.add(rid)

            for lg in item.get("LocalGroups", []):
                lg_id = lg.get("ObjectIdentifier", "")
                results = lg.get("Results", [])
                if lg_id.endswith("-544"):
                    for r in results:
                        mid = r.get("ObjectIdentifier")
                        if mid:
                            admin_to.append((mid, oid))
                            domain_data[domain]["admin_to"].append((mid, oid))
                            if mid not in all_unique_ids:
                                all_referenced_principals.add(("LocalGroupAdmin", mid))
                elif lg_id.endswith("-555"):
                    for r in results:
                        mid = r.get("ObjectIdentifier")
                        if mid:
                            rdu_raw_memberships.append((mid, oid))
                            domain_data[domain]["rdu_raw_memberships"].append((mid, oid))
                            if mid not in all_unique_ids:
                                all_referenced_principals.add(("LocalGroupRDP", mid))

                            allow_state = (
                                "positive"
                                if allow_right_collected
                                and (mid in rdp_allowed_sids or lg_id in rdp_allowed_sids)
                                else "known-negative"
                                if allow_right_collected
                                else "unknown"
                            )
                            deny_state = (
                                "positive"
                                if deny_right_collected
                                and (mid in rdp_denied_sids or lg_id in rdp_denied_sids)
                                else "known-negative"
                                if deny_right_collected
                                else "unknown"
                            )
                            classification = classify_canrdp_evidence(
                                "positive",
                                allow_state,
                                deny_state,
                                completeness=(
                                    "complete"
                                    if allow_right_collected and deny_right_collected
                                    else "unknown"
                                ),
                            )
                            if classification["materialize"]:
                                can_rdp_effective.append((mid, oid))
                                domain_data[domain]["can_rdp_effective"].append((mid, oid))
                elif lg_id.endswith("-580"):
                    for r in results:
                        mid = r.get("ObjectIdentifier")
                        if mid:
                            can_psremote.append((mid, oid))
                            if mid not in all_unique_ids:
                                all_referenced_principals.add(("LocalGroupPSRemote", mid))

            # Sessions
            for sk in ["Sessions", "PrivilegedSessions", "RegistrySessions"]:
                val = item.get(sk)
                if isinstance(val, dict):
                    res = val.get("Results", [])
                elif isinstance(val, list):
                    res = val
                else:
                    res = []
                for s in res:
                    raw_sessions += 1
                    usid = s.get("UserSID") or s.get("UserId")
                    csid = s.get("ComputerSID") or oid
                    if usid and csid:
                        unique_sessions.add((csid, usid))
                        domain_data[domain]["sessions"].append((csid, usid))
                        if usid not in all_unique_ids:
                            all_referenced_principals.add(("SessionUser", usid))

            # Trusts
            if "Trusts" in item and kind.lower() in ["domain", "domains"]:
                dname = item.get("Properties", {}).get("name")
                for t in item.get("Trusts", []):
                    target = t.get("TargetName") or t.get("TargetDomainName")
                    trusts.append(
                        {
                            "source": dname,
                            "target": target,
                            "direction": t.get("TrustDirection"),
                            "type": t.get("TrustType"),
                            "sid_filtering": t.get("SidFilteringEnabled"),
                        }
                    )

    # Compute per-domain stats
    for dname, dinfo in domain_data.items():
        domain_edge_stats[dname] = {
            "AdminTo": (len(dinfo["admin_to"]), len(set(dinfo["admin_to"]))),
            "HasSession": (len(dinfo["sessions"]), len(set(dinfo["sessions"]))),
            "MemberOf": (len(dinfo["members"]), len(set(dinfo["members"]))),
            "GenericAll": (len(dinfo["aces"]["GenericAll"]), len(set(dinfo["aces"]["GenericAll"]))),
            "WriteDacl": (len(dinfo["aces"]["WriteDacl"]), len(set(dinfo["aces"]["WriteDacl"]))),
            "ForceChangePassword": (
                len(dinfo["aces"]["ForceChangePassword"]),
                len(set(dinfo["aces"]["ForceChangePassword"])),
            ),
            "RemoteDesktopUsers_raw_memberships": (
                len(dinfo["rdu_raw_memberships"]),
                len(set(dinfo["rdu_raw_memberships"])),
            ),
            "CanRDP_effective": (
                len(dinfo["can_rdp_effective"]),
                len(set(dinfo["can_rdp_effective"])),
            ),
        }

    return {
        "files_count": len(files),
        "total_records": total_records,
        "all_unique_ids": len(all_unique_ids),
        "m1_unique_ids": len(m1_unique_ids),
        "file_stats": file_stats,
        "duplicate_counts": file_duplicate_counts,
        "duplicate_ids_per_domain": duplicate_ids_per_domain,
        "dangling_references": all_referenced_principals,
        "m1_edges": {
            "MemberOf": (raw_members, len(unique_members)),
            "GenericAll": (raw_aces["GenericAll"], len(unique_aces["GenericAll"])),
            "WriteDacl": (raw_aces["WriteDacl"], len(unique_aces["WriteDacl"])),
            "WriteOwner": (raw_aces["WriteOwner"], len(unique_aces["WriteOwner"])),
            "GenericWrite": (raw_aces["GenericWrite"], len(unique_aces["GenericWrite"])),
            "Owns": (raw_aces["Owns"], len(unique_aces["Owns"])),
            "ForceChangePassword": (
                raw_aces["ForceChangePassword"],
                len(unique_aces["ForceChangePassword"]),
            ),
            "AdminTo": (len(admin_to), len(set(admin_to))),
            "HasSession": (raw_sessions, len(unique_sessions)),
            "RemoteDesktopUsers_raw_memberships": (
                len(rdu_raw_memberships),
                len(set(rdu_raw_memberships)),
            ),
            "CanRDP (effective verified)": (
                len(can_rdp_effective),
                len(set(can_rdp_effective)),
            ),
            "CanPSRemote": (len(can_psremote), len(set(can_psremote))),
        },
        "domain_edge_stats": domain_edge_stats,
        "trusts": trusts,
    }


def main():
    paths = {
        "Dataset A (NORTH SharpHound)": "data/raw/NORTH",
        "Dataset A (NORTH Python)": "data/raw/NORTH_CE_PYTHON",
        "Dataset B (ad_sampledata)": "data/raw/ad_sampledata",
    }

    for name, p in paths.items():
        if os.path.exists(p):
            r = analyze_dataset(p)
            print(f"=== {name} ===")
            print(
                f"Files: {r['files_count']}, Records: {r['total_records']}, "
                f"Unique IDs: {r['all_unique_ids']}, M1 IDs: {r['m1_unique_ids']}"
            )
            print("Duplicate ObjectIdentifier findings:")
            total_dups = sum(r["duplicate_counts"].values())
            print(f"  Total duplicate ID occurrences across files: {total_dups}")
            for dname, kdict in r["duplicate_ids_per_domain"].items():
                for k, ids in kdict.items():
                    if ids:
                        print(f"    {dname} [{k}]: {len(ids)} duplicate IDs")

            print(f"Dangling references count: {len(r['dangling_references'])}")
            if r["dangling_references"]:
                samples = list(r["dangling_references"])[:5]
                print(f"  Sample dangling references (first 5): {samples}")

            print("M1 Edges (Raw, Unique Pairs):")
            for ek, ev in r["m1_edges"].items():
                print(f"  {ek}: {ev}")

            if len(r["domain_edge_stats"]) > 1:
                print("Per-domain breakdown:")
                for dname, stats in r["domain_edge_stats"].items():
                    print(
                        f"  {dname}: AdminTo={stats['AdminTo']}, "
                        f"HasSession={stats['HasSession']}, "
                        f"MemberOf={stats['MemberOf']}, "
                        f"GenericAll={stats['GenericAll']}, "
                        f"WriteDacl={stats['WriteDacl']}, "
                        f"ForceChangePassword={stats['ForceChangePassword']}, "
                        "RemoteDesktopUsers_raw_memberships="
                        f"{stats['RemoteDesktopUsers_raw_memberships']}, "
                        f"CanRDP_effective={stats['CanRDP_effective']}"
                    )
            print(f"Trusts: {r['trusts']}")
            print()
        else:
            print(f"Warning: {p} not found.")


if __name__ == "__main__":
    main()
