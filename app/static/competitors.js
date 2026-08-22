const state = { ownUrl: null, competitorUrls: [] };
const $ = (selector) => document.querySelector(selector);
const elements = {
  form: $("#competitorForm"), own: $("#ownImage"), ownPreview: $("#ownPreview"),
  ownPlaceholder: $("#ownPlaceholder"), competitors: $("#competitorImages"),
  previews: $("#competitorPreviews"), button: $("#analyzeButton"), status: $("#reportStatus"),
  empty: $("#reportEmpty"), content: $("#reportContent"), warning: $("#mockWarning"),
  summary: $("#reportSummary"), dimensions: $("#dimensionBody"), opportunities: $("#opportunityList"),
  briefsPanel: $("#briefs"), briefs: $("#briefGrid"), compliance: $("#complianceList"),
  trace: $("#analysisTrace"), toast: $("#toast"),
};
function escapeHtml(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;"); }
let toastTimer;
function showToast(message, type = "success") { clearTimeout(toastTimer); elements.toast.textContent = message; elements.toast.className = `toast show${type === "error" ? " error" : ""}`; toastTimer = setTimeout(() => { elements.toast.className = "toast"; }, 3200); }
async function jsonRequest(path, options = {}) { const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } }); const payload = await response.json().catch(() => null); if (!response.ok) throw new Error(payload?.detail || `请求失败：HTTP ${response.status}`); return payload; }
async function uploadImage(file) { const form = new FormData(); form.append("file", file); const response = await fetch("/api/v1/creation/uploads", { method: "POST", body: form }); const payload = await response.json().catch(() => null); if (!response.ok) throw new Error(payload?.detail || `图片上传失败：HTTP ${response.status}`); return payload; }

elements.own.addEventListener("change", () => {
  const file = elements.own.files[0]; if (!file) return;
  if (state.ownUrl) URL.revokeObjectURL(state.ownUrl); state.ownUrl = URL.createObjectURL(file);
  elements.ownPreview.src = state.ownUrl; elements.ownPreview.hidden = false; elements.ownPlaceholder.hidden = true;
});
elements.competitors.addEventListener("change", () => {
  state.competitorUrls.forEach((url) => URL.revokeObjectURL(url)); state.competitorUrls = [];
  const files = [...elements.competitors.files].slice(0, 8);
  if (elements.competitors.files.length > 8) showToast("最多分析 8 张竞品图片", "error");
  elements.previews.innerHTML = files.map((file) => { const url = URL.createObjectURL(file); state.competitorUrls.push(url); return `<img src="${url}" alt="${escapeHtml(file.name)}" title="${escapeHtml(file.name)}" />`; }).join("");
});

function renderReport(report) {
  elements.status.textContent = report.status === "completed" ? "分析完成" : report.status;
  elements.empty.hidden = true; elements.content.hidden = false; elements.briefsPanel.hidden = false;
  elements.warning.textContent = report.mock ? "MOCK 边界：本报告尚未通过真实多模态模型读取图片像素，所有视觉规律均为演示假设。" : "LIVE：报告由真实视觉模型生成，仍需人工复核。";
  elements.summary.innerHTML = `<strong>${escapeHtml(report.product.name)}</strong><br>${escapeHtml(report.summary)}`;
  elements.dimensions.innerHTML = report.dimensions.map((item) => `<tr><td>${escapeHtml(item.dimension)}<br><small>置信度 ${Math.round(item.confidence * 100)}%</small></td><td>${escapeHtml(item.competitor_pattern)}</td><td>${escapeHtml(item.own_product_gap)}</td><td>${escapeHtml(item.recommendation)}</td></tr>`).join("");
  elements.opportunities.innerHTML = report.opportunities.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  elements.briefs.innerHTML = report.creative_briefs.map((brief) => `<article class="brief-card"><h3>${escapeHtml(brief.name)}</h3><dl><div><dt>视觉方向</dt><dd>${escapeHtml(brief.visual_direction)}</dd></div><div><dt>构图</dt><dd>${escapeHtml(brief.composition)}</dd></div><div><dt>文案角度</dt><dd>${escapeHtml(brief.copy_angle)}</dd></div><div><dt>差异点</dt><dd>${escapeHtml(brief.differentiation)}</dd></div></dl></article>`).join("");
  elements.compliance.innerHTML = report.compliance_notes.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  elements.trace.innerHTML = report.trace.map((item) => `<li>${escapeHtml(item.replaceAll("_", " "))}</li>`).join("");
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault(); const ownFile = elements.own.files[0]; const competitorFiles = [...elements.competitors.files].slice(0, 8);
  if (!ownFile || !competitorFiles.length) return showToast("请上传自己的商品图和至少一张竞品图", "error");
  elements.button.disabled = true; elements.button.textContent = "正在上传并分析…"; elements.status.textContent = "分析中";
  const form = new FormData(elements.form);
  try {
    const [ownUpload, competitorUploads] = await Promise.all([uploadImage(ownFile), Promise.all(competitorFiles.map(uploadImage))]);
    const report = await jsonRequest("/api/v1/creation/competitor-analyses", { method: "POST", body: JSON.stringify({
      product: { sku: form.get("sku").trim(), name: form.get("name").trim(), category: form.get("category").trim(), source_image_url: ownUpload.url, target_audience: form.get("audience").trim() },
      competitor_images: competitorUploads.map((item, index) => ({ label: `竞品 ${index + 1}`, image_url: item.url })),
      instruction: form.get("instruction").trim(), preferred_plugin_id: "multimodal-vision.mock", actor: "creative-strategist",
    }) });
    renderReport(report); if (report.status === "failed") throw new Error(report.error || "竞品分析失败");
    showToast("竞品对标报告已生成"); $("#report").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) { elements.status.textContent = "分析失败"; showToast(error.message, "error"); }
  finally { elements.button.disabled = false; elements.button.textContent = "◉ 开始竞品分析"; }
});
