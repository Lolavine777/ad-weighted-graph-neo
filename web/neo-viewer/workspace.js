/* The local app's analysis screen: open data, search, choose a source, find paths, try a removal.
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
    WriteDacl: "có quyền sửa danh sách quyền của",
    ForceChangePassword: "có quyền đặt lại mật khẩu của",
    HasSession: "đang giữ phiên đăng nhập của",
    AdminTo: "có quyền quản trị cục bộ trên",
    CanPSRemote: "được quản trị từ xa qua PowerShell trên",
  };
  const scenarios = {
    identity: {
      label: "Chỉ quyền trong thư mục",
      detail: "Đã chiếm danh tính của nguồn và chỉ đi qua các quyền trong Active Directory.",
    },
    "host-compromise": {
      label: "Thêm máy và phiên",
      detail: "Được dùng thêm quyền quản trị máy, điều khiển từ xa và phiên đăng nhập có trên máy.",
    },
  };
  const outcomes = {
    reachable: { label: "Có đường", tone: "blue" },
    bypass: { label: "Còn đường vòng", tone: "blue" },
    blocked_in_scope: { label: "Chặn trong phạm vi xét", tone: "green" },
    inconclusive: { label: "Chưa kết luận", tone: "amber" },
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
      const error = Error(data.error || "Không nhận được câu trả lời từ ứng dụng.");
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
  const nodeName = (id) => {
    const node = S.nodes.get(id);
    return node ? shortName(node) : labelOf(id);
  };
  function labelOf(id) {
    const known = activeAnswer()?.labels?.[id];
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
    S.program = 0;
    if (S.screen === "paths") S.screen = "explore";
  }
  function pathLabels(steps, extra = []) {
    const labels = {};
    const answer = activeAnswer();
    const middle = [
      ...new Set([...steps.flatMap((s) => [s.source, s.target]), ...extra]),
    ].filter((id) => id !== S.source?.id && id !== S.target);
    const ids = [S.source?.id, ...middle, S.target].filter(Boolean);
    // Three to a row, turning back on each new row, keeps labels legible and the flow unbroken.
    const perRow = 3;
    ids.forEach((id, i) => {
      const known = answer?.labels?.[id] || S.nodes.get(id);
      const node = known || { label: id, kind: "Object" };
      const row = Math.floor(i / perRow),
        column = row % 2 ? perRow - 1 - (i % perRow) : i % perRow;
      labels[id] = {
        label: shortName(node),
        kind: node.kind,
        x: 200 + column * 340,
        y: 220 + row * 210,
      };
    });
    return labels;
  }
  function graph() {
    if (showingPaths()) {
      const program = currentProgram();
      const steps = program?.steps || [];
      const removed = S.removal?.edit;
      const cut = removed
        ? { source: removed.source, kind: removed.kind, target: removed.target }
        : null;
      const edges = steps.map((s, i) => ({
        ...s,
        id: i,
        label: `${i + 1}. ${action(s.technique_id)}`,
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
          label: "Đã gỡ: " + cut.kind,
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
    const intro = el("div", "survey-intro");
    intro.append(
      el("h2", "", "Chọn dữ liệu cần phân tích"),
      el(
        "p",
        "note",
        "Dùng dữ liệu BloodHound thu bằng SharpHound hoặc BloodHound.py. Dữ liệu chỉ được đọc trên máy này, không gửi đi đâu.",
      ),
    );
    host.append(intro);
    if (S.busy) {
      host.append(el("p", "ws-busy", S.busy));
      return;
    }
    if (S.pendingExports) {
      host.append(el("h3", "", "TỆP NÉN NÀY CÓ NHIỀU BẢN XUẤT, HÃY CHỌN MỘT"));
      for (const item of S.pendingExports)
        host.append(
          dataRow(item.domains.join(", ") || item.export, item.export, () =>
            upload(S.pendingFile, item.export),
          ),
        );
      return;
    }
    if (S.sources.length) {
      host.append(el("h3", "", "CÓ SẴN TRÊN MÁY"));
      for (const source of S.sources)
        host.append(
          dataRow(
            source.domains.join(", ") || source.name,
            `${source.name} · bản xuất ${source.export}`,
            () => openSource(source),
          ),
        );
    } else
      host.append(
        el("p", "note", "Chưa thấy bộ dữ liệu nào trong thư mục dữ liệu của ứng dụng."),
      );
    host.append(el("h3", "", "HOẶC MỞ TỆP KHÁC"));
    const input = el("input");
    input.type = "file";
    input.accept = ".zip,application/zip";
    input.hidden = true;
    input.id = "dataset-file";
    input.onchange = () => input.files[0] && upload(input.files[0]);
    host.append(
      input,
      button("Chọn tệp .zip từ BloodHound", () => input.click(), "ws-primary"),
    );
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
        throw Error("Tệp lớn hơn 2 GB. Hãy đặt dữ liệu vào thư mục data/raw rồi mở từ danh sách.");
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
  searchInput.placeholder = "Tên tài khoản, máy, nhóm…";
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
      searchResults.append(el("p", "note", "Không có đối tượng nào khớp."));
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

  function sourcePanel() {
    const box = el("div", "ws-form");
    box.append(el("div", "section-label", "ĐIỂM XUẤT PHÁT"));
    if (S.source)
      box.append(el("p", "ws-chosen", shortName(S.source)));
    else
      box.append(
        el("p", "note", "Tìm một tài khoản hoặc máy, bấm vào nó rồi chọn làm điểm xuất phát."),
      );
    box.append(el("div", "section-label ws-spaced", "GIẢ ĐỊNH BAN ĐẦU"));
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
    box.append(scenario, el("p", "note ws-hint", scenarios[S.scenario].detail));
    box.append(el("div", "section-label", "MỤC TIÊU"));
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
    box.append(target);
    const run = button("Tìm đường", findPaths, "ws-primary");
    run.disabled = !S.source || !S.target || Boolean(S.busy);
    box.append(run);
    return box;
  }
  function findPaths() {
    return job("Đang tìm đường… bộ dữ liệu lớn có thể mất khoảng một phút.", async () => {
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
    return job("Đang dựng lại đồ thị và tìm lại từ đầu…", async () => {
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
    $("list-title").hidden = !answer?.programs.length;
    $("list-title").textContent = !S.removal
      ? "CÁC ĐƯỜNG TÌM ĐƯỢC"
      : V.phase() === "before"
        ? "CÁC ĐƯỜNG TRƯỚC KHI GỠ"
        : "CÁC ĐƯỜNG SAU KHI GỠ";
    answer?.programs.forEach((program, i) => {
      const row = button(
        "",
        () => {
          S.program = i;
          S.screen = "paths";
          V.resetCanvas();
          update();
        },
        "choice" + (showingPaths() && S.program === i ? " selected" : ""),
      );
      row.setAttribute("aria-pressed", String(showingPaths() && S.program === i));
      const copy = el("span", "choice-copy");
      copy.append(
        el("strong", "", "Đường " + (i + 1)),
        el("small", "", program.steps.length + " bước"),
      );
      row.append(
        el("span", "rank", String(i + 1).padStart(2, "0")),
        copy,
        el("span", "choice-cost", "C " + program.C),
      );
      $("choices").append(row);
    });
  }
  function renderHead() {
    const answer = activeAnswer();
    const report = S.opened?.report;
    $("eyebrow").textContent = report
      ? (report.domains[0] || report.name).toUpperCase()
      : "PHÂN TÍCH TRÊN MÁY NÀY";
    if (S.screen === "data") {
      $("heading").textContent = "Mở dữ liệu";
      V.pill("Chưa chạy phân tích", "amber");
    } else if (showingPaths()) {
      const removed = S.removal?.edit;
      $("heading").textContent = removed
        ? `Gỡ ${nodeOrLabel(removed.source)} → ${nodeOrLabel(removed.target)} (${removed.kind})`
        : `${shortName(S.source)} → ${labelOf(S.target)}`;
      const verdict = verdictOf(S.removal) || outcomes[answer.outcome];
      V.pill(verdict.label, verdict.tone);
    } else {
      $("heading").textContent = "Khám phá đồ thị";
      V.pill(report ? "Đã mở dữ liệu" : "", "blue");
    }
  }
  const nodeOrLabel = (id) => {
    const known = S.answer?.labels?.[id] || S.removal?.after?.labels?.[id];
    return known ? shortName(known) : nodeName(id);
  };
  function finalVerdict(removal) {
    if (!removal.after) return { label: "Chưa gỡ được trực tiếp", tone: "amber" };
    if (removal.edit.status === "other_support_remains")
      return { label: "Quan hệ vẫn còn", tone: "amber" };
    return outcomes[removal.after.outcome];
  }
  function verdictOf(removal) {
    if (!removal) return null;
    return V.phase() === "before" && removal.after
      ? outcomes[removal.before.outcome]
      : finalVerdict(removal);
  }
  function renderStrip() {
    if (S.screen === "data") {
      $("result-strip").hidden = true;
      return;
    }
    $("result-strip").hidden = false;
    const best = (answer) => answer?.programs[0]?.C;
    if (S.removal) {
      V.metrics([
        ["C trước", best(S.removal.before) ?? "Chưa có", ""],
        [
          "C sau",
          best(S.removal.after) ??
            (S.removal.after?.outcome === "blocked_in_scope" ? "Không có đường" : "Chưa có"),
          "",
        ],
        ["Lần mở rộng sau", S.removal.after?.expansions ?? "-", ""],
      ]);
    } else if (showingPaths()) {
      const program = currentProgram();
      V.metrics([
        ["Công sức C", program?.C ?? "Không có", ""],
        ["Bước trong đường", program?.steps.length ?? 0, ""],
        ["Lần mở rộng", S.answer.expansions, "/ " + S.answer.max_expansions],
      ]);
    } else {
      const report = S.opened.report;
      const count = (m) => Object.values(m).reduce((a, b) => a + b, 0);
      V.metrics([
        ["Đối tượng", count(report.nodes), ""],
        ["Quan hệ", count(report.edges), ""],
        ["Đang vẽ", S.nodes.size, "đối tượng"],
      ]);
    }
  }
  function renderScope() {
    if (S.screen === "data") $("scope-note").textContent = "";
    else if (showingPaths()) {
      const answer = activeAnswer();
      $("scope-note").textContent = [
        answer.outcome === "blocked_in_scope"
          ? "Kết luận chỉ áp dụng cho nguồn, mục tiêu và giả định đang chọn."
          : M.limitation(answer),
        ...answer.coverage_notes,
        !currentProgram()
          ? ""
          : answer.minimum
            ? "C nhỏ nhất đã được chứng minh trong phạm vi xét."
            : "C là mức tốt nhất trong các đường đã tìm được.",
        S.removal ? "Đây là mô phỏng trên bản dữ liệu; Active Directory thật không bị thay đổi." : "",
      ]
        .filter(Boolean)
        .join(" ");
    } else
      $("scope-note").textContent =
        "Đồ thị chỉ vẽ phần lân cận của đối tượng đã mở. Bấm đúp một đối tượng để mở rộng.";
  }
  function render() {
    refreshLabels();
    const dataScreen = S.screen === "data";
    $("canvas").hidden = dataScreen;
    $("survey").hidden = !dataScreen;
    document.querySelector(".toolbar-right").hidden = dataScreen;
    $("phase-controls").hidden = !(S.removal?.after && showingPaths());
    $("before").classList.toggle("active", V.phase() === "before");
    $("after").classList.toggle("active", V.phase() === "after");
    $("flow-guide").textContent =
      "Mở dữ liệu → tìm đối tượng → chọn điểm xuất phát và mục tiêu → xem đường → thử gỡ một quan hệ.";
    $("graph-caption").textContent = dataScreen
      ? "Chọn bộ dữ liệu để bắt đầu"
      : showingPaths()
        ? "Đường đã được kiểm tra lại từng bước"
        : "Bấm đúp một đối tượng để mở rộng";
    $("dataset").textContent = S.opened
      ? S.opened.report.domains[0] || S.opened.report.name
      : "Chưa mở dữ liệu";
    $("input-origin").textContent = "Chạy trên máy này · dữ liệu không rời khỏi máy";
    const card = $("source-card");
    if (S.opened) {
      card.append(
        button(
          dataScreen ? "Quay lại đồ thị" : "Đổi dữ liệu",
          () => {
            S.pendingExports = null;
            S.pendingFile = null;
            S.screen = dataScreen ? "explore" : "data";
            update();
          },
          "ws-secondary",
        ),
      );
      const label = el("div", "section-label", "TÌM ĐỐI TƯỢNG");
      card.append(label, searchInput, searchResults, sourcePanel());
    }
    $("list-title").hidden = true;
    renderProgramList();
    renderHead();
    renderStrip();
    renderScope();
    if (dataScreen) renderData();
    const empty = $("empty");
    if (dataScreen) empty.hidden = true;
    else if (S.busy) {
      empty.hidden = false;
      empty.textContent = S.busy;
    } else if (S.screen === "explore" && !S.nodes.size) {
      empty.hidden = false;
      empty.textContent = "Gõ tên một đối tượng ở ô tìm kiếm để bắt đầu.";
    } else if (showingPaths() && !currentProgram()) {
      empty.hidden = false;
      empty.textContent =
        activeAnswer().outcome === "blocked_in_scope"
          ? `Không ${S.removal ? "còn" : "có"} đường từ nguồn này tới mục tiêu trong phạm vi đã xét.`
          : "Chưa tìm được đường trong ngân sách tìm kiếm. Chưa thể kết luận là an toàn.";
    }
    $("canvas").setAttribute("aria-busy", String(Boolean(S.busy)));
  }

  function detailsForReport(box) {
    const report = S.opened.report;
    const count = (m) => Object.values(m).reduce((a, b) => a + b, 0);
    const list = (m) =>
      Object.entries(m)
        .sort((a, b) => b[1] - a[1])
        .map(([k, v]) => `${k} ${v}`)
        .join(", ");
    box.append(
      el("h2", "", report.domains[0] || report.name),
      el("p", "detail-subtitle", "Bản xuất " + report.export),
    );
    fact(box, `Đối tượng (${count(report.nodes)})`, list(report.nodes));
    fact(box, `Quan hệ (${count(report.edges)})`, list(report.edges) || "Không có");
    box.append(el("h3", "", "NHỮNG ĐIỀU CẦN LƯU Ý"));
    const notes = [];
    if (count(report.unused_record_kinds))
      notes.push(`Chưa phân tích ${count(report.unused_record_kinds)} bản ghi loại khác: ${list(report.unused_record_kinds)}.`);
    if (!report.session_edges)
      notes.push("Không có dữ liệu phiên đăng nhập, nên kết quả không xét đường đi qua phiên.");
    if (report.failed_session_collections)
      notes.push(`${report.failed_session_collections} máy không thu được đủ dữ liệu phiên đăng nhập.`);
    const outside = Object.values(report.outside_references).reduce((a, b) => a + b, 0);
    if (outside)
      notes.push(`Bỏ ${outside} tham chiếu tới ${Object.keys(report.outside_references).length} đối tượng nằm ngoài bản xuất.`);
    if (count(report.untyped_references))
      notes.push(`${count(report.untyped_references)} tham chiếu không rõ loại được xác định theo mã đối tượng.`);
    if (Object.keys(report.dropped_identifiers).length)
      notes.push(`Bỏ ${Object.keys(report.dropped_identifiers).length} đối tượng không xác định được phạm vi.`);
    if (report.skipped_records.length)
      notes.push(`Bỏ qua ${report.skipped_records.length} bản ghi không đọc được.`);
    if (!notes.length) notes.push("Mọi bản ghi được đọc đầy đủ.");
    notes.forEach((text) => note(box, text));
    if (report.skipped_records.length) {
      const more = el("details");
      more.append(el("summary", "note", "Xem các bản ghi bị bỏ qua"));
      report.skipped_records.slice(0, 50).forEach((line) => note(more, line));
      box.append(more);
    }
  }
  function detailsForNode(box, id) {
    const node = S.nodes.get(id);
    const known = node || activeAnswer()?.labels?.[id];
    box.append(
      el("h2", "", known ? shortName(known) : id),
      el("p", "detail-subtitle", known?.kind || "Đối tượng"),
    );
    fact(box, "Tên đầy đủ", known?.label || id);
    fact(box, "Mã đối tượng", id);
    if (known?.enabled === false)
      note(box, "Đối tượng này đang bị vô hiệu hóa nên không dùng làm điểm xuất phát.");
    else if (known && ["User", "Computer"].includes(known.kind) && !known.boundary) {
      const chosen = S.source?.id === id;
      const pick = button(
        chosen ? "Đang là điểm xuất phát" : "Làm điểm xuất phát",
        () => chooseSource({ id, label: known.label, kind: known.kind }),
        "ws-primary",
      );
      pick.disabled = chosen;
      box.append(pick);
    }
    const info = S.info.get(id);
    if (info) {
      box.append(el("h3", "", `QUAN HỆ (${info.total_edges})`));
      for (const [kind, value] of Object.entries(info.counts)) fact(box, kind, value);
      if (info.total_edges > info.edges.length)
        note(box, `Đang vẽ ${info.edges.length}/${info.total_edges} quan hệ, ưu tiên quan hệ kiểm soát.`);
    } else
      box.append(
        button(
          "Xem quan hệ của đối tượng này",
          () => job("Đang mở đối tượng…", () => openNode(id, { fresh: S.screen !== "explore" })),
          "ws-secondary",
        ),
      );
  }
  function removalButton(box, edge) {
    if (!S.source || !S.target) {
      note(box, "Chọn điểm xuất phát và mục tiêu trước khi thử gỡ một quan hệ.");
      return;
    }
    box.append(button("Thử gỡ quan hệ này", () => tryRemoval(edge), "ws-primary"));
    note(box, "NEO dựng lại đồ thị không có quan hệ này rồi tìm lại từ đầu. Active Directory thật không bị thay đổi.");
  }
  function detailsForExploredEdge(box, id) {
    const edge = S.edges.get(id);
    if (!edge) return;
    box.append(
      el("span", "tag", "QUAN HỆ"),
      el("h2", "", edge.kind),
      el(
        "p",
        "detail-subtitle",
        `${nodeName(edge.source)} ${relationText[edge.kind] || "có quan hệ với"} ${nodeName(edge.target)}`,
      ),
    );
    removalButton(box, edge);
  }
  function detailsForStep(box, index) {
    const step = currentProgram()?.steps[index];
    if (!step) return;
    box.append(
      el("span", "tag", "BƯỚC " + (index + 1)),
      el("h2", "", action(step.technique_id)),
    );
    fact(box, "Chủ thể thực hiện", labelOf(step.actor));
    fact(box, "Nguồn quyền", labelOf(step.source));
    fact(box, "Đích thao tác", labelOf(step.target));
    if (step.edge) {
      fact(box, "Quan hệ trong dữ liệu", step.edge.kind);
      if (!S.removal) removalButton(box, step.edge);
    } else
      note(box, "Quan hệ này do chính chuỗi hành động tạo ra, không có trong dữ liệu gốc. Hãy thử gỡ một bước trước nó.");
    if (step.assumptions?.length) {
      box.append(el("h3", "", "GIẢ ĐỊNH CỦA BƯỚC"));
      step.assumptions.forEach((f) => note(box, factLine(f)));
    }
  }
  function factLine(fact_) {
    const value = fact_.value === true ? "đúng" : fact_.value === false ? "sai" : "chưa rõ";
    return `${fact_.predicate}: ${labelOf(fact_.subject)} → ${labelOf(fact_.target)} = ${value}`;
  }
  function detailsForRemoval(box) {
    const removal = S.removal,
      edit = removal.edit;
    box.append(
      el("span", "tag", "THỬ GỠ QUAN HỆ"),
      el("h2", "", finalVerdict(removal).label),
      el(
        "p",
        "detail-subtitle",
        `${nodeOrLabel(edit.source)} ${relationText[edit.kind] || edit.kind} ${nodeOrLabel(edit.target)}`,
      ),
    );
    if (edit.status === "derived_only")
      note(box, "Quan hệ này được suy ra từ dữ liệu khác, không có bản ghi trực tiếp để gỡ. Hãy gỡ quan hệ thành viên nhóm dẫn tới nó.");
    else if (edit.status === "other_support_remains")
      note(box, "Đã gỡ bản ghi trực tiếp nhưng quan hệ vẫn được tạo ra từ nguồn khác, ví dụ qua thành viên nhóm.");
    else if (removal.after.outcome === "bypass")
      note(box, "Đường cũ đã bị cắt, nhưng nguồn này vẫn tới được mục tiêu theo đường khác.");
    else if (removal.after.outcome === "blocked_in_scope")
      note(box, "Không còn đường từ nguồn này trong phạm vi đã xét. Kết luận chỉ áp dụng cho nguồn này, không phải cho toàn miền.");
    else
      note(box, "Hết ngân sách tìm kiếm mà chưa có đường. Chưa thể kết luận đã chặn được.");
    const removed = Object.entries(edit.removed_observations);
    if (removed.length) {
      box.append(el("h3", "", "BẢN GHI ĐÃ BỎ KHỎI MÔ PHỎNG"));
      for (const [field, value] of removed) fact(box, field, value);
    }
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
    else {
      const verdict = outcomes[answer.outcome];
      box.append(
        el("h2", "", program ? "Đường " + (S.program + 1) : verdict.label),
        el(
          "p",
          "detail-subtitle",
          program
            ? answer.minimum
              ? "C nhỏ nhất đã được chứng minh trong phạm vi xét"
              : "C tốt nhất trong các đường đã tìm được"
            : "Trong phạm vi và ngân sách đã khai báo",
        ),
      );
    }
    if (!program) {
      if (!S.removal) {
        note(box, scenarios[S.scenario].detail);
        note(
          box,
          "NEO chỉ xét các kỹ thuật trong danh mục hiện có. Kỹ thuật ngoài danh mục, như ủy quyền Kerberos hoặc AD CS, chưa được xét, nên đây không phải kết luận rằng nguồn này an toàn.",
        );
      }
      return;
    }
    const hero = el("div", "cost-hero");
    hero.append(el("span", "", "Công sức tương đối"), el("strong", "", program.C));
    box.append(hero);
    box.append(el("h3", "", "CÁC BƯỚC"));
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
        el("span", "", String(i + 1).padStart(2, "0")),
        el("div", "", `${action(step.technique_id)}: ${labelOf(step.target)}`),
      );
      box.append(row);
    });
    box.append(el("h3", "", "THÀNH PHẦN CỦA C"));
    for (const unit of program.ledger) {
      const row = el("div", "ledger-row");
      row.append(
        el("span", "", action(unit.technique || "Công việc")),
        el("b", "", M.cost(unit.effort_cost) ?? "-"),
      );
      box.append(row);
    }
    const assumptions = el("details");
    assumptions.append(
      el("summary", "note", `Giả định của đường (${program.assumptions.length})`),
    );
    program.assumptions.forEach((f) => note(assumptions, factLine(f)));
    box.append(assumptions);
    box.append(button("Tải kết quả JSON", download, "ws-secondary"));
  }
  function details(selection) {
    const box = $("details");
    box.replaceChildren();
    if (S.screen === "data") {
      note(box, "Chọn một bộ dữ liệu ở giữa màn hình. Sau khi mở, phần này cho biết NEO đã đọc và đã bỏ qua những gì.");
      return;
    }
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
  const nav = el("button", "nav", "");
  nav.id = "workspace-mode";
  nav.append(el("span", "", "◎"), document.createTextNode(" Phân tích"));
  nav.onclick = update;
  document.querySelector(".sidebar .nav").before(nav);
  document.querySelector(".brand-sub").textContent = "PHÂN TÍCH ĐƯỜNG TẤN CÔNG";
  document.querySelector(".local-indicator span").textContent = "Chạy trên máy này";
  document.title = "neo · Phân tích đường tấn công";
  document.body.classList.add("has-workspace");
  update();
  job("Đang kiểm tra dữ liệu có sẵn…", async () => {
    const status = await api("/api/status");
    S.sources = status.sources;
    if (status.opened) opened(status.opened);
  });
})();
