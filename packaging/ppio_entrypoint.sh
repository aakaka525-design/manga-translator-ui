#!/bin/bash
# PPIO Serverless 两阶段启动脚本
# 阶段1: 立刻启动轻量 HTTP 服务通过健康检查
# 阶段2: 后台启动完整 uvicorn, 就绪后用 socat 转发端口

PORT="${PORT:-8080}"
UVICORN_PORT=$((PORT + 1))
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3-flash-preview}"
export GEMINI_FALLBACK_MODEL="${GEMINI_FALLBACK_MODEL:-gemini-2.5-flash}"

echo "[entrypoint] Starting two-phase boot: phase1=$PORT -> uvicorn=$UVICORN_PORT" >&2

# ─── 阶段1: 极简 HTTP 健康检查 server ───
python3 -c "
import http.server, json

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'warming_up'}).encode())
    def do_POST(self):
        self.send_response(503)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'warming_up'}).encode())
    def log_message(self, *a): pass

http.server.HTTPServer(('0.0.0.0', $PORT), H).serve_forever()
" &
PHASE1_PID=$!
sleep 1
echo "[entrypoint] Phase 1 health server started (PID=$PHASE1_PID)" >&2

# ─── 阶段2: 启动完整 uvicorn（最终 port，不会再杀重启） ───
echo "[entrypoint] Phase 2: starting uvicorn on port $UVICORN_PORT..." >&2

uvicorn manga_translator.server.cloudrun_compute_main:app \
    --host 127.0.0.1 \
    --port "$UVICORN_PORT" \
    --log-level info &
UVICORN_PID=$!

# 轮询等待 uvicorn 就绪（模型加载完成）
echo "[entrypoint] Waiting for uvicorn model loading..." >&2
MAX_WAIT=300
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    RESP=$(curl -s "http://127.0.0.1:$UVICORN_PORT/" 2>/dev/null || echo "")
    if echo "$RESP" | grep -q '"ok"'; then
        echo "[entrypoint] Uvicorn ready after ${WAITED}s! Switching traffic..." >&2
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo "[entrypoint] ERROR: Uvicorn failed within ${MAX_WAIT}s" >&2
    kill $PHASE1_PID $UVICORN_PID 2>/dev/null
    exit 1
fi

# ─── 切换: 杀掉 phase1, 用 socat 把 $PORT 转发到 uvicorn 的 $UVICORN_PORT ───
kill $PHASE1_PID 2>/dev/null
wait $PHASE1_PID 2>/dev/null

echo "[entrypoint] Forwarding port $PORT -> $UVICORN_PORT via socat" >&2
exec socat TCP-LISTEN:${PORT},fork,reuseaddr TCP:127.0.0.1:${UVICORN_PORT}
