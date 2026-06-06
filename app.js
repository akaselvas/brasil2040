/* ─── DATA ─────────────────────────────────────────── */
const CROPS = [
  { key: "Soja", label: "Soja", pct: "sojaPercent", area: "sojaAreaPlantada", r90: "SojaRisco90", r45: "SojaRPC45", r85: "SojaRPC85" },
  { key: "Milho", label: "Milho", pct: "milhoPercent", area: "milhoAreaPlantaada", r90: "MilhoRisco90", r45: "MilhoRPC45", r85: "MilhoRPC85" },
  { key: "Safrinha", label: "Safrinha", pct: "safrinhaPercent", area: "safrinhaAreaPlantada", r90: "SafrinhaRisco90", r45: "SafrinhaRPC45", r85: "SafrinhaRPC85" },
  { key: "Arroz", label: "Arroz", pct: "arrozPercent", area: "arrozAreaPlantada", r90: "ArrozRisco90", r45: "ArrozRPC45", r85: "ArrozRPC85" },
  { key: "Feijao", label: "Feijão Verão", pct: "feijaoPercent", area: "feijaoAreaPlantada", r90: "FeijaoRisco90", r45: "FeijaoRPC45", r85: "FeijaoRPC85" },
  { key: "Feijao2", label: "Feijão Inverno", pct: "feijao2Percent", area: "feijao2AreaPlantada", r90: "Feijao2Risco90", r45: "Feijao2RPC45", r85: "Feijao2RPC85" },
  { key: "FeijaoCaupi", label: "Feijão Caupi", pct: "feijaoCaupiPercent", area: "feijaoCaupiAreaPlantada", r90: "FeijaoCaupiRisco90", r45: "FeijaoCaupiRPC45", r85: "FeijaoCaupiRPC85" },
  { key: "Cana", label: "Cana", pct: "canaPercent", area: "canaAreaPlantada", r90: "CanaRisco90", r45: "CanaRPC45", r85: "CanaRPC85" },
  { key: "Algodao", label: "Algodão", pct: "algodaoPercent", area: "algodaoAreaPlantada", r90: "AlgodaoRisco90", r45: "AlgodaoRPC45", r85: "AlgodaoRPC85" },
  { key: "Trigo", label: "Trigo", pct: "trigoPercent", area: "trigoAreaPlantada", r90: "TrigoRisco90", r45: "TrigoRPC45", r85: "TrigoRPC85" },
  { key: "Sorgo", label: "Sorgo", pct: "sorgoPercent", area: "sorgoAreaPlantada", r90: "SorgoRisco90", r45: "SorgoRPC45", r85: "SorgoRPC85" },
];
const SCENARIOS = [
  { key: "r90", label: "Risco 90" },
  { key: "r45", label: "RCP 4.5" },
  { key: "r85", label: "RCP 8.5" },
];
let activeCrop = CROPS[0];
let activeScenario = SCENARIOS[0];
let chatHistory = [];
const rowMap = new Map();

/* ─── COLOR SCALES ─────────────────────────────────── */
const colorLow = d3.scaleThreshold().domain(d3.range(0, 100, 10)).range(d3.schemeGreens[9]);
const colorHigh = d3.scaleThreshold().domain(d3.range(0, 100, 10)).range(d3.schemeReds[9]);

function getFill(d) {
  const row = rowMap.get(d.properties.COD_IBGE);
  if (!row) return "#1c2030";
  const pct = parseFloat(row[activeCrop.pct]) || 0;
  const risk = row[activeCrop[activeScenario.key]];
  return risk === "ALTO" ? colorHigh(pct) : colorLow(pct);
}

/* ─── GRADIENTS ────────────────────────────────────── */
function drawGradient(id, scaleFn, w, h) {
  const c = document.getElementById(id);
  if (!c) return;
  c.width = w || c.parentElement.clientWidth || 200;
  c.height = h || 12;
  const ctx = c.getContext("2d");
  for (let i = 0; i < c.width; i++) {
    ctx.fillStyle = scaleFn((i / c.width) * 100);
    ctx.fillRect(i, 0, 1, c.height);
  }
}
function buildLegends() {
  drawGradient("leg-green", colorLow);
  drawGradient("leg-red", colorHigh);
  drawGradient("swatch-green", colorLow, 30, 14);
  drawGradient("swatch-red", colorHigh, 30, 14);
}



/* ─── TOOLTIP ──────────────────────────────────────── */
const tooltip = document.getElementById("tooltip");
let lockedIBGE = null;

function countyHTML(row) {
  const pct = parseFloat(row[activeCrop.pct]) || 0;
  const area = parseInt(row[activeCrop.area]) || 0;
  const risk = row[activeCrop[activeScenario.key]] || "—";
  const legal = parseInt(row.areaLegal || 0);
  return `
    <div class="info-name">${row.name || "—"}</div>
    <div class="info-row"><span class="info-key">Área legal</span><span class="info-val">${legal.toLocaleString("pt-BR")} ha</span></div>
    <div class="info-row"><span class="info-key">Área plantada</span><span class="info-val">${area.toLocaleString("pt-BR")} ha</span></div>
    <div class="info-row"><span class="info-key">Percentual</span><span class="info-val">${pct.toFixed(2)}%</span></div>
    <div class="info-row"><span class="info-key">Risco · ${activeScenario.label}</span><span class="info-val ${risk === 'ALTO' ? 'alto' : 'baixo'}">${risk}</span></div>`;
}

function showTip(event, d) {
  const row = rowMap.get(d.properties.COD_IBGE);
  if (!row) return;
  const pct = parseFloat(row[activeCrop.pct]) || 0;
  const area = parseInt(row[activeCrop.area]) || 0;
  const risk = row[activeCrop[activeScenario.key]] || "—";
  document.getElementById("tt-name").textContent = row.name || "—";
  document.getElementById("tt-area").textContent = area.toLocaleString("pt-BR") + " ha";
  document.getElementById("tt-pct").textContent = pct.toFixed(2) + "%";
  const tr = document.getElementById("tt-risk");
  tr.textContent = risk; tr.className = "tt-val " + (risk === "ALTO" ? "alto" : "baixo");
  tooltip.classList.add("vis"); moveTip(event);

  // Only update the sidebar panel if no county is locked
  if (!lockedIBGE) {
    document.getElementById("county-info").innerHTML = countyHTML(row);
  }
}

function lockCounty(d) {
  const row = rowMap.get(d.properties.COD_IBGE);
  if (!row) return;
  // Clicking the same county unlocks it
  if (lockedIBGE === d.properties.COD_IBGE) {
    lockedIBGE = null;
    document.getElementById("county-info").innerHTML =
      `<span style="color:var(--muted);font-size:10px">Clique em um município no mapa para fixar os dados aqui.</span>`;
    d3.selectAll(".county").attr("stroke", null).attr("stroke-width", null);
    return;
  }
  lockedIBGE = d.properties.COD_IBGE;
  document.getElementById("county-info").innerHTML = countyHTML(row);
  // Highlight the locked county
  d3.selectAll(".county")
    .attr("stroke", f => f.properties.COD_IBGE === lockedIBGE ? "#fff" : null)
    .attr("stroke-width", f => f.properties.COD_IBGE === lockedIBGE ? 1.8 : null);
}

function moveTip(ev) {
  tooltip.style.left = Math.min(ev.clientX + 16, window.innerWidth - 210) + "px";
  tooltip.style.top = Math.max(ev.clientY - 8, 4) + "px";
}
function hideTip() { tooltip.classList.remove("vis"); }

/* ─── STATS & HEADER ───────────────────────────────── */
function updateStats() {
  let alto = 0, baixo = 0;
  rowMap.forEach(row => { row[activeCrop[activeScenario.key]] === "ALTO" ? alto++ : baixo++; });
  document.getElementById("stat-alto").textContent = alto.toLocaleString("pt-BR");
  document.getElementById("stat-baixo").textContent = baixo.toLocaleString("pt-BR");
}
function updateHeader() {
  document.getElementById("map-title").textContent = `Risco Agrícola · ${activeCrop.label}`;
  document.getElementById("map-subtitle").textContent = `Cenário: ${activeScenario.label} · Municípios Brasileiros`;
}
function updateMap() {
  d3.selectAll(".county").attr("fill", d => getFill(d));
  updateStats(); updateHeader();
  // Refresh locked county data with new crop/scenario
  if (lockedIBGE) {
    const row = rowMap.get(lockedIBGE);
    if (row) document.getElementById("county-info").innerHTML = countyHTML(row);
  }
}

/* ─── SIDEBAR TABS ─────────────────────────────────── */
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

/* ─── MOBILE DRAWER ────────────────────────────────── */
const sidebar = document.getElementById("sidebar");
const overlay = document.getElementById("sidebar-overlay");
const mobileFab = document.getElementById("mobile-fab");
function openSidebar() { sidebar.classList.add("open"); overlay.classList.add("open"); }
function closeSidebar() { sidebar.classList.remove("open"); overlay.classList.remove("open"); }
mobileFab.addEventListener("click", openSidebar);
overlay.addEventListener("click", closeSidebar);

/* ─── UI BUILDERS ──────────────────────────────────── */
function buildCropButtons() {
  const grid = document.getElementById("crop-grid");
  CROPS.forEach(crop => {
    const btn = document.createElement("button");
    btn.className = "crop-btn" + (crop === activeCrop ? " active" : "");
    btn.textContent = crop.label;
    btn.addEventListener("click", () => {
      activeCrop = crop;
      document.querySelectorAll(".crop-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active"); updateMap();
    });
    grid.appendChild(btn);
  });
}
function buildScenarioPills() {
  const row = document.getElementById("scenario-row");
  SCENARIOS.forEach(sc => {
    const btn = document.createElement("button");
    btn.className = "sc-pill" + (sc === activeScenario ? " active" : "");
    btn.textContent = sc.label;
    btn.addEventListener("click", () => {
      activeScenario = sc;
      document.querySelectorAll(".sc-pill").forEach(b => b.classList.remove("active"));
      btn.classList.add("active"); updateMap();
    });
    row.appendChild(btn);
  });
}

/* ─── AI CHAT ──────────────────────────────────────── */
let chatStreaming = false;
const chatMessages = document.getElementById("chat-bar-messages");
const chatInput = document.getElementById("chat-input");
const chatSend = document.getElementById("chat-send");

chatInput.addEventListener("input", () => {
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 34) + "px";
});

document.getElementById("chat-suggestions").addEventListener("click", e => {
  if (e.target.classList.contains("chat-suggestion")) {
    chatInput.value = e.target.textContent;
    sendChat();
  }
});
chatSend.addEventListener("click", sendChat);
chatInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

function appendBubble(role, text, streaming = false) {
  const wrap = document.createElement("div");
  wrap.className = "chat-msg-wrap";
  const rd = document.createElement("div");
  rd.className = "chat-role";
  rd.textContent = role === "user" ? "Você" : "Assistente";
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}${streaming ? " streaming" : ""}`;
  bubble.textContent = text;
  wrap.appendChild(rd); wrap.appendChild(bubble);
  chatMessages.appendChild(wrap);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return bubble;
}

const BACKEND_URL = window.location.hostname === "localhost"
  ? "http://localhost:8000"
  : "https://aka-selvas-brasil2040.hf.space"; 

async function sendChat() {
  const text = chatInput.value.trim();
  if (!text || chatStreaming) return;
  const sugg = document.getElementById("chat-suggestions");
  if (sugg) sugg.remove();
  chatInput.value = ""; chatInput.style.height = "auto";
  chatStreaming = true; chatSend.disabled = true;
  expandChat();
  appendBubble("user", text);
  const bubble = appendBubble("assistant", "", true);

  try {
    const res = await fetch(`${BACKEND_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: text,
        history: chatHistory,   // send conversation so far
        top_k: 5
      })
    });

    if (!res.ok) throw new Error("HTTP " + res.status);

    // Stream the response text
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let full = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      full += chunk;
      bubble.textContent = full;
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    bubble.classList.remove("streaming");

    // Save to history for next turn
    chatHistory.push({ role: "user",  parts: text });
    chatHistory.push({ role: "model", parts: full });

  } catch (err) {
    bubble.textContent = "Erro ao conectar com o assistente.";
    bubble.classList.remove("streaming");
    console.error(err);
  } finally {
    chatStreaming = false;
    chatSend.disabled = false;
  }
}

/* ─── CHAT EXPAND/COLLAPSE ─────────────────────────── */
const chatBar = document.getElementById("chat-bar");

function expandChat() {
  chatBar.classList.add("expanded");
  setTimeout(() => { chatMessages.scrollTop = chatMessages.scrollHeight; }, 50);
}
function collapseChat() { chatBar.classList.remove("expanded"); }

