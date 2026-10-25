/* Read-only adapters. No discovery, scoring or inference. Works under file:// and Node. */
(function (root) {
  "use strict";
  const cost = (v) =>
    typeof v === "number" && Number.isFinite(v) && v >= 0 ? v : null;
  const text = (v) => (typeof v === "string" ? v : "");
  function normalize(input) {
    if (!input || typeof input !== "object" || Array.isArray(input))
      throw Error("Cần một JSON object kết quả neo.");
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
        title: "WRAITH · Remediation",
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
      return { ...input, kind: "paths" };
    }
    const s = input.semantic || input;
    if (!s.materialized || !Array.isArray(s.candidates))
      throw Error(
        "Hỗ trợ JSON query CLI (semantic/candidates), playback và remediation summary. Không hỗ trợ snapshot hoặc decision-sample.",
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
          assumptions: (r.decisions || [])
            .map((d) => d.fact)
            .filter((f) => f?.origin === "declared_assumption"),
        };
      });
      validateSteps(steps);
      return {
        id: p.candidate_id,
        C: cost(p.effort),
        steps,
        ledger: Object.values(p.work_unit_ledger || {}),
      };
    });
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
        label: s.outcome === "bypass" ? "Còn bypass" : "Có witness",
        tone: "blue",
      };
    if (s?.no_path_proven === true)
      return { label: "Chặn trong scope", tone: "green" };
    return { label: "Chưa kết luận", tone: "amber" };
  }
  const api = { normalize, outcome, cost };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.NeoViewModel = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
