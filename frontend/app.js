/**
 * BusinessPilot Frontend Application Controller
 * Handles view routing, Apache ECharts initialization, live API polling,
 * file upload pipelines, schema mapping previews, and AI queries.
 */

const API_BASE = ""; // Relative to host
let currentCompanyId = localStorage.getItem("business_pilot_company_id") || localStorage.getItem("bizlens_company_id") || "";
let currentCurrency = localStorage.getItem("business_pilot_currency") || localStorage.getItem("bizlens_currency") || "TZS";
let currentUserName = localStorage.getItem("business_pilot_user_name") || localStorage.getItem("bizlens_user_name") || "Business Owner";
let currentCompanyName = localStorage.getItem("business_pilot_company_name") || localStorage.getItem("bizlens_company_name") || "My Business";
let currentBusinessType = localStorage.getItem("business_pilot_business_type") || "Retail";
let activeUploadedFilePath = null;

// Chart Instances
let revTrendChart = null;
let expenseDonutChart = null;
let cashProjectionChart = null;
let pnlBridgeChart = null;

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  setupUploadDropzone();
  setupAISearch();
  setupWorkspaceControls();
  checkAuthSession();
  loadDataSourcesList();
  setupUserAvatarUpload();
  setupFigureScrollObserver();
  setupIndustryPreview();

  // Initial count-up for figures on page enter
  const initialActivePanel = document.querySelector(".view-panel.active");
  if (initialActivePanel) {
    setTimeout(() => {
      animateFiguresInContainer(initialActivePanel);
    }, 150);
  }

  function resizeAllCharts() {
    if (revTrendChart) revTrendChart.resize();
    if (expenseDonutChart) expenseDonutChart.resize();
    if (cashProjectionChart) cashProjectionChart.resize();
    if (pnlBridgeChart) pnlBridgeChart.resize();
    if (forecastChartInstance) forecastChartInstance.resize();
  }

  window.addEventListener("resize", resizeAllCharts);

  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => {
      resizeAllCharts();
    });
    document.querySelectorAll(".chart-container").forEach(el => ro.observe(el));
  }
});

// -------------------------------------------------------------
// FIGURE COUNT-UP ANIMATIONS (Page Enter & Scroll Observer)
// -------------------------------------------------------------
let figureObserver = null;

function parseFigure(str) {
  if (typeof str !== "string") str = String(str || "");
  const match = str.trim().match(/^([^0-9\-+]*)([-+]?[0-9][0-9,]*(?:\.[0-9]+)?)(.*)$/);
  if (!match) return null;
  const prefix = match[1];
  const numStr = match[2];
  const suffix = match[3];
  const hasCommas = numStr.includes(",");
  const cleanNum = numStr.replace(/,/g, "");
  const targetNum = parseFloat(cleanNum);
  if (isNaN(targetNum)) return null;
  const decimals = cleanNum.includes(".") ? cleanNum.split(".")[1].length : 0;
  return { prefix, targetNum, decimals, hasCommas, suffix };
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function animateFigureCount(element, finalValue = null, duration = 1100) {
  if (!element) return;

  if (finalValue !== null && finalValue !== undefined) {
    element.setAttribute("data-target-val", String(finalValue));
  } else {
    finalValue = element.innerText.trim();
    element.setAttribute("data-target-val", finalValue);
  }

  const parsed = parseFigure(finalValue);
  if (!parsed) {
    element.innerText = finalValue;
    return;
  }

  const { prefix, targetNum, decimals, hasCommas, suffix } = parsed;

  if (element._countAnimId) {
    cancelAnimationFrame(element._countAnimId);
    element._countAnimId = null;
  }

  const card = element.closest(".kpi-card");
  if (card) {
    card.classList.remove("counting-active");
    void card.offsetWidth;
    card.classList.add("counting-active");
  }

  const startTime = performance.now();

  function step(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(1, elapsed / duration);
    const eased = easeOutCubic(progress);
    const currentVal = targetNum * eased;

    let formattedNumber;
    if (decimals > 0) {
      formattedNumber = currentVal.toFixed(decimals);
      if (hasCommas) {
        const parts = formattedNumber.split(".");
        const whole = Math.abs(Math.round(parseFloat(parts[0]))).toLocaleString("en-US");
        parts[0] = currentVal < 0 ? `-${whole}` : whole;
        formattedNumber = parts.join(".");
      }
    } else {
      const rounded = Math.round(currentVal);
      formattedNumber = hasCommas ? Math.abs(rounded).toLocaleString("en-US") : Math.abs(rounded).toString();
      if (rounded < 0) formattedNumber = `-${formattedNumber}`;
    }

    if (formattedNumber === "-0" || formattedNumber === "-0.0") {
      formattedNumber = formattedNumber.replace("-", "");
    }

    element.innerText = `${prefix}${formattedNumber}${suffix}`;

    if (progress < 1) {
      element._countAnimId = requestAnimationFrame(step);
    } else {
      element.innerText = finalValue;
      element._countAnimId = null;
      if (card) card.classList.remove("counting-active");
    }
  }

  element._countAnimId = requestAnimationFrame(step);
}

function animateFiguresInContainer(container, duration = 1100) {
  if (!container) return;
  const elements = container.querySelectorAll(".kpi-value, .count-figure, .kpi-sub span:first-child, #cash-unpaid-invoices, #cash-runway-countdown");
  const now = performance.now();
  elements.forEach((el, index) => {
    el._lastAnimatedAt = now;
    const stagger = Math.min(index * 40, 240);
    setTimeout(() => {
      animateFigureCount(el, null, duration);
    }, stagger);
  });
}

function setupFigureScrollObserver() {
  if (figureObserver) {
    figureObserver.disconnect();
  }

  const scrollContainer = document.querySelector(".content-body");

  figureObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const el = entry.target;
        const parentView = el.closest(".view-panel");
        if (parentView && !parentView.classList.contains("active")) {
          return;
        }

        const now = performance.now();
        if (el._lastAnimatedAt && (now - el._lastAnimatedAt < 1800)) {
          return;
        }

        if (el.classList.contains("kpi-value") || el.classList.contains("count-figure")) {
          el._lastAnimatedAt = now;
          animateFigureCount(el);
        } else if (el.classList.contains("kpi-card")) {
          const valEl = el.querySelector(".kpi-value, .count-figure");
          if (valEl) {
            valEl._lastAnimatedAt = now;
            animateFigureCount(valEl);
          }
        }
      }
    });
  }, {
    root: scrollContainer || null,
    rootMargin: "0px 0px -20px 0px",
    threshold: 0.15
  });

  refreshFigureObserver();
}

function refreshFigureObserver() {
  if (!figureObserver) return;
  document.querySelectorAll(".kpi-card, .kpi-value, .count-figure").forEach(el => {
    figureObserver.observe(el);
  });
}

// -------------------------------------------------------------
// NAVIGATION ROUTER
// -------------------------------------------------------------
function setupNavigation() {
  const navItems = document.querySelectorAll(".nav-item");
  const sidebar = document.querySelector(".sidebar");
  const backdrop = document.getElementById("sidebar-backdrop");
  const menuBtn = document.getElementById("btn-mobile-menu");

  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", () => {
      sidebar.classList.toggle("open");
      if (backdrop) backdrop.classList.toggle("active");
    });
  }

  if (backdrop && sidebar) {
    backdrop.addEventListener("click", () => {
      sidebar.classList.remove("open");
      backdrop.classList.remove("active");
    });
  }

  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const targetView = item.getAttribute("data-view");
      switchView(targetView);
      if (sidebar && sidebar.classList.contains("open")) {
        sidebar.classList.remove("open");
        if (backdrop) backdrop.classList.remove("active");
      }
    });
  });
}

function switchView(viewName) {
  // Update sidebar active class
  document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
  const activeNav = document.querySelector(`.nav-item[data-view="${viewName}"]`);
  if (activeNav) activeNav.classList.add("active");

  // Show target panel
  document.querySelectorAll(".view-panel").forEach(p => p.classList.remove("active"));
  const targetPanel = document.getElementById(`view-${viewName}`);
  if (targetPanel) {
    targetPanel.classList.add("active");
    setTimeout(() => {
      animateFiguresInContainer(targetPanel);
      refreshFigureObserver();
    }, 60);
  }

  // Resize charts if visible
  if (viewName === "dashboard") {
    setTimeout(() => {
      if (revTrendChart) revTrendChart.resize();
      if (expenseDonutChart) expenseDonutChart.resize();
    }, 100);
  } else if (viewName === "cashflow") {
    loadCashFlowData();
    setTimeout(() => {
      if (cashProjectionChart) cashProjectionChart.resize();
    }, 100);
  } else if (viewName === "sales") {
    loadSalesData();
  } else if (viewName === "customers") {
    loadCustomersData();
  } else if (viewName === "inventory") {
    loadInventoryData();
  } else if (viewName === "expenses") {
    loadExpensesData();
  } else if (viewName === "analytics") {
    loadAnalyticsData();
    setTimeout(() => {
      if (pnlBridgeChart) pnlBridgeChart.resize();
    }, 100);
  } else if (viewName === "forecasts") {
    loadForecastsData();
  } else if (viewName === "alerts") {
    loadAlertsData("ALL");
  } else if (viewName === "reports") {
    loadReportsData();
  } else if (viewName === "datasources") {
    loadDataSourcesList();
  }
}

// -------------------------------------------------------------
// DATA LOADERS
// -------------------------------------------------------------
async function loadAllDashboardData() {
  try {
    const res = await fetch(`${API_BASE}/api/dashboard?company_id=${currentCompanyId}`);
    const data = await res.json();
    renderDashboard(data);
  } catch (err) {
    console.error("Failed to load dashboard data:", err);
  }
}

function getCurrencySymbol(curr) {
  const c = (curr || currentCurrency || "TZS").toUpperCase();
  const map = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "TZS": "TZS",
    "KES": "KSh",
    "UGX": "USh",
    "RWF": "RF",
    "ZAR": "R",
    "NGN": "₦",
    "GHS": "GH₵",
    "CAD": "CA$",
    "AUD": "AU$",
    "INR": "₹",
    "JPY": "¥",
    "CNY": "¥"
  };
  return map[c] || c;
}

function formatCurrency(val, currency = null) {
  const curr = currency || currentCurrency || "TZS";
  const sym = getCurrencySymbol(curr);
  if (val === undefined || val === null) {
    return sym.length > 1 ? `${sym} 0` : `${sym}0`;
  }
  const abs = Math.abs(val);
  let formatted = abs.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (abs >= 1000000) {
    formatted = `${(val / 1000000).toFixed(1)}M`;
  } else if (abs >= 1000) {
    formatted = `${(val / 1000).toFixed(1)}K`;
  } else {
    formatted = `${val.toFixed(0)}`;
  }
  return sym.length > 1 ? `${sym} ${formatted}` : `${sym}${formatted}`;
}

