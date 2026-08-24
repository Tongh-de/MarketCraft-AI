const state = { view: "home", skills: [], services: [], frameSource: "" };
const $ = (selector) => document.querySelector(selector);

const elements = {
  title: $("#viewTitle"),
  eyebrow: $("#viewEyebrow"),
  description: $("#viewDescription"),
  home: $("#homeView"),
  frameView: $("#frameView"),
  frame: $("#moduleFrame"),
  skillsView: $("#skillsView"),
  servicesView: $("#servicesView"),
  nav: [...document.querySelectorAll(".unified-nav button[data-view]")],
  refresh: $("#refreshShell"),
  toast: $("#shellToast"),
  commandForm: $("#commandForm"),
  command: $("#commandInput"),
  chatLog: $("#agentChat"),
  agentPlan: $("#agentPlan"),
  skillCatalog: $("#skillCatalog"),
  skillSearch: $("#skillSearch"),
  skillStatus: $("#skillCatalogStatus"),
  skillForm: $("#skillForm"),
  skillPlan: $("#skillPlanOutput"),
  serviceCatalog: $("#serviceCatalog"),
  serviceForm: $("#serviceForm"),
  skillNavCount: $("#skillNavCount"),
  serviceNavCount: $("#serviceNavCount"),
  homeSkillCount: $("#homeSkillCount"),
  homeServiceCount: $("#homeServiceCount"),
};

const views = {
  home: { title: "AI 电商工作台", eyebrow: "CONVERSATIONAL COMMERCE WORKSPACE", description: "直接和 Agent 对话，让它调用模型并返回结果。" },
  campaign: { title: "营销文案生成", eyebrow: "CAMPAIGN COPY GENERATION", description: "调用真实模型生成卖点、小红书和抖音文案。", src: "/campaign-studio?embed=1" },
  image: { title: "文生图", eyebrow: "TEXT TO IMAGE", description: "输入提示词，直接调用通义万相生成图片。", src: "/image-studio?embed=1" },
  studio: { title: "商品创作", eyebrow: "PRODUCT CREATION", description: "上传商品图，生成多角度素材、模特试穿图和营销资产。", src: "/studio?embed=1" },
  competitors: { title: "竞品视觉分析", eyebrow: "COMPETITOR INTELLIGENCE", description: "拆解竞品视觉规律，形成原创差异化创作方案。", src: "/competitors?embed=1" },
  poster: { title: "AI 海报设计", eyebrow: "EDITABLE POSTER STUDIO", description: "在可编辑画布中调整商品、文案、颜色、尺寸和图层。", src: "/poster-editor?embed=1" },
  listing: { title: "多平台审核与上架", eyebrow: "LISTING ORCHESTRATION", description: "生成平台草稿，完成人工审核后执行幂等发布。", src: "/listing-workbench?embed=1" },
  performance: { title: "经营数据与 AI 优化", eyebrow: "PERFORMANCE FEEDBACK LOOP", description: "回流曝光、点击、转化、广告、退货和库存指标。", src: "/performance-insights?embed=1" },
  operations: { title: "订单、库存与履约", eyebrow: "COMMERCE OPERATIONS", description: "处理平台订单、库存证据、人工审批和履约执行。", src: "/dashboard?embed=1" },
  skills: { title: "Skill 插件中心", eyebrow: "EDITABLE SKILL REGISTRY", description: "创建、自动修订、启停并按需调用可插拔业务能力。" },
  services: { title: "外部服务中心", eyebrow: "EXTERNAL SERVICE ADAPTERS", description: "集中管理创作模型、电商平台、ERP 和审批接口。" },
};

function escapeHtml(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function splitCsv(value) {
  return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
}

let toastTimer;
function showToast(message, type = "success") {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.className = `shell-toast show${type === "error" ? " error" : ""}`;
  toastTimer = setTimeout(() => (elements.toast.className = "shell-toast"), 3200);
}

async function jsonRequest(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = Array.isArray(payload?.detail) ? payload.detail.map((item) => item.msg).join("，") : payload?.detail;
    throw new Error(detail || `请求失败：HTTP ${response.status}`);
  }
  return payload;
}

