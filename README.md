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

## 核心设计链路 / Core Design Flow

首页只放产品主线，方便公开演示或技术讲解时快速讲清楚：A-Level Assistant 不是「拍照给答案」，而是把一次上传变成一次可信、可继续练习、可复盘优化的学习闭环。

可直接演示的纵向版本：

- [打开 Presentation View](https://htmlpreview.github.io/?https://github.com/berylinureye/alevel-assistant/blob/main/docs/project-flow.html)
- 本地打开：`docs/project-flow.html`

```mermaid
flowchart TD
  Student([学生<br/>Student])
  Intake["1. 输入与预处理 / Intake<br/>上传图片/PDF → 规范化 → 选页、hash cache、去重"]
  Understand["2. 题目理解 / Question Understanding<br/>OCR + Vision 切题 → 保留学生步骤 → 匹配真题与评分标准"]
  Match{"3. 批改路径 / Grading Path<br/>是否高置信命中 Mark Scheme？"}
  Grounded["真题对齐批改<br/>Mark-scheme grounded grading"]
  OpenGrade["开放题批改<br/>Open-ended AI grading"]
  Verify["确定性校验 + 置信度标记<br/>Deterministic checks + needs_review"]
  Feedback([4. 可行动反馈<br/>分数、错因、薄弱点])
  Recommend{"下一题是否可靠？<br/>Is the next practice reliable?"}
  Auto["推荐真实题库题<br/>Recommend real paper practice"]
  Ask["先询问学生<br/>Ask a clarifying question"]
  Boundary["说明题库或能力边界<br/>Explain coverage limit"]
  Practice["内联作答 → 再次评分 → 更新反馈<br/>Inline attempt → re-grade → updated feedback"]
  Quality["5. 异步质量闭环 / Quality Loop<br/>SSE events + benchmark → 优化题库、模型路由、校验规则"]
  Future["改进后续运行<br/>Improve future runs"]

  Student --> Intake --> Understand --> Match
  Match -->|"命中 / Matched"| Grounded --> Verify
  Match -->|"未命中 / Not matched"| OpenGrade --> Verify
  Verify -->|"实时返回 / Sync response"| Feedback --> Recommend
  Recommend -->|"是 / Yes"| Auto --> Practice
  Recommend -->|"需要更多信息 / Need context"| Ask --> Practice
  Recommend -->|"否 / No"| Boundary
  Practice -.->|"练习结果 / Practice signal"| Quality
  Boundary -.->|"覆盖边界 / Coverage signal"| Quality
  Quality -.-> Future

  classDef learner fill:#ecfeff,stroke:#0891b2,color:#0f172a
  classDef processing fill:#eef2ff,stroke:#4f46e5,color:#0f172a
  classDef trust fill:#fef3c7,stroke:#d97706,color:#0f172a
  classDef practice fill:#ecfdf5,stroke:#059669,color:#0f172a
  classDef boundary fill:#fff1f2,stroke:#e11d48,color:#0f172a

  class Student,Feedback learner
  class Intake,Understand,Grounded,OpenGrade processing
  class Match,Verify trust
  class Recommend,Auto,Ask,Practice practice
  class Boundary,Quality,Future boundary
```

### 怎么读这张图 / How to Read It

这张图里有两种线：**实线是学生当次上传会经历的主链路**，**虚线是系统异步记录和后续优化的质量闭环**。

- **主链路 / User-facing path**：上传后，系统先做预处理、OCR/Vision 切题、真题与 Mark Scheme 匹配，再进入批改和校验，最后把分数、错因、薄弱点和下一步练习返回给学生。
- **置信度节点 / Confidence gate**：`Confidence and needs_review` 不是另一次批改，而是批改后的一道可信度闸门。它决定这道题能不能放心展示、是否要标 `needs_review`、以及结果页应该如何表达风险。
- **质量闭环 / Quality loop**：练习结果和覆盖边界会通过虚线进入 `SSE events + benchmark`。系统会记录速度、准确率、复核率、题库覆盖和推荐转化，用来改进后续版本的题库、模型路由和校验规则；它不阻塞学生当次看到批改结果。
- **练习闭环 / Practice loop**：如果系统能可靠找到下一题，就推荐真实题库题并支持内联作答、再次评分；如果信息不足，会先询问；如果题库覆盖不到，会明确说明边界，不硬猜。

这张图对应三个可以展开的产品判断：

- **先对齐真实阅卷标准**：能匹配 Past Paper 时优先使用 Mark Scheme，而不是只让模型自由发挥。
- **把 AI 风险产品化**：OCR、LLM、规则校验和多模型复核互相制衡；不确定时显示 `needs_review`，不伪装确定。
- **把批改变成闭环**：结果页不仅展示分数，还沉淀薄弱点、推荐真实练习，并支持再次作答和评分。

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