function renderDashboard(data) {
  const { briefing, kpi_cards, inventory, cash, trends, company } = data;

  if (company && company.currency) {
    currentCurrency = company.currency;
    localStorage.setItem("business_pilot_currency", currentCurrency);
  }

  if (company && company.name) {
    currentCompanyName = company.name;
    document.getElementById("sidebar-company-name").innerText = company.name;
    document.getElementById("sidebar-company-sub").innerText = `${company.industry || company.business_type || "Retail"} · ${currentCurrency}`;
    const avatar = document.getElementById("sidebar-company-avatar");
    if (avatar) avatar.innerText = company.name.charAt(0).toUpperCase();
  }

  // 1. KPI Cards
  const isRevZero = !kpi_cards || !kpi_cards.revenue || kpi_cards.revenue.value === 0;
  document.getElementById("kpi-rev-val").innerText = formatCurrency(kpi_cards ? kpi_cards.revenue.value : 0, currentCurrency);
  const revGrowth = kpi_cards ? kpi_cards.revenue.growth : 0;
  const growthEl = document.getElementById("kpi-rev-growth");
  if (isRevZero && revGrowth === 0) {
    growthEl.innerText = "0%";
    growthEl.className = "trend-up";
  } else {
    growthEl.innerText = `${revGrowth >= 0 ? "↑" : "↓"} ${Math.abs(revGrowth)}%`;
    growthEl.className = revGrowth >= 0 ? "trend-up" : "trend-down";
  }

  const isProfitZero = !kpi_cards || !kpi_cards.net_profit || kpi_cards.net_profit.value === 0;
  document.getElementById("kpi-profit-val").innerText = formatCurrency(kpi_cards ? kpi_cards.net_profit.value : 0, currentCurrency);
  const profitMarginEl = document.getElementById("kpi-profit-margin");
  if (isProfitZero && (!kpi_cards || kpi_cards.net_profit.margin === 0)) {
    profitMarginEl.innerText = "Margin: 0%";
    profitMarginEl.className = "trend-up";
  } else {
    profitMarginEl.innerText = `Margin: ${kpi_cards ? kpi_cards.net_profit.margin : 0}%`;
    profitMarginEl.className = (kpi_cards && kpi_cards.net_profit.value >= 0) ? "trend-up" : "trend-down";
  }

  const isExpZero = !kpi_cards || !kpi_cards.expenses || kpi_cards.expenses.value === 0;
  document.getElementById("kpi-exp-val").innerText = formatCurrency(kpi_cards ? kpi_cards.expenses.value : 0, currentCurrency);
  const expGrowthEl = document.getElementById("kpi-exp-growth");
  if (isExpZero && (!kpi_cards || kpi_cards.expenses.growth === 0)) {
    expGrowthEl.innerText = "0%";
    expGrowthEl.className = "trend-up";
  } else {
    expGrowthEl.innerText = `${kpi_cards ? (kpi_cards.expenses.growth >= 0 ? "↑" : "↓") : "↑"} ${Math.abs(kpi_cards ? kpi_cards.expenses.growth : 0)}%`;
    expGrowthEl.className = (kpi_cards && kpi_cards.expenses.growth <= 0) ? "trend-up" : "trend-down";
  }

  const isCashZero = !kpi_cards || !kpi_cards.cash_balance || kpi_cards.cash_balance.value === 0;
  document.getElementById("kpi-cash-val").innerText = formatCurrency(kpi_cards ? kpi_cards.cash_balance.value : 0, currentCurrency);
  const runwayEl = document.getElementById("kpi-cash-runway");
  if (isCashZero && (!kpi_cards || kpi_cards.cash_balance.runway_days === 0)) {
    runwayEl.innerText = "Runway: Awaiting Data";
    runwayEl.className = "trend-up";
  } else {
    runwayEl.innerText = `Runway: ${kpi_cards ? kpi_cards.cash_balance.runway_days : 0} days`;
    runwayEl.className = (kpi_cards && kpi_cards.cash_balance.runway_days < 30) ? "trend-down" : "trend-up";
  }

  animateFiguresInContainer(document.getElementById("view-dashboard"));

  // 2. AI Summary
  document.getElementById("dash-ai-summary").innerText = briefing.ai_summary;

  // 3. Health Badge (Removed per user request)
  const healthBadge = document.getElementById("dash-health-badge");
  if (healthBadge) {
    if (briefing.business_health === "Profitable") {
      healthBadge.innerText = "● Business Health: Profitable";
      healthBadge.className = "badge-status badge-healthy";
    } else if (briefing.business_health === "Awaiting Data") {
      healthBadge.innerText = "● Business Health: Awaiting Data";
      healthBadge.className = "badge-status badge-healthy";
    } else {
      healthBadge.innerText = "● Business Health: Runway Attention Required";
      healthBadge.className = "badge-status badge-warning";
    }
  }

  // 4. Attention Required List
  const alertsList = document.getElementById("dash-alerts-list");
  alertsList.innerHTML = "";

  if (inventory.low_stock_count > 0) {
    alertsList.innerHTML += `
      <div class="alert-item">
        <div class="alert-icon" style="display:flex; align-items:center; justify-content:center;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
        </div>
        <div class="alert-content">
          <div class="title">${inventory.low_stock_count} products reached low stock or reorder level</div>
          <div class="desc">Replenishment needed to prevent customer stockouts.</div>
        </div>
      </div>
    `;
  }

  if (inventory.locked_capital > 0) {
    const curr = (company && company.currency) || currentCurrency || "USD";
    alertsList.innerHTML += `
      <div class="alert-item">
        <div class="alert-icon" style="display:flex; align-items:center; justify-content:center;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
        </div>
        <div class="alert-content">
          <div class="title">${curr} ${inventory.locked_capital.toLocaleString()} locked in dead inventory</div>
          <div class="desc">No sales detected for these items in over 60 days.</div>
        </div>
      </div>
    `;
  }

  if (cash.runway_risk) {
    alertsList.innerHTML += `
      <div class="alert-item">
        <div class="alert-icon" style="display:flex; align-items:center; justify-content:center;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
        </div>
        <div class="alert-content">
          <div class="title">Cash runway warning (${cash.runway_days} days remaining)</div>
          <div class="desc">Operating burn exceeds collected customer receivables.</div>
        </div>
      </div>
    `;
  }

  if (!alertsList.innerHTML) {
    alertsList.innerHTML = `
      <div class="alert-item" style="border-left-color: #94a3b8; background: #f8fafc;">
        <div class="alert-icon" style="display:flex; align-items:center; justify-content:center;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
        </div>
        <div class="alert-content">
          <div class="title" style="color: #475569;">No critical issues detected</div>
          <div class="desc">Operations are clear. Upload spreadsheets to activate real-time operational alerts.</div>
        </div>
      </div>
    `;
  }

  // Update badges in sidebar
  document.getElementById("badge-inventory-warn").innerText = inventory.low_stock_count;

  // Render Charts
  renderRevenueTrendChart(trends);
  loadAndRenderExpenseDonut();
}

// -------------------------------------------------------------
// ECHARTS RENDERING (Modern Graphics System)
// -------------------------------------------------------------
function renderRevenueTrendChart(trends) {
  const chartDom = document.getElementById("chart-rev-trend");
  if (!chartDom) return;

  if (revTrendChart) revTrendChart.dispose();
  revTrendChart = echarts.init(chartDom);

  const isEmpty = !trends || trends.length === 0;
  const periods = isEmpty ? ["Month 1", "Month 2", "Month 3", "Month 4"] : trends.map(t => t.period);
  const revenues = isEmpty ? [0, 0, 0, 0] : trends.map(t => t.revenue);
  const profits = isEmpty ? [0, 0, 0, 0] : trends.map(t => t.gross_profit);

  const option = {
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(255, 255, 255, 0.98)",
      borderColor: "#e2e8f0",
      borderWidth: 1,
      padding: [12, 16],
      extraCssText: "box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.03); backdrop-filter: blur(8px); border-radius: 10px;",
      textStyle: { color: "#0f172a", fontFamily: "Inter, system-ui, sans-serif" },
      axisPointer: {
        type: "line",
        lineStyle: {
          color: "rgba(148, 163, 184, 0.5)",
          width: 1.5,
          type: [4, 4],
        },
      },
      formatter: (params) => {
        let period = params[0] ? params[0].name : "";
        if (isEmpty) {
          return `<div style="font-size:0.75rem; font-weight:700; color:#64748b; margin-bottom:4px; text-transform:uppercase; letter-spacing:0.05em;">${period} · Awaiting Data</div><div style="font-size:0.82rem; color:#475569;">Upload sales records to generate historical revenue trends.</div>`;
        }
        let html = `<div style="font-size:0.75rem; font-weight:700; color:#64748b; margin-bottom:8px; text-transform:uppercase; letter-spacing:0.05em;">${period} Financial Performance</div>`;
        params.forEach(item => {
          const color = item.color;
          const val = Number(item.value || 0);
          html += `
            <div style="display:flex; align-items:center; justify-content:space-between; gap:1.5rem; margin-top:5px; font-size:0.85rem;">
              <div style="display:flex; align-items:center; gap:6px;">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${color}; box-shadow:0 0 6px ${color}88;"></span>
                <span style="color:#475569; font-weight:500;">${item.seriesName}</span>
              </div>
              <strong style="color:#0f172a; font-variant-numeric:tabular-nums;">${formatCurrency(val)}</strong>
            </div>
          `;
        });
        return html;
      },
    },
    legend: {
      data: ["Revenue", "Gross Profit"],
      top: 0,
      right: 0,
      icon: "circle",
      itemWidth: 8,
      itemHeight: 8,
      itemGap: 18,
      textStyle: {
        color: "#64748b",
        fontSize: 12,
        fontWeight: 500,
        fontFamily: "Inter, system-ui, sans-serif",
      },
    },
    grid: {
      left: "2%",
      right: "3%",
      bottom: "4%",
      top: "14%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: periods,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#94a3b8",
        fontSize: 11,
        fontWeight: 500,
        margin: 12,
      },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: {
        lineStyle: {
          color: "rgba(226, 232, 240, 0.7)",
          type: "dashed",
          dashOffset: 2,
        },
      },
      axisLabel: {
        color: "#94a3b8",
        fontSize: 11,
        fontWeight: 500,
        formatter: (val) => {
          if (val === 0) return "0";
          if (Math.abs(val) >= 1000000) return `${(val / 1000000).toFixed(0)}M`;
          if (Math.abs(val) >= 1000) return `${(val / 1000).toFixed(0)}K`;
          return `${val}`;
        },
      },
    },
    series: [
      {
        name: "Revenue",
        type: "line",
        smooth: 0.38,
        showSymbol: false,
        symbolSize: 7,
        data: revenues,
        itemStyle: { color: "#2563eb" },
        lineStyle: {
          width: 3,
          color: "#2563eb",
          shadowColor: "rgba(37, 99, 235, 0.35)",
          shadowBlur: 10,
          shadowOffsetY: 4,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(37, 99, 235, 0.22)" },
            { offset: 0.85, color: "rgba(37, 99, 235, 0.02)" },
            { offset: 1, color: "rgba(37, 99, 235, 0.0)" },
          ]),
        },
        emphasis: {
          focus: "series",
          itemStyle: {
            borderWidth: 3,
            borderColor: "#ffffff",
            shadowColor: "rgba(37, 99, 235, 0.5)",
            shadowBlur: 8,
          },
        },
      },
      {
        name: "Gross Profit",
        type: "line",
        smooth: 0.38,
        showSymbol: false,
        symbolSize: 7,
        data: profits,
        itemStyle: { color: "#10b981" },
        lineStyle: {
          width: 2.8,
          color: "#10b981",
          shadowColor: "rgba(16, 185, 129, 0.3)",
          shadowBlur: 10,
          shadowOffsetY: 4,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(16, 185, 129, 0.16)" },
            { offset: 0.85, color: "rgba(16, 185, 129, 0.01)" },
            { offset: 1, color: "rgba(16, 185, 129, 0.0)" },
          ]),
        },
        emphasis: {
          focus: "series",
          itemStyle: {
            borderWidth: 3,
            borderColor: "#ffffff",
            shadowColor: "rgba(16, 185, 129, 0.5)",
            shadowBlur: 8,
          },
        },
      },
    ],
  };

  revTrendChart.setOption(option);
}

