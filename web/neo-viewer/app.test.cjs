// DOM regression checks. These do not assert browser layout or pointer rendering.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");
const copy = (x) => JSON.parse(JSON.stringify(x));

function openViewer(t) {
  const read = (name) => fs.readFileSync(path.join(__dirname, name), "utf8");
  const dom = new JSDOM(read("index.html"), { runScripts: "outside-only" });
  t.after(() => dom.window.close());
  const w = dom.window,
    d = w.document;
  for (const name of ["model.js", "demo.js", "app.js"]) w.eval(read(name));
  const get = (id) => d.getElementById(id);
  return {
    w,
    d,
    get,
    text: (id) => get(id).textContent,
    click: (id) => get(id).click(),
    async load(input) {
      const file = get("file");
      Object.defineProperty(file, "files", {
        configurable: true,
        value: [{ size: 100, text: async () => JSON.stringify(input) }],
      });
      await file.onchange({ target: file });
    },
  };
}

function native() {
  return {
    semantic: {
      materialized: { initial_actor: "source", target: "goal" },
      candidates: [
        {
          candidate_id: "one",
          transition_history: [
            {
              result: {
                request: {
                  actor: "source",
                  source: "via",
                  target: "goal",
                  technique_id: "fixture_action",
                },
                decisions: [
                  {
                    fact: {
                      origin: "declared_assumption",
                      predicate: "fixture_condition",
                      subject: "source",
                      target: "goal",
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
            candidate_id: "one",
            effort: 1,
            work_unit_ledger: {
              unit: { technique: "fixture_action", computed_cost: 1 },
            },
          },
        ],
      },
      engine_reported_guarantees: {
        is_minimum_proven_over_scope: false,
        is_no_path_proven_over_scope: false,
      },
    },
  };
}

test("native overview includes distinct assumptions while steps retain every original fact", async (t) => {
  const ui = openViewer(t),
    n = native();
  const history = n.semantic.candidates[0].transition_history;
  history.push(copy(history[0]), copy(history[0]));
  history[2].result.decisions[0].fact.target = "another-goal";
  const original = copy(n);
  await ui.load(n);
  assert(ui.get("error").hidden);
  assert.equal(
    ui.d.querySelector("#details summary").textContent,
    "Giả định chương trình (2)",
  );
  assert.match(ui.text("details"), /fixture_condition/);
  const normalized = ui.w.NeoViewModel.normalize(n);
  assert.equal(normalized.programs[0].steps[1].assumptions.length, 1);
  assert.equal(normalized.programs[0].assumptions.length, 2);
  assert.deepEqual(n, original);
  ui.d
    .querySelector(".edge-group")
    .dispatchEvent(
      new ui.w.KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
  assert.match(ui.text("details"), /fixture_condition/);
  assert.match(ui.text("details"), /via/);
});

test("missing decision details are incomplete, not an assertion of zero assumptions", async (t) => {
  const ui = openViewer(t),
    n = native();
  delete n.semantic.candidates[0].transition_history[0].result.decisions;
  await ui.load(n);
  assert.match(
    ui.d.querySelector("#details summary").textContent,
    /chưa đầy đủ/,
  );
  assert.doesNotMatch(ui.text("details"), /Giả định chương trình \(0\)/);
  n.semantic.candidates[0].transition_history[0].result.decisions = [];
  await ui.load(n);
  assert.equal(
    ui.d.querySelector("#details summary").textContent,
    "Giả định chương trình (0)",
  );
  n.semantic.candidates[0].transition_history.push(
    copy(native().semantic.candidates[0].transition_history[0]),
  );
  delete n.semantic.candidates[0].transition_history[0].result.decisions;
  await ui.load(n);
  assert.match(
    ui.d.querySelector("#details summary").textContent,
    /chưa đầy đủ \(đã ghi 1\)/,
  );
});

test("imported survey without metadata does not inherit demo domain or machine capability", async (t) => {
  const ui = openViewer(t),
    survey = copy(ui.w.NEO_DEMOS.survey);
  delete survey.scope;
  survey.cells = survey.cells.filter((c) => c.source_kind === "Computer");
  survey.cells.forEach((c) => {
    c.source = "TEST-MACHINE@OTHERLAB";
  });
  await ui.load(survey);
  assert.match(ui.text("dataset"), /Báo cáo đã nhập/);
  assert.doesNotMatch(ui.text("eyebrow"), /SEAMLESS|ĐÃ CÔNG BỐ/);
  assert.match(ui.text("details"), /Chưa có thông tin trong báo cáo/);
  assert.doesNotMatch(ui.text("details"), /Danh tính mạng máy dùng được/);
  assert.match(ui.text("input-origin"), /nguồn chưa xác minh/);
  ui.click("paths-mode");
  assert.match(ui.text("input-origin"), /Demo/);
  ui.click("survey-mode");
  assert.match(ui.text("input-origin"), /nguồn chưa xác minh/);
  ui.click("reset-demo");
  assert.match(ui.text("dataset"), /SEAMLESS/);
  assert.match(ui.text("input-origin"), /Demo/);
});

test("survey capability comes from the matching source profile, never its node kind alone", async (t) => {
  const ui = openViewer(t),
    survey = copy(ui.w.NEO_DEMOS.survey);
  survey.title = "OTHERLAB · Khảo sát";
  survey.cells = survey.cells.filter((c) => c.source_kind === "Computer");
  await ui.load(survey);
  assert.match(ui.text("dataset"), /OTHERLAB/);
  assert.match(ui.text("details"), /Danh tính mạng máy dùng được/);
  const source = survey.scope.request.sources.find(
    (s) => s.source_id === survey.cells[0].source_id,
  );
  source.node_id = "not-the-reported-source";
  await ui.load(survey);
  assert.match(ui.text("details"), /Chưa có thông tin trong báo cáo/);
});

test("imported remediation keeps its own goal and scenario without demo claims", async (t) => {
  const ui = openViewer(t),
    r = copy(ui.w.NEO_DEMOS.remediation);
  delete r.scenario;
  r.cases = [r.cases[1]];
  r.cases[0].case = "rodc-membership"; // Same ID does not establish WRAITH provenance.
  r.cases[0].queries.forEach((q) => {
    q.goal = "TEST GOAL";
  });
  await ui.load(r);
  assert.match(ui.text("dataset"), /Báo cáo đã nhập/);
  assert.match(ui.text("source-card"), /TEST GOAL/);
  assert.doesNotMatch(
    ui.text("source-card"),
    /credential cũ|Enterprise Admins/,
  );
  assert.doesNotMatch(ui.text("choices"), /RODCMANAGER/);
  assert.doesNotMatch(ui.text("details"), /local-admin-only/);
  assert.match(ui.text("details"), /Chưa có thông tin/);
  assert.match(ui.text("status"), /Chặn trong phạm vi xét/);
  r.title = "OTHERLAB";
  r.scenario = "fixture-scenario";
  await ui.load(r);
  assert.equal(ui.text("dataset"), "OTHERLAB");
  assert.match(ui.text("details"), /fixture-scenario/);
});

test("caps and missing conditions stay inconclusive; proof and zero-action success remain distinct", async (t) => {
  const ui = openViewer(t),
    n = native();
  n.semantic.candidates = [];
  delete n.semantic.top_k;
  n.semantic.truncated = true;
  n.semantic.truncation_reason = "expansion_limit_reached";
  n.semantic.attempts = [{ unknown: ["fixture_missing_fact"] }];
  await ui.load(n);
  assert.equal(ui.text("status"), "Chưa kết luận");
  assert.match(ui.text("empty"), /hết ngân sách/);
  assert.match(ui.text("scope-note"), /fixture_missing_fact/);
  n.semantic.truncated = false;
  delete n.semantic.truncation_reason;
  n.semantic.attempts = [];
  n.semantic.status = "blocked";
  await ui.load(n);
  assert.match(ui.text("empty"), /thiếu điều kiện/);
  delete n.semantic.status;
  await ui.load(n);
  assert.match(ui.text("empty"), /chưa cung cấp lý do/);
  n.semantic.engine_reported_guarantees.is_no_path_proven_over_scope = true;
  await ui.load(n);
  assert.match(ui.text("status"), /Không có đường trong phạm vi xét/);
  const z = native();
  z.semantic.candidates[0].transition_history = [];
  z.semantic.top_k.programs[0].effort = 0;
  z.semantic.top_k.programs[0].work_unit_ledger = {};
  await ui.load(z);
  assert.match(ui.text("status"), /Đường đã tìm được/);
  assert.match(ui.text("empty"), /trạng thái đầu/);
  assert.equal(ui.d.querySelector(".cost-hero strong").textContent, "0");
});

test("demo results and controls remain faithful across all three views", (t) => {
  const ui = openViewer(t);
  assert.equal(ui.d.querySelector(".cost-hero strong").textContent, "4");
  ui.d.querySelectorAll(".choice")[1].click();
  assert.equal(ui.d.querySelector(".cost-hero strong").textContent, "5");
  ui.click("zoom-in");
  assert.match(ui.get("viewport").getAttribute("transform"), /scale\(1.2\)/);
  ui.click("fit");
  assert.match(ui.get("viewport").getAttribute("transform"), /scale\(1\)/);
  ui.click("remediation-mode");
  assert.equal(ui.text("status"), "Còn đường vòng");
  ui.d.querySelectorAll(".choice")[1].click();
  assert.equal(ui.text("status"), "Chặn trong phạm vi xét");
  ui.click("before");
  assert.equal(ui.text("status"), "Có đường");
  ui.click("after");
  ui.d.querySelectorAll(".choice")[2].click();
  const strategy = ui.d.querySelector("select");
  strategy.value = "2";
  strategy.dispatchEvent(new ui.w.Event("change"));
  assert.equal(ui.text("status"), "Còn đường vòng");
  assert.match(ui.text("details"), /Đã hết ngân sách tìm kiếm/);
  ui.click("survey-mode");
  assert.match(ui.text("survey"), /15\/30/);
  assert.match(ui.text("survey"), /0\/10/);
  assert.equal(ui.d.querySelectorAll("tbody tr").length, 10);
  const source = ui.d.querySelector("select");
  source.value = source.options[1].value;
  source.dispatchEvent(new ui.w.Event("change"));
  assert.equal(ui.d.querySelectorAll("tbody tr").length, 2);
  ui.d.querySelectorAll(".row-button")[1].click();
  assert.match(ui.text("details"), /CỦA CÁC CHƯƠNG TRÌNH/);
});

test("file errors preserve the previous report; unrated and label text remain literal", async (t) => {
  const ui = openViewer(t),
    title = ui.text("heading");
  await ui.load({ nodes: [] });
  assert(!ui.get("error").hidden);
  assert.equal(ui.text("heading"), title);
  const p = copy(ui.w.NEO_DEMOS.paths);
  p.labels[p.source].label = "<em>plain label</em>";
  await ui.load(p);
  assert(ui.get("error").hidden);
  assert.match(ui.text("source-card"), /<em>plain label<\/em>/);
  assert.equal(ui.get("source-card").querySelector("em"), null);
  const n = native();
  n.semantic.top_k.programs[0].effort = null;
  await ui.load(n);
  assert.match(ui.text("result-strip"), /Chưa chấm/);
  assert.equal(ui.d.querySelector(".cost-hero strong").textContent, "-");
});

test("runner results.json opens directly and uses the reported source and target", async (t) => {
  const ui = openViewer(t);
  await ui.load({
    version: "neo-remediation-rediscovery/1",
    interventions: [
      {
        case: "fixture",
        removed_edges: [
          { source: "edge-source", target: "edge-target", kind: "MemberOf" },
        ],
      },
    ],
    rows: [
      {
        case: "fixture",
        strategy: "s",
        source: "initial-source",
        target: "actual-goal",
        phase: "before",
        reached: true,
        C: 3,
      },
      {
        case: "fixture",
        strategy: "s",
        source: "initial-source",
        target: "actual-goal",
        phase: "after",
        reached: false,
        no_path_proven: false,
        C: null,
        truncation_reason: "expansion_limit_reached",
      },
    ],
  });
  assert(ui.get("error").hidden);
  assert.match(ui.text("source-card"), /initial-source/);
  assert.match(ui.text("source-card"), /actual-goal/);
  assert.equal(ui.text("status"), "Chưa kết luận");
  assert.match(ui.text("scope-note"), /hết ngân sách/);
  ui.click("before");
  assert.equal(ui.text("status"), "Có đường");
});

test("invalid JSON syntax has an understandable message and preserves the selected report", async (t) => {
  const ui = openViewer(t);
  ui.d.querySelectorAll(".choice")[1].click();
  const heading = ui.text("heading"),
    choices = ui.text("choices"),
    details = ui.text("details");
  const file = ui.get("file");
  Object.defineProperty(file, "files", {
    configurable: true,
    value: [{ size: 7, text: async () => "{broken" }],
  });
  await file.onchange({ target: file });
  assert(!ui.get("error").hidden);
  assert.match(ui.text("error"), /^JSON không hợp lệ\./);
  assert.equal(ui.text("heading"), heading);
  assert.equal(ui.text("choices"), choices);
  assert.equal(ui.text("details"), details);
});

test("baseline-sized query files load while oversized files are rejected before reading", async (t) => {
  const ui = openViewer(t),
    file = ui.get("file");
  Object.defineProperty(file, "files", {
    configurable: true,
    value: [{ size: 95 * 1024 * 1024, text: async () => JSON.stringify(native()) }],
  });
  await file.onchange({ target: file });
  assert(ui.get("error").hidden);
  assert.match(ui.text("dataset"), /Kết quả đã nhập/);
  const details = ui.text("details");
  Object.defineProperty(file, "files", {
    configurable: true,
    value: [{
      size: 129 * 1024 * 1024,
      text: async () => { throw Error("must not read"); },
    }],
  });
  await file.onchange({ target: file });
  assert.match(ui.text("error"), /File vượt 128 MB/);
  assert.equal(ui.text("details"), details);
});

test("bundled demos read in Vietnamese without developer provenance or raw SIDs", (t) => {
  const ui = openViewer(t);
  const visible = () => ui.d.body.textContent;
  for (const english of ["Use identity", "Add member", "Grant rights", "Reset password", "LEDGER", "FOOTHOLD"])
    assert(!visible().includes(english), english);
  assert(!visible().includes("—"));
  assert(!ui.text("details").includes("ranking-C-example.md"));
  assert(!ui.text("details").includes("Playback"));
  assert.match(ui.text("details"), /Thêm thành viên nhóm/);
  ui.click("remediation-mode");
  assert(!ui.text("details").includes("neo_guided"));
  assert.match(ui.text("details"), /Tìm có hướng dẫn/);
  ui.click("survey-mode");
  assert.match(ui.text("details"), /KATRINA_GREEN/);
  assert.match(ui.text("details"), /ADMINISTRATORS/);
  assert(!ui.text("details").includes("S-1-5-21"));
});

test("graph view fits the laid-out nodes instead of a fixed wide canvas", (t) => {
  const ui = openViewer(t);
  const [, , w, h] = ui.get("graph").getAttribute("viewBox").split(" ").map(Number);
  assert(w >= 640 && h >= 360);
  assert.notEqual(ui.get("graph").getAttribute("viewBox"), "0 0 1200 660");
});

test("theme toggle switches the page and survives blocked storage", (t) => {
  const ui = openViewer(t);
  const root = ui.d.documentElement;
  const first = root.dataset.theme;
  ui.click("theme");
  const next = root.dataset.theme;
  assert(next === "light" || next === "dark");
  assert.notEqual(next, first);
  assert.equal(ui.text("theme"), next === "dark" ? "Nền sáng" : "Nền tối");
  ui.click("theme");
  assert.notEqual(root.dataset.theme, next);
});
