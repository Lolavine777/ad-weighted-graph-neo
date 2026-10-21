"""Small defender-facing projection of native discovery, never another planner."""

from __future__ import annotations

from src.engine.ranking.resolution_service import canonical_digest

OPERATIONS = {
    "scenario_reset_password": "Đặt lại mật khẩu của User bằng quyền GenericAll",
    "acquire_reset_identity": "Dùng danh tính vừa reset tại authentication context",
    "propagate_group_entitlement": "Có entitlement của security group với danh tính này",
}


def remediation_outcome(graph, package):
    """Describe an already verified package; do not infer safety from cut programs."""
    report = package["report"]
    cells = report["cells"]
    edits = []
    for edit in package["request"]["edits"]:
        if edit["kind"] == "deny_relationship":
            relation = edit["relationship"]
            description = (
                f"Loại quan hệ {relation['kind']}: "
                f"{graph.node(relation['source'])['label']} → "
                f"{graph.node(relation['target'])['label']}"
            )
        elif edit["kind"] == "runtime_fact_replace":
            key = edit["key"]
            target = graph.node(key["target"])["label"] if key["target"] else "không có đích"
            description = (
                f"Đặt điều kiện {key['predicate']} = {edit['after']}: "
                f"{graph.node(key['subject'])['label']} → {target}"
            )
        else:
            description = (
                f"Đổi {edit['name']} của {graph.node(edit['subject'])['label']} "
                f"thành {edit['after']}"
            )
        edits.append(description)
    return {
        "intervention": report["request_id"],
        "edits": edits,
        "programs_cut": dict(report["summary"]["programs_cut"]),
        "pairs_disconnected": dict(report["summary"]["pairs_disconnected"]),
        "reachable_before": sum(c["before"]["reachability"] == "reachable" for c in cells),
        "reachable_after": sum(c["after"]["reachability"] == "reachable" for c in cells),
        "unresolved_after": sum(
            c["after"]["reachability"] not in {"reachable", "proven_unreachable"} for c in cells
        ),
        "new_after_programs": sum(len(c["new_program_ids"]) for c in cells),
    }