async function loadAndRenderExpenseDonut() {
  const chartDom = document.getElementById("chart-expense-donut");
  if (!chartDom) return;

  try {
    const res = await fetch(`${API_BASE}/api/expenses?company_id=${currentCompanyId}`);
    const data = await res.json();
    const categories = data.summary.categories || [];
    const totalExp = data.summary.total_expenses || 0;

    if (expenseDonutChart) expenseDonutChart.dispose();
    expenseDonutChart = echarts.init(chartDom);

    const hasData = categories && categories.length > 0 && totalExp > 0;
    const chartData = hasData ? categories.map(c => ({
      name: c.category,
      value: c.total_amount,
    })) : [
      { name: "Awaiting Expenses", value: 1, itemStyle: { color: "#e2e8f0" } }
    ];

    const modernColors = hasData ? [
      "#3b82f6", // Royal Blue
      "#10b981", // Emerald
      "#8b5cf6", // Violet
      "#f59e0b", // Warm Amber
      "#06b6d4", // Cyan
      "#ec4899", // Magenta Pink
      "#f97316", // Coral Orange
      "#6366f1", // Indigo
      "#14b8a6", // Teal
      "#64748b", // Slate
    ] : ["#e2e8f0"];

    const option = {
      baseOption: {
        color: modernColors,
        title: {
          text: formatCurrency(totalExp),
          subtext: hasData ? "TOTAL OPEX" : "NO EXPENSES YET",
          left: "28%",
          top: "42%",
          textAlign: "center",
          textStyle: {
            fontSize: 14,
            fontWeight: 700,
            color: "#0f172a",
            fontFamily: "Inter, system-ui, sans-serif",
          },
          subtextStyle: {
            fontSize: 9,
            color: "#64748b",
            fontWeight: 700,
            letterSpacing: "0.08em",
          },
        },
        tooltip: {
          trigger: "item",
          backgroundColor: "rgba(255, 255, 255, 0.98)",
          borderColor: "#e2e8f0",
          borderWidth: 1,
          padding: [10, 14],
          extraCssText: "box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.03); backdrop-filter: blur(8px); border-radius: 10px;",
          textStyle: { color: "#0f172a", fontFamily: "Inter, system-ui, sans-serif" },
          formatter: (params) => {
            if (!hasData) {
              return '<div style="font-size:0.75rem; font-weight:700; color:#64748b; margin-bottom:4px; text-transform:uppercase; letter-spacing:0.04em;">Operating Expenses</div><div style="font-size:0.82rem; color:#475569;">No expenses recorded yet.</div>';
            }
            const val = Number(params.value || 0);
            return `
              <div style="font-size:0.75rem; font-weight:700; color:#64748b; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.04em;">Expense Cost Center</div>
              <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${params.color};"></span>
                <strong style="color:#0f172a; font-size:0.92rem;">${params.name}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; gap:1.2rem; font-size:0.85rem; color:#475569; margin-top:4px;">
                <span>Amount:</span>
                <strong style="color:#0f172a; font-variant-numeric:tabular-nums;">${formatCurrency(val)}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; gap:1.2rem; font-size:0.85rem; color:#475569;">
                <span>Share of OPEX:</span>
                <span class="badge-status badge-healthy" style="padding:1px 6px; font-size:0.75rem;">${params.percent}%</span>
              </div>
            `;
          },
        },
        legend: {
          show: hasData,
          type: "scroll",
          orient: "vertical",
          left: "52%",
          right: 12,
          top: "middle",
          icon: "circle",
          itemWidth: 10,
          itemHeight: 10,
          itemGap: 12,
          pageIconSize: 11,
          pageTextStyle: { fontSize: 10, color: "#94a3b8" },
          textStyle: {
            fontSize: 11.5,
            color: "#475569",
            fontFamily: "Inter, system-ui, sans-serif",
            rich: {
              name: {
                width: 140,
                overflow: "truncate",
                fontSize: 11.5,
                fontWeight: 500,
                color: "#334155",
              },
              pct: {
                width: 50,
                align: "right",
                fontSize: 11.5,
                fontWeight: 600,
                color: "#64748b",
              },
            },
          },
          formatter: (name) => {
            const cat = categories.find(c => c.category === name);
            const pct = cat && cat.percentage !== undefined ? `${cat.percentage}%` : "";
            return `{name|${name}} {pct|${pct}}`;
          },
        },
        series: [
          {
            name: "Expenses",
            type: "pie",
            radius: ["46%", "70%"],
            center: ["28%", "50%"],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 7,
              borderColor: "#ffffff",
              borderWidth: 3,
              shadowColor: "rgba(0, 0, 0, 0.04)",
              shadowBlur: 6,
            },
            emphasis: {
              scale: true,
              scaleSize: 6,
              itemStyle: {
                shadowBlur: 14,
                shadowOffsetX: 0,
                shadowColor: "rgba(0, 0, 0, 0.16)",
              },
            },
            label: { show: false },
            labelLine: { show: false },
            data: chartData,
          },
        ],
      },
      media: [
        {
          query: {
            maxWidth: 560,
          },
          option: {
            title: {
              left: "50%",
              top: "32%",
            },
            legend: {
              orient: "horizontal",
              left: "center",
              right: "auto",
              top: "auto",
              bottom: 8,
              itemGap: 10,
              textStyle: {
                fontSize: 11,
                rich: {
                  name: {
                    width: 95,
                    fontSize: 11,
                  },
                  pct: {
                    width: 40,
                    fontSize: 11,
                  },
                },
              },
            },
            series: [
              {
                center: ["50%", "35%"],
                radius: ["36%", "56%"],
              },
            ],
          },
        },
      ],
    };

    expenseDonutChart.setOption(option);
  } catch (err) {
    console.error("Failed to render expense donut:", err);
  }
}

// -------------------------------------------------------------
// SCREEN 03: ANALYTICS (P&L)
// -------------------------------------------------------------
async function loadAnalyticsData() {
  try {
    const res = await fetch(`${API_BASE}/api/analytics?company_id=${currentCompanyId}`);
    const data = await res.json();
    const pnl = data.pnl;
    const curr = currentCurrency || "TZS";

    const tbody = document.getElementById("pnl-table-body");
    tbody.innerHTML = `
      <tr>
        <td><strong>Gross Sales Revenue</strong></td>
        <td>${curr} ${pnl.revenue.toLocaleString()}</td>
        <td>100.0%</td>
        <td><span class="badge-status badge-healthy">Top-Line</span></td>
      </tr>
      <tr>
        <td>Cost of Goods Sold (COGS)</td>
        <td>${curr} ${pnl.cogs.toLocaleString()}</td>
        <td>${pnl.revenue > 0 ? ((pnl.cogs / pnl.revenue) * 100).toFixed(1) : 0}%</td>
        <td>Direct Costs</td>
      </tr>
      <tr style="background:#f8fafc; font-weight:600;">
        <td><strong>Gross Profit</strong></td>
        <td><strong>${curr} ${pnl.gross_profit.toLocaleString()}</strong></td>
        <td><strong>${pnl.gross_margin_pct}%</strong></td>
        <td><span class="badge-status badge-healthy">Margin Bridge</span></td>
      </tr>
      <tr>
        <td>Operating Expenses (OPEX)</td>
        <td>${curr} ${pnl.operating_expenses.toLocaleString()}</td>
        <td>${pnl.revenue > 0 ? ((pnl.operating_expenses / pnl.revenue) * 100).toFixed(1) : 0}%</td>
        <td>Overhead</td>
      </tr>
      <tr style="background:#f1f5f9; font-weight:700;">
        <td><strong>Net Profit (EBITDA)</strong></td>
        <td style="color:${pnl.net_profit >= 0 ? '#10b981' : '#ef4444'};">
          <strong>${curr} ${pnl.net_profit.toLocaleString()}</strong>
        </td>
        <td><strong>${pnl.net_margin_pct}%</strong></td>
        <td><span class="badge-status ${pnl.net_profit >= 0 ? 'badge-paid' : 'badge-danger'}">${pnl.net_profit >= 0 ? 'Profitable' : 'Loss'}</span></td>
      </tr>
    `;

    renderPnlBridgeChart(pnl);
  } catch (err) {
    console.error("Failed to load analytics data:", err);
  }
}

function renderPnlBridgeChart(pnl) {
  const chartDom = document.getElementById("chart-pnl-bridge");
  if (!chartDom) return;

  if (pnlBridgeChart) pnlBridgeChart.dispose();
  pnlBridgeChart = echarts.init(chartDom);

  const categories = ["Gross Sales", "COGS", "Gross Profit", "OPEX", "Net Profit"];
  const values = [
    pnl.revenue || 0,
    -(pnl.cogs || 0),
    pnl.gross_profit || 0,
    -(pnl.operating_expenses || 0),
    pnl.net_profit || 0,
  ];

  const colors = values.map((v, i) => {
    if (i === 0) return "#2563eb";
    if (i === 1) return "#f97316";
    if (i === 2) return "#10b981";
    if (i === 3) return "#f59e0b";
    return v >= 0 ? "#10b981" : "#ef4444";
  });

  const option = {
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(255, 255, 255, 0.98)",
      borderColor: "#e2e8f0",
      borderWidth: 1,
      padding: [10, 14],
      extraCssText: "box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.03); backdrop-filter: blur(8px); border-radius: 10px;",
      textStyle: { color: "#0f172a", fontFamily: "Inter, system-ui, sans-serif" },
      axisPointer: { type: "shadow", shadowStyle: { color: "rgba(241, 245, 249, 0.6)" } },
      formatter: (params) => {
        const item = params[0];
        const val = Number(item.value || 0);
        return `
          <div style="font-size:0.75rem; font-weight:700; color:#64748b; margin-bottom:4px; text-transform:uppercase; letter-spacing:0.04em;">Financial Line Item</div>
          <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
            <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${item.color};"></span>
            <strong style="color:#0f172a; font-size:0.92rem;">${item.name}</strong>
          </div>
          <div style="display:flex; justify-content:space-between; gap:1.2rem; font-size:0.85rem;">
            <span style="color:#64748b;">Amount:</span>
            <strong style="color:#0f172a; font-variant-numeric:tabular-nums;">${formatCurrency(val)}</strong>
          </div>
        `;
      },
    },
    grid: { left: "2%", right: "3%", bottom: "8%", top: "12%", containLabel: true },
    xAxis: {
      type: "category",
      data: categories,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#64748b",
        fontSize: 11,
        fontWeight: 600,
        margin: 12,
      },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: {
        lineStyle: {
          color: "rgba(226, 232, 240, 0.7)",
          type: "dashed",
          dashOffset: 2,
        },
      },
      axisLabel: {
        color: "#94a3b8",
        fontSize: 11,
        fontWeight: 500,
        formatter: (val) => `${(val / 1000000).toFixed(0)}M`,
      },
    },
    series: [
      {
        name: "Financial Bridge",
        type: "bar",
        barWidth: "38%",
        data: values.map((val, idx) => ({
          value: val,
          itemStyle: {
            color: colors[idx],
            borderRadius: val >= 0 ? [6, 6, 0, 0] : [0, 0, 6, 6],
            shadowColor: `${colors[idx]}44`,
            shadowBlur: 8,
            shadowOffsetY: val >= 0 ? 3 : -3,
          },
        })),
        emphasis: {
          itemStyle: {
            shadowBlur: 14,
            shadowColor: "rgba(0,0,0,0.15)",
          },
        },
      },
    ],
  };

  pnlBridgeChart.setOption(option);
}