document.getElementById("chat-collapse-btn").addEventListener("click", collapseChat);
document.getElementById("chat-expand-btn").addEventListener("click", () => {
  chatBar.classList.contains("expanded") ? collapseChat() : expandChat();
});

/* ─── VIEW SWITCHING ───────────────────────────────── */
const mapView = document.getElementById("map-view");
const contentView = document.getElementById("content-view");

const panelLoaded = {};  // tracks which panels have been fetched + rendered

// Per-panel chart renderers — called once after panel HTML is injected
const panelRenderers = {
  agro: renderAgro,
  energia: renderEnergia,
  hidro: renderHidro,
  transp: renderTransp,
  costa: renderCosta,
  urb: renderUrb,
  sobre: renderSobre,
};

// Re-render charts on resize (debounced)
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    // Clear rendered flag and wipe chart containers so they re-render
    Object.keys(panelLoaded).forEach(view => {
      if (view === 'sobre') return; // no charts
      const panel = document.getElementById('panel-' + view);
      if (panel && panel.classList.contains('active')) {
        // Only re-render the currently visible panel
        panel.querySelectorAll('.chart-area').forEach(el => el.innerHTML = '');
        if (panelRenderers[view]) panelRenderers[view]();
      }
    });
  }, 250);
});

async function switchView(view) {
  const isMap = view === "mapa";

  // Toggle map vs content
  mapView.style.display = isMap ? "flex" : "none";
  contentView.style.display = isMap ? "none" : "flex";

  if (!isMap) {
    // Deactivate all panels
    document.querySelectorAll("#content-view .panel").forEach(p => p.classList.remove("active"));

    const target = document.getElementById("panel-" + view);
    if (target) {
      // Lazy-load panel HTML on first visit
      if (!panelLoaded[view]) {
        try {
          const res = await fetch("panels/panel-" + view + ".html");
          if (!res.ok) throw new Error("HTTP " + res.status);
          target.outerHTML = await res.text();
          panelLoaded[view] = true;
          // Re-query after replacing outerHTML
          const fresh = document.getElementById("panel-" + view);
          if (fresh) {
            fresh.classList.add("active");
            // Run this panel's chart renderers
            if (panelRenderers[view]) panelRenderers[view]();
          }
        } catch (err) {
          console.error("Failed to load panel-" + view, err);
          target.innerHTML = '<p style="color:var(--red);padding:2rem">Erro ao carregar painel.</p>';
          target.classList.add("active");
        }
      } else {
        const fresh = document.getElementById("panel-" + view);
        if (fresh) fresh.classList.add("active");
      }
    }
    contentView.scrollTop = 0;
  }

  // Update nav active state
  document.querySelectorAll(".nav-tab").forEach(t => {
    t.classList.toggle("active", t.dataset.view === view);
  });

  // Hide mobile sidebar when switching
  if (!isMap) closeSidebar();
  // Show/hide mobile fab only on map
  mobileFab.style.display = isMap ? "" : "none";
}

// Wire up top nav tabs
document.querySelectorAll(".nav-tab").forEach(btn => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});


// ─── CHIP CLICKS → open chatbot (delegated — works for dynamically loaded panels)
document.body.addEventListener("click", e => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  chatInput.value = chip.textContent.trim();
  expandChat();
  sendChat();
});

/* ─── MAP INITIALIZATION ───────────────────────────── */
Promise.all([
  d3.json("https://huggingface.co/spaces/aka-selvas/brasil2040/resolve/main/mapaMunicipiosBR.json"),
  d3.csv("culturasRiscoBr2040.csv")
]).then(([brm, csv]) => {
  csv.forEach(row => rowMap.set(row.id, row));
  document.getElementById("map-badge").textContent = brm.features.length.toLocaleString("pt-BR") + " municípios";

  const path = d3.geoPath();
  const g = d3.select("#map-g");

  g.selectAll(".county").data(brm.features).join("path")
    .attr("class", "county")
    .attr("d", path)
    .attr("fill", d => getFill(d))
    .on("mouseover", (ev, d) => showTip(ev, d))
    .on("mousemove", moveTip)
    .on("mouseout", hideTip)
    .on("click", (ev, d) => lockCounty(d));

  const svg = d3.select("#map-svg");
  const zoom = d3.zoom().scaleExtent([0.4, 14]).on("zoom", ev => g.attr("transform", ev.transform));
  svg.call(zoom);

  const wrap = document.getElementById("map-svg-wrap");

  function centerMap(animate = false) {
    const W = wrap.clientWidth;
    const H = wrap.clientHeight;
    if (!W || !H) return;
    const bbox = g.node().getBBox();
    if (bbox.width === 0 || bbox.height === 0) return;
    const scale = Math.min(W / bbox.width, H / bbox.height) * 0.94;
    const tx = (W - bbox.width * scale) / 2 - bbox.x * scale;
    const ty = (H - bbox.height * scale) / 2 - bbox.y * scale;
    if (animate) {
      svg.transition().duration(450).call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
    } else {
      svg.call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
    }
  }

  requestAnimationFrame(() => centerMap(false));

  document.getElementById("btn-zi").addEventListener("click", () => svg.transition().duration(280).call(zoom.scaleBy, 1.55));
  document.getElementById("btn-zo").addEventListener("click", () => svg.transition().duration(280).call(zoom.scaleBy, 0.65));
  document.getElementById("btn-zr").addEventListener("click", () => centerMap(true));

  buildCropButtons();
  buildScenarioPills();
  buildLegends();
  updateStats();
  updateHeader();

  document.getElementById("loading").style.opacity = "0";
  setTimeout(() => document.getElementById("loading").style.display = "none", 620);

}).catch(err => {
  console.error(err);
  document.getElementById("loading").innerHTML = `
    <div style="font-family:'Syne',sans-serif;font-size:16px;color:#f05252">⚠ Erro ao carregar dados</div>
    <div style="font-size:11px;color:#6a708f;margin-top:8px">${err.message}</div>
    <div style="font-size:10px;color:#6a708f;margin-top:12px;max-width:340px;line-height:1.7;text-align:center">
      Certifique-se de que <code>brm.json</code> e <code>culturaRisco.csv</code> estão na mesma pasta
      e sirva a página via HTTP (ex: <code>python3 -m http.server</code>).
    </div>`;
});

/* ══════════════════════════════════════════════════
   SECTOR PANEL CHARTS
══════════════════════════════════════════════════ */
const s = getComputedStyle(document.documentElement);
const gc = v => s.getPropertyValue(v).trim();
const C = {
  miroc45: 'var(--c-miroc45)', miroc85: 'var(--c-miroc85)',
  hadgem45: 'var(--c-hadgem45)', hadgem85: 'var(--c-hadgem85)',
  blue: 'var(--c-blue)', green: 'var(--c-green)', red: 'var(--c-red)',
  amber: 'var(--c-amber)', purple: 'var(--c-purple)',
  muted: 'var(--c-muted)', text: 'var(--c-text)', border: 'var(--c-border)',
  surf: 'var(--c-surf)', dim: 'var(--c-dim)',
};
const FM = "'IBM Plex Mono'";

/* Helper — create a D3 SVG inside a container element */
function mkSvg(id, H, defaultW = 340) {
  const el = document.getElementById(id);
  if (!el) return null;
  const W = el.clientWidth || defaultW;
  const svg = d3.select(el).append('svg')
    .attr('viewBox', `0 0 ${W} ${H}`)
    .attr('width', W).attr('height', H);
  return { el, svg, W, H };   // ← add H here
}

function hBar(containerId, data, { keyField = 'label', valField = 'value', color = '#3dd98a', fmt = v => v, unit = '', showVal = true } = {}) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const W = el.clientWidth || 380;
  const rowH = 28, pad = { t: 4, r: 60, b: 8, l: 130 };
  const H = data.length * rowH + pad.t + pad.b;
  const x = d3.scaleLinear()
    .domain([d3.min(data, d => Math.min(0, +d[valField])), d3.max(data, d => Math.max(0, +d[valField]))])
    .range([pad.l, W - pad.r]).nice();
  const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', W).attr('height', H);
  const zero = x(0);
  data.forEach((d, i) => {
    const y = pad.t + i * rowH + 2;
    const v = +d[valField];
    const bx = v >= 0 ? zero : x(v);
    const bw = Math.abs(x(v) - zero);
    const c = typeof color === 'function' ? color(d) : color;
    svg.append('rect').attr('x', bx).attr('y', y + 4).attr('width', Math.max(bw, 1)).attr('height', rowH - 8)
      .attr('fill', c).attr('rx', 2).attr('opacity', .85);
    svg.append('text').attr('x', pad.l - 8).attr('y', y + rowH / 2 + 4)
      .attr('text-anchor', 'end').attr('fill', C.muted).attr('font-family', FM).attr('font-size', 12)
      .text(d[keyField]);
    if (showVal) {
      svg.append('text')
        .attr('x', v >= 0 ? bx + bw + 4 : bx - 4).attr('y', y + rowH / 2 + 4)
        .attr('text-anchor', v >= 0 ? 'start' : 'end')
        .attr('fill', c).attr('font-family', FM).attr('font-size', 12).attr('font-weight', '500')
        .text((v >= 0 ? '+' : '') + fmt(v) + unit);
    }
  });
  svg.append('line').attr('x1', zero).attr('x2', zero).attr('y1', pad.t).attr('y2', H - pad.b)
    .attr('stroke', C.border).attr('stroke-width', 1);
}

function groupedHBar(containerId, data, groups, colors, { keyField = 'label', fmt = v => v, unit = '' } = {}) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const W = el.clientWidth || 380;
  const gH = groups.length * 14 + 8;
  const rowH = gH + 4;
  const pad = { t: 4, r: 60, b: 8, l: 130 };
  const H = data.length * rowH + pad.t + pad.b;
  const allVals = data.flatMap(d => groups.map(g => d[g]));
  const x = d3.scaleLinear()
    .domain([Math.min(0, d3.min(allVals)), Math.max(0, d3.max(allVals))])
    .range([pad.l, W - pad.r]).nice();
  const zero = x(0);
  const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', W).attr('height', H);
  data.forEach((d, i) => {
    const ry = pad.t + i * rowH;
    svg.append('text').attr('x', pad.l - 8).attr('y', ry + gH / 2 + 4)
      .attr('text-anchor', 'end').attr('fill', C.muted).attr('font-family', FM).attr('font-size', 12)
      .text(d[keyField]);
    groups.forEach((g, gi) => {
      const v = +d[g];
      const by = ry + gi * 14 + 2;
      const bx = v >= 0 ? zero : x(v);
      const bw = Math.abs(x(v) - zero);
      svg.append('rect').attr('x', bx).attr('y', by + 1).attr('width', Math.max(bw, 1)).attr('height', 11)
        .attr('fill', colors[gi]).attr('rx', 2).attr('opacity', .85);
      const tx = v >= 0 ? bx + bw + 3 : bx - 3;
      svg.append('text').attr('x', tx).attr('y', by + 9)
        .attr('text-anchor', v >= 0 ? 'start' : 'end')
        .attr('fill', colors[gi]).attr('font-family', FM).attr('font-size', 11)
        .text((v >= 0 ? '+' : '') + fmt(v) + unit);
    });
  });
  svg.append('line').attr('x1', zero).attr('x2', zero).attr('y1', pad.t).attr('y2', H - pad.b)
    .attr('stroke', C.border).attr('stroke-width', 1);
}

function simpleBar(containerId, data, { keyField = 'label', valField = 'value', color = '#3dd98a', fmt = v => v, unit = '' } = {}) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const W = el.clientWidth || 380;
  const rowH = 34, pad = { t: 6, r: 80, b: 6, l: 20 };
  const H = data.length * rowH + pad.t + pad.b;
  const x = d3.scaleLinear().domain([0, d3.max(data, d => +d[valField])]).range([pad.l, W - pad.r]);
  const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', W).attr('height', H);
  data.forEach((d, i) => {
    const y = pad.t + i * rowH;
    const v = +d[valField];
    const bw = x(v) - pad.l;
    const c = typeof color === 'function' ? color(d) : color;
    svg.append('rect').attr('x', pad.l).attr('y', y + 4).attr('width', Math.max(bw, 1)).attr('height', rowH - 10)
      .attr('fill', c).attr('rx', 2).attr('opacity', .85);
    svg.append('text').attr('x', pad.l + 6).attr('y', y + rowH / 2 + 3)
      .attr('fill', C.muted).attr('font-family', FM).attr('font-size', 12).attr('font-weight', '500')
      .text(d[keyField]);
    svg.append('text').attr('x', pad.l + bw + 5).attr('y', y + rowH / 2 + 3)
      .attr('fill', c).attr('font-family', FM).attr('font-size', 10)
      .text(fmt(v) + unit);
  });
}


// ── Per-panel chart renderers ──────────────────────

