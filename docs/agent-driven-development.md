# Agent 驱动开发与提效系统

这个项目的另一个重点不是产品运行时的 grading agents，而是开发过程中如何让 agent 真正替我干活。核心做法是：把 AI 产品经理的需求定义、验收标准、任务拆解、复盘和证据回收写进仓库，让 agent 每次接手时都有稳定上下文。

## 先区分两类 agent

项目里有两类容易混淆的 agent：

| 类型 | 位置 | 作用 |
| --- | --- | --- |
| 产品运行时 agent | `pipeline/`, `grader/`, `verifier/`, `formatter/` | 批改学生作业、投票、校验、生成反馈 |
| 开发编排 agent | `agent_workflow/`, `scripts/agent_workflow.py`, `spec/` | 帮我拆任务、写代码、测试、复盘、延续上下文 |

这篇文档讲的是第二类：开发 harness。

Superpowers 插件是这套 harness 的方法层：它规定什么时候先做 brainstorming，什么时候写 implementation plan，什么时候派 subagent，什么时候必须拿验证证据。更深入的插件说明见 [Superpowers 插件使用说明](superpowers-plugin-workflow.md)。

## 1. 把需求写成 agent 可执行的规格

相关文件：

- `AGENCY.md`
- `spec/product-ui-agent-spec.md`
- `spec/acceptance.md`
- `spec/large-pdf-mode.md`
- `docs/superpowers/specs/`
- `docs/superpowers/plans/`

我没有只对 agent 说「帮我做一个功能」。每个复杂功能都会先变成规格：

- 用户是谁。
- 当前问题是什么。
- 不做什么。
- 路由和状态怎么定义。
- 前后端数据契约是什么。
- 什么叫完成。
- 什么证据能证明它完成。

这就是 AI PM 里的 PRD 思维：不是让 agent 猜，而是把目标函数和边界写清楚。

## 2. 用 acceptance criteria 管住 agent

`spec/acceptance.md` 是整个项目的验收层。它把「看起来可以」改成「必须有证据」：

- 前端改动必须有 build 和真实浏览器截图或 DOM 证据。
- 移动端要检查 horizontal overflow。
- agent_step 不能把 raw `think / act / observe / decide / final` 暴露给学生。
- Large PDF 不能把本地 PDF 路径返回到前端。
- 长任务完成必须记录 task id、命令和验证证据。

这解决了 AI 开发最常见的问题：agent 很容易说「完成了」，但没有可复现证据。验收标准把主观完成变成客观完成。

## 3. `agent_workflow/`：给 agent 的长期记忆

相关文件：

- `agent_workflow/prd.json`
- `agent_workflow/progress.md`
- `agent_workflow/knowledge.md`
- `agent_workflow/README.md`
- `scripts/agent_workflow.py`

`agent_workflow/prd.json` 记录任务、状态、优先级、文件范围、验收标准和事件历史。`progress.md` 是短期记忆，记录每轮做了什么。`knowledge.md` 是长期知识，保存项目原则、架构边界和已知坑。

常用命令：

```bash
python scripts/agent_workflow.py status
python scripts/agent_workflow.py next
python scripts/agent_workflow.py start AW-001 --agent orchestrator --note "Starting"
python scripts/agent_workflow.py complete AW-001 --agent tester --note "pytest + build + screenshot passed"
python scripts/agent_workflow.py block AW-001 --agent tester --note "Backend key unavailable"
python scripts/agent_workflow.py note --agent orchestrator --text "Learned: keep paper matching separate from grading."
```

这套机制的价值是跨会话延续。即使换一个新 agent，它也可以先读状态、读知识、读验收，而不是从零猜项目。

## 4. Orchestrator + 子 agent 分工

正式设计记录在：

- `spec/long-running-agent-workflow.md`
- `docs/decisions/ADR-001-long-running-agent-workflow.md`

主 agent 是 orchestrator，职责是：

- 读 `AGENCY.md`、相关 spec 和 `agent_workflow/knowledge.md`。
- 从 `prd.json` 选择下一项任务。
- 给子 agent 打包上下文。
- 指定文件所有权，减少互相覆盖。
- 集成结果。
- 决定完成、阻塞还是继续迭代。
- 更新 progress 和 durable knowledge。

子 agent 分成：

- Planning agent：把需求拆成步骤。
- Development agent：在限定文件里实现。
- Testing agent：按验收标准验证。
- Review agent：查风险、回归和证据是否充分。

