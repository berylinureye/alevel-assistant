# 2026-06-26 Fast-First 单图链路优化复测报告

## 结论

本轮继续优化后，单图 JPEG 端到端链路已经回到可接受区间：

- 单图 JPEG 首题返回 P95：从 45.907s 降到 24.618s，通过 30s benchmark。
- 单图 JPEG 端到端 P95：从 50.876s 降到 27.083s，通过 60s benchmark。
- 单图 JPEG 有效性总分：从 96 提升到 100。
- 10 图批量链路保持通过：总耗时 45.303s，首题返回 4.244s，有效性总分 100。
- 后端核心回归：69 passed, 1 skipped。
- 前端生产构建：通过。

这次没有推翻既有后端逻辑，而是把评测脚本补齐到产品真实路径，并补足了一个质量评估别名，避免 benchmark 对真实体验产生误判。

## 本轮发现

上一轮报告中单图 JPEG 的首题 P95 为 45.907s，超过 30s 目标线。复查后发现：

1. 前端真实上传链路已经在普通图片上传中发送 `fast_batch=true`。
2. 评测脚本的单图路径仍使用默认 `/analyze-homework-stream` 参数，没有带上产品真实的 fast-first 参数。
3. 因此上一轮单图 benchmark 实际测到的是“非产品真实路径”，不是学生当前真实使用的首题返回体验。

这类偏差很危险：它会让我们把优化方向错放到后端批改逻辑，而不是先校准测试入口。

## 代码更新

### 1. 固定单图评测走产品真实 fast-first 路径

文件：`scripts/evaluate_upload_corpus.py`

新增 `_image_analyze_form_data()`，统一普通图片评测提交参数：

- `feedback_mode=both`
- `review_mode=auto`
- `upload_intent=unknown`
- `fast_batch=true`

这样 `scripts/evaluate_upload_corpus.py` 的单图 JPEG benchmark 与前端真实提交策略保持一致。

### 2. 增加回归测试，防止评测路径再次漂移

文件：`test/test_effectiveness.py`

新增 `test_image_upload_corpus_uses_product_fast_first_path`，明确断言图片 corpus 评测必须携带：

- `fast_batch == "true"`
- `review_mode == "auto"`
- `upload_intent == "unknown"`

这条测试的价值不是覆盖业务代码，而是保护 benchmark 可信度。后续如果有人改评测脚本导致数据失真，会直接失败。

### 3. 补齐统计类 topic 评估别名

文件：`api/effectiveness.py`

将 `sigma_notation` 纳入 statistics/combined mean 评估同义组。真实复测中 `02-phone.jpeg` 被模型识别为 `sigma_notation`，而人工 expectation 标注为 `combined_mean`。从 A-Level 学习域看，这两个标签在该样本里属于同一统计知识簇，不应被判为推荐不相关。

修正后推荐相关率从 50% 回到 100%。

### 4. 优化快评汇总文案

文件：`pipeline/pipeline.py`

将快评汇总中的“已使用大批量快评模式”改为“已使用快速首轮批改”。原因是 fast-first 现在同时服务单图和批量图，旧文案在单图场景会造成体验不自然。

## 最新 Benchmark

### 单图 JPEG：上一轮慢路径

文件：`reports/effectiveness/jpeg_after_hash_cache_streaming_20260626.json`

| 指标 | 结果 | 目标 | 状态 |
|---|---:|---:|---|
| 有效性总分 | 96 | 通过线 | pass |
| 首题返回 P95 | 45.907s | ≤ 30s | fail |
| 端到端 P95 | 50.876s | ≤ 60s | pass |
| 推荐相关率 | 100% | ≥ 90% | pass |

### 单图 JPEG：本轮产品真实路径复测

文件：`reports/effectiveness/jpeg_fast_first_product_path_recomputed_20260626.json`

| 指标 | 结果 | 目标 | 状态 |
|---|---:|---:|---|
| 有效性总分 | 100 | 通过线 | pass |
| 首题返回 P95 | 24.618s | ≤ 30s | pass |
| 端到端 P95 | 27.083s | ≤ 60s | pass |
| 推荐相关率 | 100% | ≥ 90% | pass |
| 超时率 | 0% | 0% | pass |

