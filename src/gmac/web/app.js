"use strict";
// All API data is rendered with textContent / createTextNode only, never as markup.

const $ = (id) => document.getElementById(id);
const state = { tab: "repos", rows: { repos: [], pulls: [] }, loadSeq: 0 };

function el(tag, props, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === "text") n.textContent = v;
    else if (k === "class") n.className = v;
    else n.setAttribute(k, v);
  }
  for (const kid of kids) if (kid) n.append(kid);
  return n;
}

function safeUrl(u) {
  try {
    const p = new URL(u);
    return p.protocol === "https:" || p.protocol === "http:" ? p.href : null;
  } catch (e) {
    return null;
  }
}

function link(url, label) {
  const href = safeUrl(url);
  if (!href) return el("span", { text: url || "" });
  return el("a", { href, target: "_blank", rel: "noopener noreferrer", text: label || url });
}

async function api(path) {
  let r;
  try {
    r = await fetch(path, { headers: { Accept: "application/json" } });
  } catch (e) {
    throw new Error("cannot reach the GMAC server");
  }
  let data = null;
  try {
    data = await r.json();
  } catch (e) {
    /* non-JSON body */
  }
  if (!r.ok) throw new Error((data && data.error) || `HTTP ${r.status}`);
  return data;
}

function date(s) {
  return s ? s.slice(0, 10) : "";
}

function setStatus(msg, isError) {
  const s = $("status");
  s.textContent = msg;
  s.className = isError ? "error" : "";
}

const COLUMNS = {
  repos: [
    ["Repo", (r) => r.full_name + (r.private ? " (private)" : "") + (r.archived ? " (archived)" : "")],
    ["Lang", (r) => r.language || "", "hide-sm"],
    ["Stars", (r) => String(r.stars), "num"],
    ["Issues", (r) => String(r.open_issues), "num"],
    ["Pushed", (r) => date(r.pushed_at), "hide-sm"],
  ],
  pulls: [
    ["Repo", (p) => p.repo],
    ["#", (p) => String(p.number), "num"],
    ["Title", (p) => p.title + (p.draft ? " [draft]" : ""), "wrap"],
    ["Author", (p) => p.author, "hide-sm"],
    ["Updated", (p) => date(p.updated_at), "hide-sm"],
  ],
};

function activate(node, fn) {
  node.tabIndex = 0;
  node.addEventListener("click", fn);
  node.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fn();
    }
  });
}

function table(cols, rows, onPick) {
  const head = el("tr", {}, ...cols.map((c) => el("th", { scope: "col", text: c[0], class: c[2] || "" })));
  const body = el("tbody");
  for (const row of rows) {
    const tr = el("tr", {}, ...cols.map((c) => el("td", { text: c[1](row), class: c[2] || "" })));
    activate(tr, () => onPick(row));
    body.append(tr);
  }
  return el("table", {}, el("thead", {}, head), body);
}

function render() {
  const q = $("filter").value.trim().toLowerCase();
  const cols = COLUMNS[state.tab];
  const all = state.rows[state.tab];
  const rows = q ? all.filter((r) => cols.some((c) => c[1](r).toLowerCase().includes(q))) : all;
  const panel = $("panel");
  panel.replaceChildren(table(cols, rows, state.tab === "repos" ? openRepo : openRepoPulls));
  setStatus(`${rows.length} of ${all.length} ${state.tab === "repos" ? "repos" : "open pull requests"}`);
}

async function load() {
  const seq = ++state.loadSeq;
  const tab = state.tab;
  const params = new URLSearchParams();
  if ($("source").value) params.set("source", $("source").value);
  if (tab === "repos" && $("archived").checked) params.set("archived", "true");
  const qs = params.toString() ? `?${params}` : "";
  $("panel").replaceChildren();
  setStatus("Loading...");
  try {
    const data = await api(`/api/${tab}${qs}`);
    if (seq !== state.loadSeq) return;
    state.rows[tab] = data;
    render();
  } catch (e) {
    if (seq !== state.loadSeq) return;
    setStatus(`Error: ${e.message}`, true);
  }
}

async function loadSources() {
  try {
    const sources = await api("/api/sources");
    for (const s of sources) $("source").append(el("option", { value: s.name, text: `${s.name} (${s.kind})` }));
  } catch (e) {
    setStatus(`Error: ${e.message}`, true);
  }
}

function selectTab(tab) {
  state.tab = tab;
  for (const t of ["repos", "pulls"]) $(`tab-${t}`).setAttribute("aria-selected", String(t === tab));
  $("archived-label").hidden = tab !== "repos";
  load();
}

// ---- dialog with a small view stack (Back pops, Esc closes) ----
const stack = [];

function showTop() {
  const top = stack[stack.length - 1];
  $("dlg-title").textContent = top.title;
  $("dlg-back").hidden = stack.length < 2;
  $("dlg-body").replaceChildren(top.node);
  $("dlg-body").scrollTop = 0;
}

function push(title, node) {
  stack.push({ title, node });
  if (!$("dlg").open) $("dlg").showModal();
  showTop();
}

function back() {
  if (stack.length > 1) {
    stack.pop();
    showTop();
  } else {
    $("dlg").close();
  }
}

function placeholder(text, isError) {
  return el("p", { text, class: isError ? "error" : "" });
}

