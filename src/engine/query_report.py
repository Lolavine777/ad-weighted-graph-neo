"""Small human-readable view of native results; no search or scoring of its own."""

from __future__ import annotations

from collections import Counter
from html import escape

from src.engine.semantics import FactOrigin
from src.engine.top_k import effort_programs

ACTION_NAMES = {
    "propagate_group_entitlement": "Dùng quyền thành viên nhóm",
    "scenario_reset_password": "Reset mật khẩu",
    "genericall_reset_password": "Reset mật khẩu",
    "reset_target_password": "Reset mật khẩu",
    "acquire_reset_identity": "Dùng danh tính vừa reset",
    "genericall_add_member": "Thêm thành viên nhóm",
    "genericall_grant_write_dacl": "Cấp quyền sửa DACL",
    "grant_new_object_right": "Sửa DACL để cấp quyền",
    "obtain_admin_execution_on_host": "Thực thi với quyền quản trị host",
    "scenario_winrm_admin": "Thực thi quản trị qua WinRM",
    "open_winrm_remote_session": "Mở phiên lệnh WinRM (không tự cấp admin)",
    "use_session_identity": "Lấy và dùng danh tính từ session trên máy đã kiểm soát",
}

CONDITION_NAMES = {
    "security_group": "Nhóm dùng để cấp quyền bảo mật",
    "membership_usable": "Membership có hiệu lực",
    "membership_change_allowed": "Cho phép thay đổi thành viên nhóm",
    "directory_write_allowed": "Cho phép sửa đối tượng AD",
    "password_policy_accepts": "Mật khẩu mới đáp ứng policy",
    "network_rpc_reachable": "Kết nối RPC tới đích",
    "network_kdc_reachable": "Kết nối tới KDC",
    "authentication_accepted": "Xác thực được chấp nhận",
    "admin_channel": "Có kênh thực thi quản trị",
    "winrm_available": "WinRM hoạt động và truy cập được",
    "session_fresh": "Session còn mới trong kịch bản snapshot tĩnh",
    "session_present": "Session vẫn còn trên host",
    "credential_accessible": "Có thể truy cập credential trên host",
    "session_identity_usable": "Credential trong session dùng được để xác thực trong miền",
}