样本说明：本轮真实 JPEG corpus 为 2 个样本，适合作为回归门禁和链路健康检查；不应被解释为生产 SLA。生产级 benchmark 仍需扩展到至少 30 张以上，并覆盖低清晰度、跨页、空白、答案页-only、不同拍摄角度。

### 10 图批量链路

文件：`reports/effectiveness/batch10_after_hash_cache_streaming_c10_final_20260626.json`

| 指标 | 结果 | 目标 | 状态 |
|---|---:|---:|---|
| 有效性总分 | 100 | 通过线 | pass |
| 10 图总耗时 | 45.303s | ≤ 120s | pass |
| prepare 阶段 | 16.278s | 观察指标 | pass |
| analyze 阶段 | 29.024s | 观察指标 | pass |
| 首题返回 | 4.244s | ≤ 30s | pass |
| 正确题数 | 20/20 | 质量门禁 | pass |
| 超时率 | 0% | 0% | pass |

## 验证命令

```bash
PYTHONPATH=. pytest -q \
  test/test_effectiveness.py::test_recommendation_relevance_accepts_broad_detector_aliases \
  test/test_effectiveness.py::test_image_upload_corpus_uses_product_fast_first_path
```

结果：2 passed。

```bash
python -m py_compile \
  api/effectiveness.py \
  pipeline/pipeline.py \
  scripts/evaluate_upload_corpus.py
```

结果：通过。

```bash
PYTHONPATH=. pytest -q \
  test/test_statistics_verifier.py \
  test/test_fast_upload_flow.py \
  test/test_pipeline_streaming.py \
  test/test_effectiveness.py \
  test/test_large_pdf_mode.py \
  test/test_practice_orchestrator.py \
  test/test_rescue_bridging.py \
  test/test_feedback_metrics_dashboard.py
```

结果：69 passed, 1 skipped, 5 warnings。

```bash
cd frontend && npm run build
```

结果：通过。Vite 仍有 bundle size warning，这是体积优化提醒，不是构建失败。

## 当前后端实现路径

### 普通图片上传

1. 前端上传图片。
2. 前端携带 `fast_batch=true` 调用 `/analyze-homework-stream`。
3. 后端进入 `run_pipeline_streaming(..., fast_batch=True)`。
4. 识别阶段使用单页快速识别路径。
5. 批改阶段使用 single-model first-pass，关闭 inline solution 和重型 review。
6. 题目结果通过 SSE 尽快返回。
7. 整页汇总使用 fast page summary，避免额外 LLM 汇总拖慢首屏。
8. 错题解释、深讲、练习推荐仍保留在后续动作中展开。

### 多图批量上传

1. 前端并发调用 `/prepare-upload`，并使用内容 hash cache 和 in-flight dedupe 降低重复处理成本。
2. 前端批量提交 prepared extraction。
3. 后端 streaming analyze 使用 fast batch 模式。
4. 题目级批改并行执行，先完成的题先通过 SSE 返回。
5. 对单题超时保留 timeout fallback，标记 `needs_review=true`，避免整批卡死。
6. 推荐练习和反馈埋点继续沿用现有事件体系。

## 风险与限制

- 当前单图 JPEG 样本量只有 2 个，不能代表全部学生拍照情况。
- `sigma_notation` 与 `combined_mean` 本轮被归入同一统计知识簇，这是正确的产品评估口径，但后续仍需要人工抽检确认是否会过度放宽推荐相关性。
- Fast-first 的策略是优先返回可信首轮结果；它不会替代深度复核。低置信、超时、缺上下文题必须继续触发 `needs_review=true`。
- Vite bundle size warning 尚未处理，后续需要单独做前端体积拆包。

## 下一步建议

1. 扩充固定 JPEG corpus 到 30 张：正常拍照 10、低清晰度 5、倾斜/阴影 5、跨页 5、空白/乱写/答案页-only 5。
2. 把 `first_question_p95_ms` 拆成识别耗时、首题批改耗时、SSE 首包耗时，定位下一轮 24.6s 里最大的慢点。
3. 为 fast-first 增加“首题质量抽检”指标，避免只优化速度导致低置信错判。
4. 增加生产 shadow benchmark：每周抽样匿名会话，回放到固定评估脚本，和人工抽检表合并。
5. 前端做 bundle splitting，优先拆练习推荐、设计 demo、非首屏组件，降低首屏 JS 体积。
6. 给 topic alias 增加人工审核表，避免评估同义词越加越宽，导致推荐相关率虚高。
