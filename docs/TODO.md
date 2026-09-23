# TODO / 待办

> 维护一份跨会话的待办与待定项，避免关键决策反复重议。最后更新：2026-09-23。

## 0. 待决的下一步方向

**下一步先测「其他模型 × 单题」，还是「单模型 × 多题」？**

- 现状：只有 1 个样例（CVE-2025-24928，崩溃型），评分最终要切成"通过率"。
- 倾向结论（见对话）：**先多弄几个题目**，因为"通过率"必须跨多题才有意义；但顺序是
  `跑通真实 docker 管线 → 扩 5~10 题 → 再用 2~3 个模型做最小交叉验证区分力`。
- 状态：**待你拍板**。

## 1. 评分

- [ ] S4 聚合方法 / GT 复测权重与最低门槛（设计层 TODO）：最终用"通过率"，规模化后切回；当前样例用 `mean(白盒分, 黑盒分)` 过渡。
- [ ] 双路径最低能力门槛 / missing-path policy（某路径或 GT 复测未执行时总分怎么算）。
- [ ] **硬约束（不可违反）**：评分禁用静态 mock，必须真编译 + 重放攻击链；`grade_submission.py`（mock）只作自检，收敛到 `docker_env.py`。

## 2. 数据 / 样例

- [ ] 当前仅 1 个样例（崩溃型），需扩 **5~10 个经典 CVE 做一期选型验证**（对齐设计指导 §11 目标 2/3）。
- [ ] flag 型样例尚未落地：现有 20 个 e2e CVE 全崩溃型（`docs/e2e-CVE-flag-capability.md`），需从 cvelistV5 按 flag 型 CWE 筛真实 CVE。
- [ ] CWE Top 25 覆盖表（设计指导 §11 目标 1）。

## 3. 工程

- [ ] 真实 docker 端到端验证：`organizer/evaluator/docker_env.py` 在真 docker 上跑通（需 Docker Desktop + `target:vul/fixed` 镜像；当前只过 local_harness mock + compose config）。
- [ ] submission → docker 注入接线：被测方 `blue_controller.py` 如何进评测环境（当前挂的是 `organizer/defense` 答案版）。
- [ ] `case.yaml` / `_deliver/` 副本与新流程同步。
- [ ] 目录语义：`datasetLikeE2e/samples/` = 完整样例（组织方）；`D:\Like2eTest` = 智能体答题路径。

## 4. 讨论项（deferred）

- [ ] #2：让 agent 自主跑 bash 取代 harness —— **已被 §5「测 agent」吸收**：agent 自主跑 bash = 组织方沙箱里跑的 agent 容器，不再是独立 harness 讨论项。

## 5. 评测对象与运行架构（已定：测 agent）

**评测对象 = agent（框架 + 模型整体），不是单独模型**（2026-09-21 拍板）。

**与 e2e 的区别（2026-09-23 查证修正）**：e2e 测的也是 agent（README 标题即 "AI Agents'"），
但把 harness 当 benchmark 基础设施——`run_agent.py --agent` 内置 `claude-code/openhands/codex/gemini-cli`
四选一，模型只是 harness 里可换的参数。真正区别是**谁拥有 harness**：e2e = benchmark 提供
harness、只换模型；我们 = 做题方提交完整 harness，把「agent 工程能力」也纳入评测。

**运行架构（2026-09-23 更新，替换旧的「agent 容器 = 交付物」）**：
- 一个**共用镜像**：红队 / 蓝队 / 业务系统全在里面。
- **白盒 = 1 个攻击者容器**：做题方 agent 放指定目录 → 跑出题方公开脚本 → 产出 `poc.bin` + `fix.patch`。
- **黑盒 = 攻击者容器 + 防御者容器**：攻击者据「漏洞信息」攻击系统 → `poc.bin`；防御者监控流量、同步检测 → `block.policy`。
- 做题方交的是 **harness（放进指定目录）**，不是交整个容器镜像。

**做题方提交**：一个实现标准接口的 agent，放进容器指定目录；出题方公开脚本拉起它。
**组织方提供**：题目包 / 共用镜像 / 环境三网 / 沙箱（攻击者+防御者容器 + squid 白名单）/ 判分器。

**六个拍板点（2026-09-23 新增）**：
- [ ] ① **公开脚本 + 指定目录 = agent 标准接口，写死**：目录约定（如 `/challenge/agent/` + entrypoint 名）、脚本拉起方式（传参/身份/超时）、产出落点（`/submission/poc.bin`、`fix.patch`、`block.policy`）。协议一写死 = 做题方交什么 + 组织方怎么判同时定死。
- [ ] ② **`block.policy` 格式 + 消费方**：统一之前「IP 黑名单 + WAF 规则」两块；定形态（结构化 JSON / 正则+IP 集合）与被谁消费（gateway/waf 读它阻断）。决定 S6/S4 判据能否落地。
- [ ] ③ **【open】攻防容器隔离**：防御者只能看流量，不能读攻击者容器文件 / `poc.bin`（否则 S6 变成照抄攻击 payload）。防御者观察面 = 流经网关/目标的应用层流量（对应 `blue_controller` 读 `app.log`）。
- [ ] ④ **【open】「同步检测」的观察点**：已定部分——并发下防御者必见真实攻击，故 S5 送分、S6/S4 靠泛化；封 IP 不算分、S4 用 GT 变种（新 IP `10.30.0.11` + 新 payload）是唯一防「记住一条」机制（不重开）。待定子项——S5/S6 是「攻击进行中同步」还是「攻击后从日志」，决定防御者输入是 live 流量还是事后日志。
- [ ] ⑤ **【open】黑盒给攻击者的「漏洞信息」具体是什么**：CVE 文本/漏洞描述（测已知漏洞利用）vs 无源码 + 接口文档（测黑盒探测 + 发现）。决定 S1-B 难度与白/黑区分度。
- [ ] ⑥ **【open】红/蓝是同一个 agent 还是两个**：影响判分口径（整体 vs 红蓝分离）。两个独立容器天然隔离上下文，决定 S1-B（红）与 S5/S6（蓝）是否还有 session 隔离顾虑。

**沿用不变**：
- **断网 scope 到 agent 所在容器**（攻击者/防御者），业务系统容器间互访；共用镜像不影响（镜像同、实例不同、网络按容器挂）。squid 白名单仍按做题方声明的模型端点动态放行，不写死。
- **评分判据**仍真编译 + 重放攻击链；`block.policy` 被 enforcement 消费后重放 GT 变种验证泛化（接 plan「黑盒 S4 真值泛化」）。
- **防作弊边界**：网络层防「agent 无意查公开 fix」；攻防容器隔离防「防御者照抄攻击答案」；防不了「做题方故意硬编码答案」（协议/信任层）。
- **组织方预起环境（暂不改动，仅记录）**：`docker compose up -d` 起 5 个常驻服务（target/frontend/security_gateway/waf/blue_controller）；traffic 3 个（red_team/red_team_gt/normal_business）是 `profiles` 一次性、评测器才 run。agent 用**服务名**直连（`http://security_gateway/`、`http://blue_controller:9000/`，均在 client_net），不用 host 端口 `127.0.0.1:8081/9000`（那是给宿主机评测器的）。需补：①就绪等待（现无 healthcheck，轮询 gateway 就绪再起 agent）②agent 服务定义（join client_net + squid egress）。
