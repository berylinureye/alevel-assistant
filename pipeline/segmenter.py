"""
Segmenter：整页图 → 一次 LLM 调用完成切题 + 内容提取；bbox 由程序近似生成（供 debug）。

精度优化：如果传入 ocr_client（专用 OCR 模型），会与 vision 模型并行调用，
用 OCR 的纯文字结果交叉校验数字/符号，修正 vision 模型的识别错误。
并行调用不增加总耗时（max(vl, ocr) ≈ vl）。
"""
from __future__ import annotations

import difflib
import logging
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw, ImageFont

from router.models import ModelClient, ModelRequest, TaskType
from utils.image_utils import image_to_base64
from utils.json_repair import parse_json_array

_OCR_PROMPT = (
    "Extract ALL text from this image exactly as it appears, preserving line breaks. "
    "Include every number, symbol, and formula character. "
    "Do not interpret, summarize, or translate. Output plain text only, no markdown."
)

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

_SEGMENT_EXTRACT_PROMPT = """\
RESPOND WITH ONLY A JSON ARRAY. No explanation, no markdown.

CRITICAL ROLE — YOU ARE A TRANSCRIBER, NOT A SOLVER.
Your job is to faithfully copy what the student actually wrote on paper — not what they *should* have written.
- If the student's working contains an arithmetic or algebraic MISTAKE (wrong expansion, wrong sign, wrong substituted point, missed term, arithmetic slip), COPY IT VERBATIM including the mistake.
- DO NOT silently "fix" the student's error. DO NOT regenerate a correct derivation in the `working_steps`. DO NOT fill in steps the student did not write.
- If a sub-question is blank or the student only wrote 1–2 lines and stopped, leave `student_answer` empty and put only the lines they actually wrote into `working_steps`. DO NOT invent continuation steps.
- The grader downstream depends on seeing the student's REAL work to diagnose their error. Any "helpful" correction from you will make the grader mark a wrong answer as correct.

FEW-SHOT — STUDY THESE CAREFULLY (CORRECT vs WRONG output):

Example A — Student made a wrong algebraic expansion:
  Handwriting on page shows: "(2x-4)^2 = 4x^2 - 8x + 16"  (the 8x is wrong; textbook answer is 16x)
  CORRECT: working_steps contains "(2x-4)^2 = 4x^2 - 8x + 16" verbatim.
  WRONG:   working_steps contains "(2x-4)^2 = 4x^2 - 16x + 16".  ← DO NOT silently correct 8x to 16x.

Example B — Student left the sub-question completely blank:
  Printed: "(c) Find the x-coordinates of A and B. [3]"
  Handwriting region below (c): nothing, no ink strokes, just blank paper.
  CORRECT: student_answer = "", working_steps = [].
  WRONG:   working_steps = ["x + y = 3", "substitute y = 3 - x", "(x+2)^2 + (5-x)^2 = 25", "x = 5 or x = -2"].
           ← DO NOT fabricate a derivation when no ink exists on the page.

Example C — Student wrote only 1–2 partial lines and stopped:
  Handwriting under (b): only "x_A + x_B = 3" is written; the rest of the space is blank.
  CORRECT: working_steps = ["x_A + x_B = 3"], student_answer = "x_A + x_B = 3" (or "").
  WRONG:   working_steps = ["x_A + x_B = 3", "m_CD = 1/7", "m_AB = -7", "y - 1.5 = -7(x - 1.5)", "y = -7x + 12"].
           ← DO NOT continue the derivation on the student's behalf.

Example D — Student used a wrong point in a tangent line:
  Handwriting: "y - (-2) = -3/4 (x - 4)"   (student mistakenly used centre C(4,-2) instead of Q(7,2))
  CORRECT: copy "y - (-2) = -3/4 (x - 4)" verbatim.
  WRONG:   output "y - 2 = -3/4 (x - 7)" (the textbook-correct form).  ← DO NOT swap the point.

BLANK-DETECTION PROTOCOL (apply to EACH sub-question independently):
1. Locate the handwriting region belonging to this sub-question (directly below its printed stem, and the right-margin area next to it).
2. Ask: "Do I see actual pen/pencil ink strokes here, or is this blank paper?"
3. If blank (no ink): set student_answer = "" and working_steps = []. Emit the entry so downstream knows it is unanswered — but do NOT put anything in working_steps.
4. If partial (≤2 lines of ink, no boxed/underlined final answer, lots of blank space after): copy ONLY the ink you see. Do not continue.
5. Self-check before emitting: if your working_steps reads like a clean textbook solution (uniform notation, complete chain from setup to final numeric answer, no scribbles or crossings-out), and the printed sub-question has marks ≥ 3 but you cannot point to specific ink strokes for each step — YOU ARE HALLUCINATING. Delete those steps and re-read the page.

RIGHT-MARGIN / ANSWER-COLUMN LAYOUT (critical — very common pattern):
Students frequently write their work in a SEPARATE COLUMN to the right of the printed questions (or in the top/bottom margin), NOT immediately under each printed question. In that column they write their own question-number labels ("2.", "3.", "(i)", "(ii)", "Ex2", etc.) to mark which printed question each block of work belongs to.
HARD RULES for this layout:
(R1) The STUDENT'S OWN handwritten label is the ground truth for question-association. If a handwritten block starts with "3." or "Q3" or "(ii)", that block belongs to question 3 / sub-part (ii) — EVEN IF it is physically drawn next to printed question 2 because the student ran out of space.
(R2) DO NOT associate handwriting with a printed question purely by vertical y-coordinate proximity. Always look for the student's own number label first. Only fall back to proximity when no handwritten label exists anywhere nearby.
(R3) Within ONE handwritten answer block you may see multiple sub-part labels like "(i)", "(ii)", "(iii)" inline or on separate lines. SPLIT them: each sub-part becomes its own entry, and each entry must receive ONLY the working/answer that follows ITS label up to the next label. Do NOT lump "(i) 29 (ii) 2.43 (iii) 5.9" into one student_answer of "29, 2.43, 5.9" — emit three entries with student_answer = "29", "2.43", "5.9" respectively.
(R4) Answers for multiple printed questions may share the right column in sequence (Q2's work on top, Q3's work below). Trace each printed question's sub-parts through the column using the handwritten labels. Do NOT assume one column = one question.
(R5) After assigning blocks to questions by label, scan again: for any printed sub-question that ended up with empty student_answer, double-check that its answer is not hiding under a mislabeled or unlabeled block in the right column / bottom margin. Common case: student wrote "(iii) variance = 5.9" on a line physically next to question 7 but belonging to question 2(iii).

Analyze this A-Level math homework. {multi_page_note}For each question/sub-question, output:
{{"question_number":"<e.g. 1, 2a, a, b>","parent_stem":"<shared setup for the parent question — see SHARED-STEM rules below; empty string '' if no setup>","question_text":"<the sub-part's OWN instruction only, e.g. 'Show that P(X=2)=3/7.'; if the question has no sub-parts, put the whole printed text here>","student_answer":"<final answer>","working_steps":["<step1>","<step2>"],"marks":<integer or 0 if not visible>,"is_example":false,"image_quality":"good|fair|poor","confidence":0.9,"page":<1-indexed page number where the question starts>,"contains_diagram":<true|false>,"diagram_type":"<stem_leaf|histogram|box_plot|cumulative_frequency|scatter|bar_chart|other|null>"}}

SHARED-STEM RULES (critical — many questions have a common setup plus labelled sub-parts (a)/(b)/(c)/(i)/(ii)):
- The "parent_stem" field MUST contain ONLY the shared setup that every sub-part of that printed question depends on (context, given data, tables, diagrams, random-variable definitions, geometric setup, etc.).
- The "question_text" field MUST contain ONLY the instruction of this specific sub-part (e.g. "Show that P(X=2)=3/7.", "Find the median and the interquartile range of the Gulls' times.", "Draw up the probability distribution table for X."). Do NOT repeat the stem inside question_text.
- Every sub-part belonging to the SAME printed question number MUST output IDENTICAL parent_stem text (verbatim same string, same table serialization, same numbers) — downstream we dedupe by comparing, and different wording breaks it.
- If the printed question has NO shared setup (a standalone single-instruction question like "Find dy/dx when y = x^2 + 3x"), set parent_stem to "" (empty string) and put the full instruction into question_text.
- TABLES inside the stem MUST be transcribed as text in parent_stem, one row per line, with the row label (if any) on the left. Example:
    A bag contains 10 marbles, of which 4 are red and 6 are blue...
  or for a 2-row table:
    Last Sunday, teams of runners... The times recorded for 11 runners from each of the Gulls and the Herons are shown in the table.
    Gulls: 7.9, 8.2, 8.3, 8.6, 8.6, 8.8, 9.2, 9.7, 9.8, 10.0, 10.4
    Herons: 9.5, 9.9, 8.5, 8.1, 9.2, 10.8, 8.3, 9.7, 9.3, 9.9, 8.7
  For a grouped-frequency table, transcribe header row then each body row in full. Do not summarize, do not skip rows.
- DIAGRAMS given in the stem (printed triangle, circle, tree diagram, etc.): describe the key labelled features in parent_stem (points, lengths, angles, probabilities on branches) so the grader has the same info the student sees.
- CROSS-PAGE PARENT STEM (critical — read carefully):
  * If the sub-part you're emitting is on a CONTINUATION page (page N+1) and the full setup is printed earlier on page N that you CAN also see in the input, copy that page-N stem verbatim into parent_stem.
  * If the sub-part is on a continuation page and the earlier page is NOT in your input (only this continuation page was sent), you WILL NOT see the original stem. In that case set parent_stem = "" (empty string) — downstream code will inherit the correct stem from the prior page's output. DO NOT guess, paraphrase, or fabricate a stem you cannot read. A fabricated stem with wrong numbers (e.g. "12 marbles, 7 red, 5 blue" when the original printed "10 marbles, 4 red, 6 blue") will cascade into wrong final answers — it is strictly better to leave parent_stem empty and let inheritance fill it.
- STEM-NUMBER ACCURACY (critical — every digit matters):
  * When the stem contains integer counts ("N marbles", "K red, M blue", "drawn without replacement", "n trials", sample sizes, frequencies), transcribe EACH integer exactly as printed. A single misread digit (10 → 12, 4 → 7, 6 → 5) silently changes the whole probability distribution and cascades into wrong answers for every sub-part.
  * Before emitting parent_stem, re-read each numeric token once more against the image. If a digit is blurry, prefer the reading arithmetically consistent with any "Show that P(...) = <value>" target printed in a sub-part (those targets let you sanity-check the stem's counts).

IMPORTANT:
- Scan the ENTIRE page(s): students write work in ALL areas — right side, margins, next to questions, not just below.
- CROSS-PAGE CONTINUATION: a question may start on one page and continue on the next (题目文字、working steps 或 final answer 可能跨页). Merge all parts under ONE entry keyed by the original question_number. DO NOT emit duplicate entries for continued portions.
- ORIENTATION: if any image appears rotated (text sideways / upside-down / landscape paper captured as portrait or vice versa), STILL read and extract it correctly. Do not skip rotated images.
- SUB-QUESTION SPLITTING (critical): if a printed question contains multiple sub-parts labeled "(i)", "(ii)", "(iii)", "(a)", "(b)", "(c)" — each with its own instruction verb ("Find…", "Show…", "Calculate…") or its own mark allocation — you MUST emit ONE SEPARATE entry per sub-part. Use question_number like "11(i)", "11(ii)", "2a", "2b". Do NOT merge sub-parts into a single entry just because they share a stem; the stem (common setup text) should be included in the question_text of each sub-part so the sub-part is self-contained.
- When splitting sub-parts, carefully match EACH sub-part's working/answer to the correct sub-part. Students may write (i)/(ii) labels next to their work, or answers may appear in order top-to-bottom. If a student only answered one sub-part, the other sub-part entry should still be emitted with empty student_answer and working_steps (so the system knows it's unanswered, not missing).
- Look for labeled sections "(a)", "(b)", "(c)" in handwriting — these are answers to sub-questions.
- If a page has ONLY handwritten work (no printed questions), still extract each labeled section.
- Include faint pencil marks. If working exists but no clear final answer, use the last result as student_answer.
- Use plain text math (x^2, sqrt(x), frac(a,b)).
- "marks": look for mark allocations printed in square brackets like [2], [3], [4], [5] at the end of each question or sub-question. Extract as integer. If not visible, use 0.
- "is_example": set to true if ANY of these apply (do NOT grade examples):
  * Heading contains "Example", "示例", "Sample", "Worked example", "例题"
  * The "answer" or "solution" is PRINTED in the same typeset font as the question (not handwritten) — this is a textbook walkthrough
  * The work shown is a complete formal solution with no student handwriting interventions
  * Located in a section labeled "Examples", "Solved Examples", or appears between an "Exercise" header and exercise problems
- SHOW/PROVE TARGET EQUATIONS (critical — do not misread a single digit):
  * When the printed question says "Show that ... is <equation>", "Prove that ... = <value>", "Hence show that ...", or similar, the <equation>/<value> is the EXACT target the student must derive. A single-digit misread (e.g. 3 vs 4, 7 vs 1, + vs −) will flip a correct student to "wrong".
  * Read every coefficient, sign, exponent, and constant in the target digit-by-digit. Prefer the reading that is arithmetically consistent with the rest of the question's setup (e.g. if the student's derivation yields 3x+5, and the target looks like "4x+5" but is blurry, the correct reading is likely "3x+5").
  * If the target is ambiguous, copy it verbatim from the printed text rather than guessing.
- NUMBER ACCURACY (critical for statistics): when reading tables, frequencies, or numerical data:
  * Read each digit carefully — distinguish 0/O, 1/l/I, 5/S, 6/G, 8/B
  * For tables with frequencies: re-verify that row totals or partial sums make sense
  * For decimals: preserve exact decimal places the student wrote (e.g. 43.35 NOT 43.4)
  * If a digit is genuinely ambiguous, prefer the reading that makes the student's calculation arithmetically self-consistent
- DIAGRAM-AS-ANSWER DETECTION (critical for statistics — do not miss):
  * If the question asks the student to "Draw" / "Sketch" / "Construct" / "Plot" a statistical
    diagram (stem-and-leaf, histogram, box-and-whisker / box plot, cumulative frequency curve,
    scatter plot, bar chart) AND the student's answer region has visible drawn elements
    (stems+leaves, bars, whiskers/boxes, curves, plotted points, axes with tick marks) instead of
    (or in addition to) numeric text — set "contains_diagram": true and fill "diagram_type".
  * diagram_type must be one of: stem_leaf, histogram, box_plot, cumulative_frequency, scatter,
    bar_chart, other. If the drawing is clearly present but does not fit any category, use "other".
  * For contains_diagram=true, set student_answer to a short placeholder like
    "[stem-and-leaf diagram drawn]" — do NOT try to transcribe every digit in the diagram.
    working_steps may still contain any numeric pre-work the student wrote.
  * If the student did NOT draw anything (only wrote numbers/text), leave contains_diagram=false.
  * Do NOT set contains_diagram=true merely because the question asks to draw — the student's
    region must actually show a drawing. A blank drawing area still counts as unanswered, not as
    a diagram answer.
- FINAL ANSWER vs INTERMEDIATE NUMBER (critical — do not confuse):
  * The student's final answer is the LAST result of that sub-question, usually after "=", "∴", "≈" or in a box/underline at the very end of the sub-question's working.
  * DO NOT mistake intermediate quantities (row totals, Σf values, denominators like "÷20" or "÷400", frequencies summed to e.g. 40) for the final answer.
  * If the student wrote a fraction then its decimal (e.g. "= 359/8 = 44.875"), the final answer is whichever appears LAST — prefer the decimal if both are written.
  * Preserve fractions verbatim: if the student wrote "867/20" or "\\frac{{359}}{{8}}", put that EXACT form in student_answer (never just the numerator or denominator alone).
  * For multi-part sub-questions (e.g. "find median AND IQR"), record both results in student_answer separated by ", " (e.g. "median=51, IQR=15").
  * If no final answer is clearly written, use the last line of working verbatim — do not invent a number.
{user_context}
"""