// -------------------------------------------------------------
// SCREEN 04: SALES
// -------------------------------------------------------------
async function loadSalesData() {
  try {
    const res = await fetch(`${API_BASE}/api/sales?company_id=${currentCompanyId}&limit=50`);
    const data = await res.json();
    const sales = data.sales || [];
    const curr = currentCurrency || "USD";

    const tbody = document.getElementById("sales-table-body");
    if (sales.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#64748b; padding:2rem;">No sales records found. Upload an Excel or Google Sheets file to view sales transactions.</td></tr>`;
      return;
    }
    tbody.innerHTML = sales.map(s => `
      <tr>
        <td><strong>${s.invoice_number}</strong></td>
        <td>${s.customer_name || 'Walk-in'}</td>
        <td>${s.sale_date}</td>
        <td>${curr} ${s.total.toLocaleString()}</td>
        <td>${curr} ${s.cost_of_goods.toLocaleString()}</td>
        <td style="color:${s.profit >= 0 ? '#10b981' : '#ef4444'}; font-weight:600;">${curr} ${s.profit.toLocaleString()}</td>
        <td><span class="badge-status ${s.payment_status === 'Paid' ? 'badge-paid' : 'badge-warning'}">${s.payment_status}</span></td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Failed to load sales data:", err);
  }
}

// -------------------------------------------------------------
// SCREEN 05: CUSTOMERS
// -------------------------------------------------------------
async function loadCustomersData() {
  try {
    const res = await fetch(`${API_BASE}/api/customers?company_id=${currentCompanyId}`);
    const data = await res.json();
    const customers = data.top_customers || [];
    const curr = currentCurrency || "USD";

    const tbody = document.getElementById("customers-table-body");
    if (customers.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#64748b; padding:2rem;">No customer records found. Upload an Excel or Google Sheets file to analyze customer unit economics.</td></tr>`;
      return;
    }
    tbody.innerHTML = customers.map(c => `
      <tr>
        <td><strong>${c.customer_name}</strong></td>
        <td>${c.customer_type || 'Retail'}</td>
        <td>${c.total_orders}</td>
        <td>${curr} ${c.total_revenue.toLocaleString()}</td>
        <td>${curr} ${c.net_profit.toLocaleString()}</td>
        <td style="font-weight:600; color:${c.margin_pct >= 25 ? '#10b981' : '#f59e0b'};">${c.margin_pct}%</td>
        <td>
          <span class="badge-status ${c.margin_pct >= 25 ? 'badge-healthy' : 'badge-low'}">
            ${c.margin_pct >= 25 ? '⭐ Whale' : 'Margin Watch'}
          </span>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Failed to load customers data:", err);
  }
}

// -------------------------------------------------------------
// SCREEN 06: INVENTORY
// -------------------------------------------------------------
async function loadInventoryData() {
  try {
    const res = await fetch(`${API_BASE}/api/inventory?company_id=${currentCompanyId}`);
    const data = await res.json();
    const summary = data.summary || {};
    const products = data.products || [];
    const curr = currentCurrency || "USD";

    document.getElementById("inv-total-val").innerText = `${curr} ${(summary.total_inventory_value || 0).toLocaleString()}`;
    document.getElementById("inv-low-count").innerText = summary.low_stock_count || 0;
    document.getElementById("inv-dead-val").innerText = `${curr} ${(summary.locked_capital_slow_moving || 0).toLocaleString()}`;

    animateFiguresInContainer(document.getElementById("view-inventory"));

    const tbody = document.getElementById("inventory-table-body");
    if (products.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:#64748b; padding:2rem;">No inventory products found. Upload an inventory spreadsheet to track stock levels.</td></tr>`;
      return;
    }
    tbody.innerHTML = products.map(p => {
      const isLow = p.stock_on_hand <= p.reorder_level;
      const isOut = p.stock_on_hand <= 0;
      let statusClass = "badge-healthy";
      let statusLabel = "Healthy";
      if (isOut) {
        statusClass = "badge-danger";
        statusLabel = "Out of Stock";
      } else if (isLow) {
        statusClass = "badge-warning";
        statusLabel = "Low Stock";
      }

      return `
        <tr>
          <td><strong>${p.sku}</strong></td>
          <td>${p.name}</td>
          <td style="font-weight:600;">${p.stock_on_hand}</td>
          <td>${p.reorder_level}</td>
          <td>${curr} ${p.cost_price.toLocaleString()}</td>
          <td>${curr} ${p.selling_price.toLocaleString()}</td>
          <td>${curr} ${p.stock_value.toLocaleString()}</td>
          <td><span class="badge-status ${statusClass}">${statusLabel}</span></td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Failed to load inventory data:", err);
  }
}

// -------------------------------------------------------------
// SCREEN 07: EXPENSES
// -------------------------------------------------------------
async function loadExpensesData() {
  try {
    const res = await fetch(`${API_BASE}/api/expenses?company_id=${currentCompanyId}`);
    const data = await res.json();
    const summary = data.summary || {};
    const categories = summary.categories || [];
    const expenses = data.expenses || [];
    const curr = currentCurrency || "TZS";

    // 1. KPI Summary Cards
    const totalExpVal = document.getElementById("exp-total-val");
    if (totalExpVal) totalExpVal.innerText = formatCurrency(summary.total_expenses);

    const expCatsCount = document.getElementById("exp-cats-count");
    if (expCatsCount) expCatsCount.innerText = `${summary.category_count || categories.length} Consolidated`;

    const topCat = categories.length > 0 ? categories[0] : null;
    const expTopCat = document.getElementById("exp-top-category");
    if (expTopCat) expTopCat.innerText = topCat ? topCat.category : "-";

    const expTopShare = document.getElementById("exp-top-share");
    if (expTopShare) {
      expTopShare.innerText = topCat
        ? `${topCat.percentage}% of OPEX (${curr} ${Number(topCat.total_amount).toLocaleString()})`
        : "No categories recorded";
    }

    const expGrowthSub = document.getElementById("exp-growth-sub");
    if (expGrowthSub && summary.mom_growth_pct !== undefined) {
      const g = summary.mom_growth_pct;
      expGrowthSub.innerText = g !== 0 ? `MoM Expense Trend: ${g > 0 ? "+" : ""}${g}%` : "All cost centers consolidated";
    }

    animateFiguresInContainer(document.getElementById("view-expenses"));

    // 2. Auto-Summed Categories Breakdown Table
    const catTbody = document.getElementById("expenses-categories-tbody");
    if (catTbody) {
      if (categories.length === 0) {
        catTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:1.5rem; color:#94a3b8;">No expense categories recorded yet. Upload an expense spreadsheet to analyze cost centers.</td></tr>`;
      } else {
        catTbody.innerHTML = categories.map(c => `
          <tr>
            <td><strong>${c.category}</strong></td>
            <td><span class="badge-status badge-healthy" style="background:#f1f5f9; color:#475569; font-weight:600;">${c.category_type}</span></td>
            <td><span class="badge-count">Σ ${c.transaction_count || 1} entries auto-summed</span></td>
            <td style="font-weight:700;">${curr} ${Number(c.total_amount).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
            <td>
              <div style="display:flex; align-items:center;">
                <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${Math.min(100, c.percentage)}%;"></div></div>
                <span style="font-weight:600; font-size:0.8rem; color:#475569;">${c.percentage}%</span>
              </div>
            </td>
          </tr>
        `).join("");
      }
    }

    // 3. Raw Detailed Ledger Table
    const tbody = document.getElementById("expenses-table-body");
    if (tbody) {
      if (expenses.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:1.5rem; color:#94a3b8;">No individual expense entries found.</td></tr>`;
      } else {
        tbody.innerHTML = expenses.map(e => `
          <tr>
            <td>${e.expense_date}</td>
            <td><strong>${e.category_name}</strong></td>
            <td>${e.description || "-"}</td>
            <td style="font-weight:600;">${curr} ${Number(e.amount).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
            <td>${e.payment_method || "BANK"}</td>
            <td><span class="badge-status badge-paid">${e.status || "PAID"}</span></td>
          </tr>
        `).join("");
      }
    }
  } catch (err) {
    console.error("Failed to load expenses data:", err);
  }
}

// -------------------------------------------------------------
// SCREEN 08: CASH FLOW
// -------------------------------------------------------------
async function loadCashFlowData() {
  try {
    const res = await fetch(`${API_BASE}/api/cashflow?company_id=${currentCompanyId}`);
    const data = await res.json();
    const cash = data.cash_summary;
    const points = data.forecast_points || [];

    document.getElementById("cash-current-val").innerText = formatCurrency(cash.current_cash_balance);
    document.getElementById("cash-ar-val").innerText = formatCurrency(cash.accounts_receivable);
    document.getElementById("cash-unpaid-invoices").innerText = `${cash.unpaid_invoices_count} unpaid customer invoices`;
    document.getElementById("cash-burn-val").innerText = formatCurrency(cash.monthly_burn_rate);
    document.getElementById("cash-runway-countdown").innerText = cash.monthly_burn_rate > 0 ? `Runway: ${cash.runway_days} days` : "Runway: Awaiting Data";

    animateFiguresInContainer(document.getElementById("view-cashflow"));

    // Render Cash Projection Chart
    const chartDom = document.getElementById("chart-cash-projection");
    if (!chartDom) return;

    if (cashProjectionChart) cashProjectionChart.dispose();
    cashProjectionChart = echarts.init(chartDom);

    const xDays = points.map(p => p.day);
    const yVals = points.map(p => p.balance);

    const option = {
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(255, 255, 255, 0.98)",
        borderColor: "#e2e8f0",
        borderWidth: 1,
        padding: [12, 16],
        extraCssText: "box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.03); backdrop-filter: blur(8px); border-radius: 10px;",
        textStyle: { color: "#0f172a", fontFamily: "Inter, system-ui, sans-serif" },
        axisPointer: {
          type: "line",
          lineStyle: {
            color: "rgba(148, 163, 184, 0.5)",
            width: 1.5,
            type: [4, 4],
          },
        },
        formatter: (params) => {
          const p = params[0];
          const val = Number(p ? p.value : 0);
          const isPositive = val >= 0;
          return `
            <div style="font-size:0.75rem; font-weight:700; color:#64748b; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.05em;">Day ${p ? p.name : ""} · Cash Trajectory</div>
            <div style="display:flex; align-items:center; justify-content:space-between; gap:1.5rem; margin-top:4px; font-size:0.85rem;">
              <span style="color:#64748b;">Projected Balance:</span>
              <strong style="color:${isPositive ? "#0284c7" : "#ef4444"}; font-variant-numeric:tabular-nums;">${formatCurrency(val)}</strong>
            </div>
            <div style="display:flex; align-items:center; justify-content:space-between; gap:1.5rem; margin-top:2px; font-size:0.78rem; color:#94a3b8;">
              <span>Status:</span>
              <span style="color:${isPositive ? "#10b981" : "#ef4444"}; font-weight:600;">${isPositive ? "Positive Liquidity" : "Deficit / Runway Burn"}</span>
            </div>
          `;
        },
      },
      grid: { left: "2%", right: "4%", bottom: "6%", top: "10%", containLabel: true },
      xAxis: {
        type: "category",
        data: xDays,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: "#94a3b8",
          fontSize: 11,
          fontWeight: 500,
          formatter: (v) => `Day ${v}`,
        },
      },
      yAxis: {
        type: "value",
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: {
          lineStyle: {
            color: "rgba(226, 232, 240, 0.7)",
            type: "dashed",
            dashOffset: 2,
          },
        },
        axisLabel: {
          color: "#94a3b8",
          fontSize: 11,
          fontWeight: 500,
          formatter: (v) => `${(v / 1000000).toFixed(0)}M`,
        },
      },
      series: [
        {
          name: "Projected Cash",
          type: "line",
          data: yVals,
          smooth: 0.36,
          showSymbol: false,
          symbolSize: 7,
          itemStyle: { color: "#0284c7" },
          lineStyle: {
            width: 3,
            color: "#0284c7",
            shadowColor: "rgba(2, 132, 199, 0.35)",
            shadowBlur: 10,
            shadowOffsetY: 4,
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(2, 132, 199, 0.25)" },
              { offset: 0.85, color: "rgba(2, 132, 199, 0.02)" },
              { offset: 1, color: "rgba(2, 132, 199, 0.0)" },
            ]),
          },
          markLine: {
            symbol: "none",
            data: [
              {
                yAxis: 0,
                lineStyle: { color: "#ef4444", width: 1.5, type: [5, 4] },
                label: {
                  show: true,
                  position: "insideEndTop",
                  formatter: `Zero Balance Baseline (${formatCurrency(0)})`,
                  color: "#ef4444",
                  fontSize: 10.5,
                  fontWeight: 600,
                },
              },
            ],
          },
          emphasis: {
            focus: "series",
            itemStyle: {
              borderWidth: 3,
              borderColor: "#ffffff",
              shadowColor: "rgba(2, 132, 199, 0.5)",
              shadowBlur: 8,
            },
          },
        },
      ],
    };

    cashProjectionChart.setOption(option);
  } catch (err) {
    console.error("Failed to load cash flow data:", err);
  }
}

// -------------------------------------------------------------
// SCREEN 10: AI ANALYST
// -------------------------------------------------------------
function setupAISearch() {
  const btn = document.getElementById("btn-submit-ai");
  const input = document.getElementById("ai-query-input");
  if (btn && input) {
    btn.addEventListener("click", () => {
      const q = input.value.trim();
      if (q) askAI(q);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const q = input.value.trim();
        if (q) askAI(q);
      }
    });
  }
}

let currentAiThinkingInterval = null;

function tokenizeHtmlForStreaming(html) {
  const tokens = [];
  let i = 0;
  while (i < html.length) {
    if (html[i] === '<') {
      const closeIdx = html.indexOf('>', i);
      if (closeIdx !== -1) {
        tokens.push({ type: 'tag', value: html.slice(i, closeIdx + 1) });
        i = closeIdx + 1;
        continue;
      }
    }
    let nextSpace = html.indexOf(' ', i);
    let nextTag = html.indexOf('<', i);
    let endIdx;
    if (nextSpace !== -1 && nextTag !== -1) {
      endIdx = Math.min(nextSpace + 1, nextTag);
    } else if (nextSpace !== -1) {
      endIdx = nextSpace + 1;
    } else if (nextTag !== -1) {
      endIdx = nextTag;
    } else {
      endIdx = html.length;
    }
    tokens.push({ type: 'text', value: html.slice(i, endIdx) });
    i = endIdx;
  }
  return tokens;
}

async function streamHtmlWords(html, targetEl) {
  if (!targetEl) return;
  targetEl.innerHTML = "";
  const tokens = tokenizeHtmlForStreaming(html);
  let accumulated = "";

  for (const token of tokens) {
    if (token.type === 'tag') {
      accumulated += token.value;
      targetEl.innerHTML = accumulated;
    } else {
      accumulated += token.value;
      targetEl.innerHTML = accumulated;
      // Natural fluid typewriter delay (18ms per word)
      await new Promise(r => setTimeout(r, 18));
    }
  }
}

function toggleGeminiThoughts(header) {
  const body = header.nextElementSibling;
  const arrow = header.querySelector("#gemini-accordion-arrow");
  if (!body) return;
  if (body.classList.contains("open")) {
    body.classList.remove("open");
    if (arrow) arrow.innerText = "▾";
  } else {
    body.classList.add("open");
    if (arrow) arrow.innerText = "▴";
  }
}

