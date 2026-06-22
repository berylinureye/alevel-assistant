# Superpowers 插件使用说明

Superpowers 在这个项目里不是一个「替我写代码的模型」，而是一套约束 agent 工作方式的流程插件。它的价值不在于多生成几行代码，而在于把 AI 产品经理最难稳定执行的部分流程化：先澄清目标，再写规格，再拆计划，再分派子 agent，再验收证据，最后提交。

换句话说，普通 prompt 解决的是「这次让 agent 做什么」；Superpowers 解决的是「每次都让 agent 用什么方法做」。

## 1. 我为什么需要 Superpowers

这个项目的复杂度不在单个函数，而在多个系统同时变化：

- 产品侧：学习诊断、Past Paper 路由、Large PDF、练习推荐、学生可见文案。
- 后端侧：FastAPI、SSE、上传缓存、题库、paper resolver、model router。
- 模型侧：Vision extraction、多 agent grading、confidence、needs_review、verifier override。
- 前端侧：React 状态、loading timeline、移动端适配、截图验收。
- 开发侧：多个 agent 会跨会话接力，容易忘记上下文。

如果只靠一句「帮我实现 Large PDF 模式」，agent 很容易直接写代码，然后在验收时暴露问题：没有视觉证据、路由边界混乱、把学生端文案写得太技术、忘记保留旧上传路径、或者把开发 agent workflow 和产品 runtime agent 混在一起。

Superpowers 的作用就是把这些风险提前变成流程门槛。

## 2. Superpowers 在这里扮演的角色

我把 Superpowers 看成开发过程中的「操作系统层」：

```text
User idea
  -> Superpowers brainstorming/spec discipline
  -> docs/superpowers/specs/*
  -> Superpowers writing-plans
  -> docs/superpowers/plans/*
  -> subagent-driven development / executing plans
  -> verification-before-completion
  -> git commit / push
  -> project-level memory in agent_workflow/*
```

它和仓库自己的 `agent_workflow/` 分工不同：

| 层 | 作用 | 代表文件 |
| --- | --- | --- |
| Superpowers 插件 | 规定 agent 应该怎样思考和执行 | `brainstorming`, `writing-plans`, `subagent-driven-development`, `verification-before-completion` |
| 仓库内 workflow | 保存这个项目已经做过什么、下一步是什么、有什么坑 | `agent_workflow/prd.json`, `progress.md`, `knowledge.md` |
| 产品 runtime agent | 给学生批改题目，不参与开发流程 | `pipeline/`, `grader/`, `verifier/`, `formatter/` |

这个分层很重要。Superpowers 是方法论；`agent_workflow/` 是项目记忆；runtime agents 是产品能力。三者不能混在一起。

## 3. 用到的关键 Superpowers 技能

### `using-superpowers`

这个技能的作用是强制 agent 在行动前先检查是否有适用技能。它解决的是「agent 急着开干」的问题。

对这个项目来说，很多任务看似只是小修改，实际会牵动产品体验、验收标准或长期记忆。`using-superpowers` 让 agent 先进入有纪律的工作状态，而不是直接凭直觉改文件。

### `brainstorming`

用于创意和产品设计阶段。它要求先探索上下文、提出方案、形成设计，再进入实现。

在 AI PM 视角下，这一步等价于把「我想做个功能」变成「这个功能服务谁、解决什么问题、边界是什么、什么算做好」。比如 Practice Orchestrator 不是直接让 agent 写推荐接口，而是先明确三种模式：

- `auto`：可以直接推荐。
- `ask_first`：信息不足，需要先问学生。
- `none`：没有足够依据，不强行推荐。

这类模式设计如果不先做，后面代码会变成 patchwork。

### `writing-plans`

用于把规格变成可执行计划。它要求计划写到 `docs/superpowers/plans/`，并且每个任务包含文件范围、步骤、测试命令和提交点。

这个技能是我让 agent 高效工作的关键之一。它把一个大任务拆成很多可验收的小任务，让后续 agent 不需要重新理解整个世界，只要执行当前 slice。

本项目里已经有例子：

- `docs/superpowers/specs/2026-06-22-practice-orchestrator-mvp-design.md`
- `docs/superpowers/plans/2026-06-22-practice-orchestrator-mvp.md`

