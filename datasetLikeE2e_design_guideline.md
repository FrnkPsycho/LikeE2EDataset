# datasetLikeE2e 数据集设计与评测架构指导文档

## 1. 文档目的

本文档用于指导 **datasetLikeE2e** 的数据集设计、样本构建、评测流程与指标组织。

datasetLikeE2e 的目标不是复刻 CyberGym-E2E，也不是将 CyberGym-E2E 作为严格子集纳入，而是借鉴其“真实漏洞 + 自动化验证 + 端到端修复评测”的思想，在此基础上扩展漏洞类型覆盖范围，并同时评价蓝队智能体的：

- 白盒漏洞修复能力；
- 黑盒攻击检测与处置能力；
- 防御措施对正常业务的影响；
- 面向同一漏洞的综合防御能力。

整体以 **2025 CWE Top 25** 作为漏洞类型覆盖基线，以具体漏洞实例作为基本评测单元，通过 S1–S7 七个阶段形成统一的验证体系。

> **datasetLikeE2e 以 2025 CWE Top 25 为漏洞分类及覆盖基线，在扩大 Web、注入、访问控制等漏洞类型覆盖范围的同时，完整纳入 CyberGym-E2E 所重点评价的越界访问、缓冲区溢出、释放后使用等主要内存安全漏洞类型。**

---

## 2. 核心设计原则

### 2.1 以漏洞实例为基本评测单元

每个数据集 Case 应对应一个可稳定复现的真实或高保真漏洞实例，并具备：

- 明确的漏洞触发条件；
- 可重复执行的攻击/PoC；
- 可判断漏洞是否仍然存在的 Ground Truth；
- 可验证正常业务功能的回归测试；
- 可构建黑盒攻击检测与处置场景的运行环境。

数据集的组织层级建议为：

```text
CWE 漏洞类型
└── Vulnerability / CVE / Case
    ├── Vulnerable Environment
    ├── Attack / PoC
    ├── Ground Truth Patch / Reference Fix
    ├── Business Regression Tests
    ├── Detection Evidence
    └── Defense Evaluation Artifacts
```

---

### 2.2 CWE Top 25 作为漏洞覆盖骨架

datasetLikeE2e 第一阶段以 **2025 CWE Top 25** 作为漏洞分类和覆盖基线。

其作用是回答：

> 数据集需要覆盖哪些主要漏洞类型？

原则上应实现：

- CWE Top 25 类型全覆盖；
- 不要求 25 类漏洞样本数量完全相同；
- 对高频、适合自动化验证的漏洞类型配置更多样本；
- 对内存安全等构建成本较高的漏洞类型，优先保证高质量代表性样本；
- 同一 CWE 下尽量覆盖不同语言、框架、软件类型和触发方式。

因此不建议机械采用：

```text
25 CWE × 固定 N 个样本
```

而建议采用：

```text
Top 25 全覆盖 + 风险/可验证性驱动的差异化采样
```

---

## 3. S1–S7 总体评测架构

datasetLikeE2e 设置 S1–S7 共七个验证阶段，并以 S4 作为两条路径的统一能力评价出口。

其中：

- **S1 为白盒修复和黑盒防御的共同入口，用于生成并验证 PoC，输入由评测模式决定；**
- **白盒模式输入为源码与漏洞环境，之后进入 S2→S3；**
- **黑盒模式输入为目标系统与漏洞描述，之后进入 S5→S6→S7；**
- **S2–S3 构成白盒修复验证路径；**
- **S5–S7 构成黑盒检测、处置及业务影响验证路径；**
- **S4 综合 white-box 与 black-box 两条路径结果，形成 Final Score 和能力短板。**

总体结构如下：

