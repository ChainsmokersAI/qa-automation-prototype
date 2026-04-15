"use strict";

const CATEGORIES = ["inputs", "context", "scenarios", "testcases", "simulations"];
const CATEGORY_PREFIX = {
  inputs: "inputs/",
  context: "context/",
  scenarios: "outputs/scenarios/",
  testcases: "outputs/testcases/",
  simulations: "outputs/simulations/",
};

const state = {
  expandedCat: null,
  treesByCat: {},
  loadedCats: new Set(),
  currentPath: null,
  expanded: new Set(),
  dirty: new Set(),
  initialLoad: new Set(),
};

const el = {
  content: document.getElementById("content"),
  breadcrumb: document.getElementById("breadcrumb"),
  dropzone: document.getElementById("dropzone"),
  fileInput: document.getElementById("file-input"),
  uploadStatus: document.getElementById("upload-status"),
  statusDot: document.getElementById("status-dot"),
};

function categoryOf(path) {
  for (const cat of CATEGORIES) {
    if (path === CATEGORY_PREFIX[cat].slice(0, -1) || path.startsWith(CATEGORY_PREFIX[cat])) {
      return cat;
    }
  }
  return null;
}

function catLi(cat) {
  return document.querySelector(`.cat[data-cat="${cat}"]`);
}

function catTreeUl(cat) {
  const li = catLi(cat);
  return li ? li.querySelector(".tree") : null;
}

function parseHash() {
  const hash = location.hash || "";
  if (!hash.startsWith("#/view")) return null;
  const qs = hash.split("?")[1] || "";
  const params = new URLSearchParams(qs);
  return {
    cat: params.get("cat"),
    path: params.get("path"),
    anchor: params.get("anchor"),
  };
}

function setHash(cat, path, anchor) {
  const params = new URLSearchParams();
  if (cat) params.set("cat", cat);
  if (path) params.set("path", path);
  if (anchor) params.set("anchor", anchor);
  const next = `#/view?${params.toString()}`;
  if (location.hash !== next) {
    location.hash = next;
  }
}

function setDirty(cat) {
  state.dirty.add(cat);
  const li = catLi(cat);
  if (li) li.classList.add("dirty");
}

function clearDirty(cat) {
  state.dirty.delete(cat);
  const li = catLi(cat);
  if (li) li.classList.remove("dirty");
}

