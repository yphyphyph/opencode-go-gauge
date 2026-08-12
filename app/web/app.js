/* GoGauge v1.0.0 - 4 页 (首页/用量统计/设置/关于) + 双主题 + 中英国际化 */
"use strict";

const $ = (id) => document.getElementById(id);

/* ================= 国际化 ================= */
const I18N = {
  zh: {
    syncing: "同步中", themeDark: "暗色", themeLight: "亮色", refresh: "刷新",
    homeTitle: "用量统计总览", today: "今天", d7: "近7天", d30: "近30天", all: "全部",
    overviewTitle: "用量概览", followRange: "数据跟随时间范围",
    todayTrend: "今日趋势", hours24: "24 小时",
    statsTitle: "用量统计", tokenBreakdown: "Token 构成",
    modelUsage: "模型用量", input: "输入", output: "输出", cost: "成本",
    usageTrend: "用量趋势", usageRecords: "使用记录", allModels: "全部模型",
    colTime: "时间", colModel: "模型", colInput: "输入", colOutput: "输出",
    colReasoning: "推理", colCacheRead: "缓存读", colCost: "费用", colPlan: "PLAN",
    prev: "上一页", next: "下一页",
    settingsTitle: "设置", setAccount: "OpenCode 账户", setLoginState: "登录状态",
    setWorkspace: "工作区", setLoginMethod: "登录方式",
    loginMethodDesc: "内置浏览器 (WebView2) 打开官方授权页，自动回填",
    relogin: "重新登录", setLogout: "退出登录", logoutDesc: "清除本地 token 与缓存数据", logout: "退出登录",
    setAutoSync: "自动同步", autoSync: "自动增量同步", autoSyncDesc: "按间隔拉取最新用量记录",
    syncInterval: "同步间隔", syncIntervalDesc: "多久自动同步一次",
    min1: "1 分钟", min5: "5 分钟", min15: "15 分钟", min30: "30 分钟",
    syncRange: "同步范围", syncRangeDesc: "本地保留与首次拉取的历史窗口；\"所有\"= 拉取全部（500 页保险）",
    d30short: "30天", d60: "60天", d90: "90天", d180: "180天",
    fullSync: "立即全量同步", fullSyncDesc: "重新拉取历史记录，补全数据", startFullSync: "开始全量同步",
    setAppearance: "外观", theme: "主题", themeDesc: "亮色 / 深色，顶栏按钮快捷切换",
    light: "浅色", dark: "深色", currency: "默认货币", currencyDesc: "费用主显示货币（实时汇率）",
    language: "语言 / Language", languageDesc: "界面显示语言",
    setData: "数据", dataDir: "数据目录", syncInfo: "同步记录",
    aboutTitle: "关于", aboutIntro: "简介",
    introText: "是一款本地优先的 OpenCode Go 用量面板：配额窗口、Token 构成、模型排行与使用记录整理在同一处，打开即见。所有数据仅保存在本地，登录凭证只用于同步官方接口。",
    aboutFeatures: "功能", feat1: "配额窗口实时监控（滚动 5 小时 / 每周 / 每月）",
    feat2: "今日用量与 24 小时趋势", feat3: "各模型 Token 消耗排行与用量趋势",
    feat4: "详细使用记录分页浏览（10 条/页）", feat5: "自动同步数据，无需手动刷新",
    aboutTech: "技术栈", aboutLinks: "链接", aboutThanks: "致谢", thanksText: "数据提供",
    pageFoot: "v1.0.0 · GoGauge · 数据仅保存在本地 · 数据提供 OpenCode",
    loginTitle: "连接 OpenCode Go",
    welcomeDesc: "本地优先的 OpenCode Go 用量仪表盘 — 配额窗口、Token 构成、模型排行、使用记录，打开即见。",
    welcomeFeat1: "配额实时监控（5 小时 / 每周 / 每月）",
    welcomeFeat2: "Token 全维度统计与 24 小时趋势",
    welcomeFeat3: "数据仅保存在本机，安全私密",
    loginBtn: "立即登录",
    loginNote: "点击后将打开 OpenCode Go 官方授权页完成登录。",
    quitApp: "退出应用",
    rolling: "滚动用量", weekly: "每周用量", monthly: "每月用量",
    remaining: "剩余", used: "已用", resetsIn: "重置于",
    hitRate: "缓存命中率", hitAmount: "缓存命中量", totalTokens: "总 TOKEN 消耗",
    totalRequests: "总请求", totalCost: "总费用", sessions: "会话数",
    hit: "命中", miss: "未命中", pctOfInput: "占输入", inclCache: "含缓存命中",
    currentRange: "当前范围", avgPer: "均", perReq: "/次", dedup: "去重 sessionID",
    noData: "暂无记录", loadFailed: "加载失败", totalN: "共", items: "条",
    pageOf: "第", ofPages: "页",
    loggedIn: "已登录", notLoggedIn: "未登录", connected: "已连接", notConnected: "未连接",
    lastSync: "上次同步", records: "条记录", updatedAt: "更新于",
    justNow: "刚刚", minAgo: "分钟前", hrAgo: "小时前", dayAgo: "天前", never: "从未同步",
    day: "天", hour: "小时", minute: "分钟", soon: "即将重置",
    dUnit: "天", hUnit: "小时", mUnit: "分钟",
    confirm: "确认", cancel: "取消", ok: "确定",
    fullSyncConfirm: "将重新拉取历史记录（按同步范围），确定开始？", startSync: "开始同步",
    reloginConfirm: "将清除本地数据并打开官方授权页重新登录，确定？", goLogin: "去登录",
    logoutConfirm: "退出将清除本地 token 与全部缓存数据，确定退出？", quit: "退出",
    quotaFail: "配额获取失败", retryTip: "点击右上角刷新重试",
    syncIntervalSet: "同步间隔已设为", syncRangeUpdated: "同步范围已更新，下次全量同步生效",
    trendHint: "30 天", totalTokenHint: "含缓存命中",
  },
  en: {
    syncing: "Syncing", themeDark: "Dark", themeLight: "Light", refresh: "Refresh",
    homeTitle: "Usage Overview", today: "Today", d7: "7 Days", d30: "30 Days", all: "All",
    overviewTitle: "Usage Overview", followRange: "Follows selected range",
    todayTrend: "Today's Trend", hours24: "24 Hours",
    statsTitle: "Usage Stats", tokenBreakdown: "Token Breakdown",
    modelUsage: "Model Usage", input: "Input", output: "Output", cost: "Cost",
    usageTrend: "Usage Trend", usageRecords: "Usage Records", allModels: "All Models",
    colTime: "Time", colModel: "Model", colInput: "Input", colOutput: "Output",
    colReasoning: "Reasoning", colCacheRead: "Cache Read", colCost: "Cost", colPlan: "PLAN",
    prev: "Prev", next: "Next",
    settingsTitle: "Settings", setAccount: "OpenCode Account", setLoginState: "Login Status",
    setWorkspace: "Workspace", setLoginMethod: "Login Method",
    loginMethodDesc: "Built-in browser (WebView2) opens the official auth page and auto-fills",
    relogin: "Re-login", setLogout: "Logout", logoutDesc: "Clear local token and cached data", logout: "Logout",
    setAutoSync: "Auto Sync", autoSync: "Auto incremental sync", autoSyncDesc: "Fetch latest usage records at interval",
    syncInterval: "Sync Interval", syncIntervalDesc: "How often to auto sync",
    min1: "1 min", min5: "5 min", min15: "15 min", min30: "30 min",
    syncRange: "Sync Range", syncRangeDesc: "Local history window for initial fetch; \"All\" = fetch everything (500-page safety cap)",
    d30short: "30d", d60: "60d", d90: "90d", d180: "180d",
    fullSync: "Full Sync Now", fullSyncDesc: "Re-fetch history records to fill gaps", startFullSync: "Start Full Sync",
    setAppearance: "Appearance", theme: "Theme", themeDesc: "Light / Dark, quick toggle in top bar",
    light: "Light", dark: "Dark", currency: "Currency", currencyDesc: "Primary currency for costs (live FX rate)",
    language: "Language", languageDesc: "Interface language",
    setData: "Data", dataDir: "Data Directory", syncInfo: "Sync History",
    aboutTitle: "About", aboutIntro: "Intro",
    introText: "is a local-first OpenCode Go usage dashboard: quota windows, token breakdown, model ranking and usage records in one place. All data stays on your machine; credentials are only used to sync official APIs.",
    aboutFeatures: "Features", feat1: "Quota window monitoring (5h rolling / weekly / monthly)",
    feat2: "Today's usage with 24-hour trend", feat3: "Per-model token ranking and usage trend",
    feat4: "Paginated usage records (10 per page)", feat5: "Auto sync — no manual refresh needed",
    aboutTech: "Tech Stack", aboutLinks: "Links", aboutThanks: "Thanks", thanksText: "Data provided by",
    pageFoot: "v1.0.0 · GoGauge · Local-only data · Data by OpenCode",
    loginTitle: "Connect OpenCode Go",
    welcomeDesc: "A local-first OpenCode Go usage dashboard — quota windows, token breakdown, model ranking and usage records in one place.",
    welcomeFeat1: "Real-time quota monitoring (5h / weekly / monthly)",
    welcomeFeat2: "Full token stats with 24-hour trend",
    welcomeFeat3: "All data stays on your machine — private & safe",
    loginBtn: "Login Now",
    loginNote: "Clicking opens the official OpenCode Go authorization page.",
    quitApp: "Quit App",
    rolling: "Rolling Usage", weekly: "Weekly Usage", monthly: "Monthly Usage",
    remaining: "Remaining", used: "Used", resetsIn: "Resets in",
    hitRate: "Cache Hit Rate", hitAmount: "Cache Hits", totalTokens: "Total Tokens",
    totalRequests: "Requests", totalCost: "Total Cost", sessions: "Sessions",
    hit: "hit", miss: "missed", pctOfInput: "of input", inclCache: "incl. cache hits",
    currentRange: "current range", avgPer: "avg", perReq: "/req", dedup: "dedup sessionID",
    noData: "No records", loadFailed: "Failed to load", totalN: "Total", items: "records",
    pageOf: "Page", ofPages: "of",
    loggedIn: "Logged in", notLoggedIn: "Not logged in", connected: "Connected", notConnected: "Not connected",
    lastSync: "Last sync", records: "records", updatedAt: "Updated",
    justNow: "just now", minAgo: "min ago", hrAgo: "hr ago", dayAgo: "d ago", never: "Never synced",
    day: "d", hour: "h", minute: "m", soon: "resets soon",
    dUnit: "d", hUnit: "h", mUnit: "m",
    confirm: "Confirm", cancel: "Cancel", ok: "OK",
    fullSyncConfirm: "This will re-fetch all history records (per sync range). Continue?", startSync: "Start Sync",
    reloginConfirm: "This will clear local data and open the auth page. Continue?", goLogin: "Go Login",
    logoutConfirm: "This will clear local token and all cached data. Continue?", quit: "Logout",
    quotaFail: "Quota fetch failed", retryTip: "Click refresh in top bar to retry",
    syncIntervalSet: "Sync interval set to", syncRangeUpdated: "Sync range updated, takes effect on next full sync",
    trendHint: "30 days", totalTokenHint: "incl. cache hits",
  },
};
let lang = "zh";
function t(key) { return (I18N[lang] && I18N[lang][key]) || I18N.zh[key] || key; }