```text
        ┌────────────────┐          ┌────────────────┐
        │   白盒修复路径    │          │   黑盒防御路径    │
        └───────┬───────┘          └───────┬───────┘
                 │                           │
                 ▼                           ▼
        S1：源码 + 漏洞环境             S1：目标系统 + 漏洞描述
        生成并验证 PoC                  生成并验证 PoC
                 │                           │
                 ▼                           ▼
        S2 漏洞修复及有效性验证      S5 攻击检测能力评估
                 │                           │
                 ▼                           ▼
        S3 修复业务影响评估          S6 攻击处置有效性评估
                 │                           │
                 ▼                           ▼
                                    S7 处置策略业务影响评估
                 │                           │
                 └─────────────┬─────────────┘
                               ▼
                       ┌──────────────────────┐
                       │ S4 指定漏洞修复能力评估 │
                       └──────────────────────┘
```

---

## 4. 各阶段定义

### S1：攻击有效性验证

**目的：**

评价智能体生成并验证 PoC 的能力，确认当前 Case 中的漏洞能够被真实、稳定触发。S1 是统一阶段，其输入取决于评测模式。

**白盒模式输入：**

- 可运行的漏洞环境；
- 目标系统源码及必要配置；
- 漏洞描述、触发条件与允许的测试边界。

**黑盒模式输入：**

- 可通过网络访问的目标系统；
- 漏洞描述；
- 允许的攻击范围和执行约束。

黑盒路径不向智能体提供源码或预制 PoC。数据集内部可保留参考 PoC 和成功 Oracle，但仅供评测器验证 Case 有效性和判定攻击结果，不向受测智能体暴露。

**主要操作：**

- 白盒模式：智能体结合源码与漏洞环境生成 PoC，并执行、调整和验证；
- 黑盒模式：智能体根据目标系统和漏洞描述生成 PoC，并执行、调整和验证；
- 评测器使用隐藏的 Success Oracle 判定漏洞是否真正触发。

**主要输出：**

- PoC 及其执行与成功判定；
- PoC Generation and Validation Result；
- 漏洞是否可稳定复现；
- 漏洞触发证据；
- 基准攻击日志。

**意义：**

S1 是后续白盒修复和黑盒防御评测的共同前提。如果评测器使用内部参考 PoC 也无法稳定复现漏洞，则该样本无效；如果 Case 有效但智能体未能生成有效 PoC，则记录为 S1 能力失败，后续对应路径记为未执行。

---

### S2：漏洞修复及有效性验证

**目的：**

评价智能体是否能够针对指定漏洞生成或实施有效修复。

**输入：**

- S1 验证通过的漏洞环境和 PoC；
- 目标系统源码、配置与构建信息；
- 指定漏洞信息；
- 允许的修改范围与操作边界；
- 仅供评测器使用的 S2 Oracle 和 Reference Patch / Ground Truth。

**主要操作：**

- 智能体分析漏洞根因并生成或实施 Patch；
- 重新构建、启动修复后的目标系统；
- 重放 S1 中生成并验证的 PoC；
- 判断攻击是否失效、漏洞根因是否消除，以及修改是否超出允许边界。

**核心判断：**

- 是否进行了实际修复；
- 修复后原始攻击是否失效；
- 漏洞根因是否被消除；
- 修复是否符合预期代码或配置边界。

**主要输出：**

- Patch / 修改内容；
- 修复前后差异；
- 攻击复测结果；
- 漏洞消除判定；
- S2 Pass / Fail Result。

---

### S3：漏洞修复对于业务影响评估

**目的：**

验证 S2 的修复是否影响系统原有正常业务能力。S3 不应只执行漏洞相关模块测试或项目已有单元测试，而应将真实、系统级的业务功能破坏纳入评判。

核心思想是：

> 不仅要“修得住”，还要“不能修坏”。

**输入：**

- S2 修复后的完整可运行系统；
- 项目已有单元测试、模块测试和集成测试；
- 数据集额外构建的 API 测试和系统级 Business Workflow Tests；
- 正常输入、用户角色、权限关系和预期结果；
- 修复前的功能、性能和稳定性基线。

**主要操作：**

- 执行单元、模块、集成和 API 回归测试；
- 执行跨模块、多步骤的系统级正常业务流程，例如“登录 → 查询 → 修改 → 保存 → 权限校验 → API 调用”；
- 检查原有接口兼容性、正常输入、角色与权限边界；
- 对比修复前后的功能通过率、性能和稳定性。

