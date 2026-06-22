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

学生上传作业或 Past Paper，批改完成后，在结果页的学习诊断下面出现 `下一步练习` 区块。这个区块不一定直接给题：已确认 Past Paper 时自动推荐；单题照片、自定义作业或低置信识别时，先询问学生是否要练类似题。

这个入口优先于单独做一个“学习计划页”，因为它离学生刚刚犯错的时刻最近，也最容易让学生理解：“我现在该补什么？”

## 现有基础

仓库里已经有一些可以复用的基础，不需要从零做：

- 批改结果的每题数据里已有 `knowledge_tags`、`syllabus_topics`、`error_type`、`score`、`full_score`、`needs_review`。
- 总结数据里已有 `priority_topics` 和 `knowledge_tags_summary`。
- 题库模型已经支持 `topic`、`subtopic`、`difficulty`、`tags`、`marking_points`、`common_errors`。
- 题库分类覆盖 CIE 9709 Mathematics 的 P1-P6，但推荐时仍必须尊重本次上传的 paper 上下文。
- 后端已有 `/questions/random` 和 `/questions/submit-answer`。
- 前端已有练习模式、答案输入、练习结果和练习总结组件。

MVP 应该优先复用这些模块，而不是另起一套练习系统。

## 用户流程

1. 学生上传作业并获得批改结果。
2. 系统判断本次上传是否有明确 Past Paper 上下文：
   - 如果学生上传的是完整试卷、试卷页、封面页，或系统已确认 paper code / question number，则进入自动推荐。
   - 如果学生只是拍了一道题、上传老师自定义作业，或 paper 上下文不确定，则进入询问式推荐。
3. 自动推荐场景下，系统先从 `summary.priority_topics` 找最重要薄弱点；如果没有，再从错题的 `knowledge_tags` 中统计。
4. 自动推荐场景下，结果页显示 `下一步练习`，最多展示 3 个推荐：
   - `基础修复`：同知识点，低难度。
   - `巩固练习`：同知识点，中等难度。
   - `真题风格`：同知识点，高难度或 exam-style 来源。
5. 询问式推荐场景下，结果页不直接塞 3 道题，而是显示一个轻量 agent 提问：
   - `我检测到这题可能属于 P3 微分 / P5 正态分布。要不要再做 2-3 道类似题？`
   - 学生点击 `需要` 后，系统再从题库里找同 paper 或同 topic 的题。
   - 学生点击 `暂时不用` 后，只保留批改反馈和学习诊断。
6. 学生点击 `开始练习`。
7. 题目以内联面板打开，不跳走批改结果页。
8. 学生提交答案。
9. 系统复用 `/questions/submit-answer` 批改答案。
10. 面板显示正确性、得分、简短反馈和下一步动作：
   - 如果高分做对：推荐更难的同知识点题。
   - 如果部分正确：推荐另一道中等难度同知识点题。
   - 如果做错：推荐更基础的题，或提示先回看讲解。
11. 当前 session 记录已推荐和已完成题目，避免立刻重复推荐。

## 推荐触发路由

推荐题目之前必须先判断上传上下文。MVP 不把所有批改结果都自动变成练习推荐。

### 自动推荐

满足任一条件时，可以自动展示 `下一步练习`：

- 学生明确选择了 Past Paper / 真题卷。
- 上传内容识别到了可信的 paper code、paper number、variant 或 question number。
- 学生已经确认了系统识别出的试卷。
- 本次批改来自系统题库里的题目或 mark scheme grounded grading。

自动推荐的候选题必须优先来自相同 paper family 或相同 syllabus topic。不能因为题库里有相似关键词，就跨到不相关 paper。

### 询问式推荐

满足任一条件时，不自动推荐题目，而是先让 agent 询问学生：

- 学生上传的是单题照片。
- 学生上传的是老师自定义作业。
- 系统只能识别到数学 topic，但不能确认 paper。
- paper 匹配置信度为中或低。
- 批改结果 `needs_review` 为 true。

询问式推荐的文案要像学习助手，而不是系统权限弹窗：

