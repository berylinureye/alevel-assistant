# A-Level 自动批改系统 — 面试亮点总结

> 项目定位：面向 A-Level 数学的拍照作业自动批改系统。整页照片 → 结构化 JSON（题号/题文/学生答案/工作步骤/分数/双视角反馈）。
> 技术栈：FastAPI + React/Vite + 多家 LLM（Anthropic/OpenAI 兼容协议）+ SymPy + SQLite + Docker/Render。

---

## 1. 多模型路由：双层 + 6 条升级规则（`router/rules.py`）

### 做了什么
Base model 先做一次快速批改；同时计算 `RouteContext`（提取置信度、图像质量、批改置信度、工作步骤数、答案复杂度、grader 自标 needs_review）。6 条规则任一触发 → 升级到更强的 review model（进入多 agent 投票）。

### 为什么选这个方法
- **规则独立、全量评估**：新增一条规则只需往 `ESCALATION_RULES` 追加函数，不改路由核心（开闭原则）。
- **可解释**：每条规则返回 `(bool, reason_str)`，reason 会写进 `escalation_reasons` 字段，上线后能复盘"这题为什么被升级"。
- **成本/质量对冲**：简单题走快速模型，只有"危险区"才升级。

### 目标用户
- 主力用户：A-Level 学生（拍照自查）+ 教师（批作业）。
- 模型层的隐含用户：运维/产品经理，他们要能通过日志追溯路由决策。

### 不这样做的后果
- 单模型：要么准确率不够（全走 base）、要么成本/延迟爆炸（全走 review）。
- 不做规则化：升级策略散落在 grader 里，改一次要动多个文件、没法灰度测试。
- 一个被主动删掉的反例（代码注释原话）：`rule_unknown_question_type` 被移除，因为"统计等非微积分题被无谓升级，批改时间翻倍却没有质量收益"—— 这条规则的删除本身就是权衡证据。

### 检验标准
- `benchmark.py` 对真实作业图跑 end-to-end，输出 `bench_out_*.json`：`elapsed_seconds / review_count / avg_confidence / question_count`。
- `expectations` 机制可以配置期望分数/正误，产出 `correctness_match_rate / score_match_rate`，用于模型升级前后做回归对比。

---

## 2. 5-Agent 并行投票 + 早返回（`grader/multi_agent.py` + `multi_agent_config.py`）

### 做了什么
升级后的批改用 **5 个异构 agent** 并行：
- Fast tier（5–8s）：DeepSeek-chat / Qwen-plus / GLM-4-plus
- Accurate tier（10–25s）：Qwen-max-latest / GLM-5.1（thinking）

5 个并发跑，**前 3 个达成一致**（`is_correct` 相同且分数差 ≤ `EARLY_RETURN_SCORE_TOLERANCE=1.0`）即提前出结果；否则等到 `TOTAL_GRADING_TIMEOUT=35s` 上限。一致性影响最终 confidence：`unanimous +0.15 / majority +0.05 / early_return +0.10 / needs_review -0.25`。

### 为什么选这个方法
- **异构抗幻觉**：用不同厂商的模型投票，避免同一家模型的系统性偏差被共识放大。
- **延迟被最慢的 agent 决定**这个问题，用早返回破解：快模型达成共识就不等 thinking 模型。
- **Rate-limit 韧性**：GLM RPM 低，用 `_SharedGLMClient` 跨 agent 共享锁（`GLM_MIN_REQUEST_INTERVAL=5.0s`），避免并发 429。

### 目标用户
- 教师：批改结果要可信到能直接贴到学生作业上。
- 系统本身：需要在不同厂商 API 抖动时仍能给出结果。

### 不这样做的后果
- 单 agent：LLM 偶发的错误无法被发现；一家 API 故障直接瘫痪。
- 顺序调用：延迟 = sum；并行无早返回：延迟 = max（被最慢的拖）。
- 不做共享限流锁：多题并发时，两个 GLM agent 同时打 API → 429 重试风暴。

### 检验标准
- `confidence` 字段可观测：早返回 / 全员一致 / 分裂，都会在 confidence 上反映。
- 分数方差 > `SCORE_VARIANCE_THRESHOLD=20` 时切换投票策略（不取 median，取反馈质量最好的那票分数），并且方差 > 30 再扣 0.1 confidence。
- `LOW_CONFIDENCE_THRESHOLD=0.5` 下自动标 needs_review，人工兜底。

---

## 3. Segmenter 的反直觉约束：严禁"修正"学生错误（`pipeline/segmenter.py`）

### 做了什么
整页图 → 一次 LLM 调用，直接输出 JSON 数组（题号/题文/学生答案/工作步骤）。Prompt 用大量正反例（A–D 四组）强制：**学生怎么写就怎么抄，哪怕是错的**。例如 `(2x-4)^2 = 4x^2 - 8x + 16`（正确展开是 `4x^2-16x+16`），segmenter 必须抄错答。