**主要评价内容：**

- 项目已有测试是否通过；
- 核心业务功能是否正常；
- 系统级正常用户业务流程是否完整通过；
- 原有接口兼容性是否保持；
- 正常输入是否被误拦截；
- 性能或稳定性是否发生明显异常。

**主要输出：**

- Business Regression Test 结果；
- 分层测试通过率与系统级业务流程通过率；
- 异常功能列表；
- 性能与稳定性变化；
- 修复副作用及业务功能破坏判定；
- S3 Project Test Result 与 S3 System Business Workflow Result。

S3 与 CyberGym-E2E 中偏向“漏洞相关模块或项目已有测试”的回归验证保持区分：datasetLikeE2e 的 S3 在保留这些测试的基础上，要求额外构建可能跨越多个服务和权限边界的系统级正常业务流程。

---

### S4：指定漏洞修复能力评估

**目的：**

综合 white-box 与 black-box 两条路径的结果，对智能体针对指定漏洞的修复与防御能力形成统一评价。

**输入：**

- S2 的 Patch、攻击复测和漏洞消除判定；
- S3 的白盒测试得分、业务回归结果及性能/稳定性变化；
- S5 的检测评分与检测证据；
- S6 的处置评分与动作审计记录；
- S7 的黑盒测试评分、业务可用性、误封及性能变化；
- 两条路径的过程、超时、重试和环境稳定性记录；
- S4 评分规则。

**主要操作：**

- 综合 white-box 与 black-box 的阶段结果；
- 根据统一评分规则形成 Final Score，并识别能力短板。

**主要输出：**

- White-box Score 与 Black-box Score；
- Final Score；
- 能力短板和失败原因。

S4 重点回答：

> 智能体是否既能在保持业务正常的前提下修复漏洞，又能发现、阻断漏洞利用攻击并将业务代价降至最低？

建议至少综合：

- 漏洞修复成功性；
- 修复有效性；
- 业务回归结果；
- 修复副作用；
- 修复过程稳定性。

S4 是整个 Case 的统一评价终点，通过综合 white-box 与 black-box 结果输出 Final Score 和能力短板。

---

### S5：漏洞利用攻击检测能力评估

**目的：**

在不直接向蓝队智能体提供漏洞源码或修复 Ground Truth 的情况下，评价其对漏洞利用攻击的发现能力。

**输入：**

- 黑盒防御统一运行环境；
- S1 生成并经 Success Oracle 验证的有效攻击；
- 可向蓝队暴露的 WAF、防火墙、IDS/IPS、应用、网络和主机遥测；
- 正常流量和攻击流量的执行时间窗口；
- 仅供评测器使用的攻击 Ground Truth 和检测 Oracle。

默认不向蓝队智能体提供源码、Reference Patch、参考 PoC 或攻击成功 Oracle。

**主要操作：**

- 评测器在正常业务流量中执行已验证攻击；
- 蓝队智能体通过受控查询接口观察日志、告警、网络流和主机事件；
- 蓝队智能体输出检测结论、受攻击资产、异常事件和证据；
- 评测器检查检测正确性、时效性、误报和漏报。

S5 原则上仅开放观测和查询接口，不开放会改变环境状态的防御操作，以避免污染 S5 检测指标和 S6 处置指标。

**主要评价内容：**

- 是否检测到攻击；
- 检测是否发生在有效时间窗口内；
- 是否正确识别受攻击资产；
- 是否能够定位攻击行为或异常事件；
- 是否存在明显误报或漏报。

**主要输出：**

- 攻击检测成功与否；
- 检测时间及检测延迟；
- 受攻击资产和攻击行为定位结果；
- 检测证据、误报和漏报记录；
- S5 Detection Score / Detection Rate。

S5 的重点是：

> 看得见。

---

### S6：漏洞利用攻击处置有效性评估

**目的：**

评价智能体在发现攻击后，是否能够采取有效处置措施降低或阻止攻击影响。

**输入：**

