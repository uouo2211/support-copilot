#!/usr/bin/env bash
# DataPilot 客服助手演示 —— 一键启动
#
# 首次运行会自动完成：定位合适的 Python → 建虚拟环境 → 装依赖 → 生成配置 → 导入演示数据。
# 之后每次运行只做必要检查，然后直接启动服务。
#
# 用法：./start_demo.sh              （默认 http://127.0.0.1:8000）
#       PORT=9000 ./start_demo.sh
set -euo pipefail

cd "$(dirname "$0")"
PORT="${PORT:-8000}"
VENV=".venv"

version_ok() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
}

# 项目用了 str | None 这类注解，需要 Python 3.11+（macOS 自带 3.9 不支持）。
# 只用 PATH 查找与 $HOME 推导，不写死任何一台机器的绝对路径。
find_python() {
  local candidate
  for candidate in \
    python3.13 python3.12 python3.11 \
    "$HOME/.workbuddy/binaries/python/versions/3.13.12/bin/python3" \
    /opt/homebrew/bin/python3.13 /usr/local/bin/python3.13 \
    /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 \
    /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11 \
    python3
  do
    if command -v "$candidate" >/dev/null 2>&1 || [ -x "$candidate" ]; then
      if version_ok "$candidate"; then
        echo "$candidate"
        return
      fi
    fi
  done
  echo ""
}

if [ ! -x "$VENV/bin/python" ]; then
  PYTHON="$(find_python)"
  if [ -z "$PYTHON" ]; then
    echo "✗ 没找到 Python 3.11 或更高版本（本机 $($([ -x /usr/bin/python3 ] && echo /usr/bin/python3 || echo python3) --version 2>&1 || echo '未知') 版本过低）。"
    echo "  安装后再试：brew install python@3.13   或   https://www.python.org/downloads/"
    exit 1
  fi
  echo "→ 首次运行，正在创建虚拟环境（$("$PYTHON" --version 2>&1)）…"
  "$PYTHON" -m venv "$VENV"
  echo "→ 安装依赖，约需一分钟…"
  "$VENV/bin/pip" install -q --disable-pip-version-check -r requirements-demo.txt
fi

if [ ! -f .env ]; then
  echo "→ 生成配置文件 .env"
  cp .env.example .env
fi

if [ ! -f demo.db ]; then
  echo "→ 首次运行，导入演示数据…"
  "$VENV/bin/python" -m scripts.seed_demo
fi

echo "→ 服务启动：http://127.0.0.1:$PORT"
echo "  停止服务请按 Ctrl+C"
exec "$VENV/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