function renderAgro() {
  // ── Chart data ──
  const cropLossData = [
    { label: 'Soja', m45: -13.9, m85: -10.9, h45: -36.3, h85: -39.3 },
    { label: 'Trigo', m45: -3.9, m85: -5.0, h45: -21.3, h85: -24.8 },
    { label: 'Arroz', m45: -12.5, m85: -10.1, h45: -21.3, h85: -24.0 },
    { label: 'Milho 1ª', m45: -1.3, m85: -1.4, h45: -16.0, h85: -16.0 },
    { label: 'Feijão', m45: +1.5, m85: +1.5, h45: -22.4, h85: -25.7 },
    { label: 'Safrinha', m45: +7.9, m85: +0.7, h45: -25.5, h85: -28.1 },
    { label: 'Algodão', m45: -0.5, m85: -0.6, h45: -10.7, h85: -13.4 },
    { label: 'Sorgo', m45: 0.0, m85: -0.3, h45: -7.3, h85: -9.2 },
    { label: 'Cana', m45: +4.1, m85: +5.1, h45: -2.7, h85: -3.8 },
  ];
  groupedHBar('chart-crop-loss', cropLossData, ['m45', 'm85', 'h45', 'h85'],
    [C.miroc45, C.miroc85, C.hadgem45, C.hadgem85], { keyField: 'label', fmt: v => v.toFixed(1), unit: '%' });

  // ── Agro: regional production shift (new) ──
  hBar('chart-region-shift', [
    { label: 'Centro-Oeste', value: +3.3 },
    { label: 'Norte Amazônia', value: +2.7 },
    { label: 'Nordeste Cerrado', value: +0.5 },
    { label: 'Nordeste Litor.', value: +0.1 },
    { label: 'Sudeste', value: -1.5 },
    { label: 'Sul', value: -8.6 },
  ], {
    color: d => d.value >= 0 ? C.green : C.red,
    fmt: v => (v >= 0 ? '+' : '') + v.toFixed(1),
    unit: ' M ha', keyField: 'label', valField: 'value'
  });

  // ── Agro: insurance gap (new) ──
  (function () {
    const H = 110;
    const r = mkSvg('chart-insurance-gap', H, 380); if (!r) return;
    const { svg, W } = r;
    const data = [
      { label: 'Hoje (2013)', val: 4.4, covered: 1.0, color: C.amber },
      { label: '2040 · MIROC', val: 8.9, covered: 1.0, color: C.amber },
      { label: '2040 · HadGEM', val: 13.9, covered: 1.0, color: C.red },
    ];
    const pad = { l: 110, r: 20, t: 10, b: 28 };
    const x = d3.scaleLinear().domain([0, 15]).range([pad.l, W - pad.r]);
    const band = (H - pad.t - pad.b) / data.length;
    data.forEach((d, i) => {
      const y = pad.t + i * band;
      const bH = band - 6;
      // Full bar (total at risk)
      svg.append('rect').attr('x', x(0)).attr('y', y + 2)
        .attr('width', x(d.val) - x(0)).attr('height', bH)
        .attr('fill', d.color).attr('rx', 3).attr('opacity', .25);
      // Covered bar
      svg.append('rect').attr('x', x(0)).attr('y', y + 2)
        .attr('width', x(d.covered) - x(0)).attr('height', bH)
        .attr('fill', d.color).attr('rx', 3).attr('opacity', .85);
      svg.append('text').attr('x', pad.l - 6).attr('y', y + bH / 2 + 6)
        .attr('text-anchor', 'end').attr('fill', C.muted)
        .attr('font-family', FM).attr('font-size', 11).text(d.label);
      svg.append('text').attr('x', x(d.val) + 4).attr('y', y + bH / 2 + 6)
        .attr('fill', d.color).attr('font-family', FM).attr('font-size', 11).attr('font-weight', '600')
        .text(d.val + ' M ha');
    });
    // x-axis label
    svg.append('text').attr('x', pad.l).attr('y', H - 4)
      .attr('fill', C.muted).attr('font-family', FM).attr('font-size', 8.5)
      .text('Área de soja em alto risco climático (M ha)  ■ com seguro  □ sem cobertura');
  })();

  const landData = [
    { label: 'Rio Gd do Sul', value: +44 }, { label: 'Santa Catarina', value: +38 }, { label: 'Paraná', value: +27 },
    { label: 'Ceará', value: +22 }, { label: 'Rio Gd do Norte', value: +21 },
    { label: 'Rondônia', value: -34 }, { label: 'Paraíba', value: -26 }, { label: 'Acre', value: -27 },
    { label: 'Tocantins', value: -26 }, { label: 'Mato Grosso', value: -25 }, { label: 'Goiás', value: -23 },
  ];
  hBar('chart-land-value', landData, { color: d => d.value >= 0 ? C.green : C.red, fmt: v => Math.abs(v).toFixed(0), unit: '%' });

  
  // ── Agro: Productivity slope chart (2010 → 2040) ──
  (function () {
    const crops = [
      { label: 'Milho 2ª', v10: 4.16, v40: 9.18, pct: 120.7 },
      { label: 'Trigo', v10: 2.74, v40: 4.56, pct: 66.4 },
      { label: 'Arroz', v10: 4.22, v40: 6.98, pct: 65.4 },
      { label: 'Feijão V.', v10: 0.72, v40: 1.20, pct: 66.7 },
      { label: 'Milho 1ª', v10: 4.41, v40: 6.42, pct: 45.6 },
      { label: 'Soja', v10: 2.93, v40: 4.32, pct: 47.4 },
      { label: 'Feijão I.', v10: 1.36, v40: 1.99, pct: 46.3 },
      { label: 'Algodão', v10: 3.63, v40: 5.12, pct: 41.0 },
      { label: 'Cana-de-açúcar', v10: 78.28 / 10, v40: 97.03 / 10, pct: 24.0 },
    ];
    const H = 220, pad = { t: 24, b: 28, l: 70, r: 85 };
    const r = mkSvg('chart-productivity-slope', H, 380); if (!r) return;
    const { svg, W } = r;
    const avW = W - pad.l - pad.r;
    const allVals = crops.flatMap(c => [c.v10, c.v40]);
    const yScale = d3.scaleLinear().domain([0, d3.max(allVals) * 1.05]).range([H - pad.b, pad.t]);
    const xLeft = pad.l, xRight = pad.l + avW;

    // Grid lines
    [0, 2, 4, 6, 8, 10].forEach(v => {
      if (v > d3.max(allVals)) return;
      const y = yScale(v);
      svg.append('line').attr('x1', xLeft).attr('x2', xRight).attr('y1', y).attr('y2', y)
        .attr('stroke', C.border).attr('stroke-width', 0.5).attr('stroke-dasharray', '3,3');
      svg.append('text').attr('x', xLeft - 5).attr('y', y + 4).attr('text-anchor', 'end')
        .attr('fill', C.muted).attr('font-size', 8).attr('font-family', FM).text(v + ' t/ha');
    });

    // Year labels
    svg.append('text').attr('x', xLeft).attr('y', H - 6).attr('text-anchor', 'middle')
      .attr('fill', C.dim).attr('font-size', 9).attr('font-family', FM).text('2010');
    svg.append('text').attr('x', xRight).attr('y', H - 6).attr('text-anchor', 'middle')
      .attr('fill', C.dim).attr('font-size', 9).attr('font-family', FM).text('2040');

    crops.forEach((d, i) => {
      const hue = d.pct > 60 ? C.green : d.pct > 40 ? C.blue : C.amber;
      const y10 = yScale(d.v10), y40 = yScale(d.v40);
      svg.append('line')
        .attr('x1', xLeft).attr('y1', y10).attr('x2', xRight).attr('y2', y40)
        .attr('stroke', hue).attr('stroke-width', 1.5).attr('opacity', 0.75);
      svg.append('circle').attr('cx', xLeft).attr('cy', y10).attr('r', 3).attr('fill', hue).attr('opacity', 0.85);
      svg.append('circle').attr('cx', xRight).attr('cy', y40).attr('r', 3).attr('fill', hue);
      svg.append('text').attr('x', xLeft - 6).attr('y', y10 + 4).attr('text-anchor', 'end')
        .attr('fill', C.muted).attr('font-size', 8.5).attr('font-family', FM).text(d.label);
      svg.append('text').attr('x', xRight + 5).attr('y', y40 + 4).attr('text-anchor', 'start')
        .attr('fill', hue).attr('font-size', 8.5).attr('font-family', FM).attr('font-weight', '600')
        .text('+' + d.pct.toFixed(0) + '%');
    });

    // Legend note
    svg.append('text').attr('x', xLeft).attr('y', pad.t - 8).attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM)
      .text('* Cana ÷10 para escala. Fonte: Produto 5 · Brasil 2040');
  })();

  // ── Agro: Crop parameters (ISNA, CAD, cycle) ──
  (function () {
    const data = [
      { label: 'Sorgo', isna: 0.50, cad: 50, ciclo: 120, res: 5 },
      { label: 'Feijão Caupi', isna: 0.50, cad: 40, ciclo: 80, res: 5 },
      { label: 'Milho 1ª', isna: 0.55, cad: 50, ciclo: 130, res: 3 },
      { label: 'Safrinha', isna: 0.55, cad: 50, ciclo: 120, res: 3 },
      { label: 'Algodão', isna: 0.55, cad: 50, ciclo: 140, res: 3 },
      { label: 'Trigo', isna: 0.55, cad: 40, ciclo: 130, res: 3 },
      { label: 'Soja', isna: 0.60, cad: 50, ciclo: 125, res: 1 },
      { label: 'Arroz', isna: 0.60, cad: 50, ciclo: 120, res: 1 },
      { label: 'Feijão', isna: 0.60, cad: 40, ciclo: 90, res: 1 },
      { label: 'Cana', isna: 0.60, cad: 100, ciclo: 360, res: 2 },
    ];
    const H = 230, pad = { t: 32, b: 8, l: 90, r: 18 };
    const r = mkSvg('chart-crop-params', H, 380); if (!r) return;
    const { svg, W } = r;
    const rowH = (H - pad.t - pad.b) / data.length;
    const colW = (W - pad.l - pad.r) / 3;

    // Headers
    ['ISNA mínimo', 'CAD (mm)', 'Ciclo (dias)'].forEach((h, j) => {
      svg.append('text').attr('x', pad.l + j * colW + colW / 2).attr('y', pad.t - 10)
        .attr('text-anchor', 'middle').attr('fill', C.muted).attr('font-size', 8).attr('font-family', FM)
        .attr('letter-spacing', '0.5').text(h);
    });

    const cols = [
      { key: 'isna', scale: d3.scaleLinear().domain([0.48, 0.62]).range([0, colW - 10]) },
      { key: 'cad', scale: d3.scaleLinear().domain([0, 110]).range([0, colW - 10]) },
      { key: 'ciclo', scale: d3.scaleLinear().domain([0, 380]).range([0, colW - 10]) },
    ];

    data.forEach((d, i) => {
      const y = pad.t + i * rowH;
      const bH = rowH * 0.65;
      const resColor = d.res === 5 ? C.green : d.res === 3 ? C.amber : C.red;

      // Row BG for high-resistance crops
      if (d.res === 5) {
        svg.append('rect').attr('x', 0).attr('y', y - 1).attr('width', W).attr('height', rowH)
          .attr('fill', 'rgba(61,217,138,0.04)').attr('rx', 2);
      }

      svg.append('text').attr('x', pad.l - 6).attr('y', y + bH / 2 + 5).attr('text-anchor', 'end')
        .attr('fill', resColor).attr('font-size', 9.5).attr('font-family', FM)
        .attr('font-weight', d.res === 5 ? '600' : '400').text(d.label);

      cols.forEach((col, j) => {
        const bx = pad.l + j * colW;
        const bw = col.scale(d[col.key]);
        svg.append('rect').attr('x', bx).attr('y', y + 2).attr('width', bw).attr('height', bH - 2)
          .attr('fill', resColor).attr('rx', 2).attr('opacity', 0.7);
        const val = col.key === 'isna' ? d[col.key].toFixed(2) : d[col.key];
        svg.append('text').attr('x', bx + bw + 4).attr('y', y + bH / 2 + 5)
          .attr('fill', resColor).attr('font-size', 8.5).attr('font-family', FM).text(val);
      });
    });

    // Legend
    const legY = pad.t - 22;
    svg.append('rect').attr('x', pad.l).attr('y', legY - 7).attr('width', 7).attr('height', 7).attr('fill', C.green).attr('rx', 1);
    svg.append('text').attr('x', pad.l + 10).attr('y', legY).attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM).text('Alta tolerância hídrica');
    svg.append('rect').attr('x', pad.l + 115).attr('y', legY - 7).attr('width', 7).attr('height', 7).attr('fill', C.amber).attr('rx', 1);
    svg.append('text').attr('x', pad.l + 126).attr('y', legY).attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM).text('Moderada');
    svg.append('rect').attr('x', pad.l + 185).attr('y', legY - 7).attr('width', 7).attr('height', 7).attr('fill', C.red).attr('rx', 1);
    svg.append('text').attr('x', pad.l + 196).attr('y', legY).attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM).text('Sensível');
  })();

  // ── Agro: Current at-risk areas (2012 IBGE) ──
  (function () {
    const data = [
      { label: 'Soja', val: 3770, color: C.red },
      { label: 'Milho 2ª safra', val: 1103, color: C.amber },
      { label: 'Feijão verão', val: 973, color: C.amber },
      { label: 'Feijão inverno', val: 305, color: C.blue },
      { label: 'Milho 1ª safra', val: 296, color: C.blue },
      { label: 'Trigo', val: 141, color: C.blue },
    ];
    const H = 160, pad = { t: 20, b: 20, l: 110, r: 70 };
    const r = mkSvg('chart-current-risk', H, 340); if (!r) return;
    const { svg, W } = r;
    const avW = W - pad.l - pad.r;
    const scale = d3.scaleLinear().domain([0, 4200]).range([0, avW]);
    const rowH = (H - pad.t - pad.b) / data.length;

    svg.append('text').attr('x', pad.l).attr('y', 13).attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM)
      .text('Área já plantada em alto risco climático (mil ha) → ');

    data.forEach((d, i) => {
      const y = pad.t + i * rowH + rowH * 0.1;
      const bH = rowH * 0.7;
      svg.append('rect').attr('x', pad.l).attr('y', y).attr('width', scale(d.val)).attr('height', bH)
        .attr('fill', d.color).attr('rx', 2).attr('opacity', 0.82);
      svg.append('text').attr('x', pad.l - 6).attr('y', y + bH / 2 + 4).attr('text-anchor', 'end')
        .attr('fill', C.muted).attr('font-size', 9.5).attr('font-family', FM).text(d.label);
      svg.append('text').attr('x', pad.l + scale(d.val) + 5).attr('y', y + bH / 2 + 4)
        .attr('fill', d.color).attr('font-size', 9.5).attr('font-family', FM).attr('font-weight', '600')
        .text(d.val.toLocaleString('pt-BR') + ' mil ha');
    });
  })();

  // ── Agro: Insurance history 2005-2013 ──
  (function () {
    const years = [2005, 2007, 2009, 2011, 2013];
    const produtores = [849, 5200, 18000, 38000, 65556];
    const subvencao = [2.3, 35, 120, 290, 557.6];

    const H = 170, pad = { t: 30, b: 30, l: 50, r: 50 };
    const r = mkSvg('chart-insurance-history', H, 380); if (!r) return;
    const { svg, W } = r;
    const avW = W - pad.l - pad.r;
    const xScale = d3.scaleLinear().domain([2005, 2013]).range([pad.l, pad.l + avW]);
    const yScaleP = d3.scaleLinear().domain([0, 70000]).range([H - pad.b, pad.t]);
    const yScaleS = d3.scaleLinear().domain([0, 600]).range([H - pad.b, pad.t]);

    // Gridlines
    [0, 20000, 40000, 60000].forEach(v => {
      const y = yScaleP(v);
      svg.append('line').attr('x1', pad.l).attr('x2', pad.l + avW).attr('y1', y).attr('y2', y)
        .attr('stroke', C.border).attr('stroke-width', 0.5).attr('stroke-dasharray', '2,4');
      svg.append('text').attr('x', pad.l - 5).attr('y', y + 4).attr('text-anchor', 'end')
        .attr('fill', C.dim).attr('font-size', 7.5).attr('font-family', FM).text((v / 1000).toFixed(0) + 'k');
    });

    // Producers line (green)
    const lineP = d3.line().x((d, i) => xScale(years[i])).y(d => yScaleP(d)).curve(d3.curveMonotoneX);
    svg.append('path').datum(produtores).attr('fill', 'none').attr('stroke', C.green)
      .attr('stroke-width', 2).attr('d', lineP);
    produtores.forEach((v, i) => {
      svg.append('circle').attr('cx', xScale(years[i])).attr('cy', yScaleP(v)).attr('r', 3.5)
        .attr('fill', C.green).attr('stroke', '#060809').attr('stroke-width', 1);
    });

    // Subsidy bars (amber, right axis)
    const barW = avW / years.length * 0.35;
    subvencao.forEach((v, i) => {
      const bx = xScale(years[i]) - barW / 2;
      const by = yScaleS(v);
      svg.append('rect').attr('x', bx).attr('y', by).attr('width', barW).attr('height', H - pad.b - by)
        .attr('fill', C.amber).attr('opacity', 0.55).attr('rx', 1);
    });

    // X axis labels
    years.forEach(y => {
      svg.append('text').attr('x', xScale(y)).attr('y', H - 8).attr('text-anchor', 'middle')
        .attr('fill', C.dim).attr('font-size', 8.5).attr('font-family', FM).text(y);
    });

    // Right axis labels
    [0, 200, 400, 557.6].forEach(v => {
      const y = yScaleS(v);
      svg.append('text').attr('x', pad.l + avW + 5).attr('y', y + 4).attr('text-anchor', 'start')
        .attr('fill', C.amber).attr('font-size', 7).attr('font-family', FM).text(v > 500 ? 'R$557M' : v > 0 ? 'R$' + v : '');
    });

    // Legend
    svg.append('rect').attr('x', pad.l).attr('y', 6).attr('width', 10).attr('height', 3).attr('fill', C.green).attr('rx', 1);
    svg.append('text').attr('x', pad.l + 13).attr('y', 13).attr('fill', C.green).attr('font-size', 8).attr('font-family', FM).text('Produtores segurados');
    svg.append('rect').attr('x', pad.l + 125).attr('y', 4).attr('width', 10).attr('height', 8).attr('fill', C.amber).attr('opacity', 0.7).attr('rx', 1);
    svg.append('text').attr('x', pad.l + 138).attr('y', 13).attr('fill', C.amber).attr('font-size', 8).attr('font-family', FM).text('Subvenção (R$ M)');
  })();
}

