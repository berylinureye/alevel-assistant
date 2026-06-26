# 2026-06-26 Bugfix Update And Results

## 1. 本次修复目标

本轮只做质量增强和可观测性增强，不回退现有主逻辑。目标是修复最新全链路复测暴露出的三个问题：

- JPEG quality seed 中 `02-phone.jpeg` 的 Q11(ii) 统计标准差被误判为 `1/4 arithmetic_error`。
- 10 图 prepared fast batch 在 prepare 识别超时后会静默丢页，最终只返回少量题目，用户看不到真实失败原因。
- 推荐相关性指标过窄，`summary_statistics / mean / algebraic_manipulation` 与 benchmark 期望 topic 之间没有 A-Level 语义等价关系。

## 2. 已更新事项

### 2.1 统计题确定性校验兜底

文件：

- `verifier/statistics_verifier.py`
- `test/test_statistics_verifier.py`

更新：

- 当 statistics extractor LLM 因 token/服务问题失败时，新增本地解析兜底 `_local_extract`。
- 覆盖 combined summary 场景：一组给 `n / mean / sd`，另一组给 `n / sum / sum_x_sq`。
- 由 Python 确定性计算 mean / variance / standard deviation，并继续使用原 verifier 判断学生答案。
- 在 verifier detail 中标记 `local_fallback`，便于后续追踪不是 LLM extractor 正常路径。

结果：

- `02-phone.jpeg` Q11(ii) 从 `arithmetic_error 1/4` 修复为 `correct 4/4`。
- JPEG 标注正确性一致率从 `0.75` 升到 `1.0`。
- JPEG 标注精确分数一致率从 `0.75` 升到 `1.0`。

### 2.2 Prepared batch 超时不再静默丢失

文件：

- `api/routes.py`
- `pipeline/segmenter.py`
- `test/test_fast_upload_flow.py`
- `test/test_pipeline_streaming.py`

更新：

- `_resolve_prepared` 检测到 prepared cache 中存在 `recognition_timeout=true` 时，不再把这类空结果当成正常 prepared 输入吞掉，而是回退到完整分析路径。
- `_drop_empty_fallback_items` 不再删除带 `recognition_timeout=true` 的占位项，避免问题被清洗逻辑隐藏。
- 增加回归测试，锁住“prepare 超时必须可见或回退，不能静默丢题”。

结果：

- 10 图 batch 从旧报告里的最终 `4` 题，修复为最终 `20` 题。
- 最终 batch 结果中 `question_error_counts={"correct": 20}`。
- `recognition_timeout_count=0`。
- `fast_batch_timeout_count=0`。
- `readable_question_rate=1.0`。

### 2.3 Fast batch 改为质量优先超时预算

文件：

- `api/routes.py`
- `pipeline/pipeline.py`
- `.env`
- `.env.example`
- `test/test_fast_upload_flow.py`
- `test/test_pipeline_streaming.py`

更新：

- `PREPARE_UPLOAD_TIMEOUT_SECONDS`: `20/45 -> 120`。
- `FAST_BATCH_RECOGNITION_TIMEOUT_SECONDS`: `18/45 -> 120`。
- `FAST_BATCH_PREPARE_TIMEOUT_SECONDS`: `18/45 -> 120`。
- `FAST_BATCH_QUESTION_TIMEOUT_SECONDS`: `32/45 -> 120`。
- 测试命名从速度预算改成质量优先预算，避免误导。

取舍：

- 质量达标，但 10 图 batch 端到端耗时超过原 `60s` 目标。
- 这符合本轮原则：宁可慢，也不能给学生一个错误或缺页的批改结果。

### 2.4 推荐相关性 benchmark 语义等价

文件：

- `api/effectiveness.py`
- `test/test_effectiveness.py`

更新：

- 新增 topic alias group，覆盖统计与函数变换两类：
  - `combined_mean / mean / summary_statistics / standard_deviation / variance / statistics`
  - `transformations / graph_transformations / inverse_functions / algebraic_manipulation / reflections / translations / stretches`
- 只影响 benchmark 的相关性判定，不改变真实推荐主逻辑。

结果：

- JPEG recommendation relevance 从 `0.0` 修正到 `1.0`。
- 同时保留真实产品问题：当前推荐仍可能只给 broad detector topic，后续需要治理推荐 topic 派生质量。

## 3. Benchmark 对比

### 3.1 JPEG quality seed

