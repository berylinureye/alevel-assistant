# A-Level 题库系统技术方案

## 1. 项目目标

在现有的 A-Level 作业批改助手基础上，新增「题库随机出题」功能：

- 从 cie.fraft.cn 爬取 CIE A-Level 历年真题 PDF
- 将 PDF 中的题目解析为结构化数据（题号、题目文字、分值、答案、知识点）
- 存入题库数据库
- 提供 API 支持按科目/知识点/难度/年份随机抽题
- 前端新增"练习模式"，学生做完后复用现有批改流程

---

## 2. 系统架构总览

```
┌─────────────────────────────────────────────────────┐
│                   前端 (React)                        │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ 作业批改  │  │  练习模式     │  │  题库管理      │  │
│  │ (现有)    │  │  (新增)       │  │  (新增/教师)   │  │
│  └──────────┘  └──────────────┘  └───────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP API
┌──────────────────────┴──────────────────────────────┐
│                 后端 (FastAPI)                        │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ 现有路由  │  │ 题库 API     │  │  批改 API     │  │
│  │ /analyze  │  │ /questions   │  │  (复用)       │  │
│  └──────────┘  └──────────────┘  └───────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│                    数据层                             │
│  ┌──────────────────┐  ┌────────────────────────┐   │
│  │  SQLite 题库      │  │  PDF 文件存储           │   │
│  │  questions.db     │  │  data/papers/           │   │
│  └──────────────────┘  └────────────────────────┘   │
└─────────────────────────────────────────────────────┘

离线流程（一次性或定期）:
  爬虫 → PDF下载 → AI解析 → 入库
```

---

## 3. 模块一：爬虫 (Scraper)

### 3.1 目标

爬取 cie.fraft.cn 上的 A-Level 试卷 PDF，包括：
- Question Papers (试题卷)
- Mark Schemes (评分标准)
- Examiner Reports (考官报告，可选)

### 3.2 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| HTTP 请求 | `httpx` (异步) | 支持异步并发，比 requests 更现代 |
| HTML 解析 | `BeautifulSoup4` | 轻量、稳定 |
| 并发控制 | `asyncio.Semaphore` | 控制并发数，避免被封 |
| 文件存储 | 本地文件系统 | PDF 按目录结构分类存放 |

### 3.3 文件存储结构

```
data/
  papers/
    9709/                          # 科目代码 (Mathematics)
      2023/
        s23_qp_12.pdf              # 2023 夏季 Paper 1 Variant 2 试题卷
        s23_ms_12.pdf              # 对应评分标准
        w23_qp_12.pdf              # 2023 冬季 ...
      2022/
        ...
    9702/                          # 科目代码 (Physics)
      ...
```

### 3.4 爬虫流程

```python
# scraper/crawler.py 伪代码

async def crawl_subject(subject_code: str):
    """爬取某一科目的所有年份试卷"""
    # 1. 获取科目页面，解析年份列表
    # 2. 对每个年份，获取该年份下的所有 PDF 链接
    # 3. 过滤出 Question Paper 和 Mark Scheme
    # 4. 下载 PDF 到对应目录
    pass

async def main():
    subjects = ["9709"]  # 先从数学开始
    for subject in subjects:
        await crawl_subject(subject)
```

### 3.5 已确认的网站结构

通过截图已确认以下信息：

1. **网站首页**：有科目/年份/季度三个下拉框 + 查询按钮
2. **科目列表**：下拉框包含 9709 - 数学 (AS/A2) 等全部 CIE 科目
3. **PDF 直链**：`https://cie.fraft.cn/obj/Common/Fetch/redir/{filename}.pdf`
4. **文件名规则**：`9709_s25_qp_31.pdf` = 科目_季度年份_类型_试卷变体
5. **无需登录**即可查看和下载 PDF
6. **QP 和 MS 同页展示**，文件名仅 `_qp_` 和 `_ms_` 的区别

**爬虫策略**：由于 PDF 命名完全确定，无需解析 HTML。
直接构造全部可能的文件名组合，逐一尝试下载 (404 跳过，200 保存)。

---

## 4. 模块二：PDF 解析 (Parser)

### 4.1 挑战

A-Level 数学试卷 PDF 包含大量数学公式、图表和特殊排版，直接文字提取会丢失格式。

### 4.2 两阶段解析策略

#### 阶段一：PDF → 图片

```python
# parser/pdf_to_images.py
import fitz  # PyMuPDF

def pdf_to_images(pdf_path: str, dpi: int = 200) -> list[PIL.Image]:
    """将 PDF 每页转为高清图片"""
    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    return images
```

