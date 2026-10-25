const { test } = require("node:test");
const assert = require("node:assert/strict");
const M = require("./model.js");
const demo = require("./demo.js");
const fs = require("node:fs");
const path = require("node:path");
const { createHash } = require("node:crypto");
const copy = (x) => JSON.parse(JSON.stringify(x));
test("multi-source survey preserves all pairs and separates cut programs from disconnection", () => {
  const v = M.normalize(demo.survey);
  assert.equal(v.kind, "survey");
  assert.equal(v.cells.length, 10);
  assert.equal(v.totals.programs_cut, 15);
  assert.equal(v.totals.pairs_disconnected, 0);
  assert.equal(new Set(v.cells.map((c) => c.source_node_id)).size, 5);
  assert(
    v.cells.every(
      (c) => c.intervention_result.after.reachability === "reachable",
    ),
  );
  const published = JSON.parse(
    fs.readFileSync(
      path.join(__dirname, "../../reports/neo/decision-sample.json"),
      "utf8",
    ),
  );
  assert.deepEqual(demo.survey, published);
});
function native() {
  return {
    schema_version: "week4-query-result/0.4.0",
    semantic: {
      materialized: {
        initial_actor: "user",
        target: "group",
        runtime_context: { authentication_context: "host" },
      },
      candidates: [
        {
          candidate_id: "generated_0001",
          transition_history: [
            {
              result: {
                request: {
                  actor: "user",
                  source: "via-group",
                  target: "group",
                  technique_id: "genericall_add_member",
                },
                decisions: [
                  {
                    fact: {
                      origin: "declared_assumption",
                      predicate: "membership_change_allowed",
                      value: true,
                    },
                  },
                ],
              },
            },
          ],
        },
      ],
      top_k: {
        programs: [
          {
            candidate_id: "generated_0001",
            effort: 1,
            work_unit_ledger: {
              one: { technique: "genericall_add_member", computed_cost: 1 },
            },
          },
        ],
      },
      engine_reported_guarantees: { is_minimum_proven_over_scope: false },
      truncated: true,
    },
  };
}
test("published paths retain order, distinct zero-cost unit and C", () => {
  const p = M.normalize(demo.paths);
  assert.deepEqual(
    p.programs.map((p) => p.C),
    [4, 5, 5],
  );
  assert.equal(p.programs[0].steps.length, 9);
  assert.equal(p.minimum, false);
  for (const x of p.programs)
    assert.equal(
      x.ledger.reduce((n, u) => n + u.computed_cost, 0),
      x.C,
    );
  assert(p.programs[0].ledger.some((u) => u.computed_cost === 0));
});
test("demo pins the published brief and preserves the original remediation summary", () => {
  const brief = fs.readFileSync(
    path.join(__dirname, "../../reports/neo/ranking-C-example.md"),
  );
  assert.equal(
    createHash("sha256").update(brief).digest("hex"),
    demo.paths.source_sha256,
  );
  const summary = JSON.parse(
    fs.readFileSync(
      path.join(
        __dirname,
        "../../reports/neo/remediation-rediscovery-results.json",
      ),
      "utf8",
    ),
  );
  assert.deepEqual(demo.remediation, summary);
});
test("native CLI envelope retains actor/source and declared assumptions", () => {
  const p = M.normalize(native());
  assert.equal(p.programs[0].C, 1);
  assert.equal(p.programs[0].steps[0].actor, "user");
  assert.equal(p.programs[0].steps[0].source, "via-group");
  assert.equal(p.programs[0].steps[0].assumptions.length, 1);
  assert.equal(p.minimum, false);
});
test("unrated is null, not zero; unranked candidates are not sorted or priced", () => {
  const n = native();
  delete n.semantic.top_k;
  const p = M.normalize(n);
  assert.equal(p.programs[0].C, null);
  assert.deepEqual(p.programs[0].ledger, []);
  assert.equal(M.cost(0), 0);
  assert.equal(M.cost(null), null);
  assert.equal(M.cost("0"), null);
});
test("empty complete no-path and zero-action success remain distinct", () => {
  const n = native();
  n.semantic.candidates = [];
  delete n.semantic.top_k;
  n.semantic.engine_reported_guarantees.is_no_path_proven_over_scope = true;
  assert.equal(M.normalize(n).noPath, true);
  assert.equal(M.normalize(n).programs.length, 0);
  const z = native();
  z.semantic.candidates[0].transition_history = [];
  z.semantic.top_k.programs[0].effort = 0;
  assert.equal(M.normalize(z).programs[0].C, 0);
  assert.equal(M.normalize(z).programs[0].steps.length, 0);
});
test("cap/blocked without proof never becomes no-path or zero cost", () => {
  assert.equal(
    M.outcome({ reached: false, truncation_reason: "expansion_limit_reached" })
      .tone,
    "amber",
  );
  assert.equal(
    M.outcome({ status: "blocked", reached: false, no_path_proven: false })
      .label,
    "Chưa kết luận",
  );
  assert.equal(
    M.outcome({ reached: false, no_path_proven: true }).tone,
    "green",
  );
});
test("WRAITH summary retains DA/EA and both strategies without inferred bypass graphs", () => {
  const v = M.normalize(demo.remediation);
  assert.equal(v.cases.length, 3);
  assert.equal(v.cases[1].queries[0].after.C, null);
  assert.equal(v.cases[1].queries[0].after.no_path_proven, true);
  assert.equal(
    v.cases[2].queries.find(
      (q) => q.strategy === "neo_refine" && q.goal === "DA",
    ).after.truncation_reason,
    "expansion_limit_reached",
  );
  assert(!v.cases[2].queries[0].after.steps);
});
test("bad input and dangling Top-K fail explicitly", () => {
  for (const bad of [null, [], {}, { nodes: [], edges: [] }])
    assert.throws(() => M.normalize(bad));
  const n = native();
  n.semantic.top_k.programs[0].candidate_id = "missing";
  assert.throws(() => M.normalize(n), /Top-K/);
});
test("oversized programs and malformed requests are rejected", () => {
  const n = native();
  n.semantic.candidates[0].transition_history = Array(121).fill(
    n.semantic.candidates[0].transition_history[0],
  );
  assert.throws(() => M.normalize(n), /120/);
  const b = copy(demo.paths);
  b.programs[0].C = -1;
  assert.throws(() => M.normalize(b), /C phải/);
  const c = native();
  delete c.semantic.candidates[0].transition_history[0].result.request.actor;
  assert.throws(() => M.normalize(c), /actor/);
});