def _text(value):
    return escape(str(value)).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def render_query_brief(result, graph):
    """Explain selected witnesses, actual C ledger and assumptions used on them."""
    material = result.materialized_query
    labels = {}

    def label(node_id):
        if node_id is None:
            return "chưa khai báo"
        if node_id not in labels:
            node = graph.node(node_id)
            labels[node_id] = _text(node.get("label") or node_id)
        return labels[node_id]

    descriptor = material.semantic_goal.to_dict() if material.semantic_goal else {}
    required = descriptor.get("required_state", {})
    if descriptor.get("kind") == "usable_identity_entitlement":
        goal = "Danh tính dùng được có quyền thành viên nhóm đích"
    elif required.get("admin_control"):
        goal = "Quyền quản trị trên host đích"
    elif required.get("remote_command_execution"):
        goal = "Chạy lệnh từ xa; không đồng nghĩa quyền quản trị host"
    else:
        goal = "Trạng thái đích đã khai báo trong query"

    top = result.top_k_result or {}
    programs = top.get("programs", [])
    if result.top_k_result is None:
        programs, _ = effort_programs(result)
        programs = programs[:3]
    selection = [(int(p["candidate_id"].rsplit("_", 1)[1]) - 1, p) for p in programs]
    if not selection:
        selection = [(i, None) for i in range(min(3, len(result.paths)))]
    lines = [
        "# Kết quả tìm đường",
        "",
        f"**Nguồn:** {label(material.initial_actor)} → **Đích:** {label(material.target)}.",
        f"**Mục tiêu:** {goal}.",
        f"**Context xác thực:** {label(material.runtime_context.authentication_context)}.",
        "**Kỹ thuật trong scope:** "
        + "; ".join(_text(ACTION_NAMES.get(t.id, t.id)) for t in material.catalog)
        + ".",
        "",
    ]
    if result.paths:
        lines.append(
            f"Tìm được **{len(result.paths)} chương trình**; "
            f"hiển thị {len(selection)}. Đạt đích theo facts và giả định của query."
        )
    elif result.is_no_path_proven_over_scope:
        lines.append("Không có đường đạt mục tiêu trong scope đã khai báo và kiểm tra đầy đủ.")
    else:
        lines.append(
            "**Chưa tìm được đường trong giới hạn/điều kiện hiện tại; chưa kết luận an toàn.**"
        )
    if programs:
        lines.append(
            "Ưu tiên C thấp hơn trong các đường đã tìm và chấm được; "
            "đồng C không có nghĩa một đường tốt hơn."
        )
    elif result.paths:
        lines.append("Các đường dưới đây chưa được xếp hạng theo C; chưa chấm không phải C=0.")
    if result.is_minimum_proven_over_scope:
        lines.append("C nhỏ nhất đã được chứng minh trong scope công bố.")
    elif result.paths:
        lines.append("Kết quả best-found; chưa chứng minh C nhỏ nhất trong toàn scope.")
    lines.extend(
        [
            f"Giới hạn: {material.budget.max_paths} đường, {material.budget.max_steps} bước, "
            f"{material.budget.max_expansions} lần mở rộng; đã dùng {result.expansions} lần.",
            "C là công sức tương đối theo scenario, không phải số phút hay xác suất thành công.",
        ]
    )
    if result.truncated:
        lines.append(f"Tìm kiếm bị giới hạn: `{result.truncation_reason}`.")
    for rank, (index, program) in enumerate(selection, 1):
        path = result.paths[index]
        effort = program["effort"] if program else None
        lines.extend(
            ["", f"## Đường {rank} - C={effort if effort is not None else 'chưa chấm'}", ""]
        )
        if not path.transition_history:
            lines.append("Mục tiêu đã có trong trạng thái ban đầu; không cần hành động mới.")
        assumptions = set()
        for step_index, step in enumerate(path.transition_history, 1):
            request = step.result.request
            name = ACTION_NAMES.get(request.technique_id, request.technique_id)
            via = (
                f" qua {label(request.source)}"
                if request.source not in (request.actor, request.target)
                else ""
            )
            lines.append(
                f"{step_index}. {_text(name)}: {label(request.actor)}{via} "
                f"→ {label(request.target)}."
            )
            for decision in step.result.decisions:
                fact = decision.fact
                if fact is not None and fact.origin is FactOrigin.DECLARED_ASSUMPTION:
                    assumptions.add((fact.predicate, fact.subject, fact.target, fact.value))
        if program:
            ledger = program.get("work_unit_ledger", {})
            lines.extend(["", "C tính trên các công việc khác nhau, khử trùng theo ledger:", ""])
            for _, unit in sorted(ledger.items()):
                name = ACTION_NAMES.get(unit.get("technique"), unit.get("technique", "Công việc"))
                cost = unit.get("computed_cost", unit.get("cost"))
                target = unit.get("target_id")
                suffix = f" (đích: {label(target)})" if target is not None else ""
                lines.append(f"- {_text(name)}: C={cost}{suffix}.")
            if not ledger:
                lines.append("- Không có công việc chủ động; membership có sẵn không cộng C.")
            p = program.get("likelihood_interval")
            impact = program.get("impact")
            # neo-c-v1 ranks by C only; P/I lines appear only for legacy profiles that rate them.
            if p is not None or impact is not None:
                lines.extend(
                    [
                        "",
                        f"P: {_text(p) if p is not None else 'chưa chấm'}; "
                        f"I: {_text(impact) if impact is not None else 'chưa chấm'}.",
                    ]
                )
        if assumptions:
            lines.extend(["", "Giả định đã dùng trên đường này (không phải quan sát):", ""])
            for predicate, subject, target, value in sorted(assumptions, key=str):
                truth = {True: "đúng", False: "sai", None: "chưa rõ"}[value]
                name = CONDITION_NAMES.get(predicate, predicate)
                lines.append(
                    f"- {_text(name)} (`{_text(predicate)}`): "
                    f"{label(subject)} → {label(target)} = {truth}."
                )
    if not result.paths:
        unknown = Counter(p for attempt in result.attempts for p in attempt.unknown)
        if unknown:
            lines.extend(["", "Điều kiện thiếu thông tin thường gặp:", ""])
            lines.extend(f"- `{_text(p)}`: {count} lần." for p, count in unknown.most_common(3))
    lines.extend(["", "JSON đầy đủ giữ trace, provenance, ledger và các giới hạn để kiểm chứng."])
    return "\n".join(lines) + "\n"
