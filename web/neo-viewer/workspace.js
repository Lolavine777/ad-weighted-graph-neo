/* The local app's analysis screen: open data, search, find paths, try a removal, find choke points.
   Served only by scripts/neo_app.py. All questions go to that server on this machine. */
(() => {
  "use strict";
  const V = NeoViewer,
    M = NeoViewModel;
  const { el, button, fact, note, action } = V;
  const $ = (id) => document.getElementById(id);
  const MAX_UPLOAD_BYTES = 2 * 1024 ** 3;
  const ORIGIN = 2000; // Canvas coordinates stay positive so dragging a node never clamps it.
  const relationText = {
    MemberOf: "là thành viên của",
    GenericAll: "có toàn quyền trên",
    WriteDacl: "được sửa danh sách quyền của",
    ForceChangePassword: "được đặt lại mật khẩu của",
    HasSession: "đang giữ phiên đăng nhập của",
    AdminTo: "có quyền quản trị trên",
    CanPSRemote: "được quản trị từ xa qua PowerShell trên",
  };
  const scenarios = {
    identity: {
      label: "Chỉ quyền trong thư mục",
      detail: "Nguồn đã bị chiếm danh tính và chỉ đi qua quyền trong Active Directory.",
    },
    "host-compromise": {
      label: "Thêm máy và phiên",
      detail: "Được dùng thêm quyền quản trị máy, điều khiển từ xa và phiên đăng nhập trên máy.",
    },
  };
  const outcomes = {
    reachable: { label: "Có đường", tone: "route" },
    bypass: { label: "Còn đường vòng", tone: "route" },
    blocked_in_scope: { label: "Đã chặn", tone: "clear" },
    inconclusive: { label: "Chưa kết luận", tone: "pending" },
  };
  const S = {
    sources: [],
    opened: null,
    pendingExports: null,
    pendingFile: null,
    screen: "data",
    results: [],
    nodes: new Map(),
    edges: new Map(),
    info: new Map(),
    source: null,
    target: null,
    scenario: "identity",
    answer: null,
    removal: null,
    chokepoints: null,
    program: 0,
    busy: "",
  };
  const canvasView = { kind: "workspace", title: "neo", labels: {} };

  async function api(path, body) {
    const options =
      body === undefined
        ? {}
        : {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Neo-Request": "1" },
            body: JSON.stringify(body),
          };
    return reply(await fetch(path, options));
  }
  async function reply(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = Error(data.error || "Ứng dụng không trả lời. Hãy kiểm tra cửa sổ đang chạy neo.");
      error.exports = data.exports;
      throw error;
    }
    return data;
  }
  async function job(message, work) {
    if (S.busy) return;
    S.busy = message;
    update();
    try {
      await work();
      $("error").hidden = true;
    } catch (error) {
      V.showError(error);
    } finally {
      S.busy = "";
      update();
    }
  }
  const update = () => V.show(canvasView);
  const shortName = (node) =>
    node.kind === "Computer"
      ? node.label.split(".")[0]
      : node.label.split("@")[0];
  const count = (values) => Object.values(values).reduce((a, b) => a + b, 0);
  function labelOf(id) {
    const known =
      activeAnswer()?.labels?.[id] ||
      S.answer?.labels?.[id] ||
      S.nodes.get(id) ||
      S.opened?.targets.find((t) => t.id === id);
    return known ? shortName(known) : id;
  }
  const activeAnswer = () =>
    S.removal
      ? (V.phase() === "before" ? S.removal.before : S.removal.after) ||
        S.removal.before
      : S.answer;
  const showingPaths = () => S.screen === "paths" && Boolean(activeAnswer());
  const currentProgram = () => {
    const programs = activeAnswer()?.programs || [];
    return programs[Math.min(S.program, programs.length - 1)];
  };
  function sameEdge(a, b) {
    return a.source === b.source && a.kind === b.kind && a.target === b.target;
  }

  // Explored nodes fan out around the one that was opened: control flowing in on the left.
  function placeNeighbors(center, neighbors, edges) {
    const taken = () => [...S.nodes.values()].filter((n) => n.x !== undefined);
    const free = (x, y) =>
      taken().every((n) => Math.abs(n.x - x) > 200 || Math.abs(n.y - y) > 90);
    const place = (node, side) => {
      for (let column = 1; ; column++)
        for (let row = 0; row < 5; row++) {
          const y = center.y + (row % 2 ? -1 : 1) * Math.ceil(row / 2) * 112,
            x = center.x + side * (column * 340 + (row % 2) * 40);
          if (free(x, y)) {
            S.nodes.set(node.id, { ...node, x, y });
            return;
          }
        }
    };
    for (const node of neighbors) {
      if (S.nodes.get(node.id)?.x !== undefined) continue;
      const incoming = edges.some(
        (e) => e.source === node.id && e.target === center.id,
      );
      place(node, incoming ? -1 : 1);
    }
  }
  async function openNode(id, { fresh = false } = {}) {
    const data = await api("/api/neighbors?id=" + encodeURIComponent(id));
    if (fresh) {
      S.nodes.clear();
      S.edges.clear();
      V.resetCanvas();
    }
    const known = S.nodes.get(id);
    const center = known?.x !== undefined ? known : { ...data.node, x: ORIGIN, y: ORIGIN };
    S.nodes.set(id, center);
    placeNeighbors(center, data.nodes, data.edges);
    for (const edge of data.edges) S.edges.set(edge.id, edge);
    S.info.set(id, data);
    S.screen = "explore";
    V.select({ type: "node", id });
  }
  function chooseSource(node) {
    S.source = node;
    S.scenario = node.kind === "Computer" ? "host-compromise" : "identity";
    clearResults();
    update();
  }
  function clearResults() {
    S.answer = null;
    S.removal = null;
    S.chokepoints = null;
    S.program = 0;
    if (S.screen === "paths" || S.screen === "chokepoints") S.screen = "explore";
  }
  function pathLabels(steps, extra = []) {
    const labels = {};
    const middle = [
      ...new Set([...steps.flatMap((s) => [s.source, s.target]), ...extra]),
    ].filter((id) => id !== S.source?.id && id !== S.target);
    const ids = [S.source?.id, ...middle, S.target].filter(Boolean);
    // Three to a row, turning back on each new row, keeps labels legible and the line unbroken.
    const perRow = 3;
    ids.forEach((id, i) => {
      const known = activeAnswer()?.labels?.[id] || S.answer?.labels?.[id] || S.nodes.get(id);
      const node = known || { label: id, kind: "Object" };
      const row = Math.floor(i / perRow),
        column = row % 2 ? perRow - 1 - (i % perRow) : i % perRow;
      labels[id] = {
        label: shortName(node),
        kind: node.kind,
        x: 200 + column * 340,
        y: 220 + row * 240,
      };
    });
    return labels;
  }
  function graph() {
    if (showingPaths()) {
      const steps = currentProgram()?.steps || [];
      const removed = S.removal?.edit;
      const cut = removed
        ? { source: removed.source, kind: removed.kind, target: removed.target }
        : null;
      const edges = steps.map((s, i) => ({
        ...s,
        id: i,
        step: i + 1,
        label: action(s.technique_id),
        cls:
          V.phase() === "before" && cut && s.edge && sameEdge(s.edge, cut)
            ? "cut-target"
            : "on-path",
      }));
      if (S.removal?.after && V.phase() === "after")
        edges.push({
          ...cut,
          id: "removed",
          technique_id: cut.kind,
          label: "Đã gỡ " + cut.kind,
          removed: true,
        });
      return { edges, nodes: [S.source?.id, S.target].filter(Boolean) };
    }
    if (S.screen === "explore")
      return {
        edges: [...S.edges.values()].map((e) => ({
          ...e,
          technique_id: e.kind,
          label: e.kind,
          labelAt: fanLabelPosition(e),
        })),
        nodes: [...S.nodes.keys()],
      };
    return { edges: [], nodes: [] };
  }
  // In a fan the arrows meet at the middle, so a label belongs near the node at the outer end.
  function fanLabelPosition(edge) {
    const degree = (id) =>
      [...S.edges.values()].filter((e) => e.source === id || e.target === id).length;
    return degree(edge.source) > degree(edge.target) ? 0.68 : 0.32;
  }
  function refreshLabels() {
    canvasView.source = S.source?.id;
    canvasView.target = S.target;
    if (showingPaths()) {
      const removed = S.removal?.edit;
      canvasView.labels = pathLabels(
        currentProgram()?.steps || [],
        removed ? [removed.source, removed.target] : [],
      );
    } else {
      canvasView.labels = {};
      for (const node of S.nodes.values())
        canvasView.labels[node.id] = {
          label: shortName(node),
          kind: node.kind,
          x: node.x,
          y: node.y,
        };
    }
  }

  function renderData() {
    const host = $("survey");
    host.replaceChildren();
    if (S.busy) {
      host.append(el("p", "ws-busy", S.busy));
      return;
    }
    if (S.pendingExports) {
      host.append(el("h3", "", "Tệp nén có nhiều bản xuất. Mở bản nào?"));
      for (const item of S.pendingExports)
        host.append(
          dataRow(item.domains.join(", ") || item.export, item.export, () =>
            upload(S.pendingFile, item.export),
          ),
        );
      return;
    }
    const intro = el("div", "survey-intro");
    intro.append(
      el(
        "p",
        "note",
        "Mở dữ liệu thu bằng SharpHound hoặc BloodHound.py. Dữ liệu chỉ được đọc trên máy này.",
      ),
    );
    host.append(intro);
    if (S.sources.length) {
      for (const source of S.sources)
        host.append(
          dataRow(
            source.domains.join(", ") || source.name,
            `Thư mục ${source.name}, bản xuất ${source.export}`,
            () => openSource(source),
          ),
        );
    } else
      host.append(
        el("p", "note", "Thư mục data/raw chưa có bản xuất nào. Hãy chọn một tệp .zip."),
      );
    const input = el("input");
    input.type = "file";
    input.accept = ".zip,application/zip";
    input.hidden = true;
    input.id = "dataset-file";
    input.onchange = () => input.files[0] && upload(input.files[0]);
    const pick = button("Chọn tệp .zip", () => input.click(), "ws-primary");
    pick.style.marginTop = "12px";
    host.append(input, pick);
  }
  function dataRow(title, subtitle, onOpen) {
    const row = button("", onOpen, "ws-data-row");
    const copy = el("span", "choice-copy");
    copy.append(el("strong", "", title), el("small", "", subtitle));
    row.append(copy, el("span", "ws-open", "Mở"));
    return row;
  }
  function opened(data) {
    S.opened = data;
    S.pendingExports = null;
    S.pendingFile = null;
    S.nodes.clear();
    S.edges.clear();
    S.info.clear();
    S.results = [];
    S.source = null;
    S.target = data.targets[0]?.id || null;
    clearResults();
    S.screen = "explore";
    searchInput.value = "";
    searchedFor = "";
    renderResults();
    V.resetCanvas();
  }
  function openSource(source) {
    return job("Đang đọc dữ liệu…", async () => {
      opened(await api("/api/open", { source: source.id, export: source.export }));
    });
  }
  function upload(file, chosen) {
    return job("Đang đọc tệp nén…", async () => {
      if (file.size > MAX_UPLOAD_BYTES)
        throw Error("Tệp lớn hơn 2 GB. Hãy đặt dữ liệu vào data/raw rồi mở từ danh sách.");
      const headers = {
        "Content-Type": "application/zip",
        "X-Neo-Request": "1",
        "X-File-Name": encodeURIComponent(file.name),
      };
      if (chosen) headers["X-Neo-Export"] = encodeURIComponent(chosen);
      try {
        opened(
          await reply(
            await fetch("/api/upload", { method: "POST", headers, body: file }),
          ),
        );
      } catch (error) {
        if (!error.exports) throw error;
        S.pendingExports = error.exports;
        S.pendingFile = file;
        S.screen = "data";
      }
    });
  }

  const searchInput = el("input", "ws-search");
  searchInput.type = "search";
  searchInput.placeholder = "Tài khoản, máy hoặc nhóm";
  searchInput.setAttribute("aria-label", "Tìm đối tượng theo tên");
  const searchResults = el("div", "ws-results");
  let searchTimer = null,
    searchToken = 0,
    searchedFor = "";
  searchInput.oninput = () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(runSearch, 180);
  };
  async function runSearch() {
    const token = ++searchToken;
    const text = searchInput.value.trim();
    if (!text) {
      S.results = [];
      searchedFor = "";
      renderResults();
      return;
    }
    try {
      const data = await api("/api/search?q=" + encodeURIComponent(text));
      if (token === searchToken) {
        S.results = data.results;
        searchedFor = text;
        renderResults();
      }
    } catch (error) {
      V.showError(error);
    }
  }
  function renderResults() {
    searchResults.replaceChildren();
    if (searchedFor && !S.results.length)
      searchResults.append(el("p", "note", "Không có đối tượng nào tên như vậy."));
    for (const node of S.results) {
      const row = button(
        "",
        () =>
          job("Đang mở đối tượng…", async () => {
            await openNode(node.id, { fresh: true });
            S.results = [];
            searchedFor = "";
            renderResults();
          }),
        "ws-result",
      );
      row.append(
        el("i", "ws-dot " + node.kind.toLowerCase()),
        el("span", "", node.label),
      );
      searchResults.append(row);
    }
  }

  function field(title, ...content) {
    const box = el("div", "ws-field");
    box.append(el("div", "label", title), ...content);
    return box;
  }
  function sourcePanel() {
    const box = el("div", "ws-form");
    box.append(
      field(
        "Xuất phát từ",
        S.source
          ? el("p", "ws-chosen", shortName(S.source))
          : el("p", "note", "Bấm một tài khoản hoặc máy trên đồ thị."),
      ),
    );
    const scenario = el("select");
    scenario.setAttribute("aria-label", "Giả định ban đầu");
    for (const [value, item] of Object.entries(scenarios)) {
      const option = el("option", "", item.label);
      option.value = value;
      scenario.append(option);
    }
    scenario.value = S.scenario;
    scenario.onchange = () => {
      S.scenario = scenario.value;
      clearResults();
      update();
    };
    box.append(field("Giả định", scenario));
    const target = el("select");
    target.setAttribute("aria-label", "Mục tiêu");
    for (const node of S.opened.targets) {
      const option = el("option", "", shortName(node));
      option.value = node.id;
      target.append(option);
    }
    target.value = S.target;
    target.onchange = () => {
      S.target = target.value;
      clearResults();
      update();
    };
    box.append(field("Mục tiêu", target));
    const run = button("Tìm đường", findPaths, "ws-primary");
    run.disabled = !S.source || !S.target || Boolean(S.busy);
    const choke = button("Tìm điểm nghẽn", findChokepoints, "ws-secondary");
    choke.disabled = !S.target || Boolean(S.busy);
    box.append(run, choke);
    return box;
  }
  function findPaths() {
    const waitNote = count(S.opened.report.edges) > 5000 ? " Bộ dữ liệu này cần khoảng 15 giây." : "";
    return job("Đang tìm đường…" + waitNote, async () => {
      const answer = await api("/api/paths", {
        source: S.source.id,
        target: S.target,
        scenario: S.scenario,
      });
      clearResults();
      S.answer = answer;
      S.screen = "paths";
      V.resetCanvas();
    });
  }
  function tryRemoval(edge) {
    const waitNote = count(S.opened.report.edges) > 5000 ? " Bộ dữ liệu này cần khoảng nửa phút." : "";
    return job("Đang dựng lại đồ thị và tìm lại từ đầu…" + waitNote, async () => {
      const removal = await api("/api/remove", {
        edge_source: edge.source,
        edge_kind: edge.kind,
        edge_target: edge.target,
        source: S.source.id,
        target: S.target,
        scenario: S.scenario,
      });
      S.answer = removal.before;
      S.removal = removal;
      S.program = 0;
      S.screen = "paths";
      V.setPhase(removal.after ? "after" : "before");
      V.resetCanvas();
    });
  }
  function findChokepoints() {
    const waitNote = count(S.opened.report.edges) > 5000 ? " Bộ dữ liệu này cần khoảng ba phút." : "";
    return job("Đang tìm điểm nghẽn…" + waitNote, async () => {
      const poll = setInterval(async () => {
        const state = await api("/api/progress").catch(() => null);
        if (state?.stage && S.busy) {
          S.busy = `${state.stage}: ${state.done}/${state.total}`;
          update();
        }
      }, 800);
      try {
        const found = await api("/api/chokepoints", {
          target: S.target,
          scenario: S.scenario,
        });
        S.answer = null;
        S.removal = null;
        S.chokepoints = found;
        S.screen = "chokepoints";
      } finally {
        clearInterval(poll);
      }
    });
  }
  function download() {
    const payload = S.removal || S.answer;
    const link = el("a");
    link.href = URL.createObjectURL(
      new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
    );
    link.download = S.removal ? "neo-thu-go-quan-he.json" : "neo-duong-tim-duoc.json";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function renderProgramList() {
    const answer = activeAnswer();
    const hasPaths = Boolean(answer?.programs.length);
    $("list-title").hidden = !hasPaths;
    $("list-title").textContent = !S.removal
      ? "Các đường, xếp theo C"
      : V.phase() === "before"
        ? "Các đường trước khi gỡ"
        : "Các đường sau khi gỡ";
    answer?.programs.forEach((program, i) => {
      const chosen = showingPaths() && program === currentProgram();
      const row = button(
        "",
        () => {
          S.program = i;
          S.screen = "paths";
          V.resetCanvas();
          update();
        },
        "choice" + (chosen ? " selected" : ""),
      );
      row.setAttribute("aria-pressed", String(chosen));
      const copy = el("span", "choice-copy");
      copy.append(
        el("strong", "", "Đường " + (i + 1)),
        el("small", "", program.steps.length + " bước"),
      );
      row.append(copy, el("span", "choice-cost", "C " + program.C));
      $("choices").append(row);
    });
  }
  function renderHead() {
    const answer = activeAnswer();
    if (S.screen === "data") {
      $("heading").textContent = "Chọn dữ liệu";
      V.pill("");
    } else if (S.screen === "chokepoints") {
      $("heading").textContent = "Điểm nghẽn tới " + labelOf(S.target);
      V.pill("");
    } else if (showingPaths()) {
      const removed = S.removal?.edit;
      $("heading").textContent = removed
        ? `Gỡ ${labelOf(removed.source)} → ${labelOf(removed.target)}`
        : `${shortName(S.source)} → ${labelOf(S.target)}`;
      const verdict = verdictOf(S.removal) || statusOf(answer);
      V.pill(verdict.label, verdict.tone);
    } else {
      $("heading").textContent = S.nodes.size ? "Quan hệ quanh đối tượng" : "Tìm một đối tượng";
      V.pill("");
    }
  }
  function statusOf(answer) {
    return answer.outcome === "blocked_in_scope"
      ? { label: "Không có đường", tone: "clear" }
      : outcomes[answer.outcome];
  }
  function finalVerdict(removal) {
    if (!removal.after) return { label: "Không gỡ trực tiếp được", tone: "pending" };
    if (removal.edit.status === "other_support_remains")
      return { label: "Quan hệ vẫn còn", tone: "pending" };
    return outcomes[removal.after.outcome];
  }
  function verdictOf(removal) {
    if (!removal) return null;
    return V.phase() === "before" && removal.after
      ? outcomes[removal.before.outcome]
      : finalVerdict(removal);
  }
  function renderStrip() {
    const strip = $("result-strip");
    if (S.removal && showingPaths()) {
      const best = (answer) => answer?.programs[0]?.C;
      const blocked = S.removal.after?.outcome === "blocked_in_scope";
      V.metrics([
        ["C sau khi gỡ", best(S.removal.after) ?? (blocked ? "Không có đường" : "Chưa rõ"), ""],
        ["C trước", best(S.removal.before) ?? "Không có", ""],
      ]);
    } else if (showingPaths() && currentProgram()) {
      const program = currentProgram();
      V.metrics([
        [S.answer.minimum ? "C nhỏ nhất" : "C tốt nhất đã tìm", program.C, ""],
        ["bước", program.steps.length, ""],
      ]);
    } else strip.replaceChildren();
  }
  function routeThrough(answer) {
    const steps = answer.programs[0]?.steps || [];
    const stops = [...new Set(steps.map((s) => s.target))].filter(
      (id) => id !== S.target && id !== S.source?.id,
    );
    return stops.map(labelOf).join(", ");
  }
  function renderChokepoints() {
    const host = $("survey");
    host.replaceChildren();
    const found = S.chokepoints;
    const intro = el("div", "survey-intro");
    const sampled = found.sources_tried < found.eligible_sources;
    intro.append(
      el(
        "p",
        "",
        `${found.sources_reached}/${found.sources_tried} nguồn${sampled ? " lấy mẫu" : ""} tới được ${labelOf(found.target)}. Mỗi quan hệ dưới đây được gỡ thử rồi tìm lại từ đầu cho các nguồn đó.`,
      ),
    );
    host.append(intro);
    if (!found.candidates.length) {
      host.append(el("p", "note", "Không có quan hệ nào để gỡ vì chưa có nguồn nào tới được mục tiêu."));
      return;
    }
    const table = el("table", "ws-table");
    const head = el("tr");
    for (const title of ["Quan hệ", "Trên đường tốt nhất", "Nguồn mất đường", "Còn đường vòng", "C trước → sau"])
      head.append(el("th", "", title));
    const thead = el("thead");
    thead.append(head);
    const body = el("tbody");
    const shortLabel = (label) => label.split("@")[0].split(".")[0];
    for (const item of found.candidates) {
      const row = el("tr");
      const name = el("td");
      name.append(
        button(
          `${shortLabel(item.source_label)} ${relationText[item.edge.kind] || item.edge.kind} ${shortLabel(item.target_label)}`,
          () =>
            job("Đang mở đối tượng…", async () => {
              await openNode(item.edge.source, { fresh: true });
              const edge = [...S.edges.values()].find((e) => sameEdge(e, item.edge));
              if (edge) V.select({ type: "edge", id: edge.id });
            }),
        ),
      );
      const mean = (value) => (value == null ? "-" : Number(value.toFixed(1)));
      row.append(
        name,
        el("td", "num", item.in_best_paths),
        el("td", "num" + (item.blocked ? " ws-verdict-clear" : ""), item.blocked),
        el("td", "num" + (item.bypass ? " ws-verdict-route" : ""), item.bypass),
        el("td", "num", `${mean(item.C_before_mean)} → ${mean(item.C_after_mean)}`),
      );
      body.append(row);
    }
    table.append(thead, body);
    host.append(table);
  }
  function renderScope() {
    if (showingPaths()) {
      const answer = activeAnswer();
      $("scope-note").textContent =
        answer.outcome === "blocked_in_scope" || currentProgram() ? "" : M.limitation(answer);
    } else $("scope-note").textContent = "";
  }
  function render() {
    refreshLabels();
    const tableScreen = S.screen === "data" || S.screen === "chokepoints";
    $("canvas").hidden = tableScreen;
    $("survey").hidden = !tableScreen;
    document.querySelector(".inspector").hidden = S.screen === "data";
    $("phase-controls").hidden = !(S.removal?.after && showingPaths());
    document.querySelector(".toolbar-right").hidden = false;
    $("before").classList.toggle("active", V.phase() === "before");
    $("after").classList.toggle("active", V.phase() === "after");
    $("dataset").textContent = S.opened
      ? S.opened.report.domains[0] || S.opened.report.name
      : "Chưa mở dữ liệu";
    $("input-origin").textContent = "";
    const card = $("source-card");
    if (S.opened) {
      const dataScreen = S.screen === "data";
      card.append(
        button(
          dataScreen ? "Quay lại đồ thị" : "Đổi dữ liệu",
          () => {
            S.pendingExports = null;
            S.pendingFile = null;
            S.screen = dataScreen ? "explore" : "data";
            update();
          },
          "ws-switch",
        ),
        field("Tìm đối tượng", searchInput, searchResults),
        sourcePanel(),
      );
    }
    renderProgramList();
    renderHead();
    renderStrip();
    renderScope();
    if (S.screen === "data") renderData();
    if (S.screen === "chokepoints") {
      if (S.busy) {
        $("survey").replaceChildren(el("p", "ws-busy", S.busy));
      } else renderChokepoints();
    }
    const empty = $("empty");
    if (tableScreen) empty.hidden = true;
    else if (S.busy) {
      empty.hidden = false;
      empty.textContent = S.busy;
    } else if (S.screen === "explore" && !S.nodes.size) {
      empty.hidden = false;
      empty.textContent = "Gõ tên tài khoản, máy hoặc nhóm vào ô tìm kiếm.";
    } else if (showingPaths() && !currentProgram()) {
      empty.hidden = false;
      const from = S.source ? shortName(S.source) : "nguồn này";
      empty.textContent =
        activeAnswer().outcome === "blocked_in_scope"
          ? `${from} không ${S.removal ? "còn" : "có"} đường tới ${labelOf(S.target)}.`
          : "Chưa tìm được đường: hết ngân sách tìm kiếm.";
    }
    $("canvas").setAttribute("aria-busy", String(Boolean(S.busy)));
  }

  function detailsForReport(box) {
    const report = S.opened.report;
    const list = (m) =>
      Object.entries(m)
        .sort((a, b) => b[1] - a[1])
        .map(([k, v]) => `${k} ${v}`)
        .join(", ");
    box.append(el("h2", "", report.domains[0] || report.name));
    fact(box, `${count(report.nodes)} đối tượng`, list(report.nodes));
    fact(box, `${count(report.edges)} quan hệ`, list(report.edges) || "Không có");
    const notes = [];
    if (!report.session_edges) notes.push("Không có dữ liệu phiên đăng nhập.");
    else if (report.failed_session_collections)
      notes.push(`${report.failed_session_collections} máy không thu được dữ liệu phiên.`);
    const outside = count(report.outside_references);
    if (outside)
      notes.push(`Bỏ ${outside} tham chiếu tới ${Object.keys(report.outside_references).length} đối tượng ngoài bản xuất.`);
    if (count(report.untyped_references))
      notes.push(`${count(report.untyped_references)} tham chiếu không rõ loại được nhận theo mã đối tượng.`);
    if (Object.keys(report.dropped_identifiers).length)
      notes.push(`Bỏ ${Object.keys(report.dropped_identifiers).length} đối tượng không xác định được miền.`);
    if (report.skipped_records.length)
      notes.push(`Bỏ ${report.skipped_records.length} bản ghi không đọc được.`);
    if (count(report.unused_record_kinds))
      notes.push(`Chưa dùng: ${list(report.unused_record_kinds)}.`);
    if (notes.length) box.append(el("h3", "", "Khi đọc dữ liệu"));
    notes.forEach((text) => note(box, text));
    if (report.skipped_records.length) {
      const more = el("details");
      more.append(el("summary", "note", "Xem các bản ghi bị bỏ"));
      report.skipped_records.slice(0, 50).forEach((line) => note(more, line));
      box.append(more);
    }
  }
  function detailsForNode(box, id) {
    const known = S.nodes.get(id) || activeAnswer()?.labels?.[id];
    box.append(
      el("h2", "", known ? shortName(known) : id),
      el("p", "detail-subtitle", known?.label || id),
    );
    if (known?.enabled === false) note(box, "Đối tượng này đang bị vô hiệu hóa.");
    else if (known && ["User", "Computer"].includes(known.kind) && !known.boundary) {
      const chosen = S.source?.id === id;
      const pick = button(
        chosen ? "Đang xuất phát từ đây" : "Xuất phát từ đây",
        () => chooseSource({ id, label: known.label, kind: known.kind }),
        "ws-primary",
      );
      pick.disabled = chosen;
      box.append(pick);
    }
    const info = S.info.get(id);
    if (info) {
      box.append(el("h3", "", `${info.total_edges} quan hệ`));
      for (const [kind, value] of Object.entries(info.counts)) {
        const row = el("div", "ledger-row");
        row.append(el("span", "", kind), el("b", "", value));
        box.append(row);
      }
      if (info.total_edges > info.edges.length)
        note(box, `Đồ thị đang vẽ ${info.edges.length} quan hệ kiểm soát trước.`);
    } else
      box.append(
        button(
          "Xem quan hệ",
          () => job("Đang mở đối tượng…", () => openNode(id, { fresh: S.screen !== "explore" })),
          "ws-secondary",
        ),
      );
    fact(box, "Mã đối tượng", id);
  }
  function removalButton(box, edge) {
    if (!S.source || !S.target) {
      note(box, "Chọn điểm xuất phát để gỡ thử quan hệ này.");
      return;
    }
    box.append(button("Gỡ thử quan hệ này", () => tryRemoval(edge), "ws-primary"));
  }
  function detailsForExploredEdge(box, id) {
    const edge = S.edges.get(id);
    if (!edge) return;
    box.append(
      el("h2", "", edge.kind),
      el(
        "p",
        "detail-subtitle",
        `${labelOf(edge.source)} ${relationText[edge.kind] || "có quan hệ với"} ${labelOf(edge.target)}`,
      ),
    );
    removalButton(box, edge);
  }
  function detailsForStep(box, index) {
    const step = currentProgram()?.steps[index];
    if (!step) return;
    box.append(
      el("span", "tag", "Bước " + (index + 1)),
      el("h2", "", action(step.technique_id)),
    );
    if (step.edge)
      box.append(
        el(
          "p",
          "detail-subtitle",
          `${labelOf(step.edge.source)} ${relationText[step.edge.kind] || step.edge.kind} ${labelOf(step.edge.target)}`,
        ),
      );
    if (step.actor !== step.source) fact(box, "Người thực hiện", labelOf(step.actor));
    if (step.edge) {
      if (!S.removal) removalButton(box, step.edge);
    } else note(box, "Chuỗi hành động tự tạo ra quan hệ này. Hãy gỡ một bước trước nó.");
    if (step.assumptions?.length) {
      box.append(el("h3", "", "Giả định"));
      step.assumptions.forEach((f) => note(box, V.factText(f, labelOf)));
    }
  }
  function detailsForRemoval(box) {
    const removal = S.removal,
      edit = removal.edit;
    const from = shortName(S.source),
      to = labelOf(S.target);
    box.append(
      el("h2", "", finalVerdict(removal).label),
      el(
        "p",
        "detail-subtitle",
        `Gỡ: ${labelOf(edit.source)} ${relationText[edit.kind] || edit.kind} ${labelOf(edit.target)}`,
      ),
    );
    if (edit.status === "derived_only")
      note(box, `${labelOf(edit.source)} có quan hệ này nhờ thuộc một nhóm. Hãy gỡ quan hệ thành viên đó.`);
    else if (edit.status === "other_support_remains")
      note(box, `${labelOf(edit.source)} vẫn có quan hệ này qua một nhóm khác. Hãy gỡ cả quan hệ đó.`);
    else if (removal.after.outcome === "bypass") {
      const through = routeThrough(removal.after);
      note(box, `${from} vẫn tới ${to}${through ? ", đi qua " + through : ""}.`);
    } else if (removal.after.outcome === "blocked_in_scope")
      note(box, `${from} không còn đường tới ${to}.`);
    else note(box, "Hết ngân sách tìm kiếm mà chưa thấy đường nào.");
    box.append(
      button(
        "Quay lại đường ban đầu",
        () => {
          S.removal = null;
          S.program = 0;
          V.resetCanvas();
          update();
        },
        "ws-secondary",
      ),
    );
  }
  function detailsForProgram(box) {
    const answer = activeAnswer();
    const program = currentProgram();
    if (S.removal) detailsForRemoval(box);
    else if (!program) {
      box.append(el("h2", "", statusOf(answer).label));
      note(box, scenarios[S.scenario].detail);
      if (S.scenario === "identity")
        box.append(
          button(
            "Tìm lại với máy và phiên",
            () => {
              S.scenario = "host-compromise";
              findPaths();
            },
            "ws-secondary",
          ),
        );
      return;
    }
    if (!program) return;
    if (!S.removal) box.append(el("h2", "", "Đường " + (answer.programs.indexOf(program) + 1)));
    box.append(el("h3", "", "Các bước"));
    program.steps.forEach((step, i) => {
      const row = button(
        "",
        () => {
          V.select({ type: "edge", id: i });
          update();
        },
        "step-button",
      );
      row.append(
        el("span", "", i + 1),
        el("div", "", `${action(step.technique_id)}: ${labelOf(step.target)}`),
      );
      box.append(row);
    });
    box.append(el("h3", "", "C gồm những việc"));
    for (const unit of program.ledger) {
      const row = el("div", "ledger-row");
      row.append(
        el("span", "", action(unit.technique || "Công việc")),
        el("b", "", M.cost(unit.effort_cost) ?? "-"),
      );
      box.append(row);
    }
    const total = el("div", "ledger-row ledger-total");
    total.append(el("span", "", "Tổng C"), el("b", "", program.C));
    box.append(total);
    const assumptions = el("details");
    assumptions.append(
      el("summary", "note", `Giả định của đường (${program.assumptions.length})`),
    );
    program.assumptions.forEach((f) => note(assumptions, V.factText(f, labelOf)));
    box.append(assumptions);
    box.append(button("Tải kết quả JSON", download, "ws-secondary"));
  }
  function detailsForChokepoints(box) {
    const best = S.chokepoints.candidates[0];
    box.append(el("h2", "", "Cách đọc bảng"));
    note(box, "Nguồn mất đường là số nguồn không còn tới được mục tiêu sau khi gỡ quan hệ đó.");
    note(box, "Còn đường vòng là số nguồn vẫn tới được theo đường khác.");
    if (best && !best.blocked)
      note(box, "Không quan hệ nào trong bảng tự chặn được nguồn nào: cần gỡ nhiều quan hệ cùng lúc.");
  }
  function details(selection) {
    const box = $("details");
    box.replaceChildren();
    if (S.screen === "data") return;
    if (S.screen === "chokepoints") return detailsForChokepoints(box);
    if (selection?.type === "node") return detailsForNode(box, selection.id);
    if (selection?.type === "edge" && showingPaths()) {
      if (typeof selection.id === "number") return detailsForStep(box, selection.id);
      return detailsForRemoval(box);
    }
    if (selection?.type === "edge") return detailsForExploredEdge(box, selection.id);
    if (showingPaths()) return detailsForProgram(box);
    detailsForReport(box);
  }
  function expand(id) {
    if (S.screen !== "explore") return;
    return job("Đang mở đối tượng…", () => openNode(id));
  }

  V.attach({ render, details, graph, expand });
  const nav = el("button", "nav", "Phân tích");
  nav.id = "workspace-mode";
  nav.onclick = update;
  document.querySelector(".sidebar .nav").before(nav);
  document.title = "neo, phân tích đường tấn công";
  update();
  job("Đang kiểm tra dữ liệu có sẵn…", async () => {
    const status = await api("/api/status");
    S.sources = status.sources;
    if (status.opened) opened(status.opened);
  });
})();
