/* Read-only adapters. No discovery, scoring or inference. Works under file:// and Node. */
(function (root) {
  "use strict";
  const cost = (v) =>
    typeof v === "number" && Number.isFinite(v) && v >= 0 ? v : null;
  const text = (v) => (typeof v === "string" ? v : "");
  function uniqueAssumptions(steps) {
    const facts = new Map();
    for (const step of steps)
      for (const f of step.assumptions) {
        // Same condition across steps counts once; each step keeps its full fact.
        const key = JSON.stringify([f.predicate, f.subject, f.target, f.value]);
        if (!facts.has(key)) facts.set(key, f);
      }
    return [...facts.values()];
  }
  function sourceCapability(view, cell) {
    const sources = view.original?.scope?.request?.sources;
    const source = Array.isArray(sources)
      ? sources.find(
          (s) =>
            s?.source_id === cell.source_id &&
            s?.node_id === cell.source_node_id,
        )
      : null;
    const profile = text(source?.profile_kind);
    if (profile === "computer_usable_identity")
      return "Danh tính mạng máy dùng được";
    if (profile === "user_usable_identity") return "Danh tính User dùng được";
    return profile || "Chưa có thông tin trong báo cáo";
  }
  function limitation(s) {
    const reason = text(s?.truncation_reason || s?.reason);
    const reasons = {
      expansion_limit_reached: "Đã hết ngân sách tìm kiếm",
      path_limit_reached: "Đã đạt số đường tối đa được yêu cầu",
      step_limit_reached: "Đã đạt giới hạn số bước",
    };
    const parts = [];
    if (reason)
      parts.push(
        reasons[reason] ? reasons[reason] + "." : "Giới hạn báo cáo: " + reason + ".",
      );
    else if (s?.truncated === true)
      parts.push("Tìm kiếm bị giới hạn; báo cáo chưa nêu lý do cụ thể.");
    const unknown = Object.keys(s?.unknown || {}).filter(
      (k) => s.unknown[k] > 0,
    );
    if (unknown.length)
      parts.push(
        "Điều kiện thiếu thông tin: " + unknown.slice(0, 3).join(", ") + ".",
      );
    if (s?.status === "blocked")
      parts.push("Báo cáo ghi thiếu điều kiện để tiếp tục.");
    return parts.join(" ");
  }
  function normalize(input) {
    if (!input || typeof input !== "object" || Array.isArray(input))
      throw Error("Cần một JSON object kết quả neo.");
    if (input.version === "neo-remediation-rediscovery/1") {
      if (
        !Array.isArray(input.interventions) ||
        !Array.isArray(input.rows) ||
        input.rows.length > 4000
      )
        throw Error(
          "Kết quả can thiệp thiếu interventions/rows hoặc quá nhiều hàng.",
        );
      const byCase = new Map();
      for (const c of input.interventions) {
        if (!text(c.case) || byCase.has(c.case))
          throw Error("Mã can thiệp thiếu hoặc trùng.");
        byCase.set(c.case, { ...c, pairs: new Map() });
      }
      for (const row of input.rows) {
        const c = byCase.get(row.case);
        if (
          !c ||
          !text(row.strategy) ||
          !text(row.source) ||
          !text(row.target) ||
          !["before", "after"].includes(row.phase)
        )
          throw Error(
            "Hàng can thiệp thiếu nguồn/đích/strategy/phase hoặc sai case.",
          );
        const key = JSON.stringify([row.strategy, row.source, row.target]);
        if (!c.pairs.has(key))
          c.pairs.set(key, {
            strategy: row.strategy,
            source: row.source,
            goal: row.target,
          });
        const pair = c.pairs.get(key);
        if (pair[row.phase]) throw Error("Kết quả can thiệp trùng phase.");
        pair[row.phase] = row;
      }
      const result = normalize({
        version: "neo-remediation-rediscovery-summary/1",
        title: input.title,
        scenario: input.scenario,
        cases: [...byCase.values()].map(({ pairs, ...c }) => ({
          ...c,
          queries: [...pairs.values()],
        })),
      });
      result.original = input;
      return result;
    }
    if (input.schema_version === "neo-decision-sample/1.0.0") {
      if (
        !Array.isArray(input.cells) ||
        !input.cells.length ||
        input.cells.length > 1000 ||
        !input.selected_point?.edge ||
        !input.totals
      )
        throw Error("Khảo sát thiếu cells/selected_point/totals.");
      for (const c of input.cells) {
        if (
          !text(c.source_node_id) ||
          !text(c.target_node_id) ||
          !text(c.source) ||
          !text(c.target) ||
          !c.intervention_result?.before ||
          !c.intervention_result?.after ||
          !c.intervention_result?.effort ||
          !Array.isArray(c.programs)
        )
          throw Error("Cặp khảo sát thiếu thông tin.");
        for (const p of c.programs)
          if (!Array.isArray(p.work_units)) throw Error("Thiếu work units.");
      }
      return {
        kind: "survey",
        title: text(input.title) || "Báo cáo đã nhập · Khảo sát nhiều nguồn",
        cells: input.cells,
        totals: input.totals,
        point: input.selected_point,
        original: input,
      };
    }
    if (input.version === "neo-remediation-rediscovery-summary/1") {
      if (
        !Array.isArray(input.cases) ||
        !input.cases.length ||
        input.cases.length > 100
      )
        throw Error("Danh sách remediation không hợp lệ.");
      for (const c of input.cases) {
        if (
          !Array.isArray(c.queries) ||
          !c.queries.length ||
          !Array.isArray(c.removed_edges)
        )
          throw Error("Thiếu queries/removed_edges.");
        if (c.removed_edges.length > 100)
          throw Error("Quá nhiều quan hệ cho một view.");
        for (const e of c.removed_edges)
          if (!text(e.source) || !text(e.target) || !text(e.kind))
            throw Error("Quan hệ thiếu ID/type.");
        for (const q of c.queries)
          if (!q.before || !q.after) throw Error("Thiếu kết quả trước/sau.");
      }
      return {
        kind: "remediation",
        title: text(input.title) || "Báo cáo đã nhập · Can thiệp",
        scenario: text(input.scenario),
        cases: input.cases,
        original: input,
      };
    }
    if (input.version === "neo-viewer-playback/1") {
      if (!Array.isArray(input.programs) || !input.programs.length)
        throw Error("Playback thiếu chương trình.");
      if (!text(input.source) || !text(input.target))
        throw Error("Playback thiếu nguồn/đích.");
      for (const p of input.programs) {
        validateSteps(p.steps);
        if (p.C != null && cost(p.C) === null)
          throw Error("C phải là số không âm hoặc null.");
        if (
          !Array.isArray(p.ledger) ||
          p.ledger.length > 500 ||
          !Array.isArray(p.assumptions)
        )
          throw Error("Ledger/assumptions không hợp lệ.");
        if (p.ledger.some((u) => !u || typeof u !== "object"))
          throw Error("Work unit không hợp lệ.");
      }
      for (const n of Object.values(input.labels || {})) {
        if (
          !n ||
          !text(n.label) ||
          (n.x !== undefined && !Number.isFinite(n.x)) ||
          (n.y !== undefined && !Number.isFinite(n.y))
        )
          throw Error("Nhãn hoặc vị trí không hợp lệ.");
      }
      if (input.programs.length > 200)
        throw Error("Tối đa 200 chương trình/view.");
      return {
        ...input,
        title: text(input.title) || "Báo cáo đã nhập · Đường và công sức",
        kind: "paths",
        programs: input.programs.map((p) => ({
          ...p,
          assumptionsComplete: true,
        })),
      };
    }
    const s = input.semantic || input;
    if (!s.materialized || !Array.isArray(s.candidates))
      throw Error(
        "Hỗ trợ kết quả query CLI, decision-sample, playback và remediation results/summary; không hỗ trợ snapshot, query đầu vào hoặc cells.jsonl.",
      );
    if (!text(s.materialized.initial_actor) || !text(s.materialized.target))
      throw Error("Query thiếu nguồn/đích.");
    if (s.candidates.length > 200)
      throw Error("Tối đa 200 chương trình/view; hãy dùng output query riêng.");
    const ranked = s.top_k?.programs;
    const selected =
      Array.isArray(ranked) && ranked.length
        ? ranked
        : s.candidates.map((c) => ({ candidate_id: c.candidate_id }));
    if (selected.length > 200) throw Error("Quá 200 mục Top-K/view.");
    const programs = selected.map((p) => {
      const c = s.candidates.find((c) => c.candidate_id === p.candidate_id);
      if (!c) throw Error("Top-K tham chiếu candidate không có trong file.");
      if (!Array.isArray(c.transition_history))
        throw Error("Candidate thiếu transition_history.");
      const steps = c.transition_history.map((t) => {
        const r = t.result;
        if (!r?.request) throw Error("Transition thiếu request.");
        return {
          ...r.request,
          assumptionsComplete:
            Array.isArray(r.decisions) &&
            r.decisions.every((d) => d && typeof d === "object"),
          assumptions: (Array.isArray(r.decisions) ? r.decisions : [])
            .map((d) => d?.fact)
            .filter((f) => f?.origin === "declared_assumption"),
        };
      });
      validateSteps(steps);
      return {
        id: p.candidate_id,
        C: cost(p.effort),
        steps,
        assumptions: uniqueAssumptions(steps),
        assumptionsComplete: steps.every((step) => step.assumptionsComplete),
        ledger: Object.values(p.work_unit_ledger || {}),
      };
    });
    const unknown = Object.create(null);
    for (const attempt of Array.isArray(s.attempts) ? s.attempts : [])
      for (const predicate of Array.isArray(attempt?.unknown)
        ? attempt.unknown
        : [])
        if (text(predicate)) unknown[predicate] = (unknown[predicate] || 0) + 1;
    return {
      kind: "paths",
      title: "Kết quả đã nhập",
      source: s.materialized.initial_actor,
      target: s.materialized.target,
      context: s.materialized.runtime_context?.authentication_context,
      labels: {},
      programs,
      minimum:
        s.engine_reported_guarantees?.is_minimum_proven_over_scope === true,
      noPath:
        s.engine_reported_guarantees?.is_no_path_proven_over_scope === true,
      truncated: s.truncated === true,
      reason: s.truncation_reason,
      expansions: s.expansions,
      budget: s.materialized.budget,
      status: s.status,
      unknown,
      provenance:
        input.reproducibility?.git_commit ||
        input.reproducibility?.commit ||
        "File người dùng · chưa xác minh nguồn",
    };
  }
  function validateSteps(steps) {
    if (!Array.isArray(steps) || steps.length > 120)
      throw Error("Thiếu bước hoặc quá 120 bước/chương trình.");
    for (const r of steps)
      if (
        !text(r.actor) ||
        !text(r.source) ||
        !text(r.target) ||
        !text(r.technique_id)
      )
        throw Error("Bước thiếu actor/source/target/technique_id.");
  }
  function outcome(s) {
    if (s?.reached === true)
      return {
        label: s.outcome === "bypass" ? "Còn đường vòng" : "Có đường",
        tone: "blue",
      };
    if (s?.no_path_proven === true)
      return { label: "Chặn trong phạm vi xét", tone: "green" };
    return { label: "Chưa kết luận", tone: "amber" };
  }
  const api = { normalize, outcome, cost, sourceCapability, limitation };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.NeoViewModel = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
