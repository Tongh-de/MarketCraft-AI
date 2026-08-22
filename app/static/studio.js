const state = { plugins: [], tasks: [], currentTask: null, previewUrl: null };
const $ = (selector) => document.querySelector(selector);
const elements = {
  form: $("#creationForm"), image: $("#imageInput"), preview: $("#sourcePreview"),
  placeholder: $("#uploadPlaceholder"), dropzone: $("#dropzone"), plugin: $("#pluginSelect"),
  pluginList: $("#pluginList"), pluginCount: $("#pluginCount"), button: $("#generateButton"),
  empty: $("#emptyResult"), grid: $("#assetGrid"), status: $("#taskStatus"),
  summary: $("#taskSummary"), trace: $("#traceList"), recent: $("#recentTasks"),
  refresh: $("#refreshTasks"), toast: $("#toast"),
};

function escapeHtml(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

async function jsonRequest(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(payload?.detail || `请求失败：HTTP ${response.status}`);
  return payload;
}

let toastTimer;
function showToast(message, type = "success") {
  clearTimeout(toastTimer); elements.toast.textContent = message;
  elements.toast.className = `toast show${type === "error" ? " error" : ""}`;
  toastTimer = window.setTimeout(() => { elements.toast.className = "toast"; }, 3200);
}

function showSelectedImage(file) {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = URL.createObjectURL(file);
  elements.preview.src = state.previewUrl; elements.preview.hidden = false; elements.placeholder.hidden = true;
}

elements.image.addEventListener("change", () => { if (elements.image.files[0]) showSelectedImage(elements.image.files[0]); });
["dragenter", "dragover"].forEach((name) => elements.dropzone.addEventListener(name, (event) => { event.preventDefault(); elements.dropzone.classList.add("dragging"); }));
["dragleave", "drop"].forEach((name) => elements.dropzone.addEventListener(name, () => elements.dropzone.classList.remove("dragging")));
elements.dropzone.addEventListener("drop", (event) => {
  event.preventDefault(); const file = event.dataTransfer.files[0]; if (!file) return;
  const transfer = new DataTransfer(); transfer.items.add(file); elements.image.files = transfer.files; showSelectedImage(file);
});

function renderPlugins() {
  elements.pluginCount.textContent = `${state.plugins.length} 个插件已连接`;
  const generationPlugins = state.plugins.filter((item) => item.capabilities.some((capability) => capability !== "competitor_analysis"));
  elements.plugin.innerHTML = generationPlugins.map((item) => `<option value="${escapeHtml(item.plugin_id)}">${escapeHtml(item.name)} · ${item.mode.toUpperCase()}</option>`).join("");
  elements.pluginList.innerHTML = state.plugins.map((item) => `
    <div class="plugin-item"><span class="plugin-icon">${escapeHtml(item.name.slice(0, 1))}</span>
      <span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.capabilities.length)} 项能力 · ${escapeHtml(item.mode.toUpperCase())}</small></span><i class="online-dot"></i></div>`).join("");
}

const traceLabels = {
  task_created: "创建创作任务", validate_product_input: "校验商品信息",
  lock_source_product_identity: "锁定商品颜色与版型", generate_requested_assets: "生成请求素材",
  validate_asset_manifest: "校验素材清单", task_completed: "任务执行完成",
};
function renderTask(task) {
  state.currentTask = task; elements.empty.hidden = true; elements.grid.hidden = false; elements.summary.hidden = false;
  elements.status.textContent = task.status === "completed" ? "生成完成" : task.status;
  elements.grid.innerHTML = task.assets.map((asset) => `
    <article class="asset-card"><img src="${escapeHtml(asset.url)}" alt="${escapeHtml(asset.label)}" />
      <div class="asset-meta"><strong>${escapeHtml(asset.label)}</strong><span>${asset.mock ? "MOCK" : "LIVE"}</span></div></article>`).join("");
  elements.summary.innerHTML = `<strong>任务 ${escapeHtml(task.task_id)}</strong><br>Skill：${escapeHtml(task.skill_id)} · 插件：${escapeHtml(task.plugin_id)} · 产物：${task.assets.length} 个`;
  elements.trace.innerHTML = task.trace.map((step) => {
    const label = step.startsWith("select_skill:") ? `选择 Skill：${step.split(":")[1]}` : step.startsWith("select_plugin:") ? `调用插件：${step.split(":")[1]}` : (traceLabels[step] || step);
    return `<li>${escapeHtml(label)}</li>`;
  }).join("");
}

function renderRecentTasks() {
  if (!state.tasks.length) { elements.recent.innerHTML = '<p class="muted">暂无任务</p>'; return; }
  elements.recent.innerHTML = state.tasks.slice(0, 6).map((task) => `
    <article class="recent-task" data-task-id="${escapeHtml(task.task_id)}"><strong>${escapeHtml(task.product.name)}</strong>
      <small>${escapeHtml(task.status)} · ${task.assets.length} 个素材 · ${new Date(task.created_at).toLocaleString("zh-CN")}</small></article>`).join("");
}

async function loadCatalog() {
  try {
    const [plugins, tasks] = await Promise.all([jsonRequest("/api/v1/creation/plugins"), jsonRequest("/api/v1/creation/tasks?limit=20")]);
    state.plugins = plugins; state.tasks = tasks; renderPlugins(); renderRecentTasks();
  } catch (error) { showToast(error.message, "error"); }
}

async function uploadImage(file) {
  const form = new FormData(); form.append("file", file);
  const response = await fetch("/api/v1/creation/uploads", { method: "POST", body: form });
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(payload?.detail || `图片上传失败：HTTP ${response.status}`);
  return payload;
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault(); const file = elements.image.files[0]; if (!file) return showToast("请先上传商品图", "error");
  const outputs = [...document.querySelectorAll('.output-options input:checked')].map((item) => item.value);
  if (!outputs.length) return showToast("至少选择一种生成结果", "error");
  elements.button.disabled = true; elements.button.textContent = "正在上传并生成…"; elements.status.textContent = "执行中";
  const form = new FormData(elements.form);
  try {
    const uploaded = await uploadImage(file);
    const task = await jsonRequest("/api/v1/creation/tasks", { method: "POST", body: JSON.stringify({
      product: { sku: form.get("sku").trim(), name: form.get("name").trim(), category: form.get("category").trim(), source_image_url: uploaded.url, target_audience: form.get("audience").trim() },
      instruction: form.get("instruction").trim(), requested_outputs: outputs,
      preferred_plugin_id: form.get("plugin"), actor: "creative-operator",
    }) });
    renderTask(task); await loadCatalog();
    if (task.status === "failed") throw new Error(task.error || "创作任务失败");
    showToast(`已生成 ${task.assets.length} 个商品素材`); $("#results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) { elements.status.textContent = "生成失败"; showToast(error.message, "error"); }
  finally { elements.button.disabled = false; elements.button.textContent = "✦ 开始 AI 创作"; }
});

elements.refresh.addEventListener("click", loadCatalog);
elements.recent.addEventListener("click", async (event) => {
  const card = event.target.closest("[data-task-id]"); if (!card) return;
  try { renderTask(await jsonRequest(`/api/v1/creation/tasks/${card.dataset.taskId}`)); $("#results").scrollIntoView({ behavior: "smooth" }); }
  catch (error) { showToast(error.message, "error"); }
});

loadCatalog();