function switchView(view, updateHash = true) {
  if (!views[view]) view = "home";
  state.view = view;
  const meta = views[view];
  document.body.classList.toggle("home-mode", view === "home");
  if (view !== "home") document.body.classList.remove("chat-active");
  document.body.classList.toggle("frame-mode", Boolean(meta.src));
  elements.title.textContent = meta.title;
  elements.eyebrow.textContent = meta.eyebrow;
  elements.description.textContent = meta.description;
  elements.nav.forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  elements.home.classList.toggle("active", view === "home");
  elements.frameView.classList.toggle("active", Boolean(meta.src));
  elements.skillsView.classList.toggle("active", view === "skills");
  elements.servicesView.classList.toggle("active", view === "services");
  if (meta.src && state.frameSource !== meta.src) {
    state.frameSource = meta.src;
    elements.frame.src = meta.src;
  }
  if (view === "skills") loadSkills();
  if (view === "services") loadServices();
  if (updateHash && location.hash !== `#${view}`) history.pushState(null, "", `#${view}`);
}

elements.nav.forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
document.querySelectorAll("[data-open]").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.open)));
window.addEventListener("hashchange", () => switchView(location.hash.slice(1) || "home", false));
elements.refresh.addEventListener("click", () => {
  if (views[state.view].src) elements.frame.contentWindow.location.reload();
  else if (state.view === "skills") loadSkills();
  else if (state.view === "services") loadServices();
  else loadOverview();
  showToast("当前视图已刷新");
});
document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => {
  elements.command.value = button.dataset.prompt;
  elements.command.focus();
}));
elements.command.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.commandForm.requestSubmit();
  }
});
elements.command.addEventListener("focus", () => elements.commandForm.classList.remove("compact"));
elements.command.addEventListener("input", () => elements.commandForm.classList.remove("compact"));

const moduleSteps = {
  image: "调用通义万相生成图片",
  campaign: "调用 DeepSeek 生成营销文案",
  studio: "读取商品信息并生成创作任务",
  competitors: "分析竞品视觉并生成差异化 Brief",
  poster: "创建可编辑海报草稿",
  listing: "生成平台草稿并停在人工审核",
  performance: "读取经营指标并生成只读优化报告",
  operations: "读取订单与库存并生成运营建议",
};

function inferModules(prompt) {
  const candidates = [];
  if (/文生图|生图|生成图片|图片|主图|商品图|海报|poster/i.test(prompt)) candidates.push("image");
  if (/文案|小红书|抖音|种草|标题|卖点|营销/.test(prompt)) candidates.push("campaign");
  if (/多角度|模特|素材|试穿/.test(prompt)) candidates.push("studio");
  if (/竞品|对标/.test(prompt)) candidates.push("competitors");
  if (/上架|发布|listing/i.test(prompt)) candidates.push("listing");
  if (/数据|曝光|点击|转化|销量|roas|优化/i.test(prompt)) candidates.push("performance");
  if (/订单|库存|履约|补货/.test(prompt)) candidates.push("operations");
  return [...new Set(candidates.length ? candidates : ["campaign"])];
}

function isCasualChat(prompt) {
  const text = prompt.trim();
  if (/^(你好|您好|hello|hi|嗨|在吗|你是谁|你能做什么|怎么用|帮我介绍一下|介绍一下)$/i.test(text)) return true;
  return text.length <= 18 && !/生成|写|文案|图片|图|海报|主图|商品|小红书|抖音|竞品|上架|订单|库存|数据/.test(text);
}

function imagePayload(prompt) {
  return { prompt: `${prompt}。真实商业摄影质感，画面干净，主体清晰，不要文字，不要水印，不要 logo。`, size: "1280x1280", quality: "medium" };
}

function campaignPayload(prompt) {
  return {
    product: {
      sku: "AGENT-001",
      name: prompt.replace(/写|生成|文案|小红书|抖音|营销|卖点|标题/g, "").trim().slice(0, 60) || "智能商品",
      category: "电商商品",
      description: `用户希望围绕这个商品需求生成营销内容：${prompt}`,
      attributes: { 需求: prompt },
      target_audience: "电商目标消费者",
      price: null,
      image_urls: [],
    },
    brand_id: "demo-brand",
    platforms: ["xiaohongshu", "douyin"],
    tone: "friendly",
    objective: "新品种草与转化",
    forbidden_claims: ["全网最", "百分百", "治愈"],
  };
}