#### 阶段二：AI 视觉识别（复用现有 pipeline 的能力）

利用你项目中已有的 AI 模型调用能力，对每张试卷图片做结构化提取：

```python
# parser/question_extractor.py

EXTRACTION_PROMPT = """
你是一位 A-Level 数学试卷解析专家。请分析这张试卷图片，提取出每道题的信息。

对于每道题，请输出：
1. question_number: 题号（如 "1", "2(a)", "2(b)(i)"）
2. question_text: 完整的题目文字，数学公式用 LaTeX 表示
3. marks: 该题分值
4. topic: 涉及的知识点（如 differentiation, integration 等）
5. subtopic: 更细的子知识点
6. difficulty: 预估难度 (1-5)
7. has_diagram: 是否包含图表 (true/false)

请以 JSON 数组格式输出。
"""

def extract_questions_from_image(image: PIL.Image, client) -> list[dict]:
    """用 AI 从试卷图片中提取结构化题目"""
    # 调用 AI 视觉模型
    response = client.call_with_image(image, EXTRACTION_PROMPT)
    return parse_json_response(response)
```

#### 阶段三：Mark Scheme 匹配

同样用 AI 解析 Mark Scheme PDF，然后按题号匹配到对应的题目上：

```python
MS_PROMPT = """
分析这张 Mark Scheme 图片，提取每道题的评分细则：
1. question_number: 题号
2. correct_answer: 最终正确答案 (LaTeX)
3. marking_points: 得分点列表
4. common_errors: 常见错误
"""
```

### 4.3 解析质量保证

- 对 AI 提取结果做 JSON schema 校验
- 抽样人工核验（建议前 20 份试卷逐题检查）
- 记录解析置信度，低置信度的题目标记为待审核

---

## 5. 模块三：题库数据库 (Question Bank)

### 5.1 数据库选型

使用 **SQLite**（轻量、无需额外服务、适合当前规模）。未来如果题量增大，可迁移到 PostgreSQL。

### 5.2 数据表设计

```sql
-- 科目表
CREATE TABLE subjects (
    code        TEXT PRIMARY KEY,     -- "9709"
    name        TEXT NOT NULL,        -- "Mathematics"
    name_cn     TEXT,                 -- "数学"
    level       TEXT DEFAULT 'A-Level' -- AS / A-Level
);

-- 试卷表
CREATE TABLE papers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_code TEXT NOT NULL REFERENCES subjects(code),
    year        INTEGER NOT NULL,      -- 2023
    session     TEXT NOT NULL,          -- "s" (summer/June), "w" (winter/Nov), "m" (March)
    paper_num   INTEGER NOT NULL,      -- 1, 2, 3...
    variant     INTEGER DEFAULT 1,     -- 1, 2, 3
    pdf_path    TEXT,                   -- 本地 PDF 路径
    ms_pdf_path TEXT,                   -- Mark Scheme PDF 路径
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(subject_code, year, session, paper_num, variant)
);

-- 题目表（核心）
CREATE TABLE questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id        INTEGER NOT NULL REFERENCES papers(id),
    question_number TEXT NOT NULL,          -- "1", "2(a)", "2(b)(i)"
    parent_number   TEXT,                   -- 父题号，用于子题关联，如 "2"
    question_text   TEXT NOT NULL,          -- 题目文字（含 LaTeX）
    marks           INTEGER DEFAULT 0,      -- 分值
    topic           TEXT,                   -- 知识点大类
    subtopic        TEXT,                   -- 知识点子类
    difficulty      INTEGER DEFAULT 3,      -- 1-5 难度
    has_diagram     BOOLEAN DEFAULT FALSE,  -- 是否含图表
    diagram_desc    TEXT,                   -- 图表描述（文字）
    correct_answer  TEXT,                   -- 正确答案（LaTeX）
    marking_points  TEXT,                   -- JSON: 评分点列表
    common_errors   TEXT,                   -- JSON: 常见错误
    source_page     INTEGER,                -- PDF 页码
    parse_confidence REAL DEFAULT 0.0,      -- AI 解析置信度
    verified        BOOLEAN DEFAULT FALSE,  -- 是否已人工审核
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 知识点标签表（多对多）
CREATE TABLE question_tags (
    question_id INTEGER REFERENCES questions(id),
    tag         TEXT NOT NULL,             -- 如 "chain_rule", "integration_by_parts"
    PRIMARY KEY (question_id, tag)
);

-- 索引
CREATE INDEX idx_questions_topic ON questions(topic);
CREATE INDEX idx_questions_difficulty ON questions(difficulty);
CREATE INDEX idx_questions_paper ON questions(paper_id);
CREATE INDEX idx_tags_tag ON question_tags(tag);
```