function renderEnergia() {

  const flowData = [
    { label: 'Sobradinho (NE)', miroc: -32, hadgem: -57 },
    { label: 'Itaipu (Sul/SE)', miroc: -12, hadgem: -40 },
    { label: 'Tucuruí (Norte)', miroc: -34, hadgem: -44 },
    { label: 'Furnas (SE/CO)', miroc: -25, hadgem: -38 },
  ];


  groupedHBar('chart-flow', flowData, ['miroc', 'hadgem'], [C.blue, C.red],
    { keyField: 'label', fmt: v => Math.abs(v).toFixed(0), unit: '%' });

  const energyCostData = [
    { label: 'Linha de base', value: 145 },
    { label: 'MIROC 8.5', value: 1190 },
    { label: 'HadGEM 8.5', value: 2290 },
  ];
  hBar('chart-energy-cost', energyCostData,
    {
      color: d => d.label === 'Linha de base' ? C.blue : d.label === 'MIROC 8.5' ? C.amber : C.red,
      fmt: v => v >= 1000 ? `${(v / 1000).toFixed(2)} tri` : `${v}`, unit: ' R$bi', keyField: 'label', valField: 'value'
    });

  // ── Energia: full 4-scenario cost chart (new ID) ──
  hBar('chart-energy-cost-full', [
    { label: 'Base (sem clima)', value: 151 },
    { label: 'MIROC · RCP 4.5', value: 444 },
    { label: 'MIROC · RCP 8.5', value: 1254 },
    { label: 'HadGEM · RCP 4.5', value: 1856 },
    { label: 'HadGEM · RCP 8.5', value: 2530 },
  ], {
    color: d => {
      if (d.label.startsWith('Base')) return C.blue;
      if (d.label.includes('MIROC') && d.label.includes('4.5')) return C.green;
      if (d.label.includes('MIROC')) return C.amber;
      if (d.label.includes('4.5')) return '#c084fc';
      return C.red;
    },
    fmt: v => v >= 1000 ? `${(v / 1000).toFixed(2)} tri` : `${v}`,
    unit: ' R$bi', keyField: 'label', valField: 'value'
  });

  // ── Energia: deficit risk by scenario ──
  hBar('chart-deficit-scenarios', [
    { label: 'Base (sem clima)', value: 5 },
    { label: 'MIROC · RCP 4.5', value: 34 },
    { label: 'MIROC · RCP 8.5', value: 65 },
    { label: 'HadGEM · RCP 4.5', value: 86 },
    { label: 'HadGEM · RCP 8.5', value: 99 },
  ], {
    color: d => {
      const v = d.value;
      if (v <= 5) return C.blue;
      if (v <= 34) return C.green;
      if (v <= 65) return C.amber;
      return C.red;
    },
    fmt: v => v, unit: '%', keyField: 'label', valField: 'value'
  });
  // Add a 5% reference line annotation
  (function () {
    const el = document.getElementById('chart-deficit-scenarios');
    if (!el || !el.querySelector('svg')) return;
    const svg = el.querySelector('svg');
    const W = +svg.getAttribute('width') || 380;
    const viewBox = svg.getAttribute('viewBox').split(' ');
    const vW = +viewBox[2];
    // Draw reference line at 5% — approximate x position
    const pad = { l: 130, r: 60 };
    const domain = [0, 99];
    const scale = (vW - pad.l - pad.r) / (domain[1] - domain[0]);
    const x5 = pad.l + 5 * scale;
    const H = +viewBox[3];
    const ns = 'http://www.w3.org/2000/svg';
    const line = document.createElementNS(ns, 'line');
    line.setAttribute('x1', x5); line.setAttribute('x2', x5);
    line.setAttribute('y1', 4); line.setAttribute('y2', H - 8);
    line.setAttribute('stroke', '#3dd98a'); line.setAttribute('stroke-width', '1');
    line.setAttribute('stroke-dasharray', '3,3');
    svg.appendChild(line);
    const lbl = document.createElementNS(ns, 'text');
    lbl.setAttribute('x', x5 + 3); lbl.setAttribute('y', 13);
    lbl.setAttribute('fill', '#3dd98a'); lbl.setAttribute('font-size', '8');
    lbl.setAttribute('font-family', FM);
    lbl.textContent = 'limite 5%';
    svg.appendChild(lbl);
  })();

  // ── Energia: adaptation investment by scenario ──
  hBar('chart-adapt-invest', [
    { label: 'MIROC · RCP 4.5', value: 3 },
    { label: 'MIROC · RCP 8.5', value: 79 },
    { label: 'HadGEM · RCP 4.5', value: 158 },
    { label: 'HadGEM · RCP 8.5', value: 280 },
  ], {
    color: d => {
      if (d.value <= 3) return C.green;
      if (d.value <= 79) return C.amber;
      return C.red;
    },
    fmt: v => v, unit: ' US$bi', keyField: 'label', valField: 'value'
  });

  

}