- S5 的攻击检测结果和相关证据；
- S1 产生的有效攻击及攻击前效果基线；
- 黑盒防御统一运行环境；
- 可向蓝队开放的受控处置接口与 Allowed Defense Actions；
- 仅供评测器使用的攻击效果 Oracle。

**主要操作：**

- 蓝队智能体根据 S5 证据生成处置策略；
- 通过受控接口实施 WAF、防火墙、IDS/IPS、账号、服务隔离或网络策略；
- 评测器持续或重放攻击，对比处置前后的攻击效果；
- 记录每项处置动作的参数、时间、生效状态和影响范围。

处置方式可以包括但不限于：

- 访问控制调整；
- WAF / IDS / IPS 策略；
- 主机侧阻断；
- 服务隔离；
- 账号/权限处置；
- 网络策略调整；
- 临时缓解措施；
- 其他运行时防御策略。

**主要评价内容：**

- 攻击是否被阻断或限制；
- 攻击效果是否显著下降；
- 处置是否及时；
- 处置策略是否真正生效。

**主要输出：**

- 处置策略及动作审计记录；
- 处置耗时与策略生效时间；
- 攻击被阻断、限制或降效的程度；
- 处置成功与否及失败原因；
- S6 Containment Score / Containment Rate。

S6 的重点是：

> 挡得住。

---

### S7：处置策略对于业务影响评估

**目的：**

评价 S6 中采取的防御措施是否对正常业务产生不可接受的影响。

**输入：**

- S6 已生效的防御策略和处置后环境；
- S5 的检测结果与 S6 的处置结果；
- 与 S3 可共用或对齐的系统级 Business Workflow Tests；
- 正常用户、不同角色和合法 API 流量；
- 处置前的业务可用性、性能和误报基线。

**主要操作：**

- 保持 S6 防御策略生效，并使所有正常业务流量经过同一安全网关；
- 执行“登录 → 查询 → 修改 → 保存 → 权限校验 → API 调用”等系统级正常业务流程；
- 检查正常用户访问、核心业务可用性、过度阻断和误封；
- 对比处置前后的功能、性能与稳定性；
- 结合 S5 检测、S6 处置与 S7 业务影响结果，形成供 S4 使用的黑盒路径评价结果。

核心思想是：

> 黑盒处置不能以“大面积停服务”作为高质量防御。

**主要评价内容：**

- 正常用户访问是否受影响；
- 核心业务是否保持可用；
- 是否出现过度阻断；
- 是否产生大规模误封；
- 性能是否显著下降；
- 防御措施的业务代价是否可接受。

**主要输出：**

- 系统级业务流程通过率；
- 正常业务可用性与性能变化；
- 误封、过度阻断和异常功能列表；
- 防御措施的业务代价判定；
- S7 Business Availability Score；
- 包含 S5、S6、S7 分项结果的 Black-box Defense Result / Black-box Score。

S7 是 **黑盒路径的能力输出**。

---

## 5. S4 推荐评价维度

S4 作为统一评价出口，建议至少保留以下三类输出：

### 5.1 白盒修复能力

综合 S2 与 S3 输出。

用于反映：

- 指定漏洞是否得到有效修复；
- 修复是否保持正常业务。

---

### 5.2 黑盒对抗防御能力

综合 S5、S6 与 S7 输出。

用于反映：

- 攻击能否被发现；
- 攻击能否被有效处置；
- 处置是否保持业务可用。

---

### 5.3 Final Score 与能力短板

S4 综合 white-box 与 black-box 两条路径。为避免单一路径高分掩盖另一条路径的短板，建议至少保留：

- 双维度结果展示；
- 最低能力门槛；
- 对短板敏感的综合结果。

并同时保留：

```text
White-box Score = aggregate(S2, S3)
Black-box Score = aggregate(S5, S6, S7)
Final Score = S4_score
```

> **TODO：S4_score 的具体聚合方法与双路径最低能力门槛需基于实验结果校准。**

---

## 6. 白盒与黑盒两类 Workflow

### 6.1 白盒修复 Workflow

流程：

```text
S1 → S2 → S3 → S4
```

主要评价：

