const $ = (selector) => document.querySelector(selector);
const elements = {
  form: $("#campaignForm"),
  button: $("#generateCampaign"),
  status: $("#campaignStatus"),
  empty: $("#emptyCampaign"),
  output: $("#campaignOutput"),
  toast: $("#toast"),
};

let toastTimer;
function showToast(message, type = "success") {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.className = `toast show${type === "error" ? " error" : ""}`;
  toastTimer = setTimeout(() => (elements.toast.className = "toast"), 3200);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function parseAttributes(value) {
  return Object.fromEntries(
    value
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [key, ...rest] = line.split(/[=：:]/);
        return [key.trim(), rest.join("=").trim()];
      })
      .filter(([key, content]) => key && content),
  );
}

function campaignPayload() {
  const form = elements.form.elements;
  const platforms = [...elements.form.querySelectorAll('input[name="platform"]:checked')].map(
    (item) => item.value,
  );
  return {
    product: {
      sku: form.sku.value.trim(),
      name: form.name.value.trim(),
      category: form.category.value.trim(),
      description: form.description.value.trim(),
      attributes: parseAttributes(form.attributes.value),
      target_audience: form.audience.value.trim(),
      price: form.price.value ? Number(form.price.value) : null,
      image_urls: [],
    },
    brand_id: "demo-brand",
    platforms,
    tone: "friendly",
    objective: "新品种草与转化",
    forbidden_claims: ["全网最低", "百分百", "治愈"],
  };
}

async function jsonRequest(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = Array.isArray(payload?.detail)
      ? payload.detail.map((item) => item.msg).join("；")
      : payload?.detail;
    throw new Error(detail || `请求失败：HTTP ${response.status}`);
  }
  return payload;
}

function renderCampaign(result) {
  elements.empty.hidden = true;
  elements.output.hidden = false;
  elements.status.textContent = `${result.status} · ${result.quality_score}分`;
  elements.output.innerHTML = `
    <section class="result-block">
      <h3>商品卖点</h3>
      <ul>${result.selling_points.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </section>
    ${result.copies
      .map(
        (copy) => `
      <article class="copy-card">
        <h3>${escapeHtml(copy.platform)}</h3>
        <h4>${escapeHtml(copy.title)}</h4>
        <p>${escapeHtml(copy.body)}</p>
        <div class="tag-row">${copy.hashtags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
        <p><strong>CTA：</strong>${escapeHtml(copy.call_to_action)}</p>
      </article>`,
      )
      .join("")}
    <section class="result-block">
      <h3>海报 Prompt</h3>
      <p class="trace-row">${escapeHtml(result.poster_prompt)}</p>
    </section>
    <section class="result-block">
      <h3>执行轨迹</h3>
      <p class="trace-row">${result.trace.map(escapeHtml).join(" → ")}</p>
    </section>
  `;
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.button.disabled = true;
  elements.button.textContent = "正在调用模型…";
  elements.status.textContent = "生成中";
  try {
    const result = await jsonRequest("/api/v1/campaigns/generate", {
      method: "POST",
      headers: { "X-Thread-ID": `campaign-ui-${Date.now()}` },
      body: JSON.stringify(campaignPayload()),
    });
    renderCampaign(result);
    showToast("营销文案已生成");
  } catch (error) {
    elements.status.textContent = "生成失败";
    showToast(error.message, "error");
  } finally {
    elements.button.disabled = false;
    elements.button.textContent = "✎ 生成营销文案";
  }
});
