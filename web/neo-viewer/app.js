/* Local presentation only: no network requests, execution or persistence. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id),
    M = NeoViewModel;
  const NS = "http://www.w3.org/2000/svg";
  const names = {
    propagate_group_entitlement: "MemberOf",
    scenario_reset_password: "Reset password",
    genericall_reset_password: "Reset password",
    reset_target_password: "Reset password",
    acquire_reset_identity: "Use identity",
    genericall_add_member: "Add member",
    genericall_grant_write_dacl: "Grant WriteDacl",
    grant_new_object_right: "Grant rights",
    obtain_admin_execution_on_host: "Admin execution",
    scenario_winrm_admin: "WinRM admin",
    open_winrm_remote_session: "WinRM session",
    use_session_identity: "Session identity",
    "Dùng quyền thành viên nhóm": "MemberOf",
    "Reset mật khẩu": "Reset password",
    "Dùng danh tính vừa reset": "Use identity",
    "Sửa DACL để cấp quyền": "Grant rights",
    "Thêm thành viên nhóm": "Add member",
    "Cấp quyền sửa DACL": "Grant WriteDacl",
  };
  const caseNames = {
    "rodc-membership": "RODCMANAGER · Administrators",
    "extca-session": "EXTCA01 · Session BM",
    "bm-da-membership": "BM · Domain Admins",
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
    custom = null;
  const label = (id) =>
    view.labels?.[id]?.label ||
    id?.replace(/^.*-(\d+)$/, "SID …$1") ||
    "Chưa khai báo";
  const action = (id) => names[id] || id;
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
    view = next;
    mode = next.kind === "remediation" ? "remediation" : "paths";
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
    if (imported) custom = { input, mode };
    fillDataset();
    render();
  }
  function fillDataset() {
    $("dataset").textContent = view.title;
    $("paths-mode").classList.toggle("active", mode === "paths");
    $("remediation-mode").classList.toggle("active", mode === "remediation");
    $("input-origin").textContent =
      custom && custom.mode === mode
        ? "File JSON trên máy · không upload"
        : "Playback từ evidence đã công bố";
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
    if (mode === "paths") renderPath();
    else renderRemediation();
    draw();
    details();
  }
  function sourceBox(source, target) {
    const box = el("div", "source-box");
    box.append(
      el("small", "", "NGUỒN"),
      el("p", "", source),
      el("small", "", "ĐÍCH"),
      el("p", "", target),
    );
    $("source-card").append(box);
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
    b.append(
      el("span", "rank", String(i + 1).padStart(2, "0")),
      copy,
      el("span", "choice-cost", costValue),
    );
    $("choices").append(b);
  }
  function pill(label, tone = "blue") {
    $("status").textContent = label;
    $("status").className = "status-pill " + tone;
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
    $("eyebrow").textContent = view.title.toUpperCase();
    $("heading").textContent = "Đường tới " + label(view.target);
    sourceBox(label(view.source), label(view.target));
    $("list-title").textContent = "CÁC CHƯƠNG TRÌNH";
    view.programs.forEach((p, i) =>
      choice(
        i,
        "Đường " + (i + 1),
        p.steps.length +
          " bước · " +
          (p.C == null ? "chưa chấm C" : "C theo ledger"),
        p.C == null ? "—" : "C " + p.C,
      ),
    );
    const p = currentProgram();
    pill(
      p
        ? view.minimum
          ? "Minimum trong scope"
          : "Best-found"
        : view.noPath
          ? "No-path trong scope"
          : "Chưa kết luận",
      p ? "blue" : view.noPath ? "green" : "amber",
    );
    $("graph-caption").textContent = "Chương trình hành động · source → target";
    metrics([
      ["Công sức C", p?.C ?? "Chưa chấm", ""],
      ["Bước trong chương trình", p?.steps.length ?? 0, ""],
      [
        "Lần mở rộng",
        view.expansions ?? "—",
        view.budget?.max_expansions ? "/ " + view.budget.max_expansions : "",
      ],
    ]);
    $("scope-note").textContent =
      (view.truncated ? "Giới hạn: " + (view.reason || "budget") + ". " : "") +
      "C là điểm công sức theo scenario. Thứ hạng áp dụng trong tập đã tìm được.";
    if (!p || !p.steps.length) {
      $("empty").hidden = false;
      $("empty").textContent = p
        ? "Mục tiêu đã có trong trạng thái đầu; không cần hành động mới."
        : view.noPath
          ? "Không có đường trong scope đã kiểm tra."
          : "Chưa có witness để vẽ. Không đồng nghĩa an toàn.";
    }
  }
  function renderRemediation() {
    const c = currentCase(),
      q = currentQuery(),
      s = q[phase],
      out = M.outcome(s);
    $("eyebrow").textContent = "WRAITH / REMEDIATION";
    $("heading").textContent = "Kiểm tra sau can thiệp";
    pill(out.label, out.tone);
    sourceBox(
      "Foothold mới · không giữ credential cũ",
      "Domain / Enterprise Admins",
    );
    $("list-title").textContent = "CAN THIỆP ĐÃ KIỂM CHỨNG";
    view.cases.forEach((c, i) =>
      choice(
        i,
        caseNames[c.case] || c.case,
        c.removed_edges.length + " quan hệ bị gỡ",
        "",
      ),
    );
    const select = el("select");
    select.setAttribute("aria-label", "Strategy và mục tiêu");
    c.queries.forEach((q, i) => {
      const o = el("option", "", q.strategy + " → " + q.goal);
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
    $("graph-caption").textContent =
      phase === "before"
        ? "Quan hệ được chọn để can thiệp"
        : "Quan hệ đã gỡ · không phải toàn bộ witness";
    metrics([
      ["C trước", M.cost(q.before.C) ?? "Chưa chấm", ""],
      [
        "C sau",
        M.cost(q.after.C) ??
          (q.after.no_path_proven ? "Không có witness" : "Chưa xác định"),
        "",
      ],
      ["Tìm lại", M.outcome(q.after).label, ""],
    ]);
    $("scope-note").textContent =
      "Playback kết quả đã chạy. Graph chỉ vẽ các quan hệ can thiệp được summary công bố; không có witness graph của bypass trong file này.";
  }
  function graphData() {
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
    const { edges } = graphData();
    const ids = [...new Set(edges.flatMap((e) => [e.source, e.target]))];
    if (!ids.length && mode === "paths" && currentProgram())
      ids.push(view.source);
    const positions = Object.create(null);
    ids.forEach((id, i) => {
      const configured = view.labels?.[id];
      positions[id] =
        nodePositions[id] ||
        (configured?.x !== undefined
          ? { x: configured.x, y: configured.y }
          : mode === "remediation"
            ? { x: 220 + (i % 3) * 370, y: 240 + Math.floor(i / 3) * 180 }
            : { x: 130 + (i % 4) * 300, y: 210 + Math.floor(i / 4) * 200 });
    });
    let maxY = 660;
    for (const p of Object.values(positions)) maxY = Math.max(maxY, p.y + 100);
    $("graph").setAttribute("viewBox", "0 0 1200 " + maxY);
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
      const bend = (n - (pairCount.get(key) - 1) / 2) * 65,
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
          (selection?.type === "edge" && selection.id === e.id
            ? " selected"
            : ""),
        tabindex: 0,
        role: "button",
        "aria-label": `${e.id + 1}. ${action(e.technique_id)}: ${label(e.source)} → ${label(e.target)}`,
      });
      g.append(
        svg("path", { d: path, class: "edge-hit" }),
        svg("path", { d: path, class: "edge-line" }),
      );
      const t = svg("text", {
        x: (a.x + b.x) / 2 - ((dy / len) * bend) / 2,
        y: (a.y + b.y) / 2 + ((dx / len) * bend) / 2 - 10,
        class: "edge-label",
      });
      t.textContent = `${mode === "paths" ? e.id + 1 + ". " : ""}${action(e.technique_id)}`;
      g.append(t);
      if (e.source === e.target) {
        t.setAttribute("x", cx);
        t.setAttribute("y", cy);
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
          (selection?.type === "node" && selection.id === id
            ? " selected"
            : ""),
        transform: `translate(${p.x},${p.y})`,
        tabindex: 0,
        role: "button",
        "aria-label": label(id),
      });
      g.append(svg("circle", { r: 26, class: "outer" }));
      const icon = svg("text", { class: "node-icon", y: 0 });
      icon.textContent =
        k === "Group" ? "G" : k === "Computer" ? "▣" : k === "User" ? "U" : "◇";
      g.append(icon);
      const lab = svg("text", { class: "node-label", y: 49 });
      const short = label(id);
      lab.textContent = short.length > 25 ? short.slice(0, 23) + "…" : short;
      const title = svg("title");
      title.textContent = id;
      g.append(title, lab);
      if (id === view.source || id === view.target) {
        const role = svg("text", { y: -42, class: "node-role" });
        role.textContent = id === view.source ? "FOOTHOLD" : "ĐÍCH";
        g.append(role);
      }
      g.onclick = () => {
        selection = { type: "node", id };
        draw();
        details();
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
    const box = $("details");
    box.replaceChildren();
    if (mode === "remediation") {
      const c = currentCase(),
        q = currentQuery();
      box.append(
        el("h2", "", caseNames[c.case] || c.case),
        el("p", "detail-subtitle", q.strategy + " → " + q.goal),
      );
      fact(
        box,
        "Trước",
        M.outcome(q.before).label + " · C " + (q.before.C ?? "—"),
      );
      fact(box, "Sau", M.outcome(q.after).label + " · C " + (q.after.C ?? "—"));
      fact(box, "Lần mở rộng sau", q.after.expansions);
      fact(box, "Giới hạn sau", q.after.truncation_reason || "Không truncated");
      if (selection?.type === "edge") {
        const e = c.removed_edges[selection.id];
        fact(box, "Quan hệ", e.kind);
        fact(box, "Nguồn", e.source);
        fact(box, "Đích", e.target);
      } else if (selection?.type === "node")
        fact(box, "ID đối tượng", selection.id);
      box.append(el("h3", "", "OBSERVATION ĐÃ LOẠI"));
      for (const [k, v] of Object.entries(c.removed_observations || {}))
        fact(box, k, v);
      note(
        box,
        "Mỗi lần tìm lại bắt đầu từ foothold mới trong scenario đã công bố. Cắt witness cũ không tự chứng minh ngắt mọi đường.",
      );
      note(
        box,
        q.after.no_path_proven
          ? "No-path được engine chứng minh trong scope local-admin-only này."
          : "C sau là best-found nếu có witness; hết budget vẫn là chưa kết luận.",
      );
      return;
    }
    const p = currentProgram();
    if (selection?.type === "node") {
      box.append(
        el("h2", "", label(selection.id)),
        el(
          "p",
          "detail-subtitle",
          view.labels?.[selection.id]?.kind ||
            "Đối tượng · chưa có type trong output",
        ),
      );
      fact(box, "ID / nhãn gốc", selection.id);
      box.append(el("h3", "", "THAO TÁC LIÊN QUAN"));
      p?.steps.forEach((s, i) => {
        if ([s.actor, s.source, s.target].includes(selection.id))
          box.append(button("", () => selectEdge(i), "step-button"));
      });
      const buttons = box.querySelectorAll(".step-button");
      let j = 0;
      p?.steps.forEach((s, i) => {
        if ([s.actor, s.source, s.target].includes(selection.id)) {
          buttons[j++].append(
            el("span", "", String(i + 1).padStart(2, "0")),
            el("div", "", action(s.technique_id)),
          );
        }
      });
      return;
    }
    if (selection?.type === "edge") {
      const s = p.steps[selection.id];
      box.append(
        el("span", "tag", "BƯỚC " + (selection.id + 1)),
        el("h2", "", action(s.technique_id)),
      );
      fact(box, "Actor", label(s.actor));
      fact(box, "Nguồn quyền / source", label(s.source));
      fact(box, "Đích thao tác", label(s.target));
      fact(box, "Technique", s.technique_id);
      note(
        box,
        "Mũi tên biểu diễn source → target của request. Actor có thể khác source; đây không phải một cạnh BloodHound nguyên bản.",
      );
      if (s.assumptions?.length) {
        box.append(el("h3", "", "GIẢ ĐỊNH CỦA BƯỚC"));
        s.assumptions.forEach((f) =>
          note(box, typeof f === "string" ? f : JSON.stringify(f)),
        );
      } else
        note(
          box,
          "Playback này giữ giả định ở cấp chương trình; không suy ra giả định riêng cho bước.",
        );
      return;
    }
    box.append(
      el("h2", "", p ? "Tổng quan chương trình" : "Kết quả tìm kiếm"),
      el(
        "p",
        "detail-subtitle",
        view.minimum
          ? "Minimum được engine báo trong scope"
          : "Thứ hạng trong tập đã tìm được",
      ),
    );
    const hero = el("div", "cost-hero");
    hero.append(
      el("span", "", "Công sức tương đối"),
      el("strong", "", p?.C ?? "—"),
    );
    box.append(hero);
    if (p) {
      box.append(el("h3", "", "THÀNH PHẦN C · LEDGER"));
      if (!p.ledger?.length)
        note(
          box,
          "Không có ledger trong file; không tự suy C từ tên hành động.",
        );
      for (const unit of p.ledger || []) {
        const row = el("div", "ledger-row");
        row.append(
          el(
            "span",
            "",
            action(unit.technique || unit.technique_id || "Work unit"),
          ),
          el("b", "", M.cost(unit.computed_cost ?? unit.cost) ?? "—"),
        );
        box.append(row);
      }
      note(
        box,
        "C=0 là mức sàn công sức, không có nghĩa không thao tác. Tổng được đọc từ kết quả, không tính lại trong UI.",
      );
      const assumptions = p.assumptions || [];
      const det = el("details");
      const summary = el(
        "summary",
        "note",
        "Giả định chương trình (" + assumptions.length + ")",
      );
      det.append(summary);
      assumptions.forEach((f) =>
        note(det, typeof f === "string" ? f : JSON.stringify(f)),
      );
      box.append(det);
    }
    box.append(el("h3", "", "NGUỒN KẾT QUẢ"));
    note(box, view.provenance || "File người dùng");
    if (view.notice) note(box, view.notice);
    fact(box, "Context xác thực", label(view.context));
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
      if (f.size > 25 * 1024 * 1024)
        throw Error("File vượt 25 MB. Hãy dùng output query riêng.");
      const data = JSON.parse(await f.text());
      load(data, true);
      $("error").hidden = true;
    } catch (e) {
      showError(e);
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
  $("reset-demo").onclick = () => {
    custom = null;
    load(mode === "paths" ? NEO_DEMOS.paths : NEO_DEMOS.remediation);
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
  load(NEO_DEMOS.paths);
})();