### 5.3 知识点分类体系（对齐现有 QuestionType）

你现有的 `QuestionType` enum 已经有了一套分类，题库应与之对齐：

| topic (大类) | subtopics (子类) |
|-------------|-----------------|
| differentiation | chain_rule, product_rule, quotient_rule, implicit, parametric |
| integration | by_parts, substitution, partial_fractions, definite, area |
| stationary_points | max_min, inflection, curve_sketching |
| algebra | quadratics, inequalities, partial_fractions, binomial |
| trigonometry | identities, equations, graphs, radians |
| vectors | dot_product, cross_product, lines, planes |
| sequences_series | arithmetic, geometric, convergence, sum_to_infinity |
| coordinate_geometry | circles, lines, tangent_normal |
| logarithms_exponentials | laws, equations, modelling |
| statistics | probability, distributions, hypothesis_testing |

---

## 6. 模块四：题库 API

### 6.1 新增 API 端点

在现有的 FastAPI 应用中新增路由：

```
GET  /questions/random          随机抽题
GET  /questions/{id}            获取单题详情
GET  /questions/topics           获取所有知识点列表
GET  /questions/papers           获取试卷列表
POST /questions/submit-answer    提交答案并批改（复用现有 grader）
GET  /questions/stats            题库统计信息
```

### 6.2 随机出题 API 详细设计

```
GET /questions/random?
    topic=differentiation        # 知识点（可选，支持多选）
    &difficulty_min=2            # 最低难度（可选）
    &difficulty_max=4            # 最高难度（可选）
    &count=5                     # 出题数量（默认5）
    &year_from=2020              # 起始年份（可选）
    &year_to=2024                # 截止年份（可选）
    &exclude_ids=1,5,12          # 排除已做过的题（可选）
    &paper_num=1                 # 指定 Paper 编号（可选）
    &verified_only=true          # 仅返回已审核题目（可选）
```

**响应示例：**

```json
{
  "status": "success",
  "questions": [
    {
      "id": 42,
      "question_number": "3(a)",
      "question_text": "Differentiate $y = x^3 \\sin(2x)$ with respect to $x$.",
      "marks": 4,
      "topic": "differentiation",
      "subtopic": "product_rule",
      "difficulty": 3,
      "source": {
        "subject": "9709",
        "year": 2023,
        "session": "s",
        "paper": 1,
        "variant": 2
      }
    }
  ],
  "total_available": 156
}
```

### 6.3 提交答案 API

```
POST /questions/submit-answer
{
  "question_id": 42,
  "student_answer": "$3x^2 \\sin(2x) + 2x^3 \\cos(2x)$",
  "working_steps": ["Applied product rule", "u = x^3, v = sin(2x)"]
}
```

这个端点可以直接复用现有的 `grader.grader.grade_question()`，把题库中的 `question_text` 和 `correct_answer` 作为上下文传给 grader。

---

## 7. 模块五：前端「练习模式」

### 7.1 新增页面/组件

```
frontend/src/
  components/
    practice/
      PracticeMode.tsx         # 练习模式入口
      TopicSelector.tsx        # 知识点选择器
      DifficultySlider.tsx     # 难度滑块
      QuestionCard.tsx         # 题目展示卡片
      AnswerInput.tsx          # 答案输入（支持 LaTeX）
      PracticeResult.tsx       # 练习结果（复用现有反馈组件）
      PracticeHistory.tsx      # 练习历史记录
```

### 7.2 用户流程

```
选择知识点/难度/数量
        ↓
   点击"开始练习"
        ↓
  ┌─→ 展示第 N 题 ─→ 输入答案 ─→ 提交 ─→ 显示批改结果
  │                                          ↓
  │                                    [下一题] / [查看解析]
  │                                          ↓
  └──────────────────────────────────── 继续 or 结束
                                             ↓
                                       练习总结报告
                                    (正确率、薄弱知识点)
```

### 7.3 LaTeX 输入支持

学生输入数学公式需要友好的界面。推荐方案：

- **方案A（推荐）**：纯文本输入 + AI 理解。学生用自然语言写答案（如 "3x^2 sin(2x) + 2x^3 cos(2x)"），AI 批改时自动理解。这与你现有的批改流程最一致。
- **方案B**：集成 MathQuill 或 MathLive 编辑器，提供可视化公式输入。体验更好但开发成本更高。

---

## 8. 实施路线图

### Phase 1: 基础设施（1-2 天）

