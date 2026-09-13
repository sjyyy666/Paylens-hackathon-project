/* PayLens engine — browser port of src/formatting.py, src/mock_services.py,
   src/risk_engine.py and src/recommendations.py. Same inputs, same outputs.
   Mock data only: every company here is fictional demo data. */
(function (root) {
  "use strict";

  // ---------------------------------------------------------------- utils
  function pyRound(x) {                       // Python round(): half to even
    const f = Math.floor(x), d = x - f;
    if (Math.abs(d - 0.5) < 1e-12) return f % 2 === 0 ? f : f + 1;
    return Math.round(x);
  }
  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
  const pct0 = (f) => `${pyRound(f * 100)}%`;

  // ----------------------------------------------------------- formatting
  const MAX_AMOUNT = 1e12;
  function fmtCurrency(value, compactFrom = 10_000_000) {
    const n = Number(value);
    if (value === null || value === undefined || !isFinite(n)) return "—";
    const sign = n < 0 ? "-" : "";
    const v = Math.abs(n);
    const grp = (x, d) => x.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
    if (v >= 1e9 && v >= compactFrom) return `${sign}$${grp(v / 1e9, 1)}B`;
    if (v >= 1e6 && v >= compactFrom) return `${sign}$${grp(v / 1e6, 1)}M`;
    return `${sign}$${grp(v, 0)}`;
  }
  function fmtRatio(r) {
    if (r === null || r === undefined) return "No cash buffer";
    if (r >= 100) return ">100×";
    if (r >= 10) return `${r.toFixed(0)}×`;
    return `${r.toFixed(1)}×`;
  }
  function fmtMonths(m) {
    if (m === null || m === undefined) return "Not constrained";
    if (m <= 0) return "0 months";
    if (m >= 120) return "10+ years";
    if (m >= 24) return `${(m / 12).toFixed(1)} years`;
    return `${m.toFixed(1)} months`;
  }
  function fmtPct(f, digits = 0) {
    const n = Number(f);
    if (!isFinite(n)) return "—";
    return digits ? `${(n * 100).toFixed(digits)}%` : pct0(n);
  }
  function parseAmount(text) {
    if (text === null || text === undefined) return null;
    if (typeof text === "number") return text >= 0 && text <= MAX_AMOUNT ? text : null;
    let s = String(text).trim().toLowerCase();
    if (!s) return null;
    s = s.replace(/aud/g, "").replace(/[$,\s_]/g, "");
    const m = s.match(/^(\d+(?:\.\d+)?|\.\d+)([kmb])?$/);
    if (!m) return null;
    const v = parseFloat(m[1]) * ({ k: 1e3, m: 1e6, b: 1e9 }[m[2]] || 1);
    if (v > MAX_AMOUNT) return null;
    return Math.round(v * 100) / 100;
  }
  function fmtAmountInput(v) {
    if (v === null || v === undefined) return "";
    return Number.isInteger(v) ? `$${v.toLocaleString("en-US")}`
      : `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  // -------------------------------------------------------- mock services
  const COMPANIES = [
    { company_id: "demo-logistics", name: "Demo Logistics Group", abn: "00 100 200 301",
      industry: "Transport, postal & warehousing", size_band: "Large business",
      pct_within_30: 0.31, pct_31_60: 0.49, pct_over_60: 0.20, avg_days_to_pay: 47,
      trend: "worsening", trend_delta_days: 9, peer_slower_than_pct: 0.72,
      peer_group: "Transport, postal & warehousing", history_days: [36, 38, 39, 42, 45, 47] },
    { company_id: "demo-retail", name: "Demo Retail Holdings", abn: "00 100 200 302",
      industry: "Retail trade", size_band: "Large business",
      pct_within_30: 0.52, pct_31_60: 0.36, pct_over_60: 0.12, avg_days_to_pay: 36,
      trend: "stable", trend_delta_days: 1, peer_slower_than_pct: 0.55,
      peer_group: "Retail trade", history_days: [35, 37, 36, 35, 36, 36] },
    { company_id: "example-infrastructure", name: "Example Infrastructure Ltd", abn: "00 100 200 303",
      industry: "Construction", size_band: "Large business",
      pct_within_30: 0.18, pct_31_60: 0.44, pct_over_60: 0.38, avg_days_to_pay: 61,
      trend: "worsening", trend_delta_days: 14, peer_slower_than_pct: 0.88,
      peer_group: "Construction", history_days: [47, 50, 52, 55, 58, 61] },
    { company_id: "sample-corporate", name: "Sample Corporate Services", abn: "00 100 200 304",
      industry: "Professional, scientific & technical services", size_band: "Large business",
      pct_within_30: 0.78, pct_31_60: 0.18, pct_over_60: 0.04, avg_days_to_pay: 24,
      trend: "improving", trend_delta_days: -6, peer_slower_than_pct: 0.21,
      peer_group: "Professional services", history_days: [30, 29, 27, 26, 25, 24] },
    { company_id: "demo-health", name: "Demo Health Partners", abn: "00 100 200 305",
      industry: "Health care & social assistance", size_band: "Large business",
      pct_within_30: 0.66, pct_31_60: 0.26, pct_over_60: 0.08, avg_days_to_pay: 29,
      trend: "stable", trend_delta_days: 0, peer_slower_than_pct: 0.38,
      peer_group: "Health care", history_days: [29, 30, 28, 29, 30, 29] },
    { company_id: "sample-manufacturing", name: "Sample Manufacturing Co", abn: "00 100 200 306",
      industry: null, size_band: "Large business",
      pct_within_30: 0.60, pct_31_60: 0.30, pct_over_60: 0.10, avg_days_to_pay: 33,
      trend: null, trend_delta_days: null, peer_slower_than_pct: null,
      peer_group: null, history_days: null },
  ];
  const PERIODS = ["H2 2023", "H1 2024", "H2 2024", "H1 2025", "H2 2025", "H1 2026"];
  const BY_ID = Object.fromEntries(COMPANIES.map((c) => [c.company_id, c]));
  const DATA_AS_OF = "Demo dataset · H1 2026 reporting period";
  const MODEL_NAME = "mock-logistic-v0 (demo)";
  const digits = (s) => String(s || "").replace(/\D/g, "");
  const publicCompany = (c) => ({ company_id: c.company_id, name: c.name, abn: c.abn,
    industry: c.industry, size_band: c.size_band, is_demo: true });

  function searchCompany(query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return [];
    const qd = digits(q);
    const tokens = q.split(/\s+/).filter(Boolean);
    const scored = [];
    for (const c of COMPANIES) {
      const name = c.name.toLowerCase();
      const hay = `${name} ${(c.industry || "").toLowerCase()}`;
      const hitText = tokens.every((t) => hay.includes(t));
      const hitAbn = qd.length >= 3 && digits(c.abn).includes(qd) && qd === q.replace(/ /g, "");
      if (!(hitText || hitAbn)) continue;
      const rank = name.startsWith(q) ? 0 : name.includes(q) ? 1 : 2;
      scored.push([rank, c.name, c]);
    }
    scored.sort((a, b) => a[0] - b[0] || (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0));
    return scored.slice(0, 8).map((x) => publicCompany(x[2]));
  }
  const suggestedCompanies = () => COMPANIES.map(publicCompany);

  function getCompanyFeatures(id) {
    const c = BY_ID[id];
    if (!c) return null;
    const { history_days, ...rest } = c;
    return { ...rest, data_as_of: DATA_AS_OF, is_demo: true };
  }
  function getCompanyHistory(id) {
    const c = BY_ID[id];
    if (!c || !c.history_days) return [];
    return c.history_days.map((d, i) => ({ period: PERIODS[i], avg_days_to_pay: d }));
  }
  function levelForProbability(p) {
    return p < 0.30 ? "LOW" : p < 0.55 ? "MODERATE" : p < 0.80 ? "HIGH" : "CRITICAL";
  }
  function predictPaymentRisk(features) {
    const f = features || {};
    const missing = [];
    const val = (k, d) => { const v = f[k]; if (v === null || v === undefined) { missing.push(k); return d; } return v; };
    const p31 = val("pct_31_60", 0.30), p60 = val("pct_over_60", 0.10);
    const peer = val("peer_slower_than_pct", 0.50);
    const trend = val("trend", null);
    const tn = { worsening: 1, stable: 0, improving: -1 }[trend] ?? 0;
    const z = -2.8 + 2.2 * p31 + 6.0 * p60 + 1.6 * peer + 0.5 * tn;
    const prob = clamp(1 / (1 + Math.exp(-z)), 0.02, 0.98);

    const cand = [];
    if (trend === "worsening") cand.push([0.9, "Payment speed has deteriorated over recent periods", "negative"]);
    else if (trend === "improving") cand.push([0.5, "Payment speed has improved over recent periods", "positive"]);
    else if (trend === "stable") cand.push([0.35, "Payment speed has been broadly stable", "neutral"]);
    if (p60 >= 0.15) cand.push([p60 * 4, `A relatively high share of payments (${pct0(p60)}) exceed 60 days`, "negative"]);
    else if (p60 <= 0.06 && !missing.includes("pct_over_60")) cand.push([0.4, `Few payments (${pct0(p60)}) run beyond 60 days`, "positive"]);
    if (!missing.includes("peer_slower_than_pct")) {
      if (peer >= 0.6) cand.push([peer, `Payment behaviour is slower than ${pct0(peer)} of peers`, "negative"]);
      else if (peer <= 0.4) cand.push([1 - peer, "Pays faster than most comparable businesses", "positive"]);
      else cand.push([0.4, "Payment speed is broadly in line with peers", "neutral"]);
    }
    const w30 = f.pct_within_30;
    if (w30 !== null && w30 !== undefined && w30 >= 0.6) cand.push([w30 * 0.8, `Most invoices (${pct0(w30)}) are paid within 30 days`, "positive"]);
    else if (w30 !== null && w30 !== undefined && w30 < 0.35) cand.push([0.7, `Only ${pct0(w30)} of invoices are paid within 30 days`, "negative"]);
    else if (w30 !== null && w30 !== undefined) cand.push([0.45, `About ${pct0(w30)} of invoices are paid within 30 days`, "neutral"]);
    if (missing.length) cand.push([0.3, "Limited history available — estimate uses sector defaults", "neutral"]);
    cand.sort((a, b) => b[0] - a[0]);
    return {
      probability: Math.round(prob * 1000) / 1000,
      level: levelForProbability(prob),
      factors: cand.slice(0, 3).map(([, text, tone]) => ({ text, tone })),
      confidence: missing.length ? "limited" : "standard",
      model: MODEL_NAME, is_mock: true,
    };
  }

  // ---------------------------------------------------------- risk engine
  const LEVELS = ["LOW", "MODERATE", "HIGH", "CRITICAL"];
  const LEVEL_RANK = { LOW: 0, MODERATE: 1, HIGH: 2, CRITICAL: 3 };
  const METHODOLOGY_VERSION = "contract-engine-1.0";
  // Mirrors src/contract_risk_engine.py WEIGHTS and src/contract_adapter.py.
  // The customer term is held at 20%: the ML probability is the noisiest input,
  // and the freed 10% goes to cash exposure, measured from entered numbers.
  const CONFIG = { w_customer: 20, w_exposure: 40, w_timing: 20, w_protection: 20,
    delivery_days: 30, expected_delay_days: 30, materiality_full_at: 2.0 };

  // Piecewise-linear map of net-exposure-to-cash ratio onto 0-100.
  // 0.5x -> 25, 1x -> 50, 2x -> 75, 3x+ -> 100.
  function cashExposureScore(ratio) {
    if (ratio === Infinity) return 100;
    if (ratio <= 0) return 0;
    if (ratio <= 0.5) return (ratio / 0.5) * 25;
    if (ratio <= 1.0) return 25 + ((ratio - 0.5) / 0.5) * 25;
    if (ratio <= 2.0) return 50 + (ratio - 1.0) * 25;
    if (ratio <= 3.0) return 75 + (ratio - 2.0) * 25;
    return 100;
  }

  // Banded on how much of the cash runway the wait consumes.
  function waitingPeriodScore(waitMonths, runwayMonths) {
    if (waitMonths <= 0) return 0;
    if (runwayMonths === null || runwayMonths === Infinity) return 0;
    if (runwayMonths <= 0) return 100;
    const r = waitMonths / runwayMonths;
    if (r <= 0.25) return 10;
    if (r <= 0.50) return 30;
    if (r <= 1.00) return 60;
    if (r <= 1.50) return 80;
    return 100;
  }

  function levelForScore(score) {
    const s = pyRound(score);
    return s <= 30 ? "LOW" : s <= 55 ? "MODERATE" : s <= 75 ? "HIGH" : "CRITICAL";
  }
  function num(v, d = 0) { const n = Number(v); return v === null || v === undefined || v === "" || !isFinite(n) ? d : n; }
  function fraction(v) { let n = num(v); if (n > 1) n /= 100; return clamp(n, 0, 1); }
  const fmtRatioReason = (r) => (r >= 100 ? "more than 100×" : `${r.toFixed(1)}×`);

  function analyseContract(paymentProbability, contractValue, cashReserve, monthlyCost,
                           upfrontPct = 0, paymentTermsDays = 30, config = CONFIG) {
    const p = fraction(paymentProbability);
    const contract = Math.max(num(contractValue), 0);
    const cash = Math.max(num(cashReserve), 0);
    const costs = Math.max(num(monthlyCost), 0);
    const upfront = fraction(upfrontPct);
    const terms = Math.trunc(clamp(num(paymentTermsDays, 30), 0, 365));

    const upfrontAmount = contract * upfront;
    const net = contract * (1 - upfront);
    const ratio = cash > 0 ? net / cash : null;
    const ratioCalc = ratio !== null ? ratio : (net > 0 ? Infinity : 0);
    const cashRunway = costs > 0 ? cash / costs : null;
    const effRunway = costs > 0 ? (cash + upfrontAmount) / costs : null;
    const termMonths = terms / 30;
    const waitDays = config.delivery_days + terms;
    const waitMonths = waitDays / 30;
    // Displayed figure carries the delay the customer model expects on top of
    // the engine's waiting period, matching the "incl. likely delay" caption.
    const expectedDays = waitDays + p * config.expected_delay_days;
    let pressure;
    if (net <= 0 || cashRunway === null) pressure = 0;
    else if (cashRunway <= 0) pressure = Infinity;
    else pressure = waitMonths / cashRunway;
    const materiality = ratioCalc === Infinity ? 1 : Math.min(1, ratioCalc / config.materiality_full_at);

    // Each sub-score is 0-100, then weighted into the headline score.
    const sCustomer = p * 100;
    const sExposure = cashExposureScore(ratioCalc);
    const sTiming = waitingPeriodScore(waitMonths, cashRunway);
    const sProtection = (1 - upfront) * 100;

    const cCustomer = (config.w_customer * sCustomer) / 100;
    const cExposure = (config.w_exposure * sExposure) / 100;
    const cTiming = (config.w_timing * sTiming) / 100;
    const cProtection = (config.w_protection * sProtection) / 100;
    const raw = clamp(cCustomer + cExposure + cTiming + cProtection, 0, 100);
    const score = pyRound(raw);

    const r = {
      score, score_raw: raw, level: levelForScore(score),
      inputs: { payment_probability: p, contract_value: contract, cash_reserve: cash,
        monthly_cost: costs, upfront_pct: upfront, payment_terms_days: terms },
      net_exposure: net, upfront_amount: upfrontAmount, contract_to_cash_ratio: ratio,
      cash_runway_months: cashRunway, effective_runway_months: effRunway, term_months: termMonths,
      expected_days_outstanding: expectedDays, timing_pressure: pressure === Infinity ? null : pressure,
      materiality,
      components: [
        { key: "customer", label: "Customer delay risk", points: cCustomer, max_points: config.w_customer },
        { key: "exposure", label: "Exposure vs cash", points: cExposure, max_points: config.w_exposure },
        { key: "timing", label: "Timing vs runway", points: cTiming, max_points: config.w_timing },
        { key: "protection", label: "Upfront protection gap", points: cProtection, max_points: config.w_protection },
      ],
      flags: { no_contract: contract <= 0, no_cash: cash <= 0, no_costs: costs <= 0,
        fully_prepaid: contract > 0 && upfront >= 1 },
      methodology_version: METHODOLOGY_VERSION,
    };
    r.reasons = reasons(r);
    return r;
  }

  function reasons(r) {
    const inp = r.inputs, flags = r.flags, p = inp.payment_probability;
    if (flags.no_contract) return [{ text: "No contract value entered, so nothing is outstanding to assess.", tone: "neutral" }];
    if (flags.fully_prepaid) return [
      { text: "The contract is fully paid upfront, so none of it is outstanding.", tone: "positive" },
      { text: "Customer payment behaviour has no effect on your cash under these terms.", tone: "positive" }];
    const pts = Object.fromEntries(r.components.map((c) => [c.key, c.points]));
    const ratio = r.contract_to_cash_ratio;
    const items = [];
    if (flags.no_cash) items.push([pts.exposure + 5, "You have no available cash buffer to absorb a late payment.", "negative"]);
    else if (ratio >= 1) items.push([pts.exposure + 15, `This contract is ${fmtRatioReason(ratio)} your available cash.`, "negative"]);
    else if (ratio >= 0.5) items.push([pts.exposure, `Net exposure equals ${pct0(ratio)} of your available cash.`, "negative"]);
    else items.push([pts.exposure, `Net exposure is small relative to your cash (${pct0(ratio)}).`, "positive"]);

    if (p >= 0.55) items.push([pts.customer, `The prospective customer has elevated payment-delay risk (${pct0(p)}).`, "negative"]);
    else if (p >= 0.30) items.push([pts.customer, `The customer shows moderate payment-delay risk (${pct0(p)}).`, "neutral"]);
    else items.push([pts.customer * 0.5, `The customer's payment-delay risk is relatively low (${pct0(p)}).`, "positive"]);

    const runway = r.effective_runway_months;
    const days = pyRound(r.expected_days_outstanding);
    const small = r.materiality < 0.25;
    if (small) items.push([1.0, "The amount outstanding is too small to strain your cash runway.", "positive"]);
    else if (flags.no_costs) items.push([0.1, "No monthly operating costs entered, so cash runway isn't a constraint.", "neutral"]);
    else if (runway !== null && runway <= 0) items.push([pts.timing, "Without cash or upfront funds, you can't cover costs while you wait to be paid.", "negative"]);
    else if (r.timing_pressure !== null && r.timing_pressure >= 1) items.push([pts.timing, `Expected payment timing (~${days} days incl. likely delay) exceeds your ~${runway.toFixed(1)}-month cash runway.`, "negative"]);
    else if (r.timing_pressure !== null && r.timing_pressure >= 0.5) items.push([pts.timing, `Expected payment timing (~${days} days) uses much of your ~${runway.toFixed(1)}-month cash runway.`, "negative"]);
    else items.push([pts.timing * 0.5, `Your cash runway comfortably covers the expected ~${days}-day payment cycle.`, "positive"]);

    const u = inp.upfront_pct;
    if (small && u < 0.3) items.push([0.5, "Upfront payment matters less at this contract size.", "neutral"]);
    else if (u < 0.2) items.push([pts.protection, "Current terms provide limited upfront-payment protection.", "negative"]);
    else if (u >= 0.3) items.push([pts.protection * 0.5, `A ${pct0(u)} upfront payment reduces the amount at risk.`, "positive"]);
    else items.push([pts.protection * 0.8, `A ${pct0(u)} upfront payment offers some protection.`, "neutral"]);

    const tr = { negative: 0, neutral: 1, positive: 2 };
    if (r.level === "LOW") items.sort((a, b) => (-tr[a[2]]) - (-tr[b[2]]) || b[0] - a[0]);
    else items.sort((a, b) => tr[a[2]] - tr[b[2]] || b[0] - a[0]);
    return items.slice(0, 3).map(([, text, tone]) => ({ text, tone }));
  }

  // Mirrors risk_engine.MAX_SUGGESTED_UPFRONT_PCT. A 50% ceiling could only
  // answer "not reachable" on a contract worth several times the supplier's
  // cash reserve, hiding the fact that a larger deposit would work.
  const MAX_SUGGESTED_UPFRONT_PCT = 90;

  function findMinUpfront(p, cv, cash, mc, terms, target = "MODERATE", maxPct = MAX_SUGGESTED_UPFRONT_PCT, step = 5) {
    const tRank = LEVEL_RANK[target] ?? 1;
    for (let pct = 0; pct <= maxPct; pct += step) {
      const res = analyseContract(p, cv, cash, mc, pct / 100, terms);
      if (LEVEL_RANK[res.level] <= tRank) return { upfront_pct: pct, score: res.score, level: res.level, terms: Math.trunc(terms) };
    }
    return null;
  }
  function suggestStructure(p, cv, cash, mc, terms, target = "MODERATE", options = [30, 45, 60, 90]) {
    const base = analyseContract(p, cv, cash, mc, 0, terms);
    if (LEVEL_RANK[base.level] <= LEVEL_RANK[target])
      return { status: "already", suggestion: { upfront_pct: 0, terms: Math.trunc(terms), score: base.score, level: base.level } };
    const atTerms = findMinUpfront(p, cv, cash, mc, terms, target);
    if (atTerms) return { status: "upfront", suggestion: atTerms };
    for (const t of options.filter((o) => o < terms).sort((a, b) => b - a)) {
      const s = findMinUpfront(p, cv, cash, mc, t, target);
      if (s) return { status: "upfront_and_terms", suggestion: s };
    }
    return { status: "not_reachable", suggestion: null };
  }

  // Mirrors risk_engine.suggestion_is_actionable. The suggested upfront is a
  // FLOOR, so applying it when the user already asks for more would lower their
  // upfront and raise their risk; and `terms` only echoes the terms the solution
  // was found at, so it cannot tell whether anything would change.
  function suggestionIsActionable(result, revisedUpfrontPct, revisedLevel, target = "MODERATE") {
    if (!result) return false;
    const g = result.suggestion;
    if (!g || (result.status !== "upfront" && result.status !== "upfront_and_terms")) return false;
    if ((LEVEL_RANK[revisedLevel] ?? 3) <= (LEVEL_RANK[target] ?? 1)) return false;
    return g.upfront_pct > revisedUpfrontPct;
  }

  // ------------------------------------------------------ recommendations
  const titleLevel = (l) => l.charAt(0) + l.slice(1).toLowerCase();
  function buildRecommendations(current, revised = null, suggestion = null, limit = 4) {
    const target = revised || current, inp = target.inputs, recs = [];
    if (revised) {
      const delta = current.score - revised.score;
      const dropped = LEVEL_RANK[revised.level] < LEVEL_RANK[current.level];
      if (delta >= 5 && dropped) recs.push([100, { title: "This revised structure materially reduces your exposure",
        body: `Exposure falls from ${current.score} to ${revised.score} (${titleLevel(current.level)} → ${titleLevel(revised.level)}) with the same customer. Use these terms as your negotiating position.`, tone: "positive" }]);
      else if (delta >= 5) recs.push([90, { title: `The revised terms help, but exposure remains ${titleLevel(revised.level).toLowerCase()}`,
        body: `Exposure falls by ${delta} points. Combine several levers to move into a lower band.`, tone: "neutral" }]);
      else if (delta <= -5) recs.push([95, { title: "These revised terms increase your exposure",
        body: "Longer terms or a smaller upfront payment leave more of your working capital tied up in this customer.", tone: "negative" }]);
    }
    if (target.flags.no_contract) return recs.sort((a, b) => b[0] - a[0]).map((x) => x[1]).slice(0, limit);
    if (inp.upfront_pct < 0.2 && target.score >= 56) {
      let body = "An upfront or deposit payment reduces the amount outstanding and adds to your cash buffer.";
      if (suggestion && suggestion.status === "upfront") {
        const s = suggestion.suggestion;
        body = `Around ${s.upfront_pct}% upfront would bring exposure to ${titleLevel(s.level)} at ${s.terms}-day terms, under current assumptions.`;
      }
      recs.push([80, { title: "Consider requesting a higher upfront payment", body, tone: "action" }]);
    }
    if (inp.payment_terms_days > 30 && target.score >= 31) recs.push([70, { title: "Negotiate shorter payment terms",
      body: `Moving from ${inp.payment_terms_days}-day to 30-day terms could reduce the time your working capital remains exposed.`, tone: "action" }]);
    const ratio = target.contract_to_cash_ratio;
    if ((ratio === null && target.net_exposure > 0) || (ratio !== null && ratio >= 1)) recs.push([75, { title: "Reduce initial exposure or use staged billing",
      body: "The contract is large relative to your current cash position. Milestone invoices keep less money outstanding at any one time.", tone: "action" }]);
    const runway = target.effective_runway_months, monthsOut = target.expected_days_outstanding / 30;
    if (runway !== null && target.net_exposure > 0 && runway < monthsOut) recs.push([65, { title: "Line up a cash buffer before you start",
      body: `Your cash covers about ${runway.toFixed(1)} months of costs, less than the ~${target.expected_days_outstanding.toFixed(0)} days you may wait to be paid. Consider a finance facility or delaying other commitments.`, tone: "action" }]);
    if (inp.payment_probability >= 0.55 && target.score >= 31) recs.push([55, { title: "Protect yourself contractually",
      body: "Given this customer's payment history, agree clear due dates, late-payment terms and invoice promptly on delivery.", tone: "action" }]);
    if (target.level === "LOW") recs.push([60, { title: "Exposure looks manageable",
      body: `With ${fmtCurrency(target.net_exposure)} outstanding, this deal sits comfortably within your cash position under current assumptions. Standard invoicing discipline still applies.`, tone: "positive" }]);
    return recs.sort((a, b) => b[0] - a[0]).map((x) => x[1]).slice(0, limit);
  }

  root.PayLens = {
    fmtCurrency, fmtRatio, fmtMonths, fmtPct, parseAmount, fmtAmountInput,
    searchCompany, suggestedCompanies, getCompanyFeatures, getCompanyHistory, predictPaymentRisk,
    analyseContract, levelForScore, findMinUpfront, suggestStructure, suggestionIsActionable,
    buildRecommendations, MAX_SUGGESTED_UPFRONT_PCT,
    LEVELS, LEVEL_RANK, CONFIG, METHODOLOGY_VERSION, DATA_AS_OF,
  };
})(typeof window !== "undefined" ? window : globalThis);
