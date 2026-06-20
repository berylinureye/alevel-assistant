# A-Level 作业助手 · 运行说明

这个包已经包含了编译好的前端（`frontend/dist/`），直接跑 `python server.py` 就能同时服务前端和后端（单端口）。

**前端打包时 API 地址已置空，使用相对路径** —— 所以你本地跑 server.py 时，所有 API 调用都打到你本地后端，不会跑去线上旧版。手机访问你电脑 IP 也一样。部署到任何域名也都自动生效。

**部署到线上看** `DEPLOY.md`。本文档是本地运行流程。

## 第一次运行

```bash
# 1. 进入项目目录（解压后的文件夹）
cd alevel-assistant

# 2. 配置环境变量 —— 填入你的大模型 API Key
cp .env.example .env
# 用任何编辑器打开 .env，至少需要填：
#   ANTHROPIC_API_KEY=sk-xxx
#   ANTHROPIC_BASE_URL=https://api.viviai.cc
#
# 直连 DASHSCOPE / DEEPSEEK / GLM 现在是可选备用项。

# 3. 安装后端 Python 依赖
pip install -r requirements.txt

# 4. 启动
python server.py
```

打开浏览器访问 **http://localhost:8000** —— 看到主界面就 OK。

## 后续运行

只要 `.env` 没动、依赖没变，每次启动只需：

```bash
cd alevel-assistant
python server.py
```

## 端口

默认 `8000`。如果被占用：

```bash
PORT=8001 python server.py
```

## 如果改了前端代码

前端是编译后的静态文件（`frontend/dist/`），想改代码的话需要重新构建：

```bash
cd frontend
npm install       # 只第一次需要
npm run build     # 产出新的 dist/
cd ..
python server.py
```

或者开前端 dev server 单独调（两个终端）：

```bash
# 终端 1：后端
python server.py

# 终端 2：前端 dev（支持热更新）
cd frontend && npm run dev
# 访问 http://localhost:3000
```

## 排查常见问题

- **打开页面显示 `{"detail":"Not Found"}`**
  前端 `dist/` 没有被正确识别。访问 `http://localhost:8000/__debug_fs` 看 `dist_exists` 是否为 `true`。

- **批改时报 API Key 错**
  检查 `.env` 里对应的 key 是否填了。访问 `http://localhost:8000/__debug_keys` 可以查看哪些 key 被识别到。

- **前端拿不到数据**
  确认前后端是同一个域名+端口（用方案 A 的话这是默认）。跨域的话需要在 `.env` 加 `ALLOWED_ORIGINS=http://your-frontend-domain`。

## 不打算在里面的功能

- **封面页（landing page）** 还在打磨，代码包在里面但默认路由不会跳去。如果想预览，访问 `http://localhost:8000/landing`。

---

生成时间：2026-04-18
