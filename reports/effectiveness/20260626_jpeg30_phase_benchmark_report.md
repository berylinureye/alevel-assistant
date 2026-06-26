# 2026-06-26 JPEG30 阶段耗时 Benchmark 报告

## 结论

本轮按上一份报告的建议完成了两件事：

1. 建立固定 30 张 JPEG benchmark corpus。
2. 将首题耗时拆成可观测阶段：SSE 首事件、识别完成、首题批改等待、首题后汇总等待。

30 张真实链路复测结果不达标，但非常有价值：

- 上传成功率：100%，通过。
- 可解析率：100%，通过。
- 可读题目率：100%，通过。
- SSE 首事件 P95：0.489s，通过。
- 图片端到端 P95：131.071s，失败。
- 首题返回 P95：88.901s，失败。
- 识别完成 P95：77.197s，失败。
- 首题批改等待 P95：34.809s，失败。
- fast_batch_timeout：2 题，失败。

这说明系统稳定性比之前好，但真实拍照 corpus 下的长尾还没有解决。瓶颈不是网络/SSE 首包，而是“部分图片识别阶段过慢”和“部分题目 grading 调用过慢/整页等待过久”。

## 本轮代码与资产更新

### 1. 新增 JPEG benchmark corpus 生成器

文件：`scripts/build_jpeg_benchmark_corpus.py`

能力：

- 从本地真实上传素材派生固定 JPEG corpus。
- 支持正常、低清晰、倾斜阴影、跨页裁切、空白边界五类。
- 输出 `manifest.json`，记录每张图的来源、类别、尺寸、大小。
- 默认输出到 `test/fixtures/jpeg_benchmark_corpus`。

本轮生成结果：

| 类别 | 数量 |
|---|---:|
| normal | 10 |
| low_clarity | 5 |
| tilted_shadow | 5 |
| cross_page | 5 |
| blank_edge | 5 |

### 2. 新增阶段耗时记录

文件：`scripts/evaluate_upload_corpus.py`

每条记录新增 `phase_timings`：

- `sse_first_event_ms`
- `segmentation_done_ms`
- `first_question_ms`
- `first_grading_after_segmentation_ms`
- `summary_after_first_question_ms`

这些指标来自真实 SSE 事件到达时间，不改后端 API 协议。

### 3. 新增阶段耗时 effectiveness 指标

文件：`api/effectiveness.py`

新增诊断指标：

- `sse_first_event_p95_ms`
- `segmentation_done_p95_ms`
- `first_grading_after_segmentation_p95_ms`
- `summary_after_first_question_p95_ms`

它们目前 `weight=0`，用于定位性能瓶颈，不直接影响总体分数。但如果其中有 fail，会出现在 failures 列表中，便于每轮报告复盘。

### 4. 新增测试保护

文件：`test/test_effectiveness.py`

新增覆盖：

- SSE event timing parser。
- phase timing 派生逻辑。
- phase metrics 输出。
- JPEG corpus builder manifest 与类别覆盖。

## 真实复测结果

报告文件：

`reports/effectiveness/jpeg30_fast_first_phase_metrics_20260626.json`

整体：

| 指标 | 结果 | 目标 | 状态 |
|---|---:|---:|---|
| 总分 | 82 | ≥ 90 | fail |
| 上传成功率 | 100% | ≥ 95% | pass |
| 可解析率 | 100% | ≥ 90% | pass |
| 可读题目率 | 100% | ≥ 85% | pass |
| 图片端到端 P95 | 131.071s | ≤ 60s | fail |
| 首题返回 P95 | 88.901s | ≤ 30s | fail |
| SSE 首事件 P95 | 0.489s | ≤ 5s | pass |
| 识别完成 P95 | 77.197s | ≤ 20s | fail |
| 首题批改等待 P95 | 34.809s | ≤ 15s | fail |
| 首题后汇总 P95 | 113.997s | ≤ 15s | fail |
| fast_batch_timeout | 2 | 0 | fail |

错误分布：

| 类型 | 题数 |
|---|---:|
| correct | 33 |
| missing_parent_context | 13 |
| unanswered | 12 |
| incomplete_working | 7 |
| unknown | 5 |
| arithmetic_error | 2 |
| fast_batch_timeout | 2 |

## 按类别拆解

| 类别 | 样本 | 端到端 P95 | 首题 P95 | 识别 P95 | 首题批改等待 P95 | timeout |
|---|---:|---:|---:|---:|---:|---:|
| normal | 10 | 131.071s | 69.422s | 69.420s | 12.129s | 1 |
| low_clarity | 5 | 51.122s | 31.371s | 31.003s | 3.613s | 0 |
| tilted_shadow | 5 | 137.573s | 96.901s | 92.093s | 11.391s | 1 |
| cross_page | 5 | 98.402s | 88.901s | 77.197s | 11.704s | 0 |
| blank_edge | 5 | 48.929s | 48.927s | 12.241s | 42.738s | 0 |

