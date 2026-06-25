# 规则校验与确定性兜底

这个项目的核心判断是：LLM 很适合读题、理解上下文和生成解释，但不应该被单独信任来完成所有数学事实判断。A-Level 数学批改里，一个数字、一个符号、一个未化简分数都可能改变得分，所以系统把「模型判断」和「规则校验」拆开。

这里的「Simblab / Symbolab 式兜底」在代码里主要落成了 SymPy 和自写 verifier：它们不负责教学表达，只负责用确定性方式检查 LLM 容易出错的部分。

## 总体思路

```text
LLM / Vision model
  -> 擅长：读图、切题、识别学生步骤、判断作答意图、生成反馈

Rule / deterministic verifier
  -> 擅长：公式计算、表达式等价、概率枚举、统计数值、分数化简、超时可控

Final result
  -> LLM 给出教学判断
  -> verifier 校准数学事实
  -> confidence / needs_review 暴露风险
```

产品上这不是「多加几个工具」，而是把 AI 不可靠当作前提来设计。模型负责开放问题，规则负责封闭问题。

## 1. OCR + Vision 交叉校验

相关代码：

- `pipeline/segmenter.py`
- `utils/image_utils.py`
- `parser/pdf_parser.py`

整页作业进入系统后，Vision/Base 模型一次性完成切题和字段提取，输出题号、题干、学生答案、步骤、分值、页码、图表类型等结构化 JSON。与此同时，专用 OCR 模型并行抽取纯文本。当前 OCR 首选 Mathpix Convert API；如果 Mathpix 没返回可用结果，可回到本地 tesseract 作为弱探针。

关键取舍：

- 切题和提取合并成一次 Vision 调用，避免 N+1 次模型请求。
- OCR 与 Vision 并行，墙钟时间接近 `max(vision, ocr)`，而不是两者相加。
- Mathpix OCR 只有在文本看起来包含真实题干语言（如 find/show/calculate/given 等）时，才作为二级 prompt hint 交给 segmenter。
- 如果 OCR 只读到公式和手写步骤，系统不会把它当作题干来源，避免模型因为 OCR 没题干而清空或编造 `question_text`。
- OCR 只用于保守复核数字、符号、题号和手写步骤，不重写结构；旧的全量 OCR 数字回写仍由 `SEGMENT_OCR_REWRITE` 显式开关控制，默认关闭。
- Segmenter prompt 明确要求「照抄学生错误」，不能帮学生把错题修正成标准答案。

为什么这很重要：数学题里数字识别错一个，整题就可能错；但如果 OCR 擅自重排结构，也会破坏题目和答案的对应关系。因此 OCR 是校验层，不是主控层。

2026-06-25 的回归对比使用 `static/demo-input.jpg` 这张手写-only 图验证了这个 guard：未加 guard 时，Mathpix 手写 OCR 会干扰主模型，导致空题干或 final answer 被截成中间方程；加 guard 后，3 次新路径均保留空题干（符合图片无打印题干的事实），并且 d 问交点答案 `x = -1/6, y = 9/8` 命中 3/3，旧路径为 2/3。完整本地报告保存在 `reports/ocr_compare/demo_input_guarded_stability_20260625_115621.json`。

## 2. 路由规则：先判断风险，再决定是否升级

相关代码：

- `router/context.py`
- `router/rules.py`
- `pipeline/pipeline.py`

系统不会把所有题都送进最贵、最慢的批改路径。Base grader 先给出初步结果，同时构造 `RouteContext`。规则层全量检查风险信号：

- 提取置信度低。
- 图片质量差。
- Grader 自己标记 needs_review。
- 批改置信度低。
- 学生步骤过长。
- 复杂表达式等价性不确定。

任一规则触发，就升级到更强的 review / multi-agent 路径。每条规则返回可解释 reason，方便后续复盘「为什么这题被升级」。

AI PM 技巧：这是成本和质量的双目标优化。简单题不浪费慢模型，危险题不假装确定。

## 3. SymPy：校准代数、微积分和表达式等价

相关代码：

- `verifier/math_verifier.py`
- `grader/solution_verifier.py`
- `utils/latex_simplify.py`

LLM 在微积分和代数上常见问题是「过程看起来合理，但某一步算错」。SymPy 层做三件事：

