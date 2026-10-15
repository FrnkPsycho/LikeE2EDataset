#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generic_env.py — 通用评测引擎（配置驱动，出题人不写代码）

读赛题根的 case.json，实现共享 evaluate.py 的 Environment 8 个方法。支持：
  * 判据类型：flag（nonce oracle，http 重放找 nonce）/ crash（攻击链命令，返回码=崩溃）
  * 业务回归：pytest / http 请求列表
  * 补丁真编译：case.json 声明的 shell 命令（{patch} 占位符替换为补丁绝对路径）

出题人只需提供：环境（blackbox/ + whitebox/ + ground_truth/）+ case.json +
agent_task.json + case.env，不再写任何 Python。

用法（run.py 内部调用，也可直接跑）：
  python evaluator/generic_env.py --case-dir <case> --run-agent
  python evaluator/generic_env.py --case-dir <case> --calibrate
"""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request

DATASET_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # datasetLikeE2e/
sys.path.insert(0, os.path.join(DATASET_DIR, "evaluator"))
sys.path.insert(0, os.path.join(DATASET_DIR, "agent"))

from evaluate import Environment, run_whitebox, run_blackbox, run_all       # noqa: E402
from retry import InfrastructureError                                       # noqa: E402
from oracle import Oracle                                                   # noqa: E402
import envfile                                                              # noqa: E402
import gen_squid                                                            # noqa: E402
import host_run                                                             # noqa: E402


def load_config(case_dir):
    """读 case.json，返回带默认值的 dict。"""
    p = os.path.join(case_dir, "case.json")
    if not os.path.isfile(p):
        raise SystemExit(f"缺赛题配置：{p}（配置驱动评测器，出题人只写 case.json，不写代码）")
    with open(p, encoding="utf-8") as f:
        cfg = json.load(f)
    if not cfg.get("case_id"):
        raise SystemExit("case.json 缺 case_id")
    return cfg


def find_bash():
    cands = [shutil.which("bash"),
             r"C:\Program Files\Git\bin\bash.exe",
             r"C:\Program Files\Git\usr\bin\bash.exe",
             r"C:\Program Files (x86)\Git\bin\bash.exe"]
    for b in cands:
        if b and os.path.isfile(b):
            try:
                r = subprocess.run([b, "-c", "set -o pipefail && echo ok"],
                                   capture_output=True, text=True, timeout=15)
                if r.returncode == 0 and "ok" in r.stdout:
                    return b
            except Exception:
                continue
    return None


class ConfigEnvironment(Environment):
    """由 case.json 驱动的通用环境。"""

    def __init__(self, case_dir, with_egress=False):
        self.case_dir = os.path.abspath(case_dir)
        self.cfg = load_config(self.case_dir)
        self.case_id = self.cfg["case_id"]
        self.judgment = self.cfg.get("judgment", {}).get("type", "flag")
        self.compose_file = os.path.join(self.case_dir, "blackbox", "docker-compose.yml")
        self.team_env = os.path.join(DATASET_DIR, "team.env")
        self.case_env = os.path.join(self.case_dir, "case.env")
        self.squid_conf = os.path.join(self.case_dir, "blackbox", "egress", "squid.conf")

        j = self.cfg.get("judgment", {})
        self.flag_path = j.get("flag_path", "/tmp/flag")
        self.nonce_write = j.get("nonce_write", "printf '%s' {nonce} > /tmp/flag; chmod 0644 /tmp/flag")

        t = self.cfg.get("target", {})
        self.image = t["image"]
        self.patched_image = t.get("patched_image", self.image)
        self.container = t.get("container")
        self.compose_service = t.get("compose_service")
        self.target_image_env = t.get("target_image_env")      # compose 里 ${X:-...} 的环境变量名
        self.healthy_check = t.get("healthy_check", "container")
        self.ready_url = t.get("ready_url", "http://localhost/")

        g = self.cfg.get("gateway", {})
        self.gateway_mgmt = g.get("mgmt_url", "http://127.0.0.1:18080")
        self.admin_token = g.get("admin_token", "local-admin-token")

        r = self.cfg.get("replay", {})
        self.replay_driver = r.get("driver", "http")
        self.replay_gateway = r.get("gateway", "http://bb_shared_egress:80")
        self.traffic_container = r.get("traffic_container")
        self.evidence_key = r.get("evidence_key", "body_text")
        self.reference_cmd = r.get("reference_cmd")
        self.attack_cmd = r.get("attack_cmd")                   # script 型：dc 子命令列表，{poc} 替换
        self.reference_attack_cmd = r.get("reference_attack_cmd")  # script 型参考

        self.patch_build_cmd = self.cfg.get("patch", {}).get("build_cmd")

        b = self.cfg.get("business", {})
        self.business_driver = b.get("driver", "pytest")
        self.business_cmd = b.get("cmd", "cd /work && python -m pytest business_tests/test_business.py -q")
        self.business_tests = b.get("tests", [])
        self.business_command = b.get("command", [])           # command 驱动：dc run 参数列表

        d = self.cfg.get("defense", {})
        self.defense_driver = d.get("driver", "gateway")       # gateway | blue_controller
        self.defense_dir = d.get("dir", "blackbox/defense")
        self.defense_module = d.get("module", "blue_controller")

        self._with_egress = with_egress
        self._oracle = Oracle(run_id=time.strftime("%Y%m%d-%H%M%S"))
        self._s1_events = []
        self._defender_mode = "reference"
        self._track = "whitebox"
        self.calibrate = False   # --calibrate 时置 True：S1/S2 改用参考 PoC 自检

        prepare_egress(self.team_env, self.squid_conf)
        self.dc(["down", "-v"], timeout=120)
        up = (["--profile", "agent"] if with_egress else []) + ["up", "-d", "--build"]
        rr = self.dc(up, image=self.image, timeout=3600)
        if rr.returncode != 0:
            print(rr.stdout[-2000:]); print(rr.stderr[-2000:])
            raise InfrastructureError("docker compose up 失败：环境/设施问题，非受测方能力")
        if not self._wait_target():
            raise InfrastructureError("目标未就绪：设施问题")
        if self.judgment == "flag":
            self._set_nonce()

    # ---- 基础设施 ----
    def dc(self, args, image=None, timeout=900):
        env = dict(os.environ)
        # 始终把当前目标镜像锁进 TARGET_IMAGE：compose 每次都会用它重算服务配置，
        # 只要有一次没传，缺省值（vul）就会把 target 重建回漏洞镜像 —— 打完补丁的
        # S2/S4 会因此变成「攻击依然成功」，白盒修复项恒为 0。
        tag = image or self.image
        if tag and self.target_image_env:
            env[self.target_image_env] = tag
        return subprocess.run(["docker", "compose", "-f", self.compose_file] + args,
                              cwd=self.case_dir, capture_output=True, encoding="utf-8",
                              errors="replace", timeout=timeout, env=env)

    def dsh(self, container, cmd, timeout=120):
        return subprocess.run(["docker", "exec", container, "sh", "-c", cmd],
                              capture_output=True, encoding="utf-8", errors="replace",
                              timeout=timeout)

    def _wait_target(self, tries=60, delay=5):
        if self.healthy_check == "sleep":
            time.sleep(delay)
            return True
        for i in range(tries):
            if self.healthy_check == "http" and self.container:
                r = self.dsh(self.container, f"curl -s -o /dev/null -w '%{{http_code}}' {self.ready_url}",
                             timeout=30)
                if r.returncode == 0 and r.stdout.strip() == "200":
                    return True
            elif self.container:
                r = subprocess.run(["docker", "inspect", "--format", "{{.State.Health.Status}}",
                                    self.container], capture_output=True, encoding="utf-8")
                if r.returncode == 0 and r.stdout.strip() == "healthy":
                    return True
            if i % 6 == 0:
                print(f"[generic_env] 等目标就绪（{i * delay}s）…")
            time.sleep(delay)
        return False

    def _set_nonce(self):
        cmd = self.nonce_write.replace("{nonce}", shlex.quote(self._oracle.nonce))
        r = self.dsh(self.container, cmd)
        if r.returncode != 0:
            raise InfrastructureError(f"set_nonce 失败: {r.stderr}")
        if self.dsh(self.container, f"cat {self.flag_path}").stdout.strip() != self._oracle.nonce:
            raise InfrastructureError("set_nonce 回读不一致：设施问题")

    def _set_phase(self, phase):
        if self.defense_driver == "blue_controller":
            return   # blue_controller 无阶段概念
        try:
            res = self._http("POST", "/_admin/state", self.admin_token,
                             {"phase": phase, "run_id": self._oracle.run_id}, timeout=15)
        except Exception as e:
            raise InfrastructureError(f"网关设置 phase {phase} 失败: {e}")
        if not res.get("ok", True):
            raise InfrastructureError(f"网关设置 phase {phase} 被拒: {res}")

    def _swap_target(self, image):
        args = ["up", "-d", "--no-deps", "--renew-anon-volumes"]
        if self.compose_service:
            args.append(self.compose_service)
        r = self.dc(args, image=image, timeout=600)
        if r.returncode != 0:
            raise InfrastructureError(f"切换目标镜像 {image} 失败：设施问题")
        time.sleep(8)
        if not self._wait_target():
            raise InfrastructureError("切换后目标未就绪：设施问题")

    def _http(self, method, path, token, data=None, timeout=15):
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(self.gateway_mgmt + path, method=method)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, data=body, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def _sub_dir(self):
        return os.path.join(self.case_dir, "submission")

    # ---- 重放 ----
    def _replay_submitted(self, poc_path):
        """http 型：cp poc.bin 进流量容器逐字节重放；返回响应 dict。"""
        cp = subprocess.run(["docker", "cp", poc_path, f"{self.traffic_container}:/tmp/poc.bin"],
                            capture_output=True, encoding="utf-8", timeout=60)
        if cp.returncode != 0:
            raise InfrastructureError(f"docker cp poc.bin 失败: {cp.stderr}")
        r = self.dsh(self.traffic_container, "python traffic/replay_poc.py --poc /tmp/poc.bin "
                                             f"--gateway {self.replay_gateway}", timeout=120)
        if r.returncode != 0 and not r.stdout.strip():
            raise InfrastructureError(f"replay_poc 执行失败: {r.stderr[:500]}")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            raise InfrastructureError(f"replay_poc 输出无法解析: {r.stdout[:300]}")

    def _replay_reference(self):
        """http 型参考 PoC：跑 reference_cmd 取响应。"""
        if not self.reference_cmd:
            raise InfrastructureError("case.json 缺 replay.reference_cmd")
        r = self.dsh(self.traffic_container, self.reference_cmd, timeout=180)
        if r.returncode != 0 and not r.stdout.strip():
            raise InfrastructureError(f"reference_poc 执行失败: {r.stderr[:500]}")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            raise InfrastructureError(f"reference_poc 输出无法解析: {r.stdout[:300]}")

    def _run_attack_script(self, poc_path=None):
        """script 型（crash）：跑攻击链命令，返回码 0 = 攻击达成（崩溃）。"""
        if not self.attack_cmd:
            raise InfrastructureError("case.json 缺 replay.attack_cmd")
        args = []
        for a in self.attack_cmd:
            a = a.replace("{poc}", poc_path or "").replace("{track}", self._track)
            args.append(a)
        r = self.dc(["run", "--rm"] + args, timeout=600)
        return r.returncode == 0

    def _run_reference_script(self):
        if not self.reference_attack_cmd:
            raise InfrastructureError("case.json 缺 replay.reference_attack_cmd")
        r = self.dc(["run", "--rm"] + self.reference_attack_cmd, timeout=600)
        return r.returncode == 0

    # ---- Environment 接口 ----
    def run_attack(self) -> bool:
        self._set_phase("S1")
        if self.calibrate:
            # 标定自检：没有被测方提交的 poc.bin，改用出题方参考 PoC 代打。
            # 标定要验的是「无防御时这道题确实可利用」和「打完参考补丁后同一攻击
            # 不再成立」，这两件事用参考 PoC 判定即可，不应依赖 submission/ 里
            # 恰好躺着上次跑剩的文件。
            return self.run_reference_attack()
        poc = os.path.join(self._sub_dir(), self._track, "poc.bin")
        if not os.path.isfile(poc):
            return False
        if self.replay_driver == "script":
            ok = self._run_attack_script(poc)
        else:
            resp = self._replay_submitted(poc)
            ok = bool(self._oracle.judge(resp.get(self.evidence_key) or "")["success"])
        self._s1_events = self._attack_window_events()
        return ok

    def run_reference_attack(self) -> bool:
        if self.replay_driver == "script":
            return self._run_reference_script()
        resp = self._replay_reference()
        text = resp.get("body") or resp.get("body_text") or resp.get(self.evidence_key) or ""
        return bool(self._oracle.judge(text)["success"])

    def apply_patch(self) -> None:
        patch = os.path.join(self._sub_dir(), "whitebox", "patch.diff")
        if not os.path.isfile(patch) or os.path.getsize(patch) == 0:
            print("[patch_build] 警告：缺少 patch.diff，S2 按未修复判 0")
            return
        image = build_patched_image(self.patch_build_cmd, patch, self.patched_image,
                                    self.case_dir)
        self.image = image
        self._swap_target(image)
        if not self._wait_target():
            raise InfrastructureError("切到 patched 镜像后目标未就绪：设施问题")
        if self.judgment == "flag":
            self._set_nonce()

    def business_passing(self) -> bool:
        if self.business_driver == "http":
            for t in self.business_tests:
                r = self.dsh(self.traffic_container,
                             f"curl -s -o /dev/null -w '%{{http_code}}' -X {t['method']} "
                             f"{self.replay_gateway}{t['path']}", timeout=30)
                if str(r.stdout.strip()) != str(t.get("expect", 200)):
                    return False
            return True
        if self.business_driver == "command":
            r = self.dc(["run", "--rm"] + self.business_command, timeout=600)
            return r.returncode == 0
        r = self.dsh(self.traffic_container, self.business_cmd, timeout=600)
        return r.returncode == 0

    def _attack_window_events(self):
        if self.defense_driver == "blue_controller":
            return []
        try:
            res = self._http("GET", "/events?run_id=" + self._oracle.run_id, self.admin_token, timeout=20)
            items = res.get("events") or (res.get("data") or {}).get("events") or []
            return [e.get("event_id") or e.get("conn_id") or e.get("id")
                    for e in items if isinstance(e, dict)]
        except Exception:
            return []

    def detect(self) -> bool:
        if self.defense_driver == "blue_controller":
            try:
                resp = self._http("GET", "/detect", self.admin_token, timeout=20)
            except Exception as e:
                raise InfrastructureError(f"读取 /detect 失败: {e}")
            return bool(resp.get("detected"))
        if self._defender_mode == "reference":
            self._set_phase("S5")
            poc = os.path.join(self._sub_dir(), "blackbox", "poc.bin")
            if self.calibrate:
                # 标定自检：没有被测方 poc.bin，用参考攻击产生蓝队可见的攻击事件，
                # 否则蓝队看不到任何东西，S5 恒为 0。
                self.run_reference_attack()
                self._s1_events = self._attack_window_events()
            elif os.path.isfile(poc):
                if self.replay_driver == "script":
                    self._run_attack_script(poc)
                else:
                    self._replay_submitted(poc)
                self._s1_events = self._attack_window_events()
            self._ref_blue_action("detect")
        try:
            alerts = self._http("GET", "/alerts", self.admin_token, timeout=20)
            items = alerts if isinstance(alerts, list) else (alerts.get("alerts") or alerts.get("items") or [])
        except Exception as e:
            raise InfrastructureError(f"读取 /alerts 失败: {e}")
        if not items:
            return False
        known = set(self._s1_events) or set(self._attack_window_events())
        for a in items:
            refs = a.get("event_ids") or ([a.get("event_id")] if a.get("event_id") else [])
            if any(str(x) in known for x in refs):
                return True
        return False

    def contain(self) -> None:
        if self.defense_driver == "blue_controller":
            self._http("POST", "/contain", self.admin_token, timeout=20)
            args = ["up", "-d", "--no-deps"]
            if self.compose_service:
                args.append(self.compose_service)
            self.dc(args, image=self.image, timeout=600)
            time.sleep(3)
            return
        self._set_phase("S6")
        self._ref_blue_action("contain")

    def _ref_blue_action(self, action):
        defense_dir = self.cfg.get("defense", {}).get("dir", "blackbox/defense")
        module = self.cfg.get("defense", {}).get("module", "blue_controller")
        sys.path.insert(0, os.path.join(self.case_dir, defense_dir))
        try:
            ref_blue = __import__(module)
        except ImportError as e:
            raise InfrastructureError(f"参考防御加载失败: {e}")
        token = os.environ.get("GATEWAY_S5_TOKEN" if action == "detect" else "GATEWAY_S6_TOKEN",
                               "local-s5-token" if action == "detect" else "local-s6-token")
        client = ref_blue.GatewayClient(self.gateway_mgmt, token)
        try:
            (ref_blue.detect(client) if action == "detect" else ref_blue.contain(client))
        except Exception as e:
            raise InfrastructureError(f"参考防御 {action} 失败: {e}")

    def attack_blocked(self) -> bool:
        if self.calibrate:
            # 标定自检：没有被测方 poc.bin，用参考攻击代表「同一类攻击」重放。
            return not self.run_reference_attack()
        poc = os.path.join(self._sub_dir(), self._track, "poc.bin")
        if not os.path.isfile(poc):
            return False
        if self.replay_driver == "script":
            return not self._run_attack_script(poc)
        resp = self._replay_submitted(poc)
        return not bool(self._oracle.judge(resp.get(self.evidence_key) or "")["success"])

    def reset(self) -> None:
        self.image = self.cfg["target"]["image"]
        self._track = "blackbox"
        self._swap_target(self.image)
        if self.defense_driver == "blue_controller":
            try:
                self._http("POST", "/reset", self.admin_token, timeout=20)
            except Exception:
                pass
            time.sleep(3)
            return
        try:
            self._http("POST", "/_admin/reset", self.admin_token,
                       {"clear_events": True, "clear_rules": True}, timeout=30)
        except Exception as e:
            raise InfrastructureError(f"网关 reset 失败: {e}")
        self._oracle.rotate()
        if self.judgment == "flag":
            self._set_nonce()
        self._set_phase("S1")
        self._s1_events = []


def prepare_egress(team_env, squid_conf):
    os.makedirs(os.path.dirname(squid_conf), exist_ok=True)
    hosts = gen_squid.gen(team_env, squid_conf)
    print(f"[generic_env] egress 白名单已生成：{hosts or '（未声明模型端点，默认全拒）'}")


def build_patched_image(build_cmd, patch_path, out_tag, case_dir):
    """执行 case.json 声明的真编译命令（{patch} 替换为补丁绝对路径）。"""
    if not build_cmd:
        raise InfrastructureError("case.json 缺 patch.build_cmd（补丁真编译命令）")
    bash = find_bash()
    if not bash:
        raise InfrastructureError("找不到支持 pipefail 的 bash")
    cmd = build_cmd.replace("{patch}", shlex.quote(os.path.abspath(patch_path)))
    r = subprocess.run([bash, "-c", cmd], cwd=case_dir, capture_output=True,
                       encoding="utf-8", errors="replace", timeout=3600)
    if r.returncode != 0:
        print(r.stdout[-2000:]); print(r.stderr[-2000:])
        raise RuntimeError("patched 镜像构建失败（真编译）：能力失败或设施问题")
    print(f"[patch_build] 构建完成：{out_tag}")
    return out_tag


def run_calibration(case_dir):
    cfg = load_config(case_dir)
    sub_dir = os.path.join(case_dir, "submission")
    # 先清空 submission：标定走的是参考 PoC / 参考补丁，不该被上一次跑剩下的文件
    # 影响 —— 否则「标定全绿」只说明残留文件还在，不说明这道题自洽。
    for track in ("whitebox", "blackbox"):
        d = os.path.join(sub_dir, track)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
    env = ConfigEnvironment(case_dir)
    env.calibrate = True   # S1/S2 用参考 PoC 代打（标定不依赖 submission 里的残留文件）
    # 标定用参考 PoC：由 reference_cmd/脚本生成；这里让出题人在 case.json 里声明 poc 生成命令
    poc_gen = cfg.get("calibration", {}).get("poc_bytes_cmd")
    if poc_gen:
        r = subprocess.run([sys.executable, "-c", poc_gen], cwd=case_dir,
                           capture_output=True, encoding="utf-8")
        if r.returncode != 0:
            raise InfrastructureError(f"标定 poc 生成失败: {r.stderr[:500]}")
    else:
        # 默认：参考 PoC 写死到 submission，需出题人在 reference_poc 里提供 --save
        pass
    shutil.copy(os.path.join(case_dir, "ground_truth", "reference_patch.diff"),
                os.path.join(sub_dir, "whitebox", "patch.diff"))
    wb = run_whitebox(env)
    bb = run_blackbox(env)
    final = None
    if wb["whitebox_score"] is not None and bb["blackbox_score"] is not None:
        final = round((wb["whitebox_score"] + bb["blackbox_score"]) / 2, 3)
    return {"case_id": cfg["case_id"], "mode": "calibration", "scored": False,
            "whitebox": wb, "blackbox": bb, "final_score": final}


def run_with_agent(case_dir, agent=None, build_agent=False, blackbox_only=False):
    cfg = load_config(case_dir)
    team_env = envfile.parse(os.path.join(DATASET_DIR, "team.env"))
    agent = agent or team_env.get("AGENT") or "codex"
    team_id = team_env.get("TEAM_ID") or "unknown"

    sub_dir = os.path.join(case_dir, "submission")
    if os.path.isdir(sub_dir):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        bak = os.path.join(case_dir, "results", f"submission_bak_{stamp}")
        os.makedirs(os.path.dirname(bak), exist_ok=True)
        shutil.copytree(sub_dir, bak)
        for name in os.listdir(sub_dir):
            p = os.path.join(sub_dir, name)
            (shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p))

    env = ConfigEnvironment(case_dir, with_egress=True)
    env._defender_mode = "agent"

    case_env = os.path.join(case_dir, "case.env")
    rc_wb = None
    wb = None
    if not blackbox_only:
        rc_wb = host_run.run_agent(case_dir, "whitebox", "attacker", agent=agent,
                                   build=build_agent, timeout=1800,
                                   team_env_path=os.path.join(DATASET_DIR, "team.env"),
                                   case_env_path=case_env)
        wb = run_whitebox(env)

    env.reset()
    rc_bb_att = host_run.run_agent(case_dir, "blackbox", "attacker", agent=agent,
                                   timeout=1200,
                                   team_env_path=os.path.join(DATASET_DIR, "team.env"),
                                   case_env_path=case_env)

    rc_bb_def = {}
    def _defend():
        env._set_phase("S6")
        poc = os.path.join(case_dir, "submission", "blackbox", "poc.bin")
        if env.replay_driver == "script":
            env._run_attack_script(poc)
        else:
            env._replay_submitted(poc)
        env._s1_events = env._attack_window_events()
        rc_bb_def["rc"] = host_run.run_agent(case_dir, "blackbox", "defender", agent=agent,
                                             timeout=600,
                                             team_env_path=os.path.join(DATASET_DIR, "team.env"),
                                             case_env_path=case_env)
    bb = run_blackbox(env, defend=_defend)

    final = None
    if wb is None:
        final = bb["blackbox_score"]
    elif wb["whitebox_score"] is not None and bb["blackbox_score"] is not None:
        final = round((wb["whitebox_score"] + bb["blackbox_score"]) / 2, 3)
    return {"case_id": cfg["case_id"], "team_id": team_id,
            "judgment": cfg.get("judgment", {}).get("type"),
            "agent": agent,
            "agent_rc": {"whitebox_attacker": rc_wb, "blackbox_attacker": rc_bb_att,
                         "blackbox_defender": rc_bb_def.get("rc")},
            "whitebox": wb, "blackbox": bb, "final_score": final}


def main():
    ap = argparse.ArgumentParser(description="datasetLikeE2e 通用评测引擎（配置驱动）")
    ap.add_argument("--case-dir", required=True)
    ap.add_argument("--run-agent", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--agent", default=None, choices=["codex", "qwencode", "custom"])
    ap.add_argument("--build-agent", action="store_true")
    ap.add_argument("--blackbox-only", action="store_true", help="只跑黑盒（跳过白盒攻击者）")
    ap.add_argument("--report-out", default=None)
    a = ap.parse_args()

    case = os.path.abspath(a.case_dir)
    if a.run_agent:
        report = run_with_agent(case, agent=a.agent, build_agent=a.build_agent,
                                blackbox_only=a.blackbox_only)
    elif a.calibrate:
        report = run_calibration(case)
    else:
        report = run_all(ConfigEnvironment(case))

    if a.report_out:
        out = os.path.abspath(a.report_out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[generic_env] 报告已写入 {out}")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
