# 2026-06-26 Quality + Speed Optimization Iteration

## Summary

本轮目标是在不降低批改质量的前提下优化速度和准确率。核心优化不是压低 timeout，而是减少重复工作、修正 benchmark 计时口径，并让前端并发策略配合后端 in-flight 去重。

最终结果：

- 10 图 prepared fast batch：`131807ms -> 45303ms`
- 10 图 batch overall：`fail 77 -> pass 100`
- 10 图 batch 准确率保持：`20/20 correct`
- `recognition_timeout_count=0`
- `fast_batch_timeout_count=0`
- 首题返回：`6590ms -> 4244ms`
- JPEG quality seed：overall `pass 96`

## Implemented Changes

### 1. `/prepare-upload` 内容哈希缓存

文件：

- `api/upload_cache.py`
- `api/routes.py`
- `test/test_fast_upload_flow.py`

更新：

- 对上传图片 bytes 计算 SHA-256。
- 相同图片 + 相同 `user_hint` 命中缓存时，不再重复 OCR/切题。
- 每次请求仍生成独立 `upload_id`，避免 `_resolve_prepared` 的 page 顺序和 pop 语义互相污染。
- timeout 结果不写入内容缓存，避免把坏结果扩散给后续同图。

### 2. in-flight 去重

文件：

- `api/upload_cache.py`
- `api/routes.py`

更新：

- 当同一图片正在识别时，后续相同内容请求等待首个 owner 完成。
- owner 成功后写入内容缓存，再释放等待者。
- owner 失败或 timeout 时也释放等待者，避免挂住。

效果：

- benchmark 中 10 张图只有 2 种真实内容，后端只需要对 2 种内容做真正 prepare。

### 3. SSE 真实首题计时

文件：

- `scripts/evaluate_upload_corpus.py`
- `test/test_effectiveness.py`

更新：

- 评测脚本从 `client.post(...).text` 缓冲解析改成 `client.stream(...)` 流式解析。
- `first_question_ms` 记录第一个完整 `question` SSE block 到达时间。
- prepared batch 的首题时间按 final analyze submit 开始计，而不是把用户选图阶段的后台 prepare 也算入结果页首题等待。

### 4. 前端 prepare 并发与后端队列对齐

文件：

- `frontend/src/components/UploadForm.tsx`

更新：

- `PREPARE_UPLOAD_CONCURRENCY: 4 -> 10`
- 后端 `_prepare_semaphore=10`，前端并发与后端容量一致。
- 配合后端 in-flight 去重：重复图片不会产生重复重 OCR；不同图片能尽早并行 prepare。

## Benchmark Results

### 10 图 prepared fast batch

| 指标 | 上轮质量优先版 | 本轮优化后 |
|---|---:|---:|
| Report | `batch10_after_quality_timeout120_c2_solo_20260626.json` | `batch10_after_hash_cache_streaming_c10_final_20260626.json` |
| overall_status | fail | pass |
| overall_score | 77 | 100 |
| elapsed_ms | 131807 | 45303 |
| prepare_elapsed_ms | 90782 | 16278 |
| analyze_elapsed_ms | 41024 | 29024 |
| first_question_ms | 6590 | 4244 |
| question_count | 20 | 20 |
| question_error_counts | `correct=20` | `correct=20` |
| readable_question_rate | 1.0 pass | 1.0 pass |
| recognition_timeout_count | 0 pass | 0 pass |
| fast_batch_timeout_count | 0 pass | 0 pass |
| ten_image_batch_p95_ms | 131807 fail | 45303 pass |

结论：

- 速度目标达成。
- 准确率没有下降。
- hard gate 全部通过。

### JPEG quality seed

Report:

- `reports/effectiveness/jpeg_after_hash_cache_streaming_20260626.json`

结果：

- overall_status: `pass`
- overall_score: `96`
- image_end_to_end_p95_ms: `50876ms`, pass
- expected_question_recall_rate: `1.0`, pass
- expected_question_order_rate: `1.0`, pass
- marked_correctness_match_rate: `1.0`, pass
- marked_score_match_rate: `1.0`, pass
- recommendation_relevance_rate: `1.0`, pass
- question_error_counts: `correct=4`

仍需优化：

- first_question_p95_ms: `45907ms`, fail。
- 原因主要是单图非 fast batch 路径仍使用 multi-agent full grading，且外部模型池有 token/retry 波动。

## Verification

已通过：

```bash
PYTHONPATH=. pytest -q test/test_statistics_verifier.py test/test_fast_upload_flow.py test/test_pipeline_streaming.py test/test_effectiveness.py test/test_large_pdf_mode.py test/test_practice_orchestrator.py test/test_rescue_bridging.py test/test_feedback_metrics_dashboard.py
```

结果：`68 passed, 1 skipped`。

已通过：

```bash
cd frontend && npm run build
```

结果：build 成功；仍有既有 bundle size warning。

## Next Iteration

1. 单图首题速度。
   - 当前 JPEG 首题 `45907ms`，目标 `30000ms`。
   - 建议对单图也提供 fast-first result：先用 single fast grader 返回 provisional result，再后台补 multi-agent review/verifier。

2. prepare cache 持久化。
   - 当前内容缓存是进程内存，重启丢失。
   - 建议迁移到 Redis 或 SQLite durable cache，key 为 image hash + prompt/user_hint + model version。

3. 推荐 topic 精度。
   - 当前 recommendation benchmark 通过，但真实 topic 仍可能偏粗，例如 `sigma_notation`、`mean`。
   - 建议 grading summary 输出 `topic/subtopic/confidence/specificity`，推荐编排按具体度排序。

4. 更细分的速度指标。
   - 已经能拆 `prepare_elapsed_ms / analyze_elapsed_ms / first_question_ms`。
   - 下一步建议在 SSE 中加入 `segmentation_done_ms`、`first_grade_done_ms`、`all_grade_done_ms`，便于 dashboard 精确定位。
