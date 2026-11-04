"""Open a BloodHound export and answer analyst questions for the local NEO app.

The thesis runners stay strict: any record they cannot read stops the run. An analyst
opening an unfamiliar export needs the opposite, so this module keeps going and lists
everything it set aside in the open report. It reuses the same parser, facts and search.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
import zipfile
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from scripts.neo_domain import build_survey, input_coverage, scenario_profile, techniques_for
from scripts.neo_import import KINDS, prepare_records
from scripts.neo_remediation import classify
from src.data.manifest import generate_manifest
from src.engine.batch import _query_for_cell
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.ranking.effort_profiles import load_effort_profile
from src.engine.semantics.credentials import replay_path
from src.engine.top_k import collect_assessments, effort_programs
from src.parser import (
    DirectGraphBuilder,
    ErrorPolicy,
    IdentityNormalizer,
    ManifestRawDataLoader,
    RecordError,
)
from src.parser.adapters import adapt_bloodhound_v3_records
from src.parser.adapters.bloodhound_v3 import _ID_KEYS
from src.parser.builder import _REFERENCE_KIND_KEYS, _kind, _reference_from_item
from src.parser.cli import canonicalize_graph
from src.parser.loader import TimeProvenancePolicy
from src.parser.snapshot_facts import serialize_snapshot

EXPORT_FILE = re.compile(r"^(?:(?P<prefix>.+)_)?domains\.json$", re.IGNORECASE)
MAX_EXPANDED_BYTES = 8 * 1024**3  # Refuses a zip bomb before anything is written to disk.
# shortcut: draws control relationships first and drops the rest, add a per-kind list if needed.
MAX_DIRECT_NEIGHBORS = 24
MAX_BUILD_PASSES = 25
SEARCH_BUDGET = 4096  # The budget of the fixed comparison in the thesis, so results line up.
UNRESOLVED_REFERENCE = re.compile(r"unresolvable (?:\w+ )?reference '([^']+)'")
ACE_RIGHTS = {"GenericAll", "WriteDacl", "ForceChangePassword"}
# Host access edges name a builtin local group and the older flat collector field for it.
LOCAL_ACCESS = {
    "AdminTo": ("S-1-5-32-544", "LocalAdmins"),
    "CanPSRemote": ("S-1-5-32-580", "PSRemoteUsers"),
}


class ChooseExport(ValueError):
    """The source holds several exports, so the analyst must pick one."""

    def __init__(self, exports):
        super().__init__("Nguồn dữ liệu có nhiều bản xuất; hãy chọn một bản.")
        self.exports = exports


def _export_of(name):
    match = EXPORT_FILE.match(Path(name).name)
    return None if match is None else match["prefix"] or ""


def _domain_names(content):
    payload = json.loads(content.decode("utf-8-sig"))
    # Collector v3 files keep the records under their type name; later versions use "data".
    records = payload.get("data") or payload.get("domains") or []
    return sorted(
        (r.get("Properties") or {}).get("name") or r.get("Name") or r.get("ObjectIdentifier")
        for r in records
    )


def inspect_source(path):
    """List the exports in a folder or zip, without loading the records."""
    path = Path(path)
    found = {}
    if path.is_dir():
        for child in path.iterdir():
            if child.is_file() and (export := _export_of(child.name)) is not None:
                found[export] = _domain_names(child.read_bytes())
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if (export := _export_of(info.filename)) is not None:
                    found[export] = _domain_names(archive.read(info))
    return [{"export": k, "domains": found[k]} for k in sorted(found)]


def list_sources(root):
    """Offer each distinct export under ``root``; an unpacked folder wins over its zip."""
    sources = {}
    root = Path(root)
    children = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name)) if root.is_dir() else []
    for path in children:
        try:
            exports = inspect_source(path)
        except OSError, ValueError, zipfile.BadZipFile:
            continue  # An unreadable neighbour must not hide the datasets beside it.
        for item in exports:
            key = (item["export"], tuple(item["domains"]))
            sources.setdefault(key, {**item, "path": str(path), "name": path.name})
    return list(sources.values())


def _unpack(archive_path, destination):
    """Flatten JSON members only, so a crafted member path cannot leave ``destination``."""
    try:
        archive = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile:
        raise ValueError("Tệp này không phải tệp zip hợp lệ.") from None
    with archive:
        members = [i for i in archive.infolist() if i.filename.casefold().endswith(".json")]
        if sum(i.file_size for i in members) > MAX_EXPANDED_BYTES:
            raise ValueError("Tệp nén giải ra quá lớn.")
        destination.mkdir(parents=True)
        for info in members:
            target = destination / Path(info.filename.replace("\\", "/")).name
            if target.exists():
                raise ValueError(f"Tệp nén có hai tệp trùng tên: {target.name}")
            target.write_bytes(archive.read(info))
    return destination


def _time_policy(root, export):
    match = re.search(r"\d{14}", export)
    if match:
        moment = datetime.strptime(match[0], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        origin = "the export filename"
    else:
        file = next(p for p in root.iterdir() if _export_of(p.name) == export)
        moment = datetime.fromtimestamp(file.stat().st_mtime, UTC).replace(microsecond=0)
        origin = "the modification time of the export file"
    return TimeProvenancePolicy(
        timestamp=moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        status="assumed",
        reason=f"Taken from {origin}, not observed at collection; no temporal comparison is made.",
    )


def _reference_kinds(value, removed):
    """Forget a reference kind the builder cannot type, so it resolves the object by ID."""
    if isinstance(value, list):
        for item in value:
            _reference_kinds(item, removed)
    elif isinstance(value, dict):
        for key in _REFERENCE_KIND_KEYS:
            if value.get(key) is not None:
                try:
                    _kind(value[key])
                except ValueError:
                    removed[str(value[key])] += 1
                    del value[key]
        for item in value.values():
            _reference_kinds(item, removed)


def _without_identifier(value, identifier):
    """Drop list items that point at ``identifier``; blank a single-valued reference."""
    if isinstance(value, list):
        kept = []
        for item in value:
            if item == identifier or (isinstance(item, dict) and _points_at(item, identifier)):
                continue
            kept.append(_without_identifier(item, identifier))
        return kept
    if isinstance(value, dict):
        return {
            k: None if v == identifier else _without_identifier(v, identifier)
            for k, v in value.items()
        }
    return value


def _points_at(item, identifier):
    return any(k.casefold() in _ID_KEYS and v == identifier for k, v in item.items())


def _adapt(records):
    """Set aside identifiers whose scope cannot be established, then adapt the rest."""
    dropped = {}
    while True:
        try:
            return adapt_bloodhound_v3_records(records), dropped
        except RecordError as error:
            identifier = error.record_id
            if not identifier or identifier in dropped:
                raise
            dropped[identifier] = str(error).split(": ", 1)[-1]
            records = [
                replace(r, data=_without_identifier(r.data, identifier))
                for r in records
                if r.data.get("ObjectIdentifier") != identifier
            ]


class _Collect(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


@contextmanager
def _collect_warnings():
    """Keep skipped-record diagnostics for the report instead of printing them."""
    logger, handler = logging.getLogger("src.parser"), _Collect()
    propagate, logger.propagate = logger.propagate, False
    logger.addHandler(handler)
    try:
        yield handler.messages
    finally:
        logger.removeHandler(handler)
        logger.propagate = propagate


def _build(records, metadata):
    with _collect_warnings() as skipped:
        normalized = IdentityNormalizer().normalize_records(
            records, error_policy=ErrorPolicy.LOG_WARNING
        )
        canonical, facts = DirectGraphBuilder(
            retain_unresolved_members=True, metadata=metadata
        ).build_snapshot(normalized, error_policy=ErrorPolicy.LOG_WARNING)
    graph = EngineGraph.from_snapshot(serialize_snapshot(canonicalize_graph(canonical), facts))
    return graph, skipped


def _build_without_outside_references(records, metadata):
    """Keep a record that mentions an object outside this export, minus that one mention.

    The builder rejects the whole record on such a reference, so one right held by another
    domain's group would erase almost every object of a child-domain export.
    """
    outside = {}
    for _ in range(MAX_BUILD_PASSES):
        graph, skipped = _build(records, metadata)
        found = {m[1] for line in skipped if (m := UNRESOLVED_REFERENCE.search(line))}
        if not found:
            break
        for identifier in found:
            mentions = sum(1 for line in skipped if f"'{identifier}'" in line)
            outside[identifier] = outside.get(identifier, 0) + mentions
            records = tuple(
                replace(r, data=_without_identifier(r.data, identifier)) for r in records
            )
    return records, graph, skipped, outside


def _members(field_value, kept):
    """Filter a ``[...]`` or ``{"Results": [...]}`` collection in place, counting removals."""
    items = field_value["Results"] if isinstance(field_value, dict) else field_value
    before = len(items)
    items[:] = [i for i in items if kept(i)]
    return before - len(items)


def remove_relationship(records, source, kind, target):
    """Return copied records without the collector evidence of one direct relationship."""

    # Collectors write GUIDs in upper case and the graph stores them in lower case.
    source, target = source.casefold(), target.casefold()

    def other_than(identifier, field):
        def kept(item):
            return _reference_from_item(item, field=field)[0].casefold() != identifier

        return kept

    def same(value, identifier):
        return isinstance(value, str) and value.casefold() == identifier

    changed, removed = deepcopy(records), Counter()
    for record in changed:
        data = record.data
        identifier = data.get("ObjectIdentifier")
        if kind == "MemberOf" and same(identifier, target) and data.get("Members"):
            removed["Members"] += _members(data["Members"], other_than(source, "Members"))
        if (
            kind == "MemberOf"
            and same(identifier, source)
            and same(data.get("PrimaryGroupSID"), target)
        ):
            data["PrimaryGroupSID"] = None
            removed["PrimaryGroupSID"] += 1
        if kind == "HasSession" and same(identifier, source):
            for field in ("Sessions", "PrivilegedSessions", "RegistrySessions"):
                if data.get(field):
                    removed[field] += _members(data[field], other_than(target, field))
        if kind in ACE_RIGHTS and same(identifier, target) and data.get("Aces"):
            same_principal = other_than(source, "Aces")
            removed["Aces"] += _members(
                data["Aces"],
                lambda a, base=same_principal: (
                    base(a) or str(a.get("RightName", "")).casefold() != kind.casefold()
                ),
            )
        if kind in LOCAL_ACCESS and same(identifier, target):
            group_sid, flat_field = LOCAL_ACCESS[kind]
            if data.get(flat_field):
                removed[flat_field] += _members(data[flat_field], other_than(source, flat_field))
            for group in data.get("LocalGroups") or []:
                if str(group.get("ObjectIdentifier", "")).upper().endswith(group_sid[-4:]):
                    removed["LocalGroups"] += _members(group, other_than(source, "LocalGroups"))
    return changed, {k: v for k, v in removed.items() if v}


@dataclass
class Workspace:
    """One opened export: its adapted records, its graph and what was set aside."""

    name: str
    records: tuple
    graph: EngineGraph
    domain_sid: str | None
    report: dict
    # Both sides of a removal need the "before" answer, and a big graph takes seconds per search.
    _answers: dict = field(default_factory=dict)

    def search(self, text, *, limit=30):
        """Match node names without case; exact and prefix matches come first."""
        needle = text.strip().casefold()
        if not needle:
            return []
        hits = [
            n
            for n in self.graph.nodes()
            if needle in n.get("label", "").casefold() or needle == n["id"].casefold()
        ]
        hits.sort(key=lambda n: (_rank(n, needle), n.get("label", "")))
        return [_node_view(n) for n in hits[:limit]]

    def neighbors(self, node_id, *, limit=MAX_DIRECT_NEIGHBORS):
        """Return the relationships touching one node, capped so a big group stays readable."""
        node = self.graph.node(node_id)
        edges = [e for e in self.graph.edges() if node_id in (e["source"], e["target"])]
        # Inbound control and outbound reach matter more to the analyst than a long member list.
        edges.sort(key=lambda e: (e["kind"] == "MemberOf" and e["target"] == node_id, e["kind"]))
        shown = edges[:limit]
        ids = {node_id} | {e["source"] for e in shown} | {e["target"] for e in shown}
        return {
            "node": _node_view(node),
            "nodes": [_node_view(self.graph.node(i)) for i in sorted(ids)],
            "edges": [_edge_view(e) for e in shown],
            "total_edges": len(edges),
            "counts": dict(Counter(e["kind"] for e in edges)),
        }

    def targets(self):
        """The Domain Admins and Enterprise Admins groups observed in the selected domain."""
        if self.domain_sid is None:
            return []
        wanted = {self.domain_sid + "-512", self.domain_sid + "-519"}
        return [_node_view(n) for n in self.graph.nodes() if n["id"] in wanted]

    def find_paths(self, source, target, *, scenario="identity", max_expansions=SEARCH_BUDGET):
        key = (source, target, scenario, max_expansions)
        if key not in self._answers:
            self._answers[key] = _search(
                self.graph, self.domain_sid, source, target, scenario, max_expansions
            )
        return self._answers[key]

    def try_removal(
        self, edge_source, kind, edge_target, source, target, *, scenario="identity", **budget
    ):
        """Search again from scratch on a rebuilt graph without one relationship."""
        before = self.find_paths(source, target, scenario=scenario, **budget)
        records, removed = remove_relationship(self.records, edge_source, kind, edge_target)
        evidence = [
            p["attribute"]
            for e in self.graph.edges()
            if (e["source"], e["kind"], e["target"]) == (edge_source, kind, edge_target)
            for p in e["provenance"]
        ]
        edit = {
            "source": edge_source,
            "kind": kind,
            "target": edge_target,
            "removed_observations": removed,
            "evidence": sorted(set(evidence)),
        }
        if not removed:
            return {"edit": {**edit, "status": "derived_only"}, "before": before, "after": None}
        graph, _ = _build(records, self.graph.metadata)
        remains = any(
            (e["source"], e["kind"], e["target"]) == (edge_source, kind, edge_target)
            for e in graph.edges()
        )
        after = _search(graph, self.domain_sid, source, target, scenario, before["max_expansions"])
        if after["outcome"] == "reachable":
            after["outcome"] = "bypass"
        status = "other_support_remains" if remains else "removed"
        return {"edit": {**edit, "status": status}, "before": before, "after": after}


def _rank(node, needle):
    label = node.get("label", "").casefold()
    if label == needle or label.split("@")[0] == needle or label.split(".")[0] == needle:
        return 0
    return 1 if label.startswith(needle) else 2


def _node_view(node):
    return {
        "id": node["id"],
        "label": node.get("label") or node["id"],
        "kind": node["kind"],
        "domain": node.get("domain"),
        "boundary": bool(node.get("is_boundary")),
        "enabled": node.get("enabled"),
    }


def _edge_view(edge):
    return {
        "id": edge["id"],
        "source": edge["source"],
        "kind": edge["kind"],
        "target": edge["target"],
    }


def _search(graph, domain_sid, source, target, scenario, max_expansions):
    try:
        _, request = build_survey(
            graph,
            max_expansions=max_expansions,
            max_paths=10,
            domain_sid=domain_sid,
            scenario=scenario,
            source_ids=[source],
        )
    except ValueError as error:
        if "--source" not in str(error):
            raise
        raise ValueError(
            "Đối tượng này không dùng được làm điểm xuất phát: chỉ nhận tài khoản hoặc máy "
            "đang hoạt động trong miền đang mở."
        ) from None
    sources = {s.node_id: s for s in request.sources}
    goals = {g.target_node_id: g for g in request.resolve_target_goals()}
    if target not in goals:
        raise ValueError("Mục tiêu phải là Domain Admins hoặc Enterprise Admins của miền đang mở.")
    query, error = _query_for_cell(
        request,
        sources[source],
        goals[target],
        graph,
        techniques_for(scenario),
        request.common_budget,
        scenario_policy=scenario_profile(graph, scenario),
        effort_profile=load_effort_profile("neo-c-v1"),
        search_order="neo_refine",
    )
    if error is not None:
        raise ValueError(str(error))
    result = run_attack_query(query, graph)
    return _result_view(result, graph, request, scenario, max_expansions)


def _result_view(result, graph, request, scenario, max_expansions):
    """Replay every ranked path, then shape it as the viewer's playback programs."""
    assessments = collect_assessments(result)
    programs_found, exclusions = effort_programs(result)
    ranked = (result.top_k_result or {}).get("programs") or programs_found
    programs, seen = [], set()
    for entry in ranked:
        candidate = entry["candidate_id"]
        path = result.paths[int(candidate.rsplit("_", 1)[1]) - 1]
        state = replay_path(path, graph, result.materialized_query.catalog)
        if state != path.final_state or not result.materialized_query.is_success_state(state):
            raise AssertionError("Witness replay or goal diverged")
        assessment = assessments.get(candidate, {})
        ledger = assessment.get("work_unit_basis", {})
        if sum(u["effort_cost"] for u in ledger.values()) != entry["effort"]:
            raise AssertionError("C differs from the unique work ledger")
        steps = []
        for step in path.transition_history:
            request_ = step.result.request
            for node in (request_.actor, request_.source, request_.target):
                seen.add(node)
            steps.append(
                {
                    "actor": request_.actor,
                    "source": request_.source,
                    "target": request_.target,
                    "technique_id": request_.technique_id,
                    "edge": _step_edge(graph, step.edge_id),
                    "assumptions": [
                        _fact_view(d.fact)
                        for d in step.result.decisions
                        if d.fact is not None and d.fact.origin == "declared_assumption"
                    ],
                }
            )
        programs.append(
            {
                "id": candidate,
                "C": entry["effort"],
                "steps": steps,
                "ledger": list(ledger.values()),
                "assumptions": _unique_facts(steps),
            }
        )
    unknown = Counter(k for a in result.attempts for k in a.unknown)
    outcome = classify(
        result.final_goal_reached,
        result.is_no_path_proven_over_scope,
        result.truncated,
        bool(unknown),
    )
    labels = {}
    query = result.materialized_query
    for node_id in seen | {query.initial_actor, query.target}:
        node = graph.node(node_id) if _has_node(graph, node_id) else None
        labels[node_id] = {
            "label": (node or {}).get("label") or node_id,
            "kind": (node or {}).get("kind") or "Unknown",
        }
    return {
        "version": "neo-viewer-playback/1",
        "title": "Kết quả phân tích",
        "source": result.materialized_query.initial_actor,
        "target": result.materialized_query.target,
        "labels": labels,
        "programs": programs,
        "outcome": "reachable" if outcome == "bypass" else outcome,
        "reached": result.final_goal_reached,
        "minimum": result.is_minimum_proven_over_scope,
        "noPath": result.is_no_path_proven_over_scope,
        "no_path_proven": result.is_no_path_proven_over_scope,
        "truncated": result.truncated,
        "reason": result.truncation_reason,
        "expansions": result.expansions,
        "max_expansions": max_expansions,
        "status": result.status,
        "unknown": dict(unknown),
        "rating_exclusions": exclusions,
        "scenario": scenario,
        "coverage_notes": input_coverage(graph, request, scenario)["notes"],
    }