function appendChat(role, html) {
  const message = document.createElement("div");
  message.className = `chat-message ${role}`;
  message.innerHTML = `<div class="chat-avatar">${role === "user" ? "你" : "AI"}</div><div class="chat-bubble">${html}</div>`;
  elements.chatLog.append(message);
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
  return message;
}

function replaceChat(message, html) {
  message.querySelector(".chat-bubble").innerHTML = html;
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function streamChatText(message, text) {
  const bubble = message.querySelector(".chat-bubble");
  bubble.innerHTML = '<strong>MarketCraft Agent</strong><p class="typing-caret"></p>';
  const target = bubble.querySelector("p");
  let output = "";
  for (const char of text) {
    output += char;
    target.textContent = output;
    elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
    await wait(char === "，" || char === "。" ? 80 : 18);
  }
  target.classList.remove("typing-caret");
}

function bindResultButtons(scope) {
  scope.querySelectorAll("[data-open-result]").forEach((button) => button.addEventListener("click", (event) => switchView(event.currentTarget.dataset.openResult)));
}

function imageResultHtml(result) {
  const src = `data:${result.mime_type};base64,${result.image_base64}`;
  return `<strong>图片生成好了。</strong><p>${escapeHtml(result.model)} · ${escapeHtml(result.status)}</p><img src="${src}" alt="AI 生成图片" /><div class="chat-result-actions"><a href="${src}" download="marketcraft-agent-image.png">下载 PNG</a><button type="button" data-open-result="image">打开文生图窗口</button></div>`;
}

function campaignResultHtml(result) {
  return `<strong>文案生成好了。</strong><p>质量分 ${escapeHtml(result.quality_score)} · ${escapeHtml(result.status)}</p><div class="chat-copy-list"><div class="chat-copy-card"><span>商品卖点</span><p>${result.selling_points.map((item) => `• ${escapeHtml(item)}`).join("<br>")}</p></div>${result.copies.map((copy) => `<article class="chat-copy-card"><span>${escapeHtml(copy.platform)}</span><h4>${escapeHtml(copy.title)}</h4><p>${escapeHtml(copy.body)}</p><small>${copy.hashtags.map(escapeHtml).join(" ")}</small></article>`).join("")}</div><div class="chat-result-actions"><button type="button" data-open-result="campaign">打开营销文案窗口</button></div>`;
}

function openModuleHtml(module) {
  return `<strong>这个任务需要进入专业模块。</strong><p>${escapeHtml(moduleSteps[module] || "继续配置输入")}</p><div class="chat-result-actions"><button type="button" data-open-result="${module}">打开 ${escapeHtml(views[module]?.title || module)}</button></div>`;
}

function casualReplyHtml(prompt) {
  if (/你能做什么|怎么用|介绍/.test(prompt)) {
    return "我是 MarketCraft 的电商 Agent，擅长把商品创作任务拆开执行：可以帮你生成商品主图、写小红书和抖音文案、整理海报方向，也可以把任务交给左侧专业模块继续细调。";
  }
  return "我在。你可以把我当成一个电商创作搭子：闲聊可以，直接下任务也可以。比如“给一条裤子写小红书文案”，或者“生成一张手机电商主图”。";
}

elements.commandForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const prompt = elements.command.value.trim();
  if (!prompt) return;

  const button = elements.commandForm.querySelector("button[type='submit']");
  const modules = inferModules(prompt);
  document.body.classList.add("chat-active");
  elements.agentPlan.hidden = true;
  appendChat("user", `<p>${escapeHtml(prompt)}</p>`);
  const agentMessage = appendChat("agent", `<strong>收到，我来处理。</strong><p>${escapeHtml(moduleSteps[modules[0]] || "分析任务")}，完成后把结果发回这里。</p>`);
  elements.command.value = "";
  elements.command.blur();
  elements.commandForm.classList.add("compact");
  button.disabled = true;
  button.textContent = "■";

  try {
    if (isCasualChat(prompt)) {
      await streamChatText(agentMessage, casualReplyHtml(prompt));
    } else if (modules[0] === "image") {
      const result = await jsonRequest("/api/v1/posters/generate", { method: "POST", body: JSON.stringify(imagePayload(prompt)) });
      if (!result.image_base64) throw new Error("图片模型未返回图片数据");
      replaceChat(agentMessage, imageResultHtml(result));
    } else if (modules[0] === "campaign") {
      const result = await jsonRequest("/api/v1/campaigns/generate", {
        method: "POST",
        headers: { "X-Thread-ID": `agent-${Date.now()}` },
        body: JSON.stringify(campaignPayload(prompt)),
      });
      replaceChat(agentMessage, campaignResultHtml(result));
    } else {
      replaceChat(agentMessage, openModuleHtml(modules[0]));
    }
    bindResultButtons(agentMessage);
    showToast("Agent 已回复");
  } catch (error) {
    replaceChat(agentMessage, `<strong>这次执行失败了。</strong><p>${escapeHtml(error.message)}</p>`);
    showToast(error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "↑";
  }
});

