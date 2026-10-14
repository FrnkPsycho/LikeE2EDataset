# 赛题模板（_template）

出题人从本目录复制一份、改名成 `<CASE_ID>`（建议 CVE 编号），按下面的顺序填内容即可。
完整契约见 [`docs/CASE_SCHEMA.md`](../../docs/CASE_SCHEMA.md)。

## 产题顺序（重要：先想业务，再想漏洞）

1. **写业务场景描述**（第一步，不是搭环境）：这个系统是干什么的、正常用户怎么用、
   攻击者怎么穿过业务逻辑走到漏洞。这一步决定后面的攻击链和回归测试。
2. **定判据类型**：崩溃型还是 flag 型（见 schema §2）。
3. 搭 `blackbox/` 环境：业务外壳（target）+ 网关 + 出口 + 正常流量 + 参考 PoC + 业务回归。
4. 写 `ground_truth/`：参考补丁 + 业务断言 + 防御家族（真值变种）。
5. 搭 `whitebox/`：源码能拉取、能真编译、agent 能挂载审计。
6. 写 `agent_task.json`（三层线索）+ `case.env` + `docker_env.py`（8 个方法）+ `prepare_case.py`。
7. 跑 `python validate_case.py <case_dir>` 静态校验。
8. 跑 `python organizer/evaluator/docker_env.py --prepare` 和 `--calibrate`，标定全绿（final_score==1.0）。
9. 删 `.port-incomplete`，纳入 `run.py --all`。

## 哪些是"复制即可"、哪些是"必须自己写"

| 文件 | 说明 |
|---|---|
| `blackbox/security_gateway/`、`shared_egress/`、`traffic/replay_poc.py`、`runner/Dockerfile` | **通用组件**，可从任意既有 case（如 CVE-2021-41773）原样复制 |
| `blackbox/docker-compose.yml` | 拓扑骨架（复制改名字即可，服务/网络结构固定） |
| `blackbox/target/`（业务外壳 + 漏洞载体） | **必须自己写** |
| `blackbox/traffic/reference_poc.py`（攻击链）、`normal_traffic.py`（正常业务） | **必须自己写** |
| `blackbox/defense/blue_controller.py`（参考防御）+ `business_tests/`（回归） | **必须自己写** |
| `ground_truth/reference_patch.diff` 等 | **必须自己写** |
| `whitebox/service/`（从源码真编译） | **必须自己写** |
| `organizer/evaluator/docker_env.py` 的 8 个方法 | **必须自己写**（骨架已给，填方法体） |
| `organizer/evaluator/docker_env.py` 的 run_with_agent / run_calibration / main | 已给好，一般不用改 |

## 快速上手

```bash
cp -r samples/_template samples/CVE-XXXX-XXXXX
# 1. 改 agent_task.json / case.env / docker_env.py 里的占位符
# 2. 搭 blackbox 环境 + 写 ground_truth + whitebox 源码
# 3. 校验 + 标定
cd ../.. && python validate_case.py samples/CVE-XXXX-XXXXX
python samples/CVE-XXXX-XXXXX/organizer/evaluator/docker_env.py --calibrate
```
