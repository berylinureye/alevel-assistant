# 练习编排器 MVP 设计规格

日期：2026-06-22

## 目标

把批改从“一次性纠错报告”升级成学习闭环：

批改学生作业 → 诊断最该补的薄弱点 → 推荐练习 → 学生作答 → 再批改 → 根据新结果调整下一题。

这个版本的重点不是做一个很复杂的学习系统，而是先证明一个核心产品价值：**AI 不只是告诉学生错了什么，还能告诉学生下一步该练什么。**

## 产品原则

产品要让学生感觉自己被指导，而不是被审判。

每一次批改结果都必须导向一个具体学习动作。

AI 透明度的目标是建立信任：告诉学生“为什么推荐这道题”，而不是展示模型内部日志。

## MVP 入口

第一版从批改结果页进入。

学生上传作业或 Past Paper，批改完成后，在结果页的学习诊断下面出现 `下一步练习` 区块。学生可以直接从本次批改暴露出的薄弱知识点开始练习。

这个入口优先于单独做一个“学习计划页”，因为它离学生刚刚犯错的时刻最近，也最容易让学生理解：“我现在该补什么？”

## 现有基础

仓库里已经有一些可以复用的基础，不需要从零做：

- 批改结果的每题数据里已有 `knowledge_tags`、`syllabus_topics`、`error_type`、`score`、`full_score`、`needs_review`。
- 总结数据里已有 `priority_topics` 和 `knowledge_tags_summary`。
- 题库模型已经支持 `topic`、`subtopic`、`difficulty`、`tags`、`marking_points`、`common_errors`。
- 后端已有 `/questions/random` 和 `/questions/submit-answer`。
- 前端已有练习模式、答案输入、练习结果和练习总结组件。

MVP 应该优先复用这些模块，而不是另起一套练习系统。

## 用户流程

1. 学生上传作业并获得批改结果。
2. 系统先从 `summary.priority_topics` 找最重要薄弱点；如果没有，再从错题的 `knowledge_tags` 中统计。
3. 结果页显示 `下一步练习`，最多展示 3 个推荐：
   - `基础修复`：同知识点，低难度。
   - `巩固练习`：同知识点，中等难度。
   - `真题风格`：同知识点，高难度或 exam-style 来源。
4. 学生点击 `开始练习`。
5. 题目以内联面板打开，不跳走批改结果页。
6. 学生提交答案。
7. 系统复用 `/questions/submit-answer` 批改答案。
8. 面板显示正确性、得分、简短反馈和下一步动作：
   - 如果高分做对：推荐更难的同知识点题。
   - 如果部分正确：推荐另一道中等难度同知识点题。
   - 如果做错：推荐更基础的题，或提示先回看讲解。
9. 当前 session 记录已推荐和已完成题目，避免立刻重复推荐。

## 推荐策略

### 输入数据

推荐器使用这些输入：

- `PageSummary.priority_topics`
- 错题或部分正确题的 `QuestionResult`
- `knowledge_tags`
- `error_type`
- `score / full_score`
- `needs_review`
- 题库里的 `topic / subtopic / difficulty / tags`

### 薄弱点选择

优先级如下：

1. 如果 `summary.priority_topics[0]` 存在，优先用它。
2. 否则统计错题里出现最多的 `knowledge_tags`。
3. 如果标签也不足，用 `error_type` 映射到宽泛 topic。
4. 如果完全无法判断 topic，显示明确 fallback，不假装知道学生薄弱点。

### 题目选择

对每个薄弱 topic，通过 `/questions/random` 请求候选题：

- `topics`：选中的 topic 或映射后的 topic key。
- `exclude_ids`：当前 session 已推荐或已完成的题目 ID。
- 难度分层：
  - 基础修复：`1-2`
  - 巩固练习：`3`
  - 真题风格：`4-5`
- `count`：一次请求足够多候选题，用于填满 3 张推荐卡。

如果精确 topic 找不到题，放宽到父级 topic 或相关 tag。

如果仍然没有真实题目，显示禁用态 fallback 卡片，说明“当前题库还缺少这个知识点的已标注练习题”，不要展示假推荐。

## 数据结构

### 前端推荐视图模型

```ts
interface PracticeRecommendation {
  id: string
  question_id: number | null
  topic: string
  subtopic?: string | null
  difficulty: "foundation" | "consolidation" | "exam-style"
  title: string
  reason: string
  source_label?: string
  unavailable?: boolean
}
```

### 当前练习闭环状态

