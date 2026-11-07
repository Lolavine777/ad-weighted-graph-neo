/* Local presentation only: no network requests or execution; only the theme choice is remembered.
   The local app adds workspace.js through NeoViewer; Pages and the offline copy never load it. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id),
    M = NeoViewModel;
  const NS = "http://www.w3.org/2000/svg";
  const names = {
    propagate_group_entitlement: "Dùng quyền nhóm",
    scenario_reset_password: "Đặt lại mật khẩu",
    genericall_reset_password: "Đặt lại mật khẩu",
    reset_target_password: "Đặt lại mật khẩu",
    acquire_reset_identity: "Dùng danh tính vừa đặt lại",
    genericall_add_member: "Thêm thành viên nhóm",
    genericall_grant_write_dacl: "Cấp quyền sửa DACL",
    grant_new_object_right: "Cấp quyền đối tượng",
    obtain_admin_execution_on_host: "Thực thi quản trị máy",
    scenario_winrm_admin: "Quản trị qua WinRM",
    open_winrm_remote_session: "Mở phiên WinRM",
    use_session_identity: "Dùng danh tính từ phiên",
    "Dùng quyền thành viên nhóm": "Dùng quyền nhóm",
    "Reset mật khẩu": "Đặt lại mật khẩu",
    "Dùng danh tính vừa reset": "Dùng danh tính vừa đặt lại",
    "Sửa DACL để cấp quyền": "Cấp quyền đối tượng",
  };
  const factNames = {
    security_group: "Là nhóm bảo mật",
    membership_usable: "Dùng được quyền thành viên",
    membership_change_allowed: "Được đổi thành viên nhóm",
    directory_write_allowed: "Được ghi vào thư mục",
    authentication_accepted: "Xác thực được chấp nhận",
    network_kdc_reachable: "Kết nối được tới KDC",
    network_rpc_reachable: "Kết nối được qua RPC",
    session_present: "Có phiên đăng nhập",
    session_fresh: "Phiên còn mới",
    credential_accessible: "Lấy được thông tin xác thực",
    session_identity_usable: "Dùng được danh tính từ phiên",
    admin_channel: "Có kênh quản trị",
    password_policy_accepts: "Chính sách mật khẩu chấp nhận",
  };
  const strategyNames = {
    neo_guided: "Tìm có hướng dẫn",
    neo_refine: "Tìm cải tiến C",
    fifo: "Tìm theo thứ tự hàng đợi",
  };
  const caseNames = {
    "rodc-membership": "RODCMANAGER khỏi Administrators",
    "extca-session": "Phiên của BM trên EXTCA01",
    "bm-da-membership": "BM khỏi Domain Admins",
  };
  let view,
    mode = "paths",
    index = 0,
    phase = "after",
    queryIndex = 0,
    selection = null,
    zoom = 1,
    pan = { x: 0, y: 0 },
    nodePositions = Object.create(null),
    custom = null,
    bundled = false,
    host = null,
    lastNodeClick = 0;
  const label = (id) =>
    view.labels?.[id]?.label ||
    id?.replace(/^.*-(\d+)$/, "SID …$1") ||
    "Chưa khai báo";
  const action = (id) => names[id] || id;
  const strategy = (id) => strategyNames[id] || id;
  const empty = "-";
  // Imported decisions carry structured facts; show them as one readable line.
  const factText = (f, name = label) => {
    if (typeof f === "string") return f;
    const value = f.value === true ? "" : f.value === false ? " (sai)" : " (chưa rõ)";
    return `${factNames[f.predicate] || f.predicate}: ${name(f.subject)} → ${name(f.target)}${value}`;
  };
  const caseTitle = (c) => (bundled && caseNames[c.case]) || c.case;
  function el(tag, cls, content) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (content !== undefined) n.textContent = String(content);
    return n;
  }
  function svg(tag, attrs = {}) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
    return n;
  }
  function button(text, fn, cls = "") {
    const b = el("button", cls, text);
    b.onclick = fn;
    return b;
  }
  function fact(parent, title, value) {
    const f = el("div", "fact-row", title);
    f.append(el("strong", "", value ?? "Chưa khai báo"));
    parent.append(f);
  }
  function note(parent, text) {
    parent.append(el("p", "note", text));
  }
  function load(input, imported = false) {
    const next = M.normalize(input);
    bundled = Object.values(NEO_DEMOS).includes(input);
    if (input === NEO_DEMOS.survey)
      next.title = "SEAMLESS, nhiều nguồn độc lập";
    if (input === NEO_DEMOS.remediation) {
      next.title = "WRAITH, can thiệp";
      next.scenario = "Nguồn tài khoản có danh tính dùng được; nguồn máy có quyền quản trị cục bộ";
    }
    view = next;
    mode = next.kind;
    index = 0;
    queryIndex = 0;
    selection = null;
    nodePositions = Object.create(null);
    zoom = 1;
    pan = { x: 0, y: 0 };
    if (input === NEO_DEMOS.remediation) {
      const prefix = "S-1-5-21-3702535222-3822678775-2090119576";
      view.labels = {
        [prefix + "-1119"]: { label: "RODCMANAGER", kind: "User" },
        [prefix + "-1120"]: { label: "EXTCA01", kind: "Computer" },
        [prefix + "-1113"]: { label: "BM", kind: "User" },
        [prefix + "-512"]: { label: "DOMAIN ADMINS", kind: "Group" },
        ["domain:sid:" + prefix + ":S-1-5-32-544"]: {
          label: "ADMINISTRATORS",
          kind: "Group",
        },
      };
    }
    if (input === NEO_DEMOS.survey) {
      const prefix = "S-1-5-21-1271839998-3495686680-2211690266";
      view.labels = {
        [prefix + "-1116"]: { label: "KATRINA_GREEN", kind: "User" },
        ["domain:sid:" + prefix + ":S-1-5-32-544"]: {
          label: "ADMINISTRATORS",
          kind: "Group",
        },
      };
    }
    if (imported) custom = { input, mode };
    fillDataset();
    render();
  }
  function fillDataset() {
    $("dataset").textContent = view.title;
    $("paths-mode").classList.toggle("active", mode === "paths");
    $("remediation-mode").classList.toggle("active", mode === "remediation");
    $("survey-mode").classList.toggle("active", mode === "survey");
    $("workspace-mode")?.classList.toggle("active", mode === "workspace");
    $("reset-demo").hidden = mode === "workspace";
    $("dataset-label").textContent =
      mode === "workspace" ? "Dữ liệu đang mở" : "Kết quả";
    if (mode === "workspace") return;
    $("input-origin").textContent = bundled ? "Dữ liệu mẫu" : "Tệp bạn mở";
  }
  function currentProgram() {
    return view.programs?.[index];
  }
  function currentCase() {
    return view.cases?.[index];
  }
  function currentQuery() {
    return currentCase()?.queries[queryIndex] || currentCase()?.queries[0];
  }
  function selectItem(i) {
    index = i;
    queryIndex = 0;
    selection = null;
    nodePositions = Object.create(null);
    render();
  }
  function render() {
    $("choices").replaceChildren();
    $("source-card").replaceChildren();
    $("phase-controls").hidden = mode !== "remediation";
    $("before").classList.toggle("active", phase === "before");
    $("after").classList.toggle("active", phase === "after");
    $("empty").hidden = true;
    $("result-strip").hidden = false;
    $("list-title").hidden = false;
    document.querySelector(".inspector").hidden = false;
    $("scope-note").textContent = "";
    if (mode === "workspace") {
      host.render();
      draw();
      host.details(selection);
      return;
    }
    $("canvas").hidden = mode === "survey";
    $("survey").hidden = mode !== "survey";
    document.querySelector(".toolbar-right").hidden = mode === "survey";
    if (mode === "survey") {
      renderSurvey();
      return;
    }
    if (mode === "paths") renderPath();
    else renderRemediation();
    draw();
    details();
  }
  function sourceBox(source, target) {
    const box = el("div", "source-box");
    box.append(
      el("small", "", "Nguồn"),
      el("p", "", source),
      el("small", "", "Đích"),
      el("p", "", target),
    );
    $("source-card").append(box);
  }
  function renderSurvey() {
    $("heading").textContent = "Gỡ một quan hệ, nhiều nguồn còn tới được không?";
    pill("");
    $("list-title").textContent = "";
    $("list-title").hidden = true;
    sourceBox(
      new Set(view.cells.map((c) => c.source_node_id)).size + " nguồn độc lập",
      "Các đích trong khảo sát",
    );
    const sources = [
      ...new Map(view.cells.map((c) => [c.source_node_id, c.source])).entries(),
    ];
    const select = el("select");
    select.setAttribute("aria-label", "Lọc nguồn khảo sát");
    const all = el("option", "", "Tất cả nguồn");
    all.value = "";
    select.append(all);
    for (const [id, name] of sources) {
      const o = el("option", "", name.split("@")[0]);
      o.value = id;
      select.append(o);
    }
    const selectedFilter = view.filter || "";
    select.value = selectedFilter;
    select.onchange = () => {
      view.filter = select.value;
      index = 0;
      render();
    };
    $("source-card").append(select);
    const cells = view.cells.filter(
      (c) => !selectedFilter || c.source_node_id === selectedFilter,
    );
    const host = $("survey");
    host.replaceChildren();
    const summary = el("div", "survey-intro");
    summary.append(
      el("h2", "", "Gỡ quan hệ " + view.point.edge.kind),
      el(
        "p",
        "note",
        `Cắt ${view.totals.programs_cut}/${view.totals.baseline_programs} đường mẫu, nhưng chỉ ngắt ${view.totals.pairs_disconnected}/${view.totals.pairs} cặp nguồn và đích.`,
      ),
    );
    host.append(summary);
    const table = el("table");
    const head = el("thead"),
      tr = el("tr");
    for (const name of ["Nguồn", "Đích", "C trước → sau", "Sau can thiệp"])
      tr.append(el("th", "", name));
    head.append(tr);
    table.append(head);
    const body = el("tbody");
    cells.forEach((c, i) => {
      const r = c.intervention_result;
      const row = el("tr", i === index ? "selected" : "");
      const b = button(
        c.source.split("@")[0],
        () => {
          index = i;
          render();
        },
        "row-button",
      );
      const td = el("td");
      td.append(b);
      const status =
        r.after.reachability === "reachable"
          ? "Còn đường"
          : r.disconnected === true
            ? "Đã chặn"
            : "Chưa kết luận";
      row.append(
        td,
        el("td", "", c.target),
        el(
          "td",
          "",
          `${M.cost(r.effort.before) ?? empty} → ${M.cost(r.effort.after) ?? empty}`,
        ),
        el("td", "", status),
      );
      body.append(row);
    });
    table.append(body);
    host.append(table);
    metrics([
      [
        "cặp còn đường",
        cells.filter(
          (c) => c.intervention_result.after.reachability === "reachable",
        ).length,
        "/ " + cells.length,
      ],
    ]);
    $("scope-note").textContent = "";
    const box = $("details");
    box.replaceChildren();
    const c = cells[index];
    if (!c) return;
    box.append(
      el("h2", "", c.source.split("@")[0]),
      el("p", "detail-subtitle", c.source_kind + " → " + c.target),
    );
    fact(box, "Quyền ban đầu", M.sourceCapability(view, c));
    fact(
      box,
      "Kết quả sau",
      c.intervention_result.after.reachability === "reachable"
        ? "Vẫn tới được đích"
        : "Không còn đường",
    );
    fact(
      box,
      "Đường mẫu bị cắt",
      c.intervention_result.cut_program_ids?.length ?? 0,
    );
    fact(box, "Thành viên bị gỡ", label(view.point.edge.source));
    fact(box, "Nhóm đích", label(view.point.edge.target));
    box.append(el("h3", "", "C của các đường trước khi gỡ"));
    c.programs.forEach((p, i) =>
      fact(box, "Đường " + (i + 1), M.cost(p.C) ?? "Chưa chấm"),
    );
  }
  function choice(i, title, subtitle, costValue) {
    const b = button(
      "",
      () => selectItem(i),
      "choice" + (index === i ? " selected" : ""),
    );
    b.setAttribute("aria-pressed", String(index === i));
    const copy = el("span", "choice-copy");
    copy.append(el("strong", "", title), el("small", "", subtitle));
    b.append(copy, el("span", "choice-cost", costValue));
    $("choices").append(b);
  }
  function pill(label, tone = "route") {
    $("status").textContent = label;
    $("status").className = "status " + tone;
  }
  function metrics(items) {
    $("result-strip").replaceChildren(
      ...items.map(([title, value, suffix]) => {
        const d = el("div", "metric");
        const strong = el(
          "strong",
          typeof value === "number" ? "" : "word",
          value,
        );
        d.append(el("small", "", title), strong);
        if (suffix) d.append(el("em", "", suffix));
        return d;
      }),
    );
  }
  function renderPath() {
    $("heading").textContent = label(view.source) + " → " + label(view.target);
    sourceBox(label(view.source), label(view.target));
    $("list-title").textContent = "Các đường, xếp theo C";
    view.programs.forEach((p, i) =>
      choice(
        i,
        "Đường " + (i + 1),
        p.steps.length + " bước" + (p.C == null ? ", chưa chấm C" : ""),
        p.C == null ? empty : "C " + p.C,
      ),
    );
    const p = currentProgram();
    pill(
      p
        ? view.minimum
          ? "Có đường, C nhỏ nhất"
          : "Có đường"
        : view.noPath
          ? "Không có đường"
          : "Chưa kết luận",
      p ? "route" : view.noPath ? "clear" : "pending",
    );
    metrics([
      ["Công sức C", p?.C ?? "Chưa chấm", ""],
      ["bước", p?.steps.length ?? 0, ""],
    ]);
    $("scope-note").textContent = p ? "" : M.limitation(view);
    if (!p || !p.steps.length) {
      $("empty").hidden = false;
      $("empty").textContent = p
        ? "Nguồn đã có sẵn mục tiêu, không cần bước nào."
        : view.noPath
          ? "Không có đường."
          : "Chưa tìm được đường. " + (M.limitation(view) || "Tệp không ghi lý do.");
    }
  }
  function renderRemediation() {
    const c = currentCase(),
      q = currentQuery(),
      s = q[phase],
      out = M.outcome(s);
    $("heading").textContent = "Gỡ " + caseTitle(c);
    pill(out.label, out.tone);
    sourceBox(
      bundled ? "Điểm xuất phát ban đầu" : q.source || "Không ghi trong tệp",
      q.goal || "Không ghi trong tệp",
    );
    $("list-title").textContent = "Các can thiệp";
    view.cases.forEach((c, i) =>
      choice(i, caseTitle(c), c.removed_edges.length + " quan hệ", ""),
    );
    const select = el("select");
    select.setAttribute("aria-label", "Chế độ tìm kiếm và mục tiêu");
    c.queries.forEach((q, i) => {
      const o = el("option", "", strategy(q.strategy) + " → " + q.goal);
      o.value = i;
      select.append(o);
    });
    select.value = queryIndex;
    select.onchange = () => {
      queryIndex = Number(select.value);
      selection = null;
      render();
    };
    $("source-card").append(select);
    metrics([
      [
        "C sau khi gỡ",
        M.cost(q.after.C) ??
          (q.after.no_path_proven ? "Không có đường" : "Chưa rõ"),
        "",
      ],
      ["C trước", M.cost(q.before.C) ?? "Chưa chấm", ""],
    ]);
    $("scope-note").textContent = s.reached ? "" : M.limitation(s);
  }
  function graphData() {
    if (mode === "workspace") return host.graph();
    if (mode === "remediation")
      return {
        edges: currentCase().removed_edges.map((e, i) => ({
          ...e,
          id: i,
          technique_id: e.kind,
          removed: phase === "after",
        })),
      };
    return {
      edges: (currentProgram()?.steps || []).map((s, i) => ({ ...s, id: i })),
    };
  }
  function draw() {
    const { edges, nodes: lone = [] } = graphData();
    const ids = [...new Set([...edges.flatMap((e) => [e.source, e.target]), ...lone])];
    if (!ids.length && mode === "paths" && currentProgram())
      ids.push(view.source);
    const layout = Object.create(null),
      positions = Object.create(null);
    ids.forEach((id, i) => {
      const configured = view.labels?.[id];
      layout[id] =
        configured?.x !== undefined
          ? { x: configured.x, y: configured.y }
          : mode === "remediation"
            ? { x: 220 + (i % 3) * 370, y: 240 + Math.floor(i / 3) * 180 }
            : { x: 130 + (i % 4) * 300, y: 210 + Math.floor(i / 4) * 200 };
      positions[id] = nodePositions[id] || layout[id];
    });
    // Fit the view to the layout, not to dragged nodes, so labels stay legible and drags do not rescale.
    const xs = Object.values(layout).map((p) => p.x),
      ys = Object.values(layout).map((p) => p.y);
    if (xs.length) {
      const minX = Math.min(...xs) - 150,
        maxX = Math.max(...xs) + 150,
        minY = Math.min(...ys) - 110,
        maxY = Math.max(...ys) + 90,
        w = Math.max(640, maxX - minX),
        h = Math.max(360, maxY - minY);
      $("graph").setAttribute(
        "viewBox",
        `${(minX + maxX - w) / 2} ${(minY + maxY - h) / 2} ${w} ${h}`,
      );
    } else $("graph").setAttribute("viewBox", "0 0 1200 660");
    $("edges").replaceChildren();
    $("nodes").replaceChildren();
    const pairCount = new Map(),
      pairIndex = new Map();
    for (const e of edges) {
      const key = JSON.stringify([e.source, e.target]);
      pairCount.set(key, (pairCount.get(key) || 0) + 1);
    }
    for (const e of edges) {
      const a = positions[e.source],
        b = positions[e.target];
      if (!a || !b) continue;
      const key = JSON.stringify([e.source, e.target]),
        n = pairIndex.get(key) || 0;
      pairIndex.set(key, n + 1);
      const bend = (n - (pairCount.get(key) - 1) / 2) * 110,
        dx = b.x - a.x,
        dy = b.y - a.y,
        len = Math.hypot(dx, dy) || 1;
      const sx = a.x + (dx / len) * 27,
        sy = a.y + (dy / len) * 27,
        tx = b.x - (dx / len) * 30,
        ty = b.y - (dy / len) * 30;
      let path,
        cx = (a.x + b.x) / 2 - (dy / len) * bend,
        cy = (a.y + b.y) / 2 + (dx / len) * bend;
      if (e.source === e.target) {
        path = `M ${a.x - 20} ${a.y - 14} C ${a.x - 90} ${a.y - 110} ${a.x + 90} ${a.y - 110} ${a.x + 20} ${a.y - 14}`;
        cx = a.x;
        cy = a.y - 95;
      } else path = `M ${sx} ${sy} Q ${cx} ${cy} ${tx} ${ty}`;
      const g = svg("g", {
        class:
          "edge-group" +
          (e.removed ? " removed" : "") +
          (e.cls ? " " + e.cls : "") +
          (selection?.type === "edge" && selection.id === e.id
            ? " selected"
            : ""),
        tabindex: 0,
        role: "button",
        "aria-label": `${e.label || `${e.id + 1}. ${action(e.technique_id)}`}: ${label(e.source)} → ${label(e.target)}`,
      });
      g.append(
        svg("path", { d: path, class: "edge-hit" }),
        svg("path", { d: path, class: "edge-line" }),
      );
      const at = e.labelAt ?? 0.5;
      const mx = e.source === e.target ? cx : a.x + dx * at - ((dy / len) * bend) / 2,
        my = e.source === e.target ? cy : a.y + dy * at + ((dx / len) * bend) / 2;
      const stop = e.removed ? "×" : (e.step ?? (mode === "paths" ? e.id + 1 : null));
      // Beside a steep line a label stays readable, on the side the line bends towards.
      // Above a flat line it clears the stop. A middle line among parallels moves up a row.
      const steep = Math.abs(dy) > Math.abs(dx);
      const gap = stop === null ? 8 : 18;
      const lean = -(dy / len) * bend;
      const parallel = pairCount.get(key) > 1 && bend === 0 ? -26 : 0;
      const t = svg("text", {
        x: steep ? mx + (lean < 0 ? -gap : gap) : mx,
        y: steep ? my + 4 + parallel : my - (stop === null ? 12 : 21) + parallel,
        class: "edge-label" + (steep ? (lean < 0 ? " before" : " beside") : ""),
      });
      t.textContent = e.label || action(e.technique_id);
      g.append(t);
      if (stop !== null) {
        const number = svg("text", { x: mx, y: my, class: "step-num" });
        number.textContent = stop;
        g.append(svg("circle", { cx: mx, cy: my, r: 11, class: "step-dot" }), number);
      }
      g.onclick = () => selectEdge(e.id);
      g.onkeydown = (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          selectEdge(e.id);
        }
      };
      $("edges").append(g);
    }
    for (const id of ids) {
      const p = positions[id],
        k = view.labels?.[id]?.kind || "Object",
        kind =
          k === "Group"
            ? "group"
            : k === "Computer"
              ? "host"
              : k === "User"
                ? "user"
                : "object";
      const g = svg("g", {
        class:
          "node " +
          kind +
          (view.labels?.[id]?.cls ? " " + view.labels[id].cls : "") +
          (selection?.type === "node" && selection.id === id
            ? " selected"
            : ""),
        transform: `translate(${p.x},${p.y})`,
        tabindex: 0,
        role: "button",
        "aria-label": label(id),
      });
      g.append(
        k === "Group"
          ? svg("polygon", { points: "-13,-25 13,-25 27,0 13,25 -13,25 -27,0", class: "outer" })
          : k === "Computer"
            ? svg("rect", { x: -23, y: -23, width: 46, height: 46, rx: 6, class: "outer" })
            : k === "User"
              ? svg("circle", { r: 25, class: "outer" })
              : svg("polygon", { points: "0,-27 27,0 0,27 -27,0", class: "outer" }),
        svg("use", {
          href:
            k === "Group"
              ? "#i-group"
              : k === "Computer"
                ? "#i-computer"
                : k === "User"
                  ? "#i-user"
                  : "#i-object",
          x: -13,
          y: -13,
          width: 26,
          height: 26,
        }),
      );
      const lab = svg("text", { class: "node-label", y: 44 });
      const short = label(id);
      lab.textContent = short.length > 25 ? short.slice(0, 23) + "…" : short;
      const title = svg("title");
      title.textContent = id;
      g.append(title, lab);
      if (id === view.source || id === view.target) {
        const role = svg("text", { y: 60, class: "node-role" });
        role.textContent = id === view.source ? "Xuất phát" : "Đích";
        g.append(role);
      }
      g.onclick = () => {
        // Drawing replaces this element, so a browser double click would never reach it.
        const repeated =
          mode === "workspace" &&
          selection?.type === "node" &&
          selection.id === id &&
          performance.now() - lastNodeClick < 400;
        lastNodeClick = performance.now();
        selection = { type: "node", id };
        draw();
        details();
        if (repeated) host.expand(id);
      };
      g.onkeydown = (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          g.onclick();
        }
      };
      g.onpointerdown = (ev) => {
        if (ev.button !== 0) return;
        ev.stopPropagation();
        const start = point(ev),
          old = { ...p };
        let moved = false;
        g.setPointerCapture(ev.pointerId);
        g.onpointermove = (e) => {
          const q = point(e);
          nodePositions[id] = {
            x: Math.max(40, old.x + (q.x - start.x) / zoom),
            y: Math.max(60, old.y + (q.y - start.y) / zoom),
          };
          moved = true;
        };
        g.onpointerup = () => {
          g.onpointermove = null;
          if (moved) draw();
        };
      };
      $("nodes").append(g);
    }
    transform();
  }
  function point(ev) {
    const p = $("graph").createSVGPoint();
    p.x = ev.clientX;
    p.y = ev.clientY;
    return p.matrixTransform($("graph").getScreenCTM().inverse());
  }
  function transform() {
    $("viewport").setAttribute(
      "transform",
      `translate(${pan.x},${pan.y}) scale(${zoom})`,
    );
  }
  function selectEdge(id) {
    selection = { type: "edge", id };
    draw();
    details();
  }
  function details() {
    if (mode === "workspace") return host.details(selection);
    const box = $("details");
    box.replaceChildren();
    if (mode === "remediation") {
      const c = currentCase(),
        q = currentQuery();
      box.append(
        el("h2", "", caseTitle(c)),
        el("p", "detail-subtitle", strategy(q.strategy) + " → " + q.goal),
      );
      fact(
        box,
        "Trước",
        M.outcome(q.before).label + ", C " + (q.before.C ?? empty),
      );
      fact(box, "Sau", M.outcome(q.after).label + ", C " + (q.after.C ?? empty));
      if (!q.after.reached && M.limitation(q.after)) note(box, M.limitation(q.after));
      fact(box, "Giả định", view.scenario || "Chưa có thông tin");
      if (selection?.type === "edge") {
        const e = c.removed_edges[selection.id];
        fact(box, "Quan hệ", e.kind);
        fact(box, "Nguồn", label(e.source));
        fact(box, "Đích", label(e.target));
      } else if (selection?.type === "node")
        fact(box, "ID đối tượng", selection.id);
      box.append(el("h3", "", "Bản ghi đã bỏ"));
      for (const [k, v] of Object.entries(c.removed_observations || {}))
        fact(box, k, v);
      return;
    }
    const p = currentProgram();
    if (selection?.type === "node") {
      box.append(
        el("h2", "", label(selection.id)),
        el(
          "p",
          "detail-subtitle",
          view.labels?.[selection.id]?.kind || "Đối tượng",
        ),
      );
      fact(box, "Mã đối tượng", selection.id);
      box.append(el("h3", "", "Các bước liên quan"));
      p?.steps.forEach((s, i) => {
        if ([s.actor, s.source, s.target].includes(selection.id))
          box.append(button("", () => selectEdge(i), "step-button"));
      });
      const buttons = box.querySelectorAll(".step-button");
      let j = 0;
      p?.steps.forEach((s, i) => {
        if ([s.actor, s.source, s.target].includes(selection.id)) {
          buttons[j++].append(
            el("span", "", i + 1),
            el("div", "", action(s.technique_id)),
          );
        }
      });
      return;
    }
    if (selection?.type === "edge") {
      const s = p.steps[selection.id];
      box.append(
        el("span", "tag", "Bước " + (selection.id + 1)),
        el("h2", "", action(s.technique_id)),
      );
      fact(box, "Người thực hiện", label(s.actor));
      fact(box, "Quyền từ", label(s.source));
      fact(box, "Tác động lên", label(s.target));
      if (s.assumptions?.length) {
        box.append(el("h3", "", "Giả định của bước"));
        s.assumptions.forEach((f) => note(box, factText(f)));
      } else if (s.assumptionsComplete !== true)
        note(box, "Tệp không ghi giả định của bước này.");
      return;
    }
    box.append(
      el("h2", "", p ? "Đường " + (index + 1) : "Chưa có đường"),
    );
    const hero = el("div", "cost-hero");
    hero.append(
      el("span", "", view.minimum ? "C nhỏ nhất" : "C tốt nhất đã tìm"),
      el("strong", "", p?.C ?? empty),
    );
    box.append(hero);
    if (p) {
      box.append(el("h3", "", "C gồm những việc"));
      if (!p.ledger?.length) note(box, "Tệp không có sổ công việc.");
      for (const unit of p.ledger || []) {
        const row = el("div", "ledger-row");
        row.append(
          el(
            "span",
            "",
            action(unit.technique || unit.technique_id || "Công việc"),
          ),
          el("b", "", M.cost(unit.computed_cost ?? unit.cost) ?? empty),
        );
        box.append(row);
      }
      const assumptions = p.assumptions || [];
      const det = el("details");
      const summary = el(
        "summary",
        "note",
        p.assumptionsComplete
          ? "Giả định chương trình (" + assumptions.length + ")"
          : "Giả định chương trình, chưa đầy đủ (đã ghi " +
              assumptions.length +
              ")",
      );
      det.append(summary);
      assumptions.forEach((f) =>
        note(det, factText(f)),
      );
      box.append(det);
    }
  }
  function showError(e) {
    $("error").textContent = e.message || String(e);
    $("error").hidden = false;
  }
  $("error").onclick = () => {
    $("error").hidden = true;
  };
  $("open-file").onclick = () => $("file").click();
  $("file").onchange = async (ev) => {
    const f = ev.target.files[0];
    if (!f) return;
    try {
      if (f.size > 128 * 1024 * 1024)
        throw Error("File vượt 128 MB. Hãy dùng gói kết quả nhỏ hơn.");
      const data = JSON.parse(await f.text());
      load(data, true);
      $("error").hidden = true;
    } catch (e) {
      showError(
        e instanceof SyntaxError
          ? new Error("JSON không hợp lệ. Hãy kiểm tra cú pháp hoặc xuất lại file kết quả.")
          : e,
      );
    } finally {
      $("file").value = "";
    }
  };
  $("paths-mode").onclick = () => {
    selection = null;
    if (custom?.mode === "paths") load(custom.input);
    else load(NEO_DEMOS.paths);
  };
  $("remediation-mode").onclick = () => {
    selection = null;
    if (custom?.mode === "remediation") load(custom.input);
    else load(NEO_DEMOS.remediation);
  };
  $("survey-mode").onclick = () => {
    if (custom?.mode === "survey") load(custom.input);
    else load(NEO_DEMOS.survey);
  };
  $("reset-demo").onclick = () => {
    custom = null;
    load(
      mode === "paths"
        ? NEO_DEMOS.paths
        : mode === "survey"
          ? NEO_DEMOS.survey
          : NEO_DEMOS.remediation,
    );
  };
  $("before").onclick = () => {
    phase = "before";
    render();
  };
  $("after").onclick = () => {
    phase = "after";
    render();
  };
  $("clear-selection").onclick = () => {
    if (mode === "survey") {
      index = 0;
      render();
      return;
    }
    selection = null;
    draw();
    details();
  };
  $("zoom-in").onclick = () => {
    zoom = Math.min(2.5, zoom * 1.2);
    transform();
  };
  $("zoom-out").onclick = () => {
    zoom = Math.max(0.4, zoom / 1.2);
    transform();
  };
  $("fit").onclick = () => {
    zoom = 1;
    pan = { x: 0, y: 0 };
    nodePositions = Object.create(null);
    draw();
  };
  $("graph").onpointerdown = (ev) => {
    if (ev.button !== 0 || ev.target.closest(".node,.edge-group")) return;
    const start = point(ev),
      old = { ...pan };
    $("graph").setPointerCapture(ev.pointerId);
    $("graph").onpointermove = (e) => {
      const q = point(e);
      pan = { x: old.x + q.x - start.x, y: old.y + q.y - start.y };
      transform();
    };
    $("graph").onpointerup = () => {
      $("graph").onpointermove = null;
    };
  };
  const root = document.documentElement;
  const isDark = () =>
    root.dataset.theme
      ? root.dataset.theme === "dark"
      : window.matchMedia?.("(prefers-color-scheme: dark)").matches === true;
  const themeLabel = () => {
    $("theme").textContent = isDark() ? "Nền sáng" : "Nền tối";
  };
  // A per-viewer convenience: blocked storage must not break the page.
  try {
    const saved = localStorage.getItem("neo-viewer-theme");
    if (saved === "light" || saved === "dark") root.dataset.theme = saved;
  } catch {}
  $("theme").onclick = () => {
    root.dataset.theme = isDark() ? "light" : "dark";
    try {
      localStorage.setItem("neo-viewer-theme", root.dataset.theme);
    } catch {}
    themeLabel();
  };
  themeLabel();
  load(NEO_DEMOS.paths);
  // The local app's workspace screen shares this canvas, its drawing and its helpers.
  globalThis.NeoViewer = {
    el,
    button,
    fact,
    note,
    metrics,
    pill,
    action,
    factText,
    attach(next) {
      host = next;
    },
    show(nextView) {
      view = nextView;
      mode = "workspace";
      fillDataset();
      render();
    },
    select(next) {
      selection = next;
    },
    phase: () => phase,
    setPhase(next) {
      phase = next;
    },
    resetCanvas() {
      selection = null;
      nodePositions = Object.create(null);
      zoom = 1;
      pan = { x: 0, y: 0 };
    },
    showError,
  };
})();
