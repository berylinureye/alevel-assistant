# A-Level Assistant 竞品分析

调研日期：2026-06-29

## 结论摘要

A-Level Assistant 不应该被定位成“海外版作业帮”或“又一个拍照搜题工具”。更准确的定位是：

> 面向 CAIE A-Level 数学的 mark-scheme-grounded grading and adaptive past-paper practice。

中文表达：

> 按 CAIE 真题评分标准批改的 A-Level 数学学习助手：拍照或 PDF 上传后，告诉学生每一步该得几分、为什么扣分、下一道该练什么。

核心判断：

- 海外头部作业产品强在“全科、快、拍照出答案、AI tutor”，但大多不解决 exam-board-specific marking。
- 国内头部搜题产品强在“题库、错题本、同步练、家长作业检查”，但主要服务国内 K12 教材体系。
- A-Level Assistant 的机会不在更宽，而在更准：围绕 CAIE Past Paper / Mark Scheme 做可信批改、错因诊断和下一步练习闭环。

## 我们的核心优势

### 1. Exam-board vertical：更窄，但更可信

竞品通常覆盖全年级、全科和泛作业场景，价值是“我能帮你搜到/解出这道题”。A-Level Assistant 聚焦 Cambridge A-Level Mathematics，核心价值是“我知道这份答案在 CAIE 标准里该怎么给分”。

这直接对应国际课程学生和 tutor 的真实问题：

- 这一步能不能拿 method mark？
- 最终答案对但过程跳步，会不会扣分？
- 漏写定义域、单位、化简，会扣哪一类分？
- 这题薄弱点应该映射到哪个 P1-P6 topic？

### 2. 批改学生过程，而不是只解原题

普通搜题工具通常擅长生成标准解法，但学生提交的是自己的过程。A-Level Assistant 的核心是保留学生原始步骤，对照 Mark Scheme 判断每一步是否给分。

这使产品从“答案工具”变成“批改工具”：

- 区分 M1/M2 method mark 和 A1/B1 accuracy mark。
- 识别分数未化简、单位缺失、定义域遗漏、步骤跳跃等细节失分。
- 输出得分、错因、薄弱知识点和复核风险。

### 3. 把 AI 风险产品化

AI 批改最怕的问题不是“不会讲”，而是“讲得很顺但判错”。A-Level Assistant 的可信度设计包括：

- Past Paper resolver：能匹配真题时优先用 Mark Scheme grounded grading。
- confidence / needs_review：不确定时暴露风险，而不是伪装确定。
- verifier：用 SymPy、统计、概率、分数化简等确定性校验约束 LLM。
- 多模型复核：降低单模型数学推理和 OCR 偶发误判。

这对 tutor 和高年级学生尤其重要：他们愿意接受 AI 辅助，但不会接受黑箱乱判。

### 4. 从批改闭环到练习闭环

成熟搜题产品已经证明，用户不会只满足于“看一眼答案”。更强的学习链路是：

```text
批改 -> 诊断 -> 推荐练习 -> 再批改 -> 看进步
```

A-Level Assistant 的 Practice Orchestrator 已支持：

- 自动推荐：真题匹配和 topic 高置信时，直接推荐真实题库题。
- ask-first：自定义作业或置信度不足时，先询问学生是否练这个知识点。
- none：没有可靠 topic 或题库覆盖时，不硬猜。
- 内联答题与再次评分：把一次批改变成下一轮练习。

### 5. 贴近 A-Level 真实材料形态

A-Level 学生真实上传材料不是只有一张干净题图，而是：

- full past paper PDF；
- partial paper pages；
- answer pages only；
- 老师自定义作业；
- 练习册截图；
- 裁剪过的题图。

因此产品必须支持图片、多图、PDF、Large PDF、选页处理、题目匹配和开放批改 fallback。这个真实场景适配，是泛搜题产品不容易深做的地方。

## 海外竞品

### 1. Gauth

定位：AI Study Companion，拍照解题、全科作业、AI tutor。

已做什么：

- 拍照上传题目，给 step-by-step 解答。
- 覆盖数学、科学、历史、写作等多学科。
- 提供 AI Live Tutor、白板、视频和学习工具。
- 在美国教育类榜单和作业帮助场景中仍有较高可见度。

