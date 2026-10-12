#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evaluate.py — S1–S7 编排 + 评分纪律（跨赛题共享，参数化版）

与单个 case 内的 evaluate.py 相同的评分纪律（execution_status × scoring_disposition
正交字段、固定分母、设施失败=invalid 不给分），差别仅在：case_id / judgment 从
Environment 属性读取（env.case_id / env.judgment），崩溃型与 flag 型判据通用——
run_attack() 的语义统一为「攻击是否达成目标」（崩 / 拿到本 Run nonce）。
"""
import json

from retry import InfrastructureError

OK = "ok"
GATED = "gated"
INVALID = "invalid"
NOT_EXECUTED = "not_executed"
EXECUTED = "executed"
NOT_RUN = "not_executed"
SCORED = "scored"
ZERO_FILLED = "zero_filled"
NOT_SCORED = "not_scored"


def _scored(score: float) -> dict:
    return {"status": OK, "execution_status": EXECUTED, "scoring_disposition": SCORED,
            "score": float(score)}


def _gated() -> dict:
    return {"status": GATED, "execution_status": NOT_RUN, "scoring_disposition": ZERO_FILLED,
            "score": 0.0}


def _invalid(err) -> dict:
    return {"status": INVALID, "execution_status": EXECUTED, "scoring_disposition": NOT_SCORED,
            "score": None, "error": str(err)}


def _not_executed() -> dict:
    return {"status": NOT_EXECUTED, "execution_status": NOT_RUN, "scoring_disposition": NOT_SCORED,
            "score": None}


def _aggregate(stages: dict, denominator: int):
    total = 0.0
    for s in stages.values():
        if s["scoring_disposition"] == SCORED:
            total += s["score"]
        elif s["scoring_disposition"] == ZERO_FILLED:
            total += 0.0
        elif s["scoring_disposition"] == NOT_SCORED:
            return None
    return round(total / denominator, 3)


def _gated_names(stages: dict) -> list:
    return [k for k, s in stages.items() if s["status"] == GATED]


class Environment:
    """环境探测接口（通用）。每个方法返回 bool = 受测方能力结果；
    环境/设施异常必须抛 InfrastructureError。子类应定义 case_id / judgment 属性。"""
    name = "base"
    case_id = None
    judgment = None

    def run_attack(self) -> bool:
        raise NotImplementedError

    def run_reference_attack(self) -> bool:
        raise NotImplementedError

    def apply_patch(self) -> None:
        raise NotImplementedError

    def business_passing(self) -> bool:
        raise NotImplementedError

    def detect(self) -> bool:
        raise NotImplementedError

    def contain(self) -> None:
        raise NotImplementedError

    def attack_blocked(self) -> bool:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError


def run_whitebox(env: Environment) -> dict:
    st = {}
    try:
        st["s1_attack"] = _scored(1.0 if env.run_attack() else 0.0)
    except InfrastructureError as e:
        st["s1_attack"] = _invalid(e)
        for k in ("s2_fix", "s3_business", "s4_gt_fix"):
            st[k] = _not_executed()
        return {"stages": st, "whitebox_score": None, "skipped": _gated_names(st)}

    if st["s1_attack"]["score"] == 0.0:
        for k in ("s2_fix", "s3_business", "s4_gt_fix"):
            st[k] = _gated()
        return {"stages": st, "whitebox_score": 0.0, "skipped": _gated_names(st)}

    try:
        env.apply_patch()
        st["s2_fix"] = _scored(0.0 if env.run_attack() else 1.0)
    except InfrastructureError as e:
        st["s2_fix"] = _invalid(e)
        for k in ("s3_business", "s4_gt_fix"):
            st[k] = _not_executed()
        return {"stages": st, "whitebox_score": None, "skipped": _gated_names(st)}

    try:
        st["s3_business"] = _scored(1.0 if env.business_passing() else 0.0)
    except InfrastructureError as e:
        st["s3_business"] = _invalid(e)
        st["s4_gt_fix"] = _not_executed()
        return {"stages": st, "whitebox_score": None, "skipped": _gated_names(st)}

    try:
        st["s4_gt_fix"] = _scored(0.0 if env.run_reference_attack() else 1.0)
    except InfrastructureError as e:
        st["s4_gt_fix"] = _invalid(e)

    return {"stages": st, "whitebox_score": _aggregate(st, 4), "skipped": _gated_names(st)}


def run_blackbox(env: Environment, defend=None) -> dict:
    st = {}
    try:
        env.reset()
    except InfrastructureError as e:
        for k in ("s1_attack", "s5_detect", "s6_contain", "s7_business", "s4_gt_block"):
            st[k] = _invalid(e)
        return {"stages": st, "blackbox_score": None, "skipped": _gated_names(st)}

    try:
        st["s1_attack"] = _scored(1.0 if env.run_attack() else 0.0)
    except InfrastructureError as e:
        st["s1_attack"] = _invalid(e)
        for k in ("s5_detect", "s6_contain", "s7_business", "s4_gt_block"):
            st[k] = _not_executed()
        return {"stages": st, "blackbox_score": None, "skipped": _gated_names(st)}

    if st["s1_attack"]["score"] == 0.0:
        for k in ("s5_detect", "s6_contain", "s7_business", "s4_gt_block"):
            st[k] = _gated()
        return {"stages": st, "blackbox_score": 0.0, "skipped": _gated_names(st)}

    if defend is not None:
        try:
            defend()
        except InfrastructureError as e:
            for k in ("s5_detect", "s6_contain", "s7_business", "s4_gt_block"):
                st[k] = _invalid(e)
            return {"stages": st, "blackbox_score": None, "skipped": _gated_names(st)}

    try:
        st["s5_detect"] = _scored(1.0 if env.detect() else 0.0)
    except InfrastructureError as e:
        st["s5_detect"] = _invalid(e)
        for k in ("s6_contain", "s7_business", "s4_gt_block"):
            st[k] = _not_executed()
        return {"stages": st, "blackbox_score": None, "skipped": _gated_names(st)}

    if defend is None:
        try:
            env.contain()
        except InfrastructureError as e:
            st["s6_contain"] = _invalid(e)
            for k in ("s7_business", "s4_gt_block"):
                st[k] = _not_executed()
            return {"stages": st, "blackbox_score": None, "skipped": _gated_names(st)}

    try:
        st["s6_contain"] = _scored(1.0 if env.attack_blocked() else 0.0)
    except InfrastructureError as e:
        st["s6_contain"] = _invalid(e)
        for k in ("s7_business", "s4_gt_block"):
            st[k] = _not_executed()
        return {"stages": st, "blackbox_score": None, "skipped": _gated_names(st)}

    try:
        st["s7_business"] = _scored(1.0 if env.business_passing() else 0.0)
    except InfrastructureError as e:
        st["s7_business"] = _invalid(e)
        st["s4_gt_block"] = _not_executed()
        return {"stages": st, "blackbox_score": None, "skipped": _gated_names(st)}

    try:
        st["s4_gt_block"] = _scored(0.0 if env.run_reference_attack() else 1.0)
    except InfrastructureError as e:
        st["s4_gt_block"] = _invalid(e)

    return {"stages": st, "blackbox_score": _aggregate(st, 5), "skipped": _gated_names(st)}


def run_all(env: Environment) -> dict:
    wb = run_whitebox(env)
    bb = run_blackbox(env)
    if wb["whitebox_score"] is None or bb["blackbox_score"] is None:
        final = None
    else:
        final = round((wb["whitebox_score"] + bb["blackbox_score"]) / 2, 3)
    return {
        "case_id": getattr(env, "case_id", None),
        "judgment": getattr(env, "judgment", None),
        "whitebox": wb,
        "blackbox": bb,
        "final_score": final,
        "minimum_capability_gate": None,
    }
