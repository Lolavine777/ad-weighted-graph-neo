"""Bounded research checks using invented identities, never raw AD data."""

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from itertools import product
from pathlib import Path

from scripts.research import raw_path_probe as raw
from scripts.research import semantics_probe as semantics


def record(identifier, **extra):
    return {"ObjectIdentifier": identifier, "Properties": {"name": identifier}, **extra}


def fixture():
    user = record(
        "user-example", Aces=[{"PrincipalSID": "computer-example", "RightName": "GenericAll"}]
    )
    user["Properties"]["enabled"] = True
    group = record("group-example", Members=[{"MemberId": "user-example"}])
    return {"computers": [record("computer-example")], "groups": [group], "users": [user]}


class ResearchProbeTests(unittest.TestCase):
    def test_synthetic_hand_answers_and_projection_boundary(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            semantics.main()
        report = json.loads(output.getvalue())
        self.assertEqual(report["passed"], 15)
        self.assertEqual(report["projection_supported_and_matching"], 14)
        unsupported = [
            r["case"] for r in report["results"] if r["capability_graph"]["status"] == "unsupported"
        ]
        self.assertEqual(unsupported, ["and_shared_preparation"])

    def test_direction_locators_and_structural_candidates(self):
        records = fixture()
        nodes, evidence, adjacency, omitted = raw.build_projection(records)
        edge = ("computer-example", "GenericAll", "user-example")
        membership = ("user-example", "MemberOf", "group-example")
        self.assertEqual(
            raw.shortest_hops(adjacency, "computer-example", "group-example"), [edge, membership]
        )
        self.assertIsNone(raw.shortest_hops(adjacency, "group-example", "computer-example"))
        self.assertEqual(evidence[edge][0]["pointer"], "#/users/0/Aces/0")
        self.assertEqual(evidence[membership][0]["pointer"], "#/groups/0/Members/0")
        self.assertEqual(omitted, 0)
        self.assertEqual(raw.find_direct_candidates(nodes, evidence, "group-example"), [edge])
        del records["users"][0]["Properties"]["enabled"]
        self.assertEqual(raw.find_direct_candidates(nodes, evidence, "group-example"), [edge])

    def test_duplicate_evidence_unresolved_reference_and_conflict(self):
        records = fixture()
        records["groups"].append(records["groups"][0])
        records["users"][0]["Aces"].append(
            {"PrincipalSID": "missing-example", "RightName": "WriteDacl"}
        )
        _, evidence, _, omitted = raw.build_projection(records)
        self.assertEqual(len(evidence["user-example", "MemberOf", "group-example"]), 2)
        self.assertEqual(omitted, 1)
        records["computers"].append(record("user-example"))
        with self.assertRaisesRegex(ValueError, "Conflicting raw identity"):
            raw.build_projection(records)

    def test_alternative_cycle_and_unreachable(self):
        first = ("s", "relation", "t")
        adjacency = {
            "s": [first, ("s", "relation", "a")],
            "a": [("a", "relation", "s"), ("a", "relation", "t")],
        }
        self.assertEqual(raw.shortest_hops(adjacency, "s", "t"), [first])
        self.assertEqual(
            raw.shortest_hops(adjacency, "s", "t", first),
            [("s", "relation", "a"), ("a", "relation", "t")],
        )
        self.assertIsNone(raw.shortest_hops(adjacency, "s", "missing"))

    def test_verified_inputs_reject_same_length_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {"snapshot_id": "synthetic-test", "files": []}
            for kind, filename in raw.FILENAMES.items():
                payload = json.dumps({kind: fixture()[kind]}).encode()
                (root / filename).write_bytes(payload)
                manifest["files"].append(
                    {
                        "relative_path": filename,
                        "size_bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                )
            report = raw.analyze(root, manifest, "computer-example", "group-example")
            self.assertEqual(report["direct_computer_to_target_member_count"], 1)
            with self.assertRaisesRegex(ValueError, "Source must"):
                raw.analyze(root, manifest, "user-example", "group-example")
            path = root / raw.FILENAMES["users"]
            path.write_bytes(path.read_bytes().replace(b"user-example", b"user-changed"))
            with self.assertRaisesRegex(ValueError, "does not match manifest"):
                raw.read_verified(root, manifest)


def handoff_fixture():
    """Synthetic scenario proposal; strings are not new production state fields.

    Scope all identity-use facts to one directory context (directory-example).
    Costs 2/1/0/1 are arithmetic fixtures, not ratings of AD techniques.
    """
    initial = {
        "control:computer-example",
        "computer_enabled",
        "user_enabled",
        "GenericAll:computer-example:user-example",
        "password_policy_accepts",
        "directory_write_allowed",
        "MemberOf:user-example:group-example",
        "security_group",
        "authentication_accepted:directory-example",
        "membership_usable:directory-example",
        "operation_allowed:target-example",
    }
    reset = "reset_authentication_control:user-example"
    identity = "usable_identity:user-example:directory-example"
    entitlement = "effective_member:user-example:group-example:directory-example"
    operation = "operation_complete:target-example"
    steps = [
        semantics.action(
            "reset",
            {
                "control:computer-example",
                "computer_enabled",
                "user_enabled",
                "GenericAll:computer-example:user-example",
                "password_policy_accepts",
                "directory_write_allowed",
            },
            {reset},
            2,
        ),
        semantics.action(
            "activate_identity",
            {
                reset,
                "user_enabled",
                "authentication_accepted:directory-example",
            },
            {identity},
            1,
        ),
        semantics.action(
            "propagate_membership",
            {
                identity,
                "user_enabled",
                "MemberOf:user-example:group-example",
                "security_group",
                "membership_usable:directory-example",
            },
            {entitlement},
            0,
            passive=True,
        ),
        semantics.action(
            "perform_scoped_operation",
            {
                entitlement,
                "operation_allowed:target-example",
            },
            {operation},
            1,
        ),
    ]
    return initial, steps, (reset, identity, entitlement, operation)


class ScenarioHandoffTests(unittest.TestCase):
    def test_three_gate_truth_table(self):
        """27 assignments, hand-derived goal costs, including false and unknown."""
        gates = (
            "authentication_accepted:directory-example",
            "membership_usable:directory-example",
            "operation_allowed:target-example",
        )
        for values in product((True, False, None), repeat=3):
            initial, steps, goals = handoff_fixture()
            initial -= set(gates)
            initial.update(gate for gate, value in zip(gates, values, strict=True) if value is True)
            auth, membership, operation = (v is True for v in values)
            expected = (
                2,
                3 if auth else None,
                3 if auth and membership else None,
                4 if auth and membership and operation else None,
            )
            with self.subTest(gates=values):
                for goal, cost in zip(goals, expected, strict=True):
                    result = semantics.solve(initial, {goal}, steps)
                    self.assertEqual(None if result is None else result[0], cost)
                    self.assertEqual(semantics.exhaustive_cost(initial, {goal}, steps), cost)

    def test_missing_reset_prerequisite_blocks_handoff(self):
        initial, steps, goals = handoff_fixture()
        for fact in steps[0].requires:
            with self.subTest(missing=fact):
                self.assertIsNone(semantics.solve(initial - {fact}, {goals[2]}, steps))

    def test_reset_effect_alone_does_not_activate_actor(self):
        initial, steps, goals = handoff_fixture()
        self.assertEqual(semantics.solve(initial, {goals[0]}, steps[:1])[0], 2)
        without_bridge = [step for step in steps if step.name != "activate_identity"]
        self.assertIsNone(semantics.solve(initial, {goals[2]}, without_bridge))

    def test_unknown_group_kind_or_missing_membership_blocks_entitlement(self):
        initial, steps, goals = handoff_fixture()
        for fact in ("security_group", "MemberOf:user-example:group-example"):
            with self.subTest(missing=fact):
                self.assertEqual(semantics.solve(initial - {fact}, {goals[1]}, steps)[0], 3)
                self.assertIsNone(semantics.solve(initial - {fact}, {goals[2]}, steps))

    def test_other_context_or_unqualified_material_cannot_supply_identity(self):
        initial, steps, goals = handoff_fixture()
        initial -= {"authentication_accepted:directory-example"}
        initial |= {
            "usable_identity:user-example:other-service",
            "credential_material:user-example",
        }
        self.assertIsNone(semantics.solve(initial, {goals[2]}, steps))

    def test_final_goal_cost_can_match_while_action_count_changes_with_packaging(self):
        initial, steps, goals = handoff_fixture()
        reset, activate = steps[:2]
        combined = semantics.action(
            "reset_and_activate",
            reset.requires | (activate.requires - reset.adds),
            reset.adds | activate.adds,
            reset.cost + activate.cost,
        )
        packed = [combined, *steps[2:]]
        for facts in (initial, initial - {"authentication_accepted:directory-example"}):
            with self.subTest(auth_available=facts == initial):
                split_result = semantics.solve(facts, {goals[2]}, steps)
                packed_result = semantics.solve(facts, {goals[2]}, packed)
                self.assertEqual(
                    None if split_result is None else split_result[0],
                    None if packed_result is None else packed_result[0],
                )
        split_unit = [replace(step, cost=0 if step.passive else 1) for step in steps]
        packed_unit = [replace(step, cost=0 if step.passive else 1) for step in packed]
        self.assertEqual(semantics.solve(initial, {goals[2]}, split_unit)[0], 2)
        self.assertEqual(semantics.solve(initial, {goals[2]}, packed_unit)[0], 1)

    def test_action_count_uses_same_gates_and_free_closure(self):
        initial, steps, goals = handoff_fixture()
        unit_steps = [replace(step, cost=0 if step.passive else 1) for step in steps]
        self.assertEqual(semantics.solve(initial, {goals[2]}, unit_steps)[0], 2)
        self.assertEqual(semantics.solve(initial, {goals[3]}, unit_steps)[0], 3)
        self.assertIsNone(
            semantics.solve(
                initial - {"membership_usable:directory-example"}, {goals[2]}, unit_steps
            )
        )


class CostInterpretationTests(unittest.TestCase):
    """Synthetic counterexamples, not a production rubric or bounds engine."""

    def test_ordinal_relabeling_can_reverse_path_ranking(self):
        steps = [
            semantics.action("one_hard", {"start"}, {"goal"}, 3),
            semantics.action("medium_a", {"start"}, {"middle"}, 2),
            semantics.action("medium_b", {"middle"}, {"goal"}, 2),
        ]
        original = semantics.solve({"start"}, {"goal"}, steps)
        # Strictly increasing relabeling preserves easy < medium < hard.
        labels = {1: 1, 2: 2, 3: 5}
        relabeled = [replace(step, cost=labels[step.cost]) for step in steps]
        revised = semantics.solve({"start"}, {"goal"}, relabeled)
        self.assertEqual(original, (3, ("one_hard",)))
        self.assertEqual(revised, (4, ("medium_a", "medium_b")))

    def test_rated_subset_winner_need_not_be_global_winner(self):
        rated = [semantics.action("rated_route", {"start"}, {"goal"}, 5)]
        prefix = semantics.action("prefix", {"start"}, {"middle"}, 1)
        self.assertEqual(semantics.solve({"start"}, {"goal"}, rated)[0], 5)
        # These are two hypothetical completions, never imputed production values.
        for missing_cost, expected in ((1, 2), (10, 5)):
            with self.subTest(hypothetical_missing_cost=missing_cost):
                completion = [
                    *rated,
                    prefix,
                    semantics.action("unrated_step", {"middle"}, {"goal"}, missing_cost),
                ]
                self.assertEqual(semantics.solve({"start"}, {"goal"}, completion)[0], expected)

    def test_nonnegative_lower_bound_can_certify_rated_winner(self):
        rated = semantics.action("rated_route", {"start"}, {"goal"}, 5)
        prefix = semantics.action("prefix", {"start"}, {"middle"}, 7)
        # Zero is an optimistic bound, not a rating of the missing step.
        optimistic = [rated, prefix, semantics.action("unrated_step", {"middle"}, {"goal"}, 0)]
        lower_bound = semantics.solve({"start"}, {"goal"}, optimistic)[0]
        rated_upper_bound = semantics.solve({"start"}, {"goal"}, [rated])[0]
        self.assertEqual((lower_bound, rated_upper_bound), (5, 5))
        # Here all competing complete paths have cost 7 + x >= 7 for x >= 0.
        # Test representative completions; the universal inequality is mathematical.
        for missing_cost in (0, 1, 10):
            completion = [
                rated,
                prefix,
                semantics.action("unrated_step", {"middle"}, {"goal"}, missing_cost),
            ]
            self.assertEqual(semantics.solve({"start"}, {"goal"}, completion)[0], 5)


def write_probe_fixture(root, records):
    """Write only invented records, with a matching manifest for CLI E2E tests."""
    manifest = {"snapshot_id": "synthetic-discovery-test", "files": []}
    for kind, filename in raw.FILENAMES.items():
        payload = json.dumps({kind: records[kind]}).encode()
        (root / filename).write_bytes(payload)
        manifest["files"].append(
            {
                "relative_path": filename,
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def discovery_fixture():
    records = fixture()
    # Deliberately invented SID, unrelated to any raw dataset identity.
    records["groups"][0]["ObjectIdentifier"] = "S-1-5-21-1-2-3-512"
    records["groups"][0]["Properties"]["name"] = "renamed-synthetic-group"
    records["computers"].append(record("a-computer-example"))
    records["users"][0]["Aces"].append(
        {"PrincipalSID": "a-computer-example", "RightName": "GenericAll"}
    )
    records["computers"][0]["Properties"]["enabled"] = False
    return records


class RawDiscoveryTests(unittest.TestCase):
    def run_cli(self, root, *options):
        script = Path(raw.__file__).resolve()
        return subprocess.run(
            [
                sys.executable,
                str(script),
                "--raw-dir",
                str(root),
                "--manifest",
                str(root / "manifest.json"),
                *options,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    def test_cli_discovery_needs_no_identity_and_is_stable_after_reordering(self):
        records = discovery_fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_probe_fixture(root, records)
            first = self.run_cli(root, "--discover")
            self.assertEqual(first.returncode, 0, first.stderr)
            report = json.loads(first.stdout)
            aliases = [(s["alias"], s["source"]["id"]) for s in report["sources"]]
            self.assertEqual(
                aliases, [("Source A", "a-computer-example"), ("Source B", "computer-example")]
            )
            self.assertEqual(report["direct_computer_to_target_member_count"], 2)
            self.assertFalse(report["selection"]["enabled_filter"])
            facts = report["direct_candidates"][1]["enabled_facts"]
            self.assertEqual(facts["source"]["status"], "false")
            self.assertEqual(facts["target_user"]["status"], "true")
            explicit = self.run_cli(
                root, "--source", "a-computer-example", "--target", report["target"]["id"]
            )
            self.assertEqual(explicit.returncode, 0, explicit.stderr)
            self.assertEqual(
                json.loads(explicit.stdout)["shortest_structural_path"],
                report["sources"][0]["shortest_structural_path"],
            )
            records["computers"].reverse()
            records["users"][0]["Aces"].reverse()
            write_probe_fixture(root, records)
            second = self.run_cli(root, "--discover")
            self.assertEqual(second.returncode, 0, second.stderr)
            revised = json.loads(second.stdout)
            self.assertEqual([(s["alias"], s["source"]["id"]) for s in revised["sources"]], aliases)

    def test_cli_ambiguous_or_missing_target_requires_explicit_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = fixture()
            write_probe_fixture(root, records)
            missing = self.run_cli(root, "--discover")
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("found 0; supply --target", missing.stderr)
            records = discovery_fixture()
            records["groups"].append(record("S-1-5-21-4-5-6-512"))
            write_probe_fixture(root, records)
            ambiguous = self.run_cli(root, "--discover")
            self.assertNotEqual(ambiguous.returncode, 0)
            self.assertIn("found 2; supply --target", ambiguous.stderr)
            selected = self.run_cli(
                root, "--discover", "--target", records["groups"][0]["ObjectIdentifier"]
            )
            self.assertEqual(selected.returncode, 0, selected.stderr)
            self.assertEqual(
                json.loads(selected.stdout)["selection"]["target_rule"], "explicit --target"
            )
            incompatible = self.run_cli(root, "--discover", "--source", "computer-example")
            self.assertNotEqual(incompatible.returncode, 0)
            self.assertIn("cannot be combined", incompatible.stderr)

    def test_structural_join_ignores_both_enabled_states_and_reports_evidence(self):
        for source_value, target_value in product((True, False, None), repeat=2):
            with self.subTest(source=source_value, target=target_value):
                records = fixture()
                for plural, value in (("computers", source_value), ("users", target_value)):
                    props = records[plural][0]["Properties"]
                    props.pop("enabled", None)
                    if value is not None:
                        props["enabled"] = value
                nodes, evidence, _, _ = raw.build_projection(records)
                self.assertEqual(
                    len(raw.find_direct_candidates(nodes, evidence, "group-example")), 1
                )
                facts = raw.collect_enabled_facts(records)
                for identifier, value, plural in (
                    ("computer-example", source_value, "computers"),
                    ("user-example", target_value, "users"),
                ):
                    expected = "unknown" if value is None else str(value).lower()
                    self.assertEqual(facts[identifier]["status"], expected)
                    observation = facts[identifier]["observations"][0]
                    self.assertEqual(observation["pointer"], f"#/{plural}/0/Properties")
                    self.assertEqual(observation["field"], "enabled")
                    self.assertEqual(observation["present"], value is not None)

    def test_duplicate_enabled_conflict_and_invalid_value_do_not_prune(self):
        records = fixture()
        duplicate = record("user-example")
        duplicate["Properties"]["enabled"] = False
        records["users"].append(duplicate)
        nodes, evidence, _, _ = raw.build_projection(records)
        self.assertEqual(len(raw.find_direct_candidates(nodes, evidence, "group-example")), 1)
        facts = raw.collect_enabled_facts(records)["user-example"]
        self.assertEqual(facts["status"], "conflicting")
        self.assertEqual(len(facts["observations"]), 2)
        duplicate["Properties"]["enabled"] = "true"
        self.assertEqual(raw.collect_enabled_facts(records)["user-example"]["status"], "unknown")

    def test_empty_discovery_is_explicit_and_hash_mismatch_fails(self):
        records = discovery_fixture()
        records["users"][0]["Aces"] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = write_probe_fixture(root, records)
            manifest = json.loads(manifest_path.read_text())
            report = raw.analyze(root, manifest, discover=True)
            self.assertEqual(report["sources"], [])
            self.assertEqual(report["direct_computer_to_target_member_count"], 0)
            path = root / raw.FILENAMES["computers"]
            path.write_bytes(path.read_bytes() + b" ")
            result = self.run_cli(root, "--discover")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match manifest", result.stderr)


if __name__ == "__main__":
    unittest.main()
