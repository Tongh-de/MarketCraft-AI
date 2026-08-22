# MarketCraft AI

面向跨境电商运营团队的自动化 Agent 平台。系统同时覆盖营销内容生产，以及 Amazon/TikTok Shop 订单、ERP 库存、履约和补货的跨系统协作流程。

当前版本已完成七个阶段：除多模态生成、品牌 RAG、内容审批和发布外，已加入订单导入、库存校验、补货/履约决策、四眼审批、幂等执行、异常隔离和运营管理控制台。默认使用内存存储与 Mock 外部系统，无需凭证即可演示；所有模拟外部 ID 均带有 `mock-` 前缀。

## Product preview

| 运营总览 | 四眼审批 |
| --- | --- |
| ![运营控制台总览](docs/assets/dashboard-preview.svg) | ![订单人工审批](docs/assets/approval-preview.svg) |
| **库存异常与补货** | **执行结果与审计** |
| ![库存不足与补货决策](docs/assets/restock-preview.svg) | ![外部系统执行结果](docs/assets/execution-preview.svg) |

## Core workflow

```mermaid
flowchart LR
    A[商品输入] --> B[卖点提取]
    B --> C[品牌检索]
    C --> D[内容生成]
    D --> E[质量审核]
    E --> F[营销内容包]
```

```mermaid
flowchart LR
    A[平台订单] --> B[ERP 库存]
    B --> C[Agent 决策]
    C --> D[人工审核]
    D --> E[履约或补货]
```

## Current capabilities

- FastAPI 版本化接口和 Pydantic 参数校验
- LangGraph 状态工作流、线程 ID 和 Checkpoint（检查点）
- 小红书、抖音、淘宝、京东平台文案结构
- 品牌语气与品类规则检索接口
- 禁用词、绝对化表述、标题长度和可读性检查
- 完整节点执行轨迹，方便评测、排错和面试演示
- Mock 模式、自动化测试、Docker 镜像与健康检查
- 多模态商品图片分析，输出视觉优势、风险、布局建议和置信度
- OpenAI Responses API + Pydantic Structured Outputs（结构化输出）
- 独立海报生成接口，可接收 GPT Image 返回的 Base64 PNG
- 品牌知识文档增量写入和品牌、品类元数据过滤
- BM25 关键词召回＋Dense 向量召回＋RRF 排名融合
- Milvus 原生 BM25 与多向量混合检索生产适配器
- 商品目录的新增、更新、版本号和搜索接口
- 生成结果携带文档 ID、来源和融合分数，支持引用溯源
- Draft → Pending Review → Approved/Rejected → Published 审批状态机
- 四眼原则：审核人与内容提交人必须不同
- 内容修改生成不可变版本，重新审核后才能发布
- 发布幂等键、单平台错误隔离和 Partial Failed（部分失败）状态
- 小红书、抖音、淘宝、京东发布适配器接口及确定性 Mock 实现
- 追加式审计日志，记录操作者、动作、版本和审核理由
- 可切换的内存或 SQLAlchemy 状态存储，兼容 SQLite 与 PostgreSQL
- 可切换的内存或 Redis 发布幂等存储，并配置结果 TTL
- Prometheus HTTP 与业务指标，暴露于 `/metrics`
- 版本化 RAG 回归集，计算 Recall@K、MRR 和引用覆盖率
- CI 自动执行单元测试、Ruff 检查和 RAG 回归评测
- Amazon、TikTok Shop 统一订单网关，可替换官方 API 适配器
- ERP 库存查询、库存预占和补货任务接口
- LangGraph 订单工作流：校验 → 查库存 → 决策 → 人工复核
- 库存充足时生成履约方案，库存不足时阻断履约并生成补货方案
- 外部写操作四眼审批、订单级幂等、步骤级失败隔离和审计日志
- 飞书审批通知接口及确定性 Mock 实现
- 响应式运营控制台，集中展示订单、库存证据、风险、审批和执行轨迹

## Quick start

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

打开 `http://localhost:8000/dashboard` 进入运营控制台；`http://localhost:8000/docs` 提供接口文档，也可运行 `examples.http` 中的示例请求。

控制台右侧表单可以一键完成：

1. 写入 Mock ERP 库存；
2. 写入 Amazon/TikTok Shop Mock 订单；
3. 由 Agent 拉取订单并生成履约或补货建议；
4. 在详情区批准、拒绝或执行外部操作。

```bash
pytest
ruff check app scripts tests
python -m scripts.evaluate_rag --top-k 1
```

Docker 启动：

```bash
cp .env.example .env
docker compose up --build
```

## API

`POST /api/v1/campaigns/generate`

输入包含商品 SKU、名称、品类、描述、结构化属性、目标用户、平台与品牌 ID。输出包含：

- 可追溯商品卖点
- 本次使用的品牌规则
- 各平台标题、正文、标签和行动引导
- 可交给图像模型的海报 Prompt（提示词）
- 质量分数、风险项、审核状态和节点轨迹

`POST /api/v1/posters/generate`