- 把常见 LaTeX 形式转换成 SymPy 可解析表达式。
- 用 `simplify(a - b) == 0` 判断学生答案和标准答案是否等价。
- 对复杂计算加进程级超时，避免 verifier 卡死主请求。

设计原则：

- SymPy 成功时可以 override 或校准 LLM。
- SymPy 失败时返回 inconclusive，不让工具失败拖垮批改流程。
- LLM 仍负责「步骤是否完整、是否该给部分分」这类教学判断。

这就是「工具兜底而不是工具替代模型」。

## 4. 概率 verifier：LLM 抽取，Python 精确计算

相关代码：

- `verifier/probability_verifier.py`

条件概率、离散分布和超几何题是 LLM 容易系统性出错的区域。这里的做法是把任务拆成两半：

- LLM 只抽取样本空间、事件 A、事件 B、目标类型。
- Python 用 `Fraction` 和组合数精确计算概率。

支持的模式包括：

- `P(A)`
- `P(A | B)`
- `P(A and B)`
- 离散分布枚举
- 超几何组合数表达式解析

AI PM 技巧：让模型做它擅长的语义抽取，让程序做它擅长的精确计算。

## 5. 统计 verifier：避免模型算术幻觉

相关代码：

- `verifier/statistics_verifier.py`

统计题常见风险不是概念理解，而是多步算术和数据选择。Verifier 会先让模型抽取结构化数据，再用 Python 计算：

- 合并均值和标准差。
- 分组数据均值和标准差。
- 原始数据 median / quartiles / IQR。
- summary stats 中的 mean / variance / standard deviation。

它还会尝试多种四分位数 convention，减少因为考试/教材口径差异导致的误判。

## 6. 分数化简 verifier：把阅卷规则编码进去

相关代码：

- `verifier/simplification_verifier.py`

A-Level Mark Scheme 里，答案数值正确但分数没化简可能会扣 presentation mark。例如 `24/210` 应化简为 `4/35`。这个问题交给 LLM 检查既贵又不稳定，所以直接用 `gcd` 扫描学生答案和最后一步 working。

策略：

- 只在当前判对时追加 presentation issue。
- 大分值题可扣 1 分，小分值题只提醒。
- 同步写入 `short_feedback`、`student_feedback` 和 detail deductions。

这类规则的价值在于：它把具体考试阅卷标准变成可重复执行的产品能力。

## 7. Multi-Agent voting：模型之间互相校验

相关代码：

- `grader/multi_agent.py`
- `grader/multi_agent_config.py`

当规则层判断一题有风险时，系统使用多个模型并行批改，再进行投票：

- Fast tier 优先返回。
- Accurate tier 作为仲裁。
- 前 3 个结果在正误和分数上达成一致就 early return。
- 分数方差过大时降低 confidence 或标记 needs_review。
- GLM 等低 RPM 模型通过共享锁限流，避免并发 429。

这是一种「模型校验模型」的兜底。它不能替代 SymPy 这类确定性工具，但可以发现单模型偶发幻觉和厂商 API 波动。

## 8. 用户可见的风险表达

相关代码：

- `frontend/src/components/ThinkingPanel.tsx`
- `frontend/src/components/QuestionCard.tsx`
- `frontend/src/components/SkeletonQuestionCard.tsx`
- `spec/acceptance.md`

校验结果不会只留在日志里。前端会展示：

- 提取置信度。
- 批改置信度。
- 是否建议老师复核。
- agent_step 的学习化进度标签。
- 错因、弱点主题和下一步练习。

重要的是，学生界面不显示 raw `think / act / observe` 或隐藏推理，只显示安全、短小、可行动的状态。

## 方法论总结

这套规则校验体系体现了几个 AI 产品经理技巧：

- 把不可控风险拆成可观测字段：confidence、needs_review、route reason。
- 把模型能力边界写进产品架构，而不是寄希望于 prompt 一次解决。
- 把高频、封闭、可计算的问题交给程序。
- 把低频、开放、解释型的问题交给 LLM。
- 所有兜底都要失败可恢复：verifier 失败不能让主流程 500。

一句话：LLM 负责像老师一样理解题目，规则层负责像计算器和阅卷标准一样守住底线。
