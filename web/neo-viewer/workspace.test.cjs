// DOM checks for the local analysis screen against a scripted server. Layout is checked in a browser.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

const USER = { id: "u", label: "ALICE@A.LOCAL", kind: "User", domain: "A.LOCAL", boundary: false };
const GROUP = { id: "da", label: "DOMAIN ADMINS@A.LOCAL", kind: "Group", domain: "A.LOCAL", boundary: false };
const EDGE = { id: "e1", source: "u", kind: "GenericAll", target: "da" };
const STEP = {
  actor: "u",
  source: "u",
  target: "da",
  technique_id: "genericall_add_member",
  edge: EDGE,
  assumptions: [{ predicate: "membership_change_allowed", subject: "u", target: "da", value: true }],
};
const LABELS = { u: USER, da: GROUP };
const answer = (outcome, programs = []) => ({
  version: "neo-viewer-playback/1",
  source: "u",
  target: "da",
  labels: LABELS,
  programs,
  outcome,
  reached: programs.length > 0,
  minimum: false,
  noPath: outcome === "blocked_in_scope",
  no_path_proven: outcome === "blocked_in_scope",
  truncated: false,
  reason: null,
  expansions: 7,
  max_expansions: 4096,
  status: "success",
  unknown: {},
});
const program = {
  id: "generated_0001",
  C: 2,
  steps: [STEP],
  ledger: [{ technique: "genericall_add_member", effort_cost: 2 }],
  assumptions: STEP.assumptions,
};
const OPENED = {
  report: {
    name: "A",
    export: "2024",
    domains: ["A.LOCAL"],
    nodes: { User: 1, Group: 1 },
    edges: { GenericAll: 1 },
    unused_record_kinds: { containers: 3 },
    boundary_objects: 0,
    omitted_empty_records: 0,
    untyped_references: { Base: 2 },
    dropped_identifiers: {},
    outside_references: { "S-1-5-21-9-9-9-519": 4 },
    skipped_records: ["build record X: reason"],
    session_edges: 0,
    failed_session_collections: 1,
  },
  targets: [GROUP],
};

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
async function settle() {
  for (let i = 0; i < 8; i++) await tick();
}
function json(status, body) {
  return { ok: status < 400, status, json: async () => body };
}

async function openApp(t, routes = {}) {
  const read = (name) => fs.readFileSync(path.join(__dirname, name), "utf8");
  const dom = new JSDOM(read("index.html"), { runScripts: "outside-only", pretendToBeVisual: true });
  t.after(() => dom.window.close());
  const w = dom.window,
    d = w.document;
  const calls = [];
  const defaults = {
    "/api/status": () => json(200, { sources: [{ id: 0, name: "a", export: "2024", domains: ["A.LOCAL"] }], opened: null }),
    "/api/open": () => json(200, OPENED),
    "/api/search": () => json(200, { results: [USER] }),
    "/api/neighbors": () =>
      json(200, { node: USER, nodes: [USER, GROUP], edges: [EDGE], total_edges: 1, counts: { GenericAll: 1 } }),
    "/api/paths": () => json(200, answer("reachable", [program])),
    "/api/remove": () =>
      json(200, {
        edit: { source: "u", kind: "GenericAll", target: "da", removed_observations: { Aces: 1 }, evidence: [], status: "removed" },
        before: answer("reachable", [program]),
        after: answer("blocked_in_scope"),
      }),
    ...routes,
  };
  w.fetch = async (url, options = {}) => {
    const route = String(url).split("?")[0];
    calls.push({ route, url: String(url), options });
    return defaults[route](url, options);
  };
  for (const name of ["model.js", "demo.js", "app.js", "workspace.js"]) w.eval(read(name));
  await settle();
  const get = (id) => d.getElementById(id);
  const button = (text) => [...d.querySelectorAll("button")].find((b) => b.textContent.includes(text));
  const press = async (text) => {
    const target = button(text);
    assert.ok(target, "missing button: " + text);
    target.click();
    await settle();
  };
  const searchFor = async (text) => {
    const input = d.querySelector(".ws-search");
    input.value = text;
    input.dispatchEvent(new w.Event("input"));
    await new Promise((resolve) => setTimeout(resolve, 200));
    await settle();
  };
  return { w, d, get, calls, button, press, searchFor, text: (id) => get(id).textContent };
}

async function openedWithSource(t, routes) {
  const app = await openApp(t, routes);
  await app.press("A.LOCAL");
  await app.searchFor("alice");
  app.d.querySelector(".ws-result").click();
  await settle();
  await app.press("Xuất phát từ đây");
  return app;
}

