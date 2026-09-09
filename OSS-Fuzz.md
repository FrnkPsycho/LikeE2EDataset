# OSS-Fuzz

> 持续模糊测试（Continuous Fuzzing）开源软件的服务，由 Google 于 2016 年发起。

## 一、是什么

OSS-Fuzz 是 Google 运营的一个**免费、持续运行的模糊测试服务**，对开源项目的源代码进行不间断的 fuzz，自动发现并报告其中的内存安全类 bug，并跟踪直到修复。它的核心目标是：让开源软件的 C/C++ 等底层代码库，在漏洞被攻击者利用之前，先被机器"暴力"挖出来。

- 项目主页：<https://github.com/google/oss-fuzz>
- 维护方：Google（与开源社区协作）

## 二、背景与动机

2014–2016 年出现了一批影响深远的开源底层库漏洞（如 Heartbleed、Shellshock 等），暴露了"关键基础设施依赖的开源 C/C++ 代码缺乏系统性安全检查"的问题。OSS-Fuzz 的出发点就是：**把 Google 内部的 ClusterFuzz 模糊测试基础设施，开放给所有开源项目**，规模化地发现内存安全漏洞。

## 三、工作流程

一个项目加入 OSS-Fuzz 后，会进入一条自动化流水线：

1. **接入**：项目维护者提交 fuzz harness（即"怎么喂输入给某个函数/模块"的入口代码）和构建脚本。
2. **持续 fuzz**：ClusterFuzz 基础设施每天对新提交的代码持续 fuzz，分配大量 CPU 并行测试。
3. **崩溃去重与判定**：发现崩溃后自动最小化测试用例、判定是否为真实且新的 bug。
4. **报告**：自动通知项目维护者，附带可复现的崩溃输入和堆栈。
5. **修复验证**：维护者修复后，OSS-Fuzz 自动验证该崩溃是否已消失（regression 检测）。

## 四、核心技术

### Fuzzing 引擎（Fuzzing Engine）
- **libFuzzer**（LLVM 内置，默认主力）
- **AFL / AFL++**
- **Honggfuzz**

### Sanitizer（内存/未定义行为检测器）
- **ASan**：AddressSanitizer，检测越界读写、use-after-free 等
- **MSan**：MemorySanitizer，检测未初始化内存读取
- **UBSan**：UndefinedBehaviorSanitizer，检测未定义行为
- **TSan**：ThreadSanitizer，检测数据竞争

## 五、支持的语言

最初只面向 C/C++，现已扩展：

| 语言 | 状态 |
|------|------|
| C / C++ | 主力（绝大多数项目） |
| Rust | 支持 |
| Go | 支持 |
| Python | 支持 |
| Java / JVM | 支持（Jazzer） |
| JavaScript | 支持（Jazzer.js） |

架构上支持 x86_64 与 i386。

## 六、披露政策

OSS-Fuzz 遵循**负责任的披露**原则：给维护者 **90 天**修复期；到期未修复则自动公开 bug 详情。这推动了快速修复，也让 OSS-Fuzz 的漏洞数据能逐步进入公开数据库。

## 七、规模与影响

截至 **2025 年 5 月** 的累计数据：

| 指标 | 数值 |
|------|------|
| 参与项目 | **1,000+** |
| 识别并修复的漏洞（vulnerabilities） | **13,000+** |
| 识别并修复的 bug（含非安全崩溃） | **50,000+** |

> 注意这里的"漏洞（vulnerabilities）"与"bug"是两个量级：前者是被认定有安全影响、可能分配 CVE 的那部分；后者包含所有被修复的崩溃/缺陷（很多并没有 CVE）。这一点对理解后面 CyberGym-E2E 的构成很关键。

## 八、生态与数据

- **OSV**（<https://osv.dev>）：开放的漏洞数据库，收录 OSS-Fuzz 及其他来源的漏洞记录，统一为 OSV 格式（含 Git commit 范围、影响版本等）。
- **oss-fuzz-vulns**（<https://github.com/google/oss-fuzz-vulns>）：把 OSS-Fuzz 中**已被确认为安全漏洞**的 bug 整理成 OSV 格式，附 CVE 编号、影响范围、修复 commit。
- **CVE 关联**：OSS-Fuzz 发现的 bug 中，只有一部分被判定为安全漏洞并分配 CVE，其余只是"崩溃但不构成安全风险"。

## 九、与其他项目的关系

- **ARVO**：基于 OSS-Fuzz 的历史 bug，构建"可复现漏洞数据集"，是 OSS-Fuzz 漏洞的"复现层"。
- **CyberGym / CyberGym-E2E**：把 ARVO / OSS-Fuzz 的漏洞打包成 AI 智能体的评测任务。
- **OSS-Fuzz 正在整合 ARVO**：作为其官方漏洞复现组件。

## 十、参考链接

- OSS-Fuzz 仓库：<https://github.com/google/oss-fuzz>
- OSV 数据库：<https://osv.dev>
- oss-fuzz-vulns：<https://github.com/google/oss-fuzz-vulns>
