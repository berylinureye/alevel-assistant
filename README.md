# A-Level Assistant

A-Level Assistant 是一个面向 Cambridge A-Level Mathematics 的 AI 学习诊断系统：学生上传作业图片或 PDF 后，系统会识别题目、匹配 Past Paper / Mark Scheme、逐题批改、解释错因，并推荐下一步练习。

它不是一个通用聊天机器人，也不是只给答案的 demo。产品核心是：

> 让学生知道自己错在哪里、为什么错、今晚下一步该练什么。

## 现在做到哪里

当前 `main` 分支包含一个可运行的全栈 MVP：

- 上传图片、多图、PDF 页面和 Large PDF，并支持选页处理。
- `/prepare-upload` 提供 hash cache 与 in-flight dedupe，减少重复图片等待。
- Past Paper resolver 优先匹配 CIE 真题和 Mark Scheme；高置信命中时走 grounded grading。
- 匹配不到真题时回退到开放 AI 批改，并通过 confidence / needs_review 暴露风险。
- Grader 支持 fast-first 流式返回：先给首题和已完成题，慢题进入短窗口等待，超时则返回可复核 placeholder。
- SymPy、统计、概率、分数化简等 verifier 对 LLM 结果做确定性校准。
- 结果页展示得分、错因、薄弱知识点、复核风险和下一步练习建议。
- Practice Orchestrator 支持自动推荐、询问式推荐、内联答题和再次评分。
- 埋点与 benchmark 围绕「上传 -> 识别 -> 匹配 -> 批改 -> 校验 -> 讲解 -> 练习 -> 反馈」全链路组织。

## 核心架构

### 汇报版流程图

这版适合对外汇报、产品评审或快速介绍：重点讲清楚产品不是「拍照给答案」，而是从批改走到学习闭环。

```mermaid
flowchart LR
  A["上传作业或真题"] --> B["识别题目与学生答案"]
  B --> C["匹配真题与评分标准"]
  C --> D["逐题批改与扣分解释"]
  D --> E["规则校验与风险标记"]
  E --> F["生成错因讲解"]
  F --> G["推荐下一步练习"]
  G --> H["学生练习并反馈"]
```

设计原因：A-Level Assistant 的目标不是只把答案算出来，而是把学生的一次上传变成一次有效学习闭环。前半段解决「批得准」，中间用规则校验解决「不要高置信胡判」，后半段用讲解和练习解决「知道下一步练什么」。

### 详细版流程图

这版用于工程沟通和问题定位：重点展示图片、PDF、Large PDF、OCR、真题匹配、批改、校验和流式返回之间的真实后端路径。

```mermaid
flowchart TD
  U["学生上传图片或 PDF"] --> F["前端上传组件"]
  F --> P{"文件类型判断"}

  P -->|"图片 / 多图"| C["/prepare-upload<br/>哈希缓存 + 进行中请求去重"]
  C -->|"生成 upload_ids"| S["/analyze-homework-stream<br/>流式批改入口"]
  P -->|"Large PDF"| L["/large-pdf/prepare<br/>缩略图 + 选页"]
  L --> S

  S --> R{"是否走快速首题模式"}
  R -->|"是"| I["页面级识别<br/>尽量并行"]
  R -->|"否 / 高风险"| G["质量优先识别"]

  I --> O["Mathpix OCR 证据<br/>本地 OCR 弱兜底"]
  G --> O
  O --> Q{"OCR 是否可信"}
  Q -->|"含真实题干语言"| H["作为切题提示"]
  Q -->|"只有手写或证据弱"| A["只作为审计证据"]
  H --> X["结构化题目"]
  A --> X

  X --> M["真题匹配 + Mark Scheme 上下文"]
  M --> B["单模型首轮批改"]
  B --> T{"风险 / 置信度 / 校验信号"}
  T -->|"风险低"| V["确定性校验<br/>SymPy / 统计 / 概率 / 化简"]
  T -->|"需要复核"| W["复核或多模型路径"]
  W --> V

  V --> E["SSE 逐题返回<br/>先返回可用结果"]
  E --> Y{"剩余题是否过慢"}
  Y -->|"短窗口内完成"| Z["生成完整总结"]
  Y -->|"超时"| N["返回 needs_review 占位结果"]
  N --> Z
  Z --> K["推荐练习<br/>反馈与埋点"]
  K --> UI["结果页<br/>讲解 + 下一题练习"]
```

