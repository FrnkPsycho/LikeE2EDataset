# ARVO

> **A**tlas of **R**eproducible **V**ulnerabilities for **O**pen-source Software —— 开源软件可复现漏洞图集。

## 一、是什么

ARVO 是一个**大规模、可复现的真实漏洞数据集**，构建在 Google OSS-Fuzz 之上。它为每一个漏洞提供标准化的"可复现包"：能在任意环境里**重新构建、重新触发、跨版本分析**，并附有触发 PoC 输入、开发者官方补丁、以及预构建好的 Docker 镜像。

- 论文：arXiv:2408.02153（被 **IEEE EuroS&P 2026** 接收）
- 作者机构：亚利桑那州立大学 SEFCOM 实验室（Arizona State University, Security Engineering for Future Computing Lab）
- 主要作者：Xiang Mei、Brendan Dolan-Gavitt、Yan Shoshitaishvili 等

## 二、要解决的核心矛盾

漏洞数据集长期存在一个"不可能三角"（trade-off）：**可复现性（reproducibility）、数量（quantity）、多样性（diversity）**三者难以同时满足：

- 手工构造的漏洞样本（如 CTF 题）→ 可复现，但数量少、不真实；
- 从真实项目搜集的漏洞 → 真实多样，但往往难以在统一环境下复现、难以跨版本分析。

ARVO 的贡献就是**给 OSS-Fuzz 的漏洞补上"完全可复现性"**，从而在数量和多样性不受损的前提下，做到可复现。

## 三、方法：如何让漏洞可复现

每个 ARVO 漏洞单元包含：

1. **漏洞版本 commit（vulnerable commit）**：漏洞存在时的代码快照；
2. **修复版本 commit（fixed commit）**：修复该漏洞的代码版本；
3. **触发 PoC 输入**：能确定性触发崩溃的输入文件；
4. **官方补丁（canonical patch）**：开发者实际提交的修复 diff；
5. **预构建 Docker 镜像**：vul / fix 两个版本的镜像，做到"一条命令复现"。

复现示例：`docker run -it n132/arvo:25402-vul arvo`

## 四、数据集规模

| 指标 | 数值 |
|------|------|
| 漏洞数量 | **6,100+**（早期 arXiv 版本为 5,000+） |
| 覆盖项目 | **311**（早期版本 250+） |
| 来源 | OSS-Fuzz 发现的 C/C++ 项目漏洞 |
| Docker 镜像 | **12,276** 个（vul + fix 两个版本） |

## 五、关键成果

- **81% 复现成功率**：比当时最优方法（state-of-the-art）提升了 **+44 个百分点**；
- **89.4% 补丁定位准确率**：在"自动定位修复 commit"这一任务上，准确率**超过了 Google 自己的 OSV 复现努力**；
- 复现效果被多个基准（含 DARPA AIxCC）实际采用验证。

## 六、重要发现：300+ "假阳性修复"

ARVO 在复现过程中发现了一个尖锐问题：**超过 300 个被 OSS-Fuzz 标记为"已修复"的漏洞，在更新版本上仍然可以被触发**——其中包括一些**多年未真正修复、实质上仍是活跃 0-day** 的漏洞。这说明"标记已修复"不等于"真的修好了"，也是 ARVO 复现价值的直接体现。

## 七、应用与影响

- **DARPA AIxCC（AI Cyber Challenge）**：ARVO 被多个参赛队伍用作 benchmark；
- **CyberGym / CyberGym-E2E**：ARVO 是其核心数据源（E2E 的 920 个任务中，717 个来自 ARVO）；
- **上游整合**：Google 正在完成把 ARVO 作为 OSS-Fuzz 官方漏洞复现组件的整合。

## 八、开源资源

| 资源 | 地址 |
|------|------|
| 源代码 | <https://github.com/n132/arvo> |
| 数据集/元数据（含 `arvo.db`、补丁） | <https://github.com/n132/ARVO-Meta> |
| Docker 镜像 | Docker Hub：`n132/arvo` |
| 论文（arXiv） | <https://arxiv.org/abs/2408.02153> |

## 九、与 CyberGym-E2E 的对应关系

CyberGym-E2E 的每个任务目录（如 `projects/curl/arvo_66012/`）直接来自 ARVO：

- `config.toml` 中的 `task_id = "arvo:66012"` → ARVO 数据库里的任务 ID；
- `vul_commit` / `patch_commit` → ARVO 记录的漏洞/修复版本 commit；
- `patch.diff` → ARVO 提供的官方修复补丁；
- `run_poc.sh` / `compile.sh` → ARVO 复现流程在 E2E 里的标准化封装。

> 关键点：E2E 的漏洞**以 ARVO/OSS-Fuzz 任务 ID + commit 为身份**，而非以 CVE 为身份。这是理解"为什么 E2E 里很多漏洞没有直接 CVE 编号"的关键。