let state = {
  page: "home",
  range: "today",
  statsRange: "7d",
  modelDim: "input",
  data: null,
  exchangeRate: 7.0,
  currency: "CNY",
  darkMode: false,
  syncTimer: null,
  quotaRetryTimer: null,
  records: { page: 1, pageSize: 10, total: 0, model: "" },
  settings: { sync_interval_sec: 300, window_days: 60, auto_sync: true },
};

const COLOR = { input: "#4f8ef7", output: "#22c55e", reasoning: "#a78bfa", cache: "#06b6d4", cost: "#d97706" };
const QUOTA_LABEL = { "5h Rolling": () => t("rolling"), "Weekly": () => t("weekly"), "Monthly": () => t("monthly") };
const PLAN_BADGE = { lite: "GO", sub: "GO", byok: "BYOK" };

/* ---------------- 格式化 ---------------- */
function fmtTokens(n) {
  n = Number(n) || 0;
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(Math.round(n));
}
function fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }
function fmtMoney(usd) {
  usd = Number(usd) || 0;
  if (state.currency === "CNY") {
    const v = usd * state.exchangeRate;
    return "¥" + (v >= 1 ? v.toFixed(2) : v.toFixed(4));
  }
  if (usd >= 1) return "$" + usd.toFixed(2);
  if (usd > 0) return "$" + usd.toFixed(4);
  return "$0";
}
function fmtDur(sec) {
  sec = Math.max(0, Number(sec) || 0);
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
  if (d > 0) return d + " " + t("dUnit") + " " + h + " " + t("hUnit");
  if (h > 0) return h + " " + t("hUnit") + " " + m + " " + t("mUnit");
  if (m > 0) return m + " " + t("mUnit");
  return t("soon");
}
function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  const pad = (x) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
function fmtRelative(iso) {
  if (!iso) return t("never");
  const d = new Date(iso);
  if (isNaN(d)) return t("never");
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return t("justNow");
  if (diff < 3600) return Math.floor(diff / 60) + " " + t("minAgo");
  if (diff < 86400) return Math.floor(diff / 3600) + " " + t("hrAgo");
  return Math.floor(diff / 86400) + " " + t("dayAgo");
}
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