function copyGeminiAnswer() {
  const text = window._latestGeminiAnswerText || "";
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    const label = document.getElementById("gemini-copy-label");
    if (label) {
      const orig = label.innerText;
      label.innerText = "Copied!";
      setTimeout(() => { label.innerText = orig; }, 2000);
    }
  }).catch(() => {
    alert("Copied to clipboard!");
  });
}

function rateGeminiFeedback(btn, type) {
  const siblings = btn.parentElement.querySelectorAll(".gemini-tool-btn");
  siblings.forEach(s => s.classList.remove("active"));
  btn.classList.add("active");
}

async function askAI(question) {
  const box = document.getElementById("ai-answer-box");
  const input = document.getElementById("ai-query-input");

  if (input) input.value = question;
  if (!box) return;

  box.style.display = "block";
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });

  if (currentAiThinkingInterval) {
    clearInterval(currentAiThinkingInterval);
    currentAiThinkingInterval = null;
  }

  // 1. Render User Message Bubble + Gemini Thinking State
  box.innerHTML = `
    <div class="gemini-user-msg">
      <div class="gemini-user-avatar">${(currentUserName || "U").charAt(0).toUpperCase()}</div>
      <div class="gemini-user-text">${question}</div>
    </div>

    <div class="gemini-response-card" id="gemini-card-target">
      <div class="gemini-header-row">
        <div class="gemini-model-badge">
          <span class="gemini-sparkle-icon"></span>
          <span>Gemini 1.5 Flash</span>
        </div>
        <span class="gemini-status-tag" id="gemini-status-pill">Thinking...</span>
      </div>

      <!-- Thinking State Animation -->
      <div class="gemini-thinking-wrap" id="gemini-thinking-wrap">
        <div class="gemini-thinking-status">
          <span class="gemini-sparkle-icon" style="width:16px; height:16px;"></span>
          <span id="gemini-dynamic-thinking-text">Thinking...</span>
        </div>
        <div class="gemini-thinking-bars">
          <div class="gemini-shimmer-bar w-100"></div>
          <div class="gemini-shimmer-bar w-85"></div>
          <div class="gemini-shimmer-bar w-65"></div>
        </div>
      </div>

      <!-- Stream Content Area (Initially Hidden) -->
      <div id="gemini-stream-area" style="display:none;">
        <div id="gemini-accordion-container"></div>

        <div style="position:relative;">
          <div id="gemini-stream-text" class="gemini-text-stream"></div>
          <span class="gemini-cursor" id="gemini-cursor"></span>
        </div>

        <div id="gemini-recommendation-block" style="display:none; margin-top:1.15rem; padding:0.95rem 1.15rem; background:linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%); border:1px solid #bfdbfe; border-left:4px solid #3b82f6; border-radius:10px;">
          <div style="font-size:0.75rem; font-weight:700; color:#1d4ed8; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
            Strategic Tactical Action
          </div>
          <div id="gemini-recommendation-text" style="font-size:0.92rem; color:#1e293b; line-height:1.5;"></div>
        </div>

        <div class="gemini-action-bar" id="gemini-action-bar" style="display:none;">
          <div class="gemini-actions-left">
            <button class="gemini-tool-btn" id="btn-gemini-copy" onclick="copyGeminiAnswer()" title="Copy answer">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
              <span id="gemini-copy-label">Copy</span>
            </button>
            <button class="gemini-tool-btn" onclick="rateGeminiFeedback(this, 'up')" title="Good response">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>
            </button>
            <button class="gemini-tool-btn" onclick="rateGeminiFeedback(this, 'down')" title="Poor response">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path></svg>
            </button>
            <button class="gemini-tool-btn" onclick="askAI('${question.replace(/'/g, "\\'")}')" title="Regenerate analysis">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
              <span>Regenerate</span>
            </button>
          </div>
          <div class="gemini-grounding-attribution">
            <span class="gemini-sparkle-icon" style="width:13px; height:13px;"></span>
            <span>Grounded in Verified Financial Ledger</span>
          </div>
        </div>
      </div>
    </div>
  `;

  // Dynamic Thinking Messages Cycle
  const thinkingEl = document.getElementById("gemini-dynamic-thinking-text");
  const thinkingMessages = [
    "Thinking...",
    "Scanning verified business ledger & transactions...",
    "Auditing revenue margins and operating burn rates...",
    "Cross-referencing SKU velocities and cash runway...",
    "Synthesizing executive root causes and tactical next steps..."
  ];
  let msgIdx = 0;
  currentAiThinkingInterval = setInterval(() => {
    msgIdx = (msgIdx + 1) % thinkingMessages.length;
    if (thinkingEl) thinkingEl.innerText = thinkingMessages[msgIdx];
  }, 700);

  const savedGeminiKey = localStorage.getItem("business_pilot_gemini_key") || "";

  try {
    const res = await fetch(`${API_BASE}/api/ai/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: question,
        company_id: currentCompanyId,
        gemini_api_key: savedGeminiKey
      }),
    });
    const data = await res.json();
    clearInterval(currentAiThinkingInterval);

    if (data.success && data.answer) {
      const a = data.answer;

      // 1. Hide thinking animation, show stream area
      const thinkingWrap = document.getElementById("gemini-thinking-wrap");
      if (thinkingWrap) thinkingWrap.style.display = "none";

      const streamArea = document.getElementById("gemini-stream-area");
      if (streamArea) streamArea.style.display = "block";

      const statusPill = document.getElementById("gemini-status-pill");
      if (statusPill) {
        statusPill.innerText = a.provider ? a.provider.split("(")[0].trim() : "Grounded Answer";
        statusPill.style.background = "#ecfdf5";
        statusPill.style.color = "#047857";
      }

      // 2. Render Thought Process Accordion
      const accordionContainer = document.getElementById("gemini-accordion-container");
      const toolsHtml = a.tool_calls.map(t => `<code style="background:#e2e8f0; padding:2px 7px; border-radius:4px; font-size:11px; margin-right:4px;">${t}</code>`).join("");
      const citationsHtml = a.citations.map(c => `<li>${c.metric}: <strong>${c.value}</strong></li>`).join("");

      if (accordionContainer) {
        accordionContainer.innerHTML = `
          <div class="gemini-thoughts-accordion">
            <div class="gemini-thoughts-header" onclick="toggleGeminiThoughts(this)">
              <div style="display:flex; align-items:center; gap:6px;">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                <span>Thought process & ledger verification (${a.tool_calls.length} tools invoked, ${a.citations.length} metrics checked)</span>
              </div>
              <span id="gemini-accordion-arrow">▾</span>
            </div>
            <div class="gemini-thoughts-body" id="gemini-accordion-body">
              <div style="margin-bottom:0.5rem;">
                <div style="font-size:11px; font-weight:700; color:#475569; text-transform:uppercase; margin-bottom:3px;">Ledger Tools Executed:</div>
                <div>${toolsHtml}</div>
              </div>
              <div>
                <div style="font-size:11px; font-weight:700; color:#475569; text-transform:uppercase; margin-bottom:3px;">Verified Financial Citations:</div>
                <ul style="padding-left:18px; margin:0;">${citationsHtml}</ul>
              </div>
            </div>
          </div>
        `;
      }

      // 3. Word-by-Word Streaming into Target Element
      const streamTarget = document.getElementById("gemini-stream-text");
      const cursor = document.getElementById("gemini-cursor");

      await streamHtmlWords(a.explanation, streamTarget);

      // Fade out blinking cursor
      if (cursor) {
        cursor.style.transition = "opacity 0.4s ease";
        cursor.style.opacity = "0";
        setTimeout(() => cursor.remove(), 400);
      }

      // 4. Reveal Tactical Recommendation block
      const recBlock = document.getElementById("gemini-recommendation-block");
      const recText = document.getElementById("gemini-recommendation-text");
      if (recBlock && recText && a.action_recommendation) {
        recText.innerText = a.action_recommendation;
        recBlock.style.display = "block";
      }

      // 5. Reveal Action Bar
      const actionBar = document.getElementById("gemini-action-bar");
      if (actionBar) {
        actionBar.style.display = "flex";
      }

      // Cache raw text for copying
      window._latestGeminiAnswerText = streamTarget ? streamTarget.innerText : "";
      if (a.action_recommendation) {
        window._latestGeminiAnswerText += `\n\nStrategic Action: ${a.action_recommendation}`;
      }

    } else {
      const thinkingWrap = document.getElementById("gemini-thinking-wrap");
      if (thinkingWrap) {
        thinkingWrap.innerHTML = `<div style="color:#dc2626; font-size:0.9rem;">Analysis error: ${data.error || 'Failed to analyze question'}</div>`;
      }
    }
  } catch (err) {
    clearInterval(currentAiThinkingInterval);
    const thinkingWrap = document.getElementById("gemini-thinking-wrap");
    if (thinkingWrap) {
      thinkingWrap.innerHTML = `<div style="color:#dc2626; font-size:0.9rem;">Connection error: ${err.message}</div>`;
    }
  }
}

// -------------------------------------------------------------
// SCREEN 09: FORECASTS
// -------------------------------------------------------------
let forecastChartInstance = null;

async function loadForecastsData() {
  try {
    const res = await fetch(`${API_BASE}/api/forecasts?company_id=${currentCompanyId}`);
    const data = await res.json();
    const revFc = data.revenue_forecast;
    const stockFc = data.stockout_forecast || [];

    document.getElementById("forecast-conf-badge").innerText = `Model Confidence: ${Math.round(revFc.overall_confidence * 100)}%`;
    animateFiguresInContainer(document.getElementById("view-forecasts"));

    // Render Drivers
    const driversList = document.getElementById("forecast-drivers-list");
    driversList.innerHTML = revFc.drivers.map(d => {
      const iconSvg = d.type === 'POSITIVE'
        ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>`
        : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"></polyline><polyline points="17 18 23 18 23 12"></polyline></svg>`;
      return `
        <div class="alert-item">
          <div class="alert-icon" style="display:flex; align-items:center; justify-content:center;">${iconSvg}</div>
          <div class="alert-content">
            <div class="title">${d.title}</div>
            <div class="desc">${d.desc}</div>
          </div>
        </div>
      `;
    }).join("");

    // Render Stockout table
    const tbody = document.getElementById("stockout-table-body");
    tbody.innerHTML = stockFc.map(s => `
      <tr>
        <td><strong>${s.sku}</strong></td>
        <td>${s.name}</td>
        <td style="font-weight:600;">${s.current_stock}</td>
        <td>${s.daily_burn_rate} units/day</td>
        <td style="color:${s.urgency === 'CRITICAL' ? '#ef4444' : '#f59e0b'}; font-weight:700;">
          ${s.days_until_stockout} days
        </td>
        <td><strong>${s.recommended_reorder_qty} units</strong></td>
        <td><span class="badge-status ${s.urgency === 'CRITICAL' ? 'badge-danger' : 'badge-warning'}">${s.urgency}</span></td>
      </tr>
    `).join("");

    // Render ECharts confidence bands
    renderForecastChart(revFc);
  } catch (err) {
    console.error("Failed to load forecast data:", err);
  }
}