`我检测到这题像是 P5 Normal Distribution。要不要再做 2-3 道类似题来确认这个点？`

学生确认后，推荐器再调用题库；学生拒绝后，不再打扰。

### 不推荐

满足任一条件时，不推荐题目，只显示原因：

- 没有足够信息判断 topic。
- 题目可能不属于 CIE 9709 Mathematics P1-P6。
- 题库没有真实候选题。
- AI 对识别结果低置信，且学生没有确认。

这种状态必须说清楚：`这次我还不能可靠地为你匹配练习题`，不要展示假题，也不要用生成题替代题库题。

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
- 上传意图：Past Paper、单题照片、自定义作业、不确定
- paper 识别结果：paper number、question number、match confidence、是否经过学生确认

### 薄弱点选择

优先级如下：

1. 如果 `summary.priority_topics[0]` 存在，优先用它。
2. 否则统计错题里出现最多的 `knowledge_tags`。
3. 如果标签也不足，用 `error_type` 映射到宽泛 topic。
4. 如果完全无法判断 topic，显示明确 fallback，不假装知道学生薄弱点。

### 题目选择

对每个薄弱 topic，通过 `/questions/random` 请求候选题：

- `topics`：选中的 topic 或映射后的 topic key。
- `paper_num`：如果本次已确认 paper，优先限制在对应 P1-P6；如果只是拍题识别，则只在学生确认后使用。
- `exclude_ids`：当前 session 已推荐或已完成的题目 ID。
- 难度分层：
  - 基础修复：`1-2`
  - 巩固练习：`3`
  - 真题风格：`4-5`
- `count`：一次请求足够多候选题，用于填满 3 张推荐卡。

如果精确 topic 找不到题，可以在同一推荐范围内放宽到父级 topic 或相关 tag。已确认 paper 时，放宽范围仍应优先留在同 paper family。

如果仍然没有真实题目，显示禁用态 fallback 卡片，说明“当前题库还缺少这个知识点的已标注练习题”，不要展示假推荐。

### Paper 范围策略

题库可以覆盖 P1-P6，但推荐不能无条件跨 paper。

