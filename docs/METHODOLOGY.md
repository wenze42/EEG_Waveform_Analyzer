# 核心方法论：AI 写代码，不缺速度，缺对齐

> **来源**：2026年11月5日 犀牛鸟社团技术例会 · 李飞涛分享
> **实战验证**：LingDoc 项目（github.com/magician336/lingdoc）
> **范式来源**：Matt Pocock 开源技能集（github.com/mattpocock/skills）

---

## 一句话结论

**AI 写代码，不缺速度，缺对齐。**

- 写代码的能力在贬值，定义问题和判断证据的能力在升值。
- 手写代码会渐渐变成爱好，审查和监督 AI 写代码是新手艺。
- 把 AI 当**工程实习生**管理——给清晰的规范、检查清单和验收标准。

---

## AI 写代码的四种失败

### 1. 对齐错位（最大的失败）
你和 AI 说的不是同一个需求，它按自己的理解写完了。

**实例**：LingDoc Issue #636 — 规范只要求"版本仍有效"，实现却自信地多加了"已确认 + 等于评估版"的条件，导致许可链结构上无法稳定化。

**治法**：grilling（拷问）——写代码之前，AI 先把需求画成设计树，一轮一轮追问直到前沿清空。

### 2. 代码不工作
自信地写出幻觉 API、编造的测试——看起来对，跑起来错。

**治法**：tdd（红绿循环）+ code-review（双轴评审）+ dev-gating（验收矩阵）。

### 3. 输出冗长
上下文被废话占满，真正的约束被淹没。大模型标称百万级窗口，实际使用率 80% 就触发自动压缩。

**治法**：渐进式披露——skill 默认只加载名称和描述，调用时才加载完整内容；pruning——定期修剪 skill，不加节制堆 skill = 新熵增。

### 4. 代码库熵增
每次改动引入一层混乱，最终变成 "ball of mud"。AI 新增功能时容易忽略原有规范，自立门户。

**治法**：improve-codebase-architecture（扫出深化机会）+ domain-modeling（维护术语表）+ AGENTS.md（常驻规则）。

---

## 范式：把工程纪律打包成 Skill

### Skill 是什么

一段 Markdown 写成的自然语言工程纪律，说清楚三件事：

```yaml
---
name: grilling
description: "什么时候触发"
---
# 怎么做
- 祈使句写成、逐条可执行的规则
# 停止条件
前沿清空、共识确认——否则拒绝动手写码
```

三个词：**小、可组合、可忽略**。每个 skill 独立可用，你的项目可以只挑两三个。

### 技能集全家福（38 个 · 本仓库已全装）

```
🔥 Grilling 全家桶       grilling, grill-me, grill-with-docs
📝 规划 → 执行           to-spec → to-tickets → implement-spec
🔧 工程流                tdd, diagnosing-bugs, code-review
📄 交付                  pr, retro
🏗️ 架构治理              improve-arch, codebase-design, domain-modeling
🏷️ 流程管理              triage, wayfinder, chief-of-staff
🧪 探索                  prototype, research, wizard
🛡️ 安全                  git-guardrails, setup-pre-commit
🎯 Productivity          teach, handoff, wait-what, to-questionnaire
🤖 路由器                ask-matt
💾 自定义（本仓库新增）   dev-gating, health-scoring
```

### 核心流水线

`to-spec`（对话变规格）→ `to-tickets`（拆成曳光弹工单）→ `implement-spec`（并行子代理实现）→ `dev-gating`（验收矩阵 + 证据）→ `health-scoring`（结构债务诊断）→ `pr`（写 PR body）→ `code-review`（双轴评审）→ `retro`（会话复盘）

---

## 实战：LingDoc 的四件套

### 四件套是什么

