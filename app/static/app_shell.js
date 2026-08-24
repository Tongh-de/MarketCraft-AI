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
  if (/\u8fd9\u4e2a\u6708.*\u7a7f|\u7a7f\u4ec0\u4e48|\u7a7f\u642d|\u642d\u914d|\u9002\u5408\u7a7f|ootd|outfit/i.test(prompt)) candidates.push("outfit");
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
  return text.length <= 18 && !/生成|写|文案|图片|图|海报|主图|商品|小红书|抖音|竞品|上架|订单|库存|数据|穿搭|穿什么|搭配/.test(text);
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


const agentSkills = {
  outfit: {
    label: "\u672c\u6708\u7a7f\u642d\u5efa\u8bae Skill",
    badge: "OUTFIT ADVISOR",
    steps: [
      "\u8bc6\u522b\u6708\u4efd\u548c\u573a\u666f",
      "\u5224\u65ad\u5b63\u8282\u548c\u4f53\u611f",
      "\u6574\u7406\u5355\u54c1\u548c\u642d\u914d",
      "\u8f93\u51fa\u5546\u54c1\u673a\u4f1a",
    ],
  },
  image: {
    label: "\u6587\u751f\u56fe Skill",
    badge: "TEXT TO IMAGE",
    steps: [
      "\u7406\u89e3\u56fe\u7247\u9700\u6c42\u548c\u7535\u5546\u573a\u666f",
      "\u6574\u7406\u7ed9\u901a\u4e49\u4e07\u76f8\u7684\u63d0\u793a\u8bcd",
      "\u8c03\u7528\u6587\u751f\u56fe API",
      "\u68c0\u67e5\u56fe\u7247\u6570\u636e\u5e76\u8fd4\u56de\u7ed3\u679c",
    ],
  },
  campaign: {
    label: "\u8425\u9500\u6587\u6848 Skill",
    badge: "COPY GENERATION",
    steps: [
      "\u8bc6\u522b\u5546\u54c1\u3001\u573a\u666f\u548c\u5e73\u53f0\u8bed\u6c14",
      "\u7ec4\u88c5\u5546\u54c1\u8d44\u6599\u548c\u7981\u7528\u8bdd\u672f",
      "\u8c03\u7528\u771f\u5b9e\u6587\u6848\u6a21\u578b",
      "\u68c0\u67e5\u5356\u70b9\u3001\u8d28\u91cf\u5206\u548c\u5e73\u53f0\u6587\u6848",
    ],
  },
  studio: {
    label: "\u5546\u54c1\u521b\u4f5c Skill",
    badge: "PRODUCT CREATION",
    steps: [
      "\u8bc6\u522b\u5546\u54c1\u7d20\u6750\u9700\u6c42",
      "\u5224\u65ad\u9700\u8981\u56fe\u7247\u4e0a\u4f20\u548c\u4efb\u52a1\u8868\u5355",
      "\u51c6\u5907\u8fdb\u5165\u5546\u54c1\u521b\u4f5c\u6a21\u5757",
    ],
  },
  competitors: {
    label: "\u7ade\u54c1\u5206\u6790 Skill",
    badge: "COMPETITOR",
    steps: [
      "\u8bc6\u522b\u7ade\u54c1\u548c\u5bf9\u6807\u9700\u6c42",
      "\u51c6\u5907\u8fdb\u5165\u7ade\u54c1\u89c6\u89c9\u5206\u6790\u6a21\u5757",
    ],
  },
  poster: {
    label: "\u6d77\u62a5\u8bbe\u8ba1 Skill",
    badge: "POSTER",
    steps: [
      "\u8bc6\u522b\u6d77\u62a5\u573a\u666f\u548c\u5546\u54c1\u4e3b\u4f53",
      "\u51c6\u5907\u8fdb\u5165\u53ef\u7f16\u8f91\u6d77\u62a5\u5de5\u4f5c\u53f0",
    ],
  },
  listing: {
    label: "\u4e0a\u67b6\u5ba1\u6838 Skill",
    badge: "LISTING",
    steps: [
      "\u8bc6\u522b\u5e73\u53f0\u4e0a\u67b6\u9700\u6c42",
      "\u51c6\u5907\u8fdb\u5165\u5ba1\u6838\u4e0e\u4e0a\u67b6\u6a21\u5757",
    ],
  },
  performance: {
    label: "\u7ecf\u8425\u4f18\u5316 Skill",
    badge: "PERFORMANCE",
    steps: [
      "\u8bc6\u522b\u7ecf\u8425\u6570\u636e\u548c\u4f18\u5316\u95ee\u9898",
      "\u51c6\u5907\u8fdb\u5165\u7ecf\u8425\u4f18\u5316\u6a21\u5757",
    ],
  },
  operations: {
    label: "\u8ba2\u5355\u5e93\u5b58 Skill",
    badge: "OPERATIONS",
    steps: [
      "\u8bc6\u522b\u8ba2\u5355\u3001\u5e93\u5b58\u6216\u5c65\u7ea6\u9700\u6c42",
      "\u51c6\u5907\u8fdb\u5165\u8fd0\u8425\u63a7\u5236\u53f0",
    ],
  },
};

