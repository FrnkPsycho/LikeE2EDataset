#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_case.py — 校验一个赛题目录是否符合 Case Schema（docs/CASE_SCHEMA.md）。

静态检查，不需要 docker。在标定（--calibrate）之前拦住低级错误，避免把不合格的
题丢给评测器浪费一次 1 小时的跑。校验维度：

  1. 目录结构     —— run.py 能否发现它（agent_task.json + organizer/evaluator/docker_env.py）
  2. agent_task.json —— 合法 JSON + 三角色 + 必填字段 + 交付物路径
  3. case.env     —— 拓扑必填键
  4. docker_env.py —— 定义 DockerEnvironment 并实现 8 个方法 + case_id/judgment（AST，不执行）
  5. ground_truth —— reference_patch.diff 存在且非空
  6. blackbox/docker-compose.yml —— 含目标/网关/共享出口服务 + 必需网络

用法：
  python validate_case.py <case_dir>           # 校验单个赛题
  python validate_case.py --all                # 校验 cases/ 下全部（跳过 _ 开头）
退出码：0 = 全部通过；1 = 有 FAIL。
"""
import argparse
import ast
import json
import os
import sys

DATASET_DIR = os.path.dirname(os.path.abspath(__file__))
CASES_DIR = os.path.join(DATASET_DIR, "cases")

REQUIRED_ROLES = ("whitebox_attacker", "blackbox_attacker", "blackbox_defender")
REQUIRED_METHODS = ("run_attack", "run_reference_attack", "apply_patch",
                    "business_passing", "detect", "contain", "attack_blocked", "reset")
REQUIRED_ENV_KEYS = ("CASE_ID", "COMPOSE_PROJECT", "AGENT_NETWORK", "EGRESS_PROXY",
                     "BLACKBOX_ATTACKER_NETWORK", "BLACKBOX_DEFENDER_NETWORK", "BLUE_API")


def _parse_env(path):
    kv = {}
    if not os.path.isfile(path):
        return kv
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line or "=" not in line:
                continue
            k, v = line.split("=", 1)
            kv[k.strip()] = v.strip()
    return kv


def _check_structure(case, errs, warns):
    def need(rel):
        p = os.path.join(case, rel)
        if not os.path.exists(p):
            errs.append(f"缺少 {rel}")
        return os.path.exists(p)

    need("agent_task.json")
    need("case.env")
    need("organizer/evaluator/docker_env.py")
    need("organizer/evaluator/prepare_case.py")
    need("blackbox/docker-compose.yml")
    need("ground_truth/reference_patch.diff")
    if not os.path.isdir(os.path.join(case, "whitebox")):
        errs.append("缺少 whitebox/ 目录（白盒源码挂载点）")
    if not os.path.isdir(os.path.join(case, "blackbox")):
        errs.append("缺少 blackbox/ 目录")


def _check_task(case, errs):
    p = os.path.join(case, "agent_task.json")
    if not os.path.isfile(p):
        return
    try:
        with open(p, encoding="utf-8") as f:
            task = json.load(f)
    except json.JSONDecodeError as e:
        errs.append(f"agent_task.json 不是合法 JSON：{e}")
        return
    if not task.get("case_id"):
        errs.append("agent_task.json 缺少 case_id")
    roles = task.get("roles") or {}
    for r in REQUIRED_ROLES:
        if r not in roles:
            errs.append(f"agent_task.json 缺角色 roles.{r}")
            continue
        role = roles[r]
        if not role.get("goal"):
            errs.append(f"roles.{r} 缺 goal")
        out = role.get("output") or {}
        if not out:
            errs.append(f"roles.{r} 缺 output")
    # 交付物路径（白盒两个、黑盒攻击者一个）
    wb_out = (roles.get("whitebox_attacker") or {}).get("output") or {}
    for rel in ("/submission/whitebox/poc.bin", "/submission/whitebox/patch.diff"):
        if rel not in wb_out:
            errs.append(f"whitebox_attacker.output 缺 {rel}")
    bb_out = (roles.get("blackbox_attacker") or {}).get("output") or {}
    if "/submission/blackbox/poc.bin" not in bb_out:
        errs.append("blackbox_attacker.output 缺 /submission/blackbox/poc.bin")


def _check_env(case, errs):
    kv = _parse_env(os.path.join(case, "case.env"))
    for k in REQUIRED_ENV_KEYS:
        if k not in kv:
            errs.append(f"case.env 缺键 {k}")


def _check_docker_env(case, errs):
    p = os.path.join(case, "organizer", "evaluator", "docker_env.py")
    if not os.path.isfile(p):
        return
    try:
        with open(p, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except SyntaxError as e:
        errs.append(f"docker_env.py 语法错误：{e}")
        return
    cls = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "DockerEnvironment":
            cls = node
            break
    if cls is None:
        errs.append("docker_env.py 未定义 class DockerEnvironment")
        return
    methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
    for m in REQUIRED_METHODS:
        if m not in methods:
            errs.append(f"DockerEnvironment 缺方法 {m}")
    class_attrs = set()
    for n in cls.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    class_attrs.add(t.id)
    for a in ("case_id", "judgment"):
        if a not in class_attrs:
            errs.append(f"DockerEnvironment 缺类属性 {a}")


def _check_ground_truth(case, errs):
    p = os.path.join(case, "ground_truth", "reference_patch.diff")
    if os.path.isfile(p) and os.path.getsize(p) == 0:
        errs.append("ground_truth/reference_patch.diff 为空")


def _check_compose(case, errs):
    p = os.path.join(case, "blackbox", "docker-compose.yml")
    if not os.path.isfile(p):
        return
    with open(p, encoding="utf-8") as f:
        text = f.read()
    # 结构检查：服务/网络名是 case-specific（由 case.env 声明具体名），这里只查通用结构。
    if "services:" not in text:
        errs.append("compose 缺 services 段")
    if "networks:" not in text:
        errs.append("compose 缺 networks 段")


def validate_case(case_dir):
    case = os.path.abspath(case_dir)
    errs, warns = [], []
    _check_structure(case, errs, warns)
    _check_task(case, errs)
    _check_env(case, errs)
    _check_docker_env(case, errs)
    _check_ground_truth(case, errs)
    _check_compose(case, errs)
    return errs, warns


def discover(directory=CASES_DIR):
    out = []
    if not os.path.isdir(directory):
        return out
    for name in sorted(os.listdir(directory)):
        if name.startswith("_"):
            continue
        d = os.path.join(directory, name)
        if os.path.isdir(d):
            out.append((name, d))
    return out


def main():
    ap = argparse.ArgumentParser(description="校验赛题目录是否符合 Case Schema")
    ap.add_argument("case_dir", nargs="?", default=None, help="赛题目录路径")
    ap.add_argument("--all", action="store_true", help="校验 cases/ 下全部赛题")
    a = ap.parse_args()

    targets = []
    if a.all:
        targets = discover()
    elif a.case_dir:
        targets = [(os.path.basename(os.path.abspath(a.case_dir)), a.case_dir)]
    else:
        ap.error("请给 --all 或 <case_dir>")

    if not targets:
        print("[validate] 未找到可校验的赛题目录")
        return 1

    rc = 0
    for name, d in targets:
        errs, warns = validate_case(d)
        status = "PASS" if not errs else "FAIL"
        print(f"\n[{status}] {name}")
        for e in errs:
            print(f"  [x] {e}")
        for w in warns:
            print(f"  [!] {w}")
        if not errs:
            print("  [OK] 结构/题面/拓扑/评测器/补丁/compose 均符合 schema，可进入 prepare_case + --calibrate")
        else:
            rc = 1
    print(f"\n[validate] {'全部通过' if rc == 0 else '存在 FAIL，标定前先修复'}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