接收工作流生成的海报 Prompt，并返回图片生成状态、模型、MIME 类型和 Base64 图片数据。Mock 模式仅返回可验证的占位响应，不产生调用费用。

`POST /api/v1/knowledge/documents`：增量写入品牌知识文档。

`POST /api/v1/knowledge/search`：按品牌和品类执行混合检索。

`PUT /api/v1/products/{sku}`：新增或更新商品，自动递增版本号。

`POST /api/v1/products/search/query`：搜索商品目录。

`POST /api/v1/campaigns/{id}/versions`：创建内容新版本。

`POST /api/v1/campaigns/{id}/submit-review`：提交人工审核。

`POST /api/v1/campaigns/{id}/decision`：批准或驳回当前版本。

`POST /api/v1/campaigns/{id}/publish`：幂等发布已批准版本。

`PUT /api/v1/operations/inventory/{sku}`：写入 ERP 库存演示数据。

`PUT /api/v1/operations/platform-orders/{channel}/{order_id}`：写入 Mock 平台订单。

`POST /api/v1/operations/platform-orders/{channel}/{order_id}/process`：通过平台网关拉取订单并生成运营决策。

`POST /api/v1/operations/runs/{id}/decision`：人工批准或拒绝外部写操作。

`POST /api/v1/operations/runs/{id}/execute`：幂等执行库存预占、履约或补货任务。

`GET /api/v1/operations/runs`：查看运营任务、风险、执行轨迹和异常结果。

`GET /metrics`：返回 Prometheus 格式的 HTTP、内容生成和发布指标。

真实模型模式：

```bash
GENERATION_MODE=openai
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
OPENAI_IMAGE_MODEL=gpt-image-2
```

Milvus 生产检索模式：

```bash
pip install -e ".[rag]"
RETRIEVAL_MODE=milvus
MILVUS_URI=http://localhost:19530
MILVUS_TOKEN=
```

SQLite 持久化模式：

```bash
PERSISTENCE_MODE=database
DATABASE_URL=sqlite+pysqlite:///./marketcraft.db
```

PostgreSQL 与 Redis 模式已在 `docker-compose.yml` 中编排：

```bash
PERSISTENCE_MODE=database
DATABASE_URL=postgresql+psycopg://marketcraft:${POSTGRES_PASSWORD}@postgres:5432/marketcraft
IDEMPOTENCY_MODE=redis
REDIS_URL=redis://redis:6379/0
```

运行 Compose 前需在未提交的 `.env` 中设置 `POSTGRES_PASSWORD`；仓库不提供默认密码。

完整请求示例见 [examples.http](examples.http)。

## Delivery roadmap

| Phase | Deliverable | Interview value |
| --- | --- | --- |
| 1 | 商品输入 → 文案 → 海报 Prompt → 质检 | FastAPI、LangGraph、结构化输出、异常与质量控制 |
| 2 ✅ | 商品图片理解、真实 LLM、海报生成 | 多模态模型、结构化输出、供应商抽象 |
| 3 ✅ | 品牌 RAG、商品库、混合召回 | Milvus、BM25、RRF、引用溯源 |
| 4 ✅ | 人工审核、版本管理、多平台发布 | Human-in-the-loop、四眼原则、幂等与审计 |
| 5 ✅ | 评测、监控、Redis/PostgreSQL、部署 | 可重复评测、可观测性、可靠性与工程化 |
| 6 ✅ | 订单、库存、履约、补货与飞书审批 | 跨系统 Agent、Human-in-the-loop、业务闭环 |
| 7 ✅ | 电商运营管理控制台 | 可视化演示、业务状态与执行轨迹 |

## Engineering decisions

- 使用 Workflow（固定工作流）作为主链路，保证营销生产过程稳定、可审计；只在创意生成和工具选择等局部使用 Agent 自主性。
- 所有生成器都通过 `ContentGenerator` 接口接入，Mock、OpenAI 兼容接口或本地模型可以互换。
- 生成结果必须经过独立质量节点，不能让同一次生成直接充当审核结论。
- 默认内存模式降低演示成本；通过环境变量可切换 SQLAlchemy 持久化与 Redis 幂等缓存。
- 订单决策使用确定性工作流；所有会修改库存或创建任务的操作必须先经过不同操作者审批。

## Verification boundary

- 已在无外部服务模式验证：26 个自动化测试、Ruff、内存模式、SQLite 跨服务实例持久化、Mock 发布与订单操作幂等、Dashboard 页面和静态资源、Prometheus 指标端点。
- 仓库内 4 条演示 RAG 回归样例在 `top_k=1` 时 Recall@1、MRR、引用覆盖率均为 1.0；该小样本结果仅用于回归，不代表生产效果。
- 已实现但未在本环境联调：PostgreSQL、Redis、Amazon/TikTok Shop/ERP/飞书真实接口，以及需要密钥或模型权重的 OpenAI/BGE 适配器。
- Milvus Lite + HashEmbedding 曾完成本地适配验证；生产 Milvus 服务仍需按实际部署环境联调。

更完整的设计见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。