function intentLabel(module) {
  return agentSkills[module]?.label || "\u901a\u7528\u7535\u5546 Agent";
}

function traceHtml(module, activeIndex = 0, done = false) {
  const skill = agentSkills[module] || agentSkills.campaign;
  return `<div class="agent-trace-card"><div class="agent-trace-head"><span>${escapeHtml(skill.badge)}</span><strong>${escapeHtml(skill.label)}</strong></div><ol>${skill.steps.map((step, index) => {
    const status = done || index < activeIndex ? "done" : index === activeIndex ? "running" : "pending";
    return `<li class="${status}"><i></i><span>${escapeHtml(step)}</span></li>`;
  }).join("")}</ol></div>`;
}

function workingHtml(module, note) {
  return `<strong>${escapeHtml(intentLabel(module))}</strong><p>${escapeHtml(note)}</p>${traceHtml(module, 0)}`;
}

async function runTrace(message, module, beforeCallIndex) {
  const skill = agentSkills[module] || agentSkills.campaign;
  for (let index = 0; index <= beforeCallIndex; index += 1) {
    replaceChat(message, `<strong>${escapeHtml(skill.label)}</strong><p>${escapeHtml(skill.steps[index] || "\u6b63\u5728\u6267\u884c")}</p>${traceHtml(module, index)}`);
    await wait(420);
  }
}

async function revealFinalHtml(message, module, html) {
  replaceChat(message, `${traceHtml(module, 999, true)}<div class="agent-final-result revealing">${html}</div>`);
  await wait(120);
  const result = message.querySelector(".agent-final-result");
  if (result) result.classList.remove("revealing");
}