```ts
interface PracticeLoopState {
  weak_topics: string[]
  recommended_ids: number[]
  completed_ids: number[]
  current_question_id?: number
  last_result?: {
    question_id: number
    is_correct: boolean
    score: number
    full_score: number
    error_type: string | null
  }
}
```

第一版可以只放在 React state 里。

长期 mastery profile、跨天记忆、间隔复习都放到后续阶段。

## UI 设计

视觉风格要和当前批改页保持一致：

- 白色面板
- slate 文字
- blue accent
- 轻边框
- 紧凑卡片
- 不做炫技 dashboard

`下一步练习` 放在学习诊断之后。每张推荐卡展示：

- 推荐类型
- topic / subtopic
- 难度标签
- 一句话推荐理由
- 题目来源信息
- `开始练习` 按钮

学生开始练习后，用内联面板显示题目和答题区，不跳转页面。体验上应该像批改结果自然延伸出了下一步练习。

## Agentic Loop 的呈现方式

不要在学生界面显示原始 `think / act / observe`。

学生看到的是学习语言：

- `定位弱点`
- `选择练习`
- `提交作答`
- `批改反馈`
- `调整下一题`
- `总结进步`

内部可以对应到 agentic loop：

- observe：读取批改结果和练习结果。
- think：判断薄弱 topic 和难度。
- act：从题库获取下一题。
- observe：批改学生新提交的答案。
- decide：升难度、重复巩固、降难度或建议回看讲解。
- final：总结下一步学习动作。

## 题库打标策略

第一版不要求先完整人工打标题库。

MVP 采用渐进打标策略：

1. 先使用题库已有的 `topic`、`subtopic`、`difficulty`、`tags`。
2. 建一个小型 alias map，把批改输出的 `knowledge_tags` 映射到题库 topic。
3. 如果推荐失败是因为标签缺失，记录缺失的 topic key。
4. 后续对高频缺失 topic 或高频推荐题做 AI 辅助批量打标。
5. 只对高频推荐或低置信度题目做人审。

这样不会因为“题库标签还没完美”而卡住产品闭环。

## 错误和 fallback 状态

- 没找到薄弱点：显示 `本次表现较均衡`，推荐综合练习。
- 找到 topic 但题库没有匹配题：显示该薄弱点，并说明题库需要更多已标注题目。
- 提交练习答案失败：保留学生答案，提供重试。
- AI 置信度低或 `needs_review` 为 true：建议老师复核后再进入自适应练习。
- 避免重复推荐：排除当前 session 已完成和已展示过的题目 ID。

## MVP 不做什么

第一版不做：

- 跨天长期 mastery profile。
- 完整间隔复习系统。
- 全自动题库重打标系统。
- 默认用 AI 生成新题。
- 独立学习计划页。
- 学生可见的复杂多 agent 调试日志。

## 实施阶段

### Phase 1：推荐卡片

批改完成后，根据当前 session 结果和 `/questions/random` 显示 `下一步练习`。

### Phase 2：内联练习

学生可以在结果页内完成一道推荐题，并通过 `/questions/submit-answer` 批改。

### Phase 3：自适应下一步

练习批改后，根据正确性和得分推荐下一题或建议回看讲解。

### Phase 4：轻量掌握度记忆

把 topic 尝试记录存到本地或现有 history/feedback 存储里，用于避免重复和显示进步。

## 验收标准

- 一次批改中存在错题或部分正确题时，结果页能显示至少一个真实练习推荐。
- 每条推荐都显示 topic、难度和与本次错因相关的推荐理由。
- 点击推荐后，在当前结果页打开内联练习面板，不丢失批改结果。
- 提交答案后调用 `/questions/submit-answer` 并展示批改结果。
- 练习批改后展示下一步动作：升难度、继续巩固、降难度或回看讲解。
- 当前 session 内不会重复推荐已完成题目。
- 如果没有真实题目可推荐，UI 显示明确 fallback，不展示假题。
- 验收必须包含真实浏览器截图或 DOM 证据，不能只靠日志。

## 测试计划

- 用 `PageSummary` 和 `QuestionResult` fixture 测试推荐推导逻辑。
- 用 replay/component 测试 `下一步练习` 面板。
- 测试 `/questions/random` 能按选中 topic 返回候选题。
- 桌面和移动端做浏览器视觉验收，确保推荐卡片可见且无横向溢出。
- 回归检查：没有薄弱 topic 时，批改结果仍能正常渲染并显示合理 fallback。