function renderHidro() {
  const enaData = [
    { label: 'Sobradinho (NE)', p1: -20, p2: -35, p3: -50 },
    { label: 'Tucuruí (Norte)', p1: -30, p2: -45, p3: -60 },
    { label: 'Furnas (SE/CO)', p1: -15, p2: -25, p3: -35 },
    { label: 'Setor Sul', p1: +10, p2: +30, p3: +60 },
    { label: 'Paraguai (SE)', p1: +5, p2: +10, p3: +15 },
  ];
  groupedHBar('chart-ena', enaData, ['p1', 'p2', 'p3'], ['#5ba3f5', '#f5a623', '#f05252'],
    { keyField: 'label', fmt: v => Math.abs(v).toFixed(0), unit: '%' });

  simpleBar('chart-temp', [
    { label: 'Centro-Oeste', value: 2.5 }, { label: 'Amazônia', value: 1.5 },
    { label: 'Centro-Sul', value: 1.5 }, { label: 'Nordeste', value: 1.0 },
  ], { color: C.red, fmt: v => v.toFixed(1), unit: '°C' });
  
  // ── Hidro: Temperature timeline — 3 periods, 2 models ──
  (function () {
    const r = mkSvg('chart-temp-timeline', 130, 560); if (!r) return;
    const { svg, W, H } = r;
    const periods = ['2010–2040', '2041–2070', '2071–2099'];
    const hadgem = [2.5, 4.0, 6.0];
    const miroc = [1.5, 2.5, 4.0];
    const pad = { l: 70, r: 40, t: 20, b: 28 };
    const x = d3.scaleBand().domain(periods).range([pad.l, W - pad.r]).padding(.32);
    const y = d3.scaleLinear().domain([0, 7]).range([H - pad.b, pad.t]);
    [2, 4, 6].forEach(v => {
      svg.append('line').attr('x1', pad.l).attr('x2', W - pad.r).attr('y1', y(v)).attr('y2', y(v))
        .attr('stroke', C.border).attr('stroke-width', .6).attr('stroke-dasharray', '3,3');
      svg.append('text').attr('x', pad.l - 6).attr('y', y(v) + 4).attr('text-anchor', 'end')
        .attr('fill', C.muted).attr('font-size', 9).attr('font-family', FM).text('+' + v + '°C');
    });
    periods.forEach((p, i) => {
      const bW = x.bandwidth() / 2 - 2;
      svg.append('rect').attr('x', x(p)).attr('y', y(hadgem[i])).attr('width', bW).attr('height', H - pad.b - y(hadgem[i]))
        .attr('fill', C.red).attr('rx', 3).attr('opacity', .82);
      svg.append('text').attr('x', x(p) + bW / 2).attr('y', y(hadgem[i]) - 4).attr('text-anchor', 'middle')
        .attr('fill', C.red).attr('font-size', 9).attr('font-family', FM).attr('font-weight', '600').text('+' + hadgem[i] + '°C');
      svg.append('rect').attr('x', x(p) + bW + 4).attr('y', y(miroc[i])).attr('width', bW).attr('height', H - pad.b - y(miroc[i]))
        .attr('fill', C.blue).attr('rx', 3).attr('opacity', .82);
      svg.append('text').attr('x', x(p) + bW + 4 + bW / 2).attr('y', y(miroc[i]) - 4).attr('text-anchor', 'middle')
        .attr('fill', C.blue).attr('font-size', 9).attr('font-family', FM).attr('font-weight', '600').text('+' + miroc[i] + '°C');
      svg.append('text').attr('x', x(p) + x.bandwidth() / 2).attr('y', H - 4).attr('text-anchor', 'middle')
        .attr('fill', C.muted).attr('font-size', 9).attr('font-family', FM).text(p);
    });
    svg.append('rect').attr('x', pad.l).attr('y', 4).attr('width', 10).attr('height', 10).attr('fill', C.red).attr('rx', 2);
    svg.append('text').attr('x', pad.l + 14).attr('y', 13).attr('fill', C.muted).attr('font-size', 9).attr('font-family', FM).text('HadGEM2-ES');
    svg.append('rect').attr('x', pad.l + 88).attr('y', 4).attr('width', 10).attr('height', 10).attr('fill', C.blue).attr('rx', 2);
    svg.append('text').attr('x', pad.l + 102).attr('y', 13).attr('fill', C.muted).attr('font-size', 9).attr('font-family', FM).text('MIROC5');
  })();

  // ── Hidro: Mann-Kendall historical trends ──
  (function () {
    const r = mkSvg('chart-mk-trend', 150, 340); if (!r) return;
    const { svg, W, H } = r;
    const data = [
      { label: 'Sul', trend: +1, pct: +18, sig: true },
      { label: 'Sudeste', trend: +1, pct: +12, sig: true },
      { label: 'Centro-Oeste', trend: +1, pct: +8, sig: false },
      { label: 'Norte', trend: -1, pct: -6, sig: false },
      { label: 'Nordeste', trend: -1, pct: -9, sig: true },
    ];
    const labW = 100, pad = { r: 60, t: 8, b: 18 };
    const maxV = 18;
    const halfW = (W - labW - pad.r) / 2;
    const midX = labW + halfW;
    const rowH = (H - pad.t - pad.b) / data.length;
    svg.append('line').attr('x1', midX).attr('x2', midX).attr('y1', pad.t).attr('y2', H - pad.b)
      .attr('stroke', C.border2).attr('stroke-width', 1);
    const scale = d3.scaleLinear().domain([0, maxV]).range([0, halfW]);
    data.forEach((d, i) => {
      const y = pad.t + i * rowH + rowH / 2;
      const bH = Math.min(rowH * 0.55, 16);
      const color = d.trend > 0 ? C.green : C.red;
      const bW = scale(Math.abs(d.pct));
      const bX = d.trend > 0 ? midX : midX - bW;
      svg.append('rect').attr('x', bX).attr('y', y - bH / 2).attr('width', bW).attr('height', bH)
        .attr('fill', color).attr('rx', 3).attr('opacity', .8);
      svg.append('text').attr('x', labW - 6).attr('y', y + 4).attr('text-anchor', 'end')
        .attr('fill', d.sig ? C.text : C.muted).attr('font-size', 10.5).attr('font-family', FM).text(d.label);
      const valX = d.trend > 0 ? midX + bW + 4 : midX - bW - 4;
      const anchor = d.trend > 0 ? 'start' : 'end';
      svg.append('text').attr('x', valX).attr('y', y + 4).attr('text-anchor', anchor)
        .attr('fill', color).attr('font-size', 9.5).attr('font-family', FM).attr('font-weight', '600')
        .text((d.trend > 0 ? '+' : '') + d.pct + '%' + (d.sig ? ' ✓' : ''));
    });
    svg.append('text').attr('x', midX).attr('y', H - 2).attr('text-anchor', 'middle')
      .attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM).text('↑ aumento   ↓ redução · ✓ significativo');
  })();

  // ── Hidro: Precipitation contrast South vs. NE ──
  (function () {
    const r = mkSvg('chart-precip-contrast', 150, 340); if (!r) return;
    const { svg, W, H } = r;
    const data = [
      { label: 'Sul · MIROC 8.5', val: +50, color: C.green },
      { label: 'Sul · HadGEM 8.5', val: -15, color: C.red },
      { label: 'NE · MIROC 8.5', val: -35, color: C.amber },
      { label: 'NE · HadGEM 8.5', val: -50, color: C.red },
    ];
    const labW = 130, pad = { r: 55, t: 8, b: 8 };
    const maxV = 50;
    const scale = d3.scaleLinear().domain([0, maxV]).range([0, W - labW - pad.r]);
    const rowH = (H - pad.t - pad.b) / data.length;
    data.forEach((d, i) => {
      const y = pad.t + i * rowH + rowH * 0.15;
      const bH = rowH * 0.6;
      const bW = scale(Math.abs(d.val));
      svg.append('rect').attr('x', labW).attr('y', y).attr('width', bW).attr('height', bH)
        .attr('fill', d.color).attr('rx', 3).attr('opacity', .82);
      svg.append('text').attr('x', labW - 6).attr('y', y + bH / 2 + 4).attr('text-anchor', 'end')
        .attr('fill', C.muted).attr('font-size', 9.5).attr('font-family', FM).text(d.label);
      svg.append('text').attr('x', labW + bW + 5).attr('y', y + bH / 2 + 4)
        .attr('fill', d.color).attr('font-size', 10).attr('font-family', FM).attr('font-weight', '600')
        .text((d.val > 0 ? '+' : '') + d.val + '%');
    });
  })();

  const enaEl = document.getElementById('chart-ena');
  if (enaEl) {
    const leg = document.createElement('div'); leg.className = 'legend'; leg.style.marginTop = '8px';
    leg.innerHTML = `
    <div class="leg-item"><div class="leg-dot" style="background:#5ba3f5"></div>2011–2040</div>
    <div class="leg-item"><div class="leg-dot" style="background:#f5a623"></div>2041–2070</div>
    <div class="leg-item"><div class="leg-dot" style="background:#f05252"></div>2071–2099</div>`;
    enaEl.appendChild(leg);
  }

}

function renderTransp() {
  // ── Transportes: Road condition breakdown ──
  (function () {
    const r = mkSvg('chart-road-condition', 130, 340); if (!r) return;
    const { svg, W, H } = r;
    const data = [
      { category: 'Sinalização', otimo: 2, bom: 18, regular: 75, ruim: 5 },
      { category: 'Geometria', otimo: 1, bom: 12, regular: 65, ruim: 22 },
    ];
    const colors = { otimo: C.green, bom: '#3ca85a', regular: C.amber, ruim: C.red };
    const labW = 88, pad = { r: 10, t: 22, b: 8 };
    const rowH = (H - pad.t - pad.b) / data.length;
    // legend at top
    Object.entries({ Ótimo: C.green, Bom: '#3ca85a', Regular: C.amber, Ruim: C.red }).forEach(([k, c], i) => {
      svg.append('rect').attr('x', labW + i * 68).attr('y', 4).attr('width', 8).attr('height', 8).attr('fill', c).attr('rx', 2);
      svg.append('text').attr('x', labW + i * 68 + 11).attr('y', 12).attr('fill', C.muted).attr('font-size', 8.5).attr('font-family', FM).text(k);
    });
    data.forEach((d, i) => {
      const y = pad.t + i * rowH + rowH * 0.15;
      const bH = rowH * 0.6;
      const total = d.otimo + d.bom + d.regular + d.ruim;
      const avW = W - labW - pad.r;
      let x = labW;
      [['otimo', d.otimo], ['bom', d.bom], ['regular', d.regular], ['ruim', d.ruim]].forEach(([k, v]) => {
        const w = (v / total) * avW;
        svg.append('rect').attr('x', x).attr('y', y).attr('width', w).attr('height', bH).attr('fill', colors[k]).attr('opacity', .85);
        if (w > 20) {
          svg.append('text').attr('x', x + w / 2).attr('y', y + bH / 2 + 4).attr('text-anchor', 'middle')
            .attr('fill', C.muted).attr('font-size', 9).attr('font-family', FM).attr('font-weight', '600').text(v + '%');
        }
        x += w;
      });
      svg.append('text').attr('x', labW - 6).attr('y', y + bH / 2 + 4).attr('text-anchor', 'end')
        .attr('fill', C.text).attr('font-size', 10.5).attr('font-family', FM).text(d.category);
    });
  })();

  // ── Transportes: IVIR weights donut-style bars ──
  (function () {
    const r = mkSvg('chart-ivir-weights', 130, 340); if (!r) return;
    const { svg, W, H } = r;
    const data = [
      { label: 'Exposição hotspot', val: 36, color: C.red, group: 'Sensibilidade' },
      { label: 'Gestão (DNIT/conc.)', val: 28, color: C.blue, group: 'Cap. Adaptativa' },
      { label: 'Localização (PIB UF)', val: 20, color: '#a78bfa', group: 'Cap. Adaptativa' },
      { label: 'Tipo de superfície', val: 6, color: C.amber, group: 'Sensibilidade' },
      { label: 'Tráfego (VMD)', val: 4, color: C.green, group: 'Cap. Adaptativa' },
      { label: 'IGG + IRI + outros', val: 6, color: C.muted, group: 'Sensibilidade' },
    ];
    const labW = 148, pad = { r: 55, t: 6, b: 6 };
    const maxV = 36;
    const scale = d3.scaleLinear().domain([0, maxV]).range([0, W - labW - pad.r]);
    const rowH = (H - pad.t - pad.b) / data.length;
    data.forEach((d, i) => {
      const y = pad.t + i * rowH + rowH * 0.12;
      const bH = rowH * 0.65;
      const bW = scale(d.val);
      svg.append('rect').attr('x', labW).attr('y', y).attr('width', bW).attr('height', bH)
        .attr('fill', d.color).attr('rx', 3).attr('opacity', .82);
      svg.append('text').attr('x', labW - 6).attr('y', y + bH / 2 + 4).attr('text-anchor', 'end')
        .attr('fill', C.muted).attr('font-size', 9.5).attr('font-family', FM).text(d.label);
      svg.append('text').attr('x', labW + bW + 5).attr('y', y + bH / 2 + 4)
        .attr('fill', d.color).attr('font-size', 10).attr('font-family', FM).attr('font-weight', '600').text(d.val + '%');
    });
  })();

  simpleBar('chart-hotspot', [
    { label: 'Equatorial (HadGEM)', value: 98 }, { label: 'Equatorial (MIROC)', value: 98 },
    { label: 'Brasil Central (HadGEM)', value: 93 }, { label: 'Brasil Central (MIROC)', value: 48 },
    { label: 'NE Oriental (HadGEM)', value: 60 }, { label: 'NE Oriental (MIROC)', value: 30 },
    { label: 'Temperado (HadGEM)', value: 47 }, { label: 'Temperado (MIROC)', value: 7 },
  ], { color: d => d.label.includes('HadGEM') ? C.red : C.blue, fmt: v => v, unit: '%' });

  (function () {
    const r = mkSvg('chart-vuln', 120, 340); if (!r) return;
    const { svg, W, H } = r;
    const data = [{ label: 'Presente', val: 8, color: C.blue }, { label: '2040', val: 22, color: C.red }];
    const x = d3.scaleBand().domain(data.map(d => d.label)).range([60, W - 20]).padding(.35);
    const y = d3.scaleLinear().domain([0, 27]).range([H - 30, 10]);
    data.forEach(d => {
      svg.append('rect').attr('x', x(d.label)).attr('y', y(d.val))
        .attr('width', x.bandwidth()).attr('height', H - 30 - y(d.val)).attr('fill', d.color).attr('rx', 4).attr('opacity', .85);
      svg.append('text').attr('x', x(d.label) + x.bandwidth() / 2).attr('y', y(d.val) - 5)
        .attr('text-anchor', 'middle').attr('fill', d.color)
        .attr('font-family', FM).attr('font-size', 16).attr('font-weight', '600')
        .text(d.val + ' UF');
      svg.append('text').attr('x', x(d.label) + x.bandwidth() / 2).attr('y', H - 14)
        .attr('text-anchor', 'middle').attr('fill', C.muted)
        .attr('font-family', FM).attr('font-size', 11).text(d.label);
    });
    svg.append('text').attr('x', 30).attr('y', 60).attr('text-anchor', 'middle')
      .attr('fill', C.muted).attr('font-family', FM).attr('font-size', 10)
      .attr('transform', 'rotate(-90,30,60)').text('Estados (IVIR alta/muito alta)');
  })();

  // ── Transp: International maintenance cost comparison ──
  (function () {
    const data = [
      { label: 'Brasil (projetado)', pct: 40, note: 'estimativa base estudos', color: C.amber },
      { label: 'Austrália (+T ap. 2100)', pct: 57, note: 'estudo oficial', color: C.red },
      { label: 'França (dobramento)', pct: 100, note: 'previsão governamental', color: C.red },
    ];
    const H = 110, pad = { t: 18, b: 18, l: 168, r: 56 };
    const r = mkSvg('chart-intl-maint', H, 380); if (!r) return;
    const { svg, W } = r;
    const avW = W - pad.l - pad.r;
    const scale = d3.scaleLinear().domain([0, 110]).range([0, avW]);
    const rowH = (H - pad.t - pad.b) / data.length;

    svg.append('text').attr('x', pad.l).attr('y', 12).attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM)
      .text('Aumento projetado nos custos de manutenção por mudanças climáticas (%)');

    data.forEach((d, i) => {
      const y = pad.t + i * rowH + rowH * 0.1;
      const bH = rowH * 0.65;
      svg.append('rect').attr('x', pad.l).attr('y', y).attr('width', scale(d.pct)).attr('height', bH)
        .attr('fill', d.color).attr('rx', 2).attr('opacity', 0.8);
      svg.append('text').attr('x', pad.l - 6).attr('y', y + bH / 2 + 4).attr('text-anchor', 'end')
        .attr('fill', C.muted).attr('font-size', 9.5).attr('font-family', FM).text(d.label);
      svg.append('text').attr('x', pad.l + scale(d.pct) + 5).attr('y', y + bH / 2 + 4)
        .attr('fill', d.color).attr('font-size', 10).attr('font-family', FM).attr('font-weight', '600')
        .text('+' + d.pct + '%');
      svg.append('text').attr('x', W - pad.r + 2).attr('y', y + bH / 2 + 4)
        .attr('fill', C.dim).attr('font-size', 7.5).attr('font-family', FM).text(d.note);
    });
  })();

  // ── Transp: Road network breakdown ──
  (function () {
    const H = 120, pad = { t: 18, b: 18, l: 42, r: 18 };
    const r = mkSvg('chart-road-network', H, 340); if (!r) return;
    const { svg, W } = r;
    const avW = W - pad.l - pad.r;
    const total = 1713885;
    const segs = [
      { label: 'Pavimentada', km: total * 0.118, color: C.blue },
      { label: 'Não pavim. (terra)', km: total * 0.882, color: C.red },
    ];
    const concSession = [
      { label: 'Concessão (>resposta)', km: total * 0.118 * 0.11, color: C.green },
      { label: 'DNIT (≤resposta)', km: total * 0.118 * 0.88, color: C.amber },
    ];
    const allSegs = [...segs, ...concSession];
    const scale = d3.scaleLinear().domain([0, total]).range([0, avW]);

    // Total strip
    svg.append('text').attr('x', pad.l).attr('y', 12).attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM)
      .text('Total: 1.713.885 km');

    let cx = pad.l;
    segs.forEach(s => {
      const bw = scale(s.km);
      svg.append('rect').attr('x', cx).attr('y', 20).attr('width', bw).attr('height', 18)
        .attr('fill', s.color).attr('opacity', 0.8);
      if (bw > 40) {
        svg.append('text').attr('x', cx + bw / 2).attr('y', 32).attr('text-anchor', 'middle')
          .attr('fill', C.muted).attr('font-size', 8.5).attr('font-family', FM).attr('font-weight', '600')
          .text(s.label);
      }
      cx += bw;
    });

    // Zoom in on paved portion
    const pavedW = scale(segs[0].km);
    svg.append('text').attr('x', pad.l).attr('y', 56).attr('fill', C.muted).attr('font-size', 8).attr('font-family', FM)
      .text('↳ Da malha pavimentada:');
    cx = pad.l;
    concSession.forEach(s => {
      const bw = (s.km / segs[0].km) * pavedW;
      svg.append('rect').attr('x', cx).attr('y', 62).attr('width', bw).attr('height', 14)
        .attr('fill', s.color).attr('opacity', 0.8);
      svg.append('text').attr('x', cx + bw / 2).attr('y', 72).attr('text-anchor', 'middle')
        .attr('fill', C.muted).attr('font-size', 7.5).attr('font-family', FM)
        .text(s.label.split('(')[0].trim());
      cx += bw;
    });

    // Stats below
    svg.append('text').attr('x', pad.l).attr('y', 95).attr('fill', C.red).attr('font-size', 9.5).attr('font-family', FM).attr('font-weight', '600')
      .text('88,2% não pavimentada — base de partida crítica');
    svg.append('text').attr('x', pad.l).attr('y', 110).attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM)
      .text('Densidade: Brasil 23,8 km/1.000 km² · EUA 445 km/1.000 km²');
  })();

}

