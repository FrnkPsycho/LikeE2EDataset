#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_task.py — 通用：把「赛题的 agent 任务规格」+ role/mode 组合成标准接口 task.json。

通用（独立于赛题）：赛题只需提供一份 agent_task.json（见 samples/*/agent_task.json，位于赛题根目录），
本模块把它与 --mode/--role 组合，产出标准接口输入 task.json，再交给 prompt.py 渲染。

用法：
  python gen_task.py --spec <case>/agent_task.json \
      --mode whitebox|blackbox --role attacker|defender [--timeout 1800] [--out task.json]
"""
import argparse
import json


def load_spec(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build(spec: dict, mode: str, role: str, timeout: int = 1800,
          phase: str | None = None) -> dict:
    """spec 里按 f"{mode}_{role}" 命名角色条目（whitebox_attacker /
    blackbox_defender）。同一个角色可以分阶段定义（如黑盒防御者的
    blackbox_defender_s5 / _s6），此时 phase 决定取哪一段。"""
    key = f"{mode}_{role}" + (f"_{phase}" if phase else "")
    roles = spec.get("roles", {})
    if key not in roles:
        key = f"{mode}_{role}"
    if key not in roles:
        raise SystemExit(f"该赛题未定义 role 组合: {key}")
    s = roles[key]
    return {
        "case_id": spec.get("case_id"),
        "mode": mode,
        "role": role,
        "phase": phase,
        "timeout": timeout,
        "task": {k: v for k, v in s.items() if k != "output"},
        "output": s["output"],
    }


def main():
    ap = argparse.ArgumentParser(description="生成标准接口 task.json（通用）")
    ap.add_argument("--spec", required=True, help="赛题的 agent_task.json 路径")
    ap.add_argument("--mode", required=True, choices=["whitebox", "blackbox"])
    ap.add_argument("--role", required=True, choices=["attacker", "defender"])
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--phase", default=None, help="同一角色的阶段条目后缀（如 s5 / s6）")
    ap.add_argument("--out", default=None, help="输出文件；缺省打印到 stdout")
    a = ap.parse_args()

    task = build(load_spec(a.spec), a.mode, a.role, a.timeout, phase=a.phase)
    s = json.dumps(task, ensure_ascii=False, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(s)
        print(f"task.json -> {a.out}")
    else:
        print(s)


if __name__ == "__main__":
    main()