function renderForecastChart(revFc) {
  const chartDom = document.getElementById("chart-forecast-bands");
  if (!chartDom) return;

  if (forecastChartInstance) forecastChartInstance.dispose();
  forecastChartInstance = echarts.init(chartDom);

  const historical = (revFc && revFc.historical) || [];
  const forecastPoints = (revFc && revFc.forecast_points) || [];

  const histPeriods = historical.map(h => h.month);
  const histRevs = historical.map(h => h.revenue);

  const fcPeriods = forecastPoints.map(p => p.period);
  const fcPreds = forecastPoints.map(p => p.predicted_revenue);
  const fcLowers = forecastPoints.map(p => p.lower_bound);
  const fcUppers = forecastPoints.map(p => p.upper_bound);

  const allPeriods = [...histPeriods, ...fcPeriods];
  if (allPeriods.length === 0) {
    allPeriods.push("Month +1", "Month +2", "Month +3");
  }
  const histSeriesData = histPeriods.length > 0 ? [...histRevs, ...fcPeriods.map(() => null)] : [0, 0, 0];
  const predSeriesData = fcPeriods.length > 0 ? [...histPeriods.map((_, i) => i === histPeriods.length - 1 ? histRevs[i] : null), ...fcPreds] : [0, 0, 0];
  const lowerSeriesData = [...histPeriods.map(() => null), ...fcLowers];
  const upperSeriesData = [...histPeriods.map(() => null), ...fcUppers];

  const option = {
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(255, 255, 255, 0.98)",
      borderColor: "#e2e8f0",
      borderWidth: 1,
      padding: [12, 16],
      extraCssText: "box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.03); backdrop-filter: blur(8px); border-radius: 10px;",
      textStyle: { color: "#0f172a", fontFamily: "Inter, system-ui, sans-serif" },
      axisPointer: {
        type: "line",
        lineStyle: {
          color: "rgba(148, 163, 184, 0.5)",
          width: 1.5,
          type: [4, 4],
        },
      },
      formatter: (params) => {
        let period = params[0] ? params[0].name : "";
        let html = `<div style="font-size:0.75rem; font-weight:700; color:#64748b; margin-bottom:8px; text-transform:uppercase; letter-spacing:0.05em;">${period} Forecast Model</div>`;
        params.forEach(item => {
          if (item.value === null || item.value === undefined) return;
          if (item.seriesName.includes("CI)")) return;
          const color = item.color;
          const val = Number(item.value || 0);
          html += `
            <div style="display:flex; align-items:center; justify-content:space-between; gap:1.5rem; margin-top:5px; font-size:0.85rem;">
              <div style="display:flex; align-items:center; gap:6px;">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${color}; box-shadow:0 0 6px ${color}88;"></span>
                <span style="color:#475569; font-weight:500;">${item.seriesName}</span>
              </div>
              <strong style="color:#0f172a; font-variant-numeric:tabular-nums;">${formatCurrency(val)}</strong>
            </div>
          `;
        });
        return html;
      },
    },
    legend: {
      data: ["Historical Revenue", "Predicted Revenue", "80% Confidence Band"],
      top: 0,
      right: 0,
      icon: "circle",
      itemWidth: 8,
      itemHeight: 8,
      itemGap: 18,
      textStyle: {
        color: "#64748b",
        fontSize: 12,
        fontWeight: 500,
        fontFamily: "Inter, system-ui, sans-serif",
      },
    },
    grid: {
      left: "2%",
      right: "3%",
      bottom: "6%",
      top: "14%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: allPeriods,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#94a3b8",
        fontSize: 11,
        fontWeight: 500,
        margin: 12,
      },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: {
        lineStyle: {
          color: "rgba(226, 232, 240, 0.7)",
          type: "dashed",
          dashOffset: 2,
        },
      },
      axisLabel: {
        color: "#94a3b8",
        fontSize: 11,
        fontWeight: 500,
        formatter: (v) => `${(v / 1000000).toFixed(0)}M`,
      },
    },
    series: [
      {
        name: "Historical Revenue",
        type: "line",
        smooth: 0.36,
        showSymbol: false,
        symbolSize: 7,
        data: histSeriesData,
        itemStyle: { color: "#2563eb" },
        lineStyle: {
          width: 3,
          color: "#2563eb",
          shadowColor: "rgba(37, 99, 235, 0.35)",
          shadowBlur: 10,
          shadowOffsetY: 4,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(37, 99, 235, 0.22)" },
            { offset: 0.85, color: "rgba(37, 99, 235, 0.02)" },
            { offset: 1, color: "rgba(37, 99, 235, 0.0)" },
          ]),
        },
        emphasis: {
          focus: "series",
          itemStyle: {
            borderWidth: 3,
            borderColor: "#ffffff",
            shadowColor: "rgba(37, 99, 235, 0.5)",
            shadowBlur: 8,
          },
        },
      },
      {
        name: "Predicted Revenue",
        type: "line",
        smooth: 0.36,
        showSymbol: false,
        symbolSize: 7,
        data: predSeriesData,
        itemStyle: { color: "#8b5cf6" },
        lineStyle: {
          width: 3,
          color: "#8b5cf6",
          type: [5, 4],
          shadowColor: "rgba(139, 92, 246, 0.35)",
          shadowBlur: 10,
          shadowOffsetY: 4,
        },
        emphasis: {
          focus: "series",
          itemStyle: {
            borderWidth: 3,
            borderColor: "#ffffff",
            shadowColor: "rgba(139, 92, 246, 0.5)",
            shadowBlur: 8,
          },
        },
      },
      {
        name: "80% Confidence Band",
        type: "line",
        data: upperSeriesData,
        lineStyle: { opacity: 0 },
        stack: "confidence-band",
        symbol: "none",
      },
      {
        name: "80% Confidence Band",
        type: "line",
        data: lowerSeriesData,
        lineStyle: { opacity: 0 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(139, 92, 246, 0.16)" },
            { offset: 1, color: "rgba(139, 92, 246, 0.03)" },
          ]),
        },
        stack: "confidence-band",
        symbol: "none",
      },
    ],
  };

  forecastChartInstance.setOption(option);
}

// -------------------------------------------------------------
// SCREEN 11: ALERTS CENTER
// -------------------------------------------------------------
async function loadAlertsData(severity = "ALL") {
  try {
    const res = await fetch(`${API_BASE}/api/alerts?company_id=${currentCompanyId}&severity=${severity}`);
    const data = await res.json();
    const alerts = data.alerts || [];

    const container = document.getElementById("full-alerts-list");
    if (!alerts.length) {
      container.innerHTML = `<div style="padding:1.5rem; text-align:center; color:#64748b;">No active ${severity === 'ALL' ? '' : severity} alerts detected. Business is operating normally.</div>`;
      return;
    }

    container.innerHTML = alerts.map(a => {
      let iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
      let badgeClass = "badge-low";
      if (a.severity === "CRITICAL") {
        iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
        badgeClass = "badge-danger";
      } else if (a.severity === "WARNING") {
        iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;
        badgeClass = "badge-warning";
      }

      return `
        <div class="alert-item" style="padding:1rem 0;">
          <div class="alert-icon" style="display:flex; align-items:center; justify-content:center;">${iconSvg}</div>
          <div class="alert-content" style="flex:1;">
            <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.25rem;">
              <span class="badge-status ${badgeClass}">${a.severity}</span>
              <span class="title" style="font-size:0.95rem;">${a.title}</span>
            </div>
            <div class="desc" style="font-size:0.85rem; line-height:1.4; margin-bottom:0.4rem;">${a.message}</div>
            <div style="font-size:0.75rem; color:#94a3b8;">Trigger Metric: <code>${a.metric}</code> = ${a.actual_value} (Threshold: ${a.threshold_value})</div>
          </div>
        </div>
      `;
    }).join("");

    document.getElementById("badge-alerts-count").innerText = alerts.length;
  } catch (err) {
    console.error("Failed to load alerts:", err);
  }
}

function filterAlerts(severity) {
  loadAlertsData(severity);
}

function loadReportsData() {
  const compId = currentCompanyId || "company-abc-supermarket-001";
  const pdfLink = document.getElementById("report-pdf-link");
  if (pdfLink) pdfLink.href = `/api/reports/pdf?company_id=${encodeURIComponent(compId)}`;
  const htmlLink = document.getElementById("report-html-link");
  if (htmlLink) htmlLink.href = `/api/reports/html?company_id=${encodeURIComponent(compId)}`;
  const frame = document.getElementById("report-preview-frame");
  if (frame) frame.src = `/api/reports/html?company_id=${encodeURIComponent(compId)}`;

  animateFiguresInContainer(document.getElementById("view-reports"));
}

// -------------------------------------------------------------
// SCREENS 13, 14, 15: UPLOAD & DATA MAPPING
// -------------------------------------------------------------
function setupUploadDropzone() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "#2563eb";
    dropzone.style.background = "#eff6ff";
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.style.borderColor = "#cbd5e1";
    dropzone.style.background = "#ffffff";
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "#cbd5e1";
    dropzone.style.background = "#ffffff";
    if (e.dataTransfer.files.length) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
      handleFileUpload(fileInput.files[0]);
    }
  });

  // Confirm import button
  const confirmBtn = document.getElementById("btn-confirm-import");
  if (confirmBtn) {
    confirmBtn.addEventListener("click", confirmImport);
  }
}

function handleFileUpload(file) {
  const reader = new FileReader();
  reader.onload = async (e) => {
    const base64Data = e.target.result.split(",")[1];
    const payload = {
      file_name: file.name,
      file_base64: base64Data,
      company_id: currentCompanyId,
    };

    try {
      const res = await fetch(`${API_BASE}/api/upload-file`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.success) {
        activeUploadedFilePath = data.file_path;
        renderMappingReview(data);
      } else {
        alert("Upload error: " + data.error);
      }
    } catch (err) {
      alert("Upload failed: " + err.message);
    }
  };
  reader.readAsDataURL(file);
}

let currentUploadCurrencyInfo = null;

function renderMappingReview(uploadResult) {
  const mappingCard = document.getElementById("mapping-card");
  const tbody = document.getElementById("mapping-table-body");
  mappingCard.style.display = "block";

  currentUploadCurrencyInfo = uploadResult.currency_conversion || null;
  const banner = document.getElementById("currency-conversion-banner");
  if (banner && currentUploadCurrencyInfo) {
    banner.style.display = "block";
    const titleEl = document.getElementById("currency-conversion-title");
    const descEl = document.getElementById("currency-conversion-desc");
    const iconEl = document.getElementById("currency-conversion-icon");
    const inputContainer = document.getElementById("currency-rate-input-container");
    const rateInput = document.getElementById("currency-exchange-rate-input");
    const rateLabel = document.getElementById("currency-rate-label");
    const rateUnit = document.getElementById("currency-rate-unit");

    const src = currentUploadCurrencyInfo.source_currency || "USD";
    const tgt = currentUploadCurrencyInfo.target_currency || currentCurrency || "TZS";
    const rate = currentUploadCurrencyInfo.exchange_rate || 1.0;

    if (currentUploadCurrencyInfo.conversion_needed) {
      banner.style.background = "linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%)";
      banner.style.borderColor = "#93c5fd";
      if (iconEl) iconEl.innerText = "💱";
      if (titleEl) {
        titleEl.innerHTML = `Auto-Converting Currency <span class="badge-status badge-healthy" style="font-size:0.75rem; padding:2px 8px; font-weight:700;">${src} ➔ ${tgt}</span>`;
      }
      const exampleAmount = (100 * rate).toLocaleString(undefined, { maximumFractionDigits: 2 });
      if (descEl) {
        descEl.innerHTML = `Spreadsheet figures detected in <strong>${src}</strong> will automatically convert to your business currency (<strong>${tgt}</strong>). (e.g. 100 ${src} ≈ ${exampleAmount} ${tgt}).`;
      }
      if (inputContainer) inputContainer.style.display = "flex";
      if (rateLabel) rateLabel.innerText = `Rate (1 ${src} =):`;
      if (rateUnit) rateUnit.innerText = tgt;
      if (rateInput) rateInput.value = rate;
    } else {
      banner.style.background = "#f0fdf4";
      banner.style.borderColor = "#86efac";
      if (iconEl) iconEl.innerText = "✓";
      if (titleEl) {
        titleEl.innerHTML = `Currency Matched <span class="badge-status badge-healthy" style="font-size:0.75rem; padding:2px 8px; font-weight:700;">${tgt} (100% Match)</span>`;
      }
      if (descEl) {
        descEl.innerHTML = `Spreadsheet amounts match your business currency (<strong>${tgt}</strong>). No conversion needed.`;
      }
      if (inputContainer) inputContainer.style.display = "none";
    }
  } else if (banner) {
    banner.style.display = "none";
  }

  const mappings = uploadResult.mappings || {};
  let rowsHtml = "";

  for (const sheet in mappings) {
    const sheetMap = mappings[sheet];
    for (const srcCol in sheetMap.mappings) {
      const m = sheetMap.mappings[srcCol];
      rowsHtml += `
        <tr>
          <td><strong>${srcCol}</strong> <span class="trend-sub">(${sheet})</span></td>
          <td>➔</td>
          <td><code>${m.system_field}</code></td>
          <td><span class="badge-status badge-healthy">${Math.round(m.confidence * 100)}%</span></td>
          <td>✓ Auto-matched</td>
        </tr>
      `;
    }
  }

  tbody.innerHTML = rowsHtml;
  document.getElementById("progress-status-text").innerText = `Detected ${uploadResult.inspection.sheet_count} sheet(s). Ready to import.`;
}