### 为什么选这个方法
- **单次调用**：切题 + 提取合并为一次 LLM call，少一轮往返 = 少一次误差累积、少一倍延迟成本。
- **下游批改依赖真实错误**：如果 segmenter 帮学生"修"了答案，grader 看到的是对的，就会判满分 —— 但教师完全看不到学生到底哪里不会。
- **可选 OCR 交叉验证**：并行调用 Mathpix Convert API / 本地 OCR 兜底（不增加太多墙钟延迟，接近 `max(vision, ocr)`）。OCR 不直接主控结构；只有当 OCR 文本看起来包含真实题干语言时，才作为二级 prompt hint。若 OCR 只读到学生手写步骤，则仅作为 audit evidence，避免干扰 `question_text` 和 final answer。

### 目标用户
- **学生**：iPhone 拍照（HEIC 格式，已在 Dockerfile 装 libheif + pillow-heif 支持），光线差时数字容易混。
- **教师**：真正关心的是"学生在第几步算错的、是代数展开问题还是符号错误"，而不是一个被悄悄抹平的满分。

### 不这样做的后果
- 两次 LLM 调用：延迟 x2、token 成本 x2、信息在两次传输间丢失。
- Segmenter 自作主张纠错：假阳性满分、教学诊断彻底失效。
- 不做 OCR 交叉验证：数字题（统计、概率）一个数字识别错 = 整题判错。
- 不给 OCR 加 guard：手写-only 图上，专用 OCR 可能只读到学生步骤，反而诱导主模型清空或编造题干。

### 检验标准
- `test_segmenter_pdf.py` + `bench_out_*.json` 里的 `avg_confidence`、`question_count`。
- 单页 benchmark 输出 `elapsed_seconds ≈ 23s / confidence 0.9` 量级。

---

## 4. SymPy 独立验证层：对 LLM 做"客观校准"（`verifier/math_verifier.py` + `statistics_verifier.py`）

### 做了什么
LLM 给出判分后，对**微分/积分/代数**题再做一次符号验证：
- 积分题逆运算：对 LLM 给的 `correct_answer` 求导，看能否回到原题被积函数。
- 学生答案 vs. 正确答案：`simplify(a - b) == 0` 判等价（能识别 `+C` 缺失、代数恒等变形）。
- 超时保护：`multiprocessing` + 5s timeout，卡住就返回 inconclusive，**不抛异常**。
- 统计题另一条路：用轻量 LLM 做纯数值计算（mean/std/median），与学生答案数值比对，可以在 LLM 过度保守（方法对、数字也对但 LLM 判错）时反向 override。

### 为什么选这个方法
- LLM 在符号推导上有结构性幻觉（会编出"看起来对"的公式），但 SymPy 是**确定性**计算。
- 两者互补：LLM 懂教学意图、SymPy 懂数学事实。
- 不用 SymPy 替代 LLM，是因为 SymPy 无法评判"做法是否合适 / 步骤是否完整 / 哪里该给部分分"。

### 目标用户
- 数学强的学生（答案对但 LLM 判错）—— 有救济通道。
- 教师 —— 能信任系统对微积分题的判分结果。

### 不这样做的后果
- LLM 单判：微积分题的准确率被 LLM 符号幻觉拖累。
- 不做超时保护：SymPy 对某些表达式会卡死，整个请求挂起。

### 检验标准
- 日志里 `LLM overridden by SymPy` / `stat-verifier resolved contradiction` 的频次。
- 回归 benchmark 的 `score_match_rate`。

---

## 5. 学生反馈 ≠ 教师反馈（`formatter/feedback.py`）

### 做了什么
一次 grade 结果生成两份反馈：
- **student_feedback**：最多 3 条短 bullet，**禁止褒奖词**（"做得好/很棒"一律不给），只给诊断 + 提示 + 复习建议。
- **teacher_feedback**：固定 `Error / Gap / Action` 三行，定位知识漏洞 + 布置练习建议。
- **正确题不调 LLM**：走模板短语，直接省钱省延迟。
- **失败降级**：LLM 挂了就用 `_fallback_from_short()` 返回 grader 阶段已生成的短反馈，不抛 500。

### 为什么选这个方法
- 学生和教师读同一句话收益完全不同，强行共用一份反馈对谁都不好。
- 正确题调 LLM 纯属浪费（能占 80%+ 的量）。
- 反馈生成属于"锦上添花"，不该成为单点故障。

### 目标用户
- 学生：想知道**自己下一步怎么做**。
- 教师：想知道**这个班还需要补什么**。

### 不这样做的后果
- 共用反馈：学生看不懂术语、教师看不到教学线索。
- 无降级：LLM 故障一次，整次批改白跑。

### 检验标准
- `test_formatter.py` 覆盖降级路径（mock 失败 → 必须返回 fallback 而不是 raise）。

---

## 6. Model-agnostic 架构：`ModelClient` Protocol（`router/models.py`）

### 做了什么
定义 `ModelClient` 为 runtime-checkable Protocol，字段 `role / model_id / provider` + 方法 `supports_images() / call(ModelRequest)`。具体实现：
- `AnthropicCompatClient`（走 Anthropic SDK，可通过 `ANTHROPIC_BASE_URL` 指向任意兼容网关）
- `OpenAICompatClient`（DeepSeek / DashScope / GLM 都走这个）
- 通过 `build_registry()` 从环境变量装配，按 `ModelRole`（base / vision / ocr / review / explain）取用。