def _generate_approximate_bboxes(
    num_questions: int, width: int, height: int
) -> list[list[int]]:
    """
    根据题目数量，把页面等分为垂直条带，生成近似 bbox。
    这只用于 debug 可视化，不影响批改逻辑。
    """
    if num_questions <= 0:
        return []
    strip_height = height // num_questions
    bboxes = []
    for i in range(num_questions):
        y1 = i * strip_height
        y2 = min((i + 1) * strip_height, height)
        bboxes.append([0, y1, width, y2])
    return bboxes


def _call_ocr(b64: str, ocr_client: ModelClient) -> str:
    """调用专用 OCR 模型拿整图纯文字。失败返回空串，不阻塞主流程。"""
    try:
        req = ModelRequest(
            task=TaskType.extract,
            prompt=_OCR_PROMPT,
            images=[b64],
            max_tokens=4096,
            temperature=0.0,
        )
        return ocr_client.call(req) or ""
    except Exception as e:
        logging.getLogger("pipeline.segmenter").warning("OCR call failed: %s", e)
        return ""


# ---------------------------------------------------------------------------
# 跨页分组：续页（页首没有 1./2./3. 题号）回合并到前一页一起送 VLM
# ---------------------------------------------------------------------------
# 页顶抠这么大一条做 OCR：足够看到题号，又比整页快很多（多半 2-3s）
_PAGE_HEADER_CROP_RATIO = 0.18
# 匹配页首第一行的题号，如 "1.", "2)", "3 ", "11(i)", "*5."、中文全角"1．"等
_LEADING_QNUM_RE = re.compile(r"^\s*[*\[【]?\s*(\d+)\s*[.)．、。\s(]")


def _page_header_text(img: Image.Image, ocr_client: ModelClient) -> str:
    """OCR 页面顶端窄条，判断本页是否以新题开头。抠小图成本远低于整页 OCR。"""
    w, h = img.size
    crop_h = max(140, int(h * _PAGE_HEADER_CROP_RATIO))
    crop = img.crop((0, 0, w, crop_h))
    try:
        return _call_ocr(image_to_base64(crop), ocr_client)
    except Exception:
        return ""


def page_starts_with_numbered_question(header_text: str) -> bool:
    """页首第一个非空行是否以 "1." / "2)" / "11(i)" 这种题号开头。
    False 表示本页是续页（纯工作区 / 续写题干 / 延续小题）。"""
    if not header_text:
        return False
    for raw in header_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        return bool(_LEADING_QNUM_RE.match(line))
    return False


def group_pages_by_continuity(
    images: list[Image.Image],
    ocr_client: ModelClient | None,
) -> list[list[int]]:
    """按"页首是否有新题号"把连续页分组。续页与前一页合并，独立页各自成组。

    返回分组列表，每组是 0-based 页索引数组。典型情况：
      [[0], [1], [2]]        — 三张独立图，每组走一次 segmenter（并行）
      [[0, 1]]               — 两张图是同一道题的主页+续页，合并调一次 segmenter
      [[0], [1, 2]]          — 第 1 张独立，第 2+3 是连续的跨页题

    没有 ocr_client 时退化为单一大组（保留旧行为，不会比现在更慢）。
    """
    log = logging.getLogger("pipeline.segmenter")
    if not images:
        return []
    if len(images) == 1 or ocr_client is None:
        return [list(range(len(images)))]

    with ThreadPoolExecutor(max_workers=min(len(images), 5)) as pool:
        headers = list(pool.map(lambda im: _page_header_text(im, ocr_client), images))
    for i, h in enumerate(headers):
        preview = " ".join((h or "").split())[:80]
        log.info("page %d header preview: %r", i + 1, preview)

    groups: list[list[int]] = [[0]]
    for i in range(1, len(images)):
        if page_starts_with_numbered_question(headers[i]):
            groups.append([i])
        else:
            groups[-1].append(i)
    log.info("page grouping: %d pages → %d groups: %s", len(images), len(groups), groups)
    return groups