/* ---------------- API ---------------- */
async function api(path, opts = {}) {
  const resp = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!resp.ok) throw new Error("HTTP " + resp.status);
  return resp.json();
}

/* ---------------- 语言切换 ---------------- */
function applyLang(l) {
  lang = l === "en" ? "en" : "zh";
  try { localStorage.setItem("gousage-lang", lang); } catch (e) { /* ignore */ }
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  // 静态 data-i18n 文案
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("#set-lang-pills .pill").forEach((b) => b.classList.toggle("active", b.dataset.v === lang));
  document.getElementById("about-sub").textContent = "v1.0.0 · OpenCode Go Usage Panel";
  // 动态内容重渲染
  if (state.data) {
    renderAll(state.data);
    renderSettings();
    loadRecords().catch(() => {});
  }
}

/* ---------------- 弹框 / Toast ---------------- */
function showModal({ title = t("confirm"), message = "", okText = t("ok"), cancelText = t("cancel"), danger = false, onOk }) {
  const overlay = $("modal-overlay");
  $("modal-title").textContent = title;
  $("modal-message").innerHTML = message;
  $("modal-ok").textContent = okText;
  $("modal-cancel").textContent = cancelText;
  $("modal-cancel").hidden = !cancelText;
  const icon = $("modal-icon");
  icon.className = "modal-icon" + (danger ? " danger" : "");
  icon.textContent = danger ? "⚠" : "?";
  overlay.hidden = false;
  const cleanup = () => { overlay.hidden = true; $("modal-ok").onclick = null; $("modal-cancel").onclick = null; };
  $("modal-ok").onclick = () => { cleanup(); onOk && onOk(); };
  $("modal-cancel").onclick = () => { cleanup(); };
}
function toast(msg, type = "ok") {
  const wrap = $("toast-wrap");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 300); }, 3200);
}

/* ---------------- 标题栏 ---------------- */
async function pywebviewApi() {
  try { if (window.pywebview && window.pywebview.api) return window.pywebview.api; } catch (e) { /* ignore */ }
  return null;
}
function bindTitlebar() {
  $("tb-min").addEventListener("click", async () => { const a = await pywebviewApi(); if (a) a.minimize(); });
  $("tb-close").addEventListener("click", async () => { const a = await pywebviewApi(); if (a) a.close(); });
  $("tb-theme").addEventListener("click", () => applyDarkMode(document.documentElement.dataset.theme !== "dark"));
}

/* ---------------- 主题 / 货币 ---------------- */
function applyDarkMode(on) {
  state.darkMode = on;
  document.documentElement.dataset.theme = on ? "dark" : "light";
  $("tb-theme").innerHTML = `◐ <span data-i18n="${on ? "themeLight" : "themeDark"}">${on ? t("themeLight") : t("themeDark")}</span>`;
  try { localStorage.setItem("gousage-dark", on ? "1" : "0"); } catch (e) { /* ignore */ }
  syncThemePills();
  refreshIcons();
  rerenderCharts();
}
function syncThemePills() {
  document.querySelectorAll("#set-theme-pills .pill").forEach((b) => b.classList.toggle("active", b.dataset.v === (state.darkMode ? "dark" : "light")));
}
function applyCurrency(cur) {
  state.currency = cur;
  document.querySelectorAll("#set-currency-pills .pill").forEach((b) => b.classList.toggle("active", b.dataset.v === cur));
  try { localStorage.setItem("gousage-currency", cur); } catch (e) { /* ignore */ }
  if (!state.data) return;
  rerenderCharts();
  renderOverview(state.data.totals);
  renderStatsTotal(state.data.totals);
  renderDetail6(state.data.totals);
  loadRecords().catch(() => {});
}