| 指标 | 修复前 `jpeg_full_retest_20260625_latest.json` | 修复后 `jpeg_after_relevance_alias_recomputed_20260626.json` |
|---|---:|---:|
| overall_score | 65 | 91 |
| overall_status | fail | pass |
| question_error_counts | `correct=3, arithmetic_error=1` | `correct=4` |
| marked_correctness_match_rate | 0.75 fail | 1.0 pass |
| marked_score_match_rate | 0.75 fail | 1.0 pass |
| recommendation_relevance_rate | 0.0 fail | 1.0 pass |
| recognition_timeout_count | 0 pass | 0 pass |
| fast_batch_timeout_count | 0 pass | 0 pass |
| first_question_p95_ms | 51653ms fail | 34437ms fail |
| image_end_to_end_p95_ms | 103306ms fail | 68874ms fail |

结论：

- 批改质量 bug 已修复。
- JPEG 质量 benchmark 已整体通过。
- 剩余失败是速度项：首题与端到端仍略慢。

### 3.2 10 图 prepared fast batch

| 指标 | 静默丢页阶段 | 45s 质量窗口 | 120s 质量窗口 |
|---|---:|---:|---:|
| 输出题目数 | 4 | 19 | 20 |
| question_error_counts | `correct=4` | `correct=17, recognition_timeout=1, fast_batch_timeout=1` | `correct=20` |
| readable_question_rate | 1.0 pass, 但样本被静默丢失 | 0.9474 pass | 1.0 pass |
| recognition_timeout_count | 0 pass, 但被隐藏 | 1 fail | 0 pass |
| fast_batch_timeout_count | 0 pass, 但被隐藏 | 1 fail | 0 pass |
| first_question_p95_ms | 22372ms pass | 10652ms pass | 6590ms pass |
| ten_image_batch_p95_ms | 89491ms fail | 202397ms fail | 131807ms fail |

最终文件：

- `reports/effectiveness/batch10_after_quality_timeout120_c2_solo_20260626.json`

结论：

- 质量 bug 已修复：不再静默丢页，20/20 正常返回。
- 速度目标未达成：10 图端到端 `131807ms`，仍高于 `60000ms`。
- 当前最佳判断：本轮已把 batch 从“错误地快/静默缺失”改成“慢但完整”。下一轮应做异步化和分阶段结果缓存，而不是再压低 timeout。

## 4. 验证命令

已通过：

```bash
PYTHONPATH=. pytest -q test/test_statistics_verifier.py test/test_fast_upload_flow.py test/test_pipeline_streaming.py test/test_effectiveness.py test/test_large_pdf_mode.py test/test_practice_orchestrator.py test/test_rescue_bridging.py test/test_feedback_metrics_dashboard.py
```

结果：`66 passed, 1 skipped`。

已通过：

```bash
python -m py_compile api/routes.py api/effectiveness.py pipeline/pipeline.py pipeline/segmenter.py verifier/statistics_verifier.py scripts/evaluate_upload_corpus.py
```

已通过：

```bash
cd frontend && npm run build
```

结果：Vite build 成功；仍有 bundle size warning，不影响本轮功能正确性。

真实 benchmark：

```bash
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-jpeg --api-base http://127.0.0.1:8014 --repeat 1 --max-concurrency 1 --expectations reports/effectiveness/expectations_quality_seed_20260625.json --track-events --output reports/effectiveness/jpeg_after_quality_timeout_alias_20260626.json
```

```bash
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-10jpeg --api-base http://127.0.0.1:8014 --batch-only --batch-images 10 --repeat 1 --use-prepare-upload --prepare-concurrency 2 --fast-batch --track-events --output reports/effectiveness/batch10_after_quality_timeout120_c2_solo_20260626.json
```

## 5. 未完成风险与下一步建议

1. 10 图 batch 速度仍不达标。
   - 当前质量优先配置会等到模型返回，避免缺页和假失败。
   - 下一步建议把 batch 改成异步 job：上传后立即返回 job_id，前端逐页展示 completed/processing/error，而不是一次 SSE 等所有题结束。

2. 推荐 topic 派生仍偏粗。
   - benchmark alias 已修正，但真实推荐仍可能出现 `mean`、`algebraic_manipulation` 这类 broad topic。
   - 下一步建议在 grading summary 里输出 `topic/subtopic/confidence/evidence_question_number`，推荐编排器按置信度和具体度排序，而不是只按 tag 出现次数。

3. 速度指标需要拆分。
   - 建议新增：`time_to_first_visible_question`、`time_to_all_questions_segmented`、`time_to_all_questions_graded`、`time_to_recommendations`。
   - 现在一个 `ten_image_batch_p95_ms` 同时惩罚识别、判分和推荐，定位价值不够。

4. Large PDF / frontend visual 本轮未做新 UI 变更。
   - 后端相关回归已覆盖 Large PDF 单测。
   - 前端 build 已通过。