async function confirmImport() {
  if (!activeUploadedFilePath) return;

  const pBar = document.getElementById("import-progress-bar");
  const pText = document.getElementById("progress-status-text");

  pBar.style.width = "40%";
  pText.innerText = "Validating data and checking duplicates...";

  setTimeout(async () => {
    pBar.style.width = "80%";
    pText.innerText = "Calculating deterministic metrics...";

    try {
      const rateInput = document.getElementById("currency-exchange-rate-input");
      let customRate = null;
      if (rateInput && rateInput.value && currentUploadCurrencyInfo && currentUploadCurrencyInfo.conversion_needed) {
        const parsed = parseFloat(rateInput.value);
        if (!isNaN(parsed) && parsed > 0) {
          customRate = parsed;
        }
      }

      const payload = {
        file_path: activeUploadedFilePath,
        company_id: currentCompanyId,
      };
      if (customRate !== null) {
        payload.exchange_rate = customRate;
      }
      if (currentUploadCurrencyInfo && currentUploadCurrencyInfo.source_currency) {
        payload.source_currency = currentUploadCurrencyInfo.source_currency;
      }

      const res = await fetch(`${API_BASE}/api/confirm-import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await res.json();

      pBar.style.width = "100%";
      const convNotice = result.result && result.result.currency_conversion && result.result.currency_conversion.converted
        ? ` (Auto-converted from ${result.result.currency_conversion.source_currency} to ${result.result.currency_conversion.target_currency})`
        : "";
      pText.innerText = `Import Complete! ${result.result.total_rows_imported} rows imported.${convNotice}`;

      setTimeout(() => {
        document.getElementById("mapping-card").style.display = "none";
        const banner = document.getElementById("currency-conversion-banner");
        if (banner) banner.style.display = "none";
        currentUploadCurrencyInfo = null;
        loadDataSourcesList();
        switchView("dashboard");
        loadAllDashboardData();
      }, 800);
    } catch (err) {
      pText.innerText = "Import failed: " + err.message;
    }
  }, 500);
}

// -------------------------------------------------------------
// DATA SOURCES & SPREADSHEET MANAGER
// -------------------------------------------------------------
async function loadDataSourcesList() {
  const countBadge = document.getElementById("uploaded-files-count");
  const emptyBox = document.getElementById("uploaded-sources-empty");
  const tableContainer = document.getElementById("uploaded-files-table-container");
  const tbody = document.getElementById("uploaded-files-table-body");

  if (!currentCompanyId) {
    if (countBadge) countBadge.innerText = "0 Active Sources";
    if (emptyBox) {
      emptyBox.style.display = "block";
      emptyBox.innerText = "0 Active Sources";
    }
    if (tableContainer) tableContainer.style.display = "none";
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/data-sources?company_id=${encodeURIComponent(currentCompanyId)}`);
    const data = await res.json();
    const files = data.files || [];

    if (files.length === 0) {
      if (countBadge) countBadge.innerText = "0 Active Sources";
      if (emptyBox) {
        emptyBox.style.display = "block";
        emptyBox.innerText = "0 Active Sources";
      }
      if (tableContainer) tableContainer.style.display = "none";
      return;
    }

    if (countBadge) countBadge.innerText = `${files.length} Active Source${files.length === 1 ? '' : 's'}`;
    if (emptyBox) emptyBox.style.display = "none";
    if (tableContainer) tableContainer.style.display = "block";

    if (tbody) {
      tbody.innerHTML = files.map(f => {
        const sheetsList = (f.sheets || []).map(s => `<span class="badge" style="background:#f1f5f9; color:#334155; font-size:11px; margin-right:4px;">${s.name} (${s.rows} rows)</span>`).join("");
        return `
          <tr>
            <td>
              <div style="display:flex; align-items:center; gap:0.5rem;">
                <svg width="20" height="20" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink:0;">
                  <rect x="9" y="4" width="19" height="24" rx="2.5" fill="#107C41"/>
                  <path d="M9 10h19M9 16h19M9 22h19M18 4v24" stroke="#ffffff" stroke-opacity="0.3" stroke-width="1.2"/>
                  <rect x="4" y="8" width="16" height="16" rx="2.5" fill="#185C37"/>
                  <rect x="4" y="8" width="16" height="16" rx="2.5" fill="#107C41"/>
                  <path d="M8 12.2h2l1.6 3 1.6-3h2l-2.6 4.3 2.7 4.5h-2.1l-1.7-3.2-1.7 3.2H7.8l2.8-4.5L8 12.2z" fill="#ffffff"/>
                </svg>
                <strong>${f.name}</strong>
              </div>
            </td>
            <td><span class="badge-status badge-healthy" style="background:#e0f2fe; color:#0369a1;">Excel (.xlsx)</span></td>
            <td>${sheetsList || `${f.sheet_count || 1} sheets`}</td>
            <td><strong>${f.total_rows || '-'} rows</strong></td>
            <td><span class="badge-status badge-healthy">✓ Ingested & Analyzed</span></td>
            <td>
              <div style="display:flex; gap:0.4rem;">
                <a href="/api/download-file?file=${encodeURIComponent(f.name)}" class="btn-secondary" style="font-size:0.75rem; padding:0.25rem 0.6rem; text-decoration:none;" download>
                  Download
                </a>
              </div>
            </td>
          </tr>
        `;
      }).join("");
    }
  } catch (err) {
    console.error("Failed to load data sources:", err);
  }
}

// -------------------------------------------------------------
// 1-CLICK DEMO LOADER
// -------------------------------------------------------------
function setupDemoButton() {
  const btn = document.getElementById("btn-quick-sample");
  if (btn) {
    btn.addEventListener("click", async () => {
      btn.innerText = "⏳ Loading...";
      try {
        const res = await fetch(`${API_BASE}/api/load-sample`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
          btn.innerText = "✓ Demo Loaded!";
          setTimeout(() => { btn.innerText = "🔄 Load Demo Data"; }, 2000);
          // Update session to demo company
          currentCompanyId = "company-abc-supermarket-001";
          currentCurrency = "TZS";
          currentUserName = "Kennedy";
          currentCompanyName = "ABC Supermarket Ltd";
          localStorage.setItem("business_pilot_company_id", currentCompanyId);
          localStorage.setItem("business_pilot_currency", currentCurrency);
          localStorage.setItem("business_pilot_user_name", currentUserName);
          localStorage.setItem("business_pilot_company_name", currentCompanyName);
          localStorage.setItem("bizlens_company_id", currentCompanyId);
          localStorage.setItem("bizlens_currency", currentCurrency);
          localStorage.setItem("bizlens_user_name", currentUserName);
          localStorage.setItem("bizlens_company_name", currentCompanyName);
          applyCompanySession({
            id: currentCompanyId,
            name: currentCompanyName,
            currency: currentCurrency,
            business_type: "Retail",
          }, { name: currentUserName });
          switchView("dashboard");
          loadAllDashboardData();
        }
      } catch (err) {
        alert("Failed to load demo data: " + err.message);
        btn.innerText = "🔄 Load Demo Data";
      }
    });
  }
}

// -------------------------------------------------------------
// WORKSPACE & REGISTRATION MANAGEMENT
// -------------------------------------------------------------
function clearLocalSession() {
  document.documentElement.classList.remove("has-workspace");
  currentCompanyId = "";
  currentCurrency = "TZS";
  currentUserName = "Business Owner";
  currentCompanyName = "My Business";
  localStorage.removeItem("business_pilot_company_id");
  localStorage.removeItem("business_pilot_currency");
  localStorage.removeItem("business_pilot_company_name");
  localStorage.removeItem("business_pilot_user_name");
  localStorage.removeItem("bizlens_company_id");
  localStorage.removeItem("bizlens_currency");
  localStorage.removeItem("bizlens_company_name");
  localStorage.removeItem("bizlens_user_name");

  const headerUserName = document.getElementById("header-user-name");
  if (headerUserName) headerUserName.innerText = "User";

  const headerUserAvatar = document.getElementById("header-user-avatar");
  if (headerUserAvatar) {
    headerUserAvatar.style.backgroundImage = "none";
    headerUserAvatar.innerText = "U";
  }

  const sidebarCompAvatar = document.getElementById("sidebar-company-avatar");
  if (sidebarCompAvatar) sidebarCompAvatar.innerText = "B";

  const sidebarCompName = document.getElementById("sidebar-company-name");
  if (sidebarCompName) sidebarCompName.innerText = "My Business";

  const sidebarCompSub = document.getElementById("sidebar-company-sub");
  if (sidebarCompSub) sidebarCompSub.innerText = "Workspace · TZS";

  const dashGreeting = document.getElementById("dash-greeting");
  if (dashGreeting) dashGreeting.innerText = "Good morning";
}

async function checkAuthSession() {
  try {
    if (!currentCompanyId || !currentCompanyId.trim()) {
      clearLocalSession();
      openRegistrationModal(false);
      return;
    }

    const queryParams = new URLSearchParams({
      company_id: currentCompanyId,
      company_name: currentCompanyName,
      currency: currentCurrency,
      user_name: currentUserName,
      business_type: currentBusinessType,
    });

    const res = await fetch(`${API_BASE}/api/auth/session?${queryParams.toString()}`);
    const data = await res.json();
    if (data.authenticated && data.company) {
      applyCompanySession(data.company, data.user);
      closeRegistrationModal();
      loadAllDashboardData();
    } else {
      // Retain active local registration so page refresh never drops user back to modal
      applyCompanySession({
        id: currentCompanyId,
        name: currentCompanyName,
        currency: currentCurrency,
        business_type: currentBusinessType,
      }, { name: currentUserName });
      closeRegistrationModal();
      loadAllDashboardData();
    }
  } catch (err) {
    console.warn("Auth check network notice; maintaining registered workspace:", err);
    if (currentCompanyId && currentCompanyId.trim()) {
      applyCompanySession({
        id: currentCompanyId,
        name: currentCompanyName,
        currency: currentCurrency,
        business_type: currentBusinessType,
      }, { name: currentUserName });
      closeRegistrationModal();
      loadAllDashboardData();
    } else {
      clearLocalSession();
      openRegistrationModal(false);
    }
  }
}

function applyCompanySession(comp, user) {
  if (!comp) return;
  currentCompanyId = comp.id;
  currentCurrency = comp.currency || currentCurrency || "TZS";
  currentCompanyName = comp.name || currentCompanyName || "My Business";
  currentUserName = (user && user.name) ? user.name : (currentUserName || "Business Owner");

  localStorage.setItem("business_pilot_company_id", currentCompanyId);
  localStorage.setItem("business_pilot_currency", currentCurrency);
  localStorage.setItem("business_pilot_company_name", currentCompanyName);
  localStorage.setItem("business_pilot_user_name", currentUserName);
  localStorage.setItem("bizlens_company_id", currentCompanyId);
  localStorage.setItem("bizlens_currency", currentCurrency);
  localStorage.setItem("bizlens_company_name", currentCompanyName);
  localStorage.setItem("bizlens_user_name", currentUserName);

  // Prevent registration modal from popping up on page refresh
  document.documentElement.classList.add("has-workspace");

  // Update table header currency labels
  document.querySelectorAll(".currency-label").forEach(el => {
    el.innerText = currentCurrency;
  });
  const pnlCurrLabel = document.getElementById("pnl-currency-label");
  if (pnlCurrLabel) pnlCurrLabel.innerText = currentCurrency;

  // Immediately update KPI cards with the selected currency (avoid hardcoded $0)
  const revEl = document.getElementById("kpi-rev-val");
  const profitEl = document.getElementById("kpi-profit-val");
  const expEl = document.getElementById("kpi-exp-val");
  const cashEl = document.getElementById("kpi-cash-val");
  if (revEl && (!revEl.innerText || revEl.innerText === "0" || revEl.innerText.includes("$"))) {
    revEl.innerText = formatCurrency(0, currentCurrency);
  }
  if (profitEl && (!profitEl.innerText || profitEl.innerText === "0" || profitEl.innerText.includes("$"))) {
    profitEl.innerText = formatCurrency(0, currentCurrency);
  }
  if (expEl && (!expEl.innerText || expEl.innerText === "0" || expEl.innerText.includes("$"))) {
    expEl.innerText = formatCurrency(0, currentCurrency);
  }
  if (cashEl && (!cashEl.innerText || cashEl.innerText === "0" || cashEl.innerText.includes("$"))) {
    cashEl.innerText = formatCurrency(0, currentCurrency);
  }

  // Update Greeting & Badges
  const dashGreeting = document.getElementById("dash-greeting");
  if (dashGreeting) dashGreeting.innerText = `Good morning, ${currentUserName}`;

  const headerUserName = document.getElementById("header-user-name");
  if (headerUserName) headerUserName.innerText = currentUserName;

  const headerUserAvatar = document.getElementById("header-user-avatar");
  if (headerUserAvatar) {
    const savedPic = localStorage.getItem(`business_pilot_avatar_${currentCompanyId}`) || localStorage.getItem("business_pilot_user_avatar");
    if (savedPic) {
      headerUserAvatar.style.backgroundImage = `url("${savedPic}")`;
      headerUserAvatar.innerText = "";
    } else {
      headerUserAvatar.style.backgroundImage = "none";
      headerUserAvatar.innerText = currentUserName.charAt(0).toUpperCase();
    }
  }

  const sidebarCompAvatar = document.getElementById("sidebar-company-avatar");
  if (sidebarCompAvatar) sidebarCompAvatar.innerText = currentCompanyName.charAt(0).toUpperCase();

  const sidebarCompName = document.getElementById("sidebar-company-name");
  if (sidebarCompName) sidebarCompName.innerText = currentCompanyName;

  const sidebarCompSub = document.getElementById("sidebar-company-sub");
  if (sidebarCompSub) sidebarCompSub.innerText = `${comp.business_type || currentBusinessType || "Business"} · ${currentCurrency}`;

  const onboardingTitle = document.getElementById("onboarding-comp-title");
  if (onboardingTitle) onboardingTitle.innerText = `${currentCompanyName} Workspace Ready`;

  currentBusinessType = comp.business_type || currentBusinessType || "Retail";
  localStorage.setItem("business_pilot_business_type", currentBusinessType);
  applyIndustryCustomizations(currentBusinessType);

  loadReportsData();
}

function applyIndustryCustomizations(businessType) {
  const isRetail = (businessType || "").toLowerCase().includes("retail") || businessType === "Supermarket";

  const navSales = document.querySelector('.nav-item[data-view="sales"]');
  const navInventory = document.querySelector('.nav-item[data-view="inventory"]');
  const salesTitle = document.querySelector('#view-sales .view-title-group h1');
  const invTitle = document.querySelector('#view-inventory .view-title-group h1');
  const dashSub = document.querySelector('#view-dashboard .view-title-group p');
  const onboardingDesc = document.getElementById("onboarding-desc-text");

  if (isRetail) {
    if (navSales) navSales.innerHTML = `POS Sales`;
    if (navInventory) {
      const curCount = document.getElementById("badge-inventory-warn")?.innerText || "0";
      navInventory.innerHTML = `Inventory & Stockouts <span class="badge" id="badge-inventory-warn">${curCount}</span>`;
    }
    if (salesTitle) salesTitle.innerText = "Point-of-Sale (POS) & Retail Transactions";
    if (invTitle) invTitle.innerText = "Retail Shelf Stock & SKU Reorder Matrix";
    if (dashSub) dashSub.innerText = "Retail Operations & Inventory Control Center — POS Velocity, Shelf Health & Working Capital";
    if (onboardingDesc) onboardingDesc.innerText = "Upload your Point of Sale (POS) register, daily sales receipts, or SKU inventory spreadsheets.";
  } else {
    // Other businesses: standard business pilot layout
    if (navSales) navSales.innerHTML = `Sales`;
    if (navInventory) {
      const curCount = document.getElementById("badge-inventory-warn")?.innerText || "0";
      navInventory.innerHTML = `Inventory <span class="badge" id="badge-inventory-warn">${curCount}</span>`;
    }
    if (salesTitle) salesTitle.innerText = "Sales Invoices & Transactions";
    if (invTitle) invTitle.innerText = "Inventory & Stock Management";
    if (dashSub) dashSub.innerText = "Executive Financial Overview & Operational Runway";
    if (onboardingDesc) onboardingDesc.innerText = "Upload the business spreadsheet below. Business Pilot will auto-detect your data and generate your executive dashboard, P&L, cash flow, and AI analyst.";
  }
}

function setupIndustryPreview() {
  const bTypeSelect = document.getElementById("reg-business-type");
  const previewTitle = document.getElementById("preview-industry-title");
  const previewBadge = document.getElementById("preview-industry-badge");
  const previewDesc = document.getElementById("preview-industry-desc");

  if (!bTypeSelect || !previewTitle || !previewDesc) return;

  const industryProfiles = {
    "Retail": {
      title: "Retail & Supermarket Suite",
      desc: "Features enabled: Point of Sale (POS) Cash Register Invoices, SKU Reorder Matrix & Shelf Dead-Stock Alerts, Walk-in Footfall Analytics, and Product Category Margin Bridges."
    },
    "Wholesale": {
      title: "Wholesale & Distribution Suite",
      desc: "Features enabled: Bulk Invoicing & 30/60/90-Day AR Aging, Pallet & Batch Warehousing, Tiered Wholesale Pricing, and Credit Terms Risk Monitor."
    },
    "Services": {
      title: "Professional Services & Agency Suite",
      desc: "Features enabled: Client Retainers & Milestone Invoicing, Consultant Billable Overhead Burn, Client Lifetime Value (LTV), and Cash Runway Reserves."
    },
    "E-Commerce": {
      title: "E-Commerce & Digital Commerce Suite",
      desc: "Features enabled: Online Cart Conversions, Fulfillment Cost Tracking, Return & Refund Rate Analytics, and Payment Gateway Fee Auditing."
    },
    "Manufacturing": {
      title: "Manufacturing & Production Suite",
      desc: "Features enabled: Raw Material Bill of Materials (BOM), Work-In-Progress (WIP) Valuation, Scrap & Yield Rates, and Machine Operating Overhead."
    },
    "Hospitality": {
      title: "Hospitality & Restaurant Suite",
      desc: "Features enabled: Daily Table Turn Rates, Per-Cover Average Spend, Food & Beverage Spoilage Ratios, and Peak Shift Staffing Expenses."
    },
    "Healthcare": {
      title: "Pharmacy & Healthcare Suite",
      desc: "Features enabled: Prescription Sales Ledger, Batch Expiration Risk Monitoring, Regulated Insurance Receivables, and Controlled Substance Inventory."
    },
    "Other": {
      title: "Standard Executive Business Suite",
      desc: "Standard layout: Executive Profit & Loss (P&L), Revenue & Expense Breakdown, Working Capital Runway, and Deterministic AI Management Briefings."
    }
  };

  function updatePreview() {
    const val = bTypeSelect.value || "Retail";
    const profile = industryProfiles[val] || industryProfiles["Other"];
    previewTitle.innerText = profile.title;
    if (previewBadge) {
      previewBadge.remove();
    }
    previewDesc.innerText = profile.desc;
  }

  bTypeSelect.addEventListener("change", updatePreview);
  updatePreview();
}

function openRegistrationModal(canCancel = true) {
  const modal = document.getElementById("registration-modal");
  const cancelBtn = document.getElementById("btn-close-modal");
  if (cancelBtn) {
    cancelBtn.style.display = canCancel ? "inline-block" : "none";
  }
  if (modal) {
    modal.classList.add("force-open");
    modal.style.display = "flex";
  }
}

function closeRegistrationModal() {
  const modal = document.getElementById("registration-modal");
  if (modal) {
    modal.classList.remove("force-open");
    modal.style.display = "none";
  }
}

async function handleRegistrationSubmit(e) {
  e.preventDefault();
  const compName = document.getElementById("reg-company-name").value.trim();
  const userName = document.getElementById("reg-user-name").value.trim();
  const email = document.getElementById("reg-email").value.trim();
  const currency = document.getElementById("reg-currency").value;
  const bType = document.getElementById("reg-business-type").value;
  const country = document.getElementById("reg-country").value.trim();

  const btn = document.getElementById("btn-submit-register");
  btn.innerText = "Creating Workspace...";
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_name: compName,
        user_name: userName,
        email: email,
        currency: currency,
        business_type: bType,
        country: country,
      }),
    });
    const responseText = await res.text();
    let data;
    try {
      data = JSON.parse(responseText);
    } catch {
      const responseDetail = responseText.trim();
      const message = responseDetail
        ? responseDetail.slice(0, 300)
        : `The server returned an empty response (HTTP ${res.status}). Check the Vercel function logs for details.`;
      throw new Error(`Registration endpoint returned an invalid response (HTTP ${res.status}): ${message}`);
    }

    if (!data || typeof data !== "object" || Array.isArray(data)) {
      throw new Error(`Registration endpoint returned an unexpected response (HTTP ${res.status}).`);
    }

    if (!res.ok) {
      throw new Error(data.error || `The server returned HTTP ${res.status}.`);
    }

    if (data.success) {
      applyCompanySession(data.company, data.user);
      closeRegistrationModal();

      // Show onboarding card and route user directly to General Overview
      const onboardingCard = document.getElementById("onboarding-welcome-card");
      if (onboardingCard) onboardingCard.style.display = "block";
      switchView("dashboard");
      loadAllDashboardData();
    } else {
      alert("Registration failed: " + data.error);
    }
  } catch (err) {
    alert("Registration error: " + err.message);
  } finally {
    btn.innerText = "Create Business Workspace ➔";
    btn.disabled = false;
  }
}