async function loadTree(cat) {
  const ul = catTreeUl(cat);
  if (!ul) return;
  if (!state.loadedCats.has(cat)) {
    ul.innerHTML = '<li class="empty">로딩 중...</li>';
  }
  try {
    const res = await fetch(`/api/tree?category=${encodeURIComponent(cat)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const tree = await res.json();
    state.treesByCat[cat] = tree;
    state.loadedCats.add(cat);
    renderTreeFor(cat, tree);
  } catch (err) {
    ul.innerHTML = `<li class="empty">트리 로딩 실패: ${err.message}</li>`;
  }
}

function renderTreeFor(cat, tree) {
  const ul = catTreeUl(cat);
  if (!ul) return;
  ul.innerHTML = "";
  if (!tree || !tree.children || tree.children.length === 0) {
    ul.innerHTML = '<li class="empty">파일 없음</li>';
    return;
  }
  for (const child of tree.children) {
    ul.appendChild(renderNode(child));
  }
  highlightActive();
}

function renderNode(node) {
  const li = document.createElement("li");
  li.className = node.type;
  const row = document.createElement("div");
  row.className = "node";
  row.dataset.path = node.path;
  const icon = document.createElement("span");
  icon.className = "icon";
  const name = document.createElement("span");
  name.className = "name";
  name.textContent = node.name;
  row.appendChild(icon);
  row.appendChild(name);
  li.appendChild(row);
  if (node.type === "dir") {
    const ul = document.createElement("ul");
    for (const child of node.children || []) {
      ul.appendChild(renderNode(child));
    }
    li.appendChild(ul);
    if (state.expanded.has(node.path)) li.classList.add("open");
    row.addEventListener("click", (e) => {
      e.stopPropagation();
      li.classList.toggle("open");
      if (li.classList.contains("open")) {
        state.expanded.add(node.path);
      } else {
        state.expanded.delete(node.path);
      }
    });
  } else {
    row.addEventListener("click", (e) => {
      e.stopPropagation();
      const cat = categoryOf(node.path) || state.expandedCat;
      setHash(cat, node.path);
    });
  }
  return li;
}

function highlightActive() {
  document.querySelectorAll(".node.active").forEach((n) => n.classList.remove("active"));
  if (!state.currentPath) return;
  const node = document.querySelector(`.node[data-path="${cssEscape(state.currentPath)}"]`);
  if (node) {
    node.classList.add("active");
    let parent = node.parentElement;
    while (parent) {
      if (parent.tagName === "LI" && parent.classList.contains("dir")) {
        parent.classList.add("open");
        const dirRow = parent.querySelector(":scope > .node");
        if (dirRow && dirRow.dataset.path) state.expanded.add(dirRow.dataset.path);
      }
      parent = parent.parentElement;
    }
  }
}

function cssEscape(s) {
  return s.replace(/(["\\])/g, "\\$1");
}

async function loadContent(path, anchor) {
  state.currentPath = path;
  if (!path) {
    el.content.innerHTML = "";
    el.breadcrumb.innerHTML = '<span class="muted">왼쪽에서 파일을 선택하세요</span>';
    return;
  }
  el.breadcrumb.innerHTML = `<span class="title">${escapeHtml(path)}</span>`;
  el.content.innerHTML = '<div class="empty">로딩 중...</div>';
  try {
    const res = await fetch(`/api/render?path=${encodeURIComponent(path)}`);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status}: ${text}`);
    }
    const data = await res.json();
    el.content.innerHTML = data.html;
    el.content.scrollTop = 0;
    interceptInternalLinks();
    highlightActive();
    if (anchor) {
      requestAnimationFrame(() => openAnchorInContent(anchor));
    }
  } catch (err) {
    el.content.innerHTML = `<div class="error">렌더 실패: ${escapeHtml(err.message)}</div>`;
  }
}

function interceptInternalLinks() {
  el.content.querySelectorAll("a[href^='#/view']").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const href = a.getAttribute("href");
      if (href !== location.hash) {
        location.hash = href.slice(1);
      } else {
        applyRoute();
      }
    });
  });
  el.content.querySelectorAll("a[href^='#']").forEach((a) => {
    const href = a.getAttribute("href");
    if (!href || href.startsWith("#/")) return;
    a.addEventListener("click", (e) => {
      e.preventDefault();
      openAnchorInContent(href.slice(1));
    });
  });
}

function openAnchorInContent(id) {
  if (!id) return;
  let target = el.content.querySelector(`[id="${cssEscape(id)}"]`);
  if (!target) {
    target = el.content.querySelector(`[id="${cssEscape(id.toLowerCase())}"]`);
  }
  if (!target) {
    const m = id.match(/^([a-zA-Z]+-\d+)/);
    if (m) {
      target = el.content.querySelector(`[id="${cssEscape(m[1].toLowerCase())}"]`);
    }
  }
  if (!target) return;
  let parent = target;
  while (parent && parent !== el.content) {
    if (parent.tagName === "DETAILS") parent.open = true;
    parent = parent.parentElement;
  }
  target.scrollIntoView({ block: "start", behavior: "smooth" });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
  })[c]);
}

async function expandCategory(cat, opts = {}) {
  if (!CATEGORIES.includes(cat)) return;
  document.querySelectorAll(".cat.open").forEach((li) => {
    if (li.dataset.cat !== cat) li.classList.remove("open");
  });
  const li = catLi(cat);
  if (li) li.classList.add("open");
  state.expandedCat = cat;
  clearDirty(cat);
  if (opts.forceReload || !state.loadedCats.has(cat)) {
    await loadTree(cat);
  } else {
    renderTreeFor(cat, state.treesByCat[cat]);
  }
}