没做什么或弱点：

- 重点是“解题”和“辅导”，不是 exam-board-specific grading。
- 不对齐 CAIE Mark Scheme 的 M/A/B 给分逻辑。
- 难以判断学生已有过程在考试里具体能拿几分。
- 面向全科场景，高阶数学和图像/图形题稳定性仍会受限。

对我们的启发：

- 不要正面拼“全科拍题”和“AI tutor 工具箱”。
- 要强调 CAIE Mark Scheme、逐步扣分、tutor 可复核和 Past Paper 练习闭环。

### 2. Photomath

定位：数学扫码解题器。

已做什么：

- 拍照识别数学题。
- 提供 step-by-step explanations。
- 支持多种解法、图形计算和动态讲解。
- 品牌认知强，数学解题心智稳定。

没做什么或弱点：

- 更像“标准解法生成器”，不是“学生答案批改器”。
- 不判断学生已经写下的步骤该得多少分。
- 不对齐 CAIE Past Paper / Mark Scheme。
- 对 tutor 需要的复核链路、评分依据、薄弱 topic 沉淀不够。

对我们的启发：

- 用户会默认期待数学题“能拍、能识别、能讲步骤”，这是基础门槛。
- 我们的差异必须放在“考试评分”和“错因诊断”，而不是只说“也能解题”。

### 3. Question.AI

定位：AI Homework Helper，泛全科作业助手。

已做什么：

- 支持图片或文档上传。
- 覆盖数学、英语、科学、历史等全科。
- 提供 AI 聊天、写作、翻译、学习工具。
- 多语言和泛学习助手属性明显。

没做什么或弱点：

- 产品边界很宽，专业课程和考试标准深度较弱。
- 更关注答案生成和解释，不强调标准化评分。
- 难以建立“这一步为什么扣一分”的考试级信任。

对我们的启发：

- 泛 AI 助手会越来越多，不能把自己做成一个宽而浅的聊天入口。
- 首页和核心流程必须持续锚定 A-Level 数学评分。

### 4. Brainly

定位：社区答案 + AI homework helper + expert verified answers。

已做什么：

- 拥有社区问答资产。
- 提供 AI 辅助、专家验证答案、tutor 和 textbook solutions。
- 适合学生搜索类似问题和参考解答。

没做什么或弱点：

- 社区答案质量和解释风格不完全稳定。
- 更偏“找解析”，不是“按考试标准批改我的答案”。
- 对老师来说，评分依据和风险提示不够结构化。

对我们的启发：

- 内容资产和题库很重要，但最终要服务“可验证的学习动作”。
- 我们应该让 tutor 看到系统为什么这么判，而不是只看到一段 AI 解释。

## 国内竞品

### 1. 作业帮

定位：国内 K12 作业检查、拍照搜题、AI 伴学平台。

已做什么：

- 拍照搜题和整页搜。
- 作业检查和批改。
- AI 答疑、作文批改、同步练习、视频讲解。
- 大规模题库和家长辅导场景。

没做什么或弱点：

- 主要服务国内 K12 教材与考试体系。
- 不面向 CAIE A-Level 的 syllabus、paper code、variant、Mark Scheme。
- 强在平台广度，不一定适合国际课程高年级数学的评分细节。

对我们的启发：

- 错题本、同步练、讲解和二次练习已经是成熟市场标配。
- 但我们应该把这些功能做成 A-Level Past Paper 语境，而不是国内教材语境。

### 2. 小猿搜题 / 小猿AI

定位：拍照解题、作业检查、AI 讲题、举一反三。

已做什么：

- 拍照搜题和视频答疑。
- 作业检查、错因分析、1 对 1 讲题。
- 举一反三、在线练习、错题本。
- 家长检查作业和学生自主学习两端覆盖。

没做什么或弱点：

- 主要围绕国内中小学作业场景。
- 不处理 CAIE Past Paper 的 mark allocation。
- 讲解和练习偏教材同步，而不是 paper/session/variant/topic 的国际考试结构。

对我们的启发：

- “错因分析 + 举一反三”是用户已经理解的价值表达。
- 我们可以借鉴这个心智，但要升级成“Mark Scheme 扣分点 + Past Paper 类题”。

### 3. 快对AI

