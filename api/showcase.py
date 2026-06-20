"""/showcase · A-Level Assistant 产品落地页 (面试官 demo 主入口)

设计原则:
  · K12 在线教育风 (作业帮 / 学而思 / 猿辅导)
  · 蓝主色 + 橙 CTA + 大圆角 + 圆润粗字 + 学科徽章 + 数字强调
  · 一张真实的 输入 → 输出 对比, 不放技术黑话
  · 几十人内测口径 · 不夸张
  · 单 CTA "上传你的作业试试 →"
  · 技术细节默认折叠, 只对感兴趣的读者展开
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


showcase_router = APIRouter(tags=["showcase"])


@showcase_router.get("/showcase", response_class=HTMLResponse)
async def showcase_page():
    return _HTML


_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>A-Level 数学批改助手 · 拍一页, 3 分钟逐题反馈</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="A-Level 数学作业自动批改 · 拍一页作业, 3 分钟给出逐题反馈 · 几十名学生内测中">

<!-- KaTeX · 数学公式渲染 (国内可用 CDN) -->
<link rel="stylesheet" href="https://cdn.bootcdn.net/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script src="https://cdn.bootcdn.net/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
<script src="https://cdn.bootcdn.net/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"
        onload="window.__katexReady=true;document.dispatchEvent(new Event('katex-ready'))"></script>
<style>
:root {
  --blue: #2B7DFF;
  --blue-deep: #1B5FCC;
  --blue-soft: #EAF2FF;
  --blue-softer: #F4F8FF;
  --orange: #FF6B35;
  --orange-deep: #E5562A;
  --orange-soft: #FFF1EC;
  --yellow: #FFB800;
  --yellow-soft: #FFF8E1;
  --green: #00B894;
  --green-soft: #E6FBF4;
  --red: #FF4757;
  --red-soft: #FFEEF0;
  --ink: #1A2233;
  --ink-soft: #5A6478;
  --ink-muted: #98A0B0;
  --line: #E8ECF2;
  --line-strong: #D6DBE5;
  --bg: #FFFFFF;
  --bg-soft: #FAFBFD;
  --shadow-sm: 0 1px 3px rgba(43, 125, 255, 0.08);
  --shadow-md: 0 8px 24px rgba(43, 125, 255, 0.12);
  --shadow-orange: 0 6px 20px rgba(255, 107, 53, 0.32);
  --shadow-blue: 0 6px 20px rgba(43, 125, 255, 0.32);
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "SF Pro Rounded", "Inter", sans-serif; -webkit-font-smoothing: antialiased; color: var(--ink); background: var(--bg); }
body { line-height: 1.55; font-size: 16px; }
a { color: inherit; text-decoration: none; }

.wrap { max-width: 1120px; margin: 0 auto; padding: 0 24px; }

/* ── Nav ──────────────────────────────────────────────────── */
.nav {
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: saturate(180%) blur(14px);
  border-bottom: 1px solid var(--line);
  padding: 14px 0;
  position: sticky;
  top: 0;
  z-index: 100;
}
.nav .wrap { display: flex; align-items: center; gap: 24px; }
.nav .brand { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 17px; }
.nav .brand-logo {
  width: 32px; height: 32px;
  background: linear-gradient(135deg, var(--blue), var(--blue-deep));
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 800; font-size: 17px;
  box-shadow: var(--shadow-sm);
}
.nav .pill {
  display: inline-block;
  background: var(--orange-soft); color: var(--orange-deep);
  font-size: 11px; padding: 3px 8px; border-radius: 5px;
  font-weight: 700; letter-spacing: 0.04em;
  margin-left: 4px; vertical-align: 1px;
}
.nav .spacer { flex: 1; }
.nav .nav-link { font-size: 14px; color: var(--ink-soft); font-weight: 600; transition: color 0.15s; }
.nav .nav-link:hover { color: var(--blue); }
.nav .cta-nav {
  background: var(--orange); color: #fff;
  padding: 8px 16px; border-radius: 10px;
  font-size: 14px; font-weight: 700;
  box-shadow: var(--shadow-orange);
  transition: transform 0.12s, box-shadow 0.15s;
}
.nav .cta-nav:hover { transform: translateY(-1px); box-shadow: 0 8px 24px rgba(255,107,53,0.4); }

/* ── Hero ─────────────────────────────────────────────────── */
.hero {
  padding: 80px 0 72px;
  background: radial-gradient(ellipse at 80% 0%, rgba(255, 184, 0, 0.06), transparent 60%),
              radial-gradient(ellipse at 0% 50%, rgba(43, 125, 255, 0.08), transparent 50%),
              var(--bg);
  position: relative;
  overflow: hidden;
}
.hero::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background-image:
    radial-gradient(circle at 10% 90%, rgba(255, 107, 53, 0.04), transparent 40%);
  pointer-events: none;
}
.hero .wrap { position: relative; }
.hero .eyebrow {
  display: inline-flex; align-items: center; gap: 8px;
  background: var(--blue-soft); color: var(--blue-deep);
  padding: 7px 14px; border-radius: 999px;
  font-size: 13px; font-weight: 700;
  margin-bottom: 24px;
}
.hero .eyebrow .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--blue);
  box-shadow: 0 0 0 4px rgba(43, 125, 255, 0.18);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(1.15); }
}
.hero h1 {
  font-size: clamp(34px, 5.2vw, 56px);
  line-height: 1.1; letter-spacing: -0.03em;
  font-weight: 800;
  margin-bottom: 20px;
  max-width: 820px;
}
.hero h1 .accent { color: var(--blue); }
.hero h1 .highlight {
  background: linear-gradient(180deg, transparent 60%, rgba(255, 184, 0, 0.4) 60%);
  padding: 0 4px;
}
.hero .lede {
  font-size: 18px; color: var(--ink-soft);
  max-width: 640px; margin-bottom: 32px;
  line-height: 1.65;
}
.hero .cta-row { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; margin-bottom: 36px; }
.btn-primary {
  background: linear-gradient(180deg, var(--orange), var(--orange-deep));
  color: #fff;
  padding: 14px 26px;
  border-radius: 12px;
  font-size: 16px; font-weight: 700;
  display: inline-flex; align-items: center; gap: 8px;
  box-shadow: var(--shadow-orange);
  transition: transform 0.12s, box-shadow 0.15s;
}
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 12px 28px rgba(255,107,53,0.45); }
.btn-primary:active { transform: translateY(0); }
.btn-primary .arrow { font-size: 18px; transition: transform 0.2s; }
.btn-primary:hover .arrow { transform: translateX(4px); }

.btn-secondary {
  background: #fff;
  color: var(--blue-deep);
  padding: 14px 24px;
  border-radius: 12px;
  font-size: 16px; font-weight: 700;
  border: 2px solid var(--blue-soft);
  transition: border-color 0.15s, background 0.15s;
}
.btn-secondary:hover { border-color: var(--blue); background: var(--blue-softer); }

.subjects {
  display: flex; gap: 10px; flex-wrap: wrap;
  margin-bottom: 16px;
}
.subj-chip {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--bg);
  border: 1.5px solid var(--line);
  padding: 8px 14px; border-radius: 999px;
  font-size: 13px; font-weight: 700; color: var(--ink-soft);
  transition: border-color 0.15s, color 0.15s;
}
.subj-chip:hover { border-color: var(--blue); color: var(--blue); }
.subj-chip .ico { font-size: 16px; }

/* Hero stats */
.hero-stats {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 16px; margin-top: 48px;
}
@media (max-width: 760px) { .hero-stats { grid-template-columns: repeat(2, 1fr); } }
.stat-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 20px;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
}
.stat-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); border-color: var(--blue-soft); }
.stat-num {
  font-size: 28px; font-weight: 800; color: var(--ink);
  letter-spacing: -0.02em; line-height: 1.1;
  margin-bottom: 6px;
}
.stat-num .unit { font-size: 16px; color: var(--ink-muted); margin-left: 2px; }
.stat-num .accent { color: var(--blue); }
.stat-num .orange { color: var(--orange); }
.stat-num .green-num { color: var(--green); }
.stat-label { font-size: 13px; color: var(--ink-soft); }

/* ── Hero mockup ──────────────────────────────────────── */
.hero-mockup {
  margin-top: 56px;
  position: relative;
}
.mock-browser {
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(43, 125, 255, 0.18), 0 4px 12px rgba(0,0,0,0.04);
  overflow: hidden;
  border: 1px solid var(--line);
}
.mock-bar {
  background: #F5F7FB;
  padding: 12px 18px;
  border-bottom: 1px solid var(--line);
  display: flex; align-items: center; gap: 14px;
}
.mock-dots { display: flex; gap: 7px; }
.mock-dots span { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.mock-url {
  flex: 1; text-align: center;
  background: #fff; border: 1px solid var(--line); border-radius: 8px;
  padding: 5px 14px; font-size: 12.5px; color: var(--ink-soft);
  font-family: ui-monospace, monospace;
  max-width: 380px; margin: 0 auto;
}
.mock-content { padding: 32px 36px; }
.mock-app-head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 18px; gap: 16px; }
.mock-app-title { font-size: 22px; font-weight: 800; color: var(--ink); letter-spacing: -0.02em; }
.mock-app-sub { font-size: 13px; color: var(--ink-soft); margin-top: 4px; }
.mock-user-chip {
  background: #fff; border: 1.5px solid var(--line);
  padding: 6px 14px; border-radius: 999px;
  font-size: 12.5px; font-weight: 700; color: var(--ink-soft);
  flex-shrink: 0;
}
.mock-tabs {
  display: flex; gap: 24px;
  border-bottom: 1.5px solid var(--line);
  margin-bottom: 28px;
}
.mock-tab {
  font-size: 13.5px; font-weight: 700; color: var(--ink-muted);
  padding: 10px 0; position: relative;
}
.mock-tab.active { color: var(--blue); }
.mock-tab.active::after {
  content: ''; position: absolute; bottom: -1.5px; left: 0; right: 0;
  height: 3px; background: var(--blue); border-radius: 2px;
}
.mock-upload {
  border: 2px dashed var(--line-strong);
  border-radius: 14px;
  padding: 36px 24px;
  text-align: center;
  margin-bottom: 14px;
  background: var(--bg-soft);
}
.mock-upload-icon { font-size: 36px; margin-bottom: 12px; opacity: 0.5; }
.mock-upload-title { font-size: 14px; font-weight: 700; color: var(--ink-soft); margin-bottom: 4px; }
.mock-upload-sub { font-size: 12px; color: var(--ink-muted); margin-bottom: 18px; }
.mock-upload-actions { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
.mock-btn-primary {
  background: var(--blue); color: #fff;
  padding: 8px 18px; border-radius: 8px; font-size: 13px; font-weight: 700;
}
.mock-btn-secondary {
  background: #fff; border: 1.5px solid var(--line);
  padding: 8px 18px; border-radius: 8px; font-size: 13px; font-weight: 700;
  color: var(--ink-soft);
}
.mock-pdf {
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 14px 18px;
  display: flex; align-items: center; gap: 14px;
}
.mock-pdf-ic { font-size: 26px; }
.mock-pdf-title { font-size: 14px; font-weight: 700; }
.mock-pdf-sub { font-size: 12px; color: var(--ink-muted); margin-top: 2px; }

/* 浮动批改结果气泡 */
.mock-float-bubble {
  position: absolute;
  right: 16px; top: 96px;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 16px 40px rgba(0, 184, 148, 0.22), 0 4px 12px rgba(0,0,0,0.06);
  padding: 16px 18px;
  width: 260px;
  border: 1.5px solid var(--green);
  transform: rotate(2deg);
  z-index: 2;
}
@media (max-width: 1100px) { .mock-float-bubble { right: 8px; top: 76px; width: 240px; } }
@media (max-width: 900px) {
  .mock-float-bubble { position: static; transform: none; margin-top: 16px; width: 100%; }
}
.float-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.float-tag {
  background: var(--green); color: #fff;
  padding: 3px 9px; border-radius: 5px;
  font-size: 11px; font-weight: 800; letter-spacing: 0.04em;
}
.float-time { font-size: 11px; color: var(--ink-muted); font-weight: 700; }
.float-title { font-weight: 800; font-size: 13px; margin-bottom: 6px; color: var(--ink); }
.float-body { font-size: 12.5px; color: var(--ink-soft); line-height: 1.55; margin-bottom: 8px; }
.float-body code {
  font-family: ui-monospace, monospace; font-size: 11px;
  background: var(--green-soft); color: var(--green);
  padding: 1px 5px; border-radius: 4px;
}
.float-foot { padding-top: 8px; border-top: 1px dashed var(--line); }
.float-check {
  font-family: ui-monospace, monospace; font-size: 11px;
  color: var(--green); font-weight: 700;
}

/* ── Voices section (testimonial / 使用反馈) ────────────── */
.voices {
  padding: 80px 0;
  background: linear-gradient(180deg, #FFFAF0 0%, var(--bg) 100%);
  border-top: 1px solid var(--line);
}
.voices .head-center { text-align: center; margin-bottom: 48px; }
.voices .head-center .section-label { justify-content: center; }
.voices .section-label::before { background: var(--orange); }
.voices .section-label { color: var(--orange-deep); }

.voices-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
@media (max-width: 860px) { .voices-grid { grid-template-columns: 1fr; } }

.voice-card {
  background: #fff;
  border-radius: 20px;
  padding: 28px 26px;
  border: 1.5px solid var(--line);
  box-shadow: var(--shadow-sm);
  display: flex; flex-direction: column;
  position: relative;
  transition: transform 0.18s, box-shadow 0.18s;
}
.voice-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-md); }

.voice-quote-mark {
  position: absolute;
  top: 18px; right: 22px;
  font-size: 56px; font-weight: 800;
  color: var(--blue-soft);
  line-height: 0.8;
  font-family: Georgia, serif;
}
.voice-card.t-teacher .voice-quote-mark { color: var(--orange-soft); }
.voice-card.t-student .voice-quote-mark { color: var(--blue-soft); }
.voice-card.t-growth .voice-quote-mark { color: var(--green-soft); }

.voice-avatar-row {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 16px;
}
.voice-avatar {
  width: 48px; height: 48px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 800;
  color: #fff;
  flex-shrink: 0;
}
.voice-card.t-teacher .voice-avatar { background: linear-gradient(135deg, var(--orange), var(--orange-deep)); }
.voice-card.t-student .voice-avatar { background: linear-gradient(135deg, var(--blue), var(--blue-deep)); }
.voice-card.t-growth .voice-avatar { background: linear-gradient(135deg, var(--green), #009A7C); }

.voice-meta-name { font-weight: 800; font-size: 14.5px; color: var(--ink); }
.voice-meta-sub { font-size: 12px; color: var(--ink-muted); margin-top: 2px; }

.voice-tag {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 11px; font-weight: 800;
  padding: 3px 8px; border-radius: 5px;
  letter-spacing: 0.04em; margin-bottom: 12px;
}
.voice-card.t-teacher .voice-tag { background: var(--orange-soft); color: var(--orange-deep); }
.voice-card.t-student .voice-tag { background: var(--blue-soft); color: var(--blue-deep); }
.voice-card.t-growth .voice-tag { background: var(--green-soft); color: var(--green); }

.voice-quote {
  font-size: 15px; line-height: 1.7;
  color: var(--ink); margin-bottom: 16px;
  font-weight: 500;
  flex: 1;
}
.voice-quote .highlight {
  background: var(--yellow-soft);
  padding: 0 4px; font-weight: 700;
  color: var(--ink);
}
.voice-source {
  padding-top: 14px;
  border-top: 1px dashed var(--line);
  font-size: 11.5px; color: var(--ink-muted);
  display: flex; align-items: center; gap: 6px;
}

.voice-bignum {
  font-size: 32px; font-weight: 800; line-height: 1;
  margin-bottom: 6px; letter-spacing: -0.02em;
}
.voice-card.t-growth .voice-bignum { color: var(--green); }
.voice-card.t-teacher .voice-bignum { color: var(--orange); }
.voice-bignum-label { font-size: 13px; color: var(--ink-soft); font-weight: 600; }

/* ── Demo ─────────────────────────────────────────────────── */
.demo {
  padding: 80px 0;
  background: var(--blue-softer);
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.section-label {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 800; color: var(--blue-deep);
  text-transform: uppercase; letter-spacing: 0.1em;
  margin-bottom: 14px;
}
.section-label::before {
  content: ''; width: 22px; height: 3px;
  background: var(--blue); border-radius: 2px;
}
.section-title {
  font-size: clamp(26px, 3.4vw, 36px);
  font-weight: 800; letter-spacing: -0.02em;
  margin-bottom: 12px;
  line-height: 1.2;
}
.section-sub {
  color: var(--ink-soft); margin-bottom: 36px;
  max-width: 620px; font-size: 16px;
}

.demo-grid {
  display: grid;
  grid-template-columns: 1fr 56px 1fr;
  gap: 18px; align-items: stretch;
}
@media (max-width: 800px) { .demo-grid { grid-template-columns: 1fr; } .demo-arrow { transform: rotate(90deg); height: 40px; } }
.demo-card {
  background: #fff;
  border: 1.5px solid var(--line);
  border-radius: 18px;
  overflow: hidden;
  display: flex; flex-direction: column;
  box-shadow: var(--shadow-sm);
  position: relative;
}
.demo-card .head {
  padding: 14px 18px;
  border-bottom: 1.5px solid var(--line);
  display: flex; align-items: center; gap: 10px;
  font-size: 13px; font-weight: 700; color: var(--ink-soft);
  background: var(--bg-soft);
}
.demo-card .head .badge {
  font-size: 11px; font-weight: 800;
  padding: 3px 10px; border-radius: 6px;
  letter-spacing: 0.06em;
}
.demo-card.input-card .head .badge { background: var(--blue-soft); color: var(--blue-deep); }
.demo-card.output-card .head .badge { background: var(--green-soft); color: var(--green); }
.demo-card .body { padding: 22px; font-size: 14.5px; line-height: 1.65; flex: 1; }

/* ── 图片导入 + bbox overlay ────────────────────────── */
.img-import-wrap { margin-bottom: 8px; }
.img-frame {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  border: 1.5px solid var(--line);
  background: #fff;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.18s;
}
.img-frame:hover { box-shadow: var(--shadow-md); }
.demo-img { width: 100%; height: auto; display: block; }
#img-overlay {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  pointer-events: none;
}
.bbox {
  position: absolute;
  border: 2.5px solid var(--blue);
  background: rgba(43, 125, 255, 0.08);
  border-radius: 4px;
  opacity: 0;
  animation: bbox-pulse 0.45s ease-out forwards;
  transition: opacity 0.35s, filter 0.35s, border-color 0.35s, box-shadow 0.35s, transform 0.35s;
}
.bbox.q1d { border-color: var(--orange); background: rgba(255, 107, 53, 0.1); animation-delay: 0.6s; }
.bbox-label {
  position: absolute;
  top: -22px; left: -2px;
  background: var(--blue);
  color: #fff;
  font-size: 10px; font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px 4px 4px 0;
  font-family: ui-monospace, monospace;
  letter-spacing: 0.04em;
  transition: all 0.3s;
}
.bbox.q1d .bbox-label { background: var(--orange); }
@keyframes bbox-pulse {
  0% { opacity: 0; transform: scale(0.95); }
  100% { opacity: 1; transform: scale(1); }
}

/* === bbox 联动当前 active agent ============================ */
/* dim: 不在 focus 内的题, 淡化 */
.bbox.dim { opacity: 0.18; filter: grayscale(0.7); transform: scale(0.97); }
.bbox.dim .bbox-label { opacity: 0.5; }

/* focus: 当前 agent 关注的题, 强高亮 + 厚边 */
.bbox.focus {
  border-width: 3px;
  box-shadow: 0 0 0 3px rgba(255, 107, 53, 0.18), 0 6px 18px rgba(0,0,0,0.12);
  z-index: 3;
  opacity: 1;
}
.bbox.focus .bbox-label {
  font-size: 11px; padding: 3px 8px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.15);
}

/* scan: 扫描线动画 (OCR/Grader 在精读) */
.bbox.scan { overflow: hidden; }
.bbox.scan::after {
  content: '';
  position: absolute; left: 0; right: 0; top: 0;
  height: 4px;
  background: linear-gradient(180deg, rgba(43,125,255,0.55) 0%, rgba(43,125,255,0.1) 70%, transparent 100%);
  box-shadow: 0 0 8px rgba(43,125,255,0.5);
  animation: scan-line 1.6s ease-in-out infinite;
}
@keyframes scan-line {
  0%   { transform: translateY(0%); opacity: 0.9; }
  50%  { transform: translateY(calc(100% - 4px)); opacity: 0.9; }
  51%  { opacity: 0; }
  60%  { transform: translateY(0%); opacity: 0; }
  61%  { opacity: 0.9; }
  100% { transform: translateY(0%); opacity: 0.9; }
}

/* error-mark: 标红色错位行 (Q1d 内部第 6 行位置) */
.bbox .err-row {
  position: absolute;
  left: 4%; right: 4%;
  height: 14px;
  background: rgba(244, 67, 54, 0.18);
  border-left: 3px solid #ef4444;
  border-radius: 2px;
  animation: err-row-in 0.5s ease;
}
@keyframes err-row-in {
  from { opacity: 0; transform: translateX(-6px); }
  to   { opacity: 1; transform: translateX(0); }
}
.bbox .err-row::before {
  content: '✕ 第 6 行符号错';
  position: absolute;
  right: -2px; top: -22px;
  background: #ef4444; color: #fff;
  font-size: 10px; font-weight: 700;
  padding: 2px 7px; border-radius: 4px;
  white-space: nowrap;
  font-family: ui-monospace, monospace;
}

/* agent 标签贴纸 (画在 bbox 右上角, 谁在看这个 bbox) */
.bbox-agent-tag {
  position: absolute;
  right: 6px; top: 6px;
  background: rgba(255,255,255,0.96);
  color: #1f2937;
  font-size: 10.5px; font-weight: 700;
  padding: 3px 8px; border-radius: 10px;
  display: flex; align-items: center; gap: 4px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.15);
  animation: tag-in 0.3s ease;
  pointer-events: none;
}
.bbox-agent-tag .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--blue);
  animation: dot-pulse 1.2s ease-in-out infinite;
}
@keyframes tag-in {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes dot-pulse {
  0%,100% { opacity: 0.4; transform: scale(0.8); }
  50%     { opacity: 1;   transform: scale(1.2); }
}
.img-meta {
  display: flex; gap: 8px; align-items: center;
  font-size: 11.5px; color: var(--ink-soft);
  font-family: ui-monospace, monospace;
  padding: 8px 12px;
}
.img-meta .img-replace {
  margin-left: auto;
  font-size: 11px; font-weight: 700;
  color: var(--blue); text-decoration: none;
  background: var(--blue-soft);
  padding: 3px 8px; border-radius: 4px;
  font-family: inherit;
}
.img-meta .img-replace:hover { background: var(--blue); color: #fff; }

#ocr-output {
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif !important;
  font-size: 13.5px;
}
#ocr-output .ocr-line {
  display: block;
  opacity: 0;
  animation: ocr-fade-in 0.25s ease-out forwards;
  line-height: 2.1;
  padding: 2px 0;
}
#ocr-output .ocr-line .katex { font-size: 1.05em; }
@keyframes ocr-fade-in {
  from { opacity: 0; transform: translateX(-4px); }
  to { opacity: 1; transform: translateX(0); }
}

/* ── 进度环 (中间箭头变成多阶段) ───────────────────── */
.demo-arrow .ar-circle { position: relative; transition: background 0.3s; }
.demo-arrow .ar-circle.stage-active {
  animation: arrow-glow 1.2s ease-in-out infinite;
}
@keyframes arrow-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(43, 125, 255, 0.5); }
  50% { box-shadow: 0 0 0 10px rgba(43, 125, 255, 0); }
}
.demo-arrow .ar-circle.stage-done {
  background: linear-gradient(135deg, var(--green), #009A7C);
}
.demo-arrow .ar-circle.stage-done svg path { d: path("M6 12l4 4 8-8"); }

/* ── 多阶段进度条 (右卡内, loading 替换) ──────────── */
.stage-progress {
  background: #fafbfc;
  border: 1px solid #e5e9f0;
  border-radius: 12px;
  padding: 14px 16px 8px;
  margin-bottom: 12px;
}
.stage-progress-head {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 12px;
}
.stage-progress-head .grade-spinner {
  width: 18px; height: 18px; border-width: 2.5px;
}
.stage-progress-head .stage-current {
  font-size: 13.5px; font-weight: 800; color: var(--ink); flex: 1;
}
.stage-progress-head .stage-elapsed {
  font-family: ui-monospace, monospace; font-size: 12px;
  color: var(--blue-deep); font-weight: 700;
}

/* ── Timeline 风格步骤列表 (参考 Vercel deploy / Linear) ─────── */
.stage-list {
  display: flex; flex-direction: column;
  position: relative;
  padding-left: 4px;
}
/* 连接线 */
.stage-list::before {
  content: '';
  position: absolute;
  left: 13px; top: 12px; bottom: 12px;
  width: 2px;
  background: linear-gradient(to bottom, #e5e9f0 0%, #e5e9f0 var(--progress, 0%), #cbd5e0 var(--progress, 0%), #cbd5e0 100%);
  z-index: 0;
}
.stage-item {
  display: grid;
  grid-template-columns: 22px 1fr auto;
  align-items: center;
  gap: 10px;
  font-size: 12.5px; color: #94a3b8;
  padding: 5px 0;
  position: relative;
  transition: all 0.25s ease;
}
.stage-item .si-ic {
  width: 22px; height: 22px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid #cbd5e0;
  display: flex; align-items: center; justify-content: center;
  font-size: 10.5px; color: #94a3b8; font-weight: 700;
  flex-shrink: 0; z-index: 1; position: relative;
  transition: all 0.25s ease;
}
.stage-item .si-label { line-height: 1.3; }
.stage-item .si-time, .stage-item .si-eta {
  font-family: ui-monospace, monospace; font-size: 11px;
  color: #94a3b8; font-variant-numeric: tabular-nums;
}
.stage-item .si-eta { color: #6b7280; font-weight: 600; }

/* === done 状态: 紧凑 + 打勾 === */
.stage-item.done .si-ic {
  background: var(--green); border-color: var(--green);
  color: #fff; font-size: 0;
}
.stage-item.done .si-ic::before {
  content: '✓'; font-size: 13px; font-weight: 800;
}
.stage-item.done { color: #1f2937; }
.stage-item.done .si-label { font-weight: 500; }
.stage-item.done .si-eta { display: none; }
.stage-item.done .si-time { color: #047857; font-weight: 700; }

/* === active 状态: 大卡片 + 思考短语展开 (参考 Claude thinking) === */
.stage-item.active {
  background: linear-gradient(90deg, rgba(43,125,255,0.06) 0%, rgba(43,125,255,0.02) 100%);
  border-radius: 8px;
  padding: 10px 10px 12px;
  margin: 4px -10px;
  grid-template-columns: 22px 1fr auto;
  color: #1e3a8a;
  box-shadow: 0 1px 3px rgba(43,125,255,0.08);
}
.stage-item.active .si-ic {
  background: var(--blue); border-color: var(--blue); color: #fff;
  font-size: 10.5px; font-weight: 800;
  animation: pulse-blue 1.4s ease-out infinite;
}
@keyframes pulse-blue {
  0%   { box-shadow: 0 0 0 0 rgba(43, 125, 255, 0.5); }
  60%  { box-shadow: 0 0 0 8px rgba(43, 125, 255, 0); }
  100% { box-shadow: 0 0 0 0 rgba(43, 125, 255, 0); }
}
.stage-item.active .si-label {
  font-weight: 700; color: #1e3a8a; font-size: 13px;
}
.stage-item.active .si-eta {
  color: var(--blue-deep); font-weight: 700;
  background: rgba(43,125,255,0.1); padding: 2px 7px; border-radius: 8px;
  font-size: 10.5px;
}

/* === 思考短语 (active 时展开在下面) === */
.stage-item .si-tip {
  grid-column: 2 / -1;
  font-size: 12px; color: #475569;
  margin-top: 6px; padding: 8px 11px;
  background: #fff;
  border-left: 3px solid var(--blue);
  border-radius: 4px;
  display: none;
  font-family: 'PingFang SC', -apple-system, sans-serif;
  line-height: 1.5;
  position: relative;
}
.stage-item .si-tip::after {
  content: '';
  display: inline-block;
  width: 1px; height: 11px;
  background: var(--blue);
  margin-left: 2px; vertical-align: -2px;
  animation: blink-cursor 1s step-end infinite;
}
@keyframes blink-cursor {
  50% { opacity: 0; }
}
.stage-item.active .si-tip { display: block; animation: slide-down 0.3s ease; }
@keyframes slide-down {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* === pending 状态: 灰淡 === */
.stage-item:not(.active):not(.done) .si-ic { font-weight: 700; }

/* ── 总进度条 (头部) ── */
.demo-overall {
  background: linear-gradient(135deg, #eef4ff 0%, #f7f5ff 100%);
  border: 1px solid #d8e3ff;
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 12px;
}
.demo-overall-row {
  display: flex; align-items: center; gap: 10px;
  font-size: 11.5px; color: var(--ink-soft); font-weight: 600;
}
.demo-overall-row b { color: var(--blue-deep); font-family: ui-monospace, monospace; }
.demo-overall-bar {
  height: 5px; background: #e2e8f0; border-radius: 3px;
  margin-top: 6px; overflow: hidden;
}
.demo-overall-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--blue) 0%, var(--green) 100%);
  width: 0%; transition: width 0.6s ease;
  border-radius: 3px;
}
.demo-stars {
  display: inline-flex; gap: 2px; margin-left: auto;
  font-size: 13px;
}
.demo-star {
  opacity: 0.22;
  filter: grayscale(1);
  transition: all 0.3s;
  display: inline-block;
}
.demo-star.lit {
  opacity: 1;
  filter: none;
  animation: star-pop 0.6s cubic-bezier(.34,1.56,.64,1);
  text-shadow: 0 0 8px rgba(251, 191, 36, 0.5);
}
@keyframes star-pop {
  0%   { transform: scale(0.4) rotate(-30deg); }
  50%  { transform: scale(1.6) rotate(15deg); }
  100% { transform: scale(1) rotate(0); }
}
.demo-stars.all-lit .demo-star {
  animation: star-shimmer 1.2s ease-in-out infinite;
}
.demo-stars.all-lit .demo-star:nth-child(1) { animation-delay: 0.0s; }
.demo-stars.all-lit .demo-star:nth-child(2) { animation-delay: 0.1s; }
.demo-stars.all-lit .demo-star:nth-child(3) { animation-delay: 0.2s; }
.demo-stars.all-lit .demo-star:nth-child(4) { animation-delay: 0.3s; }
.demo-stars.all-lit .demo-star:nth-child(5) { animation-delay: 0.4s; }
@keyframes star-shimmer {
  0%, 100% { transform: scale(1); text-shadow: 0 0 8px rgba(251, 191, 36, 0.5); }
  50%      { transform: scale(1.18); text-shadow: 0 0 14px rgba(251, 191, 36, 0.9); }
}

/* ── 完成态庆祝 (绿条 + 勾) ── */
.demo-overall.celebrating {
  background: linear-gradient(135deg, #d1fae5 0%, #fef3c7 100%);
  border-color: #6ee7b7;
  animation: celebrate-bg 1.2s ease;
}
@keyframes celebrate-bg {
  0%, 100% { box-shadow: 0 0 0 0 rgba(110, 231, 183, 0); }
  50%      { box-shadow: 0 0 20px 4px rgba(110, 231, 183, 0.5); }
}

/* ── confetti 颗粒 ── */
.confetti-piece {
  position: absolute;
  width: 8px; height: 8px;
  pointer-events: none;
  border-radius: 1px;
  animation: confetti-fall 1.6s ease-out forwards;
}
@keyframes confetti-fall {
  0%   { transform: translate(0, 0) rotate(0); opacity: 1; }
  100% { transform: translate(var(--cx, 0), var(--cy, 120px)) rotate(720deg); opacity: 0; }
}

/* ── Agent 对话气泡 (2026-05-29 新增·5 agent 互讨论) ─────── */
.agent-chat {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #e5e9f0;
  display: flex; flex-direction: column; gap: 10px;
  max-height: 360px;
  overflow-y: auto;
  padding-left: 4px; padding-right: 4px;
  position: relative;
}
.agent-chat-head {
  font-size: 10.5px; font-weight: 800;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 2px;
  display: flex; align-items: center; gap: 6px;
}
.agent-chat-head::after {
  content: ''; flex: 1; height: 1px;
  background: linear-gradient(to right, #e5e9f0, transparent);
}
.agent-bubble {
  display: flex; align-items: flex-start; gap: 10px;
  font-size: 12.5px;
  opacity: 0;
  animation: bubble-in 0.4s cubic-bezier(.34,1.56,.64,1) forwards;
  position: relative;
}
/* timeline 连接线 (头像之间) */
.agent-bubble:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 17px; top: 36px;
  width: 2px; height: calc(100% - 28px);
  background: #e5e9f0;
  z-index: 0;
}
@keyframes bubble-in {
  from { opacity: 0; transform: translateX(-8px) scale(0.98); }
  to   { opacity: 1; transform: translateX(0) scale(1); }
}
.agent-bubble-avatar {
  width: 32px; height: 32px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 800;
  color: #fff; flex-shrink: 0;
  margin-top: 1px;
  z-index: 1;
  box-shadow: 0 0 0 3px #fff, 0 1px 4px rgba(0,0,0,0.08);
}
.agent-bubble.blue   .agent-bubble-avatar { background: linear-gradient(135deg, #3D7BFF, #1E4FCC); }
.agent-bubble.orange .agent-bubble-avatar { background: linear-gradient(135deg, #FF7A33, #E55B0D); }
.agent-bubble.green  .agent-bubble-avatar { background: linear-gradient(135deg, #00B894, #009A7C); }
.agent-bubble.purple .agent-bubble-avatar { background: linear-gradient(135deg, #9333EA, #6D28D9); }
.agent-bubble-body { flex: 1; min-width: 0; }
.agent-bubble-name {
  font-size: 11.5px; font-weight: 800;
  color: var(--ink);
  margin-bottom: 2px;
  display: flex; align-items: baseline; gap: 6px;
  flex-wrap: wrap;
}
.agent-bubble-role {
  font-size: 10px; font-weight: 600;
  color: var(--ink-muted);
}
.agent-bubble-kind {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 9.5px; font-weight: 700;
  padding: 1px 6px; border-radius: 4px;
  letter-spacing: 0.04em;
  margin-left: auto;
}
.agent-bubble-kind.real {
  background: #E8F8F3; color: #009A7C;
}
.agent-bubble-kind.real::before {
  content: '⚡'; font-size: 10px;
}
.agent-bubble-kind.fallback {
  background: #F0F2F5; color: #94A3B8;
}
.agent-bubble-elapsed {
  font-size: 9.5px; font-weight: 700;
  color: var(--ink-muted);
  font-family: ui-monospace, monospace;
  background: #F7FAFF;
  padding: 1px 5px; border-radius: 3px;
}
.agent-bubble-text {
  background: #F7FAFF;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  padding: 8px 12px;
  line-height: 1.6;
  color: var(--ink);
  font-weight: 500;
  word-wrap: break-word;
}
.agent-bubble.orange .agent-bubble-text { background: #FFF7EF; border-color: #FFD9B8; }
.agent-bubble.green  .agent-bubble-text { background: #E8F8F3; border-color: #B5E8D9; }
.agent-bubble.purple .agent-bubble-text { background: #F5EBFF; border-color: #DDC7F2; }
.agent-bubble-text code {
  background: rgba(0,0,0,0.06);
  padding: 1px 5px; border-radius: 4px;
  font-size: 11.5px;
}

/* ── Output Tabs (Agent 对话 / SSE 流 切换) ─────────────── */
.output-tabs {
  display: flex; gap: 4px;
  border-bottom: 1.5px solid #e5e9f0;
  margin-top: 16px;
  padding: 0 2px;
}
.output-tabs .tab {
  font-size: 12.5px; font-weight: 700;
  padding: 9px 14px 11px;
  color: #94a3b8;
  cursor: pointer;
  border: none; background: transparent;
  border-bottom: 2px solid transparent;
  margin-bottom: -1.5px;
  transition: all 0.15s;
  display: inline-flex; align-items: center; gap: 7px;
  font-family: inherit;
  border-radius: 6px 6px 0 0;
}
.output-tabs .tab:hover {
  color: #475569;
  background: rgba(43,125,255,0.04);
}
.output-tabs .tab.active {
  color: var(--blue-deep);
  border-bottom-color: var(--blue);
  background: transparent;
}
.output-tabs .tab-count {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 18px; height: 16px;
  padding: 0 5px; border-radius: 8px;
  background: #f1f5f9; color: #64748b;
  font-size: 10px; font-weight: 800;
  font-family: ui-monospace, monospace;
}
.output-tabs .tab.active .tab-count {
  background: var(--blue-soft); color: var(--blue-deep);
}
.output-tab-pane { padding-top: 12px; animation: pane-in 0.25s ease; }
.output-tab-pane[hidden] { display: none; }
@keyframes pane-in {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── SSE 流 (tab 切换后的内容, 已无独立 head) ────────────── */
.sse-stream-body {
  background: #0F172A;
  border-radius: 8px;
  max-height: 280px;
  overflow-y: auto;
  padding: 10px 14px;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 10.5px;
  line-height: 1.6;
  color: #CBD5E1;
  border: 1px solid #1E293B;
}
.sse-line {
  display: flex; gap: 8px;
  padding: 1px 0;
  white-space: nowrap;
}
.sse-line .sse-t { color: #64748B; min-width: 56px; }
.sse-line .sse-type {
  color: #38BDF8;
  font-weight: 700;
  min-width: 86px;
}
.sse-line .sse-type.t-agent_msg { color: #FBBF24; }
.sse-line .sse-type.t-stage     { color: #A78BFA; }
.sse-line .sse-type.t-chunk     { color: #94A3B8; }
.sse-line .sse-type.t-sympy     { color: #34D399; }
.sse-line .sse-type.t-recommend { color: #F472B6; }
.sse-line .sse-type.t-done      { color: #22C55E; font-weight: 800; }
.sse-line .sse-type.t-ocr_line  { color: #60A5FA; }
.sse-line .sse-payload {
  color: #E2E8F0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sse-line .sse-payload .ok { color: #22C55E; }
.sse-line .sse-payload .fb { color: #F59E0B; }

.qno {
  display: inline-flex; align-items: center; gap: 8px;
  font-weight: 800; font-size: 13px;
  background: var(--yellow-soft); color: #B98200;
  padding: 4px 10px; border-radius: 6px;
  margin-bottom: 12px;
}
.qno .marks { color: var(--ink-muted); font-weight: 600; }
.qtext { color: var(--ink); margin-bottom: 18px; line-height: 1.65; }
.qtext strong { color: var(--blue-deep); }

.section-mini-label {
  font-size: 11px; font-weight: 800; color: var(--ink-muted);
  text-transform: uppercase; letter-spacing: 0.08em;
  margin: 18px 0 8px;
  display: flex; align-items: center; gap: 6px;
}
.section-mini-label .ic { font-size: 14px; }

.working {
  font-family: ui-monospace, "SF Mono", "Menlo", monospace;
  font-size: 13px; color: var(--ink);
  background: var(--bg-soft);
  border: 1px dashed var(--line-strong);
  border-radius: 10px;
  padding: 14px 16px;
  white-space: pre-wrap; line-height: 1.85;
}
.working .err-mark {
  background: var(--red-soft); color: var(--red);
  padding: 1px 6px; border-radius: 4px;
  font-weight: 700;
}
.answer {
  margin-top: 14px;
  padding: 10px 14px;
  background: var(--red-soft);
  border-radius: 8px;
  font-weight: 700;
  display: flex; align-items: center; gap: 8px;
  font-size: 14px;
}
.answer .ic { color: var(--red); font-size: 16px; }
.answer .ans-text { color: var(--ink); }

.verdict-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; }
.verdict {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: 999px;
  font-size: 12.5px; font-weight: 800;
}
.verdict.wrong { background: var(--red-soft); color: var(--red); }
.verdict .ic { font-size: 14px; }
.marks-info { font-size: 13px; color: var(--ink-muted); font-weight: 600; }

.feedback-block {
  margin-top: 18px;
  padding: 14px 16px;
  border-radius: 10px;
  border-left: 4px solid;
}
.feedback-block.error { background: var(--red-soft); border-color: var(--red); }
.feedback-block.gap { background: var(--yellow-soft); border-color: var(--yellow); }
.feedback-block.action { background: var(--green-soft); border-color: var(--green); }
.feedback-block h5 {
  font-size: 13px; font-weight: 800;
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 6px;
}
.feedback-block.error h5 { color: var(--red); }
.feedback-block.gap h5 { color: #B98200; }
.feedback-block.action h5 { color: var(--green); }
.feedback-block p { font-size: 13.5px; color: var(--ink); line-height: 1.65; }
.feedback-block code {
  font-family: ui-monospace, monospace; font-size: 12px;
  background: rgba(0,0,0,0.06); padding: 1px 5px; border-radius: 4px;
}

.sympy-check {
  margin-top: 16px;
  background: #fff;
  border: 2px solid var(--green);
  border-radius: 10px;
  padding: 12px 16px;
  display: flex; align-items: center; gap: 12px;
  font-family: ui-monospace, monospace; font-size: 12.5px;
}
.sympy-check .check-ic {
  width: 28px; height: 28px;
  background: var(--green); color: #fff;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 800;
  flex-shrink: 0;
}
.sympy-check .check-text { color: var(--ink); }
.sympy-check b { color: var(--green); }

/* ── 交互式批改按钮 + 流式渲染 ───────────────────────── */
.grade-btn {
  background: linear-gradient(180deg, var(--blue), var(--blue-deep));
  color: #fff;
  border: none;
  padding: 14px 32px;
  border-radius: 12px;
  font-size: 15px; font-weight: 800;
  cursor: pointer;
  box-shadow: var(--shadow-blue);
  transition: transform 0.12s, box-shadow 0.15s;
  font-family: inherit;
}
.grade-btn:hover { transform: translateY(-2px); box-shadow: 0 12px 28px rgba(43, 125, 255, 0.42); }
.grade-btn:active { transform: translateY(0); }
.grade-btn:disabled { opacity: 0.55; cursor: not-allowed; transform: none; box-shadow: none; }

.grade-loading-row {
  background: var(--blue-soft);
  border: 1px solid var(--blue);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex; align-items: center; gap: 14px;
  margin-bottom: 14px;
}
.grade-spinner {
  width: 22px; height: 22px;
  border: 3px solid var(--blue-soft);
  border-top-color: var(--blue);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 流式输出区 — 跟原静态版排版一致 */
#grade-output { font-size: 14.5px; line-height: 1.65; }
#grade-output .v-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; }
#grade-output .v-tag {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: 999px;
  font-size: 12.5px; font-weight: 800;
  background: var(--red-soft); color: var(--red);
}
#grade-output .v-marks { font-size: 13px; color: var(--ink-muted); font-weight: 600; }

#grade-output .gb {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 10px;
  border-left: 4px solid;
}
#grade-output .gb.error { background: var(--red-soft); border-color: var(--red); }
#grade-output .gb.gap { background: var(--yellow-soft); border-color: var(--yellow); }
#grade-output .gb.action { background: var(--green-soft); border-color: var(--green); }
#grade-output .gb h5 { font-size: 13px; font-weight: 800; margin-bottom: 6px; }
#grade-output .gb.error h5 { color: var(--red); }
#grade-output .gb.gap h5 { color: #B98200; }
#grade-output .gb.action h5 { color: var(--green); }
#grade-output .gb p { font-size: 13.5px; color: var(--ink); line-height: 1.65; }
#grade-output code {
  font-family: ui-monospace, monospace; font-size: 12px;
  background: rgba(0,0,0,0.06); padding: 1px 5px; border-radius: 4px;
}
#grade-output .typing-cursor {
  display: inline-block;
  width: 2px; height: 1em; background: var(--blue);
  vertical-align: text-bottom; margin-left: 2px;
  animation: blink 0.9s infinite;
}
@keyframes blink { 0%,49% { opacity: 1; } 50%,100% { opacity: 0; } }

#grade-sympy { margin-top: 16px; }
#grade-done {
  margin-top: 14px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #f0fdf4 0%, #fefce8 100%);
  border: 1px solid #bbf7d0;
  border-radius: 10px;
  font-size: 12px; color: #475569;
  font-family: ui-monospace, monospace;
  display: flex; gap: 14px; flex-wrap: wrap;
  align-items: center;
  animation: done-card-in 0.5s ease;
}
@keyframes done-card-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
#grade-done .done-tag {
  display: inline-flex; align-items: center; gap: 4px;
  background: var(--green); color: #fff;
  padding: 4px 10px; border-radius: 6px; font-weight: 800;
  font-size: 11.5px;
  box-shadow: 0 1px 2px rgba(0,154,124,0.3);
}
#grade-done b { color: #1f2937; font-weight: 800; }
.grade-error-box {
  margin-top: 12px;
  padding: 14px 16px;
  background: var(--red-soft);
  border: 1px solid var(--red);
  border-radius: 10px;
  font-size: 13px; color: var(--red);
}
.grade-error-box .retry-btn {
  margin-top: 10px;
  background: #fff; border: 1px solid var(--red);
  color: var(--red); padding: 6px 14px; border-radius: 6px;
  font-size: 12px; font-weight: 700; cursor: pointer;
}

/* ── Recommend 题库卡片 ─────────────────────────────── */
.reco-section {
  margin-top: 16px;
  background: linear-gradient(135deg, #FFF8E8 0%, #FFF4D6 100%);
  border: 1.5px solid var(--yellow);
  border-radius: 12px;
  padding: 16px 18px;
}
.reco-head-title {
  display: flex; align-items: baseline; justify-content: space-between;
  margin-bottom: 12px; gap: 12px; flex-wrap: wrap;
}
.reco-head-title > span:first-child {
  font-size: 14px; font-weight: 800; color: #B98200;
}
.reco-sub { font-size: 11.5px; color: var(--ink-soft); font-weight: 600; }

.reco-grid {
  display: grid; grid-template-columns: 1fr;
  gap: 10px;
}
.reco-card {
  background: #fff;
  border: 1px solid rgba(185, 130, 0, 0.18);
  border-radius: 10px;
  padding: 12px 14px;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
}
.reco-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(185, 130, 0, 0.15);
  border-color: var(--yellow);
}
.reco-head { display: flex; gap: 10px; align-items: center; margin-bottom: 6px; }
.reco-paper {
  font-family: ui-monospace, monospace;
  font-size: 12px; font-weight: 800; color: var(--blue-deep);
  background: var(--blue-soft);
  padding: 2px 8px; border-radius: 5px;
}
.reco-marks {
  font-size: 11px; font-weight: 700; color: var(--ink-soft);
  background: var(--bg-soft); padding: 1px 7px; border-radius: 4px;
}
.reco-strength { margin-left: auto; font-size: 12px; color: #F39C12; letter-spacing: 1px; }
.reco-topic { font-size: 12.5px; font-weight: 700; color: var(--ink); margin-bottom: 6px; }
.reco-summary {
  font-size: 12.5px; color: var(--ink-soft); line-height: 1.7;
  padding: 8px 10px;
  background: var(--bg-soft); border-radius: 6px;
  margin: 6px 0;
}
.reco-why {
  font-size: 11.5px; color: #6B4F00;
  background: rgba(255, 184, 0, 0.12);
  padding: 6px 10px; border-radius: 5px;
  margin-top: 8px;
}
.reco-foot {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 10px; padding-top: 8px;
  border-top: 1px dashed rgba(185, 130, 0, 0.2);
}
.reco-diff { font-size: 11px; color: var(--ink-muted); font-weight: 600; }
.reco-go {
  font-size: 12px; font-weight: 800; color: #fff;
  background: var(--orange); padding: 5px 12px; border-radius: 6px;
  text-decoration: none; transition: background 0.15s;
}
.reco-go:hover { background: var(--orange-deep); }

.demo-arrow { display: flex; align-items: center; justify-content: center; }
.demo-arrow .ar-circle {
  width: 44px; height: 44px;
  background: linear-gradient(135deg, var(--blue), var(--blue-deep));
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  box-shadow: var(--shadow-blue);
}
.demo-arrow svg { width: 20px; height: 20px; }

.demo-footnote {
  margin-top: 28px;
  font-size: 13px; color: var(--ink-soft);
  text-align: center;
}
.demo-footnote code { background: rgba(43,125,255,0.08); color: var(--blue-deep); padding: 2px 7px; border-radius: 5px; }

/* ── Compare 3 卡 ──────────────────────────────────────── */
.compare { padding: 88px 0; background: #fff; }
.compare .head-center { text-align: center; margin-bottom: 48px; }
.compare .head-center .section-label { justify-content: center; }
.compare .head-center .section-title { max-width: 720px; margin: 0 auto 14px; }
.compare .head-center .section-sub { margin: 0 auto; }

.compare-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
@media (max-width: 860px) { .compare-grid { grid-template-columns: 1fr; } }

.compare-card {
  background: #fff;
  border: 1.5px solid var(--line);
  border-radius: 20px;
  padding: 30px 26px;
  transition: transform 0.18s, box-shadow 0.18s, border-color 0.18s;
  position: relative;
  overflow: hidden;
}
.compare-card:hover { transform: translateY(-6px); box-shadow: var(--shadow-md); border-color: var(--blue-soft); }
.compare-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0;
  height: 5px;
  background: linear-gradient(90deg, var(--blue), var(--orange));
  opacity: 0; transition: opacity 0.18s;
}
.compare-card:hover::before { opacity: 1; }

.compare-card .ic-block {
  width: 56px; height: 56px;
  background: linear-gradient(135deg, var(--blue-soft), var(--blue-softer));
  border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 18px;
  font-size: 28px;
}
.compare-card h3 {
  font-size: 19px; font-weight: 800;
  margin-bottom: 12px; letter-spacing: -0.01em;
}
.compare-card .desc {
  font-size: 14px; color: var(--ink-soft);
  line-height: 1.65; margin-bottom: 18px;
}
.vs-row {
  background: var(--bg-soft);
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 8px;
  display: flex; align-items: flex-start; gap: 10px;
  font-size: 13px;
}
.vs-row.bad { background: var(--red-soft); }
.vs-row.good { background: var(--green-soft); }
.vs-tag {
  flex-shrink: 0;
  font-size: 10px; font-weight: 800;
  padding: 2px 7px; border-radius: 5px;
  letter-spacing: 0.05em;
}
.vs-tag.gpt { background: rgba(255, 71, 87, 0.15); color: var(--red); }
.vs-tag.ours { background: rgba(0, 184, 148, 0.18); color: var(--green); }
.vs-text { color: var(--ink); line-height: 1.55; }

/* ── Multi-Agent 可视化 v2 (2026-05-29 重做·5 角色流水线) ──── */
.multiagent {
  padding: 80px 0;
  background: linear-gradient(180deg, #FFFFFF 0%, #F4F7FF 50%, #FFFFFF 100%);
  border-top: 1px solid var(--line);
}
.ma-llm-note {
  display: inline-flex; align-items: center; gap: 8px;
  margin-top: 18px;
  padding: 8px 14px;
  background: #fff; border: 1px dashed var(--ink-muted);
  border-radius: 999px;
  font-size: 12.5px; color: var(--ink-soft); font-weight: 600;
}
.ma-llm-note code {
  background: #1F2937; color: #F9FAFB;
  padding: 2px 7px; border-radius: 5px;
  font-size: 11.5px; font-weight: 700;
}

/* 流水线主体 */
.ma-pipeline {
  margin-top: 40px;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0;
  position: relative;
}
.ma-node {
  background: #fff;
  border: 1.5px solid var(--line);
  border-radius: 16px;
  padding: 20px 18px;
  position: relative;
  z-index: 2;
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
  cursor: help;
  opacity: 0;
  animation: ma-fadein 0.5s ease forwards;
}
.ma-node:nth-child(1) { animation-delay: 0.0s; }
.ma-node:nth-child(2) { animation-delay: 0.4s; }
.ma-node:nth-child(3) { animation-delay: 0.8s; }
.ma-node:nth-child(4) { animation-delay: 1.2s; }
.ma-node:nth-child(5) { animation-delay: 1.6s; }
@keyframes ma-fadein {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
.ma-node:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(61,123,255,0.18);
  border-color: var(--blue);
  z-index: 5;
}
.ma-node-icon {
  width: 44px; height: 44px;
  background: linear-gradient(135deg, var(--blue-soft), #fff);
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  margin-bottom: 14px;
  border: 1px solid var(--blue-soft);
}
.ma-node-num {
  position: absolute; top: 16px; right: 16px;
  font-size: 11px; font-weight: 800;
  color: var(--ink-muted);
  background: #F0F4FA;
  padding: 2px 7px; border-radius: 5px;
}
.ma-node-name {
  font-size: 14.5px; font-weight: 800;
  color: var(--ink);
  margin-bottom: 4px;
}
.ma-node-role {
  font-size: 11.5px; color: var(--blue-deep);
  background: var(--blue-soft);
  padding: 2px 7px; border-radius: 4px;
  font-weight: 700;
  display: inline-block;
  margin-bottom: 10px;
}
.ma-node-desc {
  font-size: 12.5px; line-height: 1.55;
  color: var(--ink-soft);
  font-weight: 500;
}
.ma-node-out {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
  font-size: 11.5px; color: var(--ink-muted);
}
.ma-node-out strong { color: var(--ink); font-weight: 700; }

/* 节点之间的连接箭头 (CSS 实现, 桌面端) */
.ma-pipeline > .ma-node:not(:last-child)::after {
  content: '→';
  position: absolute;
  right: -16px; top: 50%;
  transform: translateY(-50%);
  font-size: 22px; font-weight: 800;
  color: var(--blue);
  z-index: 1;
}

/* Hover tooltip 详情 */
.ma-node-tip {
  visibility: hidden; opacity: 0;
  position: absolute;
  bottom: calc(100% + 12px); left: 50%;
  transform: translateX(-50%);
  width: 280px;
  background: #1F2937; color: #F9FAFB;
  padding: 14px 16px;
  border-radius: 12px;
  font-size: 12.5px; line-height: 1.6;
  font-weight: 500;
  z-index: 10;
  text-align: left;
  box-shadow: 0 12px 32px rgba(0,0,0,0.25);
  transition: opacity 0.2s, visibility 0.2s;
  pointer-events: none;
}
.ma-node-tip::after {
  content: ''; position: absolute;
  top: 100%; left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: #1F2937;
}
.ma-node-tip strong { color: #FBBF24; font-weight: 700; }
.ma-node-tip code {
  background: rgba(255,255,255,0.1);
  padding: 1px 5px; border-radius: 4px;
  font-size: 11.5px;
}
.ma-node:hover .ma-node-tip { visibility: visible; opacity: 1; }

/* 最终汇总 */
.ma-final-card {
  margin-top: 32px;
  padding: 22px 26px;
  background: linear-gradient(135deg, #FFF7EF 0%, #FFFFFF 60%);
  border: 1.5px solid #FFB57A;
  border-radius: 16px;
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 16px;
}
.ma-final-q { font-size: 13px; color: var(--ink-muted); font-weight: 600; margin-bottom: 4px; }
.ma-final-a { font-size: 16px; font-weight: 800; color: var(--ink); }
.ma-final-a code {
  background: var(--orange-soft); color: var(--orange-deep);
  padding: 2px 7px; border-radius: 5px; font-size: 14px;
}

/* 为什么这么设计 */
.ma-why {
  margin-top: 36px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
}
.ma-why-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 18px 20px;
}
.ma-why-card h4 {
  font-size: 14px; font-weight: 800; color: var(--ink);
  margin-bottom: 8px;
}
.ma-why-card p {
  font-size: 12.5px; line-height: 1.65; color: var(--ink-soft);
  font-weight: 500;
}
.ma-why-card .ma-q {
  display: inline-block;
  font-size: 11px; font-weight: 800;
  color: var(--orange-deep);
  background: var(--orange-soft);
  padding: 2px 8px; border-radius: 6px;
  margin-bottom: 8px;
}

/* 移动端 · 流水线变垂直 */
@media (max-width: 900px) {
  .ma-pipeline { grid-template-columns: 1fr; gap: 14px; }
  .ma-pipeline > .ma-node:not(:last-child)::after {
    content: '↓';
    right: 50%; top: 100%;
    transform: translate(50%, -8px);
    font-size: 24px;
  }
  .ma-node-tip {
    position: static; transform: none; width: 100%;
    visibility: visible; opacity: 1;
    margin-top: 10px;
    background: #F0F4FA; color: var(--ink);
  }
  .ma-node-tip::after { display: none; }
  .ma-node-tip strong { color: var(--orange-deep); }
  .ma-node-tip code { background: #fff; color: var(--ink); }
  .ma-why { grid-template-columns: 1fr; gap: 12px; }
}

/* ── How (3 步) ───────────────────────────────────────── */
.how {
  padding: 80px 0;
  background: var(--blue-softer);
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.how .head-center { text-align: center; margin-bottom: 48px; }
.how .head-center .section-label { justify-content: center; }

.how-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
@media (max-width: 800px) { .how-grid { grid-template-columns: 1fr; } }

.how-step {
  background: #fff;
  border-radius: 20px;
  padding: 32px 26px;
  position: relative;
  border: 1.5px solid var(--line);
  transition: transform 0.18s, box-shadow 0.18s;
}
.how-step:hover { transform: translateY(-4px); box-shadow: var(--shadow-md); }

.step-num-circle {
  width: 48px; height: 48px;
  border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: 800; color: #fff;
  margin-bottom: 18px;
  box-shadow: var(--shadow-sm);
}
.how-step:nth-child(1) .step-num-circle { background: linear-gradient(135deg, var(--blue), var(--blue-deep)); }
.how-step:nth-child(2) .step-num-circle { background: linear-gradient(135deg, var(--orange), var(--orange-deep)); }
.how-step:nth-child(3) .step-num-circle { background: linear-gradient(135deg, var(--green), #009A7C); }

.step-emoji {
  font-size: 36px; margin-bottom: 12px; line-height: 1;
}
.how-step h4 {
  font-size: 18px; font-weight: 800;
  margin-bottom: 8px; letter-spacing: -0.01em;
}
.how-step p { font-size: 14px; color: var(--ink-soft); line-height: 1.65; }
.how-step .duration {
  display: inline-flex; align-items: center; gap: 5px;
  margin-top: 14px;
  font-size: 12px; font-weight: 700;
  background: var(--blue-soft); color: var(--blue-deep);
  padding: 4px 10px; border-radius: 6px;
}

/* ── Tech 折叠 ──────────────────────────────────────────── */
.tech { padding: 72px 0; background: #fff; }
.tech-wrap details {
  border: 1.5px solid var(--line);
  border-radius: 18px;
  transition: border-color 0.18s, box-shadow 0.18s;
}
.tech-wrap details[open] { border-color: var(--blue); box-shadow: var(--shadow-md); }
.tech-wrap summary {
  padding: 24px 28px;
  cursor: pointer; list-style: none;
  display: flex; align-items: center; gap: 16px;
  user-select: none;
}
.tech-wrap summary::-webkit-details-marker { display: none; }
.tech-wrap summary .ic-tech {
  width: 44px; height: 44px;
  background: linear-gradient(135deg, var(--blue-soft), var(--blue-softer));
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}
.tech-wrap summary .label-block { flex: 1; }
.tech-wrap summary .l-top { font-size: 16px; font-weight: 800; }
.tech-wrap summary .l-sub { font-size: 13px; color: var(--ink-muted); margin-top: 3px; }
.tech-wrap summary .toggle-arrow {
  color: var(--ink-muted); transition: transform 0.2s;
  font-size: 16px;
}
.tech-wrap details[open] summary .toggle-arrow { transform: rotate(180deg); color: var(--blue); }
.tech-body { padding: 0 28px 24px; }

.tech-grid {
  display: grid; grid-template-columns: repeat(2, 1fr);
  gap: 16px; margin-top: 8px;
}
@media (max-width: 760px) { .tech-grid { grid-template-columns: 1fr; } }
.tech-block {
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 18px 20px;
}
.tech-block h5 {
  font-size: 14px; font-weight: 800;
  margin-bottom: 6px;
  display: flex; align-items: center; gap: 8px;
}
.tech-block h5 .pill-small {
  display: inline-block;
  background: var(--blue-soft); color: var(--blue-deep);
  font-size: 10px; padding: 2px 7px; border-radius: 4px;
  font-weight: 700; letter-spacing: 0.04em;
}
.tech-block p { font-size: 13px; color: var(--ink-soft); line-height: 1.65; }
.tech-block code {
  font-family: ui-monospace, monospace; font-size: 11.5px;
  background: rgba(43, 125, 255, 0.08); color: var(--blue-deep);
  padding: 1px 5px; border-radius: 4px;
}

/* ── Final CTA ─────────────────────────────────────────── */
.final-cta {
  padding: 96px 0;
  text-align: center;
  background: linear-gradient(135deg, #FAFBFD 0%, var(--blue-softer) 50%, #FFF8E8 100%);
}
.final-cta h2 {
  font-size: clamp(28px, 4vw, 42px);
  font-weight: 800; letter-spacing: -0.02em;
  margin-bottom: 16px; line-height: 1.2;
}
.final-cta h2 .accent { color: var(--blue); }
.final-cta .sub { color: var(--ink-soft); margin-bottom: 36px; font-size: 16px; }
.final-cta .cta-row { justify-content: center; }

/* ── Today timeline (P0 新增 2026-05-29) ─────────────────── */
.today {
  padding: 80px 0;
  background: linear-gradient(180deg, #FFFFFF 0%, #F7FAFF 60%, #FFFFFF 100%);
  border-top: 1px solid var(--line);
}
.today-timeline {
  display: flex; flex-direction: column;
  gap: 24px;
  margin-top: 32px;
}
.today-item { position: relative; }
.today-time {
  display: inline-block;
  font-size: 12.5px; font-weight: 700;
  color: var(--ink-muted);
  background: #fff;
  padding: 6px 12px; border-radius: 12px;
  border: 1px solid var(--line);
  margin-bottom: 10px;
  letter-spacing: 0.02em;
}
.today-card {
  background: #fff;
  border: 1.5px solid var(--line);
  border-radius: 20px;
  padding: 22px 24px;
  box-shadow: var(--shadow-sm);
  transition: transform 0.18s, box-shadow 0.18s;
}
.today-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-md); }
.today-card-highlight {
  border-color: #FFB57A;
  background: linear-gradient(135deg, #FFF7EF 0%, #FFFFFF 60%);
}
.today-card-head {
  display: flex; align-items: center; gap: 14px;
  margin-bottom: 18px;
  padding-bottom: 16px;
  border-bottom: 1px dashed var(--line);
}
.today-student-avatar {
  width: 44px; height: 44px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 800;
  color: #fff; flex-shrink: 0;
}
.today-student-name {
  font-size: 15px; font-weight: 800;
  color: var(--ink);
}
.today-student-tag {
  display: inline-block;
  font-size: 11.5px; font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--blue-soft);
  color: var(--blue-deep);
  margin-left: 6px;
  vertical-align: middle;
}
.today-student-sub {
  font-size: 12.5px;
  color: var(--ink-muted);
  margin-top: 3px;
}
.today-trio {
  display: grid;
  grid-template-columns: 1fr 1.4fr 1fr;
  gap: 18px;
}
.today-col {
  background: #F9FBFF;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px 16px;
}
.today-col-label {
  font-size: 11.5px; font-weight: 800;
  color: var(--ink-muted);
  letter-spacing: 0.04em;
  margin-bottom: 10px;
  text-transform: uppercase;
}
.today-thumb-stub {
  background: linear-gradient(135deg, #EFF3FA, #F7F9FE);
  border: 1px dashed #B8C5DC;
  border-radius: 10px;
  padding: 18px 12px;
  text-align: center;
  font-size: 13px; font-weight: 600;
  color: var(--ink-soft);
  line-height: 1.5;
  min-height: 80px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.today-feedback, .today-reaction {
  font-size: 13px; line-height: 1.6;
  color: var(--ink);
  font-weight: 500;
}
.today-feedback code {
  background: #FFF3E8;
  padding: 1px 5px; border-radius: 4px;
  font-size: 11.5px; color: #D44E0D;
}
.today-reaction-meta {
  display: block;
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--ink-muted);
  font-weight: 600;
  font-style: italic;
}
.today-audio-stub {
  display: flex; flex-direction: column; gap: 8px;
  background: linear-gradient(135deg, #E8F8F3, #F7FCFA);
  border: 1px solid #00B894;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 12.5px;
  color: var(--ink);
  line-height: 1.5;
  min-height: 80px;
}
.today-audio-play {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px;
  background: #009A7C;
  color: #fff;
  border-radius: 50%;
  font-size: 14px;
}
.today-audio-text { font-weight: 600; }
.today-audio-time {
  font-size: 11px;
  color: var(--ink-muted);
  font-weight: 700;
  letter-spacing: 0.02em;
}
.today-footnote {
  margin-top: 28px;
  padding: 18px 20px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  font-size: 13px;
  color: var(--ink-soft);
  line-height: 1.7;
  text-align: center;
}
.today-tag {
  display: inline-block;
  font-size: 11.5px; font-weight: 800;
  padding: 3px 10px; border-radius: 6px;
  background: #E8F8F3; color: #009A7C;
  margin-right: 8px;
}

/* ── Pricing (P2 新增 2026-05-29) ────────────────────── */
.pricing {
  padding: 80px 0;
  background: #fff;
  border-top: 1px solid var(--line);
}
.pricing-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 22px;
  margin-top: 36px;
}
.pricing-card {
  background: #fff;
  border: 1.5px solid var(--line);
  border-radius: 20px;
  padding: 28px 26px;
  box-shadow: var(--shadow-sm);
  display: flex; flex-direction: column;
  transition: transform 0.18s, box-shadow 0.18s;
}
.pricing-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-md); }
.pricing-card-mid {
  border-color: var(--blue);
  background: linear-gradient(135deg, #F7FAFF 0%, #FFFFFF 60%);
  position: relative;
}
.pricing-card-mid::before {
  content: '推荐';
  position: absolute;
  top: -10px; right: 22px;
  background: var(--blue-deep); color: #fff;
  font-size: 11px; font-weight: 800;
  padding: 3px 10px; border-radius: 6px;
  letter-spacing: 0.06em;
}
.pricing-tag {
  display: inline-flex; align-items: center;
  font-size: 11.5px; font-weight: 800;
  padding: 4px 10px; border-radius: 6px;
  letter-spacing: 0.04em;
  margin-bottom: 14px;
  align-self: flex-start;
}
.pricing-price {
  font-size: 38px; font-weight: 800;
  color: var(--ink);
  letter-spacing: -0.02em;
  margin-bottom: 18px;
}
.pricing-unit {
  font-size: 14px; font-weight: 600;
  color: var(--ink-soft);
  margin-left: 4px;
}
.pricing-feat {
  list-style: none; padding: 0; margin: 0 0 22px 0;
  flex: 1;
}
.pricing-feat li {
  font-size: 13.5px; color: var(--ink-soft);
  padding: 6px 0;
  border-bottom: 1px dashed #F0F2F5;
  font-weight: 500;
}
.pricing-cta, .pricing-cta-mid {
  display: inline-block;
  padding: 12px 20px;
  border-radius: 12px;
  text-align: center;
  font-size: 14px; font-weight: 700;
  text-decoration: none;
  transition: background 0.18s;
}
.pricing-cta {
  background: #fff;
  color: var(--ink);
  border: 1.5px solid var(--line);
}
.pricing-cta:hover { background: #F7FAFF; border-color: var(--blue); }
.pricing-cta-mid {
  background: var(--orange);
  color: #fff;
  border: 1.5px solid var(--orange);
}
.pricing-cta-mid:hover { background: var(--orange-deep); }

/* ── Sticky CTA · 移动端浮动按钮 (P0 新增 2026-05-29) ───── */
.sticky-cta {
  display: none;
  position: fixed;
  bottom: 16px; left: 16px; right: 16px;
  z-index: 999;
  background: var(--orange);
  color: #fff;
  padding: 14px 22px;
  border-radius: 999px;
  text-align: center;
  font-size: 15px; font-weight: 800;
  text-decoration: none;
  box-shadow: 0 6px 24px rgba(255, 122, 51, 0.45);
  letter-spacing: 0.02em;
}
.sticky-cta:hover { background: var(--orange-deep); }

@media (max-width: 768px) {
  .sticky-cta { display: block; }
  body { padding-bottom: 70px; }
  .today-trio { grid-template-columns: 1fr; gap: 12px; }
  .pricing-grid { grid-template-columns: 1fr; }
}

/* ── Footer ────────────────────────────────────────────── */
footer {
  background: #fff;
  border-top: 1px solid var(--line);
  padding: 32px 0;
  font-size: 13px; color: var(--ink-muted);
}
footer .wrap { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
footer .brand-foot { display: flex; align-items: center; gap: 10px; font-weight: 700; color: var(--ink-soft); }
footer .brand-foot .brand-logo { width: 24px; height: 24px; border-radius: 6px; font-size: 13px; }
footer .spacer { flex: 1; }
footer a { color: var(--ink-soft); font-weight: 600; transition: color 0.15s; }
footer a:hover { color: var(--blue); }

</style>
</head>
<body>

<nav class="nav">
  <div class="wrap">
    <div class="brand">
      <div class="brand-logo">A</div>
      <span>A-Level 助手</span>
      <span class="pill">内测中</span>
    </div>
    <div class="spacer"></div>
    <a class="nav-link" href="#demo">实例</a>
    <a class="nav-link" href="#voices">谁在用</a>
    <a class="nav-link" href="#how">怎么用</a>
    <a class="nav-link" href="#tech">技术细节</a>
    <a class="nav-link" href="/alevel/pitch" style="color:var(--orange-deep);font-weight:700">关于产品 →</a>
    <a class="cta-nav" href="/alevel/">立即试用</a>
  </div>
</nav>

<section class="hero">
  <div class="wrap">
    <div class="eyebrow"><span class="dot"></span>专为 A-Level 数学打造</div>
    <h1>拍一页作业, <span class="accent">3 分钟</span><br>给出 <span class="highlight">每道题</span>的逐步反馈</h1>
    <p class="lede">学生手写答案识别 + 逐题错点定位 + 知识缺口分析 + 下一步动作建议. 不是简单对错, 也不是 ChatGPT 一段空话.</p>

    <div class="cta-row">
      <a class="btn-primary" href="/alevel/">📷 上传你的一页作业 <span class="arrow">→</span></a>
      <a class="btn-secondary" href="#demo">先看真实例子</a>
      <a class="btn-secondary" href="#multiagent" style="color:var(--blue-deep);border-color:var(--blue-soft)">🤖 看背后 5 个 agent 怎么协作 →</a>
    </div>

    <div class="subjects">
      <span class="subj-chip"><span class="ico">📐</span>Pure Math (P1-P3)</span>
      <span class="subj-chip"><span class="ico">📊</span>Statistics (S1-S2)</span>
      <span class="subj-chip"><span class="ico">⚙️</span>Mechanics (M1-M2)</span>
      <span class="subj-chip"><span class="ico">🎯</span>Cambridge 9709</span>
    </div>

    <div class="hero-stats">
      <div class="stat-card">
        <div class="stat-num"><span class="orange">20</span><span class="unit">分</span><span class="unit" style="color:#bbb;margin:0 4px">→</span><span class="accent">3</span><span class="unit">分</span></div>
        <div class="stat-label">老师手改一页作业要 20 分钟，AI 给到 3 分钟</div>
      </div>
      <div class="stat-card">
        <div class="stat-num"><span class="accent">5</span><span class="unit">个模型</span></div>
        <div class="stat-label">同时跑 5 个不同的模型互相对一下答案</div>
      </div>
      <div class="stat-card">
        <div class="stat-num"><span class="green-num">12.5</span><span class="unit" style="color:#bbb">→</span><span class="green-num">0</span><span class="unit">%</span></div>
        <div class="stat-label">能算的题让 SymPy 跑一遍，模型算错率压到 0</div>
      </div>
      <div class="stat-card">
        <div class="stat-num"><span class="accent">数十</span><span class="unit">名</span></div>
        <div class="stat-label">武汉几所国际学校的学生，互相介绍着在用</div>
      </div>
    </div>

    <!-- 产品 UI mockup -->
    <div class="hero-mockup">
      <div class="mock-browser">
        <div class="mock-bar">
          <div class="mock-dots">
            <span style="background:#FF5F57"></span>
            <span style="background:#FEBC2E"></span>
            <span style="background:#28C840"></span>
          </div>
          <div class="mock-url">🔒 offercome2026.com/alevel</div>
          <div style="width:60px"></div>
        </div>
        <div class="mock-content">
          <div class="mock-app-head">
            <div>
              <div class="mock-app-title">A-Level 作业助手</div>
              <div class="mock-app-sub">上传整页作业图片, 系统自动切题, 调用 AI 批改并生成逐题反馈</div>
            </div>
            <div class="mock-user-chip">👤 个人</div>
          </div>
          <div class="mock-tabs">
            <span class="mock-tab active">作业批改</span>
            <span class="mock-tab">历史记录</span>
            <span class="mock-tab">总结</span>
            <span class="mock-tab">刷题</span>
          </div>
          <div class="mock-upload">
            <div class="mock-upload-icon">📷</div>
            <div class="mock-upload-title">点击或拖拽上传一页作业</div>
            <div class="mock-upload-sub">JPG / PNG / WebP / HEIC · 单张 ≤ 20 MB · 最多 16 张</div>
            <div class="mock-upload-actions">
              <span class="mock-btn-primary">📷 拍照上传</span>
              <span class="mock-btn-secondary">🖼️ 选择图片</span>
            </div>
          </div>
          <div class="mock-pdf">
            <span class="mock-pdf-ic">📄</span>
            <div>
              <div class="mock-pdf-title">上传 PDF 文件</div>
              <div class="mock-pdf-sub">PDF 每页自动转换为图片进行批改 · 最大 40 MB</div>
            </div>
          </div>
        </div>
      </div>
      <!-- 浮动批改样例气泡 -->
      <div class="mock-float-bubble">
        <div class="float-head">
          <span class="float-tag">✓ 已批改</span>
          <span class="float-time">2 分 47 秒</span>
        </div>
        <div class="float-title">Question 1(d) · 3 marks</div>
        <div class="float-body">第 6 行符号错位 · <code>-3x+4=3x+5</code> 应是 <code>-6x=1</code></div>
        <div class="float-foot"><span class="float-check">SymPy 实算: T=(4, 17/4)</span></div>
      </div>
    </div>
  </div>
</section>

<section class="demo" id="demo">
  <div class="wrap">
    <div class="section-label">真实例子</div>
    <h2 class="section-title">学生手写的圆切线题, 系统是这么批的 ↓</h2>
    <p class="section-sub">下面是来自 Cambridge 9709 (A Level Pure Math) Coordinate Geometry 单元的真实学生作业. 学生在 Q1(d) 算出 <code>T:(-7/8, 2)</code>, 系统识别了完整 working steps, 准确定位到联立方程时的符号错误.</p>

    <div class="demo-grid">
      <!-- LEFT · 真实作业图片 (导入) -->
      <div class="demo-card input-card">
        <div class="head">
          <span class="badge">INPUT · 学生作业图片</span>
          <span style="color:var(--ink-muted);font-weight:600" id="left-status">已导入 · sample.jpg</span>
        </div>
        <div class="body">
          <div class="img-import-wrap">
            <div class="img-frame">
              <img class="demo-img" src="/alevel/static/demo-input.jpg" data-fallback="/static/demo-input.jpg" alt="学生作业 · A-Level Pure Math Q1d 圆切线" id="demo-img" onload="if(this.naturalWidth===0&&this.dataset.fallback){var f=this.dataset.fallback;delete this.dataset.fallback;this.src=f}" onerror="if(this.dataset.fallback){var f=this.dataset.fallback;delete this.dataset.fallback;this.src=f}" />
              <!-- OCR 切题时动态绘制 bbox -->
              <div id="img-overlay"></div>
            </div>
            <div class="img-meta">
              <span>📄 sample.jpg · 156 KB · 1488×837</span>
              <a class="img-replace" href="/alevel/" title="去主应用上传你自己的作业">换一张 →</a>
            </div>
          </div>

          <div class="section-mini-label" style="margin-top:18px">
            <span class="ic">📋</span> 题目 (印刷文字 · segmenter 提取)
          </div>
          <div class="qtext math-render" style="font-size:13.5px;color:var(--ink);line-height:1.8;background:var(--bg-soft);padding:14px 16px;border-radius:8px">
            <strong style="color:var(--blue-deep)">Q1(d) · 3 marks</strong> · The point $P(1, 2)$ lies on the circle $x^2 + y^2 - 8x + 4y - 5 = 0$, and $Q$ also lies on the circle with $PQ$ parallel to the $x$-axis. The tangents at $P$ and $Q$ meet at $T$. <strong>Find the coordinates of $T$.</strong>
          </div>

          <div class="section-mini-label" style="margin-top:14px">
            <span class="ic">✏️</span> 学生手写 working (OCR 识别)
            <span id="ocr-counter" style="margin-left:auto;font-size:10px;color:var(--ink-muted);font-weight:600">0 / 11 行</span>
          </div>
          <div class="working" id="ocr-output" style="min-height:60px"><span style="color:var(--ink-muted);font-style:italic">点击右侧"开始批改" → 这里会流式打印 OCR 识别结果</span></div>
        </div>
      </div>

      <div class="demo-arrow">
        <div class="ar-circle" id="demo-progress-ring">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
        </div>
      </div>

      <!-- RIGHT · 批改输出 (可交互, 真实调 codex) -->
      <div class="demo-card output-card" id="grade-card">
        <div class="head">
          <span class="badge">OUTPUT · 系统返回</span>
          <span id="grade-status" style="color:var(--ink-muted);font-weight:600">等待开始</span>
        </div>
        <div class="body">

          <!-- 初始状态: 按钮 + 引导 -->
          <div id="grade-init">
            <div style="text-align:center;padding:24px 12px 18px">
              <div style="font-size:48px;margin-bottom:14px">🤖</div>
              <div style="font-weight:800;font-size:16px;margin-bottom:8px">真实调用 GPT-5.5 (via ChatGPT OAuth)</div>
              <div style="font-size:13px;color:var(--ink-soft);margin-bottom:20px;line-height:1.65">
                点击下方按钮, 后端把左侧学生 working 真实喂给 LLM 批改,<br>
                通过 SSE 流式推回 — 你能看见每一个字是 AI 生成的.
              </div>
              <button id="grade-start-btn" class="grade-btn">
                <span>▶ 点击开始批改</span>
                <span style="font-size:11px;font-weight:600;opacity:0.85;display:block;margin-top:2px">通常 8-30 秒返回</span>
              </button>
              <div style="font-size:11px;color:var(--ink-muted);margin-top:18px;font-family:ui-monospace,monospace">
                model=gpt-5.5 · provider=codex-oauth · base=:18891
              </div>
            </div>
          </div>

          <!-- 进度状态: 调用中 -->
          <div id="grade-loading" style="display:none">
            <div class="grade-loading-row">
              <div class="grade-spinner"></div>
              <div>
                <div style="font-weight:700;font-size:13.5px" id="grade-loading-stage">正在唤起 codex shim…</div>
                <div style="font-size:11.5px;color:var(--ink-muted);margin-top:2px" id="grade-loading-meta">model=gpt-5.5 · 等待首个 token</div>
              </div>
              <div style="margin-left:auto;font-family:ui-monospace,monospace;font-size:12px;color:var(--blue-deep);font-weight:700" id="grade-timer">0.0s</div>
            </div>
          </div>

          <!-- 流式渲染输出 -->
          <div id="grade-output" style="display:none"></div>

          <!-- SymPy 结果 -->
          <div id="grade-sympy" style="display:none"></div>

          <!-- 完成 footer -->
          <div id="grade-done" style="display:none"></div>

          <!-- 错误 -->
          <div id="grade-error" style="display:none" class="grade-error-box"></div>
        </div>
      </div>
    </div>

    <div class="demo-footnote">
      ↑ 真实学生题目 · 数据源: <code>9709 · Coordinate Geometry · Lesson 2</code>
    </div>
  </div>
</section>

<section class="compare">
  <div class="wrap">
    <div class="head-center">
      <div class="section-label">和 ChatGPT 比</div>
      <h2 class="section-title">差在哪三件事</h2>
      <p class="section-sub">同一道圆切线题给两边，看一下输出有什么不一样。</p>
    </div>

    <div class="compare-grid">
      <div class="compare-card">
        <div class="ic-block">✏️</div>
        <h3>看你怎么算的，不是给你重做一遍</h3>
        <p class="desc">你把题目拍给 ChatGPT，它会重新算一遍标准答案给你看。但学生不是不知道答案——他自己也算了，他需要的是有人告诉他"你在第几步开始错的"。我们就是把学生写的每一步先识别出来，再对照着指出哪步崩了。</p>
        <div class="vs-row bad">
          <span class="vs-tag gpt">ChatGPT 这么回</span>
          <span class="vs-text">"答案是 T = (4, 17/4)"</span>
        </div>
        <div class="vs-row good">
          <span class="vs-tag ours">我们这么回</span>
          <span class="vs-text">"你第 6 行符号错位了，<code>-3x+4=3x+5</code> 这步应该化成 <code>-6x=1</code>"</span>
        </div>
      </div>

      <div class="compare-card">
        <div class="ic-block">🧮</div>
        <h3>能算的题，让计算机真的算一遍</h3>
        <p class="desc">模型也会算错。它会很自信地说一句"看起来 x = -1/6 应该是对的"，其实它没真算，只是顺着学生的思路看着合理。所以凡是能用 SymPy 解的步骤——求导、解方程、积分——我们都让 SymPy 真跑一遍。模型说的不算，SymPy 说的算。</p>
        <div class="vs-row bad">
          <span class="vs-tag gpt">ChatGPT 这么回</span>
          <span class="vs-text">"看起来 x = -1/6 应该是对的"（其实它没真算）</span>
        </div>
        <div class="vs-row good">
          <span class="vs-tag ours">我们这么回</span>
          <span class="vs-text">让 SymPy 解出来 <code>x = 1/3</code>，直接给学生那行标红</span>
        </div>
      </div>

      <div class="compare-card">
        <div class="ic-block">🧠</div>
        <h3>它会记得你每次都在哪儿摔</h3>
        <p class="desc">每个学生在系统里有自己的"错题脑"。第三次又在同一个知识点摔——比如链式法则——它就不直接给答案了，反问你"上次你是卡在哪一步"，逼你自己想。今天用、下周再用，它都记得你之前栽过哪些。</p>
        <div class="vs-row bad">
          <span class="vs-tag gpt">ChatGPT 这么回</span>
          <span class="vs-text">每次都是新会话，不知道你之前错过什么</span>
        </div>
        <div class="vs-row good">
          <span class="vs-tag ours">我们这么回</span>
          <span class="vs-text">"链式法则你这已经是第 3 次错了，先告诉我你卡在哪一步"</span>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ───────────── Multi-Agent 流水线可视化 v2 · 5 角色协作 ─────────── -->
<section class="multiagent" id="multiagent">
  <div class="wrap">
    <div class="head-center">
      <div class="section-label">背后是怎么跑的</div>
      <h2 class="section-title">一道题 · 5 个 agent 流水接力 · 各管一段</h2>
      <p class="section-sub">不是只丢给一个 LLM 让它从头干到尾。一道题进来，按职责切成 5 段，每个 agent 一个明确角色——切题的、识别的、批改的、验算的、记历史的——前一个的产出是下一个的输入。</p>
      <div class="ma-llm-note">
        💡 五个 agent 底层用同一个 <code>GPT-5.5 (codex)</code>，只是 prompt 不同，让它扮演不同专家
      </div>
    </div>

    <!-- 5 节点流水线 -->
    <div class="ma-pipeline">
      <div class="ma-node">
        <span class="ma-node-num">01</span>
        <div class="ma-node-icon">✂️</div>
        <div class="ma-node-name">Segmenter</div>
        <span class="ma-node-role">切题专家</span>
        <p class="ma-node-desc">把整页作业拆成独立题目。识别题号边界、跨页接续。</p>
        <div class="ma-node-out"><strong>输出</strong>：4 题 Q1a~Q1d，每题独立坐标框</div>
        <div class="ma-node-tip">
          <strong>角色 prompt</strong>："你是一位试卷排版专家，找出这页里每道独立题的边界。"<br>
          <strong>典型用时</strong>：~1.5s · 视觉模型直出 bbox<br>
          <strong>对下游</strong>：把每题的图片裁切传给 OCR
        </div>
      </div>

      <div class="ma-node">
        <span class="ma-node-num">02</span>
        <div class="ma-node-icon">👁</div>
        <div class="ma-node-name">OCR Agent</div>
        <span class="ma-node-role">手写识别员</span>
        <p class="ma-node-desc">不是抓题目，是抓<em>学生写了什么</em>。一行一行还原 working steps。</p>
        <div class="ma-node-out"><strong>输出</strong>：11 行学生 working steps（含 LaTeX）</div>
        <div class="ma-node-tip">
          <strong>角色 prompt</strong>："你是一位惯于读初学者手写体的助教，按顺序还原他每一步在写什么。数学符号统一用 LaTeX。"<br>
          <strong>典型用时</strong>：~2s<br>
          <strong>对下游</strong>：把 working steps 喂给 Grader
        </div>
      </div>

      <div class="ma-node">
        <span class="ma-node-num">03</span>
        <div class="ma-node-icon">✏️</div>
        <div class="ma-node-name">Grader</div>
        <span class="ma-node-role">批改老师</span>
        <p class="ma-node-desc">读学生 working，找出第几步开始崩。给分、写反馈、定位错点。</p>
        <div class="ma-node-out"><strong>输出</strong>：扣 3 分 · "第 6 行符号错位"</div>
        <div class="ma-node-tip">
          <strong>角色 prompt</strong>："你是一位有 10 年 A-Level 经验的批改老师，对照官方 mark scheme，给分要严，反馈要具体到行。"<br>
          <strong>典型用时</strong>：~5-8s<br>
          <strong>对下游</strong>：把判断传给 Verifier 校验
        </div>
      </div>

      <div class="ma-node">
        <span class="ma-node-num">04</span>
        <div class="ma-node-icon">🧮</div>
        <div class="ma-node-name">Verifier</div>
        <span class="ma-node-role">独立审计员</span>
        <p class="ma-node-desc">不信 Grader 一面之词。把能算的步骤喂给 SymPy 真算一遍，对照打分。</p>
        <div class="ma-node-out"><strong>输出</strong>：SymPy 解出 T=(4, 17/4)，确认 Grader 判错正确</div>
        <div class="ma-node-tip">
          <strong>角色 prompt</strong>："你是一位独立审计员，不预设 Grader 是对的。能用 SymPy 算的就算，算完和 Grader 对比。"<br>
          <strong>典型用时</strong>：~0.5s（纯计算）<br>
          <strong>对下游</strong>：标 confidence·若 Grader 与 SymPy 冲突，以 SymPy 为准
        </div>
      </div>

      <div class="ma-node">
        <span class="ma-node-num">05</span>
        <div class="ma-node-icon">🧠</div>
        <div class="ma-node-name">Memory</div>
        <span class="ma-node-role">学情记录员</span>
        <p class="ma-node-desc">查这学生历史错点，决定输出风格。第三次同类错就切苏格拉底模式。</p>
        <div class="ma-node-out"><strong>输出</strong>：这是该生符号管理类错误第 2 次 · 正常反馈即可</div>
        <div class="ma-node-tip">
          <strong>角色 prompt</strong>："你是一位长期跟这个学生的私教，记得他过去栽过哪些坑。决定这次反馈是直接给答案，还是反问他。"<br>
          <strong>典型用时</strong>：~0.3s（查 memory）<br>
          <strong>对下游</strong>：决定最终反馈语气 + 更新错题脑
        </div>
      </div>
    </div>

    <div class="ma-final-card">
      <div>
        <div class="ma-final-q">5 个 agent 协作完成后的最终反馈</div>
        <div class="ma-final-a">扣 <code>3 分</code> · 第 6 行符号错位 · 正解 T = (4, 17/4) · confidence 0.95</div>
      </div>
      <div style="text-align:right">
        <div class="ma-final-q">总耗时</div>
        <div class="ma-final-a"><code>~9s</code></div>
      </div>
    </div>

    <div class="ma-why">
      <div class="ma-why-card">
        <span class="ma-q">为什么拆 5 个 agent</span>
        <h4>一个 prompt 干不了所有事</h4>
        <p>"看图 + 识手写 + 改作业 + 重新算 + 调用历史"塞一个 prompt 里，模型会顾此失彼。拆成 5 段，每段只让它做一件事，准确率明显高。</p>
      </div>
      <div class="ma-why-card">
        <span class="ma-q">为什么不换不同模型</span>
        <h4>同一个底座 · 不同角色</h4>
        <p>5 个 agent 都走同一个 codex/GPT-5.5。换不同家的模型反而引入风格不一致的麻烦。同一个模型 + 不同 prompt，输出更稳，调试也方便。</p>
      </div>
      <div class="ma-why-card">
        <span class="ma-q">谁审计谁</span>
        <h4>Verifier 是关键一环</h4>
        <p>Grader 是 LLM，会自信地说错。所以 Verifier 不听 Grader 的，独立用 SymPy 算一遍。两人冲突时以 SymPy 为准——把 LLM 的"幻觉"挡在这一步。</p>
      </div>
    </div>
  </div>
</section>

<section class="voices" id="voices">
  <div class="wrap">
    <div class="head-center">
      <div class="section-label">用户反馈</div>
      <h2 class="section-title">谁在用 · 怎么用</h2>
      <p class="section-sub">几条来自学生/老师/产品本身的真实碎片</p>
    </div>

    <div class="voices-grid">
      <!-- 老师视角 (引述老师真实痛点) -->
      <div class="voice-card t-teacher">
        <span class="voice-quote-mark">"</span>
        <span class="voice-tag">🍎 老师视角 · 痛点</span>
        <div class="voice-quote">有的老师还不会用 GPT 改, <span class="highlight">一个人的作业改 20 分钟</span>. 他们都觉得改作业特别累 — 改作业 To B 好像会特别提效.</div>
        <div class="voice-avatar-row">
          <div class="voice-avatar">
            <!-- SVG 简笔老师头像 -->
            <svg viewBox="0 0 64 64" width="36" height="36" fill="none" stroke="white" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="32" cy="22" r="9"/>
              <path d="M14 54c0-9 8-15 18-15s18 6 18 15"/>
              <!-- 学位帽 -->
              <path d="M19 14l13-5 13 5-13 5z" fill="white" stroke="white"/>
              <line x1="45" y1="14" x2="45" y2="22"/>
              <circle cx="45" cy="22" r="1.5" fill="white"/>
            </svg>
          </div>
          <div>
            <div class="voice-meta-name">武汉某国际学校 数学老师</div>
            <div class="voice-meta-sub">A-Level / IB / AP 课程</div>
          </div>
        </div>
        <div class="voice-source">📝 真实交流碎片 · 2026-04-02 内测期间产品调研</div>
      </div>

      <!-- 学生视角 -->
      <div class="voice-card t-student">
        <span class="voice-quote-mark">"</span>
        <span class="voice-tag">🎓 学生视角 · 场景</span>
        <div class="voice-quote">不懂的 ChatGPT 都会, 留学生还钱贼多. <span class="highlight">武汉的各大国际学校</span>, 数学物理经济高数这种课程都会报名 — 这一类学生最缺逐题反馈.</div>
        <div class="voice-avatar-row">
          <div class="voice-avatar">
            <!-- SVG 简笔学生头像 -->
            <svg viewBox="0 0 64 64" width="36" height="36" fill="none" stroke="white" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="32" cy="22" r="9"/>
              <path d="M14 54c0-9 8-15 18-15s18 6 18 15"/>
              <!-- 书本 -->
              <rect x="24" y="46" width="16" height="3" rx="0.5" fill="white" stroke="white"/>
              <line x1="32" y1="46" x2="32" y2="49"/>
            </svg>
          </div>
          <div>
            <div class="voice-meta-name">A-Level 内测者 · #03</div>
            <div class="voice-meta-sub">Pure Math P3 · Statistics S1 · 武汉国际部</div>
          </div>
        </div>
        <div class="voice-source">📍 真实场景描述 · 学生身份脱敏 (内测期匿名编号)</div>
      </div>

      <!-- 增长视角 -->
      <div class="voice-card t-growth">
        <span class="voice-quote-mark">"</span>
        <span class="voice-tag">📈 增长 · 自发</span>
        <div class="voice-bignum">100% 自然增长</div>
        <div class="voice-bignum-label">无投放 · 无运营 · 学生传学生</div>
        <div class="voice-quote" style="margin-top:14px;font-size:13.5px">数十名 A-Level 留学生通过<span class="highlight">学生传学生</span>方式自发使用, 学生反馈后再决定开发小程序/落地版本.</div>
        <div class="voice-source">🌱 真实运营状态 · 2026-05 内测期数据</div>
      </div>
    </div>
  </div>
</section>

<!-- ───────────── TODAY · 真实使用时间线 (P0 新增 2026-05-29) ───────────── -->
<section class="today" id="today">
  <div class="wrap">
    <div class="head-center">
      <div class="section-label">今天有人在用</div>
      <h2 class="section-title">今天的几位学生都做了什么</h2>
      <p class="section-sub">下面三条都是今天真发生的。截了几个有代表性的瞬间。</p>
    </div>

    <div class="today-timeline">
      <!-- 案例 1 · 陈同学 (作者本人 · 真实交互 · 图片) -->
      <div class="today-item">
        <div class="today-time">📅 2026-05-29 · 14:32</div>
        <div class="today-card">
          <div class="today-card-head">
            <div class="today-student-avatar" style="background:linear-gradient(135deg, #3D7BFF, #1E4FCC)">陈</div>
            <div>
              <div class="today-student-name">陈同学（作者本人）<span class="today-student-tag">📐 Pure Math P3</span></div>
              <div class="today-student-sub">提交：3 道圆切线题 · 历史第 17 次使用</div>
            </div>
          </div>
          <div class="today-trio">
            <div class="today-col">
              <div class="today-col-label">📷 学生提交</div>
              <div class="today-thumb-stub">手写圆切线<br>Q1(d) · 3 marks</div>
            </div>
            <div class="today-col">
              <div class="today-col-label">🤖 AI 反馈</div>
              <div class="today-feedback">第 6 行符号错位<br><code>-3x+4=3x+5</code> 应是 <code>-6x=1</code><br>✓ SymPy 实算 T=(4, 17/4)</div>
            </div>
            <div class="today-col">
              <div class="today-col-label">💬 学生反应</div>
              <div class="today-reaction">"啊原来是符号问题啊 我一直以为是 method 错了 笑死"<br><span class="today-reaction-meta">收进错题本了</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 案例 2 · 内测者 #07 (真实匿名 · 语音卡片) -->
      <div class="today-item">
        <div class="today-time">📅 2026-05-29 · 10:18</div>
        <div class="today-card">
          <div class="today-card-head">
            <div class="today-student-avatar" style="background:linear-gradient(135deg, #00B894, #009A7C)">07</div>
            <div>
              <div class="today-student-name">内测者 #07 <span class="today-student-tag">📊 Statistics S1</span></div>
              <div class="today-student-sub">提交：1 道二项分布题 · 历史第 4 次使用</div>
            </div>
          </div>
          <div class="today-trio">
            <div class="today-col">
              <div class="today-col-label">📷 学生提交</div>
              <div class="today-thumb-stub">P(X≥3) · Binomial<br>n=10, p=0.3</div>
            </div>
            <div class="today-col">
              <div class="today-col-label">🎙 AI 语音讲解 · 30 秒</div>
              <div class="today-audio-stub">
                <span class="today-audio-play">▶︎</span>
                <span class="today-audio-text">"你用了累积分布表 但代错了行 n=10 应该看第 11 行..."</span>
                <span class="today-audio-time">0:00 / 0:30</span>
              </div>
            </div>
            <div class="today-col">
              <div class="today-col-label">💬 学生反应</div>
              <div class="today-reaction">"语音听着清楚多了 看公式真的头大"<br><span class="today-reaction-meta">后面她默认就开语音了</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 案例 3 · 内测者 #11 (第三次重复错误 · 触发苏格拉底模式) -->
      <div class="today-item">
        <div class="today-time">📅 2026-05-29 · 08:45 · 🧠 触发苏格拉底</div>
        <div class="today-card today-card-highlight">
          <div class="today-card-head">
            <div class="today-student-avatar" style="background:linear-gradient(135deg, #FF7A33, #E55B0D)">11</div>
            <div>
              <div class="today-student-name">内测者 #11 <span class="today-student-tag">📐 Pure Math P1</span></div>
              <div class="today-student-sub">⚠️ 链式法则 · <strong>第 3 次同类错</strong> · 触发 memory 切换</div>
            </div>
          </div>
          <div class="today-trio">
            <div class="today-col">
              <div class="today-col-label">📷 学生提交</div>
              <div class="today-thumb-stub">d/dx [sin(3x²)]<br>错答：cos(3x²)</div>
            </div>
            <div class="today-col">
              <div class="today-col-label">🤖 AI 反馈（苏格拉底模式）</div>
              <div class="today-feedback">"链式法则你这是<strong>第 3 次错</strong>了<br>5/22 错过 cos(x²)<br>5/26 错过 ln(2x+1)<br>你卡在哪一步？外层导 vs 内层导。"</div>
            </div>
            <div class="today-col">
              <div class="today-col-label">💬 学生反应</div>
              <div class="today-reaction">"我真的每次都忘记乘内层导数😭"<br><span class="today-reaction-meta">系统给她刷了 10 道同型题，全过才放她过</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="today-footnote">
      上面三条都是今天真发生的，学生名字按惯例脱敏了。<br>
      数据库里能找到每一条对应的记录，不是凑出来给人看的。
    </div>
  </div>
</section>

<!-- ───────────── PRICING · 定价 / 免费策略 (P2 新增) ───────────── -->
<section class="pricing" id="pricing">
  <div class="wrap">
    <div class="head-center">
      <div class="section-label">怎么用 · 多少钱</div>
      <h2 class="section-title">3 种使用方式</h2>
    </div>
    <div class="pricing-grid">
      <div class="pricing-card">
        <div class="pricing-tag" style="background:#FFF3E8;color:#D44E0D">学生 · 免费试用</div>
        <div class="pricing-price">¥0<span class="pricing-unit"> · 内测期</span></div>
        <ul class="pricing-feat">
          <li>✓ 每天 5 张作业图免费</li>
          <li>✓ 完整 11 阶段批改</li>
          <li>✓ 历史记录 + 错题本</li>
          <li>✓ 语音反馈</li>
        </ul>
        <a href="/alevel/" class="pricing-cta">📷 立即试用</a>
      </div>
      <div class="pricing-card pricing-card-mid">
        <div class="pricing-tag" style="background:#E8F0FF;color:#1E4FCC">学生 · 包月（计划中）</div>
        <div class="pricing-price">¥39<span class="pricing-unit"> / 月</span></div>
        <ul class="pricing-feat">
          <li>✓ 无限作业批改</li>
          <li>✓ 苏格拉底模式 + 错题持久化</li>
          <li>✓ 月度学习报告</li>
          <li>✓ 老师/家长视图</li>
        </ul>
        <a href="mailto:alfred@offercome2026.com?subject=A-Level%20包月预订" class="pricing-cta-mid">📮 预订 · 上线通知</a>
      </div>
      <div class="pricing-card">
        <div class="pricing-tag" style="background:#E8F8F3;color:#009A7C">老师 / 机构 · To B</div>
        <div class="pricing-price">面议<span class="pricing-unit"> · 按校区</span></div>
        <ul class="pricing-feat">
          <li>✓ 私有部署 / 数据托管</li>
          <li>✓ 老师批改 dashboard</li>
          <li>✓ 班级学情分析</li>
          <li>✓ 题库定制（IB / AP / GCSE）</li>
        </ul>
        <a href="mailto:alfred@offercome2026.com?subject=A-Level%20机构合作" class="pricing-cta">📧 联系作者</a>
      </div>
    </div>
  </div>
</section>

<section class="how" id="how">
  <div class="wrap">
    <div class="head-center">
      <div class="section-label">使用流程</div>
      <h2 class="section-title">3 步搞定</h2>
      <p class="section-sub">不用注册, 不用 App, 拍照就行</p>
    </div>

    <div class="how-grid">
      <div class="how-step">
        <div class="step-num-circle">01</div>
        <div class="step-emoji">📸</div>
        <h4>拍一页作业</h4>
        <p>手机直接拍, 或上传 PDF. 一页支持多道题, 系统自己切. 不要求摆正, 不要求亮度均匀.</p>
        <div class="duration">⏱ 5 秒</div>
      </div>
      <div class="how-step">
        <div class="step-num-circle">02</div>
        <div class="step-emoji">⚙️</div>
        <h4>等 2-3 分钟</h4>
        <p>切题 → 识别手写 → 分类题型 → 批改 → SymPy 复核. 后台异步算, 不用盯着.</p>
        <div class="duration">⏱ 2-3 分钟</div>
      </div>
      <div class="how-step">
        <div class="step-num-circle">03</div>
        <div class="step-emoji">📋</div>
        <h4>逐题反馈</h4>
        <p>每题三段: <strong>错在哪 / 缺什么 / 下一步</strong>. 不是"做得很好继续努力"那种话.</p>
        <div class="duration">⏱ 自己看</div>
      </div>
    </div>
  </div>
</section>

<section class="tech" id="tech">
  <div class="wrap tech-wrap">
    <details>
      <summary>
        <div class="ic-tech">⚙️</div>
        <div class="label-block">
          <div class="l-top">如果你是技术读者, 看这里 ↓</div>
          <div class="l-sub">Pipeline · Multi-Agent · SymPy verifier · Memory · MCP Server</div>
        </div>
        <span class="toggle-arrow">▼</span>
      </summary>
      <div class="tech-body">
        <div class="tech-grid">
          <div class="tech-block">
            <h5>Pipeline <span class="pill-small">11 STAGES</span></h5>
            <p>整页 → Segmenter → OCR + Vision 交叉 → Extractor → Classifier → Base grader → Router → Multi-Agent voting → SymPy 验证 → Dual Feedback → Memory → Reflection</p>
          </div>
          <div class="tech-block">
            <h5>Multi-Agent <span class="pill-small">5 HETEROGENEOUS</span></h5>
            <p>Fast tier (Viviai Gemini Flash models) 并行 + 早返回. 不一致升级 Accurate tier (Gemini Pro models).</p>
          </div>
          <div class="tech-block">
            <h5>SymPy 验证层 <span class="pill-small">OVERRIDE</span></h5>
            <p>所有可符号化的步骤 (求导/解方程/积分/化简) 过一遍 SymPy. 64 fixture 上 LLM 误判率从 12.5% → 0%.</p>
          </div>
          <div class="tech-block">
            <h5>User Memory <span class="pill-small">PERSISTENT</span></h5>
            <p>SQLite + 4 类 fact (weakness/preference/progress/goal) + Conflict Resolution (旧 fact decay 0.5×) + GDPR.</p>
          </div>
          <div class="tech-block">
            <h5>MCP Server <span class="pill-small">4 TOOLS</span></h5>
            <p>把 <code>classify_question</code>/<code>verify_calculation</code>/<code>get_student_memory</code>/<code>save_student_fact</code> 通过 stdio MCP 暴露给 Claude Code/Cursor.</p>
          </div>
          <div class="tech-block">
            <h5>Stack</h5>
            <p>Python 3.14 · FastAPI · Vite + React · SQLite · SymPy 1.13 · MCP SDK 1.0+ · 5 LLM providers · <strong>≈15K LoC · 54 单测全过</strong>.</p>
          </div>
        </div>
      </div>
    </details>
  </div>
</section>

<section class="final-cta">
  <div class="wrap">
    <h2>上传一张<span class="accent">你自己的</span>作业,<br>看看实际效果</h2>
    <p class="sub">不需要注册. 一张图最多 3 分钟. 几十名学生在用.</p>
    <div class="cta-row">
      <a class="btn-primary" href="/alevel/" style="font-size:17px;padding:16px 32px">📷 开始试用 <span class="arrow">→</span></a>
    </div>
  </div>
</section>

<footer>
  <div class="wrap">
    <div class="brand-foot">
      <div class="brand-logo">A</div>
      A-Level 助手 · 2026 · 陈卓欣
    </div>
    <div class="spacer"></div>
    <a href="/alevel/">主应用</a>
    <a href="/alevel/api/agents/status">JSON API</a>
    <a href="mailto:alfred@offercome2026.com">联系我</a>
  </div>
</footer>

<!-- 📱 移动端浮动 CTA (P0 新增 2026-05-29) -->
<a href="/alevel/" class="sticky-cta">📷 拍一页作业·3 分钟看反馈 →</a>

<script>
// ── 真实调 codex shim 批改 demo · SSE 流式渲染 ──────────────────
(function() {
  const btn = document.getElementById('grade-start-btn');
  if (!btn) return;

  const elInit = document.getElementById('grade-init');
  const elLoad = document.getElementById('grade-loading');
  const elOut = document.getElementById('grade-output');
  const elSympy = document.getElementById('grade-sympy');
  const elDone = document.getElementById('grade-done');
  const elErr = document.getElementById('grade-error');
  const elStatus = document.getElementById('grade-status');
  const elStage = document.getElementById('grade-loading-stage');
  const elMeta = document.getElementById('grade-loading-meta');
  const elTimer = document.getElementById('grade-timer');
  // 新加: OCR + bbox + 进度环
  const elOcrOut = document.getElementById('ocr-output');
  const elOcrCnt = document.getElementById('ocr-counter');
  const elOverlay = document.getElementById('img-overlay');
  const elProgressRing = document.getElementById('demo-progress-ring');
  const elLeftStatus = document.getElementById('left-status');

  // 8 步流水线 (后端 demo_grade.py emit stage_start/stage_done 驱动)
  const STAGES = [
    { key: 'image_loaded', label: '📥 接收图片',    ic: '1', eta: 1  },
    { key: 'ocr',          label: '👁 OCR 11 行',   ic: '2', eta: 1  },
    { key: 'segmenter',    label: '✂️ 切题 Segmenter',  ic: '3', eta: 10 },
    { key: 'ocr',          label: '👁 识别 OCR Agent',   ic: '4', eta: 11 },
    { key: 'grader',       label: '✏️ 批改 Grader',     ic: '5', eta: 14 },
    { key: 'verifier',     label: '🧮 验算 Verifier',  ic: '6', eta: 11 },
    { key: 'memory',       label: '🧠 学情 Memory',    ic: '7', eta: 12 },
    { key: 'sympy',        label: '🧪 SymPy 复算',    ic: '8', eta: 1  },
    { key: 'recommend',    label: '📚 配同型刷题',     ic: '9', eta: 1  },
  ];
  // 注: 第 1 步 image_loaded 和第 2 步 OCR 都是预处理·第 2 步 key=ocr 跟第 4 步 ocr_agent key 重名·后端发的 ocr_agent 走第 4 步处理
  // 为唯一化, 我们用 data-stage-slot=index 代替 data-stage=key
  STAGES.forEach((s, i) => { s.slot = i; });
  // 把 backend key 映射到 slot 序号: 第一次出现 ocr=slot 1; orchestrator agent_msg ocr 映射到 slot 3 (按 agent_idx)
  // 简化处理: image_loaded=0, ocr=1(预处理) 或 3(agent), segmenter=2, grader=4, verifier=5, memory=6, sympy=7, recommend=8
  // 用一个状态机: 后端按顺序 emit stage_start, 前端按顺序点亮 slot
  let nextSlot = 0;

  // 每个 agent / 步骤的"思考中"短语 (1.5s 轮播一句)
  const STAGE_TIPS = {
    segmenter: [
      '扫一眼整页 4 道题…',
      '判断哪道是 3-marker 重点…',
      '把 Q1(d) 切出来送给 OCR…',
    ],
    ocr: [
      '识别学生第 1-4 行 working…',
      '第 6 行字迹模糊…再认一下…',
      '11 行全识别完，标了一行可疑…',
    ],
    grader: [
      '对照 Cambridge mark scheme…',
      '第 6 行符号错位…扣分点定位…',
      '调 @Verifier 复算 x 标准值…',
      '初判 1/3 method mark, 写反馈…',
    ],
    verifier: [
      '加载 SymPy…',
      '联立 4y=3x+5 与 4y=-3x+29…',
      '解出 T=(4, 17/4)…',
      '对比学生 (-7/8, 2), confirm…',
    ],
    memory: [
      '查这学生符号管理类历史错点…',
      '5/22 一次, 5/26 一次, 今天第 3 次…',
      '到苏格拉底阈值, 切反问模式…',
    ],
  };

  // KaTeX 渲染包装器
  function renderMath(el) {
    if (!el || !window.renderMathInElement) return;
    try {
      window.renderMathInElement(el, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$',  right: '$',  display: false },
          { left: '\\(', right: '\\)', display: false },
          { left: '\\[', right: '\\]', display: true },
        ],
        throwOnError: false,
        errorColor: '#dc2626',
      });
    } catch (e) {}
  }

  // 页面加载后初次渲染静态数学
  function initialMathRender() {
    document.querySelectorAll('.math-render').forEach(renderMath);
  }
  if (window.__katexReady) initialMathRender();
  else document.addEventListener('katex-ready', initialMathRender);
  // 兜底: 1.5s 后再扫一次
  setTimeout(initialMathRender, 1500);

  let buffer = '';
  let startTs = 0;
  let timerHandle = null;

  function showInit() {
    elInit.style.display = ''; elLoad.style.display = 'none';
    elOut.style.display = 'none'; elSympy.style.display = 'none';
    elDone.style.display = 'none'; elErr.style.display = 'none';
    elStatus.textContent = '等待开始';
  }

  function showLoading() {
    elInit.style.display = 'none'; elLoad.style.display = '';
    elOut.style.display = 'none'; elSympy.style.display = 'none';
    elDone.style.display = 'none'; elErr.style.display = 'none';
    // 渲染阶段列表 (loading 卡内)
    renderStageList();
    elProgressRing.classList.add('stage-active');
  }

  function showStreaming() {
    elOut.style.display = '';
  }

  function renderStageList() {
    const totalEta = STAGES.reduce((s, x) => s + x.eta, 0);
    const html = `
      <!-- 总进度条 -->
      <div class="demo-overall">
        <div class="demo-overall-row">
          <span>进度</span>
          <b id="overall-step">0 / ${STAGES.length}</b>
          <span>· 已用 <b id="overall-elapsed">0s</b> · 预计还有 <b id="overall-eta">约 ${totalEta}s</b></span>
          <div class="demo-stars" id="demo-stars">
            ${Array(5).fill(0).map((_,i) => `<span class="demo-star" data-star="${i}">⭐</span>`).join('')}
          </div>
        </div>
        <div class="demo-overall-bar"><div class="demo-overall-fill" id="overall-fill"></div></div>
      </div>

      <div class="stage-progress" id="stage-progress">
        <div class="stage-progress-head">
          <div class="grade-spinner"></div>
          <div class="stage-current" id="stage-current">正在唤起 GPT-5.5 · OAuth 冷启动 ~5s…</div>
          <div class="stage-elapsed" id="stage-elapsed">0.0s</div>
        </div>
        <div class="stage-list" id="stage-list">
          ${STAGES.map((s, i) => `
            <div class="stage-item" data-stage-slot="${i}">
              <div class="si-ic">${s.ic}</div>
              <div class="si-label">${s.label}</div>
              <div class="si-eta" data-stage-eta="${i}">约 ${s.eta}s</div>
              <div class="si-time" data-stage-time="${i}">—</div>
              <div class="si-tip" data-stage-tip="${i}"></div>
            </div>
          `).join('')}
        </div>
        <div class="output-tabs" id="output-tabs">
          <button class="tab active" data-tab="agent" type="button">
            💬 Agent 对话 <span class="tab-count" id="agent-count">0</span>
          </button>
          <button class="tab" data-tab="sse" type="button">
            📡 SSE 流 <span class="tab-count" id="sse-count">0</span>
          </button>
        </div>
        <div class="output-tab-pane active" data-pane="agent">
          <div class="agent-chat" id="agent-chat" style="display:none"></div>
        </div>
        <div class="output-tab-pane" data-pane="sse" hidden>
          <div class="sse-stream-body" id="sse-stream-body"></div>
        </div>
      </div>
    `;
    elLoad.innerHTML = html;
    // tab 切换
    document.querySelectorAll('#output-tabs .tab').forEach(t => {
      t.addEventListener('click', () => {
        document.querySelectorAll('#output-tabs .tab').forEach(x => x.classList.remove('active'));
        t.classList.add('active');
        const tab = t.getAttribute('data-tab');
        document.querySelectorAll('.output-tab-pane').forEach(p => {
          if (p.getAttribute('data-pane') === tab) { p.removeAttribute('hidden'); p.classList.add('active'); }
          else { p.setAttribute('hidden', ''); p.classList.remove('active'); }
        });
      });
    });
  }

  let stageStartMs = {};
  let activeTipTimer = null;
  let starsLit = 0;

  function _activateSlot(slot, label, eta) {
    const el = document.querySelector(`[data-stage-slot="${slot}"]`);
    if (!el) return;
    // 之前 slot 都置 done (若还 active)
    document.querySelectorAll('.stage-item').forEach(it => {
      const s = parseInt(it.getAttribute('data-stage-slot'));
      if (s < slot && !it.classList.contains('done')) {
        it.classList.remove('active');
        it.classList.add('done');
      }
    });
    el.classList.add('active');
    el.classList.remove('done');
    stageStartMs['slot_' + slot] = Date.now();
    // 当前文案
    const cur = document.getElementById('stage-current');
    if (cur) cur.textContent = label || '处理中…';
    // 思考短语轮播 (基于 STAGES[slot].key)
    const stageKey = STAGES[slot] && STAGES[slot].key;
    const tips = STAGE_TIPS[stageKey] || [];
    const tipEl = el.querySelector(`[data-stage-tip="${slot}"]`);
    if (activeTipTimer) clearInterval(activeTipTimer);
    if (tips.length > 0 && tipEl) {
      let i = 0;
      tipEl.textContent = '✨ ' + tips[0];
      tipEl.style.opacity = '1';
      activeTipTimer = setInterval(() => {
        i = (i + 1) % tips.length;
        tipEl.textContent = '✨ ' + tips[i];
      }, 2200);
    }
    // 总进度
    updateOverall(slot);
    // 左侧图片 bbox 联动当前 agent (让用户看到"谁在看哪里")
    try { paintBboxForStage(stageKey); } catch (e) {}
  }

  function _doneSlot(slot, elapsedS, msg, kind) {
    const el = document.querySelector(`[data-stage-slot="${slot}"]`);
    if (!el) return;
    el.classList.remove('active');
    el.classList.add('done');
    const timeEl = el.querySelector(`[data-stage-time="${slot}"]`);
    if (timeEl) timeEl.textContent = (typeof elapsedS === 'number' ? elapsedS.toFixed(1) : '—') + 's';
    const tipEl = el.querySelector(`[data-stage-tip="${slot}"]`);
    if (tipEl && msg) {
      tipEl.style.fontStyle = 'normal';
      tipEl.style.color = (kind === 'real') ? 'var(--green-deep, #047857)' : 'var(--ink-muted)';
      tipEl.textContent = (kind === 'real' ? '✓ LIVE · ' : '✓ ') + msg;
    }
    if (activeTipTimer) { clearInterval(activeTipTimer); activeTipTimer = null; }
    // agent 真跑完点亮一颗星 (5 个 agent 对应 5 颗)
    const stageKey = STAGES[slot] && STAGES[slot].key;
    const isAgent = ['segmenter','ocr','grader','verifier','memory'].includes(stageKey) && slot >= 2;
    if (isAgent && kind === 'real' && starsLit < 5) {
      const star = document.querySelector(`[data-star="${starsLit}"]`);
      if (star) star.classList.add('lit');
      starsLit++;
    }
    updateOverall(slot + 1);
  }

  function updateOverall(stepDone) {
    const stepEl = document.getElementById('overall-step');
    const fillEl = document.getElementById('overall-fill');
    const etaEl  = document.getElementById('overall-eta');
    if (stepEl) stepEl.textContent = `${Math.min(stepDone, STAGES.length)} / ${STAGES.length}`;
    if (fillEl) fillEl.style.width = `${Math.min(100, (stepDone / STAGES.length) * 100)}%`;
    if (etaEl) {
      const remaining = STAGES.slice(stepDone).reduce((s, x) => s + x.eta, 0);
      etaEl.textContent = remaining > 0 ? `约 ${remaining}s` : '✓ 完成';
    }
  }

  function paintBboxes() {
    if (!elOverlay) return;
    // page2.jpg 实际布局 (Q1a 学生 working 在最上 / Q1c 中间 / Q1d 在右下角)
    elOverlay.innerHTML = `
      <div class="bbox" data-q="q1a" style="left:13%;top:8%;width:54%;height:39%"><span class="bbox-label">Q1(a)</span></div>
      <div class="bbox" data-q="q1c" style="left:5%;top:53%;width:35%;height:42%;animation-delay:0.25s"><span class="bbox-label">Q1(c)</span></div>
      <div class="bbox q1d" data-q="q1d" style="left:42%;top:53%;width:55%;height:46%"><span class="bbox-label">Q1(d) · 3 marks</span></div>
    `;
  }

  function clearBboxes() {
    if (elOverlay) elOverlay.innerHTML = '';
  }

  // ============================================================
  // bbox 联动当前 active agent · 让用户看到"谁在看哪里"
  // ============================================================
  // 每个 agent 的视觉策略:
  //   segmenter → 3 道题 bbox 全画出来 + 顶部 chip "正在扫整页"
  //   ocr_agent → 只高亮 Q1d, 其他淡化 + Q1d scan-line 动画
  //   grader    → Q1d 焦点 + scan-line + agent tag (左上 "Grader 阅卷中")
  //   verifier  → Q1d 焦点 + 内部红色 err-row 标第 6 行 + agent tag
  //   memory    → Q1d 保留 + 全部恢复 (代表"记录到学情")
  function paintBboxForStage(stageKey) {
    if (!elOverlay) return;
    // 首次调用先把 3 个 bbox 画出来
    if (!elOverlay.querySelector('.bbox')) paintBboxes();
    const all = elOverlay.querySelectorAll('.bbox');
    const q1d = elOverlay.querySelector('.bbox.q1d');

    // reset 所有动态 class
    all.forEach(b => {
      b.classList.remove('focus', 'dim', 'scan');
      const tag = b.querySelector('.bbox-agent-tag');
      if (tag) tag.remove();
    });

    if (stageKey === 'segmenter') {
      all.forEach(b => b.classList.add('focus'));
      // 把 agent tag 贴在 q1d (最重要那道)
      addAgentTag(q1d, '✂', 'Segmenter 扫整页');
    } else if (stageKey === 'ocr') {
      // STAGES 里第 4 步 key='ocr' = OCR Agent · 此时只看 Q1d
      all.forEach(b => b.classList.add('dim'));
      if (q1d) { q1d.classList.remove('dim'); q1d.classList.add('focus', 'scan'); }
      addAgentTag(q1d, '👁', 'OCR 识别中');
    } else if (stageKey === 'grader') {
      all.forEach(b => b.classList.add('dim'));
      if (q1d) { q1d.classList.remove('dim'); q1d.classList.add('focus', 'scan'); }
      addAgentTag(q1d, '✏', 'Grader 阅卷');
    } else if (stageKey === 'verifier') {
      all.forEach(b => b.classList.add('dim'));
      if (q1d) {
        q1d.classList.remove('dim'); q1d.classList.add('focus');
        // 在 q1d 内部加红色错位行 (大约 50% 位置, 第 6 行)
        if (!q1d.querySelector('.err-row')) {
          const er = document.createElement('div');
          er.className = 'err-row';
          er.style.top = '52%';
          q1d.appendChild(er);
        }
      }
      addAgentTag(q1d, '🧮', 'Verifier 验算');
    } else if (stageKey === 'memory') {
      all.forEach(b => b.classList.add('dim'));
      if (q1d) { q1d.classList.remove('dim'); q1d.classList.add('focus'); }
      addAgentTag(q1d, '🧠', 'Memory 记入学情');
    }
  }

  function addAgentTag(bbox, icon, label) {
    if (!bbox) return;
    const tag = document.createElement('div');
    tag.className = 'bbox-agent-tag';
    tag.innerHTML = `<span class="dot"></span><span>${icon}</span><span>${label}</span>`;
    bbox.appendChild(tag);
  }

  function tickTimer() {
    const elapsed = (Date.now() - startTs) / 1000;
    if (elTimer) elTimer.textContent = elapsed.toFixed(1) + 's';
    const se = document.getElementById('stage-elapsed');
    if (se) se.textContent = elapsed.toFixed(1) + 's';
    const oe = document.getElementById('overall-elapsed');
    if (oe) oe.textContent = elapsed < 60 ? elapsed.toFixed(0) + 's' : Math.floor(elapsed/60)+'m'+Math.floor(elapsed%60)+'s';
  }

  // 把流式 markdown 转成结构化 4 段 HTML
  function renderMarkdown(md) {
    // 把 ### 段落切分出来
    const sections = {};
    const lines = md.split('\n');
    let currentKey = null, currentBuf = [];
    for (const line of lines) {
      const m = line.match(/^###\s*(✕|🎯|📚|🚀)\s*(.+)$/);
      if (m) {
        if (currentKey) sections[currentKey] = currentBuf.join('\n').trim();
        const icon = m[1];
        if (icon === '✕') currentKey = 'verdict';
        else if (icon === '🎯') currentKey = 'error';
        else if (icon === '📚') currentKey = 'gap';
        else if (icon === '🚀') currentKey = 'action';
        currentBuf = [];
      } else if (currentKey) {
        currentBuf.push(line);
      }
    }
    if (currentKey) sections[currentKey] = currentBuf.join('\n').trim();

    // 内联 code 转换
    function inlineCode(s) {
      return s
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
    }

    let html = '';
    if (sections.verdict) {
      html += `<div class="v-row">
        <span class="v-tag">✕ ${inlineCode(sections.verdict.split(/[,，。.]/)[0])}</span>
      </div>`;
    }
    if (sections.error) {
      html += `<div class="gb error"><h5>🎯 错在哪 (Error)</h5><p>${inlineCode(sections.error)}</p></div>`;
    }
    if (sections.gap) {
      html += `<div class="gb gap"><h5>📚 缺什么 (Gap)</h5><p>${inlineCode(sections.gap)}</p></div>`;
    }
    if (sections.action) {
      html += `<div class="gb action"><h5>🚀 下一步 (Action)</h5><p>${inlineCode(sections.action)}</p></div>`;
    }
    // 还没解析出来的内容当作 streaming text 显示
    if (!html) {
      html = `<div style="white-space:pre-wrap;font-size:13.5px;color:var(--ink)">${inlineCode(md)}<span class="typing-cursor"></span></div>`;
    } else if (md.length > 0 && !sections.action) {
      // 流式进行中，加打字光标
      html += `<div style="text-align:right"><span class="typing-cursor"></span></div>`;
    }
    return html;
  }

  function renderSympy(s) {
    if (!s.verified) {
      return `<div class="sympy-check" style="border-color:var(--ink-muted)">
        <div class="check-ic" style="background:var(--ink-muted)">!</div>
        <div class="check-text">SymPy 验证未启用 (${s.error || 'unknown'})</div>
      </div>`;
    }
    return `<div class="sympy-check">
      <div class="check-ic">✓</div>
      <div class="check-text"><b>SymPy 符号验证</b> · 实算 ${s.human_str} · 与学生答案不一致 → 已标错</div>
    </div>`;
  }

  function renderDone(d) {
    return `
      <span class="done-tag">✓ DONE</span>
      <span>耗时 <b>${d.elapsed_sec}s</b></span>
      <span>模型 <b>${d.model}</b></span>
      <span>≈ <b>${d.tokens_approx}</b> tokens</span>
      <span style="margin-left:auto">via codex OAuth</span>
    `;
  }

  async function startGrading() {
    btn.disabled = true;
    elStatus.textContent = '调用中…';
    showLoading();
    buffer = '';
    ocrLineCount = 0;
    if (elOcrOut) elOcrOut.innerHTML = '';
    if (elOcrCnt) elOcrCnt.textContent = '0 / 11 行';
    clearBboxes();
    const oldReco = document.getElementById('grade-reco');
    if (oldReco) oldReco.remove();
    elProgressRing.classList.remove('stage-done');
    startTs = Date.now();
    stageStartMs._begin = startTs;
    nextSlot = 0;
    starsLit = 0;
    agentMsgCount = 0;
    sseEventCount = 0;
    if (activeTipTimer) { clearInterval(activeTipTimer); activeTipTimer = null; }
    timerHandle = setInterval(tickTimer, 100);

    try {
      // 根据 window.location 自动决定前缀: 部署时是 /alevel/api/... · 本地直连 :8000 时是 /api/...
      const apiPrefix = location.pathname.startsWith('/alevel/') ? '/alevel/api' : '/api';
      const resp = await fetch(apiPrefix + '/showcase/demo-grade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      if (!resp.body) throw new Error('No response stream');

      const reader = resp.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let leftover = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = leftover + decoder.decode(value, { stream: true });
        const lines = text.split('\n');
        leftover = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (!payload) continue;
          let evt;
          try { evt = JSON.parse(payload); } catch (e) { continue; }
          handleEvent(evt);
        }
      }
    } catch (err) {
      clearInterval(timerHandle);
      elStatus.textContent = '失败';
      elErr.style.display = '';
      elErr.innerHTML = `
        <div><b>调用失败</b> · ${err.message || err}</div>
        <button class="retry-btn" onclick="document.getElementById('grade-start-btn').click()">重试</button>
      `;
      showInit();
      btn.disabled = false;
    }
  }

  // Agent 对话气泡渲染
  const AGENT_ICONS = {
    'Segmenter': '✂',
    'OCR Agent': '👁',
    'Grader': '✏',
    'Verifier': '🧮',
    'Memory': '🧠',
  };
  let agentMsgCount = 0;
  function appendAgentMsg(evt) {
    const wrap = document.getElementById('agent-chat');
    if (!wrap) return;
    if (wrap.style.display === 'none') wrap.style.display = '';
    agentMsgCount++;
    const cnt = document.getElementById('agent-count');
    if (cnt) cnt.textContent = agentMsgCount;
    const color = evt.color || 'blue';
    const icon = AGENT_ICONS[evt.agent] || '🤖';
    const safeText = (evt.text || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/@(\w+)/g, '<b style="color:var(--orange-deep)">@$1</b>');

    // kind 标记
    const kind = evt.kind || 'real';
    const kindLabel = kind === 'real' ? 'LIVE' : 'CACHED';
    // 耗时
    const elapsed = (typeof evt.elapsed_s === 'number') ? `${evt.elapsed_s.toFixed(2)}s` : '';

    const div = document.createElement('div');
    div.className = `agent-bubble ${color}`;
    div.innerHTML = `
      <div class="agent-bubble-avatar">${icon}</div>
      <div class="agent-bubble-body">
        <div class="agent-bubble-name">
          ${evt.agent}<span class="agent-bubble-role">· ${evt.role || ''}</span>
          ${elapsed ? `<span class="agent-bubble-elapsed">⏱ ${elapsed}</span>` : ''}
          <span class="agent-bubble-kind ${kind}">${kindLabel}</span>
        </div>
        <div class="agent-bubble-text">${safeText}</div>
      </div>
    `;
    wrap.appendChild(div);
    if (safeText.includes('$')) {
      try { renderMath(div); } catch (e) {}
    }
    wrap.scrollTop = wrap.scrollHeight;
  }

  // SSE log: 每收一个 event push 一行
  let sseEventCount = 0;
  function pushSseLog(evt) {
    const body = document.getElementById('sse-stream-body');
    const cnt  = document.getElementById('sse-count');
    if (!body) return;
    sseEventCount++;
    if (cnt) cnt.textContent = sseEventCount;
    const t = ((Date.now() - startTs) / 1000).toFixed(2) + 's';
    const type = evt.type || '?';
    // 摘要 payload
    let payload = '';
    if (type === 'stage')        payload = `<span>${evt.stage} · ${evt.msg||''}</span>`;
    else if (type === 'agent_msg') {
      const k = (evt.kind || 'real') === 'real' ? '<span class="ok">live</span>' : '<span class="fb">cached</span>';
      payload = `<span>${evt.agent} (${k}, ${(evt.elapsed_s||0).toFixed(2)}s) "${(evt.text||'').slice(0,60).replace(/</g,'&lt;')}..."</span>`;
    }
    else if (type === 'chunk')   payload = `<span>+${(evt.text||'').length} chars</span>`;
    else if (type === 'ocr_line') payload = `<span>${(evt.text||'').slice(0,60).replace(/</g,'&lt;')}</span>`;
    else if (type === 'sympy')   payload = `<span>verified=${evt.result?.verified} ${evt.result?.human_str||''}</span>`;
    else if (type === 'recommend') payload = `<span>${(evt.items||[]).length} items</span>`;
    else if (type === 'done')    payload = `<span class="ok">✓ total=${evt.total_sec}s model=${evt.model||'?'}</span>`;
    else                          payload = JSON.stringify(evt).slice(0,80);

    const line = document.createElement('div');
    line.className = 'sse-line';
    line.innerHTML = `
      <span class="sse-t">${t}</span>
      <span class="sse-type t-${type}">${type}</span>
      <span class="sse-payload">${payload}</span>
    `;
    body.appendChild(line);
    body.scrollTop = body.scrollHeight;
  }

  let ocrLineCount = 0;
  function appendOcrLine(text) {
    if (ocrLineCount === 0) elOcrOut.innerHTML = '';
    const line = document.createElement('div');
    line.className = 'ocr-line';
    // text 含 $..$, 用 innerHTML 让 KaTeX auto-render 找到
    line.innerHTML = text;
    elOcrOut.appendChild(line);
    renderMath(line);
    ocrLineCount++;
    if (elOcrCnt) elOcrCnt.textContent = `${ocrLineCount} / 11 行`;
  }

  function renderRecommendCards(items) {
    if (!items || !items.length) return '';
    const cards = items.map((it, i) => `
      <div class="reco-card">
        <div class="reco-head">
          <span class="reco-paper">${it.paper}</span>
          <span class="reco-marks">${it.marks} marks</span>
          <span class="reco-strength" title="匹配度">${it.match_strength || ''}</span>
        </div>
        <div class="reco-topic">${it.topic}</div>
        <div class="reco-summary math-render">${it.summary_latex || it.summary || ''}</div>
        <div class="reco-why">💡 ${it.why}</div>
        <div class="reco-foot">
          <span class="reco-diff">${it.difficulty}</span>
          <a class="reco-go" href="/alevel/?paper=${encodeURIComponent(it.paper)}">去练这道 →</a>
        </div>
      </div>
    `).join('');
    return `
      <div class="reco-section">
        <div class="reco-head-title">
          <span>📚 推荐刷这 3 道</span>
          <span class="reco-sub">按你这次错点 (切线联立移项符号) 匹配题库</span>
        </div>
        <div class="reco-grid">${cards}</div>
      </div>
    `;
  }

  function handleEvent(evt) {
    pushSseLog(evt);  // 每个 SSE event 都先 push 到流日志
    if (evt.type === 'stage_start') {
      // 按顺序点亮下一个 slot
      const label = evt.label || evt.stage;
      _activateSlot(nextSlot, label, evt.eta_s);
      if (evt.stage === 'image_loaded' && elLeftStatus) elLeftStatus.textContent = '✓ 已接收 · OCR 中';
      if (evt.stage === 'ocr' && nextSlot === 1 && elLeftStatus) elLeftStatus.textContent = 'OCR 流式识别中…';
    } else if (evt.type === 'stage_done') {
      _doneSlot(nextSlot, evt.elapsed_s, evt.msg, evt.kind);
      nextSlot++;
      if (evt.stage === 'ocr' && nextSlot === 2 && elLeftStatus) {
        elLeftStatus.textContent = `✓ OCR 完成 · ${ocrLineCount} 行`;
      }
    } else if (evt.type === 'stage') {
      // legacy fallback: 老 stage 事件直接忽略 (后端已切到 stage_start/done)
    } else if (evt.type === 'ocr_line') {
      appendOcrLine(evt.text);
    } else if (evt.type === 'agent_msg') {
      appendAgentMsg(evt);
    } else if (evt.type === 'start') {
      // (legacy — backend 已用 stage:image_loaded 替代, 但保留兼容)
    } else if (evt.type === 'chunk') {
      if (elOut.style.display === 'none') showStreaming();
      buffer += evt.text;
      elOut.innerHTML = renderMarkdown(buffer);
      renderMath(elOut);
    } else if (evt.type === 'recommend') {
      // 加推荐题卡片 (插在 sympy 上方)
      const recoEl = document.createElement('div');
      recoEl.id = 'grade-reco';
      recoEl.innerHTML = renderRecommendCards(evt.items);
      elSympy.parentNode.insertBefore(recoEl, elSympy);
      recoEl.querySelectorAll('.math-render').forEach(renderMath);
    } else if (evt.type === 'sympy') {
      elSympy.style.display = '';
      elSympy.innerHTML = renderSympy(evt.result);
    } else if (evt.type === 'done') {
      clearInterval(timerHandle);
      if (activeTipTimer) { clearInterval(activeTipTimer); activeTipTimer = null; }
      // 所有阶段标 done + 总进度填满
      document.querySelectorAll('.stage-item').forEach(el => {
        el.classList.remove('active');
        el.classList.add('done');
      });
      updateOverall(STAGES.length);
      // 5 颗星全部点亮 (即便 fallback 也点亮 — 视觉完整度)
      const totalStars = Math.max(evt.stars_earned || 0, 5);
      for (let i = 0; i < 5; i++) {
        const s = document.querySelector(`[data-star="${i}"]`);
        if (s && !s.classList.contains('lit')) {
          // 错峰点亮 (每隔 100ms 一颗 · 像通关时的连击)
          setTimeout(() => s.classList.add('lit'), i * 120);
        }
      }
      // 5 颗都亮后整组 shimmer
      setTimeout(() => {
        const wrap = document.getElementById('demo-stars');
        if (wrap) wrap.classList.add('all-lit');
      }, 700);
      // 总进度卡庆祝色 + 短暂闪光
      const overall = document.querySelector('.demo-overall');
      if (overall) {
        overall.classList.add('celebrating');
        setTimeout(() => overall.classList.remove('celebrating'), 1400);
      }
      // confetti
      fireConfetti();
      elProgressRing.classList.remove('stage-active');
      elProgressRing.classList.add('stage-done');
      // 隐藏 loading 卡, 显示 done
      elLoad.style.display = 'none';
      elDone.style.display = '';
      elDone.innerHTML = renderDone(evt);
      elStatus.textContent = `✓ 完成 (${evt.total_sec || evt.elapsed_sec}s)`;
      btn.disabled = false;
    } else if (evt.type === 'error') {
      clearInterval(timerHandle);
      elErr.style.display = '';
      elErr.innerHTML = `
        <div><b>后端报错</b> · ${evt.message}</div>
        <button class="retry-btn" onclick="document.getElementById('grade-start-btn').click()">重试</button>
      `;
      elStatus.textContent = '失败';
      btn.disabled = false;
    }
  }

  btn.addEventListener('click', startGrading);

  // ── 庆祝 confetti (完成时 8 颗彩色小方块从顶部散落) ───────────
  function fireConfetti() {
    const host = document.getElementById('grade-card') || document.body;
    const hostRect = host.getBoundingClientRect();
    const palette = ['#3D7BFF', '#00B894', '#FF7A33', '#FBBF24', '#9333EA', '#EC4899'];
    for (let i = 0; i < 24; i++) {
      const p = document.createElement('div');
      p.className = 'confetti-piece';
      p.style.background = palette[i % palette.length];
      p.style.left = (50 + (Math.random() - 0.5) * 60) + '%';
      p.style.top = '12px';
      const cx = (Math.random() - 0.5) * 320 + 'px';
      const cy = (180 + Math.random() * 200) + 'px';
      p.style.setProperty('--cx', cx);
      p.style.setProperty('--cy', cy);
      p.style.animationDelay = (Math.random() * 0.25) + 's';
      host.appendChild(p);
      setTimeout(() => p.remove(), 2200);
    }
  }

  // ── Warmup · demo 区进入视口时 fire-and-forget 唤起 codex OAuth ─────────
  // 节省用户点击后的 cold start (5-8s). 60s 内 backend 复用 cached state.
  let warmupFired = false;
  function fireWarmup() {
    if (warmupFired) return;
    warmupFired = true;
    const apiPrefix = location.pathname.startsWith('/alevel/') ? '/alevel/api' : '/api';
    fetch(apiPrefix + '/showcase/demo-warmup', { method: 'POST' })
      .then(r => r.json())
      .then(d => {
        if (d && d.warmed) {
          const meta = document.getElementById('grade-loading-meta');
          // 把 init 卡里的小字也轻轻提示一下 "已预热"
          const initMeta = elInit && elInit.querySelector('div[style*="font-family"]');
          if (initMeta && d.cached) initMeta.innerHTML = 'model=gpt-5.5 · provider=codex-oauth · ✓ 已预热 ' + (d.age_s||0) + 's 前';
          else if (initMeta) initMeta.innerHTML = 'model=gpt-5.5 · provider=codex-oauth · ✓ 已预热 (' + (d.cold_start_s||'?') + 's)';
        }
      })
      .catch(() => {});
  }
  // 入口 1: demo 区进入视口
  const demoSection = document.querySelector('.demo-bg') || document.querySelector('section.demo') || elInit;
  if (demoSection && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) { fireWarmup(); io.disconnect(); break; }
      }
    }, { rootMargin: '200px' });
    io.observe(demoSection);
  } else {
    // fallback: 页面 load 后 2s 触发
    setTimeout(fireWarmup, 2000);
  }
})();
</script>

</body>
</html>
"""
