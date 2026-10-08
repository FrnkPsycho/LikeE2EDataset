# agent/Dockerfile — 预置开源 agent 的参赛者容器镜像（benchmark 通用基础设施，独立于赛题）
#
# 预置两个开源 agent CLI，参赛队 option 1 直接「用预置 agent + 接自己的模型」：
#   - Codex CLI（OpenAI，Apache-2.0）：`codex exec "<task>"` 无头跑题
#   - Qwen Code（阿里，Gemini CLI 活 fork）：`qwen -p "<task>" --approval-mode=yolo`
#
# 参赛队 option 2 也可复用此镜像：把自研 harness 挂到 /challenge/agent/ 覆盖 entrypoint 即可。
# 本镜像不含任何赛题相关内容；赛题只提供 task.json + 源码/日志挂载，见 host_run.py。
FROM node:22-slim

# 两个开源 agent CLI（均为 npm 包，需要 Node 22+）
RUN npm install -g @openai/codex @qwen-code/qwen-code

# git（codex/qwen-code 做仓库与补丁操作）+ python3（跑 prompt.py 生成任务指令）
# + ca-certificates（TLS）+ curl（黑盒攻击者经网关发 HTTP 请求；联网搜索由 egress 代理拦截）
RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# 组织方固定启动器：标准接口的容器侧 seam（所有参赛队共用，不可改）
COPY run_agent.sh /usr/local/bin/run_agent.sh
RUN chmod +x /usr/local/bin/run_agent.sh

# 参考 entrypoint（option 1）：把标准接口参数转成 codex / qwen-code 调用
COPY entrypoint.codex.sh   /opt/agent/entrypoint.codex.sh
COPY entrypoint.qwencode.sh /opt/agent/entrypoint.qwencode.sh
COPY prompt.py             /opt/agent/prompt.py
RUN chmod +x /opt/agent/entrypoint.codex.sh /opt/agent/entrypoint.qwencode.sh

# agent 的工作目录（读源码/写临时文件都在这里；/submission 由宿主挂载）
WORKDIR /workspace

# 默认入口 = 标准接口启动器。宿主 docker run 时传 --mode/--role/--task/--output/--timeout
ENTRYPOINT ["/usr/local/bin/run_agent.sh"]
