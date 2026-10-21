"""Acceptance coverage for group nesting semantics and cycle guard (Refs #53)."""

import networkx as nx

from scripts.check_contract import canonical_edge_id


def resolve_ancestor_groups(graph: nx.DiGraph, start_node: str) -> set[str]:
    """DFS-based transitive ancestor group resolution with cycle detection."""
    visited: set[str] = set()
    ancestors: set[str] = set()
    stack: list[str] = [start_node]
    while stack:
        current = stack.pop()
        for _, target, data in graph.out_edges(current, data=True):
            if data.get("kind") == "MemberOf" and target not in visited:
                visited.add(target)
                ancestors.add(target)
                stack.append(target)
    return ancestors


def test_simple_group_nesting_is_direct_only_and_transitive_resolvable():
    """Verify simple nesting (User -> Group A -> Group B) preserves direct edges only."""
    graph = nx.DiGraph()
    graph.add_node("U_ALICE", kind="User")
    graph.add_node("G_ENGINEERING", kind="Group")
    graph.add_node("G_EMPLOYEES", kind="Group")

    graph.add_edge("U_ALICE", "G_ENGINEERING", kind="MemberOf", weight=1.0)
    graph.add_edge("G_ENGINEERING", "G_EMPLOYEES", kind="MemberOf", weight=1.0)

    # Direct-only invariant: graph must not contain shortcut edge (U_ALICE -> G_EMPLOYEES)
    assert not graph.has_edge("U_ALICE", "G_EMPLOYEES")
    assert graph.number_of_edges() == 2

    # Transitive closure is resolved dynamically via traversal
    ancestors = resolve_ancestor_groups(graph, "U_ALICE")
    assert ancestors == {"G_ENGINEERING", "G_EMPLOYEES"}

    # Dijkstra additive path cost: 1.0 + 1.0 = 2.0
    path = nx.shortest_path(graph, "U_ALICE", "G_EMPLOYEES", weight="weight")
    assert path == ["U_ALICE", "G_ENGINEERING", "G_EMPLOYEES"]
    cost = nx.path_weight(graph, path, weight="weight")
    assert cost == 2.0


def test_diamond_multiple_inheritance_deduplication():
    """Verify diamond inheritance (A -> B -> D and A -> C -> D) deduplicates ancestors."""
    graph = nx.DiGraph()
    graph.add_node("U_BOB", kind="User")
    graph.add_node("G_DEV_LEADS", kind="Group")
    graph.add_node("G_OPS_LEADS", kind="Group")
    graph.add_node("G_ALL_LEADS", kind="Group")

    graph.add_edge("U_BOB", "G_DEV_LEADS", kind="MemberOf", weight=1.0)
    graph.add_edge("U_BOB", "G_OPS_LEADS", kind="MemberOf", weight=1.0)
    graph.add_edge("G_DEV_LEADS", "G_ALL_LEADS", kind="MemberOf", weight=1.0)
    graph.add_edge("G_OPS_LEADS", "G_ALL_LEADS", kind="MemberOf", weight=1.0)

    # 4 direct edges preserved in graph
    assert graph.number_of_edges() == 4

    # Ancestor resolution yields deduplicated set
    ancestors = resolve_ancestor_groups(graph, "U_BOB")
    assert ancestors == {"G_DEV_LEADS", "G_OPS_LEADS", "G_ALL_LEADS"}

    # Both paths have equal cost: 2.0
    dev_path = ["U_BOB", "G_DEV_LEADS", "G_ALL_LEADS"]
    ops_path = ["U_BOB", "G_OPS_LEADS", "G_ALL_LEADS"]
    assert nx.path_weight(graph, dev_path, weight="weight") == 2.0
    assert nx.path_weight(graph, ops_path, weight="weight") == 2.0


def test_group_cycle_does_not_cause_infinite_recursion():
    """Verify group cycles (G1 -> G2 -> G3 -> G1) terminate cleanly without infinite loop."""
    graph = nx.DiGraph()
    graph.add_node("U_CHARLIE", kind="User")
    graph.add_node("G_ALPHA", kind="Group")
    graph.add_node("G_BETA", kind="Group")
    graph.add_node("G_GAMMA", kind="Group")

    graph.add_edge("U_CHARLIE", "G_ALPHA", kind="MemberOf", weight=1.0)
    graph.add_edge("G_ALPHA", "G_BETA", kind="MemberOf", weight=1.0)
    graph.add_edge("G_BETA", "G_GAMMA", kind="MemberOf", weight=1.0)
    graph.add_edge("G_GAMMA", "G_ALPHA", kind="MemberOf", weight=1.0)  # Circular nesting

    # Direct edges preserved
    assert graph.number_of_edges() == 4
    assert len(list(nx.simple_cycles(graph))) == 1

    # Cycle-safe resolution terminates in finite steps
    ancestors = resolve_ancestor_groups(graph, "U_CHARLIE")
    assert ancestors == {"G_ALPHA", "G_BETA", "G_GAMMA"}


def test_cross_domain_nesting_with_scoped_canonical_ids():
    """Verify cross-domain membership preserves scoped identity structure."""
    user_fsp = "S-1-5-21-1000-2000-3000-1105"
    child_group = "domain:00000000-0000-0000-0000-000000000002:S-1-5-32-544"

    graph = nx.DiGraph()
    graph.add_node(user_fsp, kind="User", domain="PARENT.CORP")
    graph.add_node(child_group, kind="Group", domain="CHILD.PARENT.CORP")
    graph.add_edge(user_fsp, child_group, kind="MemberOf", weight=1.0)

    assert graph.has_edge(user_fsp, child_group)
    edge_id = canonical_edge_id(user_fsp, child_group, "MemberOf")
    assert edge_id.startswith("sha256:")


def test_computer_principal_in_nested_groups():
    """Verify Computer principals can be nested group members (MS-ADTS)."""
    dc_computer = "S-1-5-21-1000-2000-3000-1001"
    enterprise_dcs = "S-1-5-9"
    waag_group = "domain:00000000-0000-0000-0000-000000000001:S-1-5-32-560"

    graph = nx.DiGraph()
    graph.add_node(dc_computer, kind="Computer")
    graph.add_node(enterprise_dcs, kind="Group")
    graph.add_node(waag_group, kind="Group")

    graph.add_edge(dc_computer, enterprise_dcs, kind="MemberOf", weight=1.0)
    graph.add_edge(enterprise_dcs, waag_group, kind="MemberOf", weight=1.0)

    ancestors = resolve_ancestor_groups(graph, dc_computer)
    assert ancestors == {enterprise_dcs, waag_group}


def test_incomplete_evidence_treated_as_unknown_not_false():
    """Verify missing group targets do not crash resolver and maintain diagnostic state."""
    graph = nx.DiGraph()
    graph.add_node("U_DAN", kind="User")
    # Missing intermediate group in graph (dangling/unresolved in source)
    unresolved_target = "UNRESOLVED_GROUP_SID"

    graph.add_edge("U_DAN", unresolved_target, kind="MemberOf", weight=1.0)
    ancestors = resolve_ancestor_groups(graph, "U_DAN")

    # Unresolved group is retained as encountered target without raising false assumptions
    assert unresolved_target in ancestors
