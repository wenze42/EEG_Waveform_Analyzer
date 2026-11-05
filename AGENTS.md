# AGENTS.md

## Agent skills

### Issue tracker

Issues and specs live as GitHub issues in `wenze42/EEG_Waveform_Analyzer`. Uses the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical triage roles, label strings equal to role names (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Skill router (ALWAYS read before acting)

All 38 skills under `.agents/skills/*/SKILL.md` are **model-invoked** (`disable-model-invocation: false`). Scan this table every session and invoke the matching skill proactively — do not wait for the user to ask.

Each entry lists the trigger phrases, the skill name, and a one-line description. Skill paths are relative to `.agents/skills/<name>/SKILL.md`.

#### Grilling & Planning

| When user says… | Skill | Description |
|-----------------|-------|-------------|
| "拷问"、"grill"、质疑计划、想 stress-test 想法 | `grill-me` | 对计划/设计进行无情拷问，直到每个设计分支都解决 |
| grill-me + 还想建术语表和 ADR | `grill-with-docs` | 拷问 + 同步生成领域模型文档 |
| 任何需要拷问的场景的底层引擎 | `grilling` | 可复用的拷问原语，被 grill-me / grill-with-docs 等调用 |
| 选哪个 skill / 纠结用哪个流程 | `ask-matt` | 路由器：问它"我这个场景该用哪个 skill" |

#### Implementation Flow (spec → tickets → code)

| When user says… | Skill | Description |
|-----------------|-------|-------------|
| 把当前对话/想法写成 spec | `to-spec` | 合成 spec 并发布到 GitHub issues |
| 把计划拆成 tickets / 任务清单 | `to-tickets` | 拆成带 blocking edges 的 tracer-bullet tickets |
| 根据 spec 或 tickets 开始实现 | `implement` | 执行实现，跑 tdd，最后 code-review |
| 把整个 spec 一次性全部实现 | `implement-spec` | 任务图并发实现所有 ready frontier tickets |

#### Debug & Quality

| When user says… | Skill | Description |
|-----------------|-------|-------------|
| debug、诊断 bug、性能问题、报错、卡住 | `diagnosing-bugs` | 纪律化诊断循环：red feedback → 最小化 → 假设 → 插桩 → 修复 |
| 写代码，强调测试先行、红-绿-重构 | `tdd` | Test-Driven Development 完整指南 |
| code review、审查改动 | `code-review` | 双轴审查：Standards（规范）+ Spec（需求） |
| 写 PR body | `pr` | PR 规范：最小可视化总结 + 前后证据 + 风险评估 |
| retro、回顾会话、改进建议 | `retro` | 编码会话后按严重程度输出改进建议 |

#### Architecture & Codebase Health

| When user says… | Skill | Description |
|-----------------|-------|-------------|
| 改善代码架构、找模块深化机会 | `improve-codebase-architecture` | 扫描代码库生成 HTML 报告，然后拷问选哪个 |
| 定义/修改模块接口、seam、deep module | `codebase-design` | deep module 设计的共享词汇和方法论 |
| 打磨领域模型、写 GLOSSARY.md、写 ADR | `domain-modeling` | 主动构建和打磨项目的领域模型 |
| setup 完成后初始化配置 | `setup-matt-pocock-skills` | 首次 setup（issue tracker / triage labels / domain docs） |

#### Triage & Tracking

| When user says… | Skill | Description |
|-----------------|-------|-------------|
| 分诊 issue、状态机处理 ticket | `triage` | issues/PRs 状态机分诊：needs-triage → ready-for-agent/human → wontfix |
| 超大型任务规划、超过一个 session 的工作 | `wayfinder` | 在 issue tracker 上建 decision map，逐个解谜 |
| 单 session 协调多子 agent 追踪长目标 | `chief-of-staff` | 协调子 agent 并行工作 |

#### Prototyping & Research

| When user says… | Skill | Description |
|-----------------|-------|-------------|
| prototype、原型、快速验证 UI/逻辑 | `prototype` | 一个可分享 HTML 文件或多个可切换 UI 变体 |
| research、调研、查资料、API 文档 | `research` | 后台 agent 基于一手资料调研，输出带引用 Markdown |

#### Human-in-the-Loop & Safety

| When user says… | Skill | Description |
|-----------------|-------|-------------|
| 配置凭证、基础设施、CI secrets、跑迁移 | `wizard` | 交互式 bash wizard，引导人类完成只有人能做的步骤 |
| 阻止危险 git 命令（push/reset --hard 等） | `git-guardrails-claude-code` | Hook 拦截危险 git 操作 |
| Husky、pre-commit、commit 检查 | `setup-pre-commit` | 配置 commit-time 自动化检查 |

#### Handoff & Session Management

| When user says… | Skill | Description |
|-----------------|-------|-------------|
| handoff、交接给另一个 agent 继续 | `handoff` | 把对话压缩成 handoff 文档 |
| Claude Code 专用 handoff 给后台 agent | `claude-handoff` | 交给 fresh background agent 立刻接手 |
| 消息没看懂、wait what | `wait-what` | 用 GLOSSARY.md 词汇 + 用户上下文重新解释 |
| teach、教学、分步教概念 | `teach` | 多会话教学 |

#### Writing & Content

| When user says… | Skill | Description |
|-----------------|-------|-------------|
| 写给 agent 读的文档（skills、AGENTS.md 等） | `writing-for-agents` | agent-facing 文档写法 |
| 写文章、写作（输出型，已有素材） | `writing-beats` | 素材 → beats 叙事 → 成文 |
| 写文章、写作（探索型，攒素材） | `writing-fragments` | 挖原始素材，不考虑结构 |
| 写文章、塑形（素材够了开始写） | `writing-shape` | 一段一段塑造成文章 |
| 拷问工作流 spec | `loop-me` | grill-me 的工作流版本 |

#### Specialized

| When user says… | Skill | Description |
|-----------------|-------|-------------|
| 迁移 TS 测试的 `as` 断言到 shoehorn | `migrate-to-shoehorn` | TypeScript 类型安全迁移 |
| 创建练习目录结构（课程/教程项目） | `scaffold-exercises` | sections/problems/solutions/explainers |
| 给 TS monorepo 注入 dependency-cruiser | `setup-ts-deep-modules` | 强制每个包成 deep module |
| 一个人答不了的决策做成问卷 | `to-questionnaire` | Markdown 问卷，异步或一起开会填 |

### 用法

1. **每次会话开始**：先扫一遍上面的路由表，标记哪些 skill 和当前任务相关
2. **每次做决定前**：检查有没有对应 skill 可以先跑（尤其是 grilling 系列）
3. **找不到合适的**：问 `ask-matt` —— 它会基于 repo 里的 skills 推荐

### 安装与更新

```bash
npx skills@latest add mattpocock/skills --all
npx skills@latest update
```