test("starts on the data screen, reads the list from the server and offers no fake switch", async (t) => {
  const app = await openApp(t);
  assert.equal(app.text("heading"), "Chọn dữ liệu");
  assert.ok(app.get("workspace-mode").classList.contains("active"));
  assert.ok(app.button("A.LOCAL"));
  assert.equal(app.button("Đổi dữ liệu"), undefined);
  assert.equal(app.get("reset-demo").hidden, true);
});

test("opening data lists everything that was set aside", async (t) => {
  const app = await openApp(t);
  await app.press("A.LOCAL");
  assert.equal(app.text("heading"), "Tìm một đối tượng");
  const details = app.text("details");
  assert.match(details, /containers 3/);
  assert.match(details, /Không có dữ liệu phiên đăng nhập/);
  assert.match(details, /Bỏ tham chiếu ở 4 bản ghi tới 1 đối tượng/);
  assert.match(details, /2 tham chiếu không rõ loại/);
  assert.match(details, /Bỏ 1 bản ghi/);
});

test("search, choose a source, find a path and read its cost", async (t) => {
  const app = await openedWithSource(t);
  assert.equal(app.d.querySelector(".ws-chosen").textContent, "ALICE");
  await app.press("Tìm đường");
  const sent = JSON.parse(app.calls.find((c) => c.route === "/api/paths").options.body);
  assert.deepEqual(sent, { source: "u", target: "da", scenario: "identity" });
  assert.equal(app.text("status"), "Có đường");
  assert.match(app.text("result-strip"), /C tốt nhất đã tìm2/);
  assert.match(app.text("details"), /Tổng C2/);
  assert.equal(app.d.querySelectorAll("#edges .on-path").length, 1);
  assert.equal(app.d.querySelector("#edges .step-num").textContent, "1");
});

test("a later path shows its own C, not the best one", async (t) => {
  const app = await openedWithSource(t, {
    "/api/paths": () => json(200, answer("reachable", [program, { ...program, C: 5 }])),
  });
  await app.press("Tìm đường");
  app.d.querySelectorAll("button.choice")[1].click();
  await settle();
  assert.match(app.text("result-strip"), /C của đường này5/);
});

test("a computer source starts from the host assumption", async (t) => {
  const host = { ...USER, id: "h", label: "PC01.A.LOCAL", kind: "Computer" };
  const app = await openApp(t, {
    "/api/search": () => json(200, { results: [host] }),
    "/api/neighbors": () =>
      json(200, { node: host, nodes: [host], edges: [], total_edges: 0, counts: {} }),
  });
  await app.press("A.LOCAL");
  await app.searchFor("pc01");
  app.d.querySelector(".ws-result").click();
  await settle();
  await app.press("Xuất phát từ đây");
  assert.equal(app.d.querySelector(".ws-chosen").textContent, "PC01");
  assert.equal(app.d.querySelector(".ws-form select").value, "host-compromise");
});

test("trying a removal shows the verdict and the removed edge, never a real change", async (t) => {
  const app = await openedWithSource(t);
  await app.press("Tìm đường");
  app.d.querySelector(".step-button").click();
  await settle();
  await app.press("Gỡ thử quan hệ này");
  const sent = JSON.parse(app.calls.find((c) => c.route === "/api/remove").options.body);
  assert.equal(sent.edge_kind, "GenericAll");
  assert.equal(app.text("status"), "Đã chặn");
  assert.match(app.text("empty"), /ALICE không còn đường tới DOMAIN ADMINS/);
  assert.equal(app.d.querySelectorAll("#edges .removed").length, 1);
  assert.equal(app.text("scope-note"), "");

  app.get("before").click();
  await settle();
  assert.equal(app.text("status"), "Có đường");
  assert.equal(app.d.querySelectorAll("#edges .cut-target").length, 1);
  assert.match(app.text("details"), /Đã chặn/);

  await app.press("Quay lại đường ban đầu");
  assert.equal(app.get("phase-controls").hidden, true);
});

test("a derived relationship explains itself instead of pretending to be removed", async (t) => {
  const app = await openedWithSource(t, {
    "/api/remove": () =>
      json(200, {
        edit: { source: "u", kind: "AdminTo", target: "da", removed_observations: {}, evidence: [], status: "derived_only" },
        before: answer("reachable", [program]),
        after: null,
      }),
  });
  await app.press("Tìm đường");
  app.d.querySelector(".step-button").click();
  await settle();
  await app.press("Gỡ thử quan hệ này");
  assert.equal(app.text("status"), "Không gỡ trực tiếp được");
  assert.match(app.text("details"), /nhờ thuộc một nhóm/);
  assert.equal(app.get("phase-controls").hidden, true);
});

test("a step the chain itself created cannot be removed", async (t) => {
  const derived = { ...program, steps: [{ ...STEP, edge: null }] };
  const app = await openedWithSource(t, {
    "/api/paths": () => json(200, answer("reachable", [derived])),
  });
  await app.press("Tìm đường");
  app.d.querySelector(".step-button").click();
  await settle();
  assert.equal(app.button("Gỡ thử quan hệ này"), undefined);
  assert.match(app.text("details"), /Chuỗi hành động tự tạo ra/);
});