function collapseCategory(cat) {
  const li = catLi(cat);
  if (li) li.classList.remove("open");
  if (state.expandedCat === cat) state.expandedCat = null;
}

function onCatHeaderClick(cat) {
  clearDirty(cat);
  if (state.expandedCat === cat) {
    collapseCategory(cat);
  } else {
    expandCategory(cat);
  }
}

document.querySelectorAll(".cat .cat-header").forEach((header) => {
  const li = header.parentElement;
  const cat = li && li.dataset ? li.dataset.cat : null;
  if (!cat) return;
  header.addEventListener("click", () => onCatHeaderClick(cat));
});

function applyRoute() {
  const route = parseHash();
  if (route && route.path) {
    const cat = (route.cat && CATEGORIES.includes(route.cat)) ? route.cat : (categoryOf(route.path) || "inputs");
    if (state.expandedCat !== cat) {
      expandCategory(cat).then(() => loadContent(route.path, route.anchor));
    } else if (route.path !== state.currentPath) {
      loadContent(route.path, route.anchor);
    } else if (route.anchor) {
      openAnchorInContent(route.anchor);
    }
  } else if (route && route.cat && CATEGORIES.includes(route.cat)) {
    if (state.expandedCat !== route.cat) expandCategory(route.cat);
  }
}

window.addEventListener("hashchange", applyRoute);

function setupSSE() {
  const es = new EventSource("/api/events");
  es.addEventListener("hello", () => {
    el.statusDot.classList.add("live");
    el.statusDot.title = "라이브";
  });
  es.addEventListener("tree-changed", (e) => {
    let payload = {};
    try {
      payload = JSON.parse(e.data);
    } catch (_) {}
    const cat = payload.category;
    if (!cat || !CATEGORIES.includes(cat)) return;
    if (cat === state.expandedCat) {
      loadTree(cat);
    } else {
      if (state.initialLoad.has(cat)) {
        setDirty(cat);
      }
      state.loadedCats.delete(cat);
    }
    state.initialLoad.add(cat);
    if (payload.path && payload.path === state.currentPath) {
      loadContent(state.currentPath);
    }
  });
  es.onerror = () => {
    el.statusDot.classList.remove("live");
    el.statusDot.title = "연결 끊김 (재연결 중)";
  };
}

function setupUpload() {
  const dz = el.dropzone;
  if (!dz) return;
  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dz.classList.add("dragover");
    }),
  );
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (ev === "dragleave" && e.target !== dz) return;
      dz.classList.remove("dragover");
    }),
  );
  dz.addEventListener("drop", (e) => {
    if (e.dataTransfer && e.dataTransfer.files) {
      uploadFiles(e.dataTransfer.files);
    }
  });
  el.fileInput.addEventListener("change", (e) => {
    if (e.target.files) uploadFiles(e.target.files);
    e.target.value = "";
  });
}

async function uploadFiles(fileList) {
  if (!fileList || fileList.length === 0) return;
  const fd = new FormData();
  for (const f of fileList) fd.append("files", f, f.name);
  el.uploadStatus.textContent = `업로드 중... (${fileList.length}개)`;
  try {
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const renamedNote = data.renamed && data.renamed.length
      ? ` (${data.renamed.length}개 이름 변경)`
      : "";
    el.uploadStatus.textContent = `업로드 완료: ${data.saved.length}개${renamedNote}`;
    setTimeout(() => {
      if (el.uploadStatus.textContent.startsWith("업로드 완료")) {
        el.uploadStatus.textContent = "";
      }
    }, 4000);
  } catch (err) {
    el.uploadStatus.textContent = `업로드 실패: ${err.message}`;
  }
}

(async function init() {
  setupSSE();
  setupUpload();
  const route = parseHash();
  const startCat = (route && route.cat && CATEGORIES.includes(route.cat))
    ? route.cat
    : (route && route.path ? (categoryOf(route.path) || "inputs") : "inputs");
  await expandCategory(startCat);
  CATEGORIES.forEach((c) => state.initialLoad.add(c));
  if (route && route.path) {
    loadContent(route.path);
  }
})();