- 漏洞理解；
- 修复生成；
- 修复有效性；
- 分层回归与系统级正常业务流程；
- 指定漏洞修复能力。

白盒测试强调的是：

> 在能够获得源码、补丁上下文或其他必要开发信息的情况下，智能体能否真正修复漏洞。

---

### 6.2 黑盒对抗 Workflow

流程：

```text
S1 → S5 → S6 → S7 → S4
```

主要评价：

- 攻击发现；
- 运行时检测；
- 防御策略生成；
- 攻击处置；
- 正常业务保持。

黑盒测试强调的是：

> 在不依赖直接源码修复的情况下，智能体能否通过运行时检测与防御机制控制漏洞利用攻击。

---

### 6.3 黑盒防御统一运行环境

黑盒防御路径不应将观测和处置设施只视为 S5 的临时输入，而应定义一套贯穿 S1、S5、S6 和 S7 的 **Black-box Defense Environment**。

该环境至少包含：

- 运行漏洞业务的目标 Docker 系统；
- 位于目标入口必经路径的安全网关；
- WAF、防火墙、IDS/IPS 等检测与处置设施；
- 网络流量、应用日志和可选主机侧遥测组件；
- 向蓝队智能体开放的受控观测与处置接口；
- 红队攻击流量发生器与正常业务流量发生器；
- 掌握隐藏 Oracle、负责结果判定和环境重置的带外评测器。

逻辑拓扑建议为：

```text
                         management_net
蓝队 Agent ──────────────> Blue Controller
                                  │
                                  ▼
红队 Agent                Security Gateway
正常业务流量 ── client_net ──> WAF / Firewall / IDS
                                  │
                              protected_net
                                  │
                                  ▼
                         Target Docker Services

评测器 ──带外通道──> Success Oracle / 业务测试 / 环境重置
```

第一版不强制使用独立虚拟机。可在少量物理服务器上为每个 Case 启动一套隔离的 Docker Compose 运行实例，并将 Security Gateway 实现为具有独立网络命名空间的受控容器。未来可在不改变评测接口的前提下，替换为独立虚拟机或物理安全设备。

建议遵循以下网络与权限约束：

1. 每个 Case Run 使用独立的网络、卷、策略命名空间和日志索引；
2. 目标系统只连接 `protected_net`，不直接向宿主机发布服务端口；
3. 红队和正常业务流量必须通过 Security Gateway 访问目标；
4. 容器网络优先使用受控 bridge 模式，不使用会绕过统一观测路径的 host、macvlan 或 overlay 模式；
5. Docker 宿主机可在 `br-*`、`veth*` 或安全网关网络命名空间中采集流量，也可使用 tc/eBPF 等机制统一观测；
6. S5 仅开放只读观测能力，S6 才开放受控处置能力；
7. 蓝队不应获得目标源码、Docker Socket、宿主机无限 root 权限或隐藏 Oracle；
8. 防御动作应通过受控 API 执行并全量审计，避免蓝队以停机、删除容器或全局断网作为高质量处置；
9. S3 和 S7 应尽可能共用或对齐同一套系统级业务流程，便于比较 Patch 和运行时处置对业务的影响。

对于普通 Web、注入、访问控制和用户态内存安全漏洞，可优先使用非特权容器。涉及内核漏洞、容器逃逸或需要强隔离的 Case，应在专用物理节点上串行运行，或后续引入 gVisor、Kata Containers、Firecracker 或独立虚拟机。

---

## 7. 与 CyberGym-E2E 的关系

datasetLikeE2e 与 CyberGym-E2E 的关系应明确表述为：

> datasetLikeE2e 借鉴 CyberGym-E2E 的端到端漏洞修复评测思想，但 CyberGym-E2E 并不是 datasetLikeE2e 的严格子集。

两者主要区别如下：