关键规则：谁写出的 bug，谁修；谁发现的问题，谁复验。这样可以保留局部上下文，不会每一轮都重新解释。

## 5. Superpowers 插件如何参与这套流程

Superpowers 提供的是流程纪律，仓库内 `agent_workflow/` 提供的是项目记忆。二者结合后，agent 不只是按一次 prompt 工作，而是按固定链路推进：

```text
brainstorming
  -> design spec
  -> writing-plans
  -> subagent-driven-development
  -> spec review
  -> code quality review
  -> verification-before-completion
  -> git commit / push
  -> progress / knowledge update
```

这套流程的深层价值是把「会不会用 agent」从 prompt 技巧变成管理系统：每个 agent 都要知道目标、边界、文件范围、验收标准和证据要求。

## 6. Agent 完全干活的关键不是「放手」，而是「搭护栏」

这个项目里让 agent 高效工作的护栏包括：

- 文件边界：每个任务写清楚会碰哪些目录。
- 验收边界：每个任务都有 acceptance。
- 证据边界：完成时必须写命令、截图、DOM 或测试结果。
- 架构边界：模型调用必须走 `router.models.ModelClient`，开发 workflow 不能耦合 runtime grading agents。
- UI 边界：学生界面不能暴露隐藏推理，不能让技术标签污染学习体验。
- 安全边界：不提交真实 key、本地上传、缓存和无关产物。

这背后是一个 AI PM 技巧：不要幻想 agent 天然知道产品边界，要把边界写成它每次都会读到的文件。

## 7. 从功能迭代看 agent workflow 怎么提效

已经在 `agent_workflow/prd.json` 跑过的任务包括：

- `AW-001`：Past Paper route 提取 question-level Mark Scheme context。
- `AW-002`：fixture-backed `agent_step` replay，用于 loading UI 验收。
- `AW-003`：可重复的视觉验收 runner，覆盖 desktop/mobile 截图和 overflow 检查。
- `AW-004`：Large PDF Mode 设计方案。
- `AW-005`：Large PDF 后端 prepare session。
- `AW-006`：Large PDF 前端 selection UI。

这些任务横跨后端、前端、视觉验收和产品文案。如果只靠一条长聊天记录，很容易丢上下文；写进 workflow 后，每个任务都能被继续、复查和复盘。

## 8. 和 AI 产品经理方法的对应关系

| AI PM 技巧 | 在项目里的落地 |
| --- | --- |
| 用户画像约束 scope | 聚焦 A-Level / CIE 数学学生和 1v1 老师，砍掉泛教育功能 |
| 显式目标函数 | 「30 秒内最高正确率」驱动多 agent、早返回和 SSE |
| 风险矩阵 | 低置信、低画质、复杂步骤、模型分歧都会升级或 needs_review |
| 递进式交付 | 先 mark-scheme grounding，再 agent_step replay，再视觉 runner，再 Large PDF |
| Agent 方法论 | Superpowers 把 brainstorm、spec、plan、subagent、review、verification 固化成流程 |
| 证据驱动验收 | pytest、build、browser screenshot、DOM proof、SSE sample |
| 复盘沉淀 | durable lessons 写入 `agent_workflow/knowledge.md`，避免下次重复踩坑 |

## 9. 这套方法为什么有效

Agent 最大的问题不是不会写代码，而是容易：

- 忘记之前的产品取舍。
- 误改不属于它的文件。
- 把技术完成误当成产品完成。
- 缺少真实运行证据。
- 在长任务中丢失上下文。

这个 harness 的作用就是把这些风险变成流程：

```text
Spec
  -> Plan
  -> Bounded implementation
  -> Test / screenshot / evidence
  -> Review
  -> Progress note
  -> Durable lesson
```

最终效果是：agent 不只是帮我写代码，而是按我设定的产品目标、工程边界和验收证据持续推进项目。

## 10. 可以复用到其他 AI 项目的模板

如果要把这套方法迁移到别的项目，可以保留这些文件形态：

- `AGENCY.md`：项目总规则和目录地图。
- `spec/acceptance.md`：验收标准。
- `agent_workflow/prd.json`：任务 backlog 和状态机。
- `agent_workflow/progress.md`：短期进度。
- `agent_workflow/knowledge.md`：长期知识。
- `docs/decisions/ADR-xxx.md`：为什么采用某种 agent workflow。
- `scripts/agent_workflow.py`：最小可运行的状态更新工具。

一句话总结：把 agent 当成执行团队，而不是一次性代码生成器；AI PM 的工作就是定义目标、边界、验收和反馈循环。
