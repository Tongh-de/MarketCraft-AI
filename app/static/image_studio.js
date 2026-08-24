const $ = (selector) => document.querySelector(selector);
const elements = {
  form: $("#imageForm"),
  prompt: document.querySelector('[name="prompt"]'),
  button: $("#generateImage"),
  status: $("#imageStatus"),
  empty: $("#emptyImage"),
  image: $("#resultImage"),
  download: $("#downloadImage"),
  trace: $("#imageTrace"),
  toast: $("#toast"),
};

let toastTimer;
function showToast(message, type = "success") {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.className = `toast show${type === "error" ? " error" : ""}`;
  toastTimer = setTimeout(() => (elements.toast.className = "toast"), 3200);
}

async function jsonRequest(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.detail || `请求失败：HTTP ${response.status}`);
  }
  return payload;
}

const traceLabels = {
  prepare: "准备提示词、尺寸和质量参数",
  request: "POST /api/v1/posters/generate",
  submit: "后端提交通义万相异步生图任务",
  poll: "后端轮询任务状态，等待图片完成",
  image: "读取图片 URL 并转换为 Base64",
  render: "浏览器渲染生成图片并启用下载",
};

function setTrace(items) {
  elements.trace.innerHTML = items
    .map((item) => `<li class="${item.status}">${item.label}</li>`)
    .join("");
}

document.querySelectorAll("[data-prompt]").forEach((button) =>
  button.addEventListener("click", () => {
    elements.prompt.value = button.dataset.prompt;
    elements.prompt.focus();
  }),
);

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = elements.form.elements;
  const startedAt = performance.now();
  elements.button.disabled = true;
  elements.button.textContent = "正在生成…";
  elements.status.textContent = "生成中";
  setTrace([
    { status: "done", label: traceLabels.prepare },
    { status: "running", label: traceLabels.request },
    { status: "pending", label: traceLabels.submit },
    { status: "pending", label: traceLabels.poll },
    { status: "pending", label: traceLabels.image },
    { status: "pending", label: traceLabels.render },
  ]);
  try {
    const result = await jsonRequest("/api/v1/posters/generate", {
      method: "POST",
      body: JSON.stringify({
        prompt: form.prompt.value.trim(),
        size: form.size.value,
        quality: form.quality.value,
      }),
    });
    if (!result.image_base64) throw new Error("图片模型未返回图片数据");
    setTrace([
      { status: "done", label: traceLabels.prepare },
      { status: "done", label: traceLabels.request },
      { status: "done", label: `${traceLabels.submit} · ${result.model}` },
      { status: "done", label: traceLabels.poll },
      { status: "done", label: traceLabels.image },
      { status: "running", label: traceLabels.render },
    ]);
    const src = `data:${result.mime_type};base64,${result.image_base64}`;
    elements.image.src = src;
    elements.image.hidden = false;
    elements.empty.hidden = true;
    elements.download.href = src;
    elements.download.download = `marketcraft-image-${Date.now()}.png`;
    elements.download.classList.remove("disabled");
    const elapsed = ((performance.now() - startedAt) / 1000).toFixed(1);
    elements.status.textContent = `${result.model} · ${result.status} · ${elapsed}s`;
    setTrace([
      { status: "done", label: traceLabels.prepare },
      { status: "done", label: traceLabels.request },
      { status: "done", label: `${traceLabels.submit} · ${result.model}` },
      { status: "done", label: traceLabels.poll },
      { status: "done", label: traceLabels.image },
      { status: "done", label: `${traceLabels.render} · ${elapsed}s` },
    ]);
    showToast("图片已生成");
  } catch (error) {
    elements.status.textContent = "生成失败";
    setTrace([
      { status: "done", label: traceLabels.prepare },
      { status: "failed", label: error.message },
    ]);
    showToast(error.message, "error");
  } finally {
    elements.button.disabled = false;
    elements.button.textContent = "生成图片";
  }
});
