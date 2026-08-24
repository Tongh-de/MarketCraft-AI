# MarketCraft AI

> 面向电商运营团队的一体化 AI 工作台。一个入口完成对话、文案生成、文生图、海报设计、商品上架、订单库存和经营分析。

[![FastAPI](https://img.shields.io/badge/FastAPI-0f766e?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Workflow-111827?style=flat-square)](https://www.langchain.com/langgraph)
[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-16_passed-16a34a?style=flat-square)](#verification)

MarketCraft AI 把电商内容创作和运营流程整合到同一个产品里。你可以像聊天一样向 Agent 下任务, 也可以进入专业模块完成营销文案、文生图、商品创作、竞品分析、海报设计、多平台上架、订单库存处理和数据复盘。

当前项目已经支持真实 API 接入:

- DeepSeek / Qwen / OpenAI-compatible 文案模型
- 通义万相 Wanx 文生图
- LangSmith 链路追踪
- Mock 模式本地演示和测试

## Preview

### Unified Workspace

![MarketCraft AI unified workspace](docs/assets/unified-app-preview.svg)

### Operations

| Dashboard | Human Review |
| --- | --- |
| ![Dashboard preview](docs/assets/dashboard-preview.svg) | ![Approval preview](docs/assets/approval-preview.svg) |

| Inventory Decision | Execution Trace |
| --- | --- |
| ![Restock preview](docs/assets/restock-preview.svg) | ![Execution preview](docs/assets/execution-preview.svg) |

### Listing & Performance

![Listing workbench](docs/assets/listing-workbench-preview.svg)

![Performance insights](docs/assets/performance-insights-preview.svg)

## Highlights

| Module | What it does |
| --- | --- |
| AI 工作台 | 通过对话让 Agent 执行闲聊、文案生成、文生图等任务 |
| 营销文案 | 生成商品卖点、小红书/抖音/淘宝/京东文案和质量评分 |
| 文生图 | 调用通义万相生成商品主图、海报图和营销视觉 |
| 商品创作 | 管理商品素材、模特试穿、多角度图和创作产物 |
| 竞品分析 | 拆解竞品视觉、卖点、场景和原创 Brief |
| 海报设计 | 编辑图层、平台尺寸、品牌颜色和服务端 SVG 预览 |
| 审核与上架 | 生成平台 Listing, 走四眼审核和幂等发布 |
| 订单与库存 | 处理平台订单、ERP 库存、履约和补货建议 |
| 经营优化 | 分析 CTR、转化率、ROAS、退货率和库存覆盖天数 |
| 可观测性 | 支持 Prometheus metrics 和 LangSmith tracing |

## Architecture

```mermaid
flowchart LR
    User[User] --> App[Unified Web App]
    App --> API[FastAPI API Layer]
    API --> Workflow[LangGraph Workflows]
    Workflow --> Generator[LLM / Image Providers]
    Workflow --> Store[(Memory / Database)]
    Workflow --> Metrics[Prometheus + LangSmith]
```

```mermaid
flowchart LR
    Product[Product Input] --> Points[Selling Points]
    Points --> Copy[Platform Copy]
    Copy --> QA[Quality Review]
    QA --> Package[Campaign Package]
```

```mermaid
flowchart LR
    Order[Platform Order] --> Stock[ERP Stock]
    Stock --> Decision[Agent Decision]
    Decision --> Review[Human Review]
    Review --> Execute[Fulfillment / Restock]
```

More documents:

- [Product Requirements](docs/PRD.md)
- [Architecture Notes](docs/ARCHITECTURE.md)
- [API examples](examples.http)

## Quick Start

### 1. Install

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

### 2. Run

```bash
uvicorn app.main:app --reload
```

Open these pages:

| Page | URL |
| --- | --- |
| Web app | http://localhost:8000/app |
| API docs | http://localhost:8000/docs |
| Metrics | http://localhost:8000/metrics |

### 3. Test

```bash
pytest
ruff check app scripts tests
python -m scripts.evaluate_rag --top-k 1
```

### 4. Docker

```bash
cp .env.example .env
docker compose up --build
```

## Real API Configuration

The default provider is Mock mode, so the project can run without external credentials.

### DeepSeek

```bash
GENERATION_MODE=openai_compatible
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
```

### Qwen Compatible Mode

```bash
GENERATION_MODE=openai_compatible
OPENAI_API_KEY=
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus
```

### OpenAI

```bash
GENERATION_MODE=openai
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
OPENAI_IMAGE_MODEL=gpt-image-2
```

### Tongyi Wanxiang

```bash
IMAGE_GENERATION_MODE=wanx
DASHSCOPE_API_KEY=
WANX_BASE_URL=https://dashscope.aliyuncs.com/api/v1
WANX_MODEL=wan2.6-t2i
WANX_SIZE=1280*1280
WANX_POLL_INTERVAL_SECONDS=2
WANX_TIMEOUT_SECONDS=120
```

### LangSmith

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=marketcraft-ai-local
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

### Persistence

SQLite:

```bash
PERSISTENCE_MODE=database
DATABASE_URL=sqlite+pysqlite:///./marketcraft.db
```

PostgreSQL and Redis:

```bash
PERSISTENCE_MODE=database
DATABASE_URL=postgresql+psycopg://marketcraft:${POSTGRES_PASSWORD}@postgres:5432/marketcraft
IDEMPOTENCY_MODE=redis
REDIS_URL=redis://redis:6379/0
```

Milvus retrieval:

```bash
pip install -e ".[rag]"
RETRIEVAL_MODE=milvus
MILVUS_URI=http://localhost:19530
MILVUS_TOKEN=
```

## Product Routes

| Route | Description |
| --- | --- |
| `/app` | Unified product shell |
| `/campaign-studio` | Marketing copy generation |
| `/image-studio` | Text-to-image studio |
| `/studio` | Product creation workspace |
| `/competitors` | Competitor visual analysis |
| `/poster-editor` | Editable poster editor |
| `/listing-workbench` | Multi-platform listing workflow |
| `/performance-insights` | Performance analysis |
| `/dashboard` | Order and inventory dashboard |

## API Map

### Campaigns

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/campaigns/generate` | Generate selling points, platform copy and poster prompt |
| `GET` | `/api/v1/campaigns/{id}` | Read campaign lifecycle |
| `POST` | `/api/v1/campaigns/{id}/versions` | Create immutable content version |
| `POST` | `/api/v1/campaigns/{id}/submit-review` | Submit campaign for review |
| `POST` | `/api/v1/campaigns/{id}/decision` | Approve or reject campaign |
| `POST` | `/api/v1/campaigns/{id}/publish` | Idempotent platform publish |

### Image & Poster

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/posters/generate` | Generate image from text prompt |
| `POST` | `/api/v1/poster-projects` | Create editable poster project |
| `PUT` | `/api/v1/poster-projects/{id}` | Save poster revision |
| `GET` | `/api/v1/poster-projects/{id}/preview.svg` | Render server-side SVG preview |

### Products & Knowledge

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `PUT` | `/api/v1/products/{sku}` | Create or update product |
| `POST` | `/api/v1/products/search/query` | Search catalog |
| `POST` | `/api/v1/knowledge/documents` | Add brand knowledge |
| `POST` | `/api/v1/knowledge/search` | Hybrid brand retrieval |

### Operations

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `PUT` | `/api/v1/operations/inventory/{sku}` | Write demo ERP stock |
| `PUT` | `/api/v1/operations/platform-orders/{channel}/{order_id}` | Write mock platform order |
| `POST` | `/api/v1/operations/platform-orders/{channel}/{order_id}/process` | Process order through workflow |
| `POST` | `/api/v1/operations/runs/{id}/decision` | Human approval |
| `POST` | `/api/v1/operations/runs/{id}/execute` | Execute approved operation |
| `GET` | `/api/v1/operations/runs` | List operation runs |

### Platform Extensions

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/platform/skill-plugins` | List skills |
| `POST` | `/api/v1/platform/skill-plugins` | Create custom skill draft |
| `POST` | `/api/v1/platform/skill-plugins/{id}/auto-edit` | Generate skill revision |
| `POST` | `/api/v1/platform/skill-plugins/{id}/status` | Enable or disable skill |
| `GET` | `/api/v1/platform/external-services` | List service adapters |
| `POST` | `/api/v1/platform/external-services` | Register service adapter |
| `POST` | `/api/v1/platform/external-services/{id}/health` | Check adapter boundary |

## Engineering Notes

- The system uses deterministic workflows around AI calls, so results remain auditable.
- LLM and image providers are isolated behind service interfaces.
- External write operations require review, idempotency keys and audit records.
- Mock mode is safe for demos, tests and offline development.
- Real integrations are enabled only through explicit environment variables.

## Verification

Last validated locally:

```bash
pytest tests/test_api.py tests/test_poster_projects.py -q
# 16 passed
```

The broader test suite covers campaign workflow, product catalog versions, retrieval, poster projects, listing packages, order operations, performance insights, persistence boundaries, skill lifecycle and external service boundaries.

## Security Boundary

- `.env` is ignored and should never be committed.
- Real API keys should live only in local `.env`, deployment secrets or a secrets manager.
- External write operations stay behind human review.
- Mock data is clearly marked and should not be presented as real business performance.

## Roadmap

| Phase | Focus |
| --- | --- |
| 1 | Marketing copy workflow and quality checks |
| 2 | Real LLM and image providers |
| 3 | Brand RAG and product catalog |
| 4 | Human review, versioning and idempotent publishing |
| 5 | Metrics, persistence, Redis and PostgreSQL deployment |
| 6 | Order, inventory, fulfillment and restock |
| 7 | Unified operations dashboard |
| 8 | Product creation, competitor analysis and poster editor |
| 9 | Performance feedback and read-only recommendations |
| 10 | Unified AI workspace, skill registry and external service hub |

