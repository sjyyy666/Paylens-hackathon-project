/* PayLens UI — renders the journey and wires every control. Business data
   and scoring come only from window.PayLens (engine.js). */
(function () {
  "use strict";
  const P = window.PayLens;
  const TERMS = [30, 45, 60, 90];
  const $ = (id) => document.getElementById(id);
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ------------------------------------------------------------ helpers
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const LVL = { LOW: "low", MODERATE: "moderate", HIGH: "high", CRITICAL: "critical" };
  const LABEL = { LOW: "Low", MODERATE: "Moderate", HIGH: "High", CRITICAL: "Critical" };
  const ICONS = {
    check: '<path d="M5 12.5l4.2 4.2L19 7"/>',
    alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.4v.1"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.4M12 7.6v.1"/>',
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "arrow-down": '<path d="M12 5v14M6 13l6 6 6-6"/>',
    "arrow-up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4 4"/>',
    shield: '<path d="M12 3l7 3v6c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6l7-3z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/>',
    user: '<circle cx="12" cy="8.5" r="3.5"/><path d="M5 20c1.2-3.6 3.9-5.5 7-5.5s5.8 1.9 7 5.5"/>',
    sliders: '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
    doc: '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M10 12h5M10 16h5"/>',
    "trend-up": '<path d="M4 17l5.5-5.5 4 4L20 9"/><path d="M15 9h5v5"/>',
    "trend-down": '<path d="M4 7l5.5 5.5 4-4L20 15"/><path d="M15 15h5v-5"/>',
    "trend-flat": '<path d="M4 12h16M16 8l4 4-4 4"/>',
    "equal-not": '<path d="M5 9h14M5 15h14M16 5L8 19"/>',
    chevron: '<path d="M6 9l6 6 6-6"/>',
  };
  const icon = (name, size = 18) =>
    `<svg class="pl-icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.info}</svg>`;
  const logo = (size = 30) =>
    `<svg width="${size}" height="${size}" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="#006BDE"/><circle cx="15" cy="15" r="7.2" fill="none" stroke="#FFFFFF" stroke-width="2.4"/><path d="M20.2 20.2l4.6 4.6" stroke="#C5EDFC" stroke-width="2.6" stroke-linecap="round"/><path d="M11.6 15.6l2.2 2.2 3.8-4.4" fill="none" stroke="#C5EDFC" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const badge = (level, small) => `<span class="pl-badge pl-badge--${LVL[level] || "moderate"}${small ? " pl-badge--sm" : ""}"><i></i>${esc(level)}</span>`;
  const TONE_ICON = { negative: "alert", positive: "check", neutral: "info", action: "arrow-right" };
  const bullets = (items, level) =>
    `<ul class="pl-reasons">${items.map((it) => `<li class="pl-tone--${it.tone || "neutral"}${level ? " pl-lvl--" + LVL[level] : ""}">${icon(TONE_ICON[it.tone] || "info", 16)}<span>${esc(it.text)}</span></li>`).join("")}</ul>`;
  function meter(value, bands = [30, 55, 75], level = "") {
    const v = Math.max(0, Math.min(100, value));
    const [b1, b2, b3] = bands;
    return `<div class="pl-meter"><div class="pl-meter-track" role="img" aria-label="Position ${Math.round(v)} of 100">
      <span class="pl-meter-band pl-band--low" style="width:${b1}%"></span><span class="pl-meter-band pl-band--moderate" style="width:${b2 - b1}%"></span>
      <span class="pl-meter-band pl-band--high" style="width:${b3 - b2}%"></span><span class="pl-meter-band pl-band--critical" style="width:${100 - b3}%"></span>
      <span class="pl-meter-marker pl-marker--${LVL[level] || ""}" style="left:${v}%"></span></div>
      <div class="pl-meter-labels"><span style="width:${b1}%">Low</span><span style="width:${b2 - b1}%">Moderate</span><span style="width:${b3 - b2}%">High</span><span style="width:${100 - b3}%">Critical</span></div></div>`;
  }
  function emptyState(kind, query = "") {
    const map = {
      no_results: ["search", `No customers match “${esc(query)}”`, "Check the spelling or search by ABN. This prototype includes a small set of demo customers — try “Demo” or “Example”."],
      empty_query: ["info", "Enter a company name or ABN", "Start typing a prospective customer's name, then press Enter or Analyse Customer."],
      error: ["alert", "Something went wrong", "We couldn't load this information. Start a new analysis and try again."],
    };
    const [ic, title, body] = map[kind] || map.error;
    return `<div class="pl-empty">${`<div class="pl-empty-icon">${icon(ic, 20)}</div>`}<div><div class="pl-empty-title">${title}</div><div class="pl-empty-body">${body}</div></div></div>`;
  }

  // ------------------------------------------------------------- state
  const state = { showResults: false, selectedId: null, selectedName: null, features: null, history: [], risk: null,
    analysed: false, currentDeal: null };

  // ------------------------------------------------------- search area
  function renderResults() {
    const box = $("results");
    const q = $("search-input").value.trim();
    $("btn-clear").disabled = !q;
    if (!state.showResults) { box.innerHTML = ""; renderIntroVisibility(); return; }
    if (!q) { box.innerHTML = emptyState("empty_query"); renderIntroVisibility(); return; }
    const results = P.searchCompany(q);
    if (!results.length) {
      box.innerHTML = emptyState("no_results", q) +
        `<div class="pl-quickpicks"><div class="pl-quickpick-label">Or try a demo customer</div><div class="pl-chiprow">${quickpickButtons()}</div></div>`;
    } else {
      const noun = results.length === 1 ? "customer" : "customers";
      box.innerHTML = `<div class="pl-results pl-reveal"><div class="pl-results-head"><span>${results.length} matching ${noun}</span><span class="pl-results-query">for “${esc(q)}”</span></div>
        ${results.map((c) => {
          const sel = c.company_id === state.selectedId;
          return `<div class="pl-result${sel ? " pl-result--selected" : ""}"><div class="pl-result-avatar">${esc(c.name[0])}</div>
            <div class="pl-result-text"><div class="pl-result-name">${esc(c.name)}${c.is_demo ? '<span class="pl-tag">Demo</span>' : ""}</div>
            <div class="pl-result-meta">${esc(c.industry || "Industry not reported")} · ABN ${esc(c.abn || "—")}</div></div>
            <button type="button" class="pl-btn ${sel ? "" : "pl-btn--primary"} pl-btn--sm" data-select="${esc(c.company_id)}" ${sel ? "disabled" : ""}>${sel ? "Selected" : "Select"}</button></div>`;
        }).join("")}</div>`;
    }
    renderIntroVisibility();
  }
  function renderIntroVisibility() { $("intro").hidden = !!(state.selectedId || state.showResults); }
  const quickpickButtons = () => P.suggestedCompanies().map((c) =>
    `<button type="button" class="pl-btn pl-pick" data-select="${esc(c.company_id)}">${esc(c.name)}</button>`).join("");

  function analyseCustomer() {
    const q = $("search-input").value.trim();
    state.showResults = true;
    if (q) {
      const results = P.searchCompany(q);
      const exact = results.filter((r) => r.name.toLowerCase() === q.toLowerCase());
      if (exact.length || results.length === 1) return selectCompany((exact[0] || results[0]).company_id);
    }
    renderResults();
  }

  // ---------------------------------------------------------- customer
  function selectCompany(id) {
    const features = P.getCompanyFeatures(id);
    if (!features) { $("results").innerHTML = emptyState("error"); return; }
    const changed = state.selectedId !== id;
    Object.assign(state, { selectedId: id, selectedName: features.name, features,
      history: P.getCompanyHistory(id), risk: P.predictPaymentRisk(features), showResults: false });
    if (changed) { state.analysed = false; state.currentDeal = null; }
    $("search-input").value = features.name;
    $("hero").classList.add("is-compact");
    renderResults();
    renderCustomer();
    $("deal-section").hidden = false;
    renderExposure();
    renderSimulator();
    scrollTo("customer");
  }

  function sparkline(history) {
    const pts = history.filter((h) => typeof h.avg_days_to_pay === "number");
    if (pts.length < 2) return `<div class="pl-spark pl-spark--empty">${icon("info", 15)}<span>Trend history unavailable for this customer.</span></div>`;
    const vals = pts.map((p) => p.avg_days_to_pay);
    const lo = Math.min(...vals) - 4, hi = Math.max(...vals) + 4;
    const w = 320, h = 64, pad = 6, step = (w - 2 * pad) / (pts.length - 1);
    const y = (v) => pad + (h - 2 * pad) * (1 - (v - lo) / Math.max(hi - lo, 1));
    const xy = pts.map((p, i) => [pad + i * step, y(p.avg_days_to_pay)]);
    const line = xy.map(([x, yy]) => `${x.toFixed(1)},${yy.toFixed(1)}`).join(" ");
    const area = `${xy[0][0].toFixed(1)},${h} ${line} ${xy[xy.length - 1][0].toFixed(1)},${h}`;
    const [lx, ly] = xy[xy.length - 1];
    const grid = [0.25, 0.5, 0.75].map((f) => `<line x1="0" x2="${w}" y1="${(h * f).toFixed(1)}" y2="${(h * f).toFixed(1)}" class="pl-spark-grid"/>`).join("");
    const dots = xy.slice(0, -1).map(([x, yy]) => `<circle cx="${x.toFixed(1)}" cy="${yy.toFixed(1)}" r="2.2" fill="#fff" stroke="#006BDE" stroke-width="1.5" vector-effect="non-scaling-stroke"/>`).join("");
    return `<div class="pl-spark"><div class="pl-spark-head"><span>Average days to pay</span><span class="pl-spark-now">${pts[pts.length - 1].avg_days_to_pay} days</span></div>
      <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" class="pl-spark-svg" role="img" aria-label="Average days to pay rose from ${vals[0]} to ${vals[vals.length - 1]} days">${grid}
      <polygon points="${area}" class="pl-spark-area"/><polyline points="${line}" class="pl-spark-line"/>${dots}
      <circle cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="3.6" fill="#006BDE" stroke="#fff" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>
      <div class="pl-spark-axis"><span>${esc(pts[0].period)} · ${vals[0]}d</span><span>${esc(pts[pts.length - 1].period)}</span></div></div>`;
  }

  function renderCustomer() {
    const f = state.features, history = state.history, risk = state.risk;
    const w30 = f.pct_within_30, w60 = f.pct_31_60, o60 = f.pct_over_60;
    let mix;
    if ([w30, w60, o60].every((v) => typeof v === "number") && w30 + w60 + o60 > 0) {
      const t = w30 + w60 + o60;
      mix = `<div class="pl-stack" role="img" aria-label="${P.fmtPct(w30)} paid within 30 days, ${P.fmtPct(w60)} in 31 to 60 days, ${P.fmtPct(o60)} after 60 days">
        <span class="pl-seg-bar pl-c1" style="width:${(w30 / t * 100).toFixed(1)}%"></span><span class="pl-seg-bar pl-c2" style="width:${(w60 / t * 100).toFixed(1)}%"></span><span class="pl-seg-bar pl-c3" style="width:${(o60 / t * 100).toFixed(1)}%"></span></div>
        <div class="pl-legend">${[["Paid within 30 days", w30, 1], ["Paid in 31–60 days", w60, 2], ["Paid after 60 days", o60, 3]].map(([l, v, i]) =>
          `<div><div class="pl-legend-key"><i class="pl-dot pl-c${i}"></i>${l}</div><div class="pl-legend-val">${P.fmtPct(v)}</div></div>`).join("")}</div>`;
    } else {
      mix = `<div class="pl-spark--empty">${icon("info", 15)}<span>Payment timing breakdown not available.</span></div>`;
    }
    const since = history.length ? `since ${history[0].period}` : "over recent periods";
    const d = f.trend_delta_days;
    const trend = {
      worsening: [`<span class="pl-trend pl-trend--bad">${icon("trend-up", 15)}Worsening</span>`, d ? `Average payment time up ${Math.abs(d)} days ${since}` : "Paying more slowly"],
      improving: [`<span class="pl-trend pl-trend--good">${icon("trend-down", 15)}Improving</span>`, d ? `Average payment time down ${Math.abs(d)} days ${since}` : "Paying faster"],
      stable: [`<span class="pl-trend">${icon("trend-flat", 15)}Stable</span>`, "No material change across recent periods"],
    }[f.trend] || ['<span class="pl-trend pl-trend--na">Not enough history</span>', "Trend needs at least two reporting periods"];
    const peer = f.peer_slower_than_pct;
    const peerHtml = typeof peer === "number"
      ? [`<span class="pl-kv-strong">${peer >= 0.5 ? `Slower than ${P.fmtPct(peer)}` : `Faster than ${P.fmtPct(1 - peer)}`}</span>`, `of comparable businesses${f.peer_group ? " · " + esc(f.peer_group) : ""}`]
      : ['<span class="pl-kv-strong pl-kv-na">Not available</span>', "No comparable peer group for this customer"];

    let riskCard;
    if (!risk) riskCard = `<div class="pl-card"><div class="pl-label-caps">Payment-delay risk</div>${emptyState("error")}</div>`;
    else riskCard = `<div class="pl-card pl-accent pl-accent--${LVL[risk.level]}">
      <div class="pl-label-caps">Payment-delay risk</div>
      <div class="pl-risk-level"><span class="pl-risk-word pl-text--${LVL[risk.level]}">${LABEL[risk.level]}</span>${badge(risk.level, true)}</div>
      <div class="pl-risk-prob"><strong>${P.fmtPct(risk.probability)}</strong> estimated likelihood of payment running late</div>
      ${meter(risk.probability * 100, [30, 55, 80], risk.level)}
      <div class="pl-small">Based on historical payment behaviour.</div>
      ${risk.confidence === "limited" ? `<div class="pl-notice" style="margin-top:12px">${icon("info", 16)}<span>Limited data for this customer — treat this estimate with caution.</span></div>` : ""}
      <div class="pl-subhead">Key factors</div>${bullets(risk.factors.length ? risk.factors : [{ text: "No specific factors available.", tone: "neutral" }], risk.level)}</div>`;

    $("customer").hidden = false;
    $("customer").innerHTML = `<div class="pl-customer-head pl-reveal"><div>
        <div class="pl-eyebrow">Selected customer</div>
        <h2 class="pl-customer-name">${esc(f.name)}</h2>
        <div class="pl-chips">${f.industry ? `<span class="pl-chip">${esc(f.industry)}</span>` : '<span class="pl-chip pl-chip--muted">Industry not reported</span>'}
          <span class="pl-chip">ABN ${esc(f.abn || "—")}</span>${f.is_demo ? '<span class="pl-chip pl-chip--demo">Demo data</span>' : ""}</div></div>
        <div class="pl-asof">${esc(f.data_as_of || "")}</div></div>
      <div class="pl-grid-2 pl-reveal">
        <div class="pl-card"><div class="pl-card-head"><h3 class="pl-card-title">Historical payment behaviour</h3><div class="pl-card-meta">Share of invoices by time to pay</div></div>
          ${mix}
          <div class="pl-kv-grid"><div class="pl-kv"><div class="pl-kv-label">Payment trend</div>${trend[0]}<div class="pl-kv-sub">${esc(trend[1])}</div></div>
          <div class="pl-kv"><div class="pl-kv-label">Peer comparison</div>${peerHtml[0]}<div class="pl-kv-sub">${peerHtml[1]}</div></div></div>
          ${sparkline(history)}</div>
        ${riskCard}</div>`;
  }

  // ---------------------------------------------------------- deal form
  const FIELDS = [["in-contract", "contract_value", "hint-contract"], ["in-cash", "cash_reserve", "hint-cash"], ["in-costs", "monthly_cost", "hint-costs"]];
  function buildSegmented(el, onPick) {
    el.innerHTML = TERMS.map((t) => `<button type="button" role="radio" data-days="${t}" aria-checked="false">${t} days</button>`).join("");
    el.addEventListener("click", (e) => { const b = e.target.closest("button[data-days]"); if (b) { setSegmented(el, +b.dataset.days); onPick(); } });
    el.addEventListener("keydown", (e) => {
      if (!["ArrowLeft", "ArrowRight"].includes(e.key)) return;
      const i = TERMS.indexOf(+el.dataset.value) + (e.key === "ArrowRight" ? 1 : -1);
      if (i < 0 || i >= TERMS.length) return;
      e.preventDefault(); setSegmented(el, TERMS[i]); el.querySelector(`[data-days="${TERMS[i]}"]`).focus(); onPick();
    });
  }
  function setSegmented(el, days) {
    el.dataset.value = days;
    el.querySelectorAll("button").forEach((b) => { const on = +b.dataset.days === days; b.setAttribute("aria-checked", on); b.tabIndex = on ? 0 : -1; });
  }
  function setRange(input, value) {
    input.value = value;
    input.style.setProperty("--pct", `${value}%`);
  }

  function readDeal() {
    const deal = {}, errors = {};
    for (const [id, key] of FIELDS) {
      const v = P.parseAmount($(id).value);
      if (v === null) errors[key] = true;
      deal[key] = v;
    }
    deal.payment_terms_days = +$("in-terms").dataset.value;
    deal.upfront_pct = +$("in-upfront").value;
    return { deal, errors };
  }
  function refreshDealForm() {
    const { deal, errors } = readDeal();
    for (const [id, key, hintId] of FIELDS) {
      const input = $(id), hint = $(hintId), raw = input.value.trim();
      input.setAttribute("aria-invalid", errors[key] ? "true" : "false");
      hint.className = "pl-field-hint";
      if (errors[key]) { hint.classList.add("pl-field-hint--error"); hint.textContent = raw ? "That doesn't look like an amount. Try 120,000 or 120k." : "Enter an amount, e.g. 120,000"; }
      else if (deal[key] === 0) hint.textContent = input.dataset.zero;
      else if (deal[key] >= 10_000_000) hint.textContent = `≈ ${P.fmtCurrency(deal[key])}`;
      else hint.textContent = "";
    }
    $("val-upfront").textContent = `${deal.upfront_pct}%`;
    const cv = deal.contract_value;
    $("hint-upfront").textContent = cv ? `Customer pays ${P.fmtCurrency(cv * deal.upfront_pct / 100)} upfront · ${P.fmtCurrency(cv * (1 - deal.upfront_pct / 100))} on terms` : "";
    $("btn-analyse-deal").disabled = Object.keys(errors).length > 0;
    if (state.analysed) renderExposure();
  }
  const sameDeal = (a, b) => a && b && ["contract_value", "cash_reserve", "monthly_cost", "payment_terms_days", "upfront_pct"].every((k) => a[k] === b[k]);

  function analyse(deal) {
    const p = state.risk ? state.risk.probability : 0.5;
    return P.analyseContract(p, deal.contract_value, deal.cash_reserve, deal.monthly_cost, deal.upfront_pct / 100, deal.payment_terms_days);
  }

  function analyseDeal() {
    const { deal, errors } = readDeal();
    if (Object.keys(errors).length) return;
    state.currentDeal = deal; state.analysed = true;
    setRange($("sim-upfront"), deal.upfront_pct);
    setSegmented($("sim-terms"), deal.payment_terms_days);
    renderExposure(); renderSimulator();
    scrollTo("exposure");
  }

  function renderExposure() {
    const box = $("exposure");
    if (!state.analysed || !state.currentDeal) {
      box.innerHTML = `<div class="pl-card pl-card--placeholder"><div class="pl-label-caps">Contract exposure</div>
        <div class="pl-placeholder-title">Your exposure result will appear here</div>
        <div class="pl-placeholder-body">PayLens combines four signals into one transparent score:</div>
        <ul class="pl-placeholder-list">${[["user", "Customer payment-delay risk"], ["doc", "Contract size vs your available cash"], ["clock", "Payment terms vs your cash runway"], ["shield", "Upfront-payment protection"]]
          .map(([i, t]) => `<li>${icon(i, 16)}<span>${t}</span></li>`).join("")}</ul></div>`;
      return;
    }
    const r = analyse(state.currentDeal), inp = r.inputs;
    const { deal, errors } = readDeal();
    const stale = Object.keys(errors).length > 0 || !sameDeal(deal, state.currentDeal);
    const metrics = [
      ["Net exposure", P.fmtCurrency(r.net_exposure), `after ${P.fmtPct(inp.upfront_pct)} upfront`],
      ["Contract / cash", P.fmtRatio(r.contract_to_cash_ratio), "net exposure ÷ available cash"],
      ["Cash runway", P.fmtMonths(r.cash_runway_months), "available cash ÷ monthly costs"],
      ["Payment terms", `${inp.payment_terms_days} days`, `~${r.expected_days_outstanding.toFixed(0)} days incl. likely delay`],
    ];
    box.innerHTML = `<div class="pl-card pl-accent pl-accent--${LVL[r.level]}" id="exposure-card">
      ${stale ? `<div class="pl-notice pl-notice--negative">${icon("alert", 16)}<span>You've changed the deal inputs. Analyse again to update this result.</span></div>` : ""}
      ${!state.risk ? `<div class="pl-notice">${icon("info", 16)}<span>Customer risk is unavailable, so a neutral 50% delay assumption is used.</span></div>` : ""}
      <div class="pl-exp-top"><div class="pl-label-caps">Contract exposure</div>${badge(r.level)}</div>
      <div class="pl-score"><span class="pl-score-num">${r.score}</span><span class="pl-score-den">/ 100</span></div>
      ${meter(r.score, [30, 55, 75], r.level)}
      <div class="pl-subhead">Why</div>${bullets(r.reasons, r.level)}
      <div class="pl-metrics">${metrics.map(([a, b, c]) => `<div class="pl-metric"><div class="pl-metric-label">${a}</div><div class="pl-metric-value">${b}</div><div class="pl-metric-sub">${c}</div></div>`).join("")}</div>
      <div class="pl-footnote">Prototype decision-support heuristic · not a credit rating</div></div>`;
  }

  // --------------------------------------------------------- simulator
  function revisedDeal() {
    return { ...state.currentDeal, upfront_pct: +$("sim-upfront").value, payment_terms_days: +$("sim-terms").dataset.value };
  }
  let lastSuggestion = null;
  function renderSimulator() {
    const section = $("sim-section");
    if (!state.analysed || !state.currentDeal) { section.hidden = true; return; }
    section.hidden = false;
    const cd = state.currentDeal, rd = revisedDeal();
    const current = analyse(cd), revised = analyse(rd);
    const p = state.risk ? state.risk.probability : 0.5;
    const s = P.suggestStructure(p, cd.contract_value, cd.cash_reserve, cd.monthly_cost, rd.payment_terms_days);
    lastSuggestion = s;

    $("val-sim-upfront").textContent = `${rd.upfront_pct}%`;
    $("sim-upfront").style.setProperty("--pct", `${rd.upfront_pct}%`);
    $("hint-sim-upfront").textContent = `${P.fmtCurrency(cd.contract_value * rd.upfront_pct / 100)} paid before work begins`;
    $("sim-live").innerHTML = `<div class="pl-live"><span class="pl-live-dot"></span><span>Revised exposure</span><span class="pl-live-score pl-text--${LVL[revised.level]}">${revised.score}</span>${badge(revised.level, true)}</div>`;

    // Suggestion
    let sugHtml;
    if (!s || s.status === "not_reachable") sugHtml = `<div class="pl-suggest pl-suggest--muted"><div class="pl-suggest-label">${icon("info", 15)}Suggested minimum upfront payment</div><div class="pl-suggest-body">Upfront payment of up to ${P.MAX_SUGGESTED_UPFRONT_PCT}% won't reach Moderate on its own. Consider a smaller initial scope or staged billing.</div></div>`;
    else if (s.status === "already") sugHtml = `<div class="pl-suggest pl-suggest--good"><div class="pl-suggest-label">${icon("check", 15)}Suggested minimum upfront payment</div><div class="pl-suggest-value">0%</div><div class="pl-suggest-body">Your deal already sits at ${LABEL[s.suggestion.level]} exposure or lower at ${s.suggestion.terms}-day terms.</div></div>`;
    else {
      const g = s.suggestion, note = s.status === "upfront_and_terms" ? `with ${g.terms}-day terms` : `at ${g.terms}-day terms`;
      sugHtml = `<div class="pl-suggest"><div class="pl-suggest-label">${icon("shield", 15)}Suggested minimum upfront payment</div><div class="pl-suggest-value">${g.upfront_pct}%</div><div class="pl-suggest-body">To reach ${LABEL[g.level]} exposure ${note}, under the current assumptions (score ${g.score}).</div></div>`;
    }
    $("suggest").innerHTML = sugHtml;
    $("btn-apply").disabled = !P.suggestionIsActionable(s, rd.upfront_pct, revised.level);
    $("btn-reset-sim").disabled = sameDeal(rd, cd);

    renderCompare(current, revised);
    const recs = P.buildRecommendations(current, revised, s);
    $("recs").innerHTML = `<div class="pl-recs">${(recs.length ? recs : [{ title: "No specific actions", body: "Nothing stands out under current assumptions.", tone: "neutral" }]).map((r) =>
      `<div class="pl-rec pl-rec--${r.tone}"><div class="pl-rec-icon">${icon(TONE_ICON[r.tone] || "arrow-right", 17)}</div><div><div class="pl-rec-title">${esc(r.title)}</div><div class="pl-rec-body">${esc(r.body)}</div></div></div>`).join("")}</div>`;
  }

  function rows(r, other) {
    const i = r.inputs, o = other && other.inputs;
    const ch = (k) => o && Math.abs(i[k] - o[k]) > 1e-9;
    return [["Contract value", P.fmtCurrency(i.contract_value), false],
      ["Upfront", `${P.fmtPct(i.upfront_pct)} · ${P.fmtCurrency(r.upfront_amount)}`, ch("upfront_pct")],
      ["Payment terms", `${i.payment_terms_days} days`, ch("payment_terms_days")],
      ["Net exposure", P.fmtCurrency(r.net_exposure), ch("upfront_pct")]]
      .map(([a, b, c]) => `<div class="pl-crow${c ? " pl-crow--changed" : ""}"><span>${a}</span><span>${b}</span></div>`).join("");
  }
  function renderCompare(current, revised) {
    const delta = revised.score - current.score;
    const changed = revised.inputs.upfront_pct !== current.inputs.upfront_pct || revised.inputs.payment_terms_days !== current.inputs.payment_terms_days;
    let deltaHtml, cls, verdict, expWord, expCls;
    if (delta < 0) [deltaHtml, cls, verdict, expWord, expCls] = [`<div class="pl-delta pl-delta--down">${icon("arrow-down", 14)}${-delta} pts</div>`, "improved", "Lower exposure.", "Lower", "good"];
    else if (delta > 0) [deltaHtml, cls, verdict, expWord, expCls] = [`<div class="pl-delta pl-delta--up">${icon("arrow-up", 14)}${delta} pts</div>`, "worse", "Higher exposure.", "Higher", "bad"];
    else [deltaHtml, cls, verdict, expWord, expCls] = ['<div class="pl-delta">No change</div>', "same", "", "Unchanged", ""];
    const line = changed && verdict ? `Same customer. Different deal structure. <em>${verdict}</em>`
      : changed ? "Same customer. Different deal structure. Same exposure."
      : "Move the controls above to build a revised deal and compare.";
    const ri = revised.inputs;
    const card = (label, r, other, extra) => `<div class="pl-ccard ${extra}"><div class="pl-label-caps">${label}</div>
      <div class="pl-ccard-score"><span class="pl-text--${LVL[r.level]}">${r.score}</span><small>/ 100</small></div>${badge(r.level, true)}
      <div class="pl-crows">${rows(r, other)}</div></div>`;
    $("compare").innerHTML = `<div class="pl-compare pl-compare--${cls}">
      ${card("Current deal", current, null, "pl-ccard--current")}
      <div class="pl-compare-mid"><div class="pl-compare-arrow">${icon("arrow-right", 20)}</div>${deltaHtml}</div>
      ${card("Revised deal", revised, current, `pl-ccard--revised pl-accent pl-accent--${LVL[revised.level]}`)}</div>
      <div class="pl-insight pl-insight--${cls}"><div class="pl-insight-line">${line}</div>
      <div class="pl-insight-grid">
        <div class="pl-insight-item"><div class="pl-insight-k">${icon("user", 15)}The customer</div><div class="pl-insight-v">Unchanged</div><div class="pl-insight-s">${esc(state.selectedName)}${state.risk ? " · " + P.fmtPct(state.risk.probability) + " delay risk" : ""}</div></div>
        <div class="pl-insight-item"><div class="pl-insight-k">${icon("doc", 15)}The contract</div><div class="pl-insight-v">${changed ? "Restructured" : "Unchanged"}</div><div class="pl-insight-s">${changed ? `${P.fmtPct(ri.upfront_pct)} upfront · ${ri.payment_terms_days}-day terms` : "No changes yet"}</div></div>
        <div class="pl-insight-item"><div class="pl-insight-k">${icon("shield", 15)}Your exposure</div><div class="pl-insight-v${expCls ? " pl-insight-v--" + expCls : ""}">${expWord}</div><div class="pl-insight-s">${current.score} → ${revised.score} · ${LABEL[current.level]} → ${LABEL[revised.level]}</div></div>
      </div></div>`;
  }

  // ---------------------------------------------------------- misc UI
  function scrollTo(id) {
    const el = $(id === "exposure" ? "exposure" : id);
    if (el) el.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  }
  let toastTimer;
  function toast(msg) {
    const t = $("toast"); t.textContent = msg; t.classList.add("is-on");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("is-on"), 2400);
  }
  function resetAll() {
    Object.assign(state, { showResults: false, selectedId: null, selectedName: null, features: null, history: [], risk: null, analysed: false, currentDeal: null });
    $("search-input").value = "";
    $("in-contract").value = "$120,000"; $("in-cash").value = "$45,000"; $("in-costs").value = "$25,000";
    setSegmented($("in-terms"), 60); setRange($("in-upfront"), 0);
    setSegmented($("sim-terms"), 60); setRange($("sim-upfront"), 0);
    $("hero").classList.remove("is-compact");
    $("customer").hidden = true; $("customer").innerHTML = "";
    $("deal-section").hidden = true; $("sim-section").hidden = true;
    refreshDealForm(); renderResults();
    window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
    $("search-input").focus({ preventScroll: true });
  }

  function staticParts() {
    document.querySelectorAll("[data-icon]").forEach((el) => {
      const n = el.dataset.icon, s = +(el.dataset.size || (n === "logo" ? 30 : 18));
      el.outerHTML = n === "logo" ? logo(s) : icon(n, s);
    });
    $("quickpicks").innerHTML = quickpickButtons();
    $("steps").innerHTML = [["search", "Check the customer", "See how they have paid other suppliers and their payment-delay risk."],
      ["doc", "Model your deal", "Enter the contract, your cash and costs to measure your own exposure."],
      ["sliders", "Restructure the terms", "Test upfront payments and shorter terms before you negotiate."]]
      .map(([ic, t, b], i) => `<div class="pl-step"><div class="pl-step-icon">${icon(ic, 18)}</div><div class="pl-step-num">Step ${i + 1}</div><div class="pl-step-title">${t}</div><div class="pl-step-body">${b}</div></div>`).join("");
    const C = P.CONFIG;
    $("method").innerHTML = `<div class="pl-table-wrap"><table class="pl-table"><thead><tr><th>Component</th><th class="pl-num">Max points</th><th>What it measures</th></tr></thead><tbody>
      ${[["Customer delay risk", C.w_customer, "The customer's payment-delay probability, taken directly as a 0-100 risk."],
         ["Exposure vs cash", C.w_exposure, "Net exposure (contract minus upfront) as a multiple of your available cash: 0.5x, 1x, 2x and 3x map to 25, 50, 75 and 100."],
         ["Timing vs runway", C.w_timing, "Delivery time plus payment terms, as a share of how long your cash covers your operating costs."],
         ["Upfront protection gap", C.w_protection, "Share of the contract not paid upfront."]].map(([a, b, c]) => `<tr><td>${a}</td><td class="pl-num">${b}</td><td>${c}</td></tr>`).join("")}
      </tbody></table></div>
      <div class="pl-method-bands"><span>${badge("LOW", 1)} 0–30</span><span>${badge("MODERATE", 1)} 31–55</span><span>${badge("HIGH", 1)} 56–75</span><span>${badge("CRITICAL", 1)} 76–100</span></div>
      <div class="pl-small">Weights live in one place and are shared with the Python engine, not a credit rating. Customer payment data and the delay model are demo stand-ins and will be replaced by real Payment Times data and a trained model.</div>`;
  }

  // ------------------------------------------------------------ wiring
  function init() {
    staticParts();
    buildSegmented($("in-terms"), refreshDealForm);
    buildSegmented($("sim-terms"), renderSimulator);
    setSegmented($("in-terms"), 60); setSegmented($("sim-terms"), 60);
    setRange($("in-upfront"), 0); setRange($("sim-upfront"), 0);

    const search = $("search-input");
    search.addEventListener("input", () => {
      const q = search.value.trim();
      state.showResults = !!q && q !== state.selectedName;
      renderResults();
    });
    $("search-form").addEventListener("submit", (e) => { e.preventDefault(); analyseCustomer(); });
    $("btn-clear").addEventListener("click", () => { search.value = ""; state.showResults = false; renderResults(); search.focus(); });
    $("btn-new").addEventListener("click", resetAll);
    document.addEventListener("click", (e) => { const b = e.target.closest("[data-select]"); if (b && !b.disabled) selectCompany(b.dataset.select); });

    for (const [id] of FIELDS) {
      const input = $(id);
      input.addEventListener("input", refreshDealForm);
      input.addEventListener("change", () => { const v = P.parseAmount(input.value); if (v !== null) input.value = P.fmtAmountInput(v); refreshDealForm(); });
    }
    $("in-upfront").addEventListener("input", (e) => { setRange(e.target, +e.target.value); refreshDealForm(); });
    $("deal-form").addEventListener("submit", (e) => { e.preventDefault(); analyseDeal(); });

    $("sim-upfront").addEventListener("input", renderSimulator);
    $("btn-reset-sim").addEventListener("click", () => { setRange($("sim-upfront"), state.currentDeal.upfront_pct); setSegmented($("sim-terms"), state.currentDeal.payment_terms_days); renderSimulator(); });
    $("btn-apply").addEventListener("click", () => {
      const g = lastSuggestion && lastSuggestion.suggestion; if (!g) return;
      setRange($("sim-upfront"), g.upfront_pct); setSegmented($("sim-terms"), g.terms); renderSimulator();
      toast("Suggested terms applied to your revised deal.");
    });

    refreshDealForm(); renderResults(); renderExposure();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