### `subagent-driven-development`

用于执行多任务计划。它的核心思想是：每个任务派一个新 subagent，保持上下文干净；每个任务完成后先做 spec compliance review，再做 code quality review。

这对 AI 开发很关键，因为长对话里的 agent 会逐渐背上太多上下文，容易把旧目标、新目标、自己的猜测混在一起。新 subagent 只拿到当前任务所需上下文，反而更稳定。

我在项目里把它映射成几种角色：

- 产品子 agent：看学生可见文案、模式边界和用户体验。
- 后端子 agent：实现 API、schema、题库查询和测试。
- 前端子 agent：实现 UI、状态、replay fixture 和视觉入口。
- 测试子 agent：跑 pytest、build、lint、截图和 DOM 检查。
- Review agent：检查是否符合 spec、是否过度实现、是否漏验收证据。

### `verification-before-completion`

这个技能解决的是 AI 开发里最危险的一句话：「应该好了」。

它要求在声称完成、提交或创建 PR 前，必须有新鲜验证证据。对这个项目来说，验证不只是跑测试，还包括：

- 后端：focused pytest、py_compile、接口返回样例。
- 前端：`npm run build`、类型检查、focused lint。
- UI：真实浏览器截图、DOM evidence、horizontal overflow 检查。
- Workflow：`scripts/agent_workflow.py status` 能读 task state。
- 文档：placeholder scan、链接存在、diff 范围检查。

这个技能让 agent 的输出从「感觉完成」变成「证据完成」。

### `finishing-a-development-branch`

用于实现完成后处理分支、PR、merge 或保留现场。它强调先验证，再决定怎么集成。

在这个项目里，工作区经常同时存在功能开发、文档补充、测试 fixture 和本地实验。如果没有这个流程，agent 很容易把 unrelated changes 一起提交。通过 Git hygiene，我可以只提交本次文档，不碰 Large PDF 或 Practice Orchestrator 的本地改动。

## 4. Superpowers 如何和我的 agent harness 结合

我自己的 harness 在仓库里：

- `agent_workflow/prd.json`：任务状态。
- `agent_workflow/progress.md`：短期进度。
- `agent_workflow/knowledge.md`：长期项目知识。
- `scripts/agent_workflow.py`：状态更新工具。
- `spec/acceptance.md`：验收标准。

Superpowers 提供的是「工作法」，我自己的 harness 提供的是「项目记忆」。二者结合后，agent 的执行链路变成：

```text
1. 读项目总规则
   - AGENCY.md
   - spec/acceptance.md
   - agent_workflow/knowledge.md

2. 用 Superpowers 做设计和计划
   - brainstorming -> spec
   - writing-plans -> implementation plan

3. 用子 agent 执行
   - bounded file ownership
   - implementer
   - tester
   - reviewer

4. 用证据收口
   - tests
   - build
   - screenshots / DOM
   - git diff scope

5. 写回项目记忆
   - progress.md
   - knowledge.md
   - prd.json event history
```

这样做之后，agent 的行为不再像一次性问答，而像一个带流程的开发团队。

## 5. 深层价值：把 prompt 变成制度

普通 prompt 的问题是不可累积。今天你告诉 agent「注意验收」，明天换一个会话，它又忘了。Superpowers 和仓库文档配合后，规则变成可重复读取的制度。

这个项目里尤其重要的制度有五个：

### 目标函数制度

不是「做得好一点」，而是：

- 30 秒内尽量高正确率。
- 简单题少烧慢模型。
- 高风险题必须升级或标记复核。
- UI 必须让学生知道下一步怎么学。

### 上下文制度

agent 开始前必须读：

- 项目结构。
- 相关 spec。
- acceptance。
- 已知 gotchas。

这减少了 agent 自行脑补架构的概率。

### 文件所有权制度

每个子任务限定文件范围。这样多个 agent 可以接力，但不会互相覆盖或顺手重构无关模块。

### 验收证据制度

所有「完成」都要附证据。尤其是 UI 任务，build log 不够，需要截图或真实浏览器证据。

### 复盘记忆制度

每轮有价值的经验写回 `progress.md` 或 `knowledge.md`。下次 agent 不需要从聊天记录里考古。

## 6. 和 AI 产品经理能力的关系

