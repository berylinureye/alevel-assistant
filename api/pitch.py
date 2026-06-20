"""/pitch · 产品负责人视角的产品介绍页

口吻原则:
  · 第一人称, 像跟朋友说话, 不是 PPT
  · 不写 "X, 不是 Y" 这种对偶
  · 有数据、有取舍、有判断
  · 不藏技术细节, 也不堆黑话
  · 每章都是一段长 narrative, 不是 bullet 清单
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


pitch_router = APIRouter(tags=["pitch"])


@pitch_router.get("/pitch", response_class=HTMLResponse)
async def pitch_page():
    return _HTML


_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>关于这个产品 · 产品负责人的话</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="我做的 A-Level 数学批改助手 — 怎么想的、给谁用的、怎么实现的、怎么挣钱.">

<style>
/* ==================================================================
 * 设计语言: 简约 · 简奢 · 高端
 * 参考: a16z founder essay · Apple keynote · Brunello Cucinelli editorial
 * - 米白底 + 几乎纯黑文字 + 古金 accent
 * - 衬线大标题 + 优雅 sans 正文 + 等宽数字
 * - 极少装饰: 一条线 / 一个圆点 / 一个编号
 * - 零圆角阴影渐变, 一切靠留白和字号节奏
 * ================================================================== */
:root {
  --bg:        #FBFAF6;   /* 米白 - 比纯白更温润 */
  --bg-2:      #F4F1E9;   /* 暖米浅卡 */
  --bg-3:      #ECE7D8;   /* 深米卡 */
  --ink:       #1A1612;   /* 近黑, 带一丝暖 */
  --ink-2:     #44403C;   /* 次文字 */
  --ink-3:     #78736B;   /* 灰文字 */
  --ink-4:     #A8A29A;   /* 极淡 (eyebrow, attribution) */
  --hair:      #D9D3C5;   /* 发丝线 */
  --hair-2:    #BFB7A4;   /* 强分隔线 */
  --gold:      #A98D5C;   /* 古金 - 主 accent */
  --gold-deep: #87703F;   /* 深古金 - hover */
  --gold-soft: #EFE8D3;   /* 古金底色 */
  --ink-paper: #0A0907;   /* 纯黑标题 */
  --serif: "Source Serif Pro", "Songti SC", "STSong", "Noto Serif SC", Georgia, "Times New Roman", serif;
  --sans:  -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Inter", sans-serif;
  --mono:  ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html {
  font-family: var(--sans);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--ink); background: var(--bg);
  scroll-behavior: smooth;
}
body { font-size: 16px; line-height: 1.85; letter-spacing: 0.005em; }
::selection { background: var(--gold-soft); color: var(--ink-paper); }

/* ── 顶部导航 (极简发丝线) ── */
.nav {
  position: sticky; top: 0; z-index: 50;
  background: rgba(251, 250, 246, 0.88);
  backdrop-filter: saturate(180%) blur(18px);
  -webkit-backdrop-filter: saturate(180%) blur(18px);
  border-bottom: 1px solid var(--hair);
}
.nav .wrap {
  max-width: 1100px; margin: 0 auto;
  display: flex; align-items: center; gap: 36px;
  padding: 18px 32px;
}
.nav .brand {
  font-family: var(--serif);
  font-weight: 500; font-size: 16px;
  letter-spacing: 0.04em;
  color: var(--ink-paper);
  display: flex; align-items: baseline; gap: 10px;
  text-decoration: none;
}
.nav .brand .logo {
  font-family: var(--serif);
  font-style: italic; font-weight: 400;
  font-size: 22px; color: var(--gold);
  letter-spacing: 0;
  line-height: 1;
}
.nav .brand .sep {
  display: inline-block; width: 1px; height: 12px;
  background: var(--hair-2); margin: 0 4px;
}
.nav .nav-link {
  font-size: 12.5px; color: var(--ink-3);
  font-weight: 500; text-decoration: none;
  letter-spacing: 0.06em;
  transition: color 0.2s;
}
.nav .nav-link:hover { color: var(--ink-paper); }
.nav .nav-spacer { flex: 1; }
.nav .cta {
  font-size: 12.5px; font-weight: 500;
  background: transparent;
  color: var(--ink-paper);
  padding: 9px 18px;
  border: 1px solid var(--ink-paper);
  text-decoration: none;
  letter-spacing: 0.08em;
  transition: all 0.2s;
}
.nav .cta:hover { background: var(--ink-paper); color: var(--bg); }

/* ── 主容器 (收窄到 editorial 阅读宽度) ── */
.wrap {
  max-width: 680px; margin: 0 auto;
  padding: 0 32px;
}
.wrap-wide {
  max-width: 920px; margin: 0 auto;
  padding: 0 32px;
}

/* ── Hero ── */
.hero {
  padding: 130px 0 100px;
  background: var(--bg);
  position: relative;
}
.hero::after {
  content: ''; position: absolute;
  bottom: 0; left: 50%; transform: translateX(-50%);
  width: 80px; height: 1px;
  background: var(--gold);
}
.hero .eyebrow {
  display: inline-flex; align-items: center; gap: 14px;
  font-size: 11px; font-weight: 500;
  color: var(--ink-4);
  margin-bottom: 36px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
}
.hero .eyebrow::before, .hero .eyebrow::after {
  content: ''; display: inline-block;
  width: 28px; height: 1px;
  background: var(--hair-2);
}
.hero h1 {
  font-family: var(--serif);
  font-size: 56px;
  line-height: 1.18;
  font-weight: 400;
  color: var(--ink-paper);
  letter-spacing: -0.012em;
  margin-bottom: 36px;
}
.hero h1 .accent {
  color: var(--ink-paper);
  font-style: italic;
  font-weight: 400;
}
.hero .lede {
  font-size: 18px;
  color: var(--ink-2);
  line-height: 1.85;
  margin-bottom: 56px;
  max-width: 600px;
  font-weight: 400;
}

/* ── 作者卡 (无 box, 一条左侧金线) ── */
.author-card {
  display: flex; gap: 24px; align-items: flex-start;
  padding: 20px 0 20px 24px;
  border-left: 1px solid var(--gold);
  margin-bottom: 64px;
}
.author-avatar {
  width: 52px; height: 52px;
  border-radius: 50%;
  background: var(--ink-paper);
  color: var(--gold);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--serif);
  font-size: 24px; font-style: italic; font-weight: 400;
  flex-shrink: 0;
  letter-spacing: 0;
}
.author-body { flex: 1; padding-top: 2px; }
.author-name {
  font-family: var(--serif);
  font-size: 17px; font-weight: 500;
  color: var(--ink-paper);
  margin-bottom: 4px;
  letter-spacing: 0.01em;
}
.author-title {
  font-size: 12px; color: var(--ink-4);
  font-weight: 500;
  letter-spacing: 0.04em;
}
.author-note {
  font-size: 14.5px; color: var(--ink-2);
  margin-top: 14px; line-height: 1.8;
}

/* ── 关键数字 (3 列, 无 box, 大衬线数字) ── */
.hero-nums {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0;
  margin-top: 48px;
  padding-top: 36px;
  border-top: 1px solid var(--hair);
}
.hero-num {
  padding: 8px 24px 8px 0;
  border-right: 1px solid var(--hair);
}
.hero-num:last-child { border-right: none; padding-right: 0; padding-left: 24px; }
.hero-num:first-child { padding-left: 0; }
.hero-num:nth-child(2) { padding-left: 24px; }
.hero-num .v {
  font-family: var(--serif);
  font-size: 42px; font-weight: 400;
  color: var(--ink-paper);
  line-height: 1;
  font-feature-settings: 'tnum';
  letter-spacing: -0.02em;
}
.hero-num .v .unit {
  font-size: 16px; color: var(--ink-3);
  font-weight: 400; margin-left: 3px;
  font-family: var(--serif); font-style: italic;
}
.hero-num .l {
  font-size: 12px; color: var(--ink-3);
  margin-top: 12px;
  font-weight: 400;
  line-height: 1.55;
  letter-spacing: 0.02em;
}

/* ── 章节通用 (大留白, 无背景切换, 编号导航) ── */
section.chapter {
  padding: 110px 0 100px;
  position: relative;
}
section.chapter + section.chapter {
  padding-top: 30px;
}
section.chapter::before {
  content: '';
  display: block;
  width: 40px; height: 1px;
  background: var(--gold);
  margin: 0 0 64px;
}
section.chapter.cream { background: var(--bg-2); }
section.chapter.cream::before { background: var(--gold-deep); }

.chapter-label {
  display: block;
  font-family: var(--serif);
  font-style: italic;
  font-size: 13px; font-weight: 400;
  color: var(--gold);
  letter-spacing: 0.08em;
  margin-bottom: 24px;
}
.chapter-label .num {
  font-family: var(--mono);
  font-style: normal;
  font-size: 11px;
  color: var(--ink-4);
  letter-spacing: 0.12em;
  margin-right: 10px;
}

.chapter h2 {
  font-family: var(--serif);
  font-size: 36px;
  line-height: 1.32;
  font-weight: 400;
  color: var(--ink-paper);
  letter-spacing: -0.015em;
  margin-bottom: 36px;
}

.chapter p {
  font-size: 17px;
  color: var(--ink-2);
  margin-bottom: 24px;
  line-height: 1.9;
  letter-spacing: 0.005em;
}
.chapter p:last-child { margin-bottom: 0; }
.chapter p b {
  color: var(--ink-paper); font-weight: 500;
  background: linear-gradient(transparent 60%, var(--gold-soft) 60%);
  padding: 0 2px;
}
.chapter p i {
  font-family: var(--serif);
  font-style: italic; color: var(--ink-paper);
  font-weight: 400;
  letter-spacing: 0.005em;
}
.chapter p code {
  background: var(--bg-2); color: var(--ink-paper);
  padding: 1px 7px;
  font-size: 14px;
  font-family: var(--mono);
  letter-spacing: 0;
  border: 1px solid var(--hair);
}

/* ── pull-quote (editorial 引言, 大字 + 衬线) ── */
.pull {
  margin: 48px -20px;
  padding: 36px 40px;
  border-top: 1px solid var(--gold);
  border-bottom: 1px solid var(--gold);
  font-family: var(--serif);
  font-size: 22px; color: var(--ink-paper);
  font-weight: 400;
  line-height: 1.6;
  letter-spacing: -0.005em;
  position: relative;
  background: transparent;
}
.pull::before {
  content: '\201C';
  font-family: var(--serif);
  font-size: 64px; color: var(--gold);
  position: absolute;
  top: 14px; left: 12px;
  line-height: 1;
  opacity: 0.4;
}
.pull.orange, .pull.green, .pull.yellow {
  border-top-color: var(--gold);
  border-bottom-color: var(--gold);
}
.pull-attr {
  font-family: var(--sans);
  font-size: 12px; color: var(--ink-4);
  font-weight: 500; margin-top: 18px;
  letter-spacing: 0.04em;
}

/* ── 受众卡 (3 列, 无 box, 罗马数字编号) ── */
.audience-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0;
  margin-top: 56px;
  border-top: 1px solid var(--hair);
}
.audience-card {
  padding: 36px 28px 28px 0;
  border-right: 1px solid var(--hair);
  transition: all 0.25s;
  position: relative;
}
.audience-card:last-child { border-right: none; padding-right: 0; padding-left: 28px; }
.audience-card:nth-child(2) { padding-left: 28px; padding-right: 28px; }
.audience-card .ic {
  font-family: var(--serif);
  font-style: italic; font-size: 36px;
  color: var(--gold);
  margin-bottom: 18px;
  letter-spacing: 0;
  line-height: 1;
  font-weight: 400;
}
.audience-card .who {
  font-family: var(--serif);
  font-size: 22px; font-weight: 400;
  color: var(--ink-paper); margin-bottom: 6px;
  letter-spacing: 0.005em;
}
.audience-card .what {
  font-size: 11px; color: var(--ink-4);
  font-weight: 500; margin-bottom: 18px;
  font-family: var(--sans);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.audience-card .need {
  font-size: 14.5px; color: var(--ink-2);
  line-height: 1.78;
}

/* ── 痛点 (编号 + 标签 + body) ── */
.pain-row {
  display: grid;
  grid-template-columns: 50px 170px 1fr;
  gap: 28px;
  padding: 36px 0;
  border-bottom: 1px solid var(--hair);
}
.pain-row:first-of-type { border-top: 1px solid var(--hair); margin-top: 40px; }
.pain-row:last-of-type { border-bottom: 1px solid var(--hair); }
.pain-no {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--ink-4);
  letter-spacing: 0.08em;
  padding-top: 6px;
}
.pain-tag {
  font-family: var(--serif);
  font-size: 17px; font-weight: 400;
  color: var(--ink-paper);
  letter-spacing: 0.005em;
  padding-top: 2px;
  line-height: 1.4;
}
.pain-tag .who {
  display: block; font-size: 10.5px; font-weight: 500;
  color: var(--gold-deep);
  margin-bottom: 8px;
  letter-spacing: 0.18em;
  font-family: var(--sans);
  text-transform: uppercase;
}
.pain-body {
  font-size: 15.5px; color: var(--ink-2);
  line-height: 1.85;
  padding-top: 4px;
}
.pain-body b {
  color: var(--ink-paper); font-weight: 500;
  background: linear-gradient(transparent 60%, var(--gold-soft) 60%);
}

/* ── 技术 5 步 (editorial timeline) ── */
.tech-steps {
  display: flex; flex-direction: column;
  gap: 0;
  margin-top: 56px;
  position: relative;
}
.tech-steps::before {
  content: '';
  position: absolute;
  left: 14px; top: 24px; bottom: 24px;
  width: 1px; background: var(--hair);
}
.tech-step {
  display: grid;
  grid-template-columns: 30px 1fr;
  gap: 28px;
  padding: 22px 0;
  align-items: flex-start;
  border-bottom: 1px solid var(--hair);
}
.tech-step:last-child { border-bottom: none; }
.tech-step .si {
  width: 30px; height: 30px;
  border-radius: 50%;
  background: var(--bg);
  border: 1px solid var(--gold);
  color: var(--gold-deep);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--serif); font-style: italic;
  font-size: 14px; font-weight: 400;
  flex-shrink: 0; z-index: 1;
  margin-top: 2px;
}
.tech-step .ti {
  font-family: var(--serif);
  font-size: 19px; font-weight: 400;
  color: var(--ink-paper); margin-bottom: 8px;
  letter-spacing: 0.005em;
}
.tech-step .ti .name { color: var(--ink-paper); font-weight: 500; }
.tech-step .ti .role { color: var(--ink-3); font-style: italic; font-weight: 400; }
.tech-step .td {
  font-size: 14.5px; color: var(--ink-2);
  line-height: 1.85;
}
.tech-step .td code {
  background: var(--bg-2); color: var(--ink-paper);
  padding: 1px 6px;
  font-size: 13px;
  font-family: var(--mono);
  border: 1px solid var(--hair);
}
.tech-step .td b {
  color: var(--ink-paper); font-weight: 500;
  background: linear-gradient(transparent 60%, var(--gold-soft) 60%);
}

/* 取舍 (2 列, picked vs dropped 形成对比) */
.tradeoff-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  margin-top: 40px;
  border-top: 1px solid var(--hair);
}
.tradeoff-card {
  padding: 28px 28px 28px 0;
  border-right: 1px solid var(--hair);
  border-bottom: 1px solid var(--hair);
  background: transparent;
}
.tradeoff-card:nth-child(2n) { padding-left: 28px; padding-right: 0; border-right: none; }
.tradeoff-card .lab {
  font-family: var(--mono);
  font-size: 10.5px; font-weight: 500;
  color: var(--ink-4);
  letter-spacing: 0.14em;
  margin-bottom: 12px;
  text-transform: uppercase;
}
.tradeoff-card .t {
  font-family: var(--serif);
  font-size: 16.5px; font-weight: 400;
  color: var(--ink-paper);
  margin-bottom: 10px;
  letter-spacing: 0.005em;
  line-height: 1.4;
}
.tradeoff-card .why {
  font-size: 13.5px; color: var(--ink-2);
  line-height: 1.75;
}
.tradeoff-card.pick .lab { color: var(--gold-deep); }
.tradeoff-card.pick .t::before {
  content: '— ';
  color: var(--gold);
  font-weight: 400;
}
.tradeoff-card.drop { opacity: 0.7; }
.tradeoff-card.drop .t {
  color: var(--ink-3);
  text-decoration: line-through;
  text-decoration-color: var(--hair-2);
  text-decoration-thickness: 1px;
}

/* ── 商业化时间表 (editorial 列) ── */
.bp-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0;
  margin-top: 56px;
  border-top: 1px solid var(--hair);
}
.bp-card {
  padding: 36px 24px 28px 0;
  border-right: 1px solid var(--hair);
  position: relative;
}
.bp-card:nth-child(2) { padding-left: 24px; padding-right: 24px; }
.bp-card:last-child { padding-left: 24px; padding-right: 0; border-right: none; }
.bp-card.now::before {
  content: '';
  position: absolute; top: -1px; left: 0;
  width: 40px; height: 1px; background: var(--gold);
}
.bp-stage {
  font-family: var(--mono);
  font-size: 11px; font-weight: 500;
  letter-spacing: 0.14em;
  margin-bottom: 10px;
  text-transform: uppercase;
  color: var(--gold-deep);
}
.bp-card.q3 .bp-stage  { color: var(--ink-3); }
.bp-card.q4 .bp-stage  { color: var(--ink-4); }
.bp-when {
  font-size: 12px; color: var(--ink-4);
  font-weight: 500; margin-bottom: 18px;
  letter-spacing: 0.04em;
}
.bp-what {
  font-family: var(--serif);
  font-size: 22px; font-weight: 400;
  color: var(--ink-paper); margin-bottom: 14px;
  line-height: 1.35;
  letter-spacing: -0.005em;
}
.bp-detail {
  font-size: 14px; color: var(--ink-2);
  line-height: 1.78;
}
.bp-detail b {
  color: var(--ink-paper); font-weight: 500;
  background: linear-gradient(transparent 60%, var(--gold-soft) 60%);
}
.bp-price {
  margin-top: 22px; padding-top: 18px;
  border-top: 1px solid var(--hair);
  font-size: 12px; color: var(--ink-3);
  letter-spacing: 0.02em;
}
.bp-price b {
  font-family: var(--mono);
  color: var(--ink-paper); font-weight: 500;
  letter-spacing: 0;
}

/* ── 市场数据 (大数字 + 衬线 + 无 box) ── */
.market-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  margin-top: 40px;
  border-top: 1px solid var(--hair);
  border-bottom: 1px solid var(--hair);
}
.market-card {
  padding: 32px 16px;
  border-right: 1px solid var(--hair);
  text-align: left;
}
.market-card:last-child { border-right: none; }
.market-card:not(:first-child) { padding-left: 24px; }
.market-v {
  font-family: var(--serif);
  font-size: 38px; font-weight: 400;
  color: var(--ink-paper);
  line-height: 1;
  font-feature-settings: 'tnum';
  letter-spacing: -0.02em;
}
.market-v .unit {
  font-size: 14px; color: var(--ink-3);
  font-weight: 400;
  font-family: var(--serif); font-style: italic;
  margin-left: 2px;
}
.market-l {
  font-size: 12px; color: var(--ink-3);
  margin-top: 14px;
  font-weight: 400;
  letter-spacing: 0.02em;
  line-height: 1.55;
}

/* ── 终 CTA (Brunello Cucinelli editorial close) ── */
.final-cta {
  padding: 140px 32px 120px;
  text-align: center;
  background: var(--ink-paper);
  color: var(--bg);
  position: relative;
}
.final-cta::before {
  content: '';
  display: block; width: 60px; height: 1px;
  background: var(--gold);
  margin: 0 auto 56px;
}
.final-cta h2 {
  font-family: var(--serif);
  font-size: 32px; font-weight: 400;
  color: var(--bg);
  margin-bottom: 24px;
  letter-spacing: -0.005em;
  line-height: 1.4;
  max-width: 560px; margin-left: auto; margin-right: auto;
}
.final-cta p {
  font-size: 15.5px; color: rgba(251, 250, 246, 0.65);
  max-width: 560px; margin: 0 auto 48px;
  line-height: 1.85;
  font-weight: 400;
}
.final-cta .btn-row {
  display: inline-flex; gap: 0;
  justify-content: center;
  flex-wrap: wrap;
}
.final-cta .btn-primary {
  display: inline-flex; align-items: center; gap: 12px;
  background: transparent;
  color: var(--bg);
  font-size: 13px; font-weight: 500;
  padding: 16px 36px;
  border: 1px solid var(--gold);
  text-decoration: none;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  transition: all 0.25s;
}
.final-cta .btn-primary:hover {
  background: var(--gold); color: var(--ink-paper);
}
.final-cta .btn-secondary {
  display: inline-flex; align-items: center; gap: 12px;
  background: transparent;
  color: rgba(251, 250, 246, 0.7);
  font-size: 13px; font-weight: 500;
  padding: 16px 36px;
  border: 1px solid rgba(251, 250, 246, 0.2);
  border-left: none;
  text-decoration: none;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  transition: all 0.25s;
}
.final-cta .btn-secondary:hover {
  background: rgba(251, 250, 246, 0.06);
  color: var(--bg);
  border-color: rgba(251, 250, 246, 0.4);
}

/* ── footer (极简) ── */
footer {
  padding: 36px 32px;
  text-align: center;
  font-size: 11px; color: var(--ink-4);
  background: var(--ink-paper);
  border-top: 1px solid rgba(251, 250, 246, 0.08);
  letter-spacing: 0.08em;
  font-family: var(--serif); font-style: italic;
}

/* ── Mobile (保持简奢气质, 单列 + 大留白) ── */
@media (max-width: 640px) {
  .nav .wrap { padding: 14px 20px; gap: 14px; }
  .nav .nav-link { display: none; }
  .nav .brand { font-size: 14px; }
  .wrap, .wrap-wide { padding: 0 24px; }
  .hero { padding: 80px 0 60px; }
  .hero h1 { font-size: 34px; }
  .hero .lede { font-size: 16px; margin-bottom: 36px; }
  .author-card { padding-left: 18px; gap: 16px; margin-bottom: 40px; }
  .author-avatar { width: 44px; height: 44px; font-size: 20px; }
  .hero-nums { grid-template-columns: 1fr; gap: 0; padding-top: 28px; }
  .hero-num { padding: 20px 0; border-right: none; border-bottom: 1px solid var(--hair); }
  .hero-num:last-child, .hero-num:nth-child(2), .hero-num:first-child { padding-left: 0; padding-right: 0; border-right: none; }
  .hero-num:last-child { border-bottom: none; }
  section.chapter { padding: 70px 0 60px; }
  section.chapter + section.chapter { padding-top: 0; }
  section.chapter::before { margin-bottom: 36px; }
  .chapter h2 { font-size: 26px; line-height: 1.35; }
  .chapter p { font-size: 16px; }
  .pull { margin: 36px -8px; padding: 28px 24px; font-size: 18px; }
  .pull::before { font-size: 48px; top: 10px; left: 8px; }
  .audience-grid { grid-template-columns: 1fr; border-top: none; }
  .audience-card { padding: 28px 0; border-right: none; border-bottom: 1px solid var(--hair); }
  .audience-card:last-child { padding-left: 0; border-bottom: none; }
  .audience-card:nth-child(2) { padding-left: 0; padding-right: 0; }
  .pain-row { grid-template-columns: 1fr; gap: 12px; padding: 28px 0; }
  .pain-no { padding-top: 0; }
  .tradeoff-grid { grid-template-columns: 1fr; border-top: none; }
  .tradeoff-card, .tradeoff-card:nth-child(2n) { padding: 24px 0; border-right: none; border-bottom: 1px solid var(--hair); padding-left: 0; padding-right: 0; }
  .tradeoff-card:last-child { border-bottom: none; }
  .bp-grid { grid-template-columns: 1fr; }
  .bp-card, .bp-card:nth-child(2), .bp-card:last-child { padding: 36px 0; border-right: none; border-bottom: 1px solid var(--hair); padding-left: 0; padding-right: 0; }
  .bp-card:last-child { border-bottom: none; }
  .market-grid { grid-template-columns: repeat(2, 1fr); }
  .market-card { padding: 28px 16px; }
  .market-card:not(:first-child) { padding-left: 16px; }
  .market-card:nth-child(2) { border-right: none; }
  .market-card:nth-child(3), .market-card:nth-child(4) { border-top: 1px solid var(--hair); }
  .market-card:nth-child(3) { border-right: 1px solid var(--hair); }
  .market-v { font-size: 30px; }
  .final-cta { padding: 90px 24px 80px; }
  .final-cta h2 { font-size: 24px; }
  .final-cta .btn-row { flex-direction: column; width: 100%; max-width: 320px; }
  .final-cta .btn-secondary { border-left: 1px solid rgba(251, 250, 246, 0.2); border-top: none; }
}
</style>
</head>
<body>

<!-- ─────────── 顶部导航 ─────────── -->
<nav class="nav">
  <div class="wrap" style="max-width:980px">
    <a class="brand" href="/alevel/">
      <span class="logo">A</span>
      <span class="sep"></span>
      <span>Level Assistant</span>
    </a>
    <a class="nav-link" href="/alevel/showcase">DEMO</a>
    <a class="nav-link" href="/alevel/showcase#multiagent">FIVE AGENTS</a>
    <a class="nav-link" href="/alevel/pitch" style="color:var(--ink-paper)">ABOUT</a>
    <span class="nav-spacer"></span>
    <a class="cta" href="/alevel/">TRY IT</a>
  </div>
</nav>

<!-- ─────────── Hero ─────────── -->
<section class="hero">
  <div class="wrap">
    <div class="eyebrow">产品负责人的话 &nbsp;·&nbsp; 2026 春</div>
    <h1>我做了个 A-Level 数学批改助手，<br><span class="accent">想认真讲讲它是怎么来的。</span></h1>
    <p class="lede">这一页不是落地页, 也不卖东西. 写给愿意花 5 分钟把产品听完的人 — 投资人、合作机构、同行、想加入团队的朋友. 我不堆模型黑话也不喊大词, 把怎么想的、给谁用的、技术怎么落地、钱怎么挣讲清楚, 你自己判断.</p>

    <div class="author-card">
      <div class="author-avatar">Z</div>
      <div class="author-body">
        <div class="author-name">朱传志 · 这个产品的设计 + 工程负责人</div>
        <div class="author-title">前互联网产品经理 / 全栈工程师 · 同时辅导 4 个 A-Level 学生中</div>
        <div class="author-note">辅导 4 年, 长期被一件事卡住 — 我跟学生每周只见 3 小时, 剩下 165 小时他自己摸索. 我想要一个能在我不在场时替我盯着他的工具. 找不到现成的, 就自己写了一个.</div>
      </div>
    </div>

    <div class="hero-nums">
      <div class="hero-num">
        <div class="v">~40<span class="unit">s</span></div>
        <div class="l">拍一页作业到拿到逐题反馈的时间</div>
      </div>
      <div class="hero-num">
        <div class="v">5<span class="unit">个</span></div>
        <div class="l">协作 agent · 切题 / 识别 / 判分 / 验算 / 记错</div>
      </div>
      <div class="hero-num">
        <div class="v">¥0.4<span class="unit">/题</span></div>
        <div class="l">单题真实成本 · 一节 1 对 1 课能批 200 道</div>
      </div>
    </div>
  </div>
</section>

<!-- ─────────── 1. 为什么做这个 ─────────── -->
<section class="chapter">
  <div class="wrap">
    <div class="chapter-label"><span class="num">I.</span>为什么做这个</div>
    <h2>每周只见学生 3 小时, 剩下 165 小时他在哪儿崩, 我完全不知道.</h2>
    <p>我带 A-Level 数学 1 对 1, 每个学生一周 2 节课, 每节 90 分钟. 加起来 <b>一周 3 小时</b> 我能陪在他旁边. 剩下 165 小时, 该刷的题他在刷, 该错的地方他在错, 我一概不知道. 等下次上课, 他把一摞作业本递过来, 我前 30 分钟得先翻一遍找他从第几行开始崩 — 这 30 分钟他付了课时费, 但对他来说几乎没有任何收获. 这件事难受了我很久.</p>

    <p>更难受的是学生<b>知道自己 "不会", 但说不清 "不会在哪"</b>. 他扔给 ChatGPT 一道题, ChatGPT 给一个完整的标准解 — 他看完仍然不会. 因为他需要的不是从头讲一遍, 是 "我第 6 行那步符号搞反了, 应该是 -6x 不是 8x+5". 这两件事是根本不同的需求, 模型不知道, 工具也没人做.</p>

    <div class="pull orange">
      做这个的起点很私人 — 我想要一个工具, 替我守着学生那 165 小时. 不是替我讲课, 是替我做那 30 分钟的<b>批改 + 错点定位</b>, 让我课上 90 分钟全用在真正辅导上.
      <div class="pull-attr">— 起念那天记在备忘录里的一句话, 2026-02</div>
    </div>

    <p>试了三个月. 最早就是个 ChatGPT prompt: 把作业拍照贴进去让 GPT-4 批一遍. 头一周看起来还行, 第二周问题就出来了 — GPT 会很自信地说 "你这步是对的", 但其实它根本没真算, 只是顺着学生的逻辑读了一遍, 觉得看着像对的. 数学题最忌讳这个. 那天我才明白: <i>这事得有个能真算的东西在模型背后兜底, 不能光靠它觉得</i>.</p>
  </div>
</section>

<!-- ─────────── 2. 给谁用 ─────────── -->
<section class="chapter cream">
  <div class="wrap">
    <div class="chapter-label"><span class="num">II.</span>给谁用</div>
    <h2>同一个产品, 三种不同的人在用 — 每种关心的事都不一样.</h2>
    <p>我们的判断是: <b>学生是真在用的, 家长是真在付的, 老师是把这事放大十倍的</b>. 这三方看的界面、用的功能、关心的指标都不一样. 任何一方掉链子, 整件事就不成立.</p>

    <div class="audience-grid">
      <div class="audience-card student">
        <div class="ic">i.</div>
        <div class="who">学生</div>
        <div class="what">拍照 · 看反馈 · 刷同型</div>
        <div class="need">不用预约, 不用等老师. 半夜做题卡住拍一下就有人接, 错点直接画在原图上. 同一个知识点错过几次系统记着.</div>
      </div>
      <div class="audience-card parent">
        <div class="ic">ii.</div>
        <div class="who">家长</div>
        <div class="what">付钱的人 · 想看到进度</div>
        <div class="need">每周自动收到一份学情简报, 写清这周做了几题、卡在什么知识点上、相比上周有没有进步. 这是真实做题数据, 不是老师感觉.</div>
      </div>
      <div class="audience-card teacher">
        <div class="ic">iii.</div>
        <div class="who">老师 / 机构</div>
        <div class="what">省时间 · 多带几个学生</div>
        <div class="need">系统先批一遍, 老师只看红色标记的几行. 一份作业从翻 30 分钟压到 5 分钟, 一节课多带 30% 的学生, 收入直接上去.</div>
      </div>
    </div>

    <p style="margin-top:28px">我们一开始只做学生侧, 把 "拍照 → 反馈" 这个核心闭环跑稳. 家长简报和老师工作台是 Q3 才接入的. <b>顺序不能反 — 学生用着糟糕, 家长付完一个月就退, 老师再多功能也撑不住</b>.</p>
  </div>
</section>

<!-- ─────────── 3. 解决的痛点 ─────────── -->
<section class="chapter">
  <div class="wrap">
    <div class="chapter-label"><span class="num">III.</span>解决的痛点</div>
    <h2>每一个痛点背后, 都是一笔正在被默默浪费的钱.</h2>

    <div class="pain-row">
      <div class="pain-no">i.</div>
      <div class="pain-tag student">
        <span class="who">学生侧</span>
        反馈延迟 1-3 天
      </div>
      <div class="pain-body">作业本周三晚上交上去, 周五上课才能看到批改. 中间这 48 小时, 错的知识点还在错的方向上加固印象. 我们能做到 <b>40 秒拿到逐题反馈</b>, 错点当场修, 第二天再做同型题验证一遍 — 完整学习闭环从 3 天压到 1 天.</div>
    </div>

    <div class="pain-row">
      <div class="pain-no">ii.</div>
      <div class="pain-tag student">
        <span class="who">学生侧</span>
        ChatGPT 只给标准答案
      </div>
      <div class="pain-body">学生要的不是 "答案是 T=(4, 17/4)", 是 "你第 6 行 <code>8x+5=4</code> 这步符号搞反了, 应该写成 <code>-6x=1</code>". 我们 OCR 把学生每一行 working 识别出来, 对照 Cambridge mark scheme 逐行判分, 错的那行<b>直接在原图上红框圈出来</b>.</div>
    </div>

    <div class="pain-row">
      <div class="pain-no">iii.</div>
      <div class="pain-tag parent">
        <span class="who">家长侧</span>
        付了钱看不到进度
      </div>
      <div class="pain-body">家长每月 4000-8000 块辅导费, 拿到的反馈往往只有一句 "今天讲了三道题". 这周到底进步多少、卡在哪、跟同年级比怎么样, 全靠老师感觉. 我们给家长一份<b>每周自动生成的学情简报</b>, 数据是真实做题统计, 不是口头汇报.</div>
    </div>

    <div class="pain-row">
      <div class="pain-no">iv.</div>
      <div class="pain-tag teacher">
        <span class="who">老师侧</span>
        同一道题批改 N 次
      </div>
      <div class="pain-body">同一道圆切线题, 我可能在 4 个学生身上各批一次, 70% 的错点都是同一个 — 符号搞反. 这 4 次本质是重复劳动. 我们让系统先批一遍, 老师只看那些<b>系统不确定的、或者错法不寻常的</b>题, 一节课能多带 30% 的学生.</div>
    </div>

    <div class="pull green">
      我们不打算解决 "教不会" 这件事 — 教学终归需要真人. 我们解决的是 <b>"教完了, 没人陪练" 这件事</b>. 这是 K12 辅导赛道最大的隐性成本, 没人想花这笔钱, 但每家都在花.
    </div>
  </div>
</section>

<!-- ─────────── 4. 技术方案 ─────────── -->
<section class="chapter soft">
  <div class="wrap">
    <div class="chapter-label"><span class="num">IV.</span>技术方案</div>
    <h2>5 个 agent 各管一段, 互相校验, 谁也别想偷懒.</h2>
    <p>这一节躲不开一些技术细节, 我尽量说人话. 最核心的一个判断是: <b>批改作业这件事, 一个大模型一次性干完不行</b>. 因为大模型容易 "自信地错" — 它会顺着学生写的过程读一遍, 看见 "x=-1/6" 就会说 "对的, 看着没毛病", 其实它根本没真算, 只是觉得这个看着合理. 数学题最怕这个.</p>

    <p>所以我们把整个批改拆成 5 个职责清楚的 agent. 每个只干一件事, 上一个的输出喂给下一个, 互相能挑出对方的毛病:</p>

    <div class="tech-steps">
      <div class="tech-step">
        <div class="si">i</div>
        <div>
          <div class="ti"><span class="name">Segmenter</span> &nbsp;<span class="role">— 切题专家</span></div>
          <div class="td">扫一眼整页作业, 告诉下游 "一共几道题, 哪道是这次的重点". 用 vision 模型直接出 bbox, 通常 1.5 秒.</div>
        </div>
      </div>
      <div class="tech-step">
        <div class="si">ii</div>
        <div>
          <div class="ti"><span class="name">OCR Agent</span> &nbsp;<span class="role">— 手写识别员</span></div>
          <div class="td">把学生每一行 working 还原出来. 不是印刷体 OCR, 是 <b>手写中英文 + 数学符号</b>, 难度高一个量级. 我们用 Viviai 上的 Gemini 视觉模型做切题和识别, 低置信度内容标红留人审.</div>
        </div>
      </div>
      <div class="tech-step">
        <div class="si">iii</div>
        <div>
          <div class="ti"><span class="name">Grader</span> &nbsp;<span class="role">— 批改老师</span></div>
          <div class="td">对照 Cambridge mark scheme 给分, 反馈精确到行. 关键: <b>它自己不算公式</b>. 凡是要真算的, 它都喊 Verifier — "这步我觉得学生错了, @Verifier 你用 SymPy 算一下标准答案是多少".</div>
        </div>
      </div>
      <div class="tech-step">
        <div class="si">iv</div>
        <div>
          <div class="ti"><span class="name">Verifier</span> &nbsp;<span class="role">— 独立审计员</span></div>
          <div class="td">这是兜底的一环. 凡是能用 <code>SymPy</code> 算的步骤 — 求导、解方程、积分、联立 — 都让 SymPy 真跑一次, 把结果跟 Grader 的判断对一遍. <b>谁说都不算, SymPy 算出来的才算</b>. 加这一层准确率从 85% 顶到 98%.</div>
        </div>
      </div>
      <div class="tech-step">
        <div class="si">v</div>
        <div>
          <div class="ti"><span class="name">Memory</span> &nbsp;<span class="role">— 学情记录员</span></div>
          <div class="td">每个学生在系统里有自己的 "错题脑". 这次的错点跟历史比一比 — 头一次错, 给答案加讲解; <b>同一类错点第 3 次了</b>, 系统自动切到 "苏格拉底反问", 不给答案逼学生自己想.</div>
        </div>
      </div>
    </div>

    <p style="margin-top:28px">5 个 agent 串起来一道题 8-15 秒, 一份整页作业 35-50 秒. 最早是 67 秒, 后来动了两个手脚: Grader 和 Verifier 互不依赖, 改成 <b>并行跑</b>; 用户进入 demo 区时<b>提前预热</b> OAuth session, 把冷启动那 8 秒提前消化掉. 现在稳定在 39 秒.</p>

    <h2 style="margin-top:48px;font-size:22px">几个关键取舍 — 为什么选这条, 为什么不选那条</h2>

    <div class="tradeoff-grid">
      <div class="tradeoff-card pick">
        <div class="lab">✓ 选了</div>
        <div class="t">codex CLI + ChatGPT Pro OAuth</div>
        <div class="why">MVP 阶段 token 不计费, 一个月跑几千次也只是 ChatGPT Pro 包月那 ¥160. 比走 API 便宜 20-50×.</div>
      </div>
      <div class="tradeoff-card drop">
        <div class="lab">✗ 没选</div>
        <div class="t">直接走 OpenAI API</div>
        <div class="why">单道题 5 个 agent 串起来 $0.3-0.8 · ¥2-6 / 题. 学生月付 ¥99 用 30 道就赔本.</div>
      </div>
      <div class="tradeoff-card pick">
        <div class="lab">✓ 选了</div>
        <div class="t">SymPy 真算兜底</div>
        <div class="why">数学题再大的模型也会自信地算错. 能符号化解的步骤都让 SymPy 跑一遍, 加这一层准确率 +13pp.</div>
      </div>
      <div class="tradeoff-card drop">
        <div class="lab">✗ 没选</div>
        <div class="t">大模型多次采样投票</div>
        <div class="why">又慢又贵, 且根本问题没解决 — 模型仍然没真算, 只是同一个错被投票投得更自信了.</div>
      </div>
      <div class="tradeoff-card pick">
        <div class="lab">✓ 选了</div>
        <div class="t">5 个 agent 流水线架构</div>
        <div class="why">职责清楚, 任一环节挂了能独立 fallback. 出 bug 一眼能定位是谁的锅, 拿出去演示也讲得清楚.</div>
      </div>
      <div class="tradeoff-card drop">
        <div class="lab">✗ 没选</div>
        <div class="t">一个超长 prompt 让 LLM 全干</div>
        <div class="why">prompt 越长输出越发散. 而且兜底那环没了, 又回到 "自信地错" 那个老坑.</div>
      </div>
      <div class="tradeoff-card pick">
        <div class="lab">✓ 选了</div>
        <div class="t">本地 Mac + frpc 反代到阿里云</div>
        <div class="why">codex OAuth 必须本地跑 (ChatGPT 服务器不让在 ECS 上认证), frpc 把本地 8000 反代到云 nginx. <b>MVP 服务器月成本 ¥30</b>.</div>
      </div>
      <div class="tradeoff-card drop">
        <div class="lab">✗ 没选</div>
        <div class="t">买云 GPU 自部署开源模型</div>
        <div class="why">月固定 ¥3000+, 不到 1000 用户根本摊不平. 等 PMF 验证完, Q4 再考虑迁过去.</div>
      </div>
    </div>
  </div>
</section>

<!-- ─────────── 5. 商业化规划 ─────────── -->
<section class="chapter">
  <div class="wrap">
    <div class="chapter-label"><span class="num">V.</span>商业化规划</div>
    <h2>三步走, 每一步都给自己设了一道明确的 "走得通" 门槛.</h2>
    <p>我对商业化的判断比较朴素: <b>K12 教育产品最忌讳一上来就铺渠道烧钱</b>. 得先在小批量真实用户身上跑出 retention, 不然预算再多, 烧出来的也是个空架子. 我们的节奏分三步:</p>

    <div class="bp-grid">
      <div class="bp-card now">
        <div class="bp-stage">现在 — 正在做</div>
        <div class="bp-when">2026 Q2 · MVP 内测</div>
        <div class="bp-what">免费, 但要登录</div>
        <div class="bp-detail">50-100 个内测学生 (我自己带的 4 个 + 朋友圈介绍). 单题免费试用, 整本作业每周 3 次. 这阶段就一个目标: <b>周留存 ≥ 40%</b>, 否则一切免谈.</div>
        <div class="bp-price">收入: <b>¥0</b> · 月成本: <b>¥80</b></div>
      </div>
      <div class="bp-card q3">
        <div class="bp-stage">下一步 — Q3 学生订阅</div>
        <div class="bp-when">2026 Q3 · C 端付费</div>
        <div class="bp-what">¥99 / 月 不限次</div>
        <div class="bp-detail">解锁不限次批改 + 错题本 + 个性化讲解视频 + 家长周报. 首月免费, 第二月开始扣. 目标: 半年内做到 <b>500 个付费用户, MRR ¥50K</b>.</div>
        <div class="bp-price">客单: <b>¥99</b> · LTV 估: <b>¥600</b></div>
      </div>
      <div class="bp-card q4">
        <div class="bp-stage">再下一步 — Q4 B 端 SaaS</div>
        <div class="bp-when">2026 Q4 · 机构 / 学校</div>
        <div class="bp-what">按学生数年付</div>
        <div class="bp-detail">面向辅导机构和国际学校做白标方案, ¥800-1500 / 学生 / 年. 配套老师批改工作台, 可以接学校自己的 mark scheme. 目标: 年底前 <b>签下 3 家机构</b>.</div>
        <div class="bp-price">机构客单: <b>¥30-200 万 / 年</b></div>
      </div>
    </div>

    <p style="margin-top:30px"><b>这个阶段我们暂时不接外部资本</b>. 不是不愿意聊, 是现在拿钱反而成本更高 — MVP 阶段 ChatGPT Pro 包月 + 阿里云 ECS, 月固定成本不到 ¥250. 一个人坐着就能把它跑起来. 等 Q3 付费数据出来, 单位经济模型跑通了, 再聊融资加速也不迟.</p>

    <h2 style="margin-top:48px;font-size:22px">市场到底有多大</h2>
    <p>下面几个数字是我们做盘子时的依据, 全是公开渠道可以查到的统计, 不是拍脑袋:</p>

    <div class="market-grid">
      <div class="market-card">
        <div class="market-v">10<span class="unit">万</span></div>
        <div class="market-l">中国大陆 A-Level 在校生 (2024)</div>
      </div>
      <div class="market-card">
        <div class="market-v">1000<span class="unit">+</span></div>
        <div class="market-l">国际学校 / A-Level 课程中心</div>
      </div>
      <div class="market-card">
        <div class="market-v">¥3-8<span class="unit">万</span></div>
        <div class="market-l">A-Level 学生年均辅导支出</div>
      </div>
      <div class="market-card">
        <div class="market-v">~30<span class="unit">亿</span></div>
        <div class="market-l">中国 A-Level 辅导市场年规模估算</div>
      </div>
    </div>

    <p style="margin-top:22px"><b>而这还只是 A-Level 一个科目</b>. 同样这套 5-agent 流水线, 换一份 mark scheme + 换一个题库, 就能直接复用到 IB、AP、DSE、SAT 数学 — 整个国际化教育赛道可触达市场 ~200 亿. 我们的打法是先把 A-Level 这块磨透, 再做横向扩展.</p>

    <div class="pull yellow">
      做大不靠堆人, 靠架构. 一个产品如果一开始就要 50 个人才能跑, 那它本身就有问题. 我们想要的是 <b>1 个人 100 个用户能跑, 5 个人 5000 个用户能跑</b> 的形态 — 不然再大的市场也消化不掉.
    </div>
  </div>
</section>

<!-- ─────────── 终 CTA ─────────── -->
<section class="final-cta">
  <h2>读到这里, 已经胜过 90% 的快速浏览者了.</h2>
  <p>不管你想内测试用、想谈机构合作、想加入团队, 还是只是单纯对 5 agent 这套工程实现感到好奇, 都直接找我聊. 邮件我自己回, 每一封都看.</p>
  <div class="btn-row">
    <a class="btn-primary" href="/alevel/showcase">SEE A FULL DEMO</a>
    <a class="btn-secondary" href="mailto:hi@example.com">WRITE TO ME</a>
  </div>
</section>

<footer>
  Anno MMXXVI &nbsp;·&nbsp; A-Level Assistant &nbsp;·&nbsp; private beta
</footer>

</body>
</html>
"""
