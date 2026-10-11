#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retry.py — 瞬时失败的重测 + 「不可测」的判定

口径（吸收自 wrq 框架的评分纪律）：
  * 分母由声明决定，不由运行时决定——两次评测的分母必须严格相同，否则跨模型
    /跨轮次的分数不可比较。
  * 丢包、网络抖动、容器刚起、目标短暂不健康 → 瞬时失败，按指数退避重测。
  * 重测用尽后仍不可测 → 抛 InfrastructureError，必须浮出：既不能缩小分母，
    也不能记成「已阻断/已修复」。我们只是评测设施，绝不把设施故障伪装成正常分数。
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

#: 指数退避节奏：第 1 次重测前等 1s，之后 2s / 4s / 8s / 16s
DEFAULT_DELAYS: Tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0)


class InfrastructureError(RuntimeError):
    """重测用尽后仍不可测——属于设施问题，不代表受测方能力。

    刻意抛出而不是降级计分：分母由声明固定，宁可整轮不出数，
    也不能让「环境影响」变成一个看起来正常的分数。
    """


def with_backoff(
    fn: Callable[[], Any],
    retryable: Callable[[Any], bool],
    *,
    delays: Sequence[float] = DEFAULT_DELAYS,
    label: str = "",
    log: Optional[Callable[[str], None]] = None,
) -> Tuple[Any, List[Dict[str, Any]]]:
    """执行 ``fn()``；若 ``retryable(结果)`` 为真，则退避后重测。

    ``retryable`` 由调用方给出「这一轮结果是否属于瞬时不可用」的判据。
    返回 ``(最后一次结果, 尝试记录)``。
    """
    attempts: List[Dict[str, Any]] = []
    result: Any = None
    schedule: Tuple[float, ...] = (0.0,) + tuple(delays)
    for idx, delay in enumerate(schedule):
        if delay:
            if log:
                log(f"  [retry] {label or 'probe'} 瞬时不可用，{delay:.0f}s 后重测"
                    f"（第 {idx}/{len(schedule) - 1} 次）")
            time.sleep(delay)
        result = fn()
        unusable = bool(retryable(result))
        attempts.append({"attempt": idx + 1, "delay_before_s": delay, "usable": not unusable})
        if not unusable:
            return result, attempts
    return result, attempts


def infra_failure(label: str, attempts: List[Dict[str, Any]], reason: str) -> InfrastructureError:
    """构造一个信息完整的设施失败异常。"""
    return InfrastructureError(
        f"{label}：重测 {len(attempts)} 次后仍不可测（{reason}）。"
        f"分母由声明固定，不因环境问题改变；请修复环境后重跑。尝试记录: {attempts}"
    )
