#!/usr/bin/env python3
"""Thử nghiệm thiết kế #42, 2026-09-26. Python 3.10+, không cần thư viện ngoài.

Chạy: python3 scripts/research/semantics_probe.py

KẾT QUẢ THỰC CHẠY 2026-09-26
15/15 ca đạt đáp án tính tay và exhaustive DFS.
Đổi actor: cost 5; RDP session: 3, mục tiêu admin bị chặn.
AND với chuẩn bị chung: 8 (không phải 11).
Membership direct và nested: cùng cost 4.
Weighted chọn hai hành động tổng 4; baseline chọn một hành động.
Các con số trên chỉ là kết quả fixture; chạy script để xem đủ JSON 15 ca.

SO SÁNH MÔ HÌNH ĐƠN GIẢN
Chạy lại ngày 2026-09-27: cả 15 ca state search vẫn đúng.
Projection dưới đây hỗ trợ và khớp 14 ca, từ chối 1 ca tính cost AND với
chuẩn bị chung. 14/15 không phải tỷ lệ coverage SEAMLESS hay độ chính xác
production. Unsupported không có nghĩa mục tiêu không thể đạt.
Capability graph dưới đây dùng một fact làm node, suy ra reachability bằng closure
AND đơn điệu trước, rồi loại action có prerequisite không thể đạt.
Closure chỉ trả lời reachability, không gán cost cho fact.
Nó chỉ nhận action còn tối đa một prerequisite chưa đúng trong initial state,
và có đúng một effect. Goal phải là một fact.
Nếu gặp nhiều prerequisite động, nó trả unsupported, không trả no-path giả.
Đây là một phép chiếu cụ thể, không đại diện cho mọi cách xây đồ thị đơn giản.
Các assumption về context cố định, cost cố định, quyền tích lũy vẫn giữ nguyên.
Không đo scalability hoặc coverage trên dữ liệu thực trong thử nghiệm này.

PHẠM VI
Đây là prototype độc lập, không import hoặc kiểm thử implementation của repo.
Các fact, action và cost đều là giả lập; không phải dữ liệu SEAMLESS, production
weights, xác suất, thời gian thực hay quyết định ADR đã được chấp thuận.
Đáp án được tính tay trong từng ca trước khi chạy tìm kiếm.

MÔ HÌNH
Một state là tập fact được tích lũy trong một scenario cố định.
Mỗi action cần TẤT CẢ precondition và thêm các effect vào state.
Chỉ true fact mới thỏa điều kiện; absent/false đều không cho phép hành động.
Prototype không phân biệt lý do false/unknown trong diagnostics.
Các fact không bị thu hồi; không có thời gian, credential expiry, delete effect,
cross-domain policy, hay provenance thực. Đó là giới hạn, không phải kết luận
rằng các yếu tố này không cần thiết cho sản phẩm.

Uniform-cost search tìm cost nhỏ nhất trên state graph hữu hạn.
Exhaustive DFS kiểm tra lại cost trên mọi chuỗi làm tăng state của fixture nhỏ.
Hai bộ tìm kiếm dùng chung action specification, nên sự đồng ý của chúng không
kiểm chứng độc lập tính đúng ngoài thực tế của specification.
Zero-cost closure hợp lệ; action không thêm fact bị bỏ qua.
Tie được xử lý theo thứ tự action ID và hàng đợi, không liệt kê mọi lời giải.

KẾT LUẬN ĐƯỢC PHÉP RÚT RA
Các ca cho thấy biểu diễn AND, quyền tích lũy, cost chuẩn bị dùng chung và
membership không tốn cost là khả thi trong mô hình nhỏ này.
Không chứng minh hiệu năng SEAMLESS hay sự cần thiết của state search production.
Muốn đánh giá weighting, baseline phải dùng cùng action set và gating:
ở đây mỗi action thực có unit cost 1, passive closure có cost 0.

NGUỒN NGỮ NGHĨA ĐÃ ĐỌC TRONG THREAD
https://bloodhound.specterops.io/resources/edges/force-change-password
https://bloodhound.specterops.io/resources/edges/can-rdp
https://bloodhound.specterops.io/resources/edges/has-session
Repo audit đọc code: develop a0f84d66959247767af242fcdf5303d98489f4a2.
Nguồn chỉ hỗ trợ phân biệt quyền; không cung cấp các con số cost bên dưới.
"""

