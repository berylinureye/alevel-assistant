# Project Docs

这个文件夹是 A-Level Assistant 的 GitHub 阅读入口。你可以把它当成项目展示页的目录：先看产品是什么，再看可信度怎么做，最后看我是如何用 agent 和 Superpowers 插件把开发效率拉起来的。

## 推荐阅读顺序

| 顺序 | 文档 | 读完你会知道什么 |
| --- | --- | --- |
| 1 | [项目首页](../README.md) | 项目定位、当前能力、核心模块和本地运行方式 |
| 2 | [产品思路](../docs/PRODUCT.md) | 为什么它不是普通拍题工具，而是批改到练习的学习闭环 |
| 3 | [规则校验与确定性兜底](../docs/rule-based-verification.md) | OCR、SymPy、概率、统计、分数化简和多 agent 投票如何共同提升可信度 |
| 4 | [Agent 驱动开发与提效系统](../docs/agent-driven-development.md) | 如何把 PRD、验收标准、任务记忆、子 agent 分工变成开发 harness |
| 5 | [Superpowers 插件使用说明](../docs/superpowers-plugin-workflow.md) | Superpowers 如何把 brainstorm、spec、plan、subagent、review、verification 固化成流程 |
| 6 | [开发路线](../docs/ROADMAP.md) | 当前 main 已经包含什么，下一阶段要补什么 |

## 一句话项目介绍

A-Level Assistant 是一个面向 Cambridge A-Level Mathematics 的 AI 学习诊断系统。学生上传作业图片或真题 PDF 后，系统会先尝试匹配 Past Paper 和 Mark Scheme，再结合多模型批改、确定性校验和练习推荐，返回逐题得分、错因诊断、复核风险和下一步练习动作。

它的目标不是给一个“看起来很聪明”的答案，而是把一次批改变成可执行的学习闭环：

```text
上传 -> 识别题目 -> 匹配真题/开放批改 -> 校验风险 -> 学习诊断 -> 推荐练习 -> 再批改
```

## 我想突出展示的三件事

### 1. 不是单纯依赖 LLM

LLM 负责读图、理解题意和生成教学反馈；确定性工具负责守住数学事实底线。项目里有多层兜底：

- OCR 与 Vision 交叉校验，减少数字识别错误。
- SymPy 检查代数、微积分和表达式等价。
- 概率 verifier 用 LLM 抽取事件、Python 精确计算分数。
- 统计 verifier 用公式重算均值、标准差、四分位数和 IQR。
- 分数化简 verifier 把 A-Level presentation mark 规则编码进去。
- 多 agent voting 在高风险题上做模型间交叉检查。

这套设计体现的是一个 AI 产品判断：模型不可靠不是异常，而是架构前提。

### 2. 不是“批完就结束”

产品目标是从作业批改继续走到下一步练习。系统会根据错题、知识标签、paper context 和推荐模式判断：

- 可以直接推荐类似题；
- 信息不足时先询问学生；
- 题库不支持时明确说明，不硬猜。

这对应 AI PM 的一个关键动作：把模型输出变成用户流程，而不是只展示内容。

### 3. Agent 不是随便帮我写代码

我把开发过程也产品化了：

- `AGENCY.md` 记录项目总规则。
- `spec/acceptance.md` 记录验收标准。
- `agent_workflow/prd.json` 记录任务状态和验收条件。
- `agent_workflow/progress.md` 记录短期进度。
- `agent_workflow/knowledge.md` 记录长期经验。
- Superpowers 插件负责把 brainstorm、spec、plan、subagent、review 和 verification 串起来。

这样 agent 不只是一次性代码生成器，而是被流程、文件边界和验收证据约束的执行团队。

## 文件夹地图

```text
project-docs/
  README.md                        这个 GitHub 展示入口

docs/
  PRODUCT.md                       产品定位和学习闭环
  ROADMAP.md                       当前 main 能力和后续路线
  rule-based-verification.md       规则校验与确定性兜底
  agent-driven-development.md      Agent 驱动开发方法
  superpowers-plugin-workflow.md   Superpowers 插件使用说明
  question-bank-proposal.md        题库系统方案

spec/
  acceptance.md                    验收标准
  product-ui-agent-spec.md         UI 和 agent trace 规格
  long-running-agent-workflow.md   长任务 agent workflow
  large-pdf-mode.md                Large PDF Mode 设计

agent_workflow/
  README.md                        长任务开发工作台说明
  prd.json                         任务 backlog 和状态
  progress.md                      短期进度
  knowledge.md                     长期项目知识
```

## 适合面试/展示时怎么讲

可以用三段话讲清楚：

1. **产品层**：我做的是 A-Level 数学学习诊断，不是通用聊天机器人。它从上传作业开始，走到批改、错因、弱点和下一步练习。
2. **可信度层**：我没有把数学判断全交给 LLM，而是用 OCR、SymPy、概率/统计 verifier、分数化简规则和多模型投票做兜底。
3. **开发效率层**：我用 Superpowers 插件和自己的 `agent_workflow/` 把 AI PM 的 PRD、验收、任务拆解、子 agent 分工和复盘沉淀变成了可重复开发流程。

## 最短浏览路径

如果只想快速了解项目，按这个顺序点：

1. [README](../README.md)
2. [规则校验与确定性兜底](../docs/rule-based-verification.md)
3. [Agent 驱动开发与提效系统](../docs/agent-driven-development.md)
4. [Superpowers 插件使用说明](../docs/superpowers-plugin-workflow.md)