/* ---------------- 页面路由 ---------------- */
function switchPage(page) {
  state.page = page;
  document.querySelectorAll(".page").forEach((p) => (p.hidden = true));
  $("page-" + page).hidden = false;
  document.querySelectorAll(".side-item").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  if (page === "home" || page === "stats") loadDashboard();
  if (page === "settings") renderSettings();
}

/* ---------------- 骨架屏 ---------------- */
function renderSkeletons() {
  const sBlock = `<div class="ub skeleton"><div class="sk-line w40"></div><div class="sk-line w20 lg"></div><div class="sk-bar"></div><div class="sk-line w60"></div></div>`;
  $("usage-blocks").innerHTML = sBlock.repeat(3);
  const sKpi = `<div class="card kpi skeleton"><div class="sk-line w30"></div><div class="sk-line w40 lg"></div><div class="sk-line w50"></div></div>`;
  $("overview-grid").innerHTML = sKpi.repeat(6);
  // 趋势图骨架: 保留 canvas, 叠加灰色遮罩 (数据到后移除)
  const trendBox = document.querySelector(".today-trend .chart-box");
  if (trendBox) trendBox.classList.add("sk-box");
  if (!$("stats-total-cards").innerHTML) $("stats-total-cards").innerHTML = sKpi.repeat(4);
  if (!$("stats-detail6").innerHTML) $("stats-detail6").innerHTML = `<div class="tc skeleton"><div class="sk-line w40"></div><div class="sk-line w50 lg"></div><div class="sk-line w30"></div></div>`.repeat(6);
}

/* ---------------- 数据加载 ---------------- */
let loadSeq = 0;
async function loadDashboard(quiet = false) {
  const seq = ++loadSeq;
  if (!state.data) renderSkeletons();
  showLoading(true);
  try {
    const range = state.page === "stats" ? state.statsRange : state.range;
    const data = await api(`/api/dashboard?range=${range}`);
    if (seq !== loadSeq) return;
    renderAll(data);
    showLoading(false);
  } catch (e) {
    if (seq === loadSeq) showLoading(false);
    if (!quiet) console.error("dashboard load failed", e);
  }
}
function showLoading(show) { $("top-loading").hidden = !show; }

/* ---------------- 首页: 用量块 ---------------- */
function renderUsageBlocks(quota) {
  const row = $("usage-blocks");
  if (!quota || !quota.success) {
    if (quota && !quota.success) {
      clearTimeout(state.quotaRetryTimer);
      row.innerHTML = `<div class="ub ub-error">${t("quotaFail")}：${escapeHtml(quota.error || "?")}，${t("retryTip")}</div>`;
      return;
    }
    if (state.quotaRetryTimer) clearTimeout(state.quotaRetryTimer);
    state.quotaRetryTimer = setTimeout(() => loadDashboard(true), 5000);
    row.innerHTML = `<div class="ub skeleton"><div class="sk-line w40"></div><div class="sk-line w20 lg"></div><div class="sk-bar"></div><div class="sk-line w60"></div></div>`.repeat(3);
    return;
  }
  if (state.quotaRetryTimer) { clearTimeout(state.quotaRetryTimer); state.quotaRetryTimer = null; }
  const blocks = [];
  for (const w of quota.windows || []) {
    const used = Number(w.used) || 0;
    blocks.push({
      cls: w.label === "5h Rolling" ? "c-rolling" : w.label === "Weekly" ? "c-week" : "c-month",
      label: (QUOTA_LABEL[w.label] || (() => w.label))(),
      used: used,
      remaining: (Number(w.remaining) || 0).toFixed(0) + "%",
      reset: `${t("resetsIn")} ${fmtDur(w.reset_in_sec)}`,
    });
  }
  row.innerHTML = blocks.map((b) => `
    <div class="ub ${b.cls}">
      <div class="ub-head"><span class="ub-l">${b.label}</span><span class="ub-rem">${t("remaining")} ${b.remaining}</span></div>
      <div class="ub-bar"><div class="ub-bar-fill" style="width:${b.used}%"></div></div>
      <div class="ub-meta"><span>${t("used")} ${b.used.toFixed(0)}%</span><span>${b.reset}</span></div>
    </div>`).join("");
}

/* ---------------- 首页: 用量概览 6 格 ---------------- */
function renderOverview(totals) {
  const totalTokens = totals.total_input_tokens + totals.total_output_tokens + totals.total_reasoning_tokens;
  const cards = [
    { cls: "c-green", l: t("hitRate"), v: totals.hit_rate.toFixed(1) + "%", s: `${t("hit")} ${fmtTokens(totals.cache_hit_tokens)} · ${t("miss")} ${fmtTokens(totals.uncached_input_tokens)}` },
    { cls: "c-cyan", l: t("hitAmount"), v: fmtTokens(totals.cache_hit_tokens), s: `${t("pctOfInput")} ${totals.hit_rate.toFixed(1)}%` },
    { cls: "c-blue", l: t("totalTokens"), v: fmtTokens(totalTokens), s: t("inclCache") },
    { cls: "c-slate", l: t("totalRequests"), v: fmtInt(totals.request_count), s: t("currentRange") },
    { cls: "c-amber", l: t("totalCost"), v: fmtMoney(totals.total_cost_usd), s: `${t("avgPer")} ${fmtMoney(totals.request_count ? totals.total_cost_usd / totals.request_count : 0)}${t("perReq")}` },
    { cls: "c-violet", l: t("sessions"), v: fmtInt(totals.session_count), s: t("dedup") },
  ];
  $("overview-grid").innerHTML = cards.map((c) => `
    <div class="card kpi ${c.cls}"><div class="kpi-l">${c.l}</div><div class="kpi-v">${c.v}</div><div class="kpi-s">${c.s}</div></div>`).join("");
}