def _has_node(graph, node_id):
    try:
        graph.node(node_id)
    except KeyError:
        return False
    return True


def _step_edge(graph, edge_id):
    """The observed relationship behind a step; None when the chain itself created it."""
    if edge_id is None:
        return None
    try:
        return _edge_view(graph.edge(edge_id))
    except KeyError:
        return None


def _fact_view(fact):
    return {
        "predicate": fact.predicate,
        "subject": fact.subject,
        "target": fact.target,
        "value": fact.value,
    }


def _unique_facts(steps):
    facts = {}
    for step in steps:
        for fact in step["assumptions"]:
            facts.setdefault(json.dumps(fact, sort_keys=True, default=str), fact)
    return list(facts.values())


def open_dataset(source, *, export=None, name=None):
    """Load one export from a folder or zip and report everything it did not use."""
    source = Path(source)
    with tempfile.TemporaryDirectory(prefix="neo-open-") as temporary:
        temp = Path(temporary).resolve()  # The manifest refuses a root under a symlink like /var.
        root = source if source.is_dir() else _unpack(source, temp / "raw")
        exports = inspect_source(root)
        if not exports:
            raise ValueError("Không thấy tệp domains của BloodHound trong nguồn dữ liệu.")
        if export is None:
            if len(exports) != 1:
                raise ChooseExport(exports)
            export = exports[0]["export"]
        if export not in {e["export"] for e in exports}:
            raise ValueError("Không có bản xuất này trong nguồn dữ liệu.")
        manifest = generate_manifest(
            root,
            dataset_id="local-export",
            collector_name="unknown",
            collector_version=None,
            collected_at=None,
        )
        loader = ManifestRawDataLoader(manifest, time_policy=_time_policy(root, export))
        raw = list(loader.load(root))
    return _assemble(raw, export, name or source.stem, manifest)