function renderCosta() {
  // ── Costa: Sediment transport increase by port ──
  (function () {
    const r = mkSvg('chart-sediment', 140, 340); if (!r) return;
    const { svg, W, H } = r;
    const data = [
      { label: 'Rio Grande (RS)', y2015: 60, y2030: 75, y2050: 97 },
      { label: 'Imbituba (SC)', y2015: 40, y2030: 52, y2050: 68 },
      { label: 'Tubarão (ES)', y2015: 30, y2030: 40, y2050: 55 },
      { label: 'Mucuripe (CE)', y2015: 28, y2030: 32, y2050: 41 },
    ];
    const labW = 108, pad = { r: 40, t: 22, b: 8 };
    const maxV = 97;
    const avW = W - labW - pad.r;
    const scale = d3.scaleLinear().domain([0, maxV]).range([0, avW]);
    const rowH = (H - pad.t - pad.b) / data.length;
    // legend
    const cols = [{ k: 'y2015', c: C.blue, l: '2015' }, { k: 'y2030', c: C.amber, l: '2030' }, { k: 'y2050', c: C.red, l: '2050' }];
    cols.forEach((c, i) => {
      svg.append('rect').attr('x', labW + i * 58).attr('y', 4).attr('width', 8).attr('height', 8).attr('fill', c.c).attr('rx', 2);
      svg.append('text').attr('x', labW + i * 58 + 11).attr('y', 12).attr('fill', C.muted).attr('font-size', 8.5).attr('font-family', FM).text(c.l);
    });
    data.forEach((d, i) => {
      const y0 = pad.t + i * rowH;
      const subH = (rowH - 4) / 3;
      svg.append('text').attr('x', labW - 6).attr('y', y0 + rowH / 2 + 4).attr('text-anchor', 'end')
        .attr('fill', C.muted).attr('font-size', 9.5).attr('font-family', FM).text(d.label);
      cols.forEach((c, j) => {
        const bW = scale(d[c.k]);
        const y = y0 + j * subH + 2;
        svg.append('rect').attr('x', labW).attr('y', y).attr('width', bW).attr('height', subH - 1)
          .attr('fill', c.c).attr('rx', 2).attr('opacity', .82);
        svg.append('text').attr('x', labW + bW + 4).attr('y', y + subH / 2 + 3)
          .attr('fill', c.c).attr('font-size', 8.5).attr('font-family', FM).attr('font-weight', '600').text('+' + d[c.k] + '%');
      });
    });
  })();

  // ── Costa: IVCB city comparison ──
  (function () {
    const r = mkSvg('chart-ivcb-compare', 130, 340); if (!r) return;
    const { svg, W, H } = r;
    // stacked percentage bars: RJ vs Santos, levels 1-5
    const cities = [
      { name: 'Rio de Janeiro', v: [5, 15, 48, 28, 4] },
      { name: 'Santos', v: [2, 6, 24, 45, 23] },
    ];
    const colors5 = ['#3dd98a', '#76d98a', '#f5a623', '#f06b52', '#f05252'];
    const labW = 110, pad = { r: 40, t: 22, b: 8 };
    const avW = W - labW - pad.r;
    const rowH = (H - pad.t - pad.b) / cities.length;
    // legend
    ['Muito Baixa', 'Baixa', 'Média', 'Alta', 'Muito Alta'].forEach((l, i) => {
      svg.append('rect').attr('x', labW + (i % 5) * ((avW) / 5)).attr('y', 4).attr('width', 7).attr('height', 7).attr('fill', colors5[i]).attr('rx', 1);
      if (i < 3) svg.append('text').attr('x', labW + (i % 5) * ((avW) / 5) + 10).attr('y', 12).attr('fill', C.muted).attr('font-size', 7.5).attr('font-family', FM).text(l);
    });
    cities.forEach((c, i) => {
      const y = pad.t + i * rowH + rowH * 0.1;
      const bH = rowH * 0.65;
      let x = labW;
      c.v.forEach((pct, j) => {
        const bW = (pct / 100) * avW;
        svg.append('rect').attr('x', x).attr('y', y).attr('width', bW).attr('height', bH)
          .attr('fill', colors5[j]).attr('opacity', .88);
        if (bW > 16) {
          svg.append('text').attr('x', x + bW / 2).attr('y', y + bH / 2 + 4).attr('text-anchor', 'middle')
            .attr('fill', C.muted).attr('font-size', 8.5).attr('font-family', FM).attr('font-weight', '600').text(pct + '%');
        }
        x += bW;
      });
      svg.append('text').attr('x', labW - 6).attr('y', y + bH / 2 + 4).attr('text-anchor', 'end')
        .attr('fill', C.text).attr('font-size', 10).attr('font-family', FM).text(c.name);
    });
  })();

  // ── Costa: IVCB indicator weights ──
  (function () {
    const r = mkSvg('chart-ivcb-weights', 110, 560); if (!r) return;
    const { svg, W, H } = r;
    const data = [
      { label: 'Tipo de Ocupação', val: 22, color: C.red, group: 'Social' },
      { label: 'Densidade Demog.', val: 13, color: '#a78bfa', group: 'Social' },
      { label: 'Nível Socioeconômico', val: 13, color: '#a78bfa', group: 'Social' },
      { label: 'Movimentos de Massa', val: 13, color: C.amber, group: 'Físico' },
      { label: 'Exposição Ondas/Marés', val: 13, color: C.blue, group: 'Físico' },
      { label: 'Erosão Costeira', val: 13, color: C.blue, group: 'Físico' },
      { label: 'Inundação', val: 13, color: C.blue, group: 'Físico' },
    ];
    const labW = 160, pad = { r: 60, t: 8, b: 10 };
    const maxV = 22;
    const scale = d3.scaleLinear().domain([0, maxV]).range([0, W - labW - pad.r]);
    const rowH = (H - pad.t - pad.b) / data.length;
    data.forEach((d, i) => {
      const y = pad.t + i * rowH + rowH * 0.1;
      const bH = rowH * 0.7;
      const bW = scale(d.val);
      svg.append('rect').attr('x', labW).attr('y', y).attr('width', bW).attr('height', bH)
        .attr('fill', d.color).attr('rx', 3).attr('opacity', .82);
      svg.append('text').attr('x', labW - 6).attr('y', y + bH / 2 + 4).attr('text-anchor', 'end')
        .attr('fill', C.muted).attr('font-size', 9.5).attr('font-family', FM).text(d.label);
      svg.append('text').attr('x', labW + bW + 5).attr('y', y + bH / 2 + 4)
        .attr('fill', d.color).attr('font-size', 10).attr('font-family', FM).attr('font-weight', '600').text(d.val + '%');
      // group badge
      const badgeX = W - pad.r + 2;
      if (i === 0 || i === 3) {
        svg.append('text').attr('x', badgeX).attr('y', y + bH / 2 + 4)
          .attr('fill', d.group === 'Social' ? '#a78bfa' : C.blue).attr('font-size', 8).attr('font-family', FM).text(d.group);
      }
    });
  })();

  simpleBar('chart-waves', [
    { label: 'Rio Grande (RS)', value: 35.2 }, { label: 'Tubarão (ES)', value: 24.7 },
    { label: 'Imbituba (SC)', value: 25.7 }, { label: 'Santos (SP)', value: 18.4 },
    { label: 'Recife (PE)', value: 16.7 }, { label: 'Mucuripe (CE)', value: 14.4 },
  ], { color: C.blue, fmt: v => '+' + v.toFixed(1), unit: '%' });

  hBar('chart-port-cost', [
    { label: 'Emergencial', value: 0.013 }, { label: 'Até 2030', value: 1.66 }, { label: 'Até 2050', value: 7.25 },
  ], {
    color: d => d.label === 'Até 2050' ? C.red : d.label === 'Até 2030' ? C.amber : C.blue,
    fmt: v => v < 0.1 ? `${(v * 1000).toFixed(0)} M` : `${v.toFixed(2)} bi`, unit: ' R$', keyField: 'label', valField: 'value'
  });


  // ── Costa: Borda livre comparison chart ──
  (function () {
    const ports = [
      { label: 'Rio Grande', bl: 1.22, elev30: 0.42, elev50: 0.56 },
      { label: 'Paranaguá', bl: 1.60, elev30: 0.33, elev50: 0.46 },
      { label: 'Santos', bl: 1.18, elev30: 0.40, elev50: 0.54 },
      { label: 'Vitória', bl: 1.45, elev30: 0.40, elev50: 0.54 },
      { label: 'Rio de Janeiro', bl: 1.32, elev30: 0.36, elev50: 0.48 },
      { label: 'Recife', bl: 1.05, elev30: 0.53, elev50: 0.70 },
    ];
    const H = 200, pad = { t: 28, b: 20, l: 105, r: 32 };
    const r = mkSvg('chart-borda-livre', H, 380); if (!r) return;
    const { svg, W } = r;
    const avW = W - pad.l - pad.r;
    const scale = d3.scaleLinear().domain([0, 2.1]).range([0, avW]);
    const rowH = (H - pad.t - pad.b) / ports.length;
    const INTL_MIN = 1.5;

    // International minimum reference line
    const refX = pad.l + scale(INTL_MIN);
    svg.append('line').attr('x1', refX).attr('x2', refX).attr('y1', pad.t - 18).attr('y2', H - pad.b)
      .attr('stroke', C.amber).attr('stroke-width', 1).attr('stroke-dasharray', '4,3');
    svg.append('text').attr('x', refX + 3).attr('y', pad.t - 6).attr('fill', C.amber).attr('font-size', 8).attr('font-family', FM)
      .text('Mín. PIANC 1,5 m');

    // Scale ticks
    [0, 0.5, 1.0, 1.5, 2.0].forEach(v => {
      const x = pad.l + scale(v);
      svg.append('text').attr('x', x).attr('y', H - 5).attr('text-anchor', 'middle')
        .attr('fill', C.dim).attr('font-size', 7.5).attr('font-family', FM).text(v.toFixed(1) + 'm');
    });

    ports.forEach((p, i) => {
      const y = pad.t + i * rowH;
      const bH = rowH * 0.55;
      const isBelow = p.bl < INTL_MIN;

      // Borda livre bar
      const blW = scale(p.bl);
      svg.append('rect').attr('x', pad.l).attr('y', y + 2).attr('width', blW).attr('height', bH)
        .attr('fill', isBelow ? C.red : C.blue).attr('rx', 2).attr('opacity', 0.8);

      // Elevation 2030 overlay (shows erosion of margin)
      const el30x = pad.l + scale(p.bl - p.elev30);
      const el30w = scale(p.elev30);
      svg.append('rect').attr('x', Math.max(pad.l, el30x)).attr('y', y + 2)
        .attr('width', Math.min(el30w, blW)).attr('height', bH)
        .attr('fill', C.amber).attr('rx', 2).attr('opacity', 0.55);

      // Label
      svg.append('text').attr('x', pad.l - 6).attr('y', y + bH / 2 + 6).attr('text-anchor', 'end')
        .attr('fill', isBelow ? C.red : C.muted).attr('font-size', 9.5).attr('font-family', FM)
        .attr('font-weight', isBelow ? '600' : '400').text(p.label);

      svg.append('text').attr('x', pad.l + blW + 5).attr('y', y + bH / 2 + 6)
        .attr('fill', isBelow ? C.red : C.blue).attr('font-size', 9).attr('font-family', FM).attr('font-weight', '600')
        .text(p.bl.toFixed(2) + 'm' + (isBelow ? ' ⚠' : ''));
    });

    // Legend
    const legY = pad.t - 14;
    svg.append('rect').attr('x', pad.l).attr('y', legY - 7).attr('width', 10).attr('height', 7).attr('fill', C.blue).attr('opacity', 0.8);
    svg.append('text').attr('x', pad.l + 13).attr('y', legY).attr('fill', C.dim).attr('font-size', 7.5).attr('font-family', FM).text('Borda livre atual');
    svg.append('rect').attr('x', pad.l + 100).attr('y', legY - 7).attr('width', 10).attr('height', 7).attr('fill', C.amber).attr('opacity', 0.7);
    svg.append('text').attr('x', pad.l + 113).attr('y', legY).attr('fill', C.dim).attr('font-size', 7.5).attr('font-family', FM).text('Margem consumida até 2030');
  })();

  // ── Costa: Santos precipitation events timeline ──
  (function () {
    const H = 160, pad = { t: 24, b: 28, l: 44, r: 20 };
    const r = mkSvg('chart-santos-events', H, 340); if (!r) return;
    const { svg, W } = r;
    const avW = W - pad.l - pad.r;
    const decades = [
      { period: '2000–2010', events: 38, label: 'histórico' },
      { period: '2010–2020', events: 52, label: 'tendência' },
      { period: '2020–2030', events: 88, label: 'projetado', proj: true },
      { period: '2030–2040', events: 125, label: 'projetado', proj: true },
    ];
    const xScale = d3.scaleBand().domain(decades.map(d => d.period)).range([pad.l, pad.l + avW]).padding(0.28);
    const yScale = d3.scaleLinear().domain([0, 140]).range([H - pad.b, pad.t]);

    // Y axis
    [0, 50, 100, 125].forEach(v => {
      const y = yScale(v);
      svg.append('line').attr('x1', pad.l).attr('x2', pad.l + avW).attr('y1', y).attr('y2', y)
        .attr('stroke', C.border).attr('stroke-width', 0.5).attr('stroke-dasharray', '2,4');
      svg.append('text').attr('x', pad.l - 4).attr('y', y + 4).attr('text-anchor', 'end')
        .attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM).text(v);
    });

    // Bars
    decades.forEach(d => {
      const bx = xScale(d.period);
      const by = yScale(d.events);
      const bw = xScale.bandwidth();
      const color = d.proj ? (d.events >= 100 ? C.red : C.amber) : C.blue;
      svg.append('rect').attr('x', bx).attr('y', by).attr('width', bw).attr('height', H - pad.b - by)
        .attr('fill', color).attr('rx', 3).attr('opacity', d.proj ? 0.7 : 0.9)
        .attr('stroke-dasharray', d.proj ? '4,3' : 'none').attr('stroke', d.proj ? color : 'none').attr('stroke-width', 1);
      svg.append('text').attr('x', bx + bw / 2).attr('y', by - 4).attr('text-anchor', 'middle')
        .attr('fill', color).attr('font-size', 10).attr('font-family', FM).attr('font-weight', '600').text(d.events);
      svg.append('text').attr('x', bx + bw / 2).attr('y', H - 10).attr('text-anchor', 'middle')
        .attr('fill', d.proj ? C.amber : C.dim).attr('font-size', 8).attr('font-family', FM).text(d.period);
      svg.append('text').attr('x', bx + bw / 2).attr('y', H - 2).attr('text-anchor', 'middle')
        .attr('fill', C.dim).attr('font-size', 7).attr('font-family', FM).text(d.label);
    });

    svg.append('text').attr('x', pad.l).attr('y', 13).attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM)
      .text('Eventos críticos (≥100mm/72h) · Dec. Est. SP 42565/97');
  })();
}