/* ---------------- 首页: 今日趋势 24h ---------------- */
let cToday = null;
function chartToday(trend) {
  const canvas = $("today-chart");
  if (cToday) cToday.destroy();
  const box = canvas ? canvas.parentElement : null;
  if (box) box.classList.remove("sk-box");  // 移除骨架遮罩
  if (!trend || !trend.length) { cToday = null; return; }
  cToday = new Chart(canvas, {
    type: "bar",
    data: {
      labels: trend.map((d) => d.hour),
      datasets: [
        { label: t("input"), data: trend.map((d) => d.input), backgroundColor: COLOR.input, borderRadius: 2, barPercentage: 0.8 },
        { label: t("output"), data: trend.map((d) => d.output), backgroundColor: COLOR.output, borderRadius: 2, barPercentage: 0.8 },
      ],
    },
    options: {
      responsive: false, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 }, color: cssVar("--text2") } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: cssVar("--text3"), font: { size: 10 }, maxTicksLimit: 8 } },
        y: { grid: { color: cssVar("--grid") }, ticks: { color: cssVar("--text3"), font: { size: 10 }, callback: (v) => fmtTokens(v) } },
      },
    },
  });
  cToday.resize();
}

/* ---------------- 统计页: 4 总卡 + 6 明细 ---------------- */
function renderStatsTotal(totals) {
  const totalTokens = totals.total_input_tokens + totals.total_output_tokens + totals.total_reasoning_tokens;
  const cards = [
    { cls: "c-amber", l: t("totalCost"), v: fmtMoney(totals.total_cost_usd), s: `${t("avgPer")} ${fmtMoney(totals.request_count ? totals.total_cost_usd / totals.request_count : 0)}${t("perReq")}` },
    { cls: "c-blue", l: t("totalRequests"), v: fmtInt(totals.request_count), s: t("currentRange") },
    { cls: "c-violet", l: t("totalTokens"), v: fmtTokens(totalTokens), s: `${t("input")} ${fmtTokens(totals.total_input_tokens)} · ${t("output")} ${fmtTokens(totals.total_output_tokens)}` },
    { cls: "c-green", l: t("hitRate"), v: totals.hit_rate.toFixed(1) + "%", s: `${t("hit")} ${fmtTokens(totals.cache_hit_tokens)} / ${t("miss")} ${fmtTokens(totals.uncached_input_tokens)}` },
  ];
  $("stats-total-cards").innerHTML = cards.map((c) => `
    <div class="card kpi ${c.cls}"><div class="kpi-l">${c.l}</div><div class="kpi-v">${c.v}</div><div class="kpi-s">${c.s}</div></div>`).join("");
}
function renderDetail6(totals) {
  const total = totals.uncached_input_tokens + totals.total_output_tokens + totals.total_reasoning_tokens;
  const cards = [
    { l: t("input"), v: fmtTokens(totals.uncached_input_tokens), s: `${t("inclCache")} ${fmtTokens(totals.total_input_tokens)}` },
    { l: t("output"), v: fmtTokens(totals.total_output_tokens), s: t("output") },
    { l: t("colReasoning"), v: fmtTokens(totals.total_reasoning_tokens), s: total ? ((totals.total_reasoning_tokens / total) * 100).toFixed(1) + "%" : "0%" },
    { l: t("colCacheRead"), v: fmtTokens(totals.cache_hit_tokens), s: `${t("hitRate")} ${totals.hit_rate.toFixed(1)}%` },
    { l: lang === "zh" ? "缓存写" : "Cache Write", v: fmtTokens(totals.cache_write_tokens), s: lang === "zh" ? "新写入缓存" : "new cache writes" },
    { l: t("sessions"), v: fmtInt(totals.session_count), s: t("dedup") },
  ];
  $("stats-detail6").innerHTML = cards.map((c) => `
    <div class="tc"><div class="tc-l">${c.l}</div><div class="tc-v">${c.v}</div><div class="tc-s">${c.s}</div></div>`).join("");
}

/* ---------------- 统计页: 模型用量 ---------------- */
let cModel = null;
function chartModel(models) {
  const canvas = $("mr-chart");
  if (cModel) cModel.destroy();
  if (!models || !models.length) { cModel = null; $("mr-list").innerHTML = ""; return; }
  const dim = state.modelDim;
  const getVal = (m) => (dim === "input" ? m.uncached_input_tokens : dim === "output" ? m.total_output_tokens : m.total_cost_usd);
  const fmt = dim === "cost" ? (v) => fmtMoney(v) : fmtTokens;
  const sorted = [...models].sort((a, b) => getVal(b) - getVal(a));
  const top = sorted.slice(0, 6);
  const total = sorted.reduce((s, m) => s + getVal(m), 0);
  const palette = [COLOR.input, COLOR.output, COLOR.reasoning, COLOR.cache, COLOR.cost, "#ec4899"];
  cModel = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: top.map((m) => m.model),
      datasets: [{ data: top.map(getVal), backgroundColor: palette, borderWidth: 2, borderColor: cssVar("--card") }],
    },
    options: {
      responsive: false, maintainAspectRatio: false, cutout: "60%",
      plugins: {
        legend: { position: "right", labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 }, color: cssVar("--text2") } },
        tooltip: { callbacks: { label: (it) => ` ${it.label}: ${fmt(it.parsed)}${total ? ` (${((it.parsed / total) * 100).toFixed(1)}%)` : ""}` } },
      },
    },
  });
  cModel.resize();
  $("mr-list").innerHTML = sorted.slice(0, 3).map((m, i) => `
    <div class="mr-item"><span class="mr-rank">#${i + 1}</span>
    <span class="mr-name">${modelIcon(m.model)}<span class="txt">${escapeHtml(m.model)}</span></span>
    <span class="mr-sub">${fmtInt(m.request_count)} · ${t("hitRate")} ${m.hit_rate}%</span>
    <span class="mr-cost">${fmtMoney(m.total_cost_usd)}</span></div>`).join("");
}

