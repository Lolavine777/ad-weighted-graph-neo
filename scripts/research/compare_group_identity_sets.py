"""Đối soát tập Group bằng chuỗi identity nguyên vẹn và mapping tường minh.

Đầu vào: canonical Graph JSON, mảng kết quả truy vấn Legacy Group và JSON mapping
Legacy objectid -> canonical ID. Không kết nối database, không sửa raw, không suy
scope từ hậu tố SID. Kết quả đầy đủ có identity phải được giữ local theo data policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def identity(value: object) -> str:
    require(isinstance(value, str) and bool(value), "Identity phải là chuỗi không rỗng")
    require(value == value.strip(), "Identity có khoảng trắng biên không được tự sửa")
    return value


def load_json(path: Path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "JSON có key trùng")
            result[key] = value
        return result

    def constant(_value):
        raise ValueError("JSON chứa số không hữu hạn")

    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant
    )


def set_digest(values: set[str]) -> str:
    """SHA-256 của mảng chuỗi đã sort, JSON UTF-8 compact, không đổi chuỗi."""
    payload = json.dumps(sorted(values), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compare_groups(project: dict, legacy: list, mapping: dict) -> dict:
    require(
        isinstance(project, dict) and isinstance(project.get("nodes"), list),
        "Project phải có mảng nodes",
    )
    require(isinstance(legacy, list), "Legacy phải là mảng kết quả truy vấn Group")
    require(isinstance(mapping, dict), "Mapping phải là object")
    populations: dict[str, set[str]] = {"collected": set(), "boundary": set()}
    all_ids: set[str] = set()
    for node in project["nodes"]:
        require(isinstance(node, dict), "Node phải là object")
        node_id = identity(node.get("id"))
        require(node_id not in all_ids, "Project có identity trùng")
        all_ids.add(node_id)
        require(
            node.get("kind") in ("User", "Group", "Computer", "Domain", "OU", "GPO"),
            "Node thiếu kind hoặc kind ngoài Graph Contract",
        )
        require(type(node.get("is_boundary")) is bool, "Node thiếu boolean is_boundary")
        if node["kind"] == "Group":
            populations["boundary" if node["is_boundary"] else "collected"].add(node_id)
    project_ids = populations["collected"] | populations["boundary"]
    legacy_ids: set[str] = set()
    for row in legacy:
        require(isinstance(row, dict), "Legacy row phải là object")
        objectid = identity(row.get("objectid"))
        require(objectid not in legacy_ids, "Legacy có objectid trùng; cần điều tra multiplicity")
        require(
            "name" in row and (row["name"] is None or isinstance(row["name"], str)),
            "Legacy row thiếu name hoặc name sai kiểu",
        )
        legacy_ids.add(objectid)
    for source, target in mapping.items():
        identity(source)
        identity(target)
        require(source in legacy_ids, "Mapping có source ngoài export Legacy")
        require(target in project_ids, "Mapping có target ngoài tập Project Group")
        require(
            source not in project_ids or source == target,
            "Không được thay identity đã bằng canonical ID",
        )
    resolved: dict[str, str] = {}
    unresolved = []
    for objectid in sorted(legacy_ids):
        target = mapping.get(objectid, objectid if objectid in project_ids else None)
        if target is None:
            unresolved.append(objectid)
        else:
            require(target not in resolved.values(), "Mapping nhiều identity vào một target")
            resolved[objectid] = target
    mapped = set(resolved.values())
    common = mapped & project_ids
    # Khi mapping chưa đủ, project_only là chưa ghép được; không suy absence.
    return {
        "status": "measured" if not unresolved else "unknown",
        "project_collected_count": len(populations["collected"]),
        "project_boundary_count": len(populations["boundary"]),
        "project_total_count": len(project_ids),
        "legacy_count": len(legacy_ids),
        "literal_common_count": len(project_ids & legacy_ids),
        "literal_project_only_count": len(project_ids - legacy_ids),
        "literal_legacy_only_count": len(legacy_ids - project_ids),
        "mapped_common_count": len(common),
        "mapped_common_collected_count": len(common & populations["collected"]),
        "mapped_common_boundary_count": len(common & populations["boundary"]),
        "project_only": sorted(project_ids - mapped),
        "legacy_only": unresolved,
        "unresolved_mappings": unresolved,
        "identity_mapping": resolved,
        "set_digests": {
            "project_collected": set_digest(populations["collected"]),
            "project_boundary": set_digest(populations["boundary"]),
            "project_total": set_digest(project_ids),
            "legacy_stored": set_digest(legacy_ids),
            "legacy_mapped": set_digest(mapped),
        },
        "limitation": (
            "Chỉ đối soát identity Group; không chứng minh metadata, ngữ nghĩa "
            "membership, độ đầy đủ export hoặc parity của toàn graph."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--legacy-groups", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        inputs = [args.project, args.legacy_groups, args.mapping]
        require(
            args.output.resolve() not in {p.resolve() for p in inputs},
            "Output không được ghi đè input",
        )
        result = compare_groups(*(load_json(p) for p in inputs))
        result["input_sha256"] = {
            key: hashlib.sha256(path.read_bytes()).hexdigest()
            for key, path in zip(("project", "legacy_groups", "mapping"), inputs, strict=True)
        }
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({k: v for k, v in result.items() if k.endswith("count") or k == "status"}))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"Đối soát Group thất bại: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
