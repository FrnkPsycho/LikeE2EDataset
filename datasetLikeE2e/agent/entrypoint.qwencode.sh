#!/usr/bin/env bash
# entrypoint.qwencode.sh — 参考 entrypoint（option 1 预置 Qwen Code）
#
# 把标准接口参数转成 `qwen -p` 无头调用。Qwen Code 直接读 OPENAI_* 环境变量
# （OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL），也兼容 ANTHROPIC_* / GEMINI_*。
set -euo pipefail

TASK=""
while [ $# -gt 0 ]; do
  case "$1" in
    --task) TASK="$2"; shift 2 ;;
    *) shift ;;
  esac
done
[ -n "$TASK" ] || { echo "[qwen-code] 缺少 --task 参数" >&2; exit 2; }

PROMPT="$(python3 /opt/agent/prompt.py "$TASK")"

# --approval-mode=yolo：无头自动批准所有工具调用（bash/写文件等）。
# 抑制 yolo 的 stderr 告警，避免污染退出码判定。
export QWEN_CODE_SUPPRESS_YOLO_WARNING=1

cd /workspace
exec qwen --approval-mode=yolo -p "$PROMPT"