关键判断：

- `tilted_shadow` 和 `cross_page` 是首题慢的最大来源，主要卡在识别阶段。
- `blank_edge` 虽然识别快，但首题批改等待慢，说明空白/答案页-only 需要更早被规则化处理。
- `normal` 并不总是快，真实手机大图仍有识别长尾和 timeout。
- `SSE 首事件 P95=0.489s`，说明传输层不是当前瓶颈。

## 慢样本 Top

| 文件 | 类别 | 端到端 | 首题 | 主要瓶颈 |
|---|---|---:|---:|---|
| `22_tilted_shadow_微信图片_20260407170227_46_4.jpg` | tilted_shadow | 137.573s | 21.918s | 后续题 timeout，summary 等待 115.440s |
| `14_normal_微信图片_20260407170227_46_4.jpg` | normal | 131.071s | 16.943s | 后续题 timeout，summary 等待 113.997s |
| `05_cross_page_IMG_D49734AE-67A1-42A9-B5FB-7381.jpg` | cross_page | 98.402s | 88.901s | 识别 77.197s |
| `16_tilted_shadow_微信图片_20260407170127_45_4.jpg` | tilted_shadow | 97.907s | 96.901s | 识别 92.093s |
| `26_normal_IMG_BED71913-F089-4A0F-8813-33FC.jpg` | normal | 92.427s | 69.422s | 识别 69.420s |

## 本轮验证

```bash
PYTHONPATH=. pytest -q test/test_effectiveness.py
```

结果：21 passed。

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

结果：72 passed, 1 skipped, 5 warnings。

```bash
cd frontend && npm run build
```

结果：通过。仍有 Vite chunk size warning。

## 后续迭代优先级

### P0：fast-first 不应等待整页慢题到 120s

当前两个最慢样本首题已经在 17-22s 返回，但整页结果被后续题拖到 131-137s。建议：

- 将 fast-first 的整页等待策略改成“首轮结果窗口”。
- 例如首题后 15-25s 仍未完成的题，立即返回 `needs_review=true` timeout placeholder。
- 未完成题后台继续补全，或由用户展开时再深评。

验收指标：

- `summary_after_first_question_p95_ms <= 15s`
- `fast_batch_timeout_count == 0`，或 timeout 题必须在 45s 内优雅降级而不是 120s。

### P0：空白/答案页-only 提前规则化

blank-edge 样本识别快，但 grading 等待 P95 达 42.738s。建议：

- 在 segment 后增加 lightweight blank/answer-only detector。
- 如果题干弱、答案弱、无 working，直接返回 `needs_review=true` 或 `unanswered`，不要调用完整 grading LLM。

验收指标：

- `blank_edge first_grading_after_segmentation_p95_ms <= 8s`
- 空白/答案页-only 不进入昂贵 grading 路径。

### P1：倾斜阴影和跨页图的识别前处理

`tilted_shadow` 识别 P95 为 92.093s，`cross_page` 为 77.197s。建议：

- 上传前/后端增加图像质量评分：倾斜、阴影、裁切风险。
- 高风险图先做轻量增强：自动旋正、对比度提升、裁边。
- 如果质量评分很差，在 UI 上提示重拍，而不是让学生等 90s。

验收指标：

- `tilted_shadow segmentation_done_p95_ms <= 35s`
- `cross_page segmentation_done_p95_ms <= 35s`
- 质量提示出现率与低质样本匹配。

### P1：识别阶段缓存按内容 hash 覆盖单图

上一轮 batch 已经受益于 hash cache。30 张 corpus 中有同源派生样本和重复正常样本，单图路径也应复用同类缓存/去重策略。

验收指标：

- 同一文件重复上传第二次 `segmentation_done_ms` 明显下降。
- repeat stability benchmark 中题数稳定率 ≥ 90%。

### P2：人工标注这 30 张 corpus

当前 30 张 corpus 是性能/稳定性 benchmark，还不是完整质量 benchmark，因为没有逐题人工 expectation。建议下一步补：

- expected question count/order。
- 每题 `is_correct` 和 `score`。
- expected topic / recommendation topic。
- 标记哪些样本应 `needs_review=true`。

验收指标：

- `marked_correctness_match_rate >= 90%`
- `marked_score_match_rate >= 85%`
- `expected_question_recall_rate >= 95%`

## 当前判断

这轮没有把系统“优化到全绿”，但把问题定位得更准了：稳定性和可解析性达标，真实体验长尾未达标。下一轮最值得做的不是继续调 dashboard，而是改 fast-first 的等待策略和空白/低质图的早降级路径。