定位：教辅答案、AI 解题、AI 工具箱、错题本。

已做什么：

- 教辅答案检索。
- AI 解题、作业检查、作文、翻译、扫描等工具。
- 错题本和学习资料沉淀。
- 在国内 AI 应用榜单中有较高活跃度。

没做什么或弱点：

- 产品很宽，容易成为工具集合。
- 主要围绕国内教辅和 K12 学习资料。
- 对国际课程、官方 Mark Scheme 和 tutor 复核场景没有天然优势。

对我们的启发：

- 大厂会持续覆盖“搜答案”和“AI 工具箱”。
- 我们要避开红海，抓“考试结果提升”和“可信批改”。

## 功能对比

| 能力 | Gauth | Photomath | Question.AI | Brainly | 作业帮/小猿/快对 | A-Level Assistant |
| --- | --- | --- | --- | --- | --- | --- |
| 拍照识题 | 强 | 强 | 强 | 中 | 强 | 已支持 |
| 数学 step-by-step | 强 | 强 | 强 | 中 | 强 | 已支持 |
| 全科覆盖 | 强 | 弱 | 强 | 强 | 强 | 不追求 |
| 学生过程批改 | 中 | 弱 | 中 | 弱 | 中 | 核心能力 |
| CAIE A-Level 垂直 | 弱 | 弱 | 弱 | 弱 | 弱 | 核心定位 |
| Past Paper matching | 弱 | 弱 | 弱 | 弱 | 弱 | 核心能力 |
| Mark Scheme grounded grading | 弱 | 弱 | 弱 | 弱 | 弱 | 核心能力 |
| M/A/B mark 解释 | 弱 | 弱 | 弱 | 弱 | 弱 | 核心能力 |
| confidence / needs_review | 弱 | 弱 | 弱 | 弱 | 弱 | 核心信任机制 |
| 错因诊断 | 中 | 中 | 中 | 中 | 强 | 核心能力 |
| 类题推荐 | 中 | 中 | 中 | 中 | 强 | 已支持，需继续做深 |
| 再作答再评分 | 中 | 弱 | 中 | 弱 | 中 | 已支持 |
| Tutor 可复核 | 弱 | 弱 | 弱 | 中 | 中 | 重要方向 |

## 为什么现有产品必须有这些功能

### 1. 必须有 Past Paper / Mark Scheme matching

如果没有 Mark Scheme matching，产品就只能说“这个答案数学上对不对”。但 CAIE A-Level 的真实评分是“这一步是否符合给分点”。同一个最终答案，过程不同，分数可能不同。

因此 Past Paper / Mark Scheme matching 是产品的可信度底座。

### 2. 必须有开放批改 fallback

学生不会总是上传完整真题。他们会上传老师自定义题、练习册截图、裁剪图、答案页、模糊图片。如果只支持真题匹配，产品会在真实使用中频繁失败。

所以需要两条路径：

```text
高置信真题 -> Mark Scheme grounded grading
低置信或自定义题 -> Open AI grading + confidence + ask-first
```

### 3. 必须有 confidence / needs_review

AI 批改一旦误判，伤害比“不会做”更大。学生会怀疑系统，老师会拒绝采用。

所以产品必须把风险显性化：

- OCR 不确定，提示复核。
- 题目匹配不确定，先确认。
- 推荐 topic 不确定，先问学生。
- 无法可靠推荐时，不硬猜。

这不是保守，而是教育产品的信任设计。

### 4. 必须有 verifier 和多模型复核

数学题的错误经常不是语言错误，而是符号、化简、概率、统计、边界条件错误。单个 LLM 容易在这些地方给出流畅但错误的判断。

因此 verifier 和多模型复核不是锦上添花，而是批改准确率的基础设施。

### 5. 必须有错因诊断

“你错了，正确答案是 X”不会帮助学生进步。学生需要知道：

- 是概念没懂；
- 是代数运算错；
- 是漏条件；
- 是没有化简；
- 是跳步导致 method mark 丢失。

错因诊断是从答案工具升级到学习工具的关键。

### 6. 必须有练习推荐和再批改

国内头部产品已经把错题本、举一反三、同步练变成用户预期。A-Level Assistant 如果停在批改，会显得不完整。

