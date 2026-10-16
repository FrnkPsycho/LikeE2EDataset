#!/usr/bin/env bash
# entrypoint.codex.sh — 参考 entrypoint（option 1 预置 Codex）
#
# 把标准接口参数转成 `codex exec` 无头调用。模型访问走 OPENAI_* 环境变量，
# 由宿主注入（OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL）。
set -euo pipefail

TASK=""
while [ $# -gt 0 ]; do
  case "$1" in
    --task) TASK="$2"; shift 2 ;;
    *) shift ;;
  esac
done
[ -n "$TASK" ] || { echo "[codex] 缺少 --task 参数" >&2; exit 2; }

# 生成 codex 配置：自定义模型端点（OpenAI 兼容）。
# 注意：codex 当前版本要求 wire_api="responses"（不是 chat）；若端点只提供
# chat completions（部分国产端点），建议改用 Qwen Code（走 chat 协议）。
#
# 下面两个开关的默认值是评测口径的一部分，不要删：
#
#   model_reasoning_effort —— codex 只对内置元数据认识的模型名决定推理强度，
#     遇到不认识的模型名（国产端点常见）回落到 "none"，等于把推理模型的思维链
#     整个关掉，评测会系统性低估推理型模型。默认给 high。端点不接受 reasoning
#     参数时用 CODEX_REASONING_EFFORT 覆盖（如设成 none 回到旧行为）。
#
#   web_search —— codex 默认开启联网搜索，而且这个工具由**模型服务端**执行，
#     不经过本容器的 egress 代理，所以题目侧的网络隔离拦不住它（实测能搜到
#     上游公告与 oss-security 邮件列表）。评测要防「搜到现成 PoC」，默认关掉。
#     确实要放开的用 CODEX_WEB_SEARCH 覆盖（live / indexed / cached / disabled）。
mkdir -p ~/.codex
cat > ~/.codex/config.toml <<EOF
model = "${OPENAI_MODEL:-gpt-5}"
model_provider = "bench"
model_reasoning_effort = "${CODEX_REASONING_EFFORT:-high}"
web_search = "${CODEX_WEB_SEARCH:-disabled}"

[model_providers.bench]
name = "bench"
base_url = "${OPENAI_BASE_URL:-https://api.openai.com/v1}"
env_key = "OPENAI_API_KEY"
wire_api = "responses"
EOF

PROMPT="$(python3 /opt/agent/prompt.py "$TASK")"

cd /workspace
# --skip-git-repo-check：/workspace 非 git 仓库时跳过仓库校验。
# --dangerously-bypass-approvals-and-sandbox：无头跑必须。关掉 codex 内部 bwrap
#   沙箱 + 审批提示，否则容器内会因「bwrap 无法建命名空间 / approval policy is
#   Never」卡死。官方说明本 flag「专为外部已沙箱化的环境」设计——外层 Docker
#   的网络/权限隔离才是 benchmark 真正的边界。
#
# 输出同时落一份到 /tmp/agent_run.log：跑完要据此区分「agent 没做出来」和
# 「设施坏了」。模型额度用尽、DNS 挂掉这类错误不写盘的话，agent 会静悄悄退出，
# 评测器只看到「没有交付物」→ 判 0 分，把环境问题记到被测方头上。
RUN_LOG=/tmp/agent_run.log
set -o pipefail
codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox "$PROMPT" 2>&1 | tee "$RUN_LOG"
rc=${PIPESTATUS[0]}

# 设施级错误的特征。只认「模型侧调不通」这一类（额度/限流/DNS），刻意不含
# connection refused / 401 / 403 —— 那些在打目标时是正常现象，认了会误判。
if grep -qiE "quota exceeded|insufficient_quota|insufficient quota|rate limit|too many requests|could not resolve host|network is unreachable" "$RUN_LOG"; then
    echo "[codex] 检测到设施级错误（模型额度 / 网络），退出码 3 = 设施失败，不计入成绩" >&2
    exit 3
fi
exit "$rc"