### 为什么选这个方法
- 不绑死单一厂商：成本突变、限流、API 故障都能快速切。
- 5-agent 异构投票能成立，前提就是这个抽象。
- 加新厂商 = 新写一个实现类，不碰调用方。

### 目标用户
- 产品/运维：能按价格和可用性动态调整模型矩阵。

### 不这样做的后果
- 直接在业务代码里写死 `openai.ChatCompletion.create`，换厂商就是全局重写。
- 做不成多 agent 投票（只有一个厂商 SDK 的调用形状）。

### 检验标准
- `build_grading_agents()` 要求至少有一把 key（DEEPSEEK/DASHSCOPE/GLM），否则 `RuntimeError`，配置缺失能在启动时暴露。
- `build_registry()` 在 OCR 上按 Mathpix → DashScope → 显式 `OCR_MODEL`/VIVIAI → local tesseract 的顺序装配；Mathpix 缺失或失败不会拖垮主流程。

---

## 7. 并发与流式：`Semaphore` + SSE（`api/routes.py`）

### 做了什么
- `_pipeline_semaphore = Semaphore(2)`：整条 pipeline（多次 LLM 调用）最多 2 并发。
- `_prepare_semaphore = Semaphore(4)`：上传预处理较轻，允许 4 并发。
- `/analyze?stream=true` 用 SSE 逐题推送，前端边批边展示。

### 为什么选这个方法
- pipeline 并发过高会撞 LLM 厂商 RPM 限制，产生级联失败；2 是保守但稳的数。
- SSE 把"等 5 题全批完再返回"的体验变成"边批边看"。

### 目标用户
- 同时批多张作业的教师 / 多学生同时用的场景。

### 不这样做的后果
- 无并发上限：API 被打爆、429 风暴。
- 非流式：N 题的延迟 = 所有题总和，用户以为卡死。

### 检验标准
- benchmark 的 `elapsed_seconds` 单页 ≈ 23s。

---

## 8. 题库系统（`docs/question-bank-proposal.md` + `scraper/` + `questionbank/`）

### 做了什么
爬 CIE 历年真题 PDF → 高清图（200 DPI）→ AI vision 抽题 + 关联 mark scheme → SQLite 三表（subjects / papers / questions）→ `GET /questions/random?topic=differentiation&difficulty_min=2` + 复用现有 grader 自动批改。爬虫并发用 `asyncio.Semaphore(2)`。

### 为什么选这个方法
- 一次性爬 + 本地存：CIE 文件命名规则完全确定（`9709_s25_qp_31.pdf`），不需要实时爬；本地无网络依赖。
- 200 DPI 图片而非纯文本抽取：微积分公式必须保留排版。
- SQLite：题量几千级别，够用且无运维成本。

### 目标用户
- 学生：按知识点刷题。
- 教师：讲完一个知识点后精准出作业。

### 不这样做的后果
- 实时爬：每次请求都依赖第三方站点的可用性，不稳。
- 纯文本抽取：公式排版丢失、分式/积分记号失真。
- Postgres：现阶段运维开销不成比例。

### 检验标准
- scraper 入库数与目标 paper 数匹配；`verified_only` 过滤下的题目数。

---

## 9. 部署与可观测（`Dockerfile` / `render.yaml`）

- 前后端分离部署（`alevel-api` + `alevel-app`）：静态前端可走 CDN、API 独立扩展、改 prompt 不用重新 build 前端。
- `ALLOWED_ORIGINS` 环境变量收紧 CORS，生产白名单。
- 结构化日志：`pipeline` logger 记录路由决策、验证器 override、agent 超时 —— 上线后事故复盘的关键。

---

## 面试高频问答准备

**Q：你怎么平衡准确率和成本？**
双层路由 + 选择性升级（`router/rules.py` 的 6 条规则） + 升级后才走 5-agent 投票 + 早返回（`EARLY_RETURN_MIN_AGENTS=3`, 分数容忍 1.0）。简单题一次快模型搞定，复杂题才烧钱。

**Q：为什么不用一个最强模型？**
成本、延迟、单点故障都不能接受。而且异构投票比单模型多样本能更有效抑制幻觉。

**Q：Segmenter 为什么不帮学生纠错？**
如果它在提取阶段"修好"了 `4x^2 - 8x + 16`，grader 看到的是正确答案，学生拿满分，教师永远看不到那个展开公式的 sign error。教学诊断链路就断了。

**Q：SymPy 卡住怎么办？**
`multiprocessing` + 5s timeout，超时返回 inconclusive，LLM 判分继续有效。

**Q：多厂商 rate limit 怎么防？**
`_SharedGLMClient` 用模块级共享锁 + `GLM_MIN_REQUEST_INTERVAL=5.0s`，所有 GLM agent 串行排队打 API。

**Q：怎么验证改动没把系统改坏？**
`benchmark.py` 跑真实作业图，`expectations` 机制算 `correctness_match_rate / score_match_rate`，模型或 prompt 升级前后做对比。