test("no path says so plainly and offers the wider assumption", async (t) => {
  const app = await openedWithSource(t, {
    "/api/paths": () => json(200, answer("blocked_in_scope")),
  });
  await app.press("Tìm đường");
  assert.match(app.text("heading"), /ALICE → DOMAIN ADMINS/);
  assert.match(app.text("empty"), /ALICE không có đường tới DOMAIN ADMINS/);
  assert.equal(app.text("status"), "Không có đường");
  await app.press("Tìm lại với máy và phiên");
  const sent = app.calls.filter((c) => c.route === "/api/paths").at(-1);
  assert.equal(JSON.parse(sent.options.body).scenario, "host-compromise");
});

test("server errors surface and keep the screen usable", async (t) => {
  const app = await openedWithSource(t, {
    "/api/paths": () => json(400, { error: "Đối tượng này không dùng được làm điểm xuất phát." }),
  });
  await app.press("Tìm đường");
  assert.match(app.text("error"), /không dùng được/);
  assert.equal(app.get("error").hidden, false);
  assert.equal(app.button("Tìm đường").disabled, false);
});

test("a disabled account says why it cannot be a source", async (t) => {
  const disabled = { ...USER, enabled: false };
  const app = await openApp(t, {
    "/api/search": () => json(200, { results: [disabled] }),
    "/api/neighbors": () =>
      json(200, { node: disabled, nodes: [disabled], edges: [], total_edges: 0, counts: {} }),
  });
  await app.press("A.LOCAL");
  await app.searchFor("alice");
  app.d.querySelector(".ws-result").click();
  await settle();
  assert.equal(app.button("Xuất phát từ đây"), undefined);
  assert.match(app.text("details"), /vô hiệu hóa/);
});

test("a zip holding several exports asks which one", async (t) => {
  const exports = [{ export: "one", domains: ["ONE.LOCAL"] }, { export: "two", domains: ["TWO.LOCAL"] }];
  let uploads = 0;
  const app = await openApp(t, {
    "/api/upload": (_, options) => {
      uploads += 1;
      return options.headers["X-Neo-Export"]
        ? json(200, OPENED)
        : json(409, { error: "Nguồn dữ liệu có nhiều bản xuất; hãy chọn một bản.", exports });
    },
  });
  const input = app.d.getElementById("dataset-file");
  Object.defineProperty(input, "files", { value: [{ name: "many.zip" }] });
  input.onchange();
  await settle();
  assert.ok(app.button("TWO.LOCAL"));
  assert.equal(app.get("error").hidden, true);
  await app.press("TWO.LOCAL");
  assert.equal(uploads, 2);
  assert.equal(app.text("heading"), "Tìm một đối tượng");
});

test("choke points list what was tested and say when one cut stops nobody", async (t) => {
  const item = {
    edge: EDGE,
    source_label: "ALICE@A.LOCAL",
    target_label: "DOMAIN ADMINS@A.LOCAL",
    in_best_paths: 6,
    in_any_path: 9,
    blocked: 0,
    bypass: 9,
    inconclusive: 0,
    other_support_remains: false,
    C_before_mean: 2,
    C_after_mean: 2.3333,
  };
  const app = await openApp(t, {
    "/api/progress": () => json(200, {}),
    "/api/chokepoints": () =>
      json(200, {
        target: "da",
        scenario: "identity",
        eligible_sources: 36,
        sources_tried: 36,
        sources_reached: 9,
        budget: 1024,
        candidates: [item],
        derived_skipped: 0,
      }),
  });
  await app.press("A.LOCAL");
  await app.press("Tìm điểm nghẽn");
  assert.equal(app.text("heading"), "Điểm nghẽn tới DOMAIN ADMINS");
  assert.match(app.text("survey"), /9\/36 nguồn tới được/);
  assert.match(app.text("survey"), /ALICE có toàn quyền trên DOMAIN ADMINS/);
  assert.match(app.text("survey"), /2 → 2,3/);
  assert.match(app.text("details"), /cần gỡ nhiều quan hệ cùng lúc/);
});

test("the read-only screens still work beside the analysis screen", async (t) => {
  const app = await openApp(t);
  app.get("survey-mode").click();
  await settle();
  assert.equal(app.get("workspace-mode").classList.contains("active"), false);
  assert.equal(app.get("result-strip").hidden, false);
  assert.equal(app.text("dataset-label"), "Kết quả");
  app.get("workspace-mode").click();
  await settle();
  assert.equal(app.text("dataset-label"), "Dữ liệu đang mở");
  assert.equal(app.text("heading"), "Chọn dữ liệu");
});