当前主路径是 **fast-first but quality-aware**：图片上传默认尽快返回首题和已完成题；低置信、空白、跨页、慢题不会被伪装成确定结论，而是通过 `needs_review`、timeout placeholder 和 verifier 暴露风险。

这样设计的核心取舍有三点：

- 速度上，先用缓存、并行识别和 SSE 逐题返回降低等待体感。
- 质量上，真题优先对齐 Mark Scheme，开放批改只作为无法匹配时的降级路径。
- 风险上，OCR、LLM 和规则校验互相制衡；不确定时宁可提示复核，也不输出看似确定但错误的结论。

更完整的后端路径、阶段指标和 benchmark 结论见 [Runtime Pipeline And Benchmarks](docs/runtime-pipeline-and-benchmarks.md)。模型角色、环境变量和 OCR 链路见 [Model Routing And OCR Chain](docs/model-routing-and-ocr-chain.md)。

## 本地运行

后端：

```bash
cp .env.example .env
pip install -r requirements.txt
python server.py
```

前端：

```bash
cd frontend
npm install
npm run dev
```

打开主应用：

```text
http://127.0.0.1:3000/
```

最快测试学习闭环：

```text
http://127.0.0.1:3000/__practice-recommendations-replay
```

在 replay 页面可以直接测试：

1. 第一块自动推荐：点 `开始练习`。
2. 第二块询问式推荐：点 `给我 2-3 道类似题`。
3. 再点 `开始练习`。
4. 输入答案：`x = 3 or x = -1/2`。
5. 点 `提交答案`。
6. 看到评分、参考答案、评分标准和下一题动作。

## 主要目录

| Path | 作用 |
| --- | --- |
| `frontend/` | React/Vite 前端，包含上传、批改结果、Large PDF、练习推荐和 replay 页面 |
| `api/` | FastAPI 路由、上传缓存、Large PDF、题库推荐和 feedback/debug 接口 |
| `pipeline/` | 图片/PDF 处理、切题提取、批改编排和 SSE workflow events |
| `grader/` | 单题批改、多 agent 投票、置信度调整和 verifier 集成 |
| `verifier/` | SymPy、概率、统计、分数化简等确定性兜底 |
| `router/` | 模型抽象、模型注册、升级规则和路由上下文 |
| `questionbank/` | CIE 题库、Mark Scheme、Past Paper 匹配和本地 SQLite 数据 |
| `agent_workflow/` | 长任务开发的 agent 记忆、PRD、进度和 durable knowledge |
| `reports/effectiveness/` | 上传链路、批改质量、速度和阶段耗时 benchmark 报告 |
| `spec/` | 产品规格、验收标准、Large PDF 与长期 agent workflow 说明 |

## 关键文档

- [Runtime Pipeline And Benchmarks](docs/runtime-pipeline-and-benchmarks.md)
- [Model Routing And OCR Chain](docs/model-routing-and-ocr-chain.md)
- [规则校验与确定性兜底](docs/rule-based-verification.md)
- [2026-06-26 后端实现路径](reports/effectiveness/20260626_backend_implementation_path.md)
- [Acceptance Criteria](spec/acceptance.md)
- [Long-Running Agent Workflow](spec/long-running-agent-workflow.md)
- [Superpowers 插件使用说明](docs/superpowers-plugin-workflow.md)
- [本地运行](RUN.md)
- [部署指南](DEPLOY.md)

## 常用验证命令

```bash
PYTHONPATH=. pytest -q test/test_pipeline_streaming.py test/test_fast_upload_flow.py test/test_effectiveness.py test/test_large_pdf_mode.py

cd frontend
npm run build
```

更完整的产品体验验收：

```bash
cd frontend
npm run test:visual
```

## 当前边界

- 真题题库以 Cambridge 9709 数学为核心，当前产品路线优先 P1-P6。
- 非真题或题库外知识点不会强行推荐题目，会先询问或解释不可推荐原因。
- 速度优化服从质量边界：不确定题宁可 `needs_review=true`，不能给学生一个看似确定但错误的结论。
- 原始第三方 past paper PDF 不适合直接放入普通 Git 历史，见 [docs/DATA.md](docs/DATA.md)。

## 开源说明

This repository is open sourced under the [MIT License](LICENSE).

Open-source hygiene:

- Real API keys and deployment secrets must live in `.env`, never in Git.
- Raw third-party exam PDFs are excluded from normal Git history.
- The included SQLite data is for local demos and development; check redistribution rights before publishing additional paper corpora.
- Hosted deployments should review [SECURITY.md](SECURITY.md), especially debug endpoints, CORS, upload handling, and admin tokens.
