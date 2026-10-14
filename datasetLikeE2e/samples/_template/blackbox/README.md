# blackbox/ —— 黑盒环境（模板说明）

黑盒 agent 只能从共享出口打，看不到源码。这里要建：

| 子目录 | 说明 | 谁写 |
|---|---|---|
| `<target>/` | **业务外壳 + 漏洞载体**：Dockerfile + 配置 + 合法业务（页面/功能）。漏洞藏在某个功能里 | 出题人 |
| `security_gateway/` | 网关（策略执行点 + 蓝队观测点，管理 API /events /alerts /rules） | **复制**（从 CVE-2021-41773 等） |
| `shared_egress/` | 透明 TCP 出口（数据面三类流量共用同一源 IP） | **复制** |
| `traffic/replay_poc.py` | poc.bin 逐字节重放驱动（通用） | **复制** |
| `traffic/reference_poc.py` | 参考 PoC：无防御时能稳定打中漏洞的攻击链 | 出题人 |
| `traffic/normal_traffic.py` | 正常业务流量（真实用户怎么用） | 出题人 |
| `defense/blue_controller.py` | 参考防御：`GatewayClient` + `detect(client)` + `contain(client)` | 出题人 |
| `defense/strategies.json` | 防御策略（检测特征 + 处置规则） | 出题人 |
| `business_tests/test_business.py` | 业务回归（pytest，S3/S7 判据） | 出题人 |
| `runner/Dockerfile` | 通用 runner 镜像（跑 traffic/defense/business） | **复制** |

**关键点**：蓝队容器 `bb_blue_team` 不挂任何答案（defense/traffic/ground_truth 都不挂），environment 里不预置 token。
