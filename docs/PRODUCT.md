# 产品思路

## 一句话目标

A-Level Assistant 要把一次批改结果变成学生下一步能执行的学习动作。

## 产品原则

- 让学生感觉自己被指导，而不是被审判。
- 每一次批改都必须导向一个具体的下一步。
- AI 透明度的目标是建立信任，不是暴露内部推理。
- 系统不确定时要承认不确定，并让学生或老师确认。
- 只要能匹配 Past Paper，就优先使用 Mark Scheme grounded grading。

## 面向谁

### 学生

学生真正关心的是：

- 我哪几题错了？
- 我的推理在哪一步断了？
- 这是概念问题、代数失误、漏条件，还是答案识别不清？
- 我今晚应该先复习什么？
- 我应该再做哪几道类似题？

### 老师 / Tutor

老师真正关心的是：

- 哪些题需要人工复核？
- 哪些知识点反复薄弱？
- 哪类错误在学生中高频出现？
- AI 的判断哪里可靠，哪里需要老师介入？

## 核心产品形态

产品不应该停在“AI 能批改作业”。

更有价值的闭环是：

```text
批改 -> 诊断 -> 推荐练习 -> 再批改 -> 看进步
```

这个闭环是它区别于普通拍照批改工具的关键。

## 两条批改路径

### 路径 A：Past Paper 匹配批改

适用于系统能识别出 Cambridge 9709 的 paper/question。

```text
上传 -> 识别 paper -> 匹配题库 -> 找 mark scheme -> 对照批改 -> 解释扣分点 -> 推荐练习
```

价值：

- 更快；
- 更准；
- 更少幻觉；
- 老师更容易信任；
- 更容易按 topic 和 paper 推荐相似题。

### 路径 B：开放 AI 批改

适用于 paper context 缺失或不可靠的情况。

例如：

- 老师自定义作业；
- 练习册题；
- 裁剪过的截图；
- 只有答案没有题目；
- paper 匹配置信度低。

```text
分题 -> 提取答案 -> 批改 -> 投票/校验 -> 反馈 -> 询问是否推荐类似题
```

系统应该先尝试 Past Paper 匹配，但不能强迫学生必须上传整套卷子或封面。

## 练习推荐规则

推荐系统要保守，宁可先问，也不要硬猜。

### 自动推荐

适用于：

- 已确认是真题；
- 批改使用了 Mark Scheme context；
- topic 在当前 P1-P6 题库范围内；
- 系统置信度足够高。

### 先询问再推荐

适用于：

- 学生只上传了一张题图；
- 上传的是老师自定义作业；
- paper 匹配为中等置信度；
- 系统检测到可能 topic，但还不够确定。

推荐文案应该像学习助教，而不是系统日志：

```text
我检测到这题像是 P1 · quadratics。要不要再做 2-3 道类似题来确认这个点？
```

### 不推荐

适用于：

- 没有可靠 topic；
- 检测到的 topic 不在当前题库；
- paper 超出 P1-P6；
- 只有答案页，缺少题目上下文。

不推荐时要说明原因，而不是假装系统知道。

## 当前 MVP 能力

当前 `main` 已支持：

- 推荐请求/响应 contract；
- 后端推荐模式决策；
- 从 summary、knowledge tags、错题、未作答题推导 topic；
- P1-P6 题库边界处理；
- 跨多个薄弱 topic 补足推荐数量；
- 前端从批改结果推导推荐上下文；
- 结果页练习推荐 UI；
- ask-first 确认流程；
- 内联作答与提交；
- 根据作答结果调整下一题；
- replay 页面用于稳定人工测试和视觉验收。

## UI 方向

界面应该像高级学习工作台：

- 白色 / slate 作为基础；
- 蓝色用于主操作；
- 绿色、红色、琥珀色只表达语义状态；
- 卡片半径克制；
- AI workflow 可见但不喧宾夺主；
- 学生界面不展示 `think / act / observe / decide / final`；
- 错题反馈要可行动，不要打击人。

## 仓库里要容易找到什么

- 产品门面：[README.md](../README.md)
- 产品思路：[docs/PRODUCT.md](./PRODUCT.md)
- 开发路线：[docs/ROADMAP.md](./ROADMAP.md)
- 验收标准：[spec/acceptance.md](../spec/acceptance.md)
- UI 和 Agent 规格：[spec/product-ui-agent-spec.md](../spec/product-ui-agent-spec.md)
- 后端推荐编排器：[api/practice_orchestrator.py](../api/practice_orchestrator.py)
- 前端练习组件：[frontend/src/components/practice/PracticeRecommendations.tsx](../frontend/src/components/practice/PracticeRecommendations.tsx)
