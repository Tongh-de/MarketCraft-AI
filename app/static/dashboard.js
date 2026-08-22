const state = {
  runs: [],
  selectedRunId: null,
};

const labels = {
  status: {
    pending_review: "待审核",
    approved: "已批准",
    rejected: "已拒绝",
    completed: "已完成",
    partial_failed: "部分失败",
  },
  action: {
    fulfill_order: "预占库存并履约",
    create_restock_task: "创建补货任务",
  },
  channel: {
    amazon: "Amazon",
    tiktok_shop: "TikTok Shop",
  },
  trace: {
    validate_order: "校验订单结构",
    fetch_inventory: "读取 ERP 库存",
    plan_operation: "生成运营决策",
    require_human_review: "进入人工审核",
    execute_approved_operation: "执行已批准操作",
  },
};

const elements = {
  body: document.querySelector("#runsTableBody"),
  empty: document.querySelector("#emptyState"),
  detail: document.querySelector("#runDetail"),
  form: document.querySelector("#operationForm"),
  filter: document.querySelector("#statusFilter"),
  refresh: document.querySelector("#refreshButton"),
  submit: document.querySelector("#submitButton"),
  toast: document.querySelector("#toast"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload?.detail || `请求失败：HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

let toastTimer;
function showToast(message, type = "success") {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.className = `toast show${type === "error" ? " error" : ""}`;
  toastTimer = window.setTimeout(() => {
    elements.toast.className = "toast";
  }, 3200);
}

function renderKpis() {
  document.querySelector("#totalRuns").textContent = state.runs.length;
  document.querySelector("#pendingRuns").textContent = state.runs.filter(
    (run) => run.status === "pending_review",
  ).length;
  document.querySelector("#completedRuns").textContent = state.runs.filter(
    (run) => run.status === "completed",
  ).length;
  document.querySelector("#riskRuns").textContent = state.runs.filter(
    (run) => run.risk_flags.length > 0 || run.status === "partial_failed",
  ).length;
}

function filteredRuns() {
  const selectedStatus = elements.filter.value;
  return selectedStatus
    ? state.runs.filter((run) => run.status === selectedStatus)
    : state.runs;
}

function renderTable() {
  const runs = filteredRuns();
  elements.empty.hidden = runs.length > 0;
  elements.body.innerHTML = runs
    .map((run) => {
      const risk = run.risk_flags.length
        ? `<span class="risk-chip">${escapeHtml(run.risk_flags.length)} 项风险</span>`
        : '<span class="risk-chip clear">正常</span>';
      const selected = run.run_id === state.selectedRunId ? "selected" : "";
      return `
        <tr class="${selected}" data-run-id="${escapeHtml(run.run_id)}">
          <td class="order-cell">
            <strong>${escapeHtml(run.order.order_id)}</strong>
            <small>${escapeHtml(run.order.buyer_region)} · ${escapeHtml(run.order.lines.length)} 个 SKU</small>
          </td>
          <td><span class="platform-chip">${escapeHtml(labels.channel[run.order.channel] || run.order.channel)}</span></td>
          <td>${escapeHtml(labels.action[run.recommended_action] || run.recommended_action)}</td>
          <td><span class="status-chip status-${escapeHtml(run.status)}">${escapeHtml(labels.status[run.status] || run.status)}</span></td>
          <td>${risk}</td>
        </tr>`;
    })
    .join("");
}

function renderInventory(run) {
  return run.inventory_checks
    .map(
      (item) => `
        <li class="evidence-row">
          <span><strong>${escapeHtml(item.sku)}</strong><br>${escapeHtml(item.warehouse)}</span>
          <span>需求 ${escapeHtml(item.required)} / 可用 ${escapeHtml(item.available)} / 缺口 ${escapeHtml(item.shortage)}</span>
        </li>`,
    )
    .join("");
}

function renderTrace(run) {
  return run.trace
    .map(
      (step, index) => `
        <li><strong>${String(index + 1).padStart(2, "0")}</strong> ${escapeHtml(labels.trace[step] || step)}</li>`,
    )
    .join("");
}

function renderExecutions(run) {
  if (!run.execution_results.length) {
    return '<p class="panel-description">审批通过并执行后，这里会显示 ERP 与平台返回结果。</p>';
  }
  return run.execution_results
    .map(
      (item) => `
        <div class="execution-result">
          <strong>${escapeHtml(item.system)} · ${escapeHtml(item.action)}</strong>
          <span class="status-chip status-${item.status === "completed" ? "completed" : "partial_failed"}">
            ${item.status === "completed" ? "成功" : "失败"}${item.mock ? " · MOCK" : ""}
          </span>
          ${item.external_id ? `<code>${escapeHtml(item.external_id)}</code>` : ""}
          ${item.error ? `<code>${escapeHtml(item.error)}</code>` : ""}
        </div>`,
    )
    .join("");
}

function renderActions(run) {
  if (run.status === "pending_review") {
    return `
      <button class="button danger" type="button" data-action="reject">拒绝</button>
      <button class="button primary" type="button" data-action="approve">批准方案</button>`;
  }
  if (run.status === "approved") {
    return '<button class="button primary" type="button" data-action="execute">执行外部操作</button>';
  }
  return "";
}

function renderDetail() {
  const run = state.runs.find((item) => item.run_id === state.selectedRunId);
  if (!run) {
    elements.detail.innerHTML = `
      <div class="detail-placeholder">
        <span>选择一条任务</span>
        <p>查看库存证据、Agent 决策、审批记录和外部系统执行结果。</p>
      </div>`;
    return;
  }
  const risks = run.risk_flags.length
    ? run.risk_flags.map((risk) => `<span class="risk-chip">${escapeHtml(risk)}</span>`).join(" ")
    : '<span class="risk-chip clear">未发现阻断风险</span>';
  elements.detail.innerHTML = `
    <div class="detail-content">
      <div class="detail-heading">
        <div>
          <div class="eyebrow">RUN ${escapeHtml(run.run_id)}</div>
          <h2>${escapeHtml(run.order.order_id)} · ${escapeHtml(labels.action[run.recommended_action])}</h2>
          <p>${escapeHtml(run.recommendation_reason)}</p>
        </div>
        <div class="detail-actions">${renderActions(run)}</div>
      </div>
      <div class="detail-grid">
        <article class="detail-card">
          <h3>库存证据</h3>
          <ul class="evidence-list">${renderInventory(run)}</ul>
        </article>
        <article class="detail-card">
          <h3>风险与审批</h3>
          <div>${risks}</div>
          <ul class="evidence-list" style="margin-top: 14px">
            <li class="evidence-row"><span>提交人</span><strong>${escapeHtml(run.requested_by)}</strong></li>
            <li class="evidence-row"><span>审核人</span><strong>${escapeHtml(run.reviewed_by || "等待审核")}</strong></li>
            <li class="evidence-row"><span>飞书通知</span><strong>MOCK 已生成</strong></li>
          </ul>
        </article>
        <article class="detail-card">
          <h3>Agent 执行轨迹</h3>
          <ol class="timeline">${renderTrace(run)}</ol>
        </article>
        <article class="detail-card" style="grid-column: 1 / -1">
          <h3>外部系统执行结果</h3>
          ${renderExecutions(run)}
        </article>
      </div>
    </div>`;
}

async function loadRuns({ preserveSelection = true } = {}) {
  elements.refresh.disabled = true;
  try {
    state.runs = await request("/api/v1/operations/runs?limit=200");
    if (!preserveSelection || !state.runs.some((run) => run.run_id === state.selectedRunId)) {
      state.selectedRunId = state.runs[0]?.run_id || null;
    }
    renderKpis();
    renderTable();
    renderDetail();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    elements.refresh.disabled = false;
  }
}

elements.body.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-run-id]");
  if (!row) return;
  state.selectedRunId = row.dataset.runId;
  renderTable();
  renderDetail();
  elements.detail.scrollIntoView({ behavior: "smooth", block: "start" });
});

elements.detail.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button || !state.selectedRunId) return;
  button.disabled = true;
  try {
    if (button.dataset.action === "approve") {
      await request(`/api/v1/operations/runs/${state.selectedRunId}/decision`, {
        method: "POST",
        body: JSON.stringify({ reviewer: "reviewer-b", action: "approve" }),
      });
      showToast("运营方案已由 reviewer-b 批准");
    } else if (button.dataset.action === "reject") {
      const reason = window.prompt("请输入拒绝原因", "库存或履约方案需要调整");
      if (!reason) return;
      await request(`/api/v1/operations/runs/${state.selectedRunId}/decision`, {
        method: "POST",
        body: JSON.stringify({ reviewer: "reviewer-b", action: "reject", reason }),
      });
      showToast("运营方案已拒绝");
    } else if (button.dataset.action === "execute") {
      await request(`/api/v1/operations/runs/${state.selectedRunId}/execute`, {
        method: "POST",
        body: JSON.stringify({ actor: "executor-c" }),
      });
      showToast("外部系统操作执行完成");
    }
    await loadRuns();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    button.disabled = false;
  }
});

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.submit.disabled = true;
  elements.submit.textContent = "Agent 运行中…";
  const form = new FormData(elements.form);
  const channel = form.get("channel");
  const orderId = form.get("orderId").trim();
  const sku = form.get("sku").trim();
  const quantity = Number(form.get("quantity"));
  try {
    await request(`/api/v1/operations/inventory/${encodeURIComponent(sku)}`, {
      method: "PUT",
      body: JSON.stringify({
        sku,
        warehouse: form.get("warehouse").trim(),
        available: Number(form.get("available")),
        reserved: 0,
        reorder_point: Number(form.get("reorderPoint")),
      }),
    });
    await request(
      `/api/v1/operations/platform-orders/${channel}/${encodeURIComponent(orderId)}`,
      {
        method: "PUT",
        body: JSON.stringify({
          order_id: orderId,
          channel,
          buyer_region: form.get("region"),
          lines: [{ sku, quantity }],
        }),
      },
    );
    const run = await request(
      `/api/v1/operations/platform-orders/${channel}/${encodeURIComponent(orderId)}/process`,
      {
        method: "POST",
        body: JSON.stringify({
          actor: "operations-agent",
          idempotency_key: `dashboard-${channel}-${orderId}`,
        }),
      },
    );
    state.selectedRunId = run.run_id;
    showToast("订单已拉取，Agent 决策等待人工审核");
    await loadRuns();
    elements.detail.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    elements.submit.disabled = false;
    elements.submit.textContent = "创建并运行 Agent";
  }
});

elements.filter.addEventListener("change", renderTable);
elements.refresh.addEventListener("click", () => loadRuns());

loadRuns({ preserveSelection: false });
window.setInterval(() => loadRuns(), 15000);
