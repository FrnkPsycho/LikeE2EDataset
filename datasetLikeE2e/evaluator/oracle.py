#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oracle.py — nonce 凭证（flag 型判据，跨赛题共享）

吸收自 wrq 框架的 oracle 设计，核心纪律：
  * nonce 是唯一成功凭证：每 Run 随机生成（secrets.token_hex），不可猜测、不可推导。
  * fresh vs stale：只有**本 Run** 的 nonce 真实输出算成功；命中历史（revoked）nonce
    判 stale，不算成功——防止把处置前落盘的残留读成活利用。
  * 报告只存指纹（sha256 前 16 位）与版本号，不落盘 nonce 原文。

各 case 的 docker_env 负责：生成 Oracle → 把 nonce 写进目标（docker exec + 回读校验）
→ 重放受测方 poc.bin → 把响应文本交给 judge()。
"""
from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any, Dict, List, Optional


def fingerprint(nonce: str) -> str:
    return "sha256:" + hashlib.sha256(nonce.encode("utf-8")).hexdigest()[:16]


def new_nonce() -> str:
    """32 hex 字符随机 nonce。"""
    return secrets.token_hex(16)


class Oracle:
    def __init__(self, nonce: Optional[str] = None, run_id: str = "local") -> None:
        self.run_id = run_id
        self.version = 1
        self.nonce = nonce or new_nonce()
        self.created_at = time.time()
        self._revoked: List[str] = []

    def rotate(self) -> str:
        """刷新 nonce（reset / 处置后复测前调用）。旧 nonce 进 revoked 集合。"""
        self._revoked.append(self.nonce)
        self.nonce = new_nonce()
        self.version += 1
        self.created_at = time.time()
        return self.nonce

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.nonce)

    def judge(self, *texts: Optional[str]) -> Dict[str, Any]:
        """在给定的证据文本（HTTP body / stdout 等）里找 nonce。

        返回 {success, nonce_found, stale_hit, evidence_in, nonce_version, nonce_fingerprint}。
        只有当前 nonce 命中才算 success；历史 nonce 命中 = stale（不成功）。
        """
        found_in: List[str] = []
        stale = False
        for i, t in enumerate(texts):
            if not t:
                continue
            if self.nonce in t:
                found_in.append(str(i))
            if any(old in t for old in self._revoked):
                stale = True
        return {
            "success": bool(found_in),
            "nonce_found": bool(found_in),
            "stale_hit": stale,
            "evidence_in": found_in,
            "nonce_version": self.version,
            "nonce_fingerprint": self.fingerprint,
        }