function renderUrb() {
  groupedHBar('chart-drain', [
    { label: 'Rio de Janeiro', miroc: -14, hadgem: +16 },
    { label: 'São Paulo', miroc: -48, hadgem: -37 },
  ], ['miroc', 'hadgem'], [C.blue, C.red], { keyField: 'label', fmt: v => Math.abs(v).toFixed(0), unit: '%' });


  // ── Urb: CN impermeabilização simulation ──
  (function () {
    const r = mkSvg('chart-cn-sim', 140, 340); if (!r) return;
    const { svg, W, H } = r;

    const rows = [
      { city: 'RJ · Canal do Mangue', cnA: 43, cnB: 30, lA: 'CN 87', lB: 'CN 77' },
      { city: 'SP · Córrego Anhangabaú', cnA: 42, cnB: 28, lA: 'CN 88', lB: 'CN 78' },
    ];
    const labW = 148, pad = { r: 52, t: 22, b: 20 };
    const maxV = 52;
    const avW = W - labW - pad.r;
    const scale = d3.scaleLinear().domain([0, maxV]).range([0, avW]);
    const rowH = (H - pad.t - pad.b) / rows.length;

    [0, 10, 20, 30, 40, 50].forEach(v => {
      const x = labW + scale(v);
      svg.append('line').attr('x1', x).attr('x2', x).attr('y1', pad.t).attr('y2', H - pad.b)
        .attr('stroke', C.border).attr('stroke-width', .7).attr('stroke-dasharray', '3,3');
      svg.append('text').attr('x', x).attr('y', H - 6).attr('text-anchor', 'middle')
        .attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM).text(v + 'mm');
    });

    rows.forEach((d, i) => {
      const y0 = pad.t + i * rowH;
      const subH = (rowH - 8) / 2;
      svg.append('text').attr('x', labW - 7).attr('y', y0 + rowH / 2 + 4).attr('text-anchor', 'end')
        .attr('fill', C.muted).attr('font-size', 9).attr('font-family', FM).text(d.city);
      const bWA = scale(d.cnA);
      svg.append('rect').attr('x', labW).attr('y', y0 + 2).attr('width', bWA).attr('height', subH - 1)
        .attr('fill', C.red).attr('rx', 2).attr('opacity', .82);
      svg.append('text').attr('x', labW + bWA + 4).attr('y', y0 + 2 + subH / 2 + 4)
        .attr('fill', C.red).attr('font-size', 9).attr('font-family', FM).attr('font-weight', '600')
        .text(d.cnA + 'mm (' + d.lA + ')');
      const bWB = scale(d.cnB);
      svg.append('rect').attr('x', labW).attr('y', y0 + subH + 5).attr('width', bWB).attr('height', subH - 1)
        .attr('fill', C.green).attr('rx', 2).attr('opacity', .82);
      svg.append('text').attr('x', labW + bWB + 4).attr('y', y0 + subH + 5 + subH / 2 + 4)
        .attr('fill', C.green).attr('font-size', 9).attr('font-family', FM).attr('font-weight', '600')
        .text(d.cnB + 'mm (' + d.lB + ')');
    });
  })();

  // ── Urb: Fortaleza drainage basins ──
  (function () {
    const r = mkSvg('chart-fortaleza-basins', 160, 340); if (!r) return;
    const { svg, W, H } = r;

    const data = [
      { bacia: 'Vertente Marítima', rede: 203.51, area: 34.54, dens: 5.89 },
      { bacia: 'Maranguapinho', rede: 207.89, area: 86.84, dens: 2.39 },
      { bacia: 'Rio Cocó', rede: 108.20, area: 209.63, dens: 0.52 },
      { bacia: 'Rio Pacoti', rede: 0, area: 5.02, dens: 0.0 },
    ];
    const labW = 128, pad = { r: 48, t: 22, b: 12 };
    const maxV = 7;
    const avW = W - labW - pad.r;
    const rowH = (H - pad.t - pad.b) / data.length;
    const scale = d3.scaleLinear().domain([0, maxV]).range([0, avW]);

    svg.append('text').attr('x', labW).attr('y', 14).attr('fill', C.muted).attr('font-size', 8.5)
      .attr('font-family', FM).text('km de rede / km² de bacia →');

    data.forEach((d, i) => {
      const y = pad.t + i * rowH + rowH * 0.12;
      const bH = rowH * 0.65;
      const bW = scale(d.dens);
      const color = d.dens > 4 ? C.red : d.dens > 1.5 ? C.amber : d.dens > 0 ? C.blue : C.dim;
      svg.append('text').attr('x', labW - 7).attr('y', y + bH / 2 + 4).attr('text-anchor', 'end')
        .attr('fill', C.muted).attr('font-size', 9.5).attr('font-family', FM).text(d.bacia);
      svg.append('rect').attr('x', labW).attr('y', y).attr('width', Math.max(bW, 2)).attr('height', bH)
        .attr('fill', color).attr('rx', 2).attr('opacity', .85);
      svg.append('text').attr('x', labW + Math.max(bW, 2) + 5).attr('y', y + bH / 2 + 4)
        .attr('fill', color).attr('font-size', 9.5).attr('font-family', FM).attr('font-weight', '600')
        .text(d.dens > 0 ? d.dens.toFixed(2) : 'sem rede');
      svg.append('text').attr('x', W - pad.r + 2).attr('y', y + bH / 2 + 4)
        .attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM)
        .text(d.rede > 0 ? d.rede.toFixed(0) + 'km' : '0 km');
    });
  })();

  // ── Urb: Data availability matrix ──
  (function () {
    const r = mkSvg('chart-data-matrix', 200, 700); if (!r) return;
    const { svg, W, H, el } = r;
    svg.style('max-width', '100%');
    const cities = ['São Paulo', 'Rio de Janeiro', 'Fortaleza', 'Salvador', 'Recife'];
    const cols = ['MDT', 'Pedologia', 'Uso do Solo', 'Macrodrenagem', 'Precipitação', 'Vazão', 'Áreas de Risco', 'Plano Drenagem'];
    // 0=indisponível  1=parcial  2=disponível
    const matrix = [
      [2, 2, 2, 1, 2, 1, 2, 2],
      [1, 2, 2, 0, 2, 1, 1, 1],
      [1, 0, 0, 2, 1, 0, 1, 2],
      [1, 2, 1, 1, 2, 0, 1, 2],
      [1, 2, 0, 0, 1, 0, 1, 0],
    ];
    const statusColor = [C.red, C.amber, C.green];
    const statusBg = ['rgba(240,82,82,.13)', 'rgba(245,166,35,.13)', 'rgba(61,217,138,.13)'];
    const statusSym = ['✗', '~', '✓'];

    const labW = 118;
    const cellW = (W - labW) / cols.length;
    const hdrH = 44;
    const rowH = (H - hdrH - 22) / cities.length;

    cols.forEach((c, j) => {
      const cx = labW + j * cellW + cellW / 2;
      svg.append('text').attr('x', cx).attr('y', hdrH - 4).attr('text-anchor', 'middle')
        .attr('fill', C.muted).attr('font-size', 8.5).attr('font-family', FM).text(c);
    });

    cities.forEach((city, i) => {
      const y = hdrH + i * rowH;
      const cityColor = i === 4 ? C.red : C.text;
      svg.append('text').attr('x', labW - 8).attr('y', y + rowH / 2 + 4).attr('text-anchor', 'end')
        .attr('fill', cityColor).attr('font-size', 10).attr('font-family', FM).attr('font-weight', '500').text(city);
      matrix[i].forEach((status, j) => {
        const cx = labW + j * cellW;
        const p = 3;
        svg.append('rect').attr('x', cx + p).attr('y', y + p)
          .attr('width', cellW - p * 2).attr('height', rowH - p * 2)
          .attr('fill', statusBg[status]).attr('stroke', statusColor[status])
          .attr('stroke-width', .8).attr('rx', 3).attr('opacity', .9);
        svg.append('text').attr('x', cx + cellW / 2).attr('y', y + rowH / 2 + 4)
          .attr('text-anchor', 'middle').attr('fill', statusColor[status])
          .attr('font-size', 10).attr('font-family', FM).attr('font-weight', '600').text(statusSym[status]);
      });
    });

    const legY = H - 12;
    ['Indisponível', 'Parcial', 'Disponível'].forEach((lbl, i) => {
      const x = labW + i * 120;
      svg.append('rect').attr('x', x).attr('y', legY - 9).attr('width', 10).attr('height', 10)
        .attr('fill', statusColor[i]).attr('rx', 2).attr('opacity', .7);
      svg.append('text').attr('x', x + 14).attr('y', legY).attr('fill', C.dim)
        .attr('font-size', 8.5).attr('font-family', FM).text(lbl);
    });
  })();

  (function () {
    const cities = [
      { city: 'São Paulo', factors: ['Solo CN 88', 'Ilha de calor', 'Mancha urbana +38%'] },
      { city: 'Rio de Janeiro', factors: ['Solo D impermeável', 'Encostas desmatadas', '+16% vazão pico'] },
      { city: 'Fortaleza', factors: ['Topografia plana', 'Chuvas curtas intensas', 'Rede deficiente'] },
      { city: 'Salvador', factors: ['Relevo ondulado', '>300 alag. Bolandeira', 'Dados insuficientes'] },
      { city: 'Recife', factors: ['Planície descaract.', 'Marés + rios', 'Maior déficit de dados'] },
    ];
    const rowH = 55, H = cities.length * rowH + 8;
    const r = mkSvg('chart-cities', H); if (!r) return;
    const { svg, W } = r;
    cities.forEach((c, i) => {
      const y = 4 + i * rowH;
      svg.append('rect').attr('x', 0).attr('y', y).attr('width', W).attr('height', rowH - 4).attr('fill', C.surf).attr('rx', 4);
      svg.append('text').attr('x', 10).attr('y', y + 16)
        .attr('fill', C.text).attr('font-family', FM).attr('font-size', 11).attr('font-weight', '500')
        .text(c.city);
      c.factors.forEach((f, fi) => {
        svg.append('text').attr('x', 10 + fi * (W - 20) / 3).attr('y', y + 32)
          .attr('fill', C.muted).attr('font-family', FM).attr('font-size', 8.5)
          .text('· ' + f.slice(0, 20));
      });
    });
  })();

  // ══════════════════════════════════════════════════
  // NEW CHARTS — Added sections
  // ══════════════════════════════════════════════════

  // ── Urb: Rain stations lollipop ──
  (function () {
    const cities = [
      { city: 'São Paulo', stations: 65, pop: 12.3, deficit: 0 },
      { city: 'Rio de Janeiro', stations: 60, pop: 6.7, deficit: 0 },
      { city: 'Salvador', stations: 15, pop: 2.9, deficit: 2 },
      { city: 'Fortaleza', stations: 11, pop: 2.7, deficit: 3 },
      { city: 'Recife', stations: 7, pop: 1.6, deficit: 4 },
    ];
    const H = 170, pad = { t: 24, b: 28, l: 120, r: 60 };
    const r = mkSvg('chart-rain-stations', H, 380); if (!r) return;
    const { svg, W } = r;
    const avW = W - pad.l - pad.r;
    const xScale = d3.scaleLinear().domain([0, 70]).range([0, avW]);
    const rowH = (H - pad.t - pad.b) / cities.length;

    cities.forEach((d, i) => {
      const y = pad.t + i * rowH + rowH / 2;
      const bx = pad.l + xScale(d.stations);
      const defColors = ['#3dd98a', '#5ba3f5', '#f5a623', '#f05252', '#f05252'];
      const col = defColors[d.deficit];

      svg.append('line').attr('x1', pad.l).attr('x2', bx).attr('y1', y).attr('y2', y)
        .attr('stroke', col).attr('stroke-width', d.stations > 30 ? 2 : 1.5).attr('opacity', 0.7);
      svg.append('circle').attr('cx', bx).attr('cy', y).attr('r', 5).attr('fill', col);
      svg.append('text').attr('x', pad.l - 8).attr('y', y + 4).attr('text-anchor', 'end')
        .attr('fill', d.deficit >= 3 ? col : C.muted).attr('font-size', 10.5).attr('font-family', FM)
        .attr('font-weight', d.deficit >= 3 ? '600' : '400').text(d.city);
      svg.append('text').attr('x', bx + 10).attr('y', y + 4)
        .attr('fill', col).attr('font-size', 11).attr('font-family', FM).attr('font-weight', '600')
        .text(d.stations + ' est.');

      // Pop density annotation
      const densPer = (d.stations / d.pop).toFixed(1);
      svg.append('text').attr('x', W - pad.r + 4).attr('y', y + 4)
        .attr('fill', C.dim).attr('font-size', 8.5).attr('font-family', FM)
        .text(densPer + '/M hab');
    });

    // X grid
    [0, 20, 40, 60].forEach(v => {
      const x = pad.l + xScale(v);
      svg.append('text').attr('x', x).attr('y', H - 8).attr('text-anchor', 'middle')
        .attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM).text(v);
    });

    svg.append('text').attr('x', pad.l).attr('y', 13).attr('fill', C.dim).attr('font-size', 8).attr('font-family', FM)
      .text('Número de estações pluviométricas operacionais (2014) · est./M hab. = densidade');
  })();

  // ── Urb: Piscininha Interactive Calculator ──
  (function () {
    const el = document.getElementById('chart-piscininha-calc');
    if (!el) return;
    el.style.cssText = 'padding: 0; background: transparent;';

    const UI = document.createElement('div');
    UI.style.cssText = `
        font-family: 'IBM Plex Mono', monospace;
        font-size: 11px;
        color: #9ba6c5;
        padding: 6px 0;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
      `;

    function calc(areaLote, pctImp) {
      const IP = 0.06; // m/h - fixed intensity
      const areaImp = areaLote * pctImp / 100;
      const Vu = IP * areaImp; // m³/h inflow
      const VreqM3 = areaImp * IP * 1.0; // vol for 1h = IP * area (m³)
      const Vres = Math.min(VreqM3, 5.0); // simplified reservoir ~min
      const tEsgota = (Vres / Vu) * 60; // minutes
      return { tEsgota: Math.min(tEsgota, 60), areaImp, Vres: (Vres * 1000).toFixed(0) };
    }

    function makeSlider(label, min, max, val, step, unit, onChange) {
      const wrap = document.createElement('div');
      wrap.style.cssText = 'display:flex;flex-direction:column;gap:4px;';
      const lbl = document.createElement('div');
      lbl.style.cssText = 'font-size:9px;color:#717ba0;text-transform:uppercase;letter-spacing:.08em';
      lbl.textContent = label;
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:8px;';
      const inp = document.createElement('input');
      inp.type = 'range'; inp.min = min; inp.max = max; inp.value = val; inp.step = step;
      inp.style.cssText = 'flex:1;accent-color:#3dd98a;height:3px;';
      const valEl = document.createElement('span');
      valEl.style.cssText = 'color:#dde3ef;font-weight:600;min-width:44px;font-size:11px;';
      valEl.textContent = val + unit;
      inp.addEventListener('input', () => { valEl.textContent = inp.value + unit; onChange(+inp.value); });
      row.appendChild(inp); row.appendChild(valEl);
      wrap.appendChild(lbl); wrap.appendChild(row);
      return { wrap, get: () => +inp.value };
    }

    // Visualizer area
    const vizDiv = document.createElement('div');
    vizDiv.style.cssText = 'grid-column:1/-1;position:relative;height:72px;background:#0c1118;border:1px solid #1c2535;border-radius:6px;overflow:hidden;';

    const barEl = document.createElement('div');
    barEl.style.cssText = 'position:absolute;left:0;top:0;bottom:0;background:rgba(61,217,138,.22);transition:width .4s;';
    const warnEl = document.createElement('div');
    warnEl.style.cssText = 'position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;';
    const timeEl = document.createElement('div');
    timeEl.style.cssText = 'font-family:"Syne",sans-serif;font-size:22px;font-weight:800;line-height:1;color:#3dd98a;';
    const sublEl = document.createElement('div');
    sublEl.style.cssText = 'font-size:9px;color:#717ba0;letter-spacing:.06em;';
    warnEl.appendChild(timeEl); warnEl.appendChild(sublEl);
    vizDiv.appendChild(barEl); vizDiv.appendChild(warnEl);

    let areaLote = 1000, pctImp = 75;

    function update() {
      const { tEsgota, areaImp, Vres } = calc(areaLote, pctImp);
      const pct = Math.min(tEsgota / 60, 1);
      const isWarn = tEsgota < 15;
      barEl.style.width = (pct * 100) + '%';
      barEl.style.background = isWarn ? 'rgba(240,82,82,.22)' : 'rgba(61,217,138,.22)';
      timeEl.style.color = isWarn ? '#f05252' : '#3dd98a';
      timeEl.textContent = tEsgota.toFixed(0) + ' min';
      sublEl.textContent = `Reservatório (~${Vres} L) esgota em ${tEsgota.toFixed(0)} min · A partir daí, extravasor a 100%`;
    }

    const sliders = document.createElement('div');
    sliders.style.cssText = 'display:flex;flex-direction:column;gap:10px;';
    const { wrap: w1, get: getArea } = makeSlider('Área do lote (m²)', 300, 3000, areaLote, 50, 'm²', v => { areaLote = v; update(); });
    const { wrap: w2, get: getPct } = makeSlider('Impermeabilização (%)', 30, 95, pctImp, 5, '%', v => { pctImp = v; update(); });
    sliders.appendChild(w1); sliders.appendChild(w2);

    UI.appendChild(sliders);
    UI.appendChild(vizDiv);
    el.appendChild(UI);
    update();
  })();
}

function renderSobre() { /* no charts */ }