import json
from dataclasses import dataclass, replace
from heapq import heappop, heappush
from itertools import count


@dataclass(frozen=True)
class Action:
    name: str
    requires: frozenset[str]
    adds: frozenset[str]
    cost: int
    passive: bool = False

    def __post_init__(self):
        if type(self.cost) is not int or self.cost < 0:
            raise ValueError("cost must be a nonnegative integer")


def action(name, requires, adds, cost, passive=False):
    return Action(name, frozenset(requires), frozenset(adds), cost, passive)


def solve(initial, goal, actions):
    serial = count()
    start = frozenset(initial)
    queue = [(0, next(serial), start, ())]
    best = {start: 0}
    while queue:
        cost, _, state, path = heappop(queue)
        if cost != best[state]:
            continue
        if goal <= state:
            return cost, path
        for step in sorted(actions, key=lambda a: a.name):
            if not step.requires <= state:
                continue
            after = state | step.adds
            candidate = cost + step.cost
            if after == state or candidate >= best.get(after, float("inf")):
                continue
            best[after] = candidate
            heappush(queue, (candidate, next(serial), after, path + (step.name,)))
    return None


def exhaustive_cost(initial, goal, actions):
    """Independent search procedure; shared model, not an independent AD oracle."""
    state = frozenset(initial)
    if goal <= state:
        return 0
    outcomes = []
    for step in actions:
        after = state | step.adds
        if step.requires <= state and after != state:
            tail = exhaustive_cost(after, goal, actions)
            if tail is not None:
                outcomes.append(step.cost + tail)
    return min(outcomes) if outcomes else None


def capability_graph_cost(initial, goal, actions):
    """Strict unary projection; refuse unsupported conjunction instead of guessing."""
    initial = frozenset(initial)
    if len(goal) != 1:
        return {"status": "unsupported", "reason": "requires one goal fact"}
    reachable = set(initial)
    while True:
        previous = len(reachable)
        for step in actions:
            if step.requires <= reachable:
                reachable.update(step.adds)
        if len(reachable) == previous:
            break
    if not goal <= reachable:
        return {
            "status": "supported",
            "cost": None,
            "reason": "goal absent from monotone reachability closure",
        }
    edges = []
    for step in sorted(actions, key=lambda a: a.name):
        if not step.requires <= reachable:
            continue
        dynamic = step.requires - initial
        if len(dynamic) > 1 or len(step.adds) != 1:
            return {
                "status": "unsupported",
                "reason": step.name,
                "dynamic_prerequisites": sorted(dynamic),
            }
        source = next(iter(dynamic)) if dynamic else None
        edges.append((source, next(iter(step.adds)), step.cost))
    serial = count()
    best = {node: 0 for node in initial}
    best[None] = 0
    queue = [(0, next(serial), node) for node in best]
    # All initial entries have equal priority; this list is already a valid heap.
    target = next(iter(goal))
    while queue:
        cost, _, node = heappop(queue)
        if cost != best[node]:
            continue
        if node == target:
            return {"status": "supported", "cost": cost}
        for source, destination, weight in edges:
            candidate = cost + weight
            if source == node and candidate < best.get(destination, float("inf")):
                best[destination] = candidate
                heappush(queue, (candidate, next(serial), destination))
    return {"status": "supported", "cost": None}