async function loadOverview() {
  try {
    const [skills, services] = await Promise.all([jsonRequest("/api/v1/platform/skill-plugins"), jsonRequest("/api/v1/platform/external-services")]);
    state.skills = skills;
    state.services = services;
    updateCounts();
  } catch (error) {
    showToast(error.message, "error");
  }
}

function updateCounts() {
  elements.skillNavCount.textContent = state.skills.length;
  elements.serviceNavCount.textContent = state.services.length;
  if (elements.homeSkillCount) elements.homeSkillCount.textContent = state.skills.length;
  if (elements.homeServiceCount) elements.homeServiceCount.textContent = state.services.length;
}

async function loadSkills() {
  try {
    state.skills = await jsonRequest("/api/v1/platform/skill-plugins");
    updateCounts();
    renderSkills();
  } catch (error) {
    showToast(error.message, "error");
  }
}

function renderSkills() {
  const query = elements.skillSearch.value.trim().toLowerCase();
  const skills = state.skills.filter((item) => JSON.stringify(item).toLowerCase().includes(query));
  elements.skillStatus.textContent = `${skills.length} 个可用清单 · ${state.skills.filter((item) => item.status === "enabled").length} 个已启用`;
  elements.skillCatalog.innerHTML = skills.map((item) => `<article class="skill-card"><div class="skill-head"><div class="skill-symbol">S</div><div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.plugin_id)} · v${escapeHtml(item.version)} · ${item.built_in ? "BUILT-IN" : "CUSTOM"}</small></div><span class="state-tag ${item.status}">${item.status.toUpperCase()}</span></div><p>${escapeHtml(item.description)}</p><div class="tag-row">${item.capabilities.slice(0, 4).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div><div class="skill-actions">${item.editable ? `<button data-action="auto-edit" data-id="${item.plugin_id}">自动编辑</button><button data-action="toggle" data-id="${item.plugin_id}" data-status="${item.status === "enabled" ? "disabled" : "enabled"}">${item.status === "enabled" ? "停用" : "启用"}</button>` : '<span class="locked-note">内置 Skill 由代码版本维护</span>'}${item.status === "enabled" ? `<button class="primary-action" data-action="invoke" data-id="${item.plugin_id}">测试调用</button>` : ""}</div></article>`).join("") || '<p class="locked-note">没有匹配的 Skill。</p>';
}

