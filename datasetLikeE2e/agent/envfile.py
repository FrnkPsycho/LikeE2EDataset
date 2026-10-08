#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""envfile.py — 极简 .env 解析（通用，独立于赛题）。

支持：KEY=VALUE、`export KEY=VALUE`、`#` 注释、空行、行内注释（值后空白 + # 起为注释）。
不做变量展开/类型推断，值原样返回；文件不存在返回空 dict（缺省由调用方决定）。
"""
import os


def parse(path):
    """解析 .env 文件为 dict；path 不存在或为空返回 {}。"""
    if not path or not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if " #" in val:          # 行内注释：值后空白 + # 起为注释
                val = val.split(" #", 1)[0].rstrip()
            out[key] = val
    return out