function outfitAdviceHtml(prompt) {
  const month = new Intl.DateTimeFormat("zh-CN", { month: "long" })
    .format(new Date());
  const office = /\u901a\u52e4|\u4e0a\u73ed|office|\u804c\u573a/i.test(prompt);
  const travel = /\u65c5\u884c|\u51fa\u6e38|\u6237\u5916|\u5468\u672b/i.test(prompt);
  const scene = office ? "\u901a\u52e4" : travel ? "\u51fa\u6e38" : "\u65e5\u5e38";
  const items = office
    ? ["\u8f7b\u8584\u9488\u7ec7\u886b", "\u76f4\u7b52\u88e4", "\u8584\u5916\u5957"]
    : travel
      ? ["\u9632\u6652\u5916\u5957", "\u901f\u5e72 T \u6064", "\u5bbd\u677e\u957f\u88e4"]
      : ["\u900f\u6c14\u4e0a\u8863", "\u5bbd\u677e\u88e4\u88c5", "\u8584\u5f00\u886b"];
  const combos = office
    ? ["\u886c\u886b + \u9614\u817f\u88e4 + \u8584\u897f\u88c5", "\u9488\u7ec7\u77ed\u8896 + \u76f4\u7b52\u88e4"]
    : travel
      ? ["\u901f\u5e72 T \u6064 + \u9632\u6652\u5916\u5957", "\u8f7b\u8584\u886c\u886b + \u5de5\u88c5\u88e4"]
      : ["\u900f\u6c14\u4e0a\u8863 + \u5bbd\u677e\u88e4\u88c5", "\u8584\u5f00\u886b + \u57fa\u7840\u5185\u642d"];
  const commerce = [
    "\u5173\u952e\u8bcd\uff1a\u8f7b\u8584\u3001\u900f\u6c14\u3001\u663e\u7626\u3002",
    "\u5185\u5bb9\uff1a\u7528\u2018\u672c\u6708\u4e0d\u77e5\u9053\u7a7f\u4ec0\u4e48\u2019\u5207\u5165\u3002",
    "\u7ec4\u5408\uff1a\u4e0a\u8863 + \u4e0b\u88c5 + \u8584\u5916\u5957\u3002",
  ];
  return `<strong>${month}${scene}\u7a7f\u642d\u5efa\u8bae</strong>` +
    `<p>\u5df2\u89e6\u53d1\u300c\u672c\u6708\u7a7f\u642d\u5efa\u8bae Skill\u300d\u3002</p>` +
    `<div class="chat-copy-list">` +
    `<article class="chat-copy-card"><span>\u63a8\u8350\u5355\u54c1</span><p>` +
    `${items.map((x) => `? ${escapeHtml(x)}`).join("<br>")}` +
    `</p></article><article class="chat-copy-card">` +
    `<span>\u642d\u914d\u65b9\u6848</span><p>` +
    `${combos.map((x) => `? ${escapeHtml(x)}`).join("<br>")}` +
    `</p></article><article class="chat-copy-card">` +
    `<span>\u7535\u5546\u673a\u4f1a\u70b9</span><p>` +
    `${commerce.map((x) => `? ${escapeHtml(x)}`).join("<br>")}` +
    `</p></article></div>`;
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
  const module = modules[0];
  document.body.classList.add("chat-active");
  elements.agentPlan.hidden = true;
  appendChat("user", `<p>${escapeHtml(prompt)}</p>`);
  const agentMessage = appendChat(
    "agent",
    workingHtml(module, "\u6211\u5148\u5224\u65ad\u4efb\u52a1\u7c7b\u578b\uff0c\u7136\u540e\u9009\u62e9\u5408\u9002\u7684 Skill\u3002")
  );
  elements.command.value = "";
  elements.command.blur();
  elements.commandForm.classList.add("compact");
  button.disabled = true;
  button.textContent = "\u25a0";

  try {
    if (isCasualChat(prompt)) {
      await streamChatText(agentMessage, casualReplyHtml(prompt));
    } else if (module === "outfit") {
      await runTrace(agentMessage, module, 3);
      await revealFinalHtml(agentMessage, module, outfitAdviceHtml(prompt));
    } else if (module === "image") {
      await runTrace(agentMessage, module, 2);
      const result = await jsonRequest("/api/v1/posters/generate", {
        method: "POST",
        body: JSON.stringify(imagePayload(prompt)),
      });
      if (!result.image_base64) throw new Error("\u56fe\u7247\u6a21\u578b\u672a\u8fd4\u56de\u56fe\u7247\u6570\u636e");
      replaceChat(agentMessage, `<strong>${escapeHtml(intentLabel(module))}</strong><p>\u6b63\u5728\u68c0\u67e5\u751f\u6210\u7ed3\u679c\u5e76\u7ec4\u88c5\u56fe\u7247\u5361\u7247\u3002</p>${traceHtml(module, 3)}`);
      await wait(360);
      await revealFinalHtml(agentMessage, module, imageResultHtml(result));
    } else if (module === "campaign") {
      await runTrace(agentMessage, module, 2);
      const result = await jsonRequest("/api/v1/campaigns/generate", {
        method: "POST",
        headers: { "X-Thread-ID": `agent-${Date.now()}` },
        body: JSON.stringify(campaignPayload(prompt)),
      });
      replaceChat(agentMessage, `<strong>${escapeHtml(intentLabel(module))}</strong><p>\u6b63\u5728\u68c0\u67e5\u5356\u70b9\u3001\u5e73\u53f0\u6587\u6848\u548c\u8d28\u91cf\u5206\u3002</p>${traceHtml(module, 3)}`);
      await wait(360);
      await revealFinalHtml(agentMessage, module, campaignResultHtml(result));
    } else {
      await runTrace(agentMessage, module, (agentSkills[module]?.steps.length || 1) - 1);
      await revealFinalHtml(agentMessage, module, openModuleHtml(module));
    }
    bindResultButtons(agentMessage);
    showToast("Agent \u5df2\u56de\u590d");
  } catch (error) {
    replaceChat(agentMessage, `<strong>\u8fd9\u6b21\u6267\u884c\u5931\u8d25\u4e86\u3002</strong><p>${escapeHtml(error.message)}</p>${traceHtml(module, 999, true)}`);
    showToast(error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "\u2191";
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