| 维度 | CyberGym-E2E | datasetLikeE2e |
|---|---|---|
| 主要漏洞范围 | 以 C/C++ 内存安全漏洞为主 | 以 2025 CWE Top 25 为覆盖基线 |
| 核心能力 | 漏洞修复与回归验证 | 白盒修复 + 黑盒对抗防御 |
| 组织方式 | OSS-Fuzz 等真实漏洞任务 | CWE → Vulnerability/CVE → Case |
| 业务回归深度 | 漏洞相关模块或项目已有测试为主 | 已有测试 + API/集成测试 + 系统级正常业务流程 |
| 评价出口 | 修复效果 | S4 综合白盒与黑盒结果形成 Final Score |
| 黑盒检测/处置 | 非核心 | 核心评价内容 |

datasetLikeE2e 应保证覆盖 CyberGym-E2E 所重点涉及的主要内存安全漏洞类型，例如：

- Out-of-bounds Write；
- Out-of-bounds Read；
- Use After Free；
- Buffer Overflow；
- Stack-based Buffer Overflow；
- Heap-based Buffer Overflow；
- NULL Pointer Dereference 等。

但不应表述为：

> CyberGym-E2E 的所有具体 Case 都是 datasetLikeE2e 的子集。

更准确的关系是：

> datasetLikeE2e 在漏洞类型层面覆盖 CyberGym-E2E 重点涉及的主要内存安全弱点，并进一步扩展至 CWE Top 25 中的 Web、注入、访问控制、文件处理等其他重要漏洞类型。

---

## 8. 数据集 Case 筛选原则

并非所有 CWE Top 25 对应漏洞都适合直接纳入 datasetLikeE2e。

候选 Case 建议经过以下筛选：

```text
CWE Top 25
    ↓
候选漏洞/CVE
    ↓
漏洞环境可稳定构建
    ↓
攻击/PoC 可稳定复现
    ↓
Ground Truth 明确
    ↓
可进行白盒修复验证
    ↓
可构建业务回归测试
    ↓
可构建黑盒检测/处置场景
    ↓
datasetLikeE2e Case
```

优先选择同时满足以下条件的样本：

1. 漏洞真实、边界清晰；
2. 漏洞可重复触发；
3. 修复 Ground Truth 明确；
4. 业务功能可以自动验证；
5. 攻击过程中存在可观测证据；
6. 可以实施有效的运行时防御措施；
7. 白盒与黑盒两条 Workflow 均具有评价意义。

---

## 9. Case 推荐数据结构

每个 Case 建议至少包含：

```yaml
case_id:
cwe_id:
cwe_name:

vulnerability:
  product:
  version:
  language:
  framework:
  description:

environment:
  target:
    images:
    services:
    startup:
    healthcheck:
  networks:
    client_net:
    protected_net:
    management_net:
  security_gateway:
    implementation: container  # 第一版；可替换为 VM / 物理设备
    waf:
    firewall:
    ids_ips:
  telemetry:
    application_logs:
    network_telemetry:
    host_telemetry:
  traffic_generators:
    red_team:
    normal_business:
  evaluator:
    out_of_band_access:
    reset:

attack:
  generated_poc:
  reference_poc:  # evaluator_only
  prerequisites:
  success_oracle:  # evaluator_only
  evidence:

ground_truth:
  reference_patch:
  vulnerable_code:
  fixed_code:

business_tests:
  existing_project_tests:
  module_and_integration_tests:
  api_tests:
  system_workflows:
  roles_and_permissions:
  pre_change_baseline:
  expected_results:

whitebox:
  s1_input:
    source_code:
    vulnerable_environment:
    vulnerability_description:
  repair_input_scope:
  allowed_operations:
  s2_oracle:
  s3_oracle:
  s3_whitebox_score:

blackbox:
  s1_redteam_input:
    target_endpoint:
    vulnerability_description:
    attack_constraints:
  s1_generated_poc:
  blue_observability:
    observable_logs:
    network_telemetry:
    host_telemetry:
  blue_control:
    query_apis:
    allowed_defense_actions:
    action_audit:
  s5_score:
  s6_score:
  s7_score:

final:
  whitebox_score:
  blackbox_score:
  minimum_capability_gate:
  s4_score:  # Final Score; TODO: aggregation method
  capability_gaps:
```

---

## 10. 数据集推荐输出指标

datasetLikeE2e 不建议仅给出单一总分。

