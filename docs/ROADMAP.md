# 开发路线

## 当前 `main` 已包含

- 上传与流式批改流程。
- Past Paper 路由，支持 question-level Mark Scheme context。
- 自定义题或不确定上传的开放 AI 批改 fallback。
- 结果页学习诊断。
- Practice Orchestrator：
  - `auto`：上下文可靠时自动推荐；
  - `ask_first`：自定义题或不确定时先询问；
  - `none`：无法可靠推荐时说明原因。
- 内联练习闭环：
  - 推荐题目；
  - 学生作答；
  - 再次批改；
  - 给出下一题调整动作。
- 用于人工测试和视觉验收的 replay 页面：
  - `/__practice-recommendations-replay`。

## 产品方向

产品要成为 Past Paper 学习闭环，而不只是 AI 批改工具。

```text
批改 -> 诊断 -> 推荐练习 -> 学生作答 -> 再批改 -> 看到进步
```

最强路径：

```text
识别 paper -> 匹配题库 -> 使用 mark scheme -> 解释扣分点 -> 推荐相似题
```

fallback 路径：

```text
开放批改 -> 识别可能 topic -> 先询问学生 -> 从 P1-P6 题库里找可用练习
```

## 下一阶段

1. **让 Past Paper 匹配更显性**
   - 增加 paper 确认 UI；
   - 展示 paper code、question number、match source、confidence；
   - 允许学生纠正错误匹配，而不是重新上传。

2. **收紧 P1-P6 推荐边界**
   - 给题库补充 paper、topic、subtopic、difficulty 标签；
   - 避免推荐当前题库外的内容；
   - 当检测到题库外 topic 时，给出更清楚的学生文案。

3. **完成 Large PDF Mode**
   - 完整 PDF prepare session；
   - 页面缩略图；
   - 学生选择页码或题号；
   - 只处理选中的页面；
   - 保持普通图片上传的页数限制。

4. **升级结果页诊断**
   - 固定顶部结构：`本次表现`、`主要问题`、`下一步`；
   - 强化 `建议老师复核` 状态；
   - 把英文 difficulty label 映射成学生能读懂的中文。

5. **补强视觉和交互证据**
   - 继续保留 replay 页面；
   - 给关键状态保存 desktop/mobile 截图；
   - 增加 ask-first 和 adaptive practice 的交互烟测。

## 后续方向

- 老师端班级薄弱点 dashboard。
- 学生多次上传后的进步记忆。
- 裁剪截图的 OCR / question matching 增强。
- 原始 Past Paper PDF 的私有恢复流程。
- 部署安全加固，限制 debug endpoint。