def build_defender_brief(graph, inventory, request, result, *, remediation=None):
    """Project exact native witnesses/guarantees; missing ratings stay missing.

    A technical target tier is not a business-impact score. Negative/truncated
    cells remain visible, and a path to an authentication context is not host
    execution. Full attempt/state audit stays in result.json.
    """
    selected = (
        request.get("target_goal_ids")
        or request["target_manifest"].get("default_discovery_goals")
        or [g["goal_id"] for g in request["target_manifest"]["targets"]]
    )
    goals = {g["goal_id"]: g for g in request["target_manifest"]["targets"]}
    criteria = {t["goal"]["goal_id"]: t for t in inventory["targets"]}
    traces = result["reproducibility"]["inputs"]["public_queries"]
    sources = {s["source_id"]: s for s in request["sources"]}
    if not (
        graph.metadata["snapshot_id"]
        == inventory["snapshot_id"]
        == request["snapshot_id"]
        == result["snapshot_id"]
    ):
        raise ValueError("Defender brief requires the same snapshot in all input packages")

    def identity(node_id):
        node = graph.node(node_id)
        return {"id": node_id, "label": node["label"], "kind": node["kind"]}

    rows = []
    for sid, cells in result["source_goal_matrix"].items():
        for gid, cell in cells.items():
            goal = goals[gid]
            key = canonical_digest([sid, gid])
            trace = traces.get(key, {})
            native = trace.get("result", {})
            guarantees = trace.get("guarantees", {})
            path = native.get("best_path") or next(iter(native.get("paths", [])), None)
            evidence, steps = {}, []
            pointer = f"result.json#/reproducibility/inputs/public_queries/{key}"
            if cell["final_goal_reached"]:
                if path is None:
                    raise ValueError("Reached goal has no native witness in public trace")
                for index, step in enumerate(path["transition_history"], 1):
                    transition = step["result"]
                    action = transition["request"]
                    condition_refs = []
                    for decision in transition["decisions"]:
                        fact = decision.get("fact")
                        if fact is not None:
                            ref = canonical_digest(fact)
                            evidence[ref] = fact
                            condition_refs.append(ref)
                    edge_id = step.get("edge_id")
                    steps.append(
                        {
                            "step": index,
                            "technique": action["technique_id"],
                            "operation": OPERATIONS.get(
                                action["technique_id"], action["technique_id"]
                            ),
                            "actor": identity(action["actor"]),
                            "right_source": identity(action["source"]),
                            "target": identity(action["target"]),
                            "effects": {k: v for k, v in transition["additions"].items() if v},
                            "condition_refs": sorted(set(condition_refs)),
                            "edge_id": edge_id,
                            "derived_from_step": step.get("derived_from_step"),
                            "edge_provenance": graph.edge(edge_id).get("provenance", [])
                            if edge_id
                            else [],
                        }
                    )
            # Give one grounded example of missing evidence at the requested
            # endpoint. It is not a predicted full route or a probability.
            frontier = None
            if not cell["final_goal_reached"]:
                for index, attempt in enumerate(native.get("attempts", [])):
                    if (
                        attempt["status"] == "indeterminate"
                        and attempt["request"]["target"] == goal["target_node_id"]
                        and (frontier is None or len(attempt["unknown"]) < len(frontier["unknown"]))
                    ):
                        frontier = {
                            "technique": attempt["request"]["technique_id"],
                            "actor": identity(attempt["request"]["actor"]),
                            "unknown": attempt["unknown"],
                            "trace": pointer + f"/result/attempts/{index}",
                        }
            candidate_id = (cell.get("min_effort_path") or {}).get("candidate_id")
            rating = native.get("rating_coverage") or {}
            candidate = rating.get("candidates", {}).get(candidate_id, {})
            units = []
            for uid, unit in candidate.get("effort", {}).get("units", {}).items():
                audit = unit.get("rating_audit") or {}
                units.append(
                    {
                        "work_unit_id": uid,
                        "cost": unit["cost"],
                        "disposition": unit["disposition"],
                        "basis_category": unit["basis_category"],
                        "numeric_basis_class": audit.get("numeric_basis_class"),
                        "lookup": audit.get("lookup_key"),
                        "provenance_digest": audit.get("provenance_digest"),
                        "review_reference": audit.get("review_reference"),
                    }
                )
            row = {
                "source_id": sid,
                "source": identity(sources[sid]["node_id"]),
                "goal_id": gid,
                "goal": identity(goal["target_node_id"]),
                "technical_priority": criteria[gid]["technical_priority"],
                "selection_reason": criteria[gid]["selection_reason"],
                "business_impact": cell["impact"],
                "status": cell["status"],
                "reached": cell["final_goal_reached"],
                "C": cell["min_effort"],
                "effort_units": units,
                "P": cell["likelihood_interval"],
                "minimum_proven": bool(guarantees.get("is_minimum_proven_over_scope", False)),
                "no_path_proven_in_declared_scope": bool(
                    guarantees.get("is_no_path_proven_over_scope", False)
                ),
                "truncated": cell["truncated"],
                "truncation_reason": cell["truncation_reason"],
                "expansions": cell["expansions"],
                "effort_applicability": trace.get("query", {}).get("effort_profile_metadata"),
                "steps": steps,
                "conditions": [{"ref": ref, **evidence[ref]} for ref in sorted(evidence)],
                "missing_endpoint_evidence_example": frontier,
                "trace": pointer,
            }
            rows.append(row)
    rows.sort(
        key=lambda r: (
            not r["reached"],
            r["technical_priority"],
            r["C"] is None,
            r["C"] if r["C"] is not None else 0,
            r["source_id"],
            r["goal_id"],
        )
    )
    profile = result["reproducibility"]["inputs"].get("effort_profile")
    return {
        "version": "defender-brief/1.0.0",
        "snapshot_id": request["snapshot_id"],
        "evaluation_mode": request["evaluation_mode"],
        "sources": [
            {
                **identity(s["node_id"]),
                "source_id": sid,
                "profile": s["profile_kind"],
                "authentication_context": s.get("authentication_context"),
                "identity_provenance": s.get("identity_provenance_reference"),
            }
            for sid, s in sources.items()
        ],
        "coverage": {
            "selected_pairs": len(sources) * len(selected),
            "reported_pairs": len(rows),
            "evaluated_pairs": result["summary"]["evaluated_cells"],
            "not_run_pairs": len(result["summary"]["not_run_cells"]),
            "witness_pairs": sum(r["reached"] for r in rows),
            "unresolved_pairs": sum(
                not r["reached"] and not r["no_path_proven_in_declared_scope"] for r in rows
            ),
            "inventory_pairs_outside_cohort": inventory["counts"]["potential_pairs"]
            - len(sources) * len(selected),
        },
        "ordering": (
            "Witnesses first; within each technical target tier, comparable rated C then unrated. "
            "Technical tiers are not business impact or probability."
        ),
        "allowed_techniques": result["reproducibility"]["inputs"].get("allowed_techniques"),
        "effort_basis": profile,
        "goals": rows,
        "remediation": remediation,
        "limits": [
            "C is conditional ordinal effort, not elapsed time or a measured success rate.",
            "A witness is conditional on its listed assumptions and initial identity declaration.",
            "Best found is not minimum unless the native guarantee says so; unrated is not zero.",
            "Incomplete/unrun/unsupported goals remain inconclusive; not domain-wide coverage.",
            "An authentication context endpoint does not itself imply host control.",
        ],
    }


