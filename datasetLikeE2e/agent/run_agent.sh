#!/usr/bin/env bash
# run_agent.sh — 标准接口的容器侧启动器（组织方固定，所有参赛队共用，不可改）
#
# 宿主通过 docker run 调用：
#   docker run --rm <agent_image> run_agent.sh \
#       --mode whitebox|blackbox --role attacker|defender \
#       --task /challenge/task.json --output /submission/ --timeout 1800
#
# 职责：
#   1. 校验 /challenge/agent/entrypoint.sh 存在且可执行（做题方交付的 harness 入口）
#   2. 用 `timeout` 兜底执行上限（--timeout），到点返回 124
#   3. 原样把参数转发给 entrypoint.sh，并透传退出码：0 = 正常完成，非 0 = 该阶段记 0 分
set -euo pipefail

ENTRYPOINT="/challenge/agent/entrypoint.sh"
ALL_ARGS=("$@")
TIMEOUT=1800

# 只从参数里提取 --timeout 计算超时；其余参数原样透传（entrypoint 自行解析）
prev=""
for a in "${ALL_ARGS[@]}"; do
  if [ "$prev" = "--timeout" ]; then TIMEOUT="$a"; fi
  prev="$a"
done

if [ ! -x "$ENTRYPOINT" ]; then
  echo "[run_agent] 缺少可执行的 /challenge/agent/entrypoint.sh（做题方交付的 harness 入口）" >&2
  exit 2
fi

# timeout -k 10：到点后 10s 强杀；退出码透传（timeout 到点返回 124）
exec timeout -k 10 "$TIMEOUT" "$ENTRYPOINT" "${ALL_ARGS[@]}"