elements.skillSearch.addEventListener("input", renderSkills);
elements.skillCatalog.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = button.dataset.id;
  try {
    if (button.dataset.action === "auto-edit") {
      const change = window.prompt("输入希望自动修改的要求。修改后 Skill 会回到草稿态：", "增加对低库存风险的判断，并要求所有建议携带数字证据");
      if (!change) return;
      await jsonRequest(`/api/v1/platform/skill-plugins/${id}/auto-edit`, { method: "POST", body: JSON.stringify({ change_request: change, actor: "skill-ai-editor" }) });
      showToast("Skill 已生成修订版本，请检查后重新启用");
      await loadSkills();
    } else if (button.dataset.action === "toggle") {
      await jsonRequest(`/api/v1/platform/skill-plugins/${id}/status`, { method: "POST", body: JSON.stringify({ status: button.dataset.status, actor: "skill-admin" }) });
      showToast(`Skill 已${button.dataset.status === "enabled" ? "启用" : "停用"}`);
      await loadSkills();
    } else {
      const prompt = window.prompt("输入测试调用指令：", "分析这个商品的数据并给出优化建议");
      if (!prompt) return;
      const plan = await jsonRequest(`/api/v1/platform/skill-plugins/${id}/invoke`, { method: "POST", body: JSON.stringify({ prompt, actor: "workspace-user" }) });
      elements.skillPlan.hidden = false;
      elements.skillPlan.innerHTML = `<div class="shell-eyebrow">INVOCATION PLAN · MOCK</div><h3>${escapeHtml(plan.plugin_id)} 已生成调用计划</h3><p>能力：${plan.capabilities.map(escapeHtml).join("，")} · ${plan.approval_required ? "执行前需要人工审核" : "只读计划"}</p><code>${escapeHtml(plan.planned_tools.join(" → ") || "未绑定工具，仅输出规划")}</code>`;
      elements.skillPlan.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  } catch (error) {
    showToast(error.message, "error");
  }
});

elements.skillForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = elements.skillForm.elements;
  try {
    await jsonRequest("/api/v1/platform/skill-plugins", {
      method: "POST",
      body: JSON.stringify({
        plugin_id: form.pluginId.value.trim(),
        name: form.name.value.trim(),
        description: form.description.value.trim(),
        instructions: form.instructions.value.trim(),
        triggers: splitCsv(form.triggers.value),
        capabilities: splitCsv(form.capabilities.value),
        tool_bindings: splitCsv(form.tools.value),
        risk_level: form.risk.value,
        actor: "skill-designer",
      }),
    });
    showToast("自定义 Skill 草稿已创建");
    await loadSkills();
  } catch (error) {
    showToast(error.message, "error");
  }
});

async function loadServices() {
  try {
    state.services = await jsonRequest("/api/v1/platform/external-services");
    updateCounts();
    renderServices();
  } catch (error) {
    showToast(error.message, "error");
  }
}

function renderServices() {
  elements.serviceCatalog.innerHTML = state.services.map((item) => `<article class="service-card"><div class="service-head"><div class="service-symbol">API</div><div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.service_id)} · ${item.kind}</small></div><span class="state-tag ${item.status}">${item.mode.toUpperCase()} · ${item.status.replaceAll("_", " ").toUpperCase()}</span></div><p>${escapeHtml(item.description)}</p><div class="tag-row">${item.capabilities.slice(0, 4).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div><div class="service-meta"><div><small>BASE URL</small><strong>${escapeHtml(item.base_url || "内置 Mock")}</strong></div><div><small>SECRET</small><strong>${escapeHtml(item.secret_reference || "不需要")}</strong></div></div><div class="service-actions"><button data-health="${item.service_id}">检查连接</button>${item.built_in ? '<span class="locked-note">内置适配器</span>' : ""}</div></article>`).join("");
}

elements.serviceCatalog.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-health]");
  if (!button) return;
  try {
    const result = await jsonRequest(`/api/v1/platform/external-services/${button.dataset.health}/health`, { method: "POST" });
    showToast(result.message, result.checked ? "success" : "error");
  } catch (error) {
    showToast(error.message, "error");
  }
});

elements.serviceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = elements.serviceForm.elements;
  try {
    await jsonRequest("/api/v1/platform/external-services", {
      method: "POST",
      body: JSON.stringify({
        service_id: form.serviceId.value.trim(),
        name: form.name.value.trim(),
        kind: form.kind.value,
        description: form.description.value.trim(),
        base_url: form.baseUrl.value.trim() || null,
        auth_type: form.auth.value,
        secret_reference: form.secretRef.value.trim() || null,
        capabilities: splitCsv(form.capabilities.value),
        mode: form.mode.value,
        actor: "integration-admin",
      }),
    });
    showToast("外部服务适配器已注册");
    await loadServices();
  } catch (error) {
    showToast(error.message, "error");
  }
});

switchView(location.hash.slice(1) || "home", false);
loadOverview();