| 文件 | 作用 | 对应 Pocock 概念 |
|------|------|-----------------|
| **CONTEXT.md** | 产品语境 + "避免"表 | 共享词汇——专治对齐错位 |
| **GLOSSARY.md** | 人机共用词汇表（246 行） | 共享词汇（落到术语级） |
| **AGENTS.md + docs/adr/** | 16 个 ADR：规则 + 历史决策 | 规则 + 尊重历史决策 |
| **.agents/skills/** | 三个自定义 skill（dev-gating, health-scoring, arch-loop） | "拿来改成自己的"——不是照搬，是长在项目规矩上 |

### LingDoc 实战数据

- 780+ 累计开过的 issue（编号已到 #779）
- 49 当前 open，修一个关一个
- 97 后端包目录，接近百模块
- 16 个 ADR 决策记录

### 两个纪律时刻

#### 时刻 A：审计失败的告警写在哪

AI 十有八九会"图省事"把告警写进业务事务——但业务事务可能正因这次失败在回滚，告警跟着一起消失。

**规范**（ADR 0011）：告警写在自己的独立事务里。
- 分级策略：读类 fail-open（继续读、另发告警）；关键写 fail-closed（业务 + 审计一起成功或一起失败）

#### 时刻 B：PR 证据门禁

"AI 说过了，不算；证据过了，才算。"

- 写代码之前先建验收矩阵（成功、失败、权限、恢复路径全覆盖）
- PR 从 Draft 转 Ready，不靠 AI 汇报"做完了"，靠矩阵每一行有当前代码版本的验证证据
- 绿色通用 CI 不能替代 Spec 证据
- **代码合并不等于验收通过**

---

## 代价与回报

### 代价 1：CONTEXT/GLOSSARY 持续投入
化解：维护交给 AI，人只审——支出的是"审查那几分钟"，不可外包的是判断。

### 代价 2：技能会被 AI 忽略
化解：门禁与验证兜底——skills 管"怎么做"，gate 管"没做到就拦住"。

### 代价 3：门禁过重会拖慢开发
化解：分级处理——读类 fail-open，关键写 fail-closed。

### 回报
一个持续生产的真实系统。LingDoc 从 0 到 780+ issue、16 个 ADR、97 个模块，纪律可控。

---

## 人机新分工

| 维度 | 人（判断 · 不可外包） | AI（执行 · 可规模化） |
|------|----------------------|----------------------|
| 需求 | 定义 + 确认（grilling 的甲方） | 提问 + 澄清 |
| 规范 | 写 CONTEXT / GLOSSARY / ADR | 遵守 + 提示冲突 |
| 代码 | 审证据、做决策 | 生成、重构、修 bug |
| 验收 | 定矩阵、判 PASS/FAIL | 跑验证、补证据 |

> "以后人和 AI 的分工：人去提需求、定义、确认，AI 负责遵守、生成、重构修 bug；人再去审代码、做决策，AI 去跑证据、补验证；最后人再去做验收。"

---

## 三层接口：从 Prompt 到 Skills

```
Prompt   (一次性)   → 每次从零开始，状态留不下
Rules    (常驻)     → AGENTS.md，一直在场，每次生效
Skills   (结构化)   → SKILL.md，可触发的工作流，带步骤、约束和停止条件
```

从轻到重：成本递增，带走的纪律也越多。**越往右越接近协议、越可携带**。

---

## 插头与插座

**核心理念**：AI 编程不应和特定智能体软件绑定。

```
插头 = 智能体（Claude Code / Codex / Cursor / Gemini CLI / ...）
       随时可换，即插即拔

插座 = 你的代码仓库（CONTEXT.md / GLOSSARY.md / AGENTS.md + ADR / .agents/skills/）
       长期资产，不跟任何厂商走

协议 = 协作模式（词汇 · 规范 · 流程 · 门禁）
       写进仓库文件，纪律住进文件而不是会话
```

> 自测：如果"我的会话都在 Claude Code 里，迁不动"——说明你的协作模式从未离开过那家工具。

---

## 技能选择的四个维度

| 维度 | 含义 |
|------|------|
| **触发（Invocation）** | 什么场景自动唤起，唤不起来等于没有 |
| **内部结构（Internal Structure）** | 步骤清晰、可执行 |
| **行为引导（Behavioral Steering）** | 先收敛方向再动手（grilling 就是 steering） |
| **克制修剪（Pruning）** | 技能会膨胀，要定期删 |

**自查口令**：触发得准吗？步骤实吗？方向收敛吗？清单瘦吗？

> "不加节制地堆技能，其实就是一个熵增啊。"

---

## 今晚就能做的三件事

1. **写一页 CONTEXT.md** — 带上"避免"表，把最容易混的两三个概念写死
2. **装技能集，只用 grilling** — 装进你正在用的 agent，先只开 grilling 这一个（别贪多）
3. **固化最痛的环节** — 比如 PR 审查，固化成一个 skill；记得季度修剪

**最小起步 = 一页文档 + 一个技能**。插头随你换，纪律跟仓库走。

---

## 资源

| 资源 | 链接 |
|------|------|
| **Pocock 技能集** | github.com/mattpocock/skills |
| **LingDoc 实战仓库** | github.com/magician336/lingdoc |
| **《软件设计哲学》** | John Ousterhout（deep module 词汇源头） |
| **Total TypeScript** | mattpocock.com |
| **agskills.dev** | 技能目录站 |

---

## 本周挑战

**用 grilling 跑通你手头任何一个真实小需求**，下次社团活动带回来交流："AI 问了几个问题？哪个问题最值？"