// Push a view whose content is fetched; the node is filled in place when ready.
function pushLoaded(title, path, build) {
  const node = el("div", {}, placeholder("Loading..."));
  push(title, node);
  api(path).then(
    (data) => node.replaceChildren(build(data)),
    (e) => node.replaceChildren(placeholder(`Error: ${e.message}`, true)),
  );
}

function facts(pairs) {
  const dl = el("dl");
  for (const [k, v] of pairs) {
    dl.append(el("dt", { text: k }), el("dd", {}, typeof v === "string" ? document.createTextNode(v) : v));
  }
  return dl;
}

function repoPath(full) {
  return full.split("/").map(encodeURIComponent).join("/");
}

function openRepo(repo) {
  const node = el("div");
  node.append(
    facts([
      ["Name", repo.full_name],
      ["Visibility", repo.private ? "private" : "public"],
      ["Archived", repo.archived ? "yes" : "no"],
      ["Fork", repo.fork ? "yes" : "no"],
      ["Language", repo.language || "none"],
      ["Stars", String(repo.stars)],
      ["Open issues", String(repo.open_issues)],
      ["Last push", repo.pushed_at || "never"],
      ["GitHub", link(repo.url)],
    ]),
  );
  const localBox = el("div", {}, placeholder("Looking for local clones..."));
  node.append(el("h3", { class: "sub", text: "On this machine" }), localBox);
  const issuesBtn = el("button", { type: "button", text: "Issues" });
  issuesBtn.addEventListener("click", () => openIssues(repo.full_name));
  node.append(el("p", {}, issuesBtn));
  push(repo.full_name, node);
  api(`/api/repos/${repoPath(repo.full_name)}/local`).then(
    (info) => localBox.replaceChildren(renderLocal(info)),
    (e) => localBox.replaceChildren(placeholder(`Error: ${e.message}`, true)),
  );
}

function renderLocal(info) {
  if (info.error) return placeholder(info.error, true);
  if (!info.clones.length) return placeholder("No local clone found.");
  const pairs = [["Directory", info.clones.join("\n")], ["Remote", info.remote || "none"]];
  const st = info.status;
  if (st) {
    pairs.push(
      ["Branch", st.branch],
      ["Ahead / behind", `${st.ahead} / ${st.behind}`],
      ["Changes", st.clean ? "clean" : `${st.staged} staged, ${st.modified} modified, ${st.untracked} untracked`],
    );
  }
  return facts(pairs);
}

function openIssues(full) {
  pushLoaded(`Issues: ${full}`, `/api/repos/${repoPath(full)}/issues`, (issues) => {
    if (!issues.length) return placeholder("No open issues.");
    const cols = [
      ["#", (i) => String(i.number), "num"],
      ["Title", (i) => i.title, "wrap"],
      ["Author", (i) => i.author, "hide-sm"],
      ["Updated", (i) => date(i.updated_at), "hide-sm"],
    ];
    return table(cols, issues, openIssue);
  });
}

function openIssue(issue) {
  const node = el("div");
  const labels = el("span");
  for (const l of issue.labels) labels.append(el("span", { class: "tag", text: l }));
  node.append(
    facts([
      ["Repo", issue.repo],
      ["Author", issue.author],
      ["Comments", String(issue.comments)],
      ["Updated", issue.updated_at || ""],
      ["Labels", issue.labels.length ? labels : "none"],
      ["GitHub", link(issue.url)],
    ]),
    el("pre", { text: issue.body || "(no description)" }),
  );
  push(`#${issue.number} ${issue.title}`, node);
}

function openRepoPulls(pr) {
  pushLoaded(`Open PRs: ${pr.repo}`, `/api/repos/${repoPath(pr.repo)}/pulls`, (pulls) => {
    if (!pulls.length) return placeholder("No open pull requests.");
    const cols = [
      ["#", (p) => String(p.number), "num"],
      ["Title", (p) => p.title + (p.draft ? " [draft]" : ""), "wrap"],
      ["Author", (p) => p.author, "hide-sm"],
      ["Updated", (p) => date(p.updated_at), "hide-sm"],
    ];
    return table(cols, pulls, openPull);
  });
}

function openPull(p) {
  const node = el("div");
  node.append(
    facts([
      ["Repo", p.repo],
      ["Author", p.author],
      ["Branches", `${p.head} -> ${p.base}`],
      ["Draft", p.draft ? "yes" : "no"],
      ["Changes", `+${p.additions} -${p.deletions} in ${p.changed_files} files, ${p.commits} commits`],
      ["Comments", String(p.comments)],
      ["Mergeable", p.mergeable_state || "unknown"],
      ["Created", p.created_at || ""],
      ["Updated", p.updated_at || ""],
      ["GitHub", link(p.url)],
    ]),
    el("pre", { text: p.body || "(no description)" }),
  );
  push(`#${p.number} ${p.title}`, node);
}

$("dlg-back").addEventListener("click", back);
$("dlg-close").addEventListener("click", () => $("dlg").close());
$("dlg").addEventListener("close", () => {
  stack.length = 0;
});
$("tab-repos").addEventListener("click", () => selectTab("repos"));
$("tab-pulls").addEventListener("click", () => selectTab("pulls"));
$("filter").addEventListener("input", render);
$("source").addEventListener("change", load);
$("archived").addEventListener("change", load);
$("refresh").addEventListener("click", load);

loadSources();
selectTab("repos");