def _assemble(raw, export, name, manifest):
    excluded = Counter(r.kind for r in raw if r.kind.casefold() not in KINDS)
    chosen = [r for r in raw if Path(r.provenance["raw_file"]).name.startswith(export)]
    domains = [r for r in chosen if r.kind.casefold() == "domains"]
    # One observed domain lets foreign identities become boundary objects, as in the thesis runs.
    records, preparation = (
        prepare_records(raw, export) if len(domains) == 1 else prepare_records(chosen, None)
    )
    records = deepcopy(records)
    untyped = Counter()
    for record in records:
        _reference_kinds(record.data, untyped)
    adapted, dropped_identifiers = _adapt(records)
    adapted, graph, skipped, outside = _build_without_outside_references(
        adapted,
        {
            "snapshot_id": manifest["snapshot_id"],
            "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "code_version": "neo-workspace",
        },
    )
    if not graph.nodes():
        raise ValueError("Không đọc được đối tượng nào từ bản xuất này.")
    domain_sid = preparation["selected_domain_sid"]
    if domain_sid is None and len(domains) >= 1:
        domain_sid = domains[0].data["ObjectIdentifier"]
    return Workspace(
        name=name,
        records=adapted,
        graph=graph,
        domain_sid=domain_sid,
        report={
            "name": name,
            "export": export,
            "domains": [d.data["Properties"].get("name") for d in domains],
            "nodes": dict(Counter(n["kind"] for n in graph.nodes())),
            "edges": dict(Counter(e["kind"] for e in graph.edges())),
            "unused_record_kinds": dict(excluded),
            "boundary_objects": len(preparation["boundary_representations"]),
            "omitted_empty_records": len(preparation["omitted_unreferenced_empty_generated"]),
            "untyped_references": dict(untyped),
            "dropped_identifiers": dropped_identifiers,
            "outside_references": outside,
            "skipped_records": skipped,
            "session_edges": sum(e["kind"] == "HasSession" for e in graph.edges()),
            "failed_session_collections": _failed_sessions(chosen),
        },
    )


def _failed_sessions(records):
    """Count hosts whose session data was never collected, so absence is not read as safety."""
    return sum(
        1
        for r in records
        if r.kind.casefold() == "computers"
        and any(
            (r.data.get(field) or {}).get("Collected") is False
            for field in ("Sessions", "PrivilegedSessions", "RegistrySessions")
        )
    )
