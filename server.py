"""uvicorn 启动入口（本地开发用，生产环境由 render.yaml 的 startCommand 启动）"""
import logging
import os
import uvicorn

if __name__ == "__main__":
    # Enable INFO-level logging so verifier / grader / segmenter logs surface in stdout.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "urllib3", "watchfiles"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api.app:app", host="0.0.0.0", port=port, reload=True)