/* ---------------- 统计页: 用量趋势 ---------------- */
let cTrend = null;
function chartTrend(trend) {
  const canvas = $("trend-chart");
  if (cTrend) cTrend.destroy();
  if (!trend || !trend.length) { cTrend = null; return; }
  cTrend = new Chart(canvas, {
    data: {
      labels: trend.map((d) => d.date.slice(5)),
      datasets: [
        { type: "line", label: t("totalCost"), data: trend.map((d) => d.total_cost_usd), borderColor: COLOR.input, borderWidth: 2, pointRadius: 1.5, tension: 0.3, yAxisID: "y" },
        { type: "line", label: t("totalRequests"), data: trend.map((d) => d.request_count), borderColor: COLOR.output, borderWidth: 2, pointRadius: 1.5, tension: 0.3, yAxisID: "y1", borderDash: [4, 3] },
        { type: "line", label: t("totalTokens"), data: trend.map((d) => d.total_input_tokens + d.total_output_tokens + d.total_reasoning_tokens), borderColor: COLOR.reasoning, borderWidth: 2, pointRadius: 1.5, tension: 0.3, yAxisID: "y2" },
      ],
    },
    options: {
      responsive: false, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 }, color: cssVar("--text2") } },
        tooltip: {
          callbacks: {
            label: (item) => {
              if (item.dataset.label === t("totalTokens")) return ` ${item.dataset.label}: ${fmtTokens(item.parsed.y)}`;
              if (item.dataset.label === t("totalRequests")) return ` ${item.dataset.label}: ${fmtInt(item.parsed.y)}`;
              return ` ${item.dataset.label}: $${item.parsed.y}`;
            },
          },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: cssVar("--text3"), font: { size: 10 }, maxTicksLimit: 8 } },
        y: { position: "left", grid: { color: cssVar("--grid") }, ticks: { color: cssVar("--text3"), font: { size: 10 }, callback: (v) => "$" + v } },
        y1: { position: "right", grid: { display: false }, ticks: { color: cssVar("--text3"), font: { size: 10 } } },
        y2: { position: "right", display: false },  // 总 Token 独立隐藏轴
      },
    },
  });
  cTrend.resize();
}

/* ---------------- 使用记录 ---------------- */
let recLoading = false;
async function loadRecords() {
  if (recLoading) return;
  recLoading = true;
  const body = $("records-body");
  try {
    const q = new URLSearchParams({ page: state.records.page, page_size: state.records.pageSize });
    if (state.records.model) q.set("model", state.records.model);
    const data = await api(`/api/usage/records?${q}`);
    state.records.total = data.total;
    const sel = $("rec-model-filter");
    const cur = sel.value;
    sel.innerHTML = '<option value="">' + t("allModels") + '</option>' + data.models.map((m) => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join("");
    sel.value = state.records.model || cur || "";
    $("rec-count").textContent = `${t("totalN")} ${fmtInt(data.total)} ${t("items")}`;
    if (!data.records.length) {
      body.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--text3);padding:24px">${t("noData")}</td></tr>`;
    } else {
      body.innerHTML = data.records.map((r) => `
        <tr><td>${fmtDateTime(r.created_at)}</td>
        <td><span class="model-cell">${modelIcon(r.model)}${escapeHtml(r.model)}</span></td>
        <td class="num">${fmtInt(r.input_tokens)}</td>
        <td class="num">${fmtInt(r.output_tokens)}</td>
        <td class="num">${fmtInt(r.reasoning_tokens)}</td>
        <td class="num">${fmtInt(r.cache_read_tokens)}</td>
        <td class="num">${fmtMoney(r.cost_usd)}</td>
        <td><span class="plan-badge">${PLAN_BADGE[(r.plan || "").toLowerCase()] || (r.plan || "").toUpperCase() || "—"}</span></td></tr>`).join("");
    }
    const totalPages = Math.max(1, Math.ceil(data.total / state.records.pageSize));
    $("rec-pager").textContent = `${t("pageOf")} ${state.records.page} ${t("ofPages")} ${totalPages}`;
    $("pg-prev").disabled = state.records.page <= 1;
    $("pg-next").disabled = state.records.page >= totalPages;
  } catch (e) {
    body.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--red);padding:24px">${t("loadFailed")}: ${escapeHtml(e.message)}</td></tr>`;
  } finally {
    recLoading = false;
  }
}

/* ---------------- 模型图标 ---------------- */
function modelIcon(m) {
  const base = String(m || "").toLowerCase().split("-")[0];
  const map = { deepseek: "deepseek", glm: "glm", gpt: "gpt", grok: "grok", kimi: "kimi", mimo: "mimo", minimax: "minimax", qwen: "qwen", hy: "hy" };
  const name = map[base] || "deepseek";
  const dark = document.documentElement.dataset.theme === "dark";
  const themed = dark && ["gpt", "grok", "mimo"].includes(name) ? `${name}-color` : name;
  return `<img src="icons/${themed}.svg" alt="${escapeHtml(m)}" title="${escapeHtml(m)}" style="width:16px;height:16px">`;
}
function refreshIcons() {
  if (!document.getElementById("page-stats").hidden) chartModel(state.data?.models);
}