def main():
    results = []

    def check(name, initial, goal, steps, expected):
        goal = frozenset(goal)
        result = solve(initial, goal, steps)
        cost = None if result is None else result[0]
        exhaustive = exhaustive_cost(initial, goal, steps)
        if cost != expected or exhaustive != expected:
            raise AssertionError((name, expected, result, exhaustive))
        projection = capability_graph_cost(initial, goal, steps)
        if projection["status"] == "supported" and projection["cost"] != expected:
            raise AssertionError((name, "projection mismatch", projection, expected))
        results.append(
            {
                "case": name,
                "expected_cost": expected,
                "actual_cost": cost,
                "plan": [] if result is None else result[1],
                "status": "PASS",
                "capability_graph": projection,
            }
        )
        return result

    # Hand answer: reset 2 + privileged access 3 = 5.
    reset = action("reset_bob", {"auth_alice", "reset_right", "reset_allowed"}, {"password_bob"}, 2)
    admin = action(
        "admin_h_as_bob",
        {"password_bob", "bob_admin_h", "auth_accepted_h", "admin_channel_h"},
        {"admin_h"},
        3,
    )
    initial = {
        "auth_alice",
        "reset_right",
        "reset_allowed",
        "bob_admin_h",
        "auth_accepted_h",
        "admin_channel_h",
    }
    check("actor_handoff", initial, {"admin_h"}, [reset, admin], 5)
    check(
        "authentication_unknown", initial - {"auth_accepted_h"}, {"admin_h"}, [reset, admin], None
    )
    check(
        "authentication_false",
        (initial - {"auth_accepted_h"}) | {"auth_rejected_h"},
        {"admin_h"},
        [reset, admin],
        None,
    )
    check("missing_reset_evidence", initial - {"reset_right"}, {"admin_h"}, [reset, admin], None)
    rdp = action(
        "rdp_h_as_bob",
        {"password_bob", "bob_rdp_h", "rdp_ready_h", "auth_accepted_h"},
        {"interactive_h"},
        1,
    )
    rdp_initial = (initial - {"bob_admin_h"}) | {"bob_rdp_h", "rdp_ready_h"}
    check("rdp_session_reachable", rdp_initial, {"interactive_h"}, [reset, rdp, admin], 3)
    check("rdp_not_admin", rdp_initial, {"admin_h"}, [reset, rdp, admin], None)
    check(
        "unqualified_material_not_password",
        {"material_bob", "bob_admin_h", "auth_accepted_h", "admin_channel_h"},
        {"admin_h"},
        [admin],
        None,
    )

    # Hand answer: P once (3), obtain A (2), obtain B (2), finish (1) = 8.
    # Separate shortest branch costs would sum to 5 + 5 + 1 = 11 (incorrect).
    shared = [
        action("prepare", {"start"}, {"prepared"}, 3),
        action("get_a", {"prepared"}, {"a"}, 2),
        action("get_b", {"prepared"}, {"b"}, 2),
        action("finish", {"a", "b"}, {"goal"}, 1),
    ]
    check("and_shared_preparation", {"start"}, {"goal"}, shared, 8)
    check(
        "and_one_capability_insufficient",
        {"start"},
        {"goal"},
        [a for a in shared if a.name != "get_b"],
        None,
    )

    # Hand answer: entitlement propagation is passive; only use costs 4.
    use = action("use_entitlement", {"effective_g"}, {"goal"}, 4)
    direct = [action("direct_membership", {"auth"}, {"effective_g"}, 0, True), use]
    nested = [
        action("membership_1", {"auth"}, {"g1"}, 0, True),
        action("membership_2", {"g1"}, {"g2"}, 0, True),
        action("membership_3", {"g2"}, {"effective_g"}, 0, True),
        action("cycle", {"effective_g"}, {"g1"}, 0, True),
        use,
    ]
    check("direct_membership", {"auth"}, {"goal"}, direct, 4)
    check("nested_membership_and_zero_cycle", {"auth"}, {"goal"}, nested, 4)

    # Same applicability model: weighted chooses two actions at 2+2=4;
    # action-count baseline chooses one action, cost 1 rather than 2.
    choices = [
        action("direct_expensive", {"start"}, {"goal"}, 5),
        action("detour_1", {"start"}, {"middle"}, 2),
        action("detour_2", {"middle"}, {"goal"}, 2),
    ]
    weighted = check("weighted_prefers_two_actions", {"start"}, {"goal"}, choices, 4)
    unit = check(
        "action_count_prefers_one",
        {"start"},
        {"goal"},
        [replace(a, cost=0 if a.passive else 1) for a in choices],
        1,
    )
    if weighted[1] != ("detour_1", "detour_2") or unit[1] != ("direct_expensive",):
        raise AssertionError("unexpected baseline comparison")
    # Same endpoints/effects, different action IDs/costs remain distinct.
    check(
        "parallel_techniques",
        {"start"},
        {"goal"},
        [action("expensive", {"start"}, {"goal"}, 7), action("cheap", {"start"}, {"goal"}, 2)],
        2,
    )
    check("initial_goal", {"goal"}, {"goal"}, [], 0)
    supported = sum(r["capability_graph"]["status"] == "supported" for r in results)
    print(
        json.dumps(
            {
                "scope": "synthetic design probe, not repository acceptance",
                "passed": len(results),
                "projection_supported_and_matching": supported,
                "projection_explicitly_unsupported": len(results) - supported,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