def render_defender_brief(brief):
    """Vietnamese decision view; identifiers/provenance remain in the JSON/audit."""

    def safe(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    coverage = brief["coverage"]
    lines = ["# Từ foothold này, cần quan tâm gì?", ""]
    for source in brief["sources"]:
        lines += [
            f"Nguồn: **{safe(source['label'])}** ({source['kind']}); "
            f"profile `{source['profile']}`.",
            f"ID: `{source['id']}`; context: `{source['authentication_context']}`.",
            "Initial capability là đầu vào khai báo; reference: "
            f"`{safe(source['identity_provenance'])}`.",
        ]
    lines += [
        "",
        f"Đã xử lý {coverage['evaluated_pairs']}/{coverage['selected_pairs']} cặp trong cohort: "
        f"**{coverage['witness_pairs']} có witness**, "
        f"{coverage['unresolved_pairs']} chưa kết luận; {coverage['not_run_pairs']} chưa chạy. "
        f"Ngoài cohort: {coverage['inventory_pairs_outside_cohort']} cặp inventory.",
        "",
        "C là mức công sức ordinal có điều kiện; chưa chấm giữ trống. Thứ tự: có witness trước, "
        "rồi tầng mục tiêu kỹ thuật và C trong cùng tầng; không phải business-impact/P ranking.",
        "",
        "| Nguồn | Mục tiêu | Kết quả | C tìm thấy | Bằng chứng tối ưu |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in brief["goals"]:
        lines.append(
            "| "
            + " | ".join(
                map(
                    safe,
                    [
                        row["source"]["label"],
                        row["goal"]["label"],
                        row["status"],
                        row["C"] if row["C"] is not None else "chưa chấm",
                        "có, trong scope" if row["minimum_proven"] else "chưa có",
                    ],
                )
            )
            + " |"
        )
    for row in brief["goals"]:
        if not row["reached"]:
            continue
        lines += [
            "",
            f"## Đường tìm thấy tới {safe(row['goal']['label'])}",
            "",
            "| Bước | Hành động | Danh tính thực hiện | Đối tượng / context |",
            "| --- | --- | --- | --- |",
        ]
        for step in row["steps"]:
            lines.append(
                "| "
                + " | ".join(
                    map(
                        safe,
                        [
                            step["step"],
                            step["operation"],
                            step["actor"]["label"],
                            step["target"]["label"],
                        ],
                    )
                )
                + " |"
            )
        if not row["steps"]:
            lines.append("| 0 | Goal đã có trong initial capability | — | — |")
        assumptions = [f for f in row["conditions"] if f["origin"] == "declared_assumption"]
        if row["effort_units"]:
            lines += ["", "Work units được chấm C (union, không cộng số bước):"]
            for unit in row["effort_units"]:
                lookup = unit["lookup"] or {}
                price = unit["cost"] if unit["cost"] is not None else "chưa chấm"
                lines.append(
                    f"- `{lookup.get('technique', unit['work_unit_id'])}`: "
                    f"C={price}; basis `{unit['numeric_basis_class']}`."
                )
        lines += [
            "",
            f"Đường này dùng **{len(assumptions)} runtime assumptions**; "
            "đây là dự đoán có điều kiện, không phải quan sát đăng nhập hoặc P=1.",
        ]
        for fact in assumptions:
            lines.append(
                f"- `{fact['predicate']}`: `{fact['subject']}` → `{fact['target']}`; "
                f"reference `{safe(fact.get('provenance_reference'))}`."
            )
        reset = next((s for s in row["steps"] if s["technique"] == "scenario_reset_password"), None)
        if reset:
            lines += [
                "",
                "**Quyền nên kiểm tra trước:** GenericAll của "
                f"**{safe(reset['right_source']['label'])}** "
                f"trên **{safe(reset['target']['label'])}**. "
                "Xem toàn bộ ACE/inheritance provenance trong JSON trước khi thu hồi quyền; "
                "đây là điểm can thiệp đề xuất từ witness, chưa phải bằng chứng cắt hết đường.",
            ]
        lines += [
            "",
            f"Full native trace: `{row['trace']}`. "
            "Bước dùng danh tính tại context không tự cấp quyền admin trên context đó.",
        ]
    lines += ["", "## Các mục tiêu chưa có witness", ""]
    for row in brief["goals"]:
        if row["reached"]:
            continue
        example = row["missing_endpoint_evidence_example"]
        reason = (
            "không có đường trong capabilities/techniques/facts đã khai báo"
            if row["no_path_proven_in_declared_scope"]
            else "đã hết budget"
            if row["truncated"]
            else row["status"]
        )
        if example:
            reason += "; ví dụ một transition tới đích còn thiếu " + ", ".join(
                f"`{p}`" for p in example["unknown"]
            )
        lines.append(f"- {safe(row['goal']['label'])}: {reason}; chưa có cơ sở gọi là an toàn.")
    remediation = brief.get("remediation") or {}
    if remediation.get("status") == "executed":
        lines += [
            "",
            "## Can thiệp đã được replay và tìm đường lại",
            "",
            "| Can thiệp | Programs bị cắt | Cặp chứng minh ngắt | Cặp còn Unknown |",
            "| --- | --- | --- | --- |",
        ]
        for row in remediation.get("ranking") or []:
            q = row["quantities"]
            lines.append(
                "| "
                + " | ".join(
                    map(
                        safe,
                        [
                            row["intervention"],
                            q["observed_programs_cut"],
                            q["proven_disconnected_pairs"],
                            q["unresolved_after_pairs"],
                        ],
                    )
                )
                + " |"
            )
        lines += [
            "",
            "Các số này chỉ áp dụng cohort can thiệp đã chạy. "
            "Chưa có chi phí vận hành defender hoặc bằng chứng can thiệp tối ưu toàn hệ thống.",
        ]
        for outcome in remediation.get("outcomes", []):
            cut = outcome["programs_cut"]
            disconnected = outcome["pairs_disconnected"]
            lines += [
                "",
                "**Đã thử:** " + "; ".join(safe(e) for e in outcome["edits"]) + ".",
                f"Cắt {cut['numerator']}/{cut['denominator']} programs đã quan sát; "
                f"cặp còn reachable: **{outcome['reachable_before']} → "
                f"{outcome['reachable_after']}**. "
                f"Chứng minh ngắt: {disconnected['numerator']}/{disconnected['denominator']}; "
                f"chưa kết luận sau sửa: {outcome['unresolved_after']}.",
                f"Tìm lại được {outcome['new_after_programs']} programs mới. "
                "Tỷ lệ cắt programs chỉ tính corpus đã trả về, không phải toàn bộ đường có thể có.",
            ]
    lines += [
        "",
        "Chi tiết kiểu identity, actor, nguồn quyền, raw-edge provenance và từng runtime fact "
        "nằm trong defender-brief.json. result.json giữ toàn bộ attempts/state audit. "
        "Nếu có remediation, program elimination và source–goal disconnection được báo riêng.",
    ]
    return "\n".join(lines) + "\n"
