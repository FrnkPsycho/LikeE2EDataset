#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_agent.py — 被测方 agent+model 连通性自检。

给 agent 一个最小任务（输入 "hi"），验证三件事：
  1. agent 镜像 + harness（codex/qwencode）能起；
  2. 模型端点能通、API key 有效；
  3. 模型能响应、agent 能按指令产出。

跑完整评测前先跑这个——否则模型连不上，会白等 1 小时才发现。
本检查直连模型端点（不起 egress 白名单代理），只测「agent+model 本身通不通」。

用法：
  python check_agent.py                 # 用 team.env 的 AGENT + MODEL_*
  python check_agent.py --agent codex   # 强制指定 agent
  python check_agent.py --timeout 180   # 超时（默认 120s）
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

DATASET_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.join(DATASET_DIR, "agent")
IMAGE = "datasetlikee2e/agent:v1"
DEFAULT_TEAM_ENV = os.path.join(DATASET_DIR, "team.env")


def parse_env(path):
    kv = {}
    if not os.path.isfile(path):
        return kv
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                kv[k.strip()] = v.strip()
    return kv


def build_task(timeout):
    return {
        "case_id": "connectivity-check",
        "mode": "whitebox",
        "role": "attacker",
        "timeout": timeout,
        "task": {
            "goal": "这是连通性测试。收到这则输入后，在 /submission/whitebox/poc.bin 里写入 "
                    "hi 两个字母，表示你已收到。不要做任何其它分析或动作。"
        },
        "output": {"/submission/whitebox/poc.bin": "内容为 hi"},
    }


def main():
    # Windows GBK 控制台编不了 stderr 里的非 ASCII 字符，先放宽 stdout/stderr
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="agent+model 连通性自检")
    ap.add_argument("--timeout", type=int, default=120, help="等模型响应的超时秒数")
    ap.add_argument("--team-env", default=DEFAULT_TEAM_ENV)
    ap.add_argument("--agent", default=None, choices=["codex", "qwencode", "custom"],
                    help="强制指定 agent（缺省读 team.env 的 AGENT）")
    a = ap.parse_args()

    team = parse_env(a.team_env)
    agent = a.agent or team.get("AGENT") or "codex"
    model = {
        "OPENAI_BASE_URL": team.get("MODEL_BASE_URL"),
        "OPENAI_API_KEY": team.get("MODEL_API_KEY"),
        "OPENAI_MODEL": team.get("MODEL_NAME"),
    }

    if not model["OPENAI_API_KEY"]:
        print("[check] team.env 缺 MODEL_API_KEY，无法测模型连通性")
        return 1
    if not model["OPENAI_MODEL"]:
        print("[check] team.env 缺 MODEL_NAME")
        return 1

    # 0. agent 镜像在不在
    r = subprocess.run(["docker", "image", "inspect", IMAGE],
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print(f"[check] agent 镜像 {IMAGE} 不存在，先 docker build（或 host_run --build）")
        return 1

    ep = os.path.join(AGENT_DIR, f"entrypoint.{agent}.sh")
    if not os.path.isfile(ep):
        print(f"[check] 没有 entrypoint：{ep}")
        return 1

    # 1. 写最小 task.json
    tmp = tempfile.mkdtemp(prefix="check_agent_")
    task_path = os.path.join(tmp, "task.json")
    with open(task_path, "w", encoding="utf-8") as f:
        json.dump(build_task(a.timeout), f, ensure_ascii=False, indent=2)

    out_dir = tempfile.mkdtemp(prefix="check_out_")
    container = f"agent-check-{uuid.uuid4().hex[:8]}"

    cmd = ["docker", "run", "--name", container,
           "-v", f"{ep}:/challenge/agent/entrypoint.sh:ro",
           "-v", f"{task_path}:/challenge/task.json:ro",
           "-v", f"{os.path.join(AGENT_DIR, 'prompt.py')}:/opt/agent/prompt.py:ro",
           "-v", f"{out_dir}:/submission"]
    for k, v in model.items():
        if v:
            cmd += ["-e", f"{k}={v}"]
    cmd += [IMAGE, "--mode", "whitebox", "--role", "attacker",
            "--task", "/challenge/task.json", "--output", "/submission/",
            "--timeout", str(a.timeout)]

    print(f"[check] agent={agent} model={model['OPENAI_MODEL']}，输入 hi，"
          f"等响应（超时 {a.timeout}s）…")
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                           timeout=a.timeout + 120)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)
        print(f"[check] FAIL：agent 容器 {a.timeout + 120}s 内没退出（模型无响应或卡死）")
        return 1
    elapsed = time.time() - t0

    # 2. 看结果：agent 是否按指令写了 hi
    poc = os.path.join(out_dir, "whitebox", "poc.bin")
    ok = os.path.isfile(poc) and "hi" in open(poc, encoding="utf-8", errors="replace").read()

    subprocess.run(["docker", "rm", "-f", container], capture_output=True)

    if ok:
        print(f"[check] PASS：agent+model 可用（{elapsed:.0f}s 内收到 hi 回复，poc.bin 已写 hi）")
        return 0

    print(f"[check] FAIL：agent 未在 {a.timeout}s 内正确响应（退出码 {r.returncode}）")
    if r.stdout:
        print("  --- stdout 末尾 ---\n" + r.stdout[-800:])
    if r.stderr:
        print("  --- stderr 末尾 ---\n" + r.stderr[-800:])
    print("  常见原因：")
    print("    1) 模型端点不通 / API key 错 —— 直接 curl 一下 MODEL_BASE_URL 验证；")
    print("    2) 协议不匹配：codex 要 responses 协议，若端点只给 chat completions，换 --agent qwencode；")
    print("    3) 模型名写错（MODEL_NAME 与端点实际模型不一致）。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