至少应保留以下几组指标。

### 10.1 Stage-level Metrics

```text
S1 PoC Generation and Validation Success Rate（按评测模式分别统计）
S2 Pass Rate
S3 Project Test Pass Rate
S3 System Business Workflow Pass Rate
S5 Detection Rate
S6 Containment Rate
S7 Business Availability Score
S4 Final Score（aggregation TODO）
```

---

### 10.2 CWE-level Metrics

按 CWE 类型输出：

```text
CWE-79 Pass Rate
CWE-89 Pass Rate
CWE-787 Pass Rate
...
```

用于分析不同智能体在不同漏洞机制上的能力差异。

---

### 10.3 Workflow-level Metrics

分别统计：

```text
White-box Repair Score
Black-box Defense Score
Overall Defense Completeness
```

避免将不同性质的红蓝能力混成一个不可解释的单一分数。

---

## 11. 第一版数据集建设建议

第一阶段建议优先完成以下目标：

### 目标 1：建立 CWE Top 25 覆盖表

至少维护：

```text
CWE ID
CWE Name
候选 Case 数
已完成 Case 数
语言/框架
白盒适配性
黑盒适配性
当前状态
```

---

### 目标 2：优先构建“双路径均可评价”的样本

第一版优先选择：

- 漏洞利用稳定；
- Patch 明确；
- 业务功能清晰；
- 攻击容易观察；
- 防御策略可实施；

的 Case。

这样可以最大程度验证 S1–S7 框架本身是否成立。

---

### 目标 3：先验证评测体系，再扩大规模

第一阶段不应过度追求 Case 数量。

更重要的是验证：

- S1–S7 是否能够自动运行；
- S2–S3 是否可以稳定评价白盒修复能力；
- S7 是否可以稳定评价黑盒防御能力；
- S4 的门槛与聚合方法是否能够形成合理的综合评价；
- 不同 Agent 的能力差异是否能够被指标真实区分。

在评价框架稳定后，再扩大 CWE 和 Case 数量。

---

### 目标 4：建立可容器化部署的黑盒防御环境

第一版优先在现有少量物理服务器上实现：

- 每个 Case Run 独立的 Docker Compose 实例；
- `client_net` / `protected_net` / `management_net` 三类逻辑网络；
- 容器化 Security Gateway 与受控蓝队 API；
- 红队攻击流量与正常业务流量同路径进入目标；
- 可重现、可审计和可自动重置的运行环境。

---

## 12. 当前版本的一句话定义

> **datasetLikeE2e 是一个以 2025 CWE Top 25 为漏洞类型覆盖基线、以真实可复现漏洞实例为基本评测单元，通过 S1–S7 统一验证流程评价 PoC 生成与验证能力、智能体白盒漏洞修复能力以及黑盒攻击检测处置能力，并由 S4 形成统一能力评价的端到端安全智能体评测数据集。**

---

## 13. 当前暂不纳入的设计

为避免第一版体系过度复杂，当前暂不引入：

- OWASP Top 10 作为独立分类体系；
- ATT&CK 等攻击战术标签作为核心数据组织维度；
- 多套风险分类体系的交叉映射；
- 仅用于增加标签数量、但不直接服务 S1–S7 评价的分类字段；
- S4_score 的最终聚合公式与双路径门槛（TODO）。

后续如需要构建更复杂的企业级攻击链场景，可以在不改变 CWE 主分类体系的前提下增加场景标签。

---

## 14. 当前架构总结

最终可将 datasetLikeE2e 概括为四层：

```text
第一层：漏洞范围
2025 CWE Top 25

        ↓

第二层：数据样本
真实漏洞 / CVE / Vulnerability Case

        ↓

第三层：评测流程
S1–S7
├── 白盒：S1 → S2 → S3 → S4
└── 黑盒：S1 → S5 → S6 → S7 → S4

        ↓

第四层：综合评价
white-box + black-box → S4 Final Score（聚合方法 TODO）
```

核心思想可以概括为：

> **同一个漏洞，两条防御路径，一套统一评价体系。**
