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

首页只放主流程，方便产品汇报时快速讲清楚：A-Level Assistant 不是「拍照给答案」，而是把一次上传变成一次可继续练习的学习闭环。

```mermaid
flowchart LR
  A["上传"] --> B["识别"]
  B --> C["批改"]
  C --> D["校验"]
  D --> E["讲解"]
  E --> F["练习"]
  F --> G["反馈"]
```

主流程背后的设计取舍：

- 速度上，先用缓存、并行识别和 SSE 逐题返回降低等待体感。
- 质量上，真题优先对齐 Mark Scheme，开放批改只作为无法匹配时的降级路径。
- 风险上，OCR、LLM 和规则校验互相制衡；不确定时宁可提示复核，也不输出看似确定但错误的结论。

需要展开时看这两个链接：

- [详细后端流程、快速首题模式和 benchmark](docs/runtime-pipeline-and-benchmarks.md)
- [模型路由、OCR 链路和环境变量](docs/model-routing-and-ocr-chain.md)

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