function setupWorkspaceControls() {
  const newBtn = document.getElementById("btn-new-workspace");
  if (newBtn) {
    newBtn.addEventListener("click", () => openRegistrationModal(true));
  }
}

// -------------------------------------------------------------
// USER PROFILE AVATAR UPLOADER
// -------------------------------------------------------------
function setupUserAvatarUpload() {
  const badge = document.getElementById("header-user-badge");
  const fileInput = document.getElementById("user-avatar-input");
  const avatar = document.getElementById("header-user-avatar");

  if (!badge || !fileInput || !avatar) return;

  badge.addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files[0]) {
      const file = fileInput.files[0];
      if (!file.type.startsWith("image/")) {
        alert("Please select a valid image file (PNG, JPG, WEBP).");
        return;
      }
      const reader = new FileReader();
      reader.onload = (e) => {
        const dataUrl = e.target.result;
        avatar.style.backgroundImage = `url("${dataUrl}")`;
        avatar.innerText = "";
        localStorage.setItem(`business_pilot_avatar_${currentCompanyId}`, dataUrl);
        localStorage.setItem("business_pilot_user_avatar", dataUrl);
      };
      reader.readAsDataURL(file);
    }
  });

  // Restore avatar on load if available
  const savedPic = localStorage.getItem(`business_pilot_avatar_${currentCompanyId}`) || localStorage.getItem("business_pilot_user_avatar");
  if (savedPic) {
    avatar.style.backgroundImage = `url("${savedPic}")`;
    avatar.innerText = "";
  }
}

// -------------------------------------------------------------
// GOOGLE SHEETS & UPLOAD TAB SWITCHER
// -------------------------------------------------------------
function switchUploadTab(tab) {
  const fileTab = document.getElementById("tab-btn-file");
  const gsheetTab = document.getElementById("tab-btn-gsheet");
  const filePanel = document.getElementById("upload-panel-file");
  const gsheetPanel = document.getElementById("upload-panel-gsheet");

  if (tab === "file") {
    if (fileTab) fileTab.classList.add("active");
    if (gsheetTab) gsheetTab.classList.remove("active");
    if (filePanel) filePanel.style.display = "block";
    if (gsheetPanel) gsheetPanel.style.display = "none";
  } else {
    if (fileTab) fileTab.classList.remove("active");
    if (gsheetTab) gsheetTab.classList.add("active");
    if (filePanel) filePanel.style.display = "none";
    if (gsheetPanel) gsheetPanel.style.display = "block";
  }
}

async function handleGoogleSheetsImport() {
  const input = document.getElementById("gsheet-url-input");
  const btn = document.getElementById("btn-fetch-gsheet");
  const url = input ? input.value.trim() : "";

  if (!url) {
    alert("Please paste a Google Sheets URL first.");
    return;
  }

  btn.innerHTML = "<span>⏳</span> Getting Sheet...";
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/import-google-sheet`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: url,
        company_id: currentCompanyId,
      }),
    });
    const data = await res.json();
    if (data.success) {
      activeUploadedFilePath = data.file_path;
      renderMappingReview(data);
    } else {
      alert("Google Sheets Import Notice:\n\n" + data.error);
    }
  } catch (err) {
    alert("Error fetching Google Sheet: " + err.message);
  } finally {
    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"></path><polyline points="7 11 12 16 17 11"></polyline><line x1="12" y1="4" x2="12" y2="16"></line></svg><span>Get Sheet</span>`;
    btn.disabled = false;
  }
}