Superpowers 不是把 PM 工作自动化掉，而是放大 PM 的杠杆。

AI PM 真正要做的不是写更多 prompt，而是设计 agent 能稳定执行的工作系统：

| PM 能力 | Superpowers 放大的部分 | 本项目里的例子 |
| --- | --- | --- |
| 需求澄清 | brainstorming 把模糊想法变成规格 | Practice Orchestrator 的 `auto / ask_first / none` |
| Scope 管理 | spec 和 plan 明确不做什么 | Large PDF 不提高普通上传上限，而是单独 session |
| 验收设计 | verification-before-completion 要求证据 | UI 任务必须有截图和 overflow 检查 |
| 任务拆解 | writing-plans 形成 bite-sized tasks | 后端、前端、replay、测试拆开 |
| 团队编排 | subagent-driven-development 分角色执行 | 产品、后端、前端、测试、评审子 agent |
| 知识沉淀 | 文档和 agent_workflow 保存决策 | ADR、knowledge、progress、acceptance |

这也是我认为「会用 agent」和「会管理 agent」的区别：前者是让模型回答，后者是设计一套模型可以持续工作的生产系统。

## 7. 具体例子：Practice Orchestrator MVP

Practice Orchestrator 是一个典型例子。

如果直接实现，很容易变成「批改结果页塞 3 道题」。但 Superpowers 流程把它拆成了更产品化的闭环：

1. 先写设计规格，明确目标是学习闭环，而不是推荐列表。
2. 定义三种推荐模式：自动推荐、先询问、不推荐。
3. 后端只做薄编排：题库查询、topic 推导、去重、模式决策。
4. 前端负责结果页交互、询问式推荐、内联作答。
5. replay fixture 覆盖三种状态，方便视觉验收。
6. 测试子 agent 负责后端测试、前端 build、lint、截图和 DOM 证据。

这背后体现的是 AI PM 的一个核心动作：不要让功能停留在「输出内容」，要把它做成「可验证的用户流程」。

## 8. 具体例子：Large PDF Mode

Large PDF Mode 也是这样。

最粗暴的做法是把普通上传上限调高，让系统一次处理完整 PDF。但这会冲击已有路径，增加延迟和失败率。

在 Superpowers 的规格和计划约束下，方案变成：

- Large PDF 是独立 route/session。
- 后端先 prepare，返回 page_count、缩略图、paper-resolution metadata。
- 前端让用户看到页面并自动选择可处理页。
- 单次 grading 仍保持预算上限。
- 本地 PDF 路径只保存在后端 session，不返回前端。
- 验收要求包含后端 response、截图、流式证据和普通上传回归。

这个例子说明：Superpowers 不是让 agent 更激进，而是让 agent 更会克制。

## 9. 我从使用 Superpowers 得到的经验

第一，规格比 prompt 更重要。
prompt 是一次性指令，spec 是可复用上下文。

第二，计划比速度更重要。
没有 plan 的快速实现，常常会把错误藏到后面；有 plan 的慢启动，反而让后续子 agent 更快。

第三，验收比自信更重要。
AI 很容易给出自信的完成感，但产品需要证据。

第四，子 agent 不是越多越好。
只有当任务能清楚拆分、文件边界明确、验收标准明确时，子 agent 才能提高效率。

第五，插件不是替代思考，而是强迫思考。
Superpowers 的价值是把我本来就该做的 PM 和工程纪律固定下来，让 agent 不容易绕开。

## 10. 可复用模板

以后做类似 AI 项目，我会继续沿用这套结构：

```text
AGENCY.md
spec/acceptance.md
docs/decisions/ADR-001-*.md
docs/superpowers/specs/YYYY-MM-DD-feature-design.md
docs/superpowers/plans/YYYY-MM-DD-feature.md
agent_workflow/prd.json
agent_workflow/progress.md
agent_workflow/knowledge.md
scripts/agent_workflow.py
```

对应流程：

```text
Idea
  -> brainstorm/spec
  -> plan
  -> subagent execution
  -> spec review
  -> quality review
  -> verification evidence
  -> commit
  -> durable memory
```

一句话总结：Superpowers 插件让 agent 不再只是「会写代码的模型」，而更像一个被流程约束的开发团队；而我的工作，是把产品判断、验收标准和项目记忆放进这套流程里。
