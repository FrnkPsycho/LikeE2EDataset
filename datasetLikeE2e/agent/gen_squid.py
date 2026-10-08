#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_squid.py — 从 team.env 的模型端点生成 egress 代理（squid）白名单配置。

强制「agent 只能访问模型端点，禁止联网搜索/浏览」：squid 只放行 MODEL_BASE_URL 的
host，其余一律 deny。模型 host 由 team.env（或宿主机 OPENAI_BASE_URL）推导，通用、独立于赛题。

用法：
  python gen_squid.py --team-env ../../team.env --out organizer/egress/squid.conf
"""
import argparse
import os
from urllib.parse import urlparse

import envfile


def model_hosts(team_env_path):
    """从 team.env（或宿主机 OPENAI_BASE_URL）提取模型端点 host。"""
    data = envfile.parse(team_env_path) if team_env_path else {}
    base = data.get("MODEL_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    if not base:
        return []
    host = urlparse(base).hostname
    return [host] if host else []


def render(hosts):
    if hosts:
        acl_lines = "\n".join(f"acl model_host dstdomain {h}" for h in hosts)
        allow_lines = ("http_access allow CONNECT model_host\n"
                       "http_access allow model_host")
    else:
        acl_lines = "# （未声明模型端点：默认全拒，agent 无法出网）"
        allow_lines = ""
    return f"""# squid.conf —— egress 代理白名单（自动生成，勿手改）
# agent 只能访问模型端点（MODEL_BASE_URL 的 host），其余一律 deny，禁止联网搜索。
# 重新生成：python gen_squid.py --team-env ../../team.env --out squid.conf

acl SSL_ports port 443
acl Safe_ports port 443
acl CONNECT method CONNECT
{acl_lines}

http_access deny !Safe_ports
http_access deny CONNECT !SSL_ports
{allow_lines or "http_access deny all"}
http_access deny all

http_port 3128
dns_v4_first on
cache deny all
coredump_dir /var/spool/squid
"""


def gen(team_env_path, out_path):
    """生成并写回 squid.conf，返回放行的 host 列表。"""
    hosts = model_hosts(team_env_path)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render(hosts))
    return hosts


def main():
    ap = argparse.ArgumentParser(description="生成 squid egress 白名单配置")
    ap.add_argument("--team-env", default=None, help="team.env 路径（读 MODEL_BASE_URL）")
    ap.add_argument("--out", required=True, help="输出 squid.conf 路径")
    a = ap.parse_args()
    hosts = gen(a.team_env, a.out)
    print(f"squid.conf -> {a.out}（放行 {hosts or '无，默认全拒'}）")


if __name__ == "__main__":
    main()