- 已确认 Past Paper：优先从同 paper number 和同 topic 里找题；不足时可以放宽到同 topic 的其他年份或 variant。
- 只拍到单题：先识别可能属于哪个 paper/topic，再询问学生是否需要类似题；学生确认后才能推荐。
- 自定义作业：可以根据 topic 推荐，但 UI 要说明“这是按题型匹配的练习，不是同一套 Past Paper 的题”。
- 识别到 P1-P6 之外：不推荐题库题，只给学习诊断和人工确认建议。
- 不能确认 paper 但 topic 明确：使用询问式推荐，不自动展示 3 张题卡。

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
  trigger: "auto" | "ask_first" | "unavailable"
  paper_num?: 1 | 2 | 3 | 4 | 5 | 6 | null
  requires_confirmation?: boolean
}
```

### 推荐触发上下文

```ts
interface PracticeRecommendationContext {
  upload_intent: "past_paper" | "single_question_photo" | "custom_homework" | "unknown"
  paper_num?: 1 | 2 | 3 | 4 | 5 | 6 | null
  question_number?: string | null
  match_confidence?: "high" | "medium" | "low" | null
  confirmed_by_user: boolean
  recommendation_mode: "auto" | "ask_first" | "none"
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

`下一步练习` 放在学习诊断之后。

自动推荐时，每张推荐卡展示：

- 推荐类型
- topic / subtopic
- 难度标签
- 一句话推荐理由
- 题目来源信息
- `开始练习` 按钮

询问式推荐时，先展示一张轻量提问卡：

- 检测到的 paper/topic
- 匹配置信度：高 / 中 / 低
- 为什么这样判断
- `给我 2-3 道类似题` 按钮
- `暂时不用` 次级按钮

学生开始练习后，用内联面板显示题目和答题区，不跳转页面。体验上应该像批改结果自然延伸出了下一步练习。

## Agentic Loop 的呈现方式

不要在学生界面显示原始 `think / act / observe`。

学生看到的是学习语言：

- `定位弱点`
- `选择练习`
- `询问是否练习`
- `提交作答`
- `批改反馈`
- `调整下一题`
- `总结进步`

内部可以对应到 agentic loop：

- observe：读取批改结果和练习结果。
- think：判断薄弱 topic、paper 上下文和是否需要先询问学生。
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

- 没找到薄弱点：显示 `本次表现较均衡`。只有已确认 Past Paper 或学生明确请求练习时，才推荐综合练习。
- 找到 topic 但题库没有匹配题：显示该薄弱点，并说明题库需要更多已标注题目。
- 只拍到单题或自定义作业：不自动展示题卡，先询问学生是否需要类似题。
- 识别到 P1-P6 之外或非 CIE 9709 数学：不推荐题库题，只显示能力边界和人工确认建议。
- paper 识别置信度中/低：显示候选 paper/topic，让学生确认后再推荐。
- 提交练习答案失败：保留学生答案，提供重试。
- AI 置信度低或 `needs_review` 为 true：建议老师复核后再进入自适应练习。
- 避免重复推荐：排除当前 session 已完成和已展示过的题目 ID。

## MVP 不做什么

第一版不做：

- 跨天长期 mastery profile。
- 完整间隔复习系统。
- 全自动题库重打标系统。
- 默认用 AI 生成新题。
- 在没有学生确认的情况下，把单题照片强行匹配到某套试卷。
- 独立学习计划页。
- 学生可见的复杂多 agent 调试日志。

## 实施阶段

### Phase 1：推荐卡片

批改完成后，先判断推荐触发路由。已确认 Past Paper 场景显示 `下一步练习`；单题照片或自定义作业显示询问式推荐卡。

### Phase 2：内联练习

学生可以在结果页内完成一道推荐题，并通过 `/questions/submit-answer` 批改。

### Phase 3：自适应下一步

练习批改后，根据正确性和得分推荐下一题或建议回看讲解。

### Phase 4：拍题识别增强

对单题照片和自定义作业引入模型识别，判断可能的 paper/topic，并和学生确认是否需要相似题。

### Phase 5：轻量掌握度记忆

把 topic 尝试记录存到本地或现有 history/feedback 存储里，用于避免重复和显示进步。

## 验收标准

- 已确认 Past Paper 的批改中存在错题或部分正确题时，结果页能显示至少一个真实练习推荐。
- 单题照片或自定义作业不会自动展示题卡，而是先显示询问式推荐卡。
- 学生确认需要类似题后，系统能从题库里返回真实题目。
- 每条推荐都显示 topic、难度和与本次错因相关的推荐理由。
- 每条自动推荐都显示来源范围，例如同 paper、同 topic、同题型。
- 点击推荐后，在当前结果页打开内联练习面板，不丢失批改结果。
- 提交答案后调用 `/questions/submit-answer` 并展示批改结果。
- 练习批改后展示下一步动作：升难度、继续巩固、降难度或回看讲解。
- 当前 session 内不会重复推荐已完成题目。
- 如果没有真实题目可推荐，UI 显示明确 fallback，不展示假题。
- 如果识别到 P1-P6 之外或非 CIE 9709 数学，UI 明确说明当前题库不覆盖，不推荐题库题。
- 验收必须包含真实浏览器截图或 DOM 证据，不能只靠日志。

## 测试计划

- 用 `PageSummary` 和 `QuestionResult` fixture 测试推荐推导逻辑。
- 测试 Past Paper 场景走自动推荐，单题照片和自定义作业走询问式推荐。
- 测试 P1-P6 之外或低置信 paper 识别不会返回自动推荐。
- 用 replay/component 测试 `下一步练习` 面板。
- 测试 `/questions/random` 能按选中 topic 返回候选题。
- 桌面和移动端做浏览器视觉验收，确保推荐卡片可见且无横向溢出。
- 回归检查：没有薄弱 topic 时，批改结果仍能正常渲染并显示合理 fallback。