def _correct_numbers(vl_text: str, ocr_text: str, window: int = 12) -> str:
    """
    用 OCR 文字修正 vl_text 中的数字识别错误。
    规则：对 vl_text 中每个数字串，取它在 vl_text 里前后 window 个字符作为上下文，
    在 ocr_text 中用 SequenceMatcher 找最相似的上下文窗口；如果 OCR 在相同语义位置
    是另一个数字，就替换。只在上下文匹配度 >= 0.7 时替换，避免误伤。
    """
    if not vl_text or not ocr_text:
        return vl_text

    ocr_low = ocr_text.lower()
    result_parts: list[str] = []
    last = 0
    for m in _NUMBER_RE.finditer(vl_text):
        num = m.group(0)
        start, end = m.span()
        ctx_before = vl_text[max(0, start - window):start].lower()
        ctx_after = vl_text[end:end + window].lower()

        # 在 OCR 中找最相似的前缀上下文
        best_ratio = 0.0
        best_pos = -1
        if ctx_before.strip():
            matcher = difflib.SequenceMatcher(None, ocr_low, ctx_before)
            match = matcher.find_longest_match(0, len(ocr_low), 0, len(ctx_before))
            if match.size >= max(3, len(ctx_before.strip()) // 2):
                # 上下文匹配位置之后就是候选数字
                candidate_pos = match.a + match.size
                ratio = match.size / max(len(ctx_before), 1)
                if ratio >= 0.5:
                    best_ratio = ratio
                    best_pos = candidate_pos

        replaced = num
        if best_pos >= 0 and best_pos < len(ocr_text):
            # 从 best_pos 开始找第一个数字
            tail = ocr_text[best_pos:best_pos + window + len(num) + 4]
            ocr_num_match = _NUMBER_RE.search(tail)
            if ocr_num_match:
                ocr_num = ocr_num_match.group(0)
                # 只在长度相近且内容不同时替换（避免 "3" 被换成 "3.14159"）
                if ocr_num != num and abs(len(ocr_num) - len(num)) <= 1:
                    # 再校验后置上下文
                    after_ocr = ocr_text[best_pos + ocr_num_match.end():
                                          best_pos + ocr_num_match.end() + window].lower()
                    if ctx_after.strip() and difflib.SequenceMatcher(
                        None, after_ocr, ctx_after
                    ).ratio() >= 0.5:
                        replaced = ocr_num

        result_parts.append(vl_text[last:start])
        result_parts.append(replaced)
        last = end
    result_parts.append(vl_text[last:])
    return "".join(result_parts)


def _merge_ocr(items: list[dict], ocr_text: str) -> list[dict]:
    """用 OCR 结果修正 vision 模型提取的字段（主要是数字）"""
    if not ocr_text.strip():
        return items
    for it in items:
        for field in ("question_text", "student_answer"):
            v = it.get(field, "")
            if isinstance(v, str) and v:
                it[field] = _correct_numbers(v, ocr_text)
        ws = it.get("working_steps", [])
        if isinstance(ws, list):
            it["working_steps"] = [
                _correct_numbers(str(s), ocr_text) if s else s for s in ws
            ]
    return items


_QNUM_STRIP_RE = re.compile(r"[\s().,:：]+")


def _normalize_qnum(qn: object) -> str:
    """
    题号归一化：去空格/括号/标点，统一小写。
    同桶：'1' = '1.' = ' 1 '；'1(i)' = '1i' = '1 (i)'；'1(a)' = '1a'。
    不同桶：'1' ≠ '1a'；'1(i)' ≠ '1(ii)'（子题独立评分）。
    """
    if qn is None:
        return ""
    s = str(qn).strip().lower()
    s = _QNUM_STRIP_RE.sub("", s)
    return s


_QUALITY_RANK = {"good": 3, "fair": 2, "poor": 1}


def _merge_cross_page_items(items: list[dict]) -> list[dict]:
    """
    方案 1：题号归一化后在 CPU 层合并跨页条目。
    同一归一化题号下：
      - question_text / student_answer：取第一个非空（若多个非空取最长）
      - working_steps：按出现顺序拼接，去相邻重复
      - marks / confidence：取最大
      - image_quality：good > fair > poor
      - page：取最小（最早出现页用于排序）
      - bbox / question_number：沿用「主题目页」（question_text 最长那一条）
    纯字符串处理，不调用任何模型。
    """
    buckets: dict[str, list[int]] = {}
    order: list[str] = []
    for i, it in enumerate(items):
        key = _normalize_qnum(it.get("question_number", ""))
        if not key:
            key = f"__orphan_{i}"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(i)

    merged: list[dict] = []
    for key in order:
        idxs = buckets[key]
        if len(idxs) == 1:
            merged.append(items[idxs[0]])
            continue

        group = [items[i] for i in idxs]

        # 主条目：question_text 最长的那条（最有可能是题目页）
        def _qt_len(it: dict) -> int:
            v = it.get("question_text")
            return len(v.strip()) if isinstance(v, str) else 0
        main_pos = max(range(len(group)), key=lambda j: _qt_len(group[j]))
        main = group[main_pos]
        merged_item: dict = dict(main)

        def _best_text(field: str) -> str:
            best = ""
            for it in group:
                v = it.get(field)
                if isinstance(v, str) and v.strip() and len(v) > len(best):
                    best = v
            return best

        merged_item["question_text"] = _best_text("question_text")
        merged_item["student_answer"] = _best_text("student_answer")
        merged_item["parent_stem"] = _best_text("parent_stem")

        all_ws: list[str] = []
        for it in group:
            ws = it.get("working_steps")
            if not isinstance(ws, list):
                continue
            for s in ws:
                if s is None:
                    continue
                t = str(s).strip()
                if not t:
                    continue
                if all_ws and t == all_ws[-1]:
                    continue
                all_ws.append(t)
        merged_item["working_steps"] = all_ws

        marks = 0
        for it in group:
            try:
                m = int(it.get("marks", 0) or 0)
            except (ValueError, TypeError):
                m = 0
            if m > marks:
                marks = m
        merged_item["marks"] = marks

        conf = 0.0
        for it in group:
            try:
                c = float(it.get("confidence", 0.0) or 0.0)
            except Exception:
                c = 0.0
            if c > conf:
                conf = c
        merged_item["confidence"] = conf

        best_q = ""
        for it in group:
            q = str(it.get("image_quality", "") or "").lower()
            if _QUALITY_RANK.get(q, 0) > _QUALITY_RANK.get(best_q, 0):
                best_q = q
        if best_q:
            merged_item["image_quality"] = best_q

        pages: list[int] = []
        for it in group:
            try:
                pages.append(int(it.get("page", 1) or 1))
            except (ValueError, TypeError):
                continue
        if pages:
            merged_item["page"] = min(pages)

        merged.append(merged_item)

    if len(merged) != len(items):
        logging.getLogger("pipeline.segmenter").info(
            "cross-page merge: %d items → %d (collapsed %d)",
            len(items), len(merged), len(items) - len(merged),
        )
    return merged


_STITCH_SEP_HEIGHT = 70
_STITCH_BATCH_SIZE = 3         # 每组最多拼 N 页
_STITCH_MAX_BATCH_HEIGHT = 3500  # 每组拼接后最大像素高度，超过则该组回退分页
_STITCH_LABEL_COLOR = (60, 60, 60)
_STITCH_BAR_COLOR = (235, 235, 235)


def _load_label_font(size: int = 32) -> ImageFont.ImageFont:
    # 按平台找一个能用的 TrueType，找不到退回 PIL 默认位图字体。
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",              # macOS
        "/System/Library/Fonts/Supplemental/Arial.ttf",     # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "C:/Windows/Fonts/arial.ttf",                       # Windows
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _stitch_pages(
    images: list[Image.Image],
    start_page: int = 1,
    max_total_height: int = _STITCH_MAX_BATCH_HEIGHT,
) -> Image.Image | None:
    """
    方案 2：纵向拼图。把 N 页按同一宽度上下拼成一张长图，每页前插一条「— Page N —」分隔条。
    `start_page` 指定第一页的全局页号（便于批量拼图时保持全局编号连续）。
    总高度超阈值时返回 None，调用方可选择分批或回退分页。
    """
    if len(images) < 2:
        return None

    target_w = max(im.size[0] for im in images)
    scaled: list[Image.Image] = []
    for im in images:
        if im.size[0] != target_w:
            ratio = target_w / im.size[0]
            new_h = max(1, int(im.size[1] * ratio))
            scaled.append(im.resize((target_w, new_h), Image.LANCZOS))
        else:
            scaled.append(im)

    total_h = sum(im.size[1] for im in scaled) + _STITCH_SEP_HEIGHT * len(scaled)
    if total_h > max_total_height:
        logging.getLogger("pipeline.segmenter").info(
            "stitch skipped: total height %d > %d", total_h, max_total_height,
        )
        return None

    canvas = Image.new("RGB", (target_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    font = _load_label_font(32)

    y = 0
    for i, im in enumerate(scaled):
        draw.rectangle([(0, y), (target_w, y + _STITCH_SEP_HEIGHT)], fill=_STITCH_BAR_COLOR)
        label = f"— Page {start_page + i} —"
        try:
            bbox = draw.textbbox((0, 0), label, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = len(label) * 12, 20
        draw.text(
            ((target_w - tw) // 2, y + (_STITCH_SEP_HEIGHT - th) // 2),
            label,
            fill=_STITCH_LABEL_COLOR,
            font=font,
        )
        y += _STITCH_SEP_HEIGHT
        canvas.paste(im, (0, y))
        y += im.size[1]

    return canvas


def _batch_stitch_pages(
    images: list[Image.Image],
    batch_size: int = _STITCH_BATCH_SIZE,
) -> list[Image.Image]:
    """
    把 N 页按 batch_size 分组，每组尝试拼成一张长图。
    拼不下（超高度阈值）的那组自动回退为组内逐页。
    单页组不拼图，直接返回原页。
    返回的图像列表顺序与原页顺序一致，只是相邻 2~3 页在同一张里。
    """
    if len(images) < 2:
        return list(images)

    out: list[Image.Image] = []
    for i in range(0, len(images), batch_size):
        group = images[i:i + batch_size]
        if len(group) == 1:
            out.append(group[0])
            continue
        stitched = _stitch_pages(group, start_page=i + 1)
        if stitched is None:
            out.extend(group)
        else:
            out.append(stitched)
    return out


_TOKEN_NUM_RE = re.compile(r"\d+(?:\.\d+)?")

_MATH_SUB = [
    ("²", "**2"), ("³", "**3"), ("⁴", "**4"),
    ("×", "*"), ("·", "*"), ("÷", "/"),
    ("^", "**"),
    ("，", ","), ("（", "("), ("）", ")"),
]

_SQRT_NUM_RE = re.compile(r"√\s*(\d+(?:\.\d+)?)")
_ANSWER_ASSIGN_RE = re.compile(r"^\s*([a-zA-Z][\w_]*)\s*=\s*(.+?)\s*$")


def _normalize_math(s: str) -> str:
    # `√45` → `sqrt(45)`（带裸数字的 sqrt 必须加括号，否则 sympy 会当成符号 "sqrt45"）
    s = _SQRT_NUM_RE.sub(r"sqrt(\1)", s)
    s = s.replace("√", "sqrt")  # `√(expr)` 情形
    for a, b in _MATH_SUB:
        s = s.replace(a, b)
    return s.strip()


def _arithmetic_inconsistent(sa: str, ws: list[str]) -> str | None:
    """
    用 sympy 验证 student_answer 是否满足 working_steps 最后一个等式。
    解析失败/不适用 → 返回 None（保守放过，避免假阳性）。
    命中 → 返回 reason 字符串。
    只检查最简单形式：`var = expr`（支持 ± 展开成两个值，支持 "or"）。
    """
    if not sa or not ws:
        return None
    try:
        from sympy import Symbol, simplify
        from sympy.parsing.sympy_parser import (
            parse_expr, standard_transformations,
            implicit_multiplication_application, convert_xor,
        )
    except Exception:
        return None
    transforms = standard_transformations + (implicit_multiplication_application, convert_xor)

    sa_norm = _normalize_math(sa)
    # 支持 "x = a or b" 和 "x = a ± b" 两种多值形式
    m = _ANSWER_ASSIGN_RE.match(sa_norm)
    if not m:
        return None
    var, expr_str = m.group(1), m.group(2)
    # 先按 " or " 分，再在每段里展开 ±，允许两者同时出现
    parts = [p.strip() for p in re.split(r"\bor\b", expr_str)] if re.search(r"\bor\b", expr_str) else [expr_str]
    candidates: list[str] = []
    for part in parts:
        if not part:
            continue
        if "±" in part:
            candidates.append(part.replace("±", "+"))
            candidates.append(part.replace("±", "-"))
        else:
            candidates.append(part)

    # 找 working_steps 里最后一个干净的 LHS = RHS（单等号、非赋值链）
    last_eq: tuple[str, str] | None = None
    for step in reversed(ws):
        s = _normalize_math(str(step))
        if s.count("=") != 1:
            continue
        lhs, rhs = [p.strip() for p in s.split("=", 1)]
        if not lhs or not rhs:
            continue
        # 跳过纯变量赋值（如 y = 2x - 4，这类是定义不是约束）
        if re.fullmatch(r"[a-zA-Z_][\w_]*", lhs) and len(rhs) > 2:
            continue
        last_eq = (lhs, rhs)
        break
    if last_eq is None:
        return None

    try:
        lhs_expr = parse_expr(last_eq[0], transformations=transforms)
        rhs_expr = parse_expr(last_eq[1], transformations=transforms)
    except Exception:
        return None
    diff = lhs_expr - rhs_expr
    sym = Symbol(var)
    if sym not in diff.free_symbols:
        return None

    for cand in candidates:
        try:
            val = parse_expr(cand, transformations=transforms)
        except Exception:
            return None  # 解析不了就保守放过
        try:
            residual = simplify(diff.subs(sym, val))
        except Exception:
            return None
        if residual != 0:
            return (
                f"answer {var}={cand} does not satisfy '{last_eq[0]} = {last_eq[1]}' "
                f"(residual={residual})"
            )
    return None


def _flag_inconsistencies(items: list[dict]) -> None:
    """
    纯 Python 自洽检测：working_steps 和 student_answer 不一致时标 needs_review。
    不调用任何模型，微秒级耗时，不影响用户体验。

    规则：
    1. 有 working_steps 且最后一步含 '=' 但 student_answer 为空、marks ≥ 2：答案漏抽。
    2. student_answer 中的「长数字」(≥2 位) 在 working_steps + question_text 中找不到：疑似幻觉/错读。
    3. student_answer 非空但 working_steps 空、marks ≥ 3：大题只有答案没过程，可疑。
    """
    for it in items:
        sa = str(it.get("student_answer", "") or "").strip()
        ws = it.get("working_steps", []) or []
        qt = str(it.get("question_text", "") or "")
        try:
            marks = int(it.get("marks", 0) or 0)
        except Exception:
            marks = 0

        reasons: list[str] = []

        if ws and not sa and marks >= 2:
            last = str(ws[-1])
            if "=" in last:
                reasons.append("working ends with '=' but student_answer empty")

        if sa and ws:
            sa_nums = set(_TOKEN_NUM_RE.findall(sa))
            ctx = " ".join(str(s) for s in ws) + " " + qt
            ctx_nums = set(_TOKEN_NUM_RE.findall(ctx))
            orphan = {n for n in sa_nums if n not in ctx_nums and len(n) >= 2}
            if orphan:
                reasons.append(f"answer numbers not traceable: {sorted(orphan)}")

        if sa and not ws and marks >= 3:
            reasons.append(f"answer without any working (marks={marks})")

        arith_reason = _arithmetic_inconsistent(sa, [str(s) for s in ws])
        if arith_reason:
            reasons.append(arith_reason)

        if reasons:
            it["needs_review"] = True
            it["review_reason"] = "; ".join(reasons)
            try:
                conf = float(it.get("confidence", 0.9) or 0.9)
            except Exception:
                conf = 0.9
            it["confidence"] = max(0.0, conf - 0.2)


# ---------------------------------------------------------------------------
# Orphan sub-question detection + parent stem recovery
# ---------------------------------------------------------------------------
# 一个「孤儿子题」= 题号形如 "(i)"/"(ii)"/"(a)"/"(b)" 等纯子标签，没有父题编号前缀
# (如 "7(i)"/"2a")。这类题通常是 OCR/segmenter 在翻页时丢了父题号，导致批改时
# 完全看不到上文条件。我们往前扫描，把最近一个有完整题干的父题的 question_text
# 作为 parent_stem 回填给这些孤儿。

# 匹配 "(i)"、"ii"、"(a)"、"B" 等纯子标签（不含数字前缀）
_ORPHAN_QNUM_RE = re.compile(
    r"^\s*\(?\s*(?:[ivxIVX]{1,4}|[a-eA-E])\s*\)?\s*\.?\s*$"
)
# 匹配 "7"、"7(i)"、"2a"、"11(ii)" 等带数字的题号（可做 parent）
_NUMBERED_QNUM_RE = re.compile(r"^\s*\d+")

# 在一段题干文字里找到第一个子问标记 "(a)" / "(i)" 等，返回其 start 索引；找不到返回 -1
_SUBPART_MARKER_RE = re.compile(
    r"[\(（]\s*(?:[ivxIVX]{1,4}|[a-eA-E])\s*[\)）]"
)

# 从裸孤儿 qnum（"c" / "(ii)" / "a." 等）里拎出子标签
_ORPHAN_LABEL_RE = re.compile(r"(?:[ivxIVX]{1,4}|[a-eA-E])")


def _extract_orphan_label(qnum: str) -> str | None:
    m = _ORPHAN_LABEL_RE.search(qnum)
    return m.group(0).lower() if m else None


def _is_orphan_qnum(qn: str) -> bool:
    if not qn:
        return False
    s = str(qn).strip()
    if not s:
        return False
    # "7(i)" / "2a" / "11" 都算正常题号（前缀是数字）
    if _NUMBERED_QNUM_RE.match(s):
        return False
    return bool(_ORPHAN_QNUM_RE.match(s))


# ---------------------------------------------------------------------------
# Rescue trailing bridging sentences from question_text → next item's ps.
# Phase 1: handles the "POLLUTED_QT" variant observed in the user's
# 2026-04-18 23:18 screenshot (qwen3-vl-plus non-deterministically appends
# a next-sub-part bridging sentence to current sub-part's qt).
# Phase 2 (not yet implemented): shift-by-one prepend (bridging at START
# of next sub-part's qt, historical qwen-vl-max pattern). See
# test/fixtures/rescue_bridging/adv_3_shift_by_one_prepend.json.
# ---------------------------------------------------------------------------

# Unicode dash family — all collapse to ASCII '-' for structural matching.
# U+2212 MINUS SIGN / U+2010 HYPHEN / U+2011 NB-HYPHEN / U+2013 EN DASH /
# U+2014 EM DASH. Seen counts in bench_out_*.json corpus: 0/0/0/6/15.
_BRIDGING_DASH_FAMILY = ("\u2212", "\u2010", "\u2011", "\u2013", "\u2014")
# U+2044 FRACTION SLASH — appears post-NFKC of vulgar fractions like '½'
# (NFKC of U+00BD → '1\u20442').
_BRIDGING_FRACTION_SLASH = "\u2044"

# Instruction-opener whitelist, case-insensitive, tokens stripped of trailing
# punctuation. Derived from a frequency scan of 248 sub-parts across 18 real
# Cambridge 9709 QPs (s22/w22/s23/w23/s24/w24 × papers 11/41/51) plus
# standard CAIE vocabulary additions. Coverage: top-24 observed tokens cover
# 95% of sub-part openers in that sample. A qt sentence starting with any of
# these is treated as an INSTRUCTION and never strippable.
_INSTRUCTION_OPENERS: frozenset = frozenset({
    # Observed imperatives (by frequency, highest first)
    "find", "show", "express", "draw", "use", "sketch", "state",
    "determine", "verify", "prove", "explain", "calculate", "write",
    "describe", "make", "expand", "deduce", "solve",
    # Standard CAIE vocabulary — rarer than the above in the 18-paper
    # sample but unambiguously imperative when they appear
    "evaluate", "obtain", "simplify", "differentiate", "integrate",
    "derive", "estimate", "factorise", "factorize", "identify",
    "plot", "construct", "complete", "compute",
    # Connective / qualifier instruction starters
    "hence", "by", "using", "without", "assuming",
})

# Split on sentence boundary: period/?/! followed by whitespace. The
# look-behind prevents splits inside numeric literals (3.14, P(1, 2)),
# since those have no trailing whitespace after the dot.
_RESCUE_SENTENCE_SPLIT = re.compile(r"(?<=[.?!])\s+")


def _rescue_normalize(s: str) -> str:
    """Normalize a sentence for fuzzy structural matching across VL runs.

    Rules (calibrated against bench_out_*.json character inventory — 21
    distinct non-ASCII chars observed — and user-flagged hazards):
      1. Unicode NFKC — collapses compatibility equivalents
         (superscripts ²³ → 2/3, subscripts ₁₂ → 1/2, vulgar fractions
         ½ → '1⁄2' pending slash normalization below).
      2. Dash family (_BRIDGING_DASH_FAMILY) → ASCII hyphen '-'.
      3. Fraction slash U+2044 → ASCII '/'.
      4. Math operators: ×→*, ÷→/, ·→*.
      5. π → 'pi' (defensive; 0 occurrences in current corpus but trivial
         to support and standard CAIE usage).
      6. Lowercase.
      7. Keep only [a-z0-9+-*/=().,^] — drops all whitespace, quotes,
         non-structural punctuation, inequality/equality symbols (≥≤≈).

    Two sentences that differ only in spacing ('P(1,2)' vs 'P(1, 2)'),
    case, Unicode math representation, or dash variant will normalize to
    identical strings. Paraphrases will NOT match (that's desired — we
    want structural identity, not semantic similarity).
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    for dash in _BRIDGING_DASH_FAMILY:
        s = s.replace(dash, "-")
    s = s.replace(_BRIDGING_FRACTION_SLASH, "/")
    s = s.replace("\u00d7", "*").replace("\u00f7", "/").replace("\u00b7", "*")
    s = s.replace("\u03c0", "pi")
    s = s.lower()
    return re.sub(r"[^a-z0-9+\-*/=().,^]", "", s)


def _rescue_starts_with_instruction(sentence: str) -> bool:
    """Return True iff the sentence's leading token (lowercased, trailing
    punctuation stripped) is in _INSTRUCTION_OPENERS. Tolerates 'Find,'
    / 'Calculate,' — the comma-suffixed form seen 2× each in the
    real-paper sample."""
    if not sentence:
        return False
    tokens = sentence.strip().split(None, 1)
    if not tokens:
        return False
    first = tokens[0].lower().rstrip(",.;:)")
    return first in _INSTRUCTION_OPENERS


def _rescue_trailing_bridging_to_next_stem(
    results: list[dict],
    group_stems: dict,
) -> None:
    """Step 1.5 of _attach_parent_stems — strip trailing "bridging"
    sentences from an item's question_text when that bridging belongs
    to the NEXT sub-part's setup, not the current sub-part's instruction.

    BUG CONTEXT
    -----------
    User-reported 2026-04-18 23:18 screenshot of Lesson2 PDF: 1a's
    "本小题" block showed the real instruction ("Find the radius... of C.")
    concatenated with a bridging sentence ("The point P(1, 2) lies on
    the circle.") that belongs to (b)'s setup. Investigation found
    qwen3-vl-plus is non-deterministic across runs even at
    temperature=0.0: an N=8 stress test on the same PDF produced 3
    distinct structural variants of ps/qt boundary placement. The
    23:18 screenshot matches the "POLLUTED_QT" variant.

    SCOPE
    -----
    Phase 1 (this function): strip trailing bridging sentences from qt
      tail, using the next sub-part's parent_stem as the structural
      anchor. Greedy multi-strip supported (for 2+ bridging sentences).
    Phase 2 (deferred — currently uncovered): symmetric strip of leading
      bridging from qt HEAD (the historical qwen-vl-max shift-by-one-
      prepend pattern, e.g. 1b.qt = "The point P... lies on circle.
      Show that ..."). If qwen3-vl-plus non-determinism ever produces
      the qt-head-pollution variant in production, Phase 1 leaves it
      unchanged — by design, not by accident. Phase 2 would add a
      symmetric "first-sentence vs previous-item.parent_stem or own ps"
      match rule. Decision 2026-04-19: defer to an independent PR
      after Phase 1 accumulates production log data. See
      test/fixtures/rescue_bridging/adv_3_shift_by_one_prepend.json.

    THREE GUARDRAILS (all three must HOLD, i.e. AND-gating — any one
    failing skips the strip and halts the greedy loop for this item)
    ------------------------------------------------------------------
      G1. CANDIDATE IS NOT AN INSTRUCTION.
          The last sentence (the strip candidate) must NOT start with a
          token in _INSTRUCTION_OPENERS. If it does, it IS the real
          instruction — stripping would destroy the sub-part.
          Covers adv_2_hence_is_instruction (last sentence opens with
          'Hence').

      G2. RESIDUAL STILL CONTAINS AN INSTRUCTION.
          After hypothetically removing the candidate, at least one
          remaining sentence must open with a token in
          _INSTRUCTION_OPENERS. Guarantees we never leave qt instruction-
          less, even when the candidate itself isn't verb-led (e.g.
          setup-form "Given that..., find k" where the verb is embedded).
          Covers adv_1_setup_opener_is_instruction (only one sentence,
          starts with 'Given') and case_1_last_subpart (single-sentence
          qts across the whole group).

      G3. CANDIDATE APPEARS IN NEXT_PS (structural anchor).
          The candidate's normalized form (via _rescue_normalize) must
          appear as a substring in the STRUCTURAL TARGET, selected by
          a STRICT (non-fallback) rule:

            STRICT PRIMARY: if next_item.parent_stem is non-empty →
              use it and only it. Do NOT fall back to group_stems even
              if the candidate doesn't match — G3 fails hard.
            FALLBACK (only when next.ps is empty): use
              group_stems[numeric_prefix]. This handles the cross-page
              continuation case (case_5): VL couldn't see the original
              stem on the continuation page and returned ps="".

          Rationale for strict-primary: if VL populated next.ps at all,
          that's the authoritative signal for what bridging belongs to
          that sub-part. Falling back when next.ps is non-empty-but-
          non-matching would let us rescue against a DIFFERENT target
          than the one VL cared about — that's a soft license to strip
          things we shouldn't. Being conservative (G3 fails, leave qt
          alone) is the safe choice; the user keeps reading a mildly
          polluted qt instead of losing a legitimate instruction.
          Covers case_3_next_ps_no_match + case_5_cross_page.

    All three must be TRUE to strip. The combination is tight enough
    that Step 2 post-hoc verification against the 7 enabled fixtures is
    definitive: if any fixture fails, one of the guardrails is wrong.

    GREEDY MULTI-STRIP
    ------------------
    When a strip succeeds, the new last sentence of qt is re-evaluated
    against the same three guards (next_ps target unchanged). Terminates
    on any guard failure or when only one sentence remains.

    STRUCTURED LOGGING (PRODUCTION-ENABLED, JSON-FORMATTED)
    -------------------------------------------------------
    Every decision — strip (with counts + matched source) and skip
    (with specific guard reason) — is logged at INFO level on the
    'pipeline.segmenter' logger. Production observability depends on
    these logs to monitor VL non-determinism frequency; they MUST stay
    enabled in prod. Format: ``rescue_decision <json>`` where the JSON
    payload is a single-line object safe to pipe into jq / ELK / Sentry
    / Grafana-Loki.

    Example strip event:
        rescue_decision {"qnum":"1a","action":"strip","n":1,
        "matched_in":"1b.parent_stem",
        "sentences":"The point P(1, 2) lies on the circle."}

    Example skip event:
        rescue_decision {"qnum":"1a","action":"skip","guard":"G1",
        "reason":"candidate_is_instruction",
        "candidate":"Hence find the minimum value of y."}

    Rationale for JSON over key=value: fields may carry embedded
    quotes, equals signs, whitespace (math formulas like "a = b") that
    break naive regex parsing. JSON quote-escapes them. Migration cost
    is trivial (json.dumps one-liner), migration later is more work.

    In-place modification of `results`. Returns nothing. Must be called
    AFTER group_stems is populated (Step 1) and BEFORE Step 2's
    per-item parent_stem overwrites, so rescue sees each item's
    VL-original parent_stem (not the group-max-overwrite target).
    """
    import json as _json
    log = logging.getLogger("pipeline.segmenter")

    def _emit(payload: dict) -> None:
        # Single-line JSON so log aggregators (jq / ELK / Loki) can
        # parse each rescue decision as one structured record.
        log.info("rescue_decision %s", _json.dumps(payload, ensure_ascii=False))

    # Build ordered groups by numeric prefix. "Next item" means next in
    # the SAME numeric-prefix group, not next in results[].
    groups_ordered: dict = {}
    for idx, item in enumerate(results):
        qnum = str(item.get("question_number") or "").strip()
        m = re.match(r"^\s*(\d+)", qnum)
        if not m:
            continue
        prefix = m.group(1)
        groups_ordered.setdefault(prefix, []).append(idx)

    for prefix, idxs in groups_ordered.items():
        if len(idxs) < 2:
            continue  # single-item group: nothing to rescue to

        # Iterate every sub-part except the LAST in its group — the last
        # has no next-item ps to anchor against (case_1_last_subpart).
        for pos in range(len(idxs) - 1):
            i_idx = idxs[pos]
            j_idx = idxs[pos + 1]
            item = results[i_idx]
            next_item = results[j_idx]
            qnum = str(item.get("question_number") or "")
            next_qnum = str(next_item.get("question_number") or "")

            qt_initial = str(item.get("question_text") or "").strip()
            if not qt_initial:
                continue

            # Pick the structural anchor for G3.
            next_ps_raw = str(next_item.get("parent_stem") or "").strip()
            if next_ps_raw:
                match_target = next_ps_raw
                match_source = f"{next_qnum}.parent_stem"
            else:
                match_target = group_stems.get(prefix, "")
                match_source = f"group_stems[{prefix!r}]"
            if not match_target:
                _emit({"qnum": qnum, "action": "skip", "guard": "G3",
                       "reason": "no_match_target"})
                continue
            target_norm = _rescue_normalize(match_target)

            # Greedy strip loop. `qt` mutates; `total_stripped` accumulates
            # the originally-last-to-originally-earlier sentences that were
            # stripped (reversed at the end for logging order).
            qt = qt_initial
            total_stripped: list = []
            while True:
                sentences = [
                    s for s in _RESCUE_SENTENCE_SPLIT.split(qt) if s.strip()
                ]
                if len(sentences) < 2:
                    # Either single-sentence qt (adv_1 / case_1 pattern)
                    # or we already stripped down to 1. Halt to preserve
                    # the instruction.
                    break
                candidate = sentences[-1].strip()

                # G1: candidate must not BE the instruction
                if _rescue_starts_with_instruction(candidate):
                    _emit({"qnum": qnum, "action": "skip", "guard": "G1",
                           "reason": "candidate_is_instruction",
                           "candidate": candidate[:200]})
                    break

                # G2: residual must contain at least one instruction opener
                residual = sentences[:-1]
                residual_has_instruction = any(
                    _rescue_starts_with_instruction(s) for s in residual
                )
                if not residual_has_instruction:
                    _emit({"qnum": qnum, "action": "skip", "guard": "G2",
                           "reason": "no_instruction_in_residual"})
                    break

                # G3: candidate must substring-match the target (next ps
                # or group stem), after structural normalization
                cand_norm = _rescue_normalize(candidate)
                if not cand_norm:
                    _emit({"qnum": qnum, "action": "skip", "guard": "G3",
                           "reason": "candidate_empty_after_normalize"})
                    break
                if cand_norm not in target_norm:
                    _emit({"qnum": qnum, "action": "skip", "guard": "G3",
                           "reason": "not_in_target", "target": match_source,
                           "candidate": candidate[:200]})
                    break

                # All three guards passed — strip the candidate
                total_stripped.append(candidate)
                qt = " ".join(residual).strip()

            if total_stripped:
                item["question_text"] = qt
                # Reverse so log reads in document order (earliest-stripped
                # sentence first — matches how a reader would see them).
                stripped_joined = " ".join(reversed(total_stripped))
                _emit({"qnum": qnum, "action": "strip",
                       "n": len(total_stripped),
                       "matched_in": match_source,
                       "sentences": stripped_joined[:500]})


def _attach_parent_stems(results: list[dict]) -> None:
    """
    给每条子题补上父题题干（parent_stem 字段），便于下游 grader 看到完整语境、
    FE 把主干和小题分开展示。

    优先级：
      1) 模型直接在 segmenter 输出里给了非空 parent_stem → 直接信任。
      2) 模型把 stem 混在 question_text 里（老行为）：按题号数字前缀建组，在每条
         question_text 中找到第一个 "(a)"/"(i)" 标记，把前缀当共享 stem；取组内最长
         的一条作为该组的 stem，并把 question_text 里对应前缀剥掉。
      3) 带数字前缀的子题（"6b"/"6(c)"）：若没有 parent_stem，填组共享 stem。
      4) 纯字母/罗马数字孤儿（"(a)"/"(i)"/"c"）：归到最近的数字组，同样填 parent_stem，
         并把题号升格为 "6(c)" 形式。

    就地修改 results —— 每条 item 最终有 parent_stem 字段（可能为空字符串）。
    question_text 被规范成「只含本小题指令」的版本，前面不再重复 stem。
    """
    log = logging.getLogger("pipeline.segmenter")

    # Step 0: 归一化 parent_stem 字段；把 None 归成 ""
    for item in results:
        ps = item.get("parent_stem")
        if ps is None:
            item["parent_stem"] = ""
        else:
            item["parent_stem"] = str(ps).strip()

    # Step 1: 按数字前缀建组，挑出最干净的 stem
    # 优先用模型自己给的 parent_stem；没给才回退到从 question_text 里切
    # 只有文本里存在 "(a)"/"(i)" 标记时才能安全地把前半段当 stem —— 否则会把 a 问自己的
    # "Show that P(X=2)=3/7" 这种 sub-part 具体指令错当成 stem 传染给其他小题。
    #
    # 多页选 stem 策略（关键）：同一题号下不同小题可能来自不同页面。比如 Q6a/6b 在 page 1、
    # Q6c 在 page 2。Page 2 的 VLM 调用看不到 page 1 的题干，它给 6c 产出的 parent_stem
    # 往往是「凭印象臆造」（e.g. 10 marbles 4R 6B 被瞎猜成 12 marbles 7R 5B），这会直接把
    # 整组的 stem 污染成错的。正确做法：取**最早出现该题号那一页**提供的 stem 为准。
    # 若同一页多个小题都提供了 stem，再按长度挑最完整的一份。
    group_stems: dict[str, str] = {}
    # 记录每个 group 当前 stem 来自哪一页，便于后续页比对
    group_stem_page: dict[str, int] = {}
    for item in results:
        qnum = str(item.get("question_number") or "").strip()
        num_match = re.match(r"^\s*(\d+)", qnum)
        if not num_match:
            continue
        number = num_match.group(1)
        try:
            page = int(item.get("page") or item.get("_page_norm") or 1)
        except (ValueError, TypeError):
            page = 1

        def _consider(candidate: str) -> None:
            if not candidate or len(candidate) < 20:
                return
            existing = group_stems.get(number)
            existing_page = group_stem_page.get(number)
            # 更早的页面优先；同页再按长度
            if existing is None:
                group_stems[number] = candidate
                group_stem_page[number] = page
                return
            if page < (existing_page or 10**9):
                group_stems[number] = candidate
                group_stem_page[number] = page
                return
            if page == existing_page and len(candidate) > len(existing):
                group_stems[number] = candidate

        # 模型直接给的 parent_stem 优先
        model_stem = str(item.get("parent_stem") or "").strip()
        if model_stem:
            _consider(model_stem)
            if len(model_stem) >= 20:
                continue

        qtext = str(item.get("question_text") or "").strip()
        if not qtext:
            continue
        marker = _SUBPART_MARKER_RE.search(qtext)
        if not marker:
            continue  # 没 marker 就没法切干净，宁缺勿带错
        stem_candidate = qtext[: marker.start()].strip()
        if len(stem_candidate) < 40:
            continue  # 切出来太短，大概率不是真 stem
        _consider(stem_candidate)

    # Step 1.5: rescue trailing bridging sentences out of question_text
    # BEFORE Step 2's group-max-overwrite modifies per-item parent_stem.
    # This decouples rescue from the group-max-overwrite issue (see Step
    # 2 coupling analysis) — rescue sees each item's VL-original
    # parent_stem, not the group's canonical stem overwrite target.
    _rescue_trailing_bridging_to_next_stem(results, group_stems)

    # Step 2: 回填 parent_stem；并把 question_text 里重复的 stem 前缀剥掉
    last_group: str | None = None
    for idx, item in enumerate(results):
        qnum = str(item.get("question_number") or "").strip()
        qtext = str(item.get("question_text") or "").strip()
        num_match = re.match(r"^\s*(\d+)", qnum)
        try:
            item_page = int(item.get("page") or item.get("_page_norm") or 1)
        except (ValueError, TypeError):
            item_page = 1

        if num_match:
            last_group = num_match.group(1)
            stem = group_stems.get(last_group)
            if stem:
                existing_ps = str(item.get("parent_stem") or "").strip()
                stem_src_page = group_stem_page.get(last_group, item_page)
                # 核心修复：如果本 item 的 parent_stem 来自「后续页」(继续页没见过原题干，
                # 模型凭猜测填的)，而 group_stems 里另有更早页的权威 stem —— 用权威的覆盖。
                # 即便权威 stem 更短也要覆盖，防止臆造版 (7 red 5 blue) 污染 Q6c。
                if stem_src_page < item_page and existing_ps and existing_ps != stem:
                    log.warning(
                        "overriding %r parent_stem from page %d (likely hallucinated) with group-%s stem from page %d",
                        qnum, item_page, last_group, stem_src_page,
                    )
                    item["parent_stem"] = stem
                elif len(stem) > len(existing_ps):
                    item["parent_stem"] = stem
                # 剥掉 question_text 里重复的 stem 前缀
                new_qtext = _strip_stem_prefix(qtext, stem)
                if new_qtext != qtext:
                    item["question_text"] = new_qtext
                    log.info(
                        "stripped duplicated stem prefix from %r question_text (%d → %d chars)",
                        qnum, len(qtext), len(new_qtext),
                    )
            continue

        # 孤儿子题：优先 last_group；没有则回溯/向前扫描最近一个带 stem 的数字组
        if not _is_orphan_qnum(qnum):
            continue

        # 页感知的跨页查找：先在「本页、上一页、上上页…」里往回扫，找最近的数字题号做父题。
        # results 按页顺序合并，所以 idx-1 向 0 方向就是「更早的页面」。
        target_group: str | None = None
        target_page: int | None = None
        if last_group and last_group in group_stems:
            target_group = last_group
            target_page = group_stem_page.get(last_group)
        if target_group is None:
            for j in range(idx - 1, -1, -1):
                prev = results[j]
                prev_qnum = str(prev.get("question_number") or "").strip()
                prev_match = re.match(r"^\s*(\d+)", prev_qnum)
                if prev_match and prev_match.group(1) in group_stems:
                    target_group = prev_match.group(1)
                    try:
                        target_page = int(prev.get("page") or prev.get("_page_norm") or 1)
                    except (ValueError, TypeError):
                        target_page = None
                    break
        if target_group is None:
            for j in range(idx + 1, len(results)):
                nxt = results[j]
                nxt_qnum = str(nxt.get("question_number") or "").strip()
                nxt_match = re.match(r"^\s*(\d+)", nxt_qnum)
                if nxt_match and nxt_match.group(1) in group_stems:
                    target_group = nxt_match.group(1)
                    try:
                        target_page = int(nxt.get("page") or nxt.get("_page_norm") or 1)
                    except (ValueError, TypeError):
                        target_page = None
                    break

        if target_group is None:
            continue

        stem = group_stems.get(target_group)
        if stem:
            existing_ps = str(item.get("parent_stem") or "").strip()
            stem_src_page = group_stem_page.get(target_group, target_page or item_page)
            # 孤儿同理：如果当前 ps 是后续页臆造的，用更早页的权威版本覆盖
            if stem_src_page < item_page and existing_ps and existing_ps != stem:
                log.warning(
                    "overriding orphan %r parent_stem from page %d with group-%s stem from page %d",
                    qnum, item_page, target_group, stem_src_page,
                )
                item["parent_stem"] = stem
            elif len(stem) > len(existing_ps):
                item["parent_stem"] = stem
            new_qtext = _strip_stem_prefix(qtext, stem)
            if new_qtext != qtext:
                item["question_text"] = new_qtext
            log.info(
                "attached parent_stem to orphan %r (page %d) from group %s on page %s (stem %d chars)",
                qnum, item_page, target_group,
                str(stem_src_page) if stem_src_page is not None else "?",
                len(stem),
            )

        # 强制把题号提升成 "6(c)" 形式，让 FE 和 grader 都看得出它属于 Q6
        label = _extract_orphan_label(qnum)
        if label:
            new_qnum = f"{target_group}({label})"
            if new_qnum != qnum:
                item["question_number"] = new_qnum
                # Mark this as a promoted orphan so _merge_cross_page_answers
                # can trust it's a continuation answer (not a real sub-question
                # on its own page). 100% precision signal by construction.
                item["_was_orphan"] = True
                log.info("promoted orphan qnum %r → %r", qnum, new_qnum)

    # Fold labelled cross-page answer blocks (page N+1 has (a)/(C)/(d) hand-
    # written answers belonging to Q-something on page N) back into their
    # target sub-questions, so page-N's empty "1(a)" doesn't stay "未作答"
    # while page-N+1 surfaces phantom "图片 2-a" cards that the grader
    # mis-grades without a printed stem. Runs BEFORE _merge_orphan_answers
    # so inline-label splitting gets a chance on single-item continuation
    # pages; any label-less residue falls through to the blind-fold below.
    _merge_cross_page_answers(results)

    # After stems are attached, clean up answer-continuation orphans: pages
    # that only contain student handwriting (no printed question text, no
    # parent_stem) but have student_answer / working_steps — those are almost
    # certainly the overflow of the previous question's answer onto a new page.
    # Merging them prevents empty "识别 0% 批改 0%" cards from showing up.
    _merge_orphan_answers(results)

    # Final cleanup: drop truly-empty fallback items that came from blank
    # pages (uploaded pages where the VL model returned nothing, triggering
    # _empty_fallback's `{"question_number": "1", ..., confidence: 0.0}`
    # placeholder). These would otherwise surface as phantom "图片 N-1 识别
    # 0%" cards. An item is "truly empty" when all of: no question_text, no
    # parent_stem, no student_answer, no working_steps. Items that are
    # unanswered but printed (empty student_answer but real question_text)
    # are preserved — pipeline.py routes them to the unanswered branch.
    _drop_empty_fallback_items(results)


def _drop_empty_fallback_items(results: list[dict]) -> None:
    """In-place removal of items with no gradable content.

    ``parent_stem`` is deliberately NOT checked — ``_attach_parent_stems``
    propagates the group's stem to every item sharing the numeric prefix,
    including blank-page fallbacks (``{"question_number": "1", ...}``)
    whose qnum lands in group "1" and picks up Q1's stem. An inherited
    stem doesn't make the item gradable: with empty question_text,
    student_answer AND working_steps, there's nothing for the frontend
    to display or the grader to score — surfacing it as "图片 N-1" is
    the exact phantom-card regression we're fixing.
    """
    log = logging.getLogger("pipeline.segmenter")
    to_remove: list[int] = []
    for i, item in enumerate(results):
        if str(item.get("question_text") or "").strip():
            continue
        if str(item.get("student_answer") or "").strip():
            continue
        if any(str(s or "").strip() for s in (item.get("working_steps") or [])):
            continue
        to_remove.append(i)
    # If dropping would leave the list empty, keep everything. A single
    # page whose segmentation totally failed returns a single empty
    # fallback item — the frontend still needs it as a placeholder so the
    # user sees "couldn't recognize this page" instead of a blank UI.
    # Only drop when there are real items alongside the empties (the
    # multi-page case, where phantom blank cards between real questions
    # are the actual regression).
    if to_remove and len(to_remove) < len(results):
        for i in reversed(to_remove):
            results.pop(i)
        log.info("dropped %d blank-page fallback item(s)", len(to_remove))


_CROSS_PAGE_LABEL_TAIL_RE = re.compile(
    r"(?:^|[^A-Za-z])([a-eA-E]|[ivxIVX]{1,4})\s*\)?\s*$"
)
_CROSS_PAGE_INLINE_LABEL_RE = re.compile(
    r"[\(（]\s*([a-eA-E]|[ivxIVX]{1,4})\s*[\)）]"
)


def _fallback_last_item_on_nearest_strong_page(
    i_page: int,
    results: list[dict],
    will_be_popped: set[int],
    src_idx: int,
) -> int | None:
    """For a weak-page item whose label finds no matching sub-part on any
    earlier page, return the index of the LAST item on the nearest earlier
    page that carries a strong-printed item (marks ≥ 2). Returns None if
    no such page exists.

    Why the LAST item: when a student's answer spills past the printed
    sub-parts, the overflow most commonly belongs to the final sub-part
    they were working on. Appending to the last item is a safer fallback
    than guessing a specific sub-part by label (the label was hallucinated
    anyway, since no earlier page carried it)."""
    def _page_of_local(item: dict) -> int:
        try:
            return int(item.get("page") or item.get("_page_norm") or 1)
        except (ValueError, TypeError):
            return 1

    def _is_strong_printed_local(item: dict) -> bool:
        try:
            return int(item.get("marks", 0) or 0) >= 2
        except (ValueError, TypeError):
            return False

    # Find nearest earlier page that has at least one strong-printed item.
    nearest_strong_page: int | None = None
    for idx, it in enumerate(results):
        p = _page_of_local(it)
        if p >= i_page:
            continue
        if not _is_strong_printed_local(it):
            continue
        if nearest_strong_page is None or p > nearest_strong_page:
            nearest_strong_page = p
    if nearest_strong_page is None:
        return None

    # Return the last (by results index) item on that page that's not
    # already scheduled for removal and isn't the source itself.
    last_idx: int | None = None
    for idx, it in enumerate(results):
        if idx == src_idx or idx in will_be_popped:
            continue
        if _page_of_local(it) == nearest_strong_page:
            last_idx = idx
    return last_idx


def _merge_cross_page_answers(results: list[dict]) -> None:
    """Fold cross-page labelled sub-part answers into the matching
    sub-question entry on an earlier page, then drop the now-redundant
    continuation card.

    Scenario this fixes (the earlier page-level classifier was too fragile):
    student writes (a)/(c)/(d) answers on a pure-handwriting page; segmenter
    may emit them as promoted orphans OR may hallucinate a fresh question
    with numeric-prefixed qnums (like "2a"/"2c"/"2d") by transcribing the
    student's first handwritten line as the "question". Either way the page
    is really a continuation of Q1 on an earlier page.

    Detection uses per-item signals grounded in structural evidence —
    never page-level question_text / marks heuristics (those are exactly
    what the segmenter hallucinates). Signals, evaluated in priority order:

      1. Explicit duplicate qnum — ``_normalize_qnum(I) == _normalize_qnum(J)``
         for some J on an earlier page. Segmenter emitted two copies of the
         same sub-part; later one is the continuation answer.
      2. ``_was_orphan`` flag — set by ``_attach_parent_stems`` at the
         moment it promotes a bare label qnum like ``(a)`` to ``1(a)``.
         By construction this item is a continuation.
      3. ``_continuation_page`` flag — set by ``_segment_with_grouping`` in
         ``pipeline.py`` from OCR page-header evidence: a page whose header
         does NOT start with a numbered question belongs to the previous
         group (i.e. pure continuation). When I is on such a page AND the
         nearest earlier J with the same trailing label is currently
         unanswered, fold I into J.

    Guardrail — never fold across a "strong intervening printed Q":
    an item K between J.page and I.page with a numeric-prefix qnum whose
    number differs from J's, with question_text ≥ 40 chars AND marks > 0
    (i.e. a real new question between them). Folding across such a K would
    misattribute content.

    Scenario B — if an item's own student_answer / working_steps contains
    ≥ 2 inline labels like "(a)...(c)...", split it into virtual blocks
    BEFORE matching so each chunk goes to its own target.

    Source items whose blocks ALL found targets are removed. Items with
    unmatched blocks are left alone (conservative — avoid content loss).

    Fields are never overwritten — merges append. No ``is_answered``
    field is set; once the target has real content, the unanswered
    heuristic in ``pipeline.py:_unanswered`` naturally returns False and
    normal grading proceeds.

    In-place modification of ``results``.
    """
    if len(results) < 2:
        return
    log = logging.getLogger("pipeline.segmenter")

    def _page_of(item: dict) -> int:
        try:
            return int(item.get("page") or item.get("_page_norm") or 1)
        except (ValueError, TypeError):
            return 1

    def _has_content(item: dict) -> bool:
        if str(item.get("student_answer") or "").strip():
            return True
        steps = item.get("working_steps") or []
        return any(str(s or "").strip() for s in steps)

    def _trailing_label(qnum: str) -> str | None:
        if not qnum:
            return None
        m = _CROSS_PAGE_LABEL_TAIL_RE.search(qnum.strip())
        return m.group(1).lower() if m else None

    def _numeric_prefix(qnum: str) -> str | None:
        if not qnum:
            return None
        m = re.match(r"^\s*(\d+)", qnum)
        return m.group(1) if m else None

    # ---- Step 1: pre-split Scenario B items into virtual blocks ---------
    # blocks: (source_idx, label, ans, steps, was_split)
    # source_idx always points back to the same results[i] so we can drop
    # it atomically once all its produced blocks find targets.
    blocks: list[tuple[int, str, str, list[str], bool]] = []
    source_block_count: dict[int, int] = {}

    for i, item in enumerate(results):
        qnum = str(item.get("question_number") or "").strip()
        ans = str(item.get("student_answer") or "").strip()
        steps = [str(s) for s in (item.get("working_steps") or []) if str(s or "").strip()]

        corpus = ans + ("\n" + "\n".join(steps) if steps else "")
        inline = list(_CROSS_PAGE_INLINE_LABEL_RE.finditer(corpus))
        trailing = _trailing_label(qnum)

        if len(inline) >= 2 and not trailing:
            # One item holds several inline-labelled answer regions and has
            # no trailing qnum label of its own — split by inline labels.
            for bidx, m in enumerate(inline):
                next_start = inline[bidx + 1].start() if bidx + 1 < len(inline) else len(corpus)
                chunk = corpus[m.end():next_start].strip()
                if chunk:
                    blocks.append((i, m.group(1).lower(), chunk, [], True))
                    source_block_count[i] = source_block_count.get(i, 0) + 1
            continue

        if trailing and (ans or steps):
            blocks.append((i, trailing, ans, steps, False))
            source_block_count[i] = source_block_count.get(i, 0) + 1
            continue

        # No label / no content — not a candidate. Existing orphan logic
        # downstream handles truly-unlabelled continuation items.

    if not blocks:
        return

    # ---- Step 2: per-block target matching ------------------------------
    # For each block, scan earlier-page items with matching trailing label;
    # apply the three priority signals + guardrail.
    source_matched_count: dict[int, int] = {}

    def _is_strong_printed(item: dict) -> bool:
        """Strong evidence an item is a real printed question: marks ≥ 2.

        A-Level papers rarely allocate just 1 mark to a sub-part (usual
        range is 2-5). When the segmenter hallucinates a question on a
        handwriting-only page, it typically invents marks=1 or marks=0
        (or nothing). Real sub-parts — even with short instruction text
        like "(a) State coordinates of C." — carry their real [3] / [4]
        mark allocation. Using marks as the signal avoids false negatives
        on terse real prompts and false positives on padded hallucinations.
        """
        try:
            return int(item.get("marks", 0) or 0) >= 2
        except (ValueError, TypeError):
            return False

    def _strong_intervening_Q(j_page: int, i_page: int, j_prefix: str | None) -> bool:
        """Is there any item K strictly between j_page and i_page that
        represents a *different* real printed question?

        Uses marks>=2 (see ``_is_strong_printed``) as the primary signal.
        Numeric-prefix qnum is no longer required — some segmenter outputs
        emit bare sub-part labels like ``'a'`` even for real printed
        questions (no numeric prefix ever surfaces), and gating on
        ``_NUMBERED_QNUM_RE`` makes the whole guardrail silent on such
        outputs, allowing catastrophic over-folding (Q2/Q3/Q4's sub-parts
        all collapsed into Q1).
        """
        for k_item in results:
            kp = _page_of(k_item)
            if kp <= j_page or kp >= i_page:
                continue
            if not _is_strong_printed(k_item):
                continue
            # If both have explicit numeric prefix AND they match, not a
            # boundary (same question spanning pages).
            k_prefix = _numeric_prefix(str(k_item.get("question_number") or "").strip())
            if k_prefix and j_prefix and k_prefix == j_prefix:
                continue
            return True
        return False

    def _page_has_strong_printed(page: int) -> bool:
        """Does any item on ``page`` carry strong printed-question evidence?
        Used as a second gate on Priority-3 (cont-page) fold, because the
        OCR page-header probe has false negatives — a page with a real
        small-font printed question number may still fail the header check
        and be tagged ``_continuation_page=True``."""
        return any(
            _page_of(it) == page and _is_strong_printed(it) for it in results
        )

    # Track source indices that are DEFINITELY being popped (all their
    # blocks matched). Only these should be excluded from candidate target
    # selection — excluding every source index would wrongly bar items like
    # "1a" (answered on page 1, collected as a source but never matches
    # anything because it's on the leader page) from ever being a target.
    # We update this set incrementally as blocks are processed in
    # page-ascending order, so earlier-processed matches inform later ones.
    will_be_popped: set[int] = set()

    # Process blocks in page-ascending order: leader-page items (which are
    # legitimate targets) are matched first (and skip), so later continuation
    # items can target them without being blocked.
    blocks.sort(key=lambda b: _page_of(results[b[0]]))

    for src_idx, label, ans, steps, was_split in blocks:
        I = results[src_idx]
        i_page = _page_of(I)
        i_norm = _normalize_qnum(I.get("question_number", ""))
        i_was_orphan = bool(I.get("_was_orphan"))
        i_is_cont_page = bool(I.get("_continuation_page"))

        # Top-level short-circuit: if I's own page has ANY strong-printed
        # item (marks>=2), I itself is a real printed sub-part on a
        # question page, not a continuation answer — don't fold it.
        #
        # This is what prevents catastrophic over-folding when the segmenter
        # emits bare labels like 'a'/'b'/'c' for every sub-part across
        # distinct questions (Q1(a) on p1, Q2(a) on p3, Q3(a) on p5 all
        # look the same after normalization). The earlier-page-match loop
        # below can't distinguish legitimate Q2(a) from "continuation of
        # Q1(a)"; the source page's strong-printed status is the true
        # discriminator.
        if _page_has_strong_printed(i_page):
            continue

        # Build candidates: earlier-page items whose trailing label matches.
        candidates: list[tuple[int, int]] = []  # (page, results_idx)
        for j_idx, J in enumerate(results):
            if j_idx == src_idx:
                continue
            if j_idx in will_be_popped:
                # Previously-processed source already scheduled for removal;
                # merging into it would lose the merged content with the pop.
                continue
            jp = _page_of(J)
            if jp >= i_page:
                continue
            j_qnum = str(J.get("question_number") or "").strip()
            if _trailing_label(j_qnum) != label:
                continue
            candidates.append((jp, j_idx))

        # No label match → try weak-page fallback before giving up.
        # I's page is known to be weak (strong-page check short-circuits
        # above). Fallback: append I's content to the LAST item on the
        # nearest earlier strong-printed page. This catches VL-hallucinated
        # labels like page-2 '(e)' (a non-existent sub-part the VL invented
        # from the student's spillover working) that would otherwise surface
        # as phantom "图片 N-x" cards. The hallucinated block's real owner
        # is the last sub-part on the previous printed page, so merging
        # there preserves the student's work.
        if not candidates:
            fallback_idx = _fallback_last_item_on_nearest_strong_page(
                i_page, results, will_be_popped, src_idx,
            )
            if fallback_idx is not None:
                target = results[fallback_idx]
                if ans:
                    existing = str(target.get("student_answer") or "").strip()
                    target["student_answer"] = (existing + "\n\n" + ans).strip() if existing else ans
                if steps:
                    target["working_steps"] = list(target.get("working_steps") or []) + steps
                source_matched_count[src_idx] = source_block_count[src_idx]
                will_be_popped.add(src_idx)
                log.info(
                    "cross-page merge [weak→strong fallback]: page %d unmatched label %r → %r (page %s) (+%d ans chars, +%d steps)",
                    i_page, label,
                    target.get("question_number"),
                    target.get("page"),
                    len(ans), len(steps),
                )
            continue

        # Sort nearest-earlier first.
        candidates.sort(key=lambda t: -t[0])

        chosen_idx: int | None = None
        reason = ""
        for jp, j_idx in candidates:
            J = results[j_idx]
            j_qnum = str(J.get("question_number") or "").strip()
            j_prefix = _numeric_prefix(j_qnum)

            # Guardrail: skip if there's a strong intervening printed Q
            # with a different numeric prefix between J and I.
            if _strong_intervening_Q(jp, i_page, j_prefix):
                continue

            # Priority 1: explicit duplicate after qnum normalization.
            # Requires numeric prefix — bare labels like 'a' / '(c)' look
            # identical across distinct questions (Q2(a) and Q1(a) both
            # normalize to 'a'), and matching on that alone causes Q2/Q3/Q4's
            # sub-parts to all collapse into Q1. Numeric prefix is what makes
            # 'dup-qnum' truly "explicit duplicate of the SAME question".
            if (
                i_norm
                and _normalize_qnum(j_qnum) == i_norm
                and _numeric_prefix(str(I.get("question_number") or "").strip())
                and _numeric_prefix(j_qnum)
            ):
                chosen_idx = j_idx
                reason = "dup-qnum"
                break
            # Priority 2: I was a promoted orphan — trust it.
            if i_was_orphan:
                chosen_idx = j_idx
                reason = "was-orphan"
                break
            # Priority 4: weak-source → strong-target. I's page has no
            # strong-printed item (we already short-circuit above, so this
            # is guaranteed True at this point), and J is the nearest
            # earlier item whose page DOES have a strong-printed item —
            # i.e. J is on the most recent real question page. This is
            # the /prepare-upload fallback for when _continuation_page
            # isn't populated (because per-image extraction has no cross-
            # page grouping) and bare labels prevent _was_orphan promotion.
            #
            # Evaluated before Priority 3 because it's strictly more
            # reliable than the OCR-header hint (which has false negatives).
            if _page_has_strong_printed(jp):
                chosen_idx = j_idx
                reason = "weak→strong"
                break
            # Priority 3: I's page is an OCR-confirmed continuation page
            # AND no item on that page carries strong printed-question
            # evidence (long question_text + non-zero marks). The second
            # gate is critical — OCR header probe has false negatives
            # (e.g. small-font "3." not detected), so we MUST verify there
            # isn't a real printed Q on I's page before folding its
            # sub-parts into earlier questions. Otherwise self-contained
            # Q2/Q3/Q4 pages get misfolded into Q1.
            if i_is_cont_page and not _page_has_strong_printed(i_page):
                chosen_idx = j_idx
                reason = "cont-page"
                break

        if chosen_idx is None:
            continue

        target = results[chosen_idx]
        if ans:
            existing = str(target.get("student_answer") or "").strip()
            target["student_answer"] = (existing + "\n\n" + ans).strip() if existing else ans
        if steps:
            existing_steps = list(target.get("working_steps") or [])
            target["working_steps"] = existing_steps + steps

        source_matched_count[src_idx] = source_matched_count.get(src_idx, 0) + 1
        # If all blocks from this source have now matched, flag it for pop
        # so subsequent blocks won't target it.
        if source_matched_count[src_idx] == source_block_count[src_idx]:
            will_be_popped.add(src_idx)
        log.info(
            "cross-page merge [%s]: page %d label %r → %r (page %s) %s(+%d ans chars, +%d steps)",
            reason, i_page, label,
            target.get("question_number"),
            target.get("page"),
            "[split] " if was_split else "",
            len(ans), len(steps),
        )

    # ---- Step 3: drop source items fully consumed -----------------------
    to_remove: set[int] = set()
    for src_idx, produced in source_block_count.items():
        if source_matched_count.get(src_idx, 0) == produced:
            to_remove.add(src_idx)

    if to_remove:
        for i in sorted(to_remove, reverse=True):
            results.pop(i)
        log.info(
            "cross-page merge: dropped %d continuation item(s) after folding",
            len(to_remove),
        )


def _merge_orphan_answers(results: list[dict]) -> None:
    """Fold answer-only pages (no question text, no stem, but with handwriting)
    into the preceding question's student_answer / working_steps, then drop
    them from the results list.

    This handles the case where the student's written answer to question Q on
    page N overflows onto page N+1 without any question number being present —
    the segmenter would otherwise emit a phantom "N+1-1" card with 0% recognition.

    In-place modification of ``results``.
    """
    if len(results) < 2:
        return
    log = logging.getLogger("pipeline.segmenter")

    def _has_answer_content(item: dict) -> bool:
        if str(item.get("student_answer") or "").strip():
            return True
        steps = item.get("working_steps") or []
        return any(str(s or "").strip() for s in steps)

    def _is_answer_orphan(item: dict) -> bool:
        qtext = str(item.get("question_text") or "").strip()
        pstem = str(item.get("parent_stem") or "").strip()
        # Only consider it an orphan if there is literally no question content
        # AND the segmenter did pick up some student writing.
        return not qtext and not pstem and _has_answer_content(item)

    to_remove: list[int] = []
    for i, item in enumerate(results):
        if i == 0:
            continue
        if not _is_answer_orphan(item):
            continue
        item_page = int(item.get("page") or 1)
        # Walk backwards for the nearest item on an earlier-or-same page that
        # has real question content to attach this handwriting onto.
        target_idx: int | None = None
        for j in range(i - 1, -1, -1):
            if j in to_remove:
                continue
            prev = results[j]
            prev_page = int(prev.get("page") or 1)
            if prev_page > item_page:
                continue
            prev_qtext = str(prev.get("question_text") or "").strip()
            prev_pstem = str(prev.get("parent_stem") or "").strip()
            if prev_qtext or prev_pstem:
                target_idx = j
                break
        if target_idx is None:
            continue

        target = results[target_idx]
        orphan_ans = str(item.get("student_answer") or "").strip()
        if orphan_ans:
            existing_ans = str(target.get("student_answer") or "").strip()
            target["student_answer"] = (existing_ans + "\n\n" + orphan_ans).strip() if existing_ans else orphan_ans
        orphan_steps = [s for s in (item.get("working_steps") or []) if str(s or "").strip()]
        if orphan_steps:
            existing_steps = list(target.get("working_steps") or [])
            target["working_steps"] = existing_steps + orphan_steps
        to_remove.append(i)
        log.info(
            "merged orphan answer on page %d into question %r (page %d): +%d steps, +%d ans chars",
            item_page, target.get("question_number"),
            int(target.get("page") or 1),
            len(orphan_steps), len(orphan_ans),
        )

    if to_remove:
        for i in sorted(to_remove, reverse=True):
            results.pop(i)


def _strip_stem_prefix(qtext: str, stem: str) -> str:
    """若 question_text 以 stem 开头（可能带一点换行/标签差异），剥掉这段前缀。"""
    if not qtext or not stem:
        return qtext
    # 精确前缀
    if qtext.startswith(stem):
        rest = qtext[len(stem):]
        return rest.lstrip(" \n\r\t")
    # 宽松前缀：忽略空白差异比较前 N 个非空白字符
    def _squash(s: str) -> str:
        return re.sub(r"\s+", "", s)
    sq_stem = _squash(stem)
    sq_text = _squash(qtext)
    if sq_stem and sq_text.startswith(sq_stem):
        # 找出原 qtext 中到第 len(sq_stem) 个非空白字符为止的切点
        count = 0
        for i, ch in enumerate(qtext):
            if not ch.isspace():
                count += 1
                if count == len(sq_stem):
                    return qtext[i + 1:].lstrip(" \n\r\t")
    return qtext


def _empty_fallback(width: int, height: int) -> list[dict]:
    return [{
        "question_number": "1",
        "bbox": [0, 0, width, height],
        "question_text": "",
        "student_answer": "",
        "working_steps": [],
        "image_quality": "poor",
        "confidence": 0.0,
        "page": 1,
    }]


def _dump_vl_snapshot(items: list, stage: str) -> None:
    """
    Env-gated diagnostic dump: write per-page JSON snapshots of the segmenter's
    intermediate state to SEGMENTER_DUMP_DIR. Used to investigate how VL
    handles CAIE multi-sub-part structure (bridging sentence attribution,
    parent_stem vs question_text split, orphan items, etc.).

    Activation:
      * SEGMENTER_DUMP_DIR (required, abs path): when unset this function is
        a zero-cost no-op and the segmenter's production path is untouched.
      * SEGMENTER_DUMP_PREFIX (optional): filename prefix, typically the
        source PDF stem (e.g. "Lesson2-Coordinate_geometry_11"). Defaults
        to "unknown_prefix" if not provided.

    ``stage`` identifies the snapshot point:
      * "raw" — VL's parsed JSON array AS-IS, before any dict-filter,
        _merge_cross_page_items, _attach_parent_stems, or OCR rewrite.
      * "postprocessed" — final results list after all merges, stem
        attachment, inconsistency flagging. Right before the function
        returns.

    Items are grouped by their ``page`` field and each group is written to
    ``{prefix}_page{N}_{stage}.json``. Items missing/with invalid ``page``
    fall into ``{prefix}_page_unknown_{stage}.json`` so orphan bridging-
    sentence items can be spotted. Each entry is augmented with
    ``_vl_order`` (position in the input list) so original ordering is
    recoverable after per-page splitting.

    Non-dict entries (rare VL garbage) are surfaced too, not silently
    dropped — they're part of what "raw" means.
    """
    dump_dir = os.environ.get("SEGMENTER_DUMP_DIR", "").strip()
    if not dump_dir:
        return
    import json
    from pathlib import Path
    prefix = os.environ.get("SEGMENTER_DUMP_PREFIX", "").strip() or "unknown_prefix"
    out_dir = Path(dump_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logging.getLogger("pipeline.segmenter").warning(
            "dump dir create failed (%s): %s", dump_dir, e,
        )
        return

    buckets: dict[str, list[dict]] = {}
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            entry = {"_vl_order": idx, "_non_dict": True, "_raw_repr": repr(it)[:500]}
            buckets.setdefault("unknown", []).append(entry)
            continue
        page_raw = it.get("page")
        try:
            page_key = str(int(page_raw)) if page_raw is not None else "unknown"
        except (ValueError, TypeError):
            page_key = "unknown"
        entry = dict(it)
        entry["_vl_order"] = idx
        buckets.setdefault(page_key, []).append(entry)

    for page_key, bucket in buckets.items():
        fname = f"{prefix}_page{page_key}_{stage}.json"
        path = out_dir / fname
        try:
            path.write_text(
                json.dumps(bucket, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logging.getLogger("pipeline.segmenter").info(
                "dumped %d item(s) (%s) to %s", len(bucket), stage, path,
            )
        except Exception as e:
            logging.getLogger("pipeline.segmenter").warning(
                "dump write failed (%s): %s", path, e,
            )


def segment_and_extract(
    images: Image.Image | list[Image.Image],
    client: ModelClient,
    user_hint: str = "",
    ocr_client: ModelClient | None = None,
) -> list[dict]:
    """
    一次 LLM 调用完成切题 + 内容提取（支持多页）。

    - images: 单张 PIL Image 或按阅读顺序的 list[PIL Image]。多页时 VL 模型一次看到所有图，
      能正确合并跨页题目。
    - 如果提供 ocr_client，会为每张图并行调用 OCR 做交叉校验（总耗时 ≈ max(VL, 单张 OCR)，
      因为所有调用都在同一线程池里并发）。

    返回 list[dict]，每个 dict 包含：
    question_number, bbox, question_text, student_answer, working_steps, image_quality, confidence, page
    """
    assert client.supports_images(), "requires a client that supports images"

    # 归一化为 list
    if isinstance(images, Image.Image):
        images = [images]
    if not images:
        return _empty_fallback(1, 1)

    b64_list = [image_to_base64(img) for img in images]
    widths = [img.size[0] for img in images]
    heights = [img.size[1] for img in images]
    n_pages = len(images)

    # 方案 2：多页时按 batch 拼图喂给 VL，消除模型视角下的「跨页」歧义。
    # 单图过高会撑爆 8192 token 的 JSON 输出，所以 ≤3 页/批、高度 ≤3500px；超过则该批退化为单页。
    stitch_enabled = os.environ.get("SEGMENT_STITCH_PAGES", "1").strip() not in ("0", "false", "False", "")
    vl_images_b64 = b64_list
    stitched = False
    if stitch_enabled and n_pages > 1:
        batched = _batch_stitch_pages(images)
        if len(batched) < n_pages:
            vl_images_b64 = [image_to_base64(im) for im in batched]
            stitched = True
            logging.getLogger("pipeline.segmenter").info(
                "batch-stitched %d pages into %d image(s) for VL (sizes: %s)",
                n_pages, len(batched),
                [f"{im.size[0]}x{im.size[1]}" for im in batched],
            )

    # 并行启动 OCR（每张原图一个 future），与主 VL 调用同时跑。
    # 注意 OCR 仍然走原始分页，保持每页独立，不受拼图影响。
    ocr_futures: list = []
    ocr_pool: ThreadPoolExecutor | None = None
    if ocr_client is not None and ocr_client is not client:
        ocr_pool = ThreadPoolExecutor(max_workers=max(1, n_pages))
        ocr_futures = [ocr_pool.submit(_call_ocr, b64, ocr_client) for b64 in b64_list]

    if user_hint.strip():
        uh = user_hint.strip()
        user_context = (
            "\n\nIMPORTANT — The user provided the following hint about this page:\n"
            f'"""\n{uh}\n"""\n'
            "Use this information to guide your segmentation. Trust the user's description of question count and positions.\n"
        )
    else:
        user_context = ""

    if stitched:
        multi_page_note = (
            f"This single image is a vertical stitch of {n_pages} consecutive homework pages. "
            f'Each page begins with a gray bar labeled "— Page N —" (N = 1..{n_pages}). '
            f"Treat everything between two consecutive bars as the content of that page; "
            f"report the correct \"page\" field (1..{n_pages}) for each question you emit. "
            f"Since all pages are now in one image, cross-page continuation is automatic — "
            f"simply merge a question's printed stem with its handwritten work even if they "
            f"lie in different page sections of this stitched image. "
        )
    else:
        multi_page_note = (
            f"The following {n_pages} images are consecutive pages (page 1 to page {n_pages}) "
            f"of the same homework; read them in order. "
            if n_pages > 1 else ""
        )
    prompt = _SEGMENT_EXTRACT_PROMPT.format(
        multi_page_note=multi_page_note,
        user_context=user_context,
    )

    request = ModelRequest(
        task=TaskType.segment,
        prompt=prompt,
        images=vl_images_b64,
        max_tokens=8192,
    )

    last_err: Exception = RuntimeError("no attempts made")
    items: list[dict] | None = None
    for attempt in range(3):
        try:
            raw = client.call(request)
            parsed = parse_json_array(raw)
            if not parsed:
                raise ValueError("Model returned empty question list")
            items = parsed
            break
        except Exception as e:
            last_err = e
            logging.getLogger("pipeline.segmenter").warning(
                "segment_and_extract attempt %d/3 failed: %s", attempt + 1, e,
            )
            request = ModelRequest(
                task=TaskType.segment,
                images=vl_images_b64,
                max_tokens=4096,
                prompt=(
                    "OUTPUT ONLY A RAW JSON ARRAY. NO EXPLANATION. NO MARKDOWN.\n\n"
                    + _SEGMENT_EXTRACT_PROMPT.format(
                        multi_page_note=multi_page_note,
                        user_context=user_context,
                    )
                ),
            )

    # 收取并行 OCR 结果（按页拼接）
    ocr_text = ""
    if ocr_futures:
        parts: list[str] = []
        for i, fut in enumerate(ocr_futures):
            try:
                t = fut.result(timeout=30) or ""
            except Exception as e:
                logging.getLogger("pipeline.segmenter").warning("OCR page %d failed: %s", i + 1, e)
                t = ""
            if t:
                parts.append(f"--- Page {i + 1} ---\n{t}")
        ocr_text = "\n\n".join(parts)
        if ocr_pool is not None:
            ocr_pool.shutdown(wait=False)

    if items is None:
        logging.getLogger("pipeline.segmenter").warning(
            "segment_and_extract failed after 3 attempts: %s — returning empty",
            last_err,
        )
        return _empty_fallback(widths[0], heights[0])

    # Env-gated raw VL snapshot: BEFORE dict-filter, BEFORE any merging /
    # stem-attachment. No-op in production (SEGMENTER_DUMP_DIR unset).
    _dump_vl_snapshot(items, "raw")

    items = [it for it in items if isinstance(it, dict)]
    if not items:
        return _empty_fallback(widths[0], heights[0])

    # 方案 1：按题号归一化合并跨页条目（零 LLM 调用，纯 CPU）
    items = _merge_cross_page_items(items)
    if not items:
        return _empty_fallback(widths[0], heights[0])

    # 按页分组生成近似 bbox（每页内部按该页上的题数等分）
    page_to_items: dict[int, list[int]] = {}
    for idx, item in enumerate(items):
        try:
            page = int(item.get("page", 1) or 1)
        except (ValueError, TypeError):
            page = 1
        page = max(1, min(page, n_pages))
        item["_page_norm"] = page
        page_to_items.setdefault(page, []).append(idx)

    bbox_map: dict[int, list[int]] = {}
    for page, idx_list in page_to_items.items():
        page_w = widths[page - 1]
        page_h = heights[page - 1]
        pbboxes = _generate_approximate_bboxes(len(idx_list), page_w, page_h)
        for pos, global_idx in enumerate(idx_list):
            bbox_map[global_idx] = pbboxes[pos] if pos < len(pbboxes) else [0, 0, page_w, page_h]

    results = []
    for i, item in enumerate(items):
        bbox = bbox_map.get(i, [0, 0, widths[0], heights[0]])

        working_steps_raw = item.get("working_steps", [])
        if not isinstance(working_steps_raw, list):
            working_steps_raw = []
        working_steps = [str(s) for s in working_steps_raw if s is not None]

        try:
            confidence = float(item.get("confidence", 0.5))
        except Exception:
            confidence = 0.5

        # Skip textbook examples
        if item.get("is_example", False):
            continue

        try:
            marks = int(item.get("marks", 0) or 0)
        except (ValueError, TypeError):
            marks = 0

        contains_diagram = bool(item.get("contains_diagram", False))
        raw_dt = item.get("diagram_type")
        diagram_type: str | None = None
        if contains_diagram and raw_dt and str(raw_dt).strip().lower() not in ("", "null", "none"):
            dt = str(raw_dt).strip().lower()
            _ALLOWED = {"stem_leaf", "histogram", "box_plot", "cumulative_frequency",
                        "scatter", "bar_chart", "other"}
            diagram_type = dt if dt in _ALLOWED else "other"

        results.append({
            "question_number": str(item.get("question_number", str(i + 1))),
            "bbox": bbox,
            "question_text": str(item.get("question_text", "")),
            "parent_stem": str(item.get("parent_stem", "") or ""),
            "student_answer": str(item.get("student_answer", "")),
            "working_steps": working_steps,
            "marks": marks,
            "image_quality": str(item.get("image_quality", "fair")),
            "confidence": confidence,
            "page": int(item.get("_page_norm", 1)),
            "contains_diagram": contains_diagram,
            "diagram_type": diagram_type,
        })

    # OCR 回写默认关闭（SequenceMatcher 窗口对齐会误伤数字密集的数学题面，
    # 实测会把 "-8x" 改成 "-4x"、"√85" 改成 "√45"）。
    # 保留 OCR 调用以便以后做 question_number 锚点等用途，但不再改写 VL 抽取结果。
    if ocr_text and os.environ.get("SEGMENT_OCR_REWRITE", "0").strip() in ("1", "true", "True"):
        logging.getLogger("pipeline.segmenter").info(
            "cross-verifying with OCR (%d chars)", len(ocr_text)
        )
        results = _merge_ocr(results, ocr_text)

    # 孤儿子题（裸 "(i)"/"(a)"）回填父题题干，避免 grader 看空白题干直接判错
    _attach_parent_stems(results)

    _flag_inconsistencies(results)
    flagged = sum(1 for r in results if r.get("needs_review"))
    if flagged:
        logging.getLogger("pipeline.segmenter").info(
            "consistency check: flagged %d/%d items as needs_review", flagged, len(results)
        )

    # Env-gated post-processed snapshot: AFTER all merges, stem attachment,
    # inconsistency flagging. Paired with the "raw" dump above so we can
    # diff VL-original vs final state for each item.
    _dump_vl_snapshot(results, "postprocessed")

    return results