/* ---------------- 组装 ---------------- */
function renderAll(data) {
  state.data = data;
  if (data.exchange_rate?.usd_cny) state.exchangeRate = data.exchange_rate.usd_cny;
  renderUsageBlocks(data.quota);
  renderOverview(data.totals);
  const homeVisible = !document.getElementById("page-home").hidden;
  const statsVisible = !document.getElementById("page-stats").hidden;
  // 只重建当前可见页面的图表 (hidden 页面的 canvas 尺寸为 0, 创建会失败)
  if (homeVisible) chartToday(data.today_trend);
  if (statsVisible) {
    renderStatsTotal(data.totals);
    renderDetail6(data.totals);
    chartModel(data.models);
    chartTrend(data.trend);
    $("trend-hint").textContent = t("trendHint");
    loadRecords().catch(() => {});
  }
  $("tb-sync").textContent = data.logged_in ? `${t("lastSync")} ${fmtRelative(data.sync?.last_sync_at)} · ${fmtInt(data.sync?.total_records || 0)} ${t("records")}` : t("notLoggedIn");
  $("tb-login").innerHTML = data.logged_in ? `<b>${t("loggedIn")}</b> ${maskWs(data)}` : t("notLoggedIn");
  $("tb-login").style.color = data.logged_in ? "" : "var(--red)";
  const st = data.server_time || "";
  if (st) $("tb-updated").textContent = `${t("updatedAt")} ${st.slice(0, 16).replace("T", " ")}`;
  renderSyncBanner(data.progress);
  renderSettingsSyncProgress(data.progress);
}
function maskWs(data) {
  const ws = data?.quota?.workspace_id || "";
  return ws.length > 12 ? ws.slice(0, 8) + "…" : ws;
}

/* ---------------- 同步 ---------------- */
async function startSync(mode) {
  $("tb-refresh").disabled = true;
  $("btn-full-sync").disabled = true;
  try { await api("/api/sync?mode=" + mode, { method: "POST" }); } catch (e) { console.error(e); }
  pollUntilIdle();
}
function pollUntilIdle() {
  if (state.syncTimer) clearInterval(state.syncTimer);
  state.syncTimer = setInterval(async () => {
    try {
      const st = await api("/api/state");
      renderSyncBanner(st.progress);
      renderSettingsSyncProgress(st.progress);
      if (!st.progress.running) {
        clearInterval(state.syncTimer); state.syncTimer = null;
        $("tb-refresh").disabled = false;
        $("btn-full-sync").disabled = false;
        await loadDashboard();
        if (state.page === "settings") renderSettings();
      }
    } catch (e) { /* ignore */ }
  }, 2500);
}
function renderSyncBanner(progress) {
  $("sync-indicator").hidden = !(progress && progress.running);
}
function renderSettingsSyncProgress(progress) {
  if (!progress || !progress.running) {
    $("set-sync-progress-desc").textContent = t("fullSyncDesc");
    $("set-sync-progress-val").textContent = "";
    return;
  }
  const phase = progress.phase === "usage" ? t("syncing") : t("syncing");
  $("set-sync-progress-desc").textContent = `${phase} · ${t("pageOf")} ${progress.page + 1}`;
  $("set-sync-progress-val").textContent = `${t("totalN")} ${fmtInt(progress.inserted)}`;
}

/* ---------------- 设置页 ---------------- */
async function renderSettings() {
  try {
    const st = await api("/api/state");
    const acc = st.account || {};
    const sync = st.sync || {};
    const logged = st.logged_in;
    $("set-login-state").textContent = logged ? `${t("loggedIn")} · ${acc.workspace_id || "—"}` : t("notLoggedIn");
    const badge = $("set-login-badge");
    badge.textContent = logged ? t("connected") : t("notConnected");
    badge.className = "badge " + (logged ? "ok" : "no");
    $("set-workspace").textContent = acc.workspace_id || "—";
    $("set-sync-info").textContent = sync.last_sync_at
      ? `${t("lastSync")} ${fmtDateTime(sync.last_sync_at)} (${sync.last_sync_status}) · ${t("totalN")} ${fmtInt(sync.total_records || 0)} ${t("items")}`
      : t("never");
    $("set-datadir").textContent = st.datadir || "—";
    const settings = await api("/api/settings");
    state.settings = settings;
    syncSettingsPills();
    $("set-auto-sync").checked = settings.auto_sync !== false;
  } catch (e) { /* ignore */ }
}
function syncSettingsPills() {
  const s = state.settings;
  document.querySelectorAll("#set-interval-pills .pill").forEach((b) => b.classList.toggle("active", Number(b.dataset.v) === Number(s.sync_interval_sec)));
  document.querySelectorAll("#set-window-pills .pill").forEach((b) => b.classList.toggle("active", (s.window_days == null ? "all" : String(s.window_days)) === b.dataset.v));
}

/* ---------------- 登录状态 ---------------- */
let loginPollTimer = null;
function showLoginOverlay(show) {
  // 遮罩背景不透明, 直接显示即可覆盖页面; 不要隐藏 .app (会连同遮罩一起隐藏)
  $("login-overlay").hidden = !show;
  if (show) {
    // 欢迎页显示时轮询登录状态: 独立登录窗登录成功后自动进入面板
    if (loginPollTimer) clearInterval(loginPollTimer);
    loginPollTimer = setInterval(async () => {
      try {
        const st = await api("/api/state");
        if (st.logged_in) {
          clearInterval(loginPollTimer);
          loginPollTimer = null;
          showLoginOverlay(false);
          await loadDashboard();
          renderSettings().catch(() => {});
        }
      } catch (e) { /* ignore */ }
    }, 2000);
  } else if (loginPollTimer) {
    clearInterval(loginPollTimer);
    loginPollTimer = null;
  }
}
async function checkState() {
  try {
    const st = await api("/api/state");
    if (!st.logged_in) { showLoginOverlay(true); return; }
    showLoginOverlay(false);
    if (st.progress && st.progress.running) pollUntilIdle();
    await loadDashboard();
  } catch (e) { console.error("state check failed", e); }
}

