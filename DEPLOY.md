# 部署指南

这个包是 **deploy-ready** 的:
- 前端已经编译好,在 `frontend/dist/`
- 前端 bundle 用**相对路径**调 API,所以部署到哪个域名都自动适配
- 后端 FastAPI 启动时会自动把 `frontend/dist/` 挂载成静态文件,**单端口同时服务前后端**

## 方案 A:腾讯 CloudBase / 任何支持 Dockerfile 的 PaaS

项目根目录已有 `Dockerfile`,可以直接部署。

```bash
# 本机先测一下 docker build 没问题
docker build -t alevel-assistant .
docker run -p 8000:8000 --env-file .env alevel-assistant
# 访问 http://localhost:8000 测通后再推
```

上线到腾讯 CloudBase:
1. 在 CloudBase 控制台创建"云托管"服务
2. 上传这个项目目录(不要 node_modules / .git)
3. 控制台配置环境变量:
   - `ANTHROPIC_API_KEY`(Viviai / New API key)
   - `ANTHROPIC_BASE_URL=https://api.viviai.cc`
   - `PORT`(CloudBase 默认 80,如果它强制就用 80;否则 8000)
   - `ALLOWED_ORIGINS=*`(或者写你前端绑的域名)
4. 触发部署,几分钟后拿到一个 `xxx.run.tcloudbase.com` 域名
5. 浏览器访问那个域名,应该直接看到主界面

## 方案 B:Render / Railway / 其他 Python PaaS

项目根目录有 `render.yaml`,直接连 GitHub 仓库即可。或者:

- **启动命令**: `uvicorn api.app:app --host 0.0.0.0 --port $PORT`
- **构建命令**: `pip install -r requirements.txt`
- **环境变量**: 同上(三个 API key + PORT)

## 方案 C:自有服务器 / VPS

```bash
# 在服务器上
unzip alevel-assistant-<stamp>.zip
cd alevel-assistant

# 装 Python 依赖
pip3 install -r requirements.txt

# 配置 .env
cp .env.example .env
# vim .env  填 keys

# 后台跑
nohup python3 server.py > server.log 2>&1 &

# 或者用 systemd / supervisor / pm2 管理
```

## 环境变量速查

| Key | 必填? | 说明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 是 | Viviai / New API key |
| `ANTHROPIC_BASE_URL` | 是 | `https://api.viviai.cc` |
| `DASHSCOPE_API_KEY` | 否 | 阿里百炼(Qwen 系列)直连备用 |
| `DEEPSEEK_API_KEY` | 否 | DeepSeek 直连备用 |
| `GLM_API_KEY` | 否 | 智谱 AI(GLM 系列)直连备用 |
| `PORT` | 否 | 默认 8000,PaaS 通常自动注入 |
| `ALLOWED_ORIGINS` | 建议 | 前端域名,`*` 或精确写(如 `https://foo.com`) |
| `REVIEW_MODEL` | 否 | 默认 `gemini-3-pro-preview` |
| `SOLUTION_MODEL` | 否 | 同上,解题思路的 fallback 模型 |

## 部署后验证

```bash
# 健康检查
curl https://your-domain/health
# → {"status":"ok"}

# 确认前端挂上了
curl -I https://your-domain/
# → 200,返回 HTML

# 确认 API key 都被识别
curl https://your-domain/__debug_keys
# → 三个主要 key 都 set:true
```

## 线上建议

1. **关掉 `__debug_fs` 和 `__debug_keys` 两个 debug endpoint**:生产环境不该暴露这些。在 `api/app.py` 里注释掉或加条件 `if os.environ.get("DEBUG")`.
2. **设 `ALLOWED_ORIGINS` 为精确域名**,不要 `*`,减少 CORS 风险
3. **注意 API 账号配额**:
   - Viviai / New API 的模型池和限流以控制台为准
   - 多 agent 会并发调用多个模型,注意账户额度和 QPM
4. **监控日志**,特别关注 `Agent xxx attempt n failed` 之类的 WARNING,如果频繁说明账号配额或网络有问题
5. **首次部署后做一次真实作业测试**,确认批改路径通

## 回退

如果线上出问题要回退:
- 任何时候重新上传这个 zip 包就行
- 也可以保留之前那个工作的 zip 做备份

---

生成时间:2026-04-18