- [ ] 确认 cie.fraft.cn 网站结构（需要你提供信息）
- [ ] 创建 `data/` 目录和数据库
- [ ] 设计并创建 SQLite 表
- [ ] 实现基础的数据库操作层 (CRUD)

### Phase 2: 爬虫 + 下载（1-2 天）

- [ ] 编写爬虫脚本 `scraper/crawler.py`
- [ ] 实现 PDF 下载和文件管理
- [ ] 添加断点续传支持
- [ ] 先爬 Mathematics 9709 作为试点

### Phase 3: PDF 解析入库（2-3 天）

- [ ] 实现 PDF → 图片转换
- [ ] 编写 AI 结构化提取 prompt
- [ ] 实现 Mark Scheme 匹配
- [ ] 批量解析并入库
- [ ] 抽样验证解析质量

### Phase 4: 题库 API（1 天）

- [ ] 实现随机出题 API
- [ ] 实现答案提交 + 批改对接
- [ ] 实现题库统计 API

### Phase 5: 前端练习模式（2-3 天）

- [ ] 练习模式页面骨架
- [ ] 知识点选择和出题流程
- [ ] 答案输入和提交
- [ ] 批改结果展示（复用现有组件）
- [ ] 练习历史和统计

### Phase 6: 优化迭代

- [ ] 题目去重（不同年份可能有相似题）
- [ ] 智能出题（根据学生弱项加权）
- [ ] 教师端题库管理界面
- [ ] 支持更多科目

---

## 9. 关键风险和应对

| 风险 | 影响 | 应对方案 |
|------|------|---------|
| 网站反爬/封 IP | 无法下载 PDF | 控制爬取速度（2-3秒/请求），使用随机 User-Agent |
| PDF 解析质量差 | 题目数据不准确 | 用高 DPI 转图片 + AI 视觉模型；增加人工审核机制 |
| 数学公式丢失 | 题目不完整 | 用图片模式（非文字提取）保留公式完整性 |
| 网站结构变化 | 爬虫失效 | 爬虫加异常检测和告警，定期维护 |
| AI 解析成本高 | 费用超预期 | 先小批量试跑估算成本；考虑缓存已解析结果 |

---

## 10. 新增依赖

```txt
# requirements.txt 新增
httpx>=0.27.0          # 异步 HTTP（爬虫）
beautifulsoup4>=4.12   # HTML 解析（爬虫）
PyMuPDF>=1.24.0        # PDF → 图片
aiosqlite>=0.20.0      # 异步 SQLite
```

---

## 11. 目录结构变更

```
alevel-teaching-assistant/
  ...（现有文件不变）
  scraper/                # 新增：爬虫模块
    __init__.py
    crawler.py            # 网站爬取
    downloader.py         # PDF 下载管理
    config.py             # 爬虫配置（URL 模式等）
  parser/                 # 新增：PDF 解析模块
    __init__.py
    pdf_to_images.py      # PDF 转图片
    question_extractor.py # AI 结构化提取
    ms_matcher.py         # Mark Scheme 匹配
  questionbank/           # 新增：题库模块
    __init__.py
    database.py           # SQLite 操作层
    models.py             # Pydantic 数据模型
    service.py            # 业务逻辑（随机出题等）
  api/
    routes.py             # 修改：新增题库路由
    qb_routes.py          # 新增：题库专用路由
    qb_schemas.py         # 新增：题库 API 模型
  data/                   # 新增：数据目录
    papers/               # PDF 存放
    questions.db           # SQLite 数据库
```

---

## 12. 已完成的代码实现

以下模块已经编写完成，可以直接使用：

| 模块 | 文件 | 状态 |
|------|------|------|
| 爬虫配置 | `scraper/config.py` | 已完成 |
| 爬虫脚本 | `scraper/crawler.py` | 已完成 |
| PDF 解析器 | `parser/pdf_parser.py` | 已完成 |
| 题库数据模型 | `questionbank/models.py` | 已完成 |
| 数据库操作层 | `questionbank/database.py` | 已完成 |
| 题库 API | `api/qb_routes.py` | 已完成 |
| API 注册 | `api/app.py` (已修改) | 已完成 |
| 依赖更新 | `requirements.txt` (已修改) | 已完成 |

## 下一步

代码已就绪，接下来需要：

1. **安装新依赖**: `pip install httpx beautifulsoup4 PyMuPDF`
2. **运行爬虫**: `python -m scraper.crawler --year-start 24 --year-end 25 --types qp ms` (先试 2024-2025)
3. **批量解析入库**: `python -m parser.pdf_parser data/papers/9709/ --batch`
4. **启动服务测试**: `python server.py` 然后访问 `/questions/random`
5. **开发前端练习模式** (Phase 5)