/* ---------------- 事件绑定 ---------------- */
function bindEvents() {
  document.querySelectorAll(".side-item").forEach((btn) => btn.addEventListener("click", () => switchPage(btn.dataset.page)));

  document.querySelectorAll("#home-pills .pill").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#home-pills .pill").forEach((x) => x.classList.remove("active"));
    b.classList.add("active"); state.range = b.dataset.r; loadDashboard();
  }));
  document.querySelectorAll("#stats-pills .pill").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#stats-pills .pill").forEach((x) => x.classList.remove("active"));
    b.classList.add("active"); state.statsRange = b.dataset.r; loadDashboard();
  }));
  $("mr-dim").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    document.querySelectorAll("#mr-dim button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active"); state.modelDim = b.dataset.dim;
    if (state.data) chartModel(state.data.models);
  });
  $("tb-refresh").addEventListener("click", () => startSync("incremental"));
  $("btn-full-sync").addEventListener("click", () => {
    showModal({ title: t("fullSync"), message: t("fullSyncConfirm"), okText: t("startSync"), onOk: () => startSync("full") });
  });
  $("pg-prev").addEventListener("click", () => { if (state.records.page > 1) { state.records.page--; loadRecords(); } });
  $("pg-next").addEventListener("click", () => { state.records.page++; loadRecords(); });
  $("rec-model-filter").addEventListener("change", (e) => { state.records.model = e.target.value; state.records.page = 1; loadRecords(); });

  document.querySelectorAll("#set-interval-pills .pill").forEach((b) => b.addEventListener("click", async () => {
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ sync_interval_sec: Number(b.dataset.v) }) });
    state.settings = await api("/api/settings");
    syncSettingsPills(); restartAutoSync(); toast(`${t("syncIntervalSet")} ${b.textContent}`);
  }));
  document.querySelectorAll("#set-window-pills .pill").forEach((b) => b.addEventListener("click", async () => {
    const v = b.dataset.v === "all" ? null : Number(b.dataset.v);
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ window_days: v }) });
    state.settings = await api("/api/settings");
    syncSettingsPills();
    toast(t("syncRangeUpdated"));
  }));
  document.querySelectorAll("#set-theme-pills .pill").forEach((b) => b.addEventListener("click", () => applyDarkMode(b.dataset.v === "dark")));
  document.querySelectorAll("#set-currency-pills .pill").forEach((b) => b.addEventListener("click", () => applyCurrency(b.dataset.v)));
  document.querySelectorAll("#set-lang-pills .pill").forEach((b) => b.addEventListener("click", () => applyLang(b.dataset.v)));
  $("set-auto-sync").addEventListener("change", (e) => {
    state.settings.auto_sync = e.target.checked;
    api("/api/settings", { method: "PUT", body: JSON.stringify({ auto_sync: e.target.checked }) }).catch(() => {});
    restartAutoSync();
  });
  $("btn-relogin").addEventListener("click", () => {
    showModal({
      title: t("relogin"), message: t("reloginConfirm"), okText: t("goLogin"),
      onOk: async () => {
        await api("/api/logout", { method: "POST" });  // 清除旧凭据
        const a = await pywebviewApi();
        if (a && a.open_login) { a.open_login(); return; }
        await api("/api/relogin", { method: "POST" });  // 浏览器兜底
      },
    });
  });
  $("btn-logout").addEventListener("click", () => {
    showModal({ title: t("logout"), danger: true, message: t("logoutConfirm"), okText: t("quit"), onOk: async () => { await api("/api/logout", { method: "POST" }); showLoginOverlay(true); } });
  });
  $("btn-login").addEventListener("click", async () => {
    const a = await pywebviewApi();
    if (a && a.open_login) { a.open_login(); return; }  // 弹出独立登录窗口
    // 浏览器环境兜底: 跳转授权页
    $("btn-login").disabled = true;
    $("btn-login").textContent = t("loginBtn") + "…";
    await api("/api/relogin", { method: "POST" });
  });
  $("btn-quit-app").addEventListener("click", async () => {
    const a = await pywebviewApi();
    if (a) a.quit();
  });
  bindTitlebar();
}

/* ---------------- 自动同步 ---------------- */
let autoSyncTimer = null;
function restartAutoSync() {
  if (autoSyncTimer) clearInterval(autoSyncTimer);
  if (state.settings.auto_sync === false) return;
  const sec = Math.max(30, Number(state.settings?.sync_interval_sec) || 300) * 1000;
  autoSyncTimer = setInterval(() => {
    const prog = state.data && state.data.progress;
    if (!prog || !prog.running) startSync("incremental");
  }, sec);
}

/* ---------------- 图表辅助 ---------------- */
function cssVar(name) {
  return getComputedStyle(document.body).getPropertyValue(name).trim() || "#8a94a8";
}
function rerenderCharts() {
  if (!state.data) return;
  if (!document.getElementById("page-home").hidden) chartToday(state.data.today_trend);
  if (!document.getElementById("page-stats").hidden) {
    chartModel(state.data.models);
    chartTrend(state.data.trend);
  }
}

/* 窗口尺寸变化: 长防抖(250ms)后执行一次轻量 chart.resize()
   (只处理可见页图表 — hidden 页面容器尺寸为 0, resize() 会死循环卡死) */
function safeResize(chart) {
  if (!chart || !chart.canvas) return;
  const box = chart.canvas.parentElement;
  if (box && box.clientWidth > 0 && box.clientHeight > 0) chart.resize();
}
let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (!document.getElementById("page-home").hidden) safeResize(cToday);
    if (!document.getElementById("page-stats").hidden) {
      safeResize(cModel);
      safeResize(cTrend);
    }
  }, 250);
});

/* ---------------- 启动 ---------------- */
(async function init() {
  let dark = false, cur = "CNY", l = "zh";
  try {
    dark = localStorage.getItem("gousage-dark") === "1";
    cur = localStorage.getItem("gousage-currency") || "CNY";
    l = localStorage.getItem("gousage-lang") || "zh";
  } catch (e) { /* ignore */ }
  applyLang(l);
  applyDarkMode(dark);
  applyCurrency(cur);
  bindEvents();
  try { state.settings = await api("/api/settings"); } catch (e) { /* ignore */ }
  syncSettingsPills();
  $("set-auto-sync").checked = state.settings.auto_sync !== false;
  await checkState();
  restartAutoSync();
})();