真正有粘性的闭环是：

```text
这次哪里丢分 -> 应该练哪个 topic -> 做一道同类 Past Paper -> 再评分 -> 调整下一题
```

这也是产品长期留存和学习效果的核心。

### 7. 必须有 PDF / Large PDF / 选页处理

A-Level 学生的真实学习材料以 PDF past paper 为主。只支持单图，会让产品停留在 demo 状态。

Large PDF 和选页处理能把产品带进真实工作流：

- 上传整套 paper；
- 识别 paper code / session / variant；
- 选择题号或页面；
- 只处理相关页面；
- 对齐 Mark Scheme 批改。

## 推荐定位

### 面向学生

> 拍照或上传 PDF，不只是给答案，而是按 CAIE Mark Scheme 告诉你每一步为什么得分或扣分，并推荐下一道该练的 Past Paper 题。

### 面向 tutor / 老师

> 一个可复核的 A-Level 数学批改助手：优先对齐官方 Mark Scheme，标出 needs_review 风险，沉淀薄弱 topic，并把批改结果转成后续练习。

### 英文一句话

> A-Level Assistant is a CAIE mark-scheme grading and adaptive past-paper practice workspace for A-Level Mathematics.

## 下一步建议

1. 首页继续弱化“AI 老师全包”，强化“CAIE Mark Scheme grading”。
2. 结果页更显性展示 paper code、question number、match confidence、mark scheme source。
3. 把 M/A/B mark explanation 做成可扫描模块，形成与 Photomath/Gauth 的第一屏差异。
4. 练习推荐文案统一为“next past-paper practice”，避免像普通题库推荐。
5. 增加 tutor 复核视图：按 needs_review、weak topic、mark lost reason 聚合。
6. 把 benchmark 结果转成对外可信表达，例如“10 图 batch 保持 20/20 标注准确，首题约 4.2s 返回”。

## 参考来源

- Gauth App Store: https://apps.apple.com/us/app/gauth-ai-study-companion/id1542571008
- Gauth Similarweb: https://www.similarweb.com/app/google/com.education.android.h.intelligence/
- WIRED 对 Gauth 的测试报道: https://www.wired.com/story/gauth-ai-math-homework-app
- Photomath App Store: https://apps.apple.com/us/app/photomath/id919087726
- Question.AI Google Play: https://play.google.com/store/apps/details?hl=en_US&id=com.qianfan.aihomework
- Question.AI 官网: https://questionai.ai/
- Brainly Similarweb: https://www.similarweb.com/app/google/co.brainly/
- 作业帮 App Store: https://apps.apple.com/cn/app/%E4%BD%9C%E4%B8%9A%E5%B8%AE-%E4%B8%AD%E5%B0%8F%E5%AD%A6%E5%AE%B6%E9%95%BF%E4%BD%9C%E4%B8%9A%E6%A3%80%E6%9F%A5%E5%92%8Cai%E4%BC%B4%E5%AD%A6%E8%BE%85%E5%AF%BC%E5%B7%A5%E5%85%B7/id803781859
- 小猿搜题 App Store: https://apps.apple.com/cn/app/%E5%B0%8F%E7%8C%BF%E6%90%9C%E9%A2%98-%E4%B8%AD%E5%B0%8F%E5%AD%A6%E5%AE%B6%E9%95%BF%E8%BE%85%E5%AF%BC%E5%92%8C%E4%BD%9C%E4%B8%9A%E6%A3%80%E6%9F%A5%E5%B7%A5%E5%85%B7/id906995758
- 小猿AI App Store: https://apps.apple.com/cn/app/%E5%B0%8F%E7%8C%BFai-%E5%8E%9F-%E5%B0%8F%E7%8C%BF%E5%8F%A3%E7%AE%97-%E6%A3%80%E6%9F%A5%E4%BD%9C%E4%B8%9A%E7%A5%9E%E5%99%A8/id1325419855
- 快对AI App Store: https://apps.apple.com/cn/app/%E5%BF%AB%E5%AF%B9ai-%E4%BD%9C%E4%B8%9A%E5%8A%A9%E6%89%8B/id1330927814
- 多知网关于 AIGCRank 和快对AI 的报道: https://www.duozhi.com/industry/insight/2025041817196.shtml
