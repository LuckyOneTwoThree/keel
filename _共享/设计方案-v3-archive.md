<aside>
🐾

**一句话定位**：v2 是"文件系统优先 + AI 旁路建议"，v3 升级为"**agent 可托管 + 人在环确认**"。补三层强制机制地基（frontmatter + git + check.py）+ 一条短时记忆层（agent 会话状态）+ 一套编排协议（SOP / 确认门 / 草稿区 / 派生视图）。本方案只定**结构与协议**，不含具体项目内容。

</aside>

## 〇、变更摘要（v2 → v3）

| 维度 | v2 | v3 |
| --- | --- | --- |
| 协作模式 | PM 主导 + AI 旁路建议 | agent 自治编排 + PM 人在环确认 |
| 协议载体 | AGENTS.md（人读·静态路由） | AGENTS.md（人读） + `.agent/contract.yaml`（机读 SOP/权限/触发） |
| 字段格式 | Markdown prose | YAML frontmatter（机读） + prose（人读） |
| 强制机制 | 自觉遵守 | check.py pre-commit + agent 写前自检 |
| 并发/审计/回滚 | 无 | git = 唯一并发层 + 审计层 + 回滚层 |
| 短时记忆 | 无（仅项目长时记忆） | `记忆/agent会话.md` 跨会话延续 |
| 上下文预算 | 无（默认全读） | `.meta.md` 缓存 + 分级读取策略 |
| 草稿区 | 无（PM 确认才落但无处起草） | `.draft/` 暂存，PM 审完移正式位 |
| 行动项归宿 | 无（散在 DEC-/COM- prose 里） | 真相源字段结构化 + 派生视图聚合 |
| 编号分配 | "AI 不编造" | AI 提议 + PM 拍板 + git 锁 + 写前二次校验 |
| 元规则 | 无 | "摩擦 < 维护" + 两周复审砍肥肉 |

**三条地基约束（v3 仍不可动）**：① 单一真相源 ② 记忆层只追加不回改，推翻只改状态字段 ③ AI 最小权限四条。

---

## 一、设计目标（继承 v2 + 新增）

继承：项目解耦、知识可沉淀、全链路可追溯、规则不漂移、可扩展可检索、守住灵魂。

v3 新增三条：

1. **agent 可托管**：桌面 agent 能按 SOP 自治推进多步工作流，不必 PM 逐步指挥。
2. **跨会话延续**：会话中断/重启后，agent 能从短时记忆层恢复"讨论到哪、卡在哪、下一步"。
3. **反膨胀可收敛**：新增设施必须经"摩擦 < 维护"元规则校验，可被周期性砍掉。

---

## 二、三层强制机制地基（v3 核心新增）

> 没有这三层，所有 SOP / 触发规则 / 派生视图都是纸面能力。

### 2.1 YAML frontmatter schema

**为什么是 P1**：触发规则、`.meta` 缓存、`gen-index`、阈值告警、check.py 校验——全部依赖字段机器可读。prose 字段下这些 agent 能力都是空话。

**条目级 frontmatter（写入 `记忆/` 与 `项目管理/` 各登记册）**：

```yaml
---
id: REQ-0007
type: req              # req / prg / dec / com / kb / rsk / dep / todo / gkb
title: 用户登录双因子认证
date: 2026-07-25
status: 待评审          # 见 §2.1.2 状态枚举
scope: 在范围           # 仅 req 用：在范围 / 明确不做
related: [DEC-0012, RSK-0003, DEP-0002]
review_due: 2026-08-25  # 仅 dec / rsk 用：复审到期日
sensitive: false        # 见 §十九
---
```

**文件级 frontmatter（写入 `文档库/` 各文件头）**：

```yaml
---
doc_id: REQ-0007-PRD
req: REQ-0007
type: prd               # prd / 方案 / 验收 / 会议 / 报告
status: 草稿 / 评审中 / 已定稿
date: 2026-07-25
author: PM / agent起草-PM确认
---
```

**项目级 frontmatter（`.meta.md`，见 §十三）**。

#### 2.1.2 状态枚举（check.py 强制）

| 类型 | 允许状态 |
| --- | --- |
| REQ | 待评审 / 开发中 / 已验收 / 已砍 |
| PRG | 进行中 / 已完成 / 已阻塞 |
| DEC | 评估中 / 生效 / 已推翻→DEC-XXXX / 待复审 |
| COM | 已对齐 / 待跟进 / 失效 |
| KB | 本地 / 已晋升→GKB-XXXX / 过时 |
| RSK | 开放 / 已缓解 / 已关闭 |
| DEP | 等待中 / 已就绪 / 已逾期 |
| TODO | 待办 / 进行中 / 已完成 / 已作废→(指向) |
| GKB | 生效 / 已归档 |

> **通用例外状态**：所有类型均可追加 `已作废(PM拒绝)` 或 `已作废(误)→(指向)`，用于回滚（§十七）与勘误（§二十）。这是只追加原则下的标准纠错状态，不计入"活跃条目"过滤。

### 2.2 git 版本层

**为什么是 P1**：append-only 日志天然抗并发（不同条目 git 干净 merge），同时一次性解决审计、回滚、并发根因。

**commit 规范**：

```
[<编号>] <动作短语>

例：
[REQ-0007] 新增需求
[DEC-0012] 状态:生效→已推翻→DEC-0013
[RSK-0003] 等级 升级为中→高
[现状.md] 派生刷新
```

**写入原子性**：**一条条目 = 一个 commit**。多步工作流可拆多 commit，但单条目状态变更不得跨 commit（防半成品状态）。

**回滚协议（见 §十七）**：PM 拒绝 agent 写入 → 改条目状态为 `已作废(PM拒绝)` + 新 commit（保只追加 + 保审计层在 markdown）。草稿区例外可直接删。

**派生文件冲突**：`现状.md` / `.meta.md` / `INDEX.md` / `行动项.md` 冲突时**重跑派生即可**，不必上锁、不必 merge。

**基线文件冲突**：章程 / 需求登记册范围 / 路线图里程碑——本就走 L3 确认门串行化，天然不冲突。

### 2.3 check.py 校验层

**为什么是 P1**：把"约定"变"强制"。没有它，所有编号协议、状态枚举、frontmatter schema 都是自觉。

**最小校验集**（双跑：pre-commit hook + agent 写入前自检）：

| 校验项 | 规则 | 失败动作 |
| --- | --- | --- |
| 编号唯一 | 同前缀编号全局唯一 | 阻断 + 提示冲突文件 |
| 编号递增 | 新编号 = 该类现有最大 + 1 | 阻断 + 提示正确编号 |
| 悬空引用 | `related:` 中每项必须存在 | 阻断 + 列出悬空项 |
| 状态枚举 | 必须命中 §2.1.2 枚举 | 阻断 |
| frontmatter schema | 必填字段齐全、类型正确 | 阻断 |
| 日期格式 | ISO `YYYY-MM-DD` | 阻断 |
| 排序 | 同文件内倒序（最新在顶） | 警告 |
| 双写检测 | 同一信息不在两处真相源 | 警告（启发式） |

**落地形态**：`scripts/check.py` + `.git/hooks/pre-commit` 调用。agent 写入前先跑一次自检（不必走 git），失败则不落盘、回报 PM。

---

## 三、顶层架构（继承 v2 三段式 + v3 新增设施）

```
pm-playbook/
├── README.md                       导航 + 心智模型（瘦身）
├── 工作区现状.md                    【v3 新增·P2】派生·非真相源·跨项目聚合
├── _共享/
│   ├── PM工作宪章.md                （不变）
│   ├── AGENTS.md                   【v3 重写·P1】人读·协作契约 + SOP 概要
│   ├── 写入协议.md                  【v3 补·P2】编号分配流程 + 勘误模式 + 冲突处理
│   ├── 设计方案.md                  v2 存档（不动）
│   ├── 设计方案-v3.md               本文件
│   ├── 知识库/全局知识库.md          （不变，补 frontmatter）
│   └── .agent/                     【v3 新增·P1】机读契约层
│       ├── contract.yaml           机读 SOP / 权限 / 触发规则
│       └── schema_version.yaml     schema 版本号（见 §十八）
├── _模板/
│   ├── 现状.md                      【v3 补·P2】更新协议说明
│   ├── .meta.md                    【v3 新增·P2】项目元数据机读模板
│   ├── INDEX.md                    （不变）
│   ├── 记忆/
│   │   ├── 进度日志.md  决策记录.md  沟通记录.md  知识库.md   （补 frontmatter）
│   │   ├── 行动项.md                【v3 新增·P1】派生·非真相源·可重建
│   │   └── agent会话.md             【v3 新增·P1】append-only·跨会话延续
│   ├── 项目管理/                    （补 frontmatter）
│   ├── 文档库/06-会议/_模板.md       【v3 新增·P3】
│   └── ...                          （注：`.draft/` 为运行时临时区，项目实例中按需创建，不预置模板）
├── 项目/PROJ-X/
│   ├── .meta.md                    填实
│   ├── .draft/                     草稿区
│   └── ...
├── 已结项/                          （不变）
├── scripts/
│   ├── check.py                    【v3 新增·P1】校验层
│   └── gen-index.sh                【v3 新增·P3】INDEX 派生脚本
└── .gitignore                      忽略 `.draft/`（可选）
```

---

## 四、机读契约与人读文档分离（v3 新增·P1）

> AGENTS.md 不再膨胀成"人机两用巨石"。

### 4.1 AGENTS.md（人读）

保留协作契约 + 真相源路由表 + 域边界速记 + SOP **概要**（一句话级，PM 一眼能读懂）。细节字段、触发阈值、权限矩阵下沉到 contract.yaml。

### 4.2 `.agent/contract.yaml`（机读）

桌面 agent（Cursor / Claude Desktop / Codex 等）以此 yaml 为**单一真相源**，各 IDE 适配文件（`.cursorrules` / `CLAUDE.md` 等）由它派生，**不手写**。

草案见 §五。

---

## 五、`.agent/contract.yaml` 草案

```yaml
schema_version: 3
workspace:
  root: pm-playbook/
  shared: _共享/
  template: _模板/
  projects: 项目/
  archived: 已结项/

# 真相源路由（agent 读取的权威表）
routes:
  需求主线: { file: 项目管理/需求登记册.md, prefix: REQ- }
  里程碑:   { file: 项目管理/路线图.md }
  风险:     { file: 项目管理/风险登记册.md, prefix: RSK- }
  依赖:     { file: 项目管理/依赖登记册.md, prefix: DEP- }
  干系人:   { file: 项目管理/干系人矩阵.md }
  成功指标: { file: 项目管理/项目章程.md }
  决策:     { file: 记忆/决策记录.md, prefix: DEC- }
  沟通:     { file: 记忆/沟通记录.md, prefix: COM- }
  进度:     { file: 记忆/进度日志.md, prefix: PRG- }
  本地知识: { file: 记忆/知识库.md, prefix: KB- }
  通用知识: { file: _共享/知识库/全局知识库.md, prefix: GKB- }
  会议纪要: { file: 文档库/06-会议, naming: YYYY-MM-DD-* }
  周报报告: { file: 文档库/07-报告, naming: YYYY-MM-DD-* }
  # v3 新增
  行动项:   { file: 记忆/行动项.md, derived: true }       # 派生·非真相源
  agent会话: { file: 记忆/agent会话.md, append_only: true }

# 确认门四级（见 §七）
gates:
  L0_read:   { ops: [read], auto: true }
  L1_draft:  { ops: [write_draft, refresh_derived], auto: true, notify: true }
  L2_write:  { ops: [write_record], require: pm_confirm, fields: [id, content] }
  L3_baseline: { ops: [write_charter, write_scope, write_milestone], require: pm_explicit_auth + DEC- }

# SOP 工作流（见 §六）
workflows:
  new_req:
    steps:
      - grep 需求登记册取最大 REQ 号
      - 输出草稿含提议编号 → .draft/
      - PM 确认编号 + 内容
      - 写登记册一行（frontmatter） + 起 PRD 草稿 → 01-需求/
      - git commit [REQ-XXXX] 新增需求
      - check.py 自检
  weekly_report:
    steps:
      - 扫本周 PRG-
      - 关联 DEC- / RSK- / DEP-
      - 出稿 → .draft/
      - PM 确认 → 落 07-报告/YYYY-MM-DD-周报.md
      - git commit [报告] 周报
  refresh_现状:
    steps:
      - 读路线图 → §2
      - 扫未关闭 RSK-/未就绪 DEP-/待决策 DEC- → §3
      - 扫 DEC- 复审字段 → §4
      - 覆盖式写 现状.md（§1 PM 手填保留）
      - git commit [现状.md] 派生刷新

# 触发规则（见 §十六）
triggers:
  - condition: "RSK.等级 == P0 and RSK.状态 == 开放"
    action: 立即提醒 PM
    silent_until: null   # PM 可设静默: 直到 HH:MM
    escalate_after: 24h   # 静默超 24h 升级打扰
  - condition: "DEP.期望交付 - today <= 3 and DEP.状态 == 等待中"
    action: 提醒 PM
  - condition: "DEC.复审 <= today"
    action: 提醒 PM
  - condition: "any RSK.等级 == P0 and 静默 > 24h"
    action: 强制提醒（无视静默）

# 访问白名单（按 agent 角色，见 §十五）
roles:
  prd_agent:
    read: [REQ, DEC, COM, 项目章程, 干系人矩阵]
    write: [.draft/, 文档库/01-需求/]   # 草稿 + 确认后落 PRD
  ops_agent:
    read: [全部]
    write: [.draft/, 现状.md, .meta.md, 记忆/行动项.md]   # 仅派生 + 草稿
  checker_agent:
    read: [全部]
    write: []   # 只跑 check.py，不写真相源
  main_agent:                            # PM 主入口 agent，协调其他角色
    read: [全部]
    write: [全部]   # 须经确认门 L0-L3

# 上下文预算（见 §十二）
context_budget:
  default_strategy: meta_first   # 先读 .meta 缓存
  stale_threshold_sec: 3600       # 缓存超 1h 视为 stale，回源
  log_tail: 50                    # 记忆类文件只读最近 50 条
  log_window_days: 30             # 或最近 30 天，取小
```

---

## 六、工作流 SOP（agent 可执行）

写入 AGENTS.md 概要 + contract.yaml 详情。最小集四条：

| SOP | 触发 | 关键步骤 | 确认门 |
| --- | --- | --- | --- |
| 新建需求 | PM 说"加需求 X" | 扫最大号 → 起草（含提议编号）→ PM 确认 → 写登记册 + 起 PRD 草稿 → commit → 自检 | L2 |
| 周报生成 | PM 说"出周报" / 周五触发 | 扫本周 PRG-/DEC-/RSK-/DEP- → 出稿 `.draft/` → PM 确认 → 落 07-报告 → commit | L2 |
| 现状刷新 | 每次 agent 会话开始 / RSK/DEP/DEC 变更后 | 派生 §2/§3/§4（§1 PM 手填保留）→ 覆盖式写 → commit | L1 |
| 需求验收 | PM 说"REQ-0007 验收了" | 比对 05-验收/REQ-0007.md 与验收标准 → 更新登记册状态字段 → commit | L2 |

幂等键：草稿阶段用 `.draft/draft-{uuid}.md`，PM 确认编号时 rename 为 `REQ-0007-PRD.md`。**编号不预占**——与"PM 拍板编号"原则一致。

---

## 七、确认门四级（L0-L3）

| 级别 | 操作 | agent 行为 |
| --- | --- | --- |
| L0 只读 | 读任何真相源文件（敏感字段除外，见 §十九） | 直接做，无需确认 |
| L1 起草 | `.draft/` 写草稿、刷新派生文件（现状/.meta/INDEX/行动项） | 直接做，事后告知 PM |
| L2 写真相源 | 写 REQ-/DEC-/RSK-/DEP-/PRG-/COM-/KB-/GKB- 条目 | **PM 确认编号 + 内容后落盘** |
| L3 改基线 | 改章程 / 需求登记册范围 / 路线图里程碑 | **PM 显式授权 + 走 DEC-** |

宪章第 1 条"不擅自落盘"在此细化为可执行规则。

---

## 八、编号分配协议

```
PM: "加一条需求，关于 X"
agent:
  1. grep 需求登记册取当前最大 REQ 号 → 候选 = max+1
  2. 输出草稿（含提议编号 REQ-XXXX）→ .draft/draft-{uuid}.md
  3. PM 确认编号 + 内容
  4. 写入前二次校验最大值（防并发抢号）→ 写登记册 + 起 PRD 草稿
  5. git commit [REQ-XXXX] 新增需求
  6. check.py 自检
```

"AI 不编造编号"细化为：**AI 可提议、PM 拍板、写入时二次校验最大值、commit 即锁**。

并发场景：单实例桌面 agent 极少真并发；若发生，git commit 作锁，冲突 agent 重读最大值重试。**不采用 hash 编号**——破坏"按编号看时序"语义，PM 引用成本暴涨。

---

## 九、草稿区机制（`.draft/`）

**为什么是 P1**：宪章第 1 条"所有写入先出稿"，但 v2 没有"稿"的物理位置。agent 起草 PRD/周报/方案时，要么直接写正式文件（违规），要么塞对话里（PM 看不清、易丢）。

**规则**：

- 位置：项目根 `.draft/`（可选 gitignore，或纳入 git 作审计）
- 命名：`draft-{uuid}.md` 或 `draft-{意图}-{uuid}.md`（如 `draft-req-{uuid}.md`）
- 生命周期：起草 → PM 审 → 确认后 rename/移动到正式位 → 清空草稿
- 拒绝：PM 拒绝 → `git rm` 或直接删（草稿区不享受只追加保护）
- 幂等：草稿文件存在 = 工作流断点；agent 重启后扫 `.draft/` 可续传

---

## 十、行动项派生视图（C+ 方案）

> 真相源仍是 DEC-影响 / COM-结论；行动项.md 是派生聚合视图，**不是新真相源**。避免与"只追加"哲学冲突。

### 10.1 真相源字段结构化

DEC-/COM-/PRG- 条目中"行动项"字段强制结构化：

```markdown
- 行动项:
  - [ ] 与法务对齐数据合规要求 #REQ-0007 @张三 due:2026-08-10
  - [ ] 补埋点清单 #REQ-0007 @李四 due:2026-08-05
```

勾选 `[ ]→[x]` 属"状态字段变更"，符合只追加原则（不删原文、只改状态）。

### 10.2 派生视图 `记忆/行动项.md`

```markdown
---
derived: true
rebuilt_at: 2026-07-25T14:30
source: [记忆/决策记录.md, 记忆/沟通记录.md, 记忆/进度日志.md]
note: 派生·非真相源·可重建
---
# 行动项（派生）
## 待办（未勾选）
- [ ] 与法务对齐数据合规 #REQ-0007 @张三 due:2026-08-10  ← DEC-0012
- [ ] 补埋点清单 #REQ-0007 @李四 due:2026-08-05          ← COM-0008

## 已完成（已勾选·近 30 天）
- [x] ...
```

### 10.3 "我今天要做什么"

agent 现算视图：过滤 `未勾选 + due ≤ today`，不落盘为新文件（行动项.md 已是缓存）。

### 10.4 例外声明

在 AGENTS.md 显式写死：**"行动项.md 是 append-only 体系的唯一派生覆盖区，不享受只追加保护，可覆盖式重生成。"** 把例外写明，而非让它悄悄破坏原则。

---

## 十一、agent 会话状态（短时记忆层）

> v2 有"项目长时记忆"（PRG/DEC/COM），但**没有"协作短时记忆"**。PM 跟 agent 聊到一半会话断了，明天重开 agent 一脸懵。这是 PM-agent 协作能跨会话延续的命脉。

**位置**：`记忆/agent会话.md`（append-only，享受只追加保护）

**模板**：

```markdown
### SESSION-2026-07-25-1430 — 2026-07-25
- 项目: PROJ-灯塔
- 目标: 起草 REQ-0007 PRD
- 已做: 读 REQ-0007 登记册条目 + DEC-0012；起草 PRD 到 .draft/draft-abc.md
- 卡在: PRD §4 验收标准未定，等 PM 给验收清单
- 下一步: PM 给验收清单 → 补 PRD → 落 01-需求/REQ-0007-PRD.md
- 相关: REQ-0007, DEC-0012
```

**规则**：

- 每次会话**结束前**写一行（agent 主动写，PM 不必手填）
- 每次会话**开始时**先读最近 3 条 SESSION-，恢复上下文
- 仅记"工作流状态"，不记"项目事"（项目事归 PRG/DEC/COM）
- 不作真相源，但享受只追加（防 agent 误删历史会话）

---

## 十二、上下文预算与读取策略

> 记忆系统无限追加会爆 agent 上下文窗口；每次会话扫全项目 RSK/DEP/DEC 成本高。

**三级读取策略**：

| 层级 | 何时用 | 读什么 |
| --- | --- | --- |
| L1 缓存 | 默认 | `.meta.md`（见 §十三），5 秒读懂项目 |
| L2 摘要 | 缓存 stale 或需细节 | grep 各文件 frontmatter（id/title/status/date） |
| L3 全文 | 必须读条目正文 | Read 单条目（按 grep 定位的行号） |

**stale 判定**：`.meta.updated` 距今 > 1h，或本会话内有 L2 写入 → 视为 stale，回源。

**记忆类文件读取**：默认只读最近 50 条 或 最近 30 天（取小），不全读。需要更早的 → grep + 按需 Read。

---

## 十三、`.meta.md` 机读缓存

> 与 `现状.md` 分工：`.meta` = 机读缓存（agent 写、可重建）；`现状.md` = 人读驾驶舱（PM 看，§1 手填）。

**模板**（项目根）：

```yaml
---
proj_id: PROJ-灯塔
schema_version: 3
status: 活跃          # 活跃 / 暂停 / 收尾 / 已归档
owner: 张三
current_milestone: M2
last_prg: PRG-0007
last_dec: DEC-0012
last_com: COM-0008
open_rsk: [RSK-0003, RSK-0005]      # 状态=开放
waiting_dep: [DEP-0002]              # 状态=等待中
pending_dec: [DEC-0013]              # 状态=评估中
updated: 2026-07-25T14:30
derived: true
note: 派生·非真相源·可从真相源重建
---
```

**规则**：

- agent 每次 L2 写入后刷新 `.meta`
- 字段必须可从真相源重建（否则就是第二个事实源）
- 冲突时重跑派生，不上锁、不必 merge

---

## 十四、`现状.md` 与 `工作区现状.md`

### 14.1 `现状.md`（项目级·人读）

继承 v2，补更新协议：

| 字段 | 更新方 | 触发时机 |
| --- | --- | --- |
| §1 本周焦点 | PM 手填 | 周一或里程碑切换 |
| §2 当前里程碑 | agent 派生 | 路线图变更时 |
| §3 阻塞与待办 | agent 派生 | RSK/DEP/DEC 变更后 |
| §4 到期复审 | agent 派生 | 每次会话开始扫一遍 |

派生失败兜底：数据缺失时显示 `(待补: 引用 X)`，不留空字段。

### 14.2 `工作区现状.md`（工作区级·派生·P2）

跨项目聚合，agent 现算或定期刷新：

```markdown
# 工作区现状（派生·非真相源·可重建）
## 1. 本周焦点（聚合各项目 现状.md §1）
## 2. 全局高风险（聚合各项目 RSK- 等级=P0/P1 且 开放）
## 3. 全局阻塞依赖（聚合各项目 DEP- 等待中/已逾期）
## 4. 到期复审（聚合各项目 DEC- 复审字段）
```

---

## 十五、多 agent 角色边界

> 实际场景会有 PRD 起草 agent、跑校验 agent、生成周报 agent 并存。宪章"AI 角色边界"是单 agent 假设。

**最小角色集**（contract.yaml `roles` 段）：

| 角色 | 读 | 写 | 典型任务 |
| --- | --- | --- | --- |
| prd_agent | REQ/DEC/COM/章程/干系人 | `.draft/` + `01-需求/` | 起 PRD |
| ops_agent | 全部 | `.draft/` + 派生文件（现状/.meta/行动项） | 现状刷新、周报、行项聚合 |
| checker_agent | 全部 | 无 | 跑 check.py |
| main_agent | 全部 | 全部（经确认门 L0-L3） | PM 主入口，协调其他角色 |

跨角色写入冲突：以 git commit 为锁，后写者重读重试。

---

## 十六、触发规则与静默期

| 触发条件 | 动作 | 静默期 |
| --- | --- | --- |
| RSK 等级=P0 且 开放 | 立即提醒 | PM 可设 `静默: 直到 HH:MM`；超 24h 强制升级打扰 |
| DEP 期望交付 T-3 天 且 等待中 | 提醒 | 无静默 |
| DEC 复审到期 | 提醒 | 无静默 |
| 静默超 24h 且 仍有 P0 | 强制提醒（无视静默） | — |

PM 休假/开会场景：设静默期，P0 阻塞超 24h 才升级打扰，避免"立即提醒"在 PM 不便时变成噪音。

---

## 十七、agent 自我回滚协议

> L2 写入被 PM 拒绝后如何处理？git revert 会让条目从文件消失（违审计友好）；手工删行违只追加。正确做法：**保留条目 + 改状态为作废 + 新 commit**。

**触发**：PM 在确认门拒绝 agent 的 L2/L3 写入。

**动作**：

```
agent:
  1. 不删原条目，将其 status 改为 "已作废(PM拒绝)"
  2. （可选）追加一行 "拒绝原因: ..."
  3. git commit [编号] 状态:作废(PM拒绝)
```

**为什么不 git revert**：revert 会让条目从 markdown 文件消失，PM 翻文件看不到"曾写过+被拒"的痕迹，审计要靠 git log 才能还原。改状态则 markdown 自身就是审计层。

**禁止**：手工删行、`git reset --hard`、`git push --force`、`git revert`（除非 PM 显式要求且接受审计层迁移到 git log）。

**草稿区例外**：`.draft/` 下的草稿被拒绝 → 直接删（草稿区不享受只追加保护，见 §九）。

---

## 十八、schema 版本号

> 模板/协议会演进 v2→v3。agent 拿到老项目不知道是哪版结构。

**位置**：`.agent/schema_version.yaml` + 每个文件 frontmatter `schema_version` 字段。

```yaml
# .agent/schema_version.yaml
schema_version: 3
changelog:
  - version: 3
    date: 2026-07-25
    changes: [frontmatter, git层, check.py, 草稿区, 派生行动项, agent会话]
  - version: 2
    date: 2026-07-20
    changes: [三段式, REQ-主线, 双层知识, DEP-]
```

check.py 据此判断项目 schema 版本，老项目走老规则、新项目走新规则。

---

## 十九、字段级敏感数据

> 项目里有薪资/合同金额，PM 不一定想让 agent 全读。

**机制**：frontmatter 加 `sensitive: true`，条目级或字段级。

```yaml
---
id: COM-0012
sensitive: true   # 整条敏感
---
```

```markdown
- 合同金额: [[sensitive]] 120万   # 字段级敏感，agent 默认不读
```

**规则**：L0 只读默认跳过 `sensitive: true` 条目；读需 PM 会话内显式授权。这是 L0 的例外。

---

## 二十、勘误模式

> append-only 下 agent 写错了不能删。

**模式**：新增条目，状态标"作废(误)→指向正确条目"，而非删除。

```markdown
### DEC-0013 — 2026-07-25
- 状态: 已作废(误) → 正确见 DEC-0014
- 原因: 数据引用错误
- 正文: (保留原内容，不删)
```

这是只追加原则的标准应用，不是新机制。在 `写入协议.md` 里"勘误模式"一节显式写出即可。

---

## 二十一、反膨胀元规则

> 警惕重新长回刚砍掉的肥肉。立"摩擦 < 维护"元规则 + 两周复审。

**元规则**：

> 新增设施必须证明它减少的 agent 摩擦 > 它引入的维护负担。

**两周复审**（PM 主导）：

> 新设施上线 2 周后，PM 回答三问：① 这周它被用过吗？② 没有它你卡了几次？③ 维护它花了几分钟？三个皆负 → 砍。

**已砍项（v3 不做）**：

| 砍掉项 | 理由 |
| --- | --- |
| 来源标记每条 | git blame 已能溯源，写入摩擦大、收益边际 |
| 时间戳全局到分钟 | 仅高频写入的日志需要，全局铺开是负担 |
| 冲突"最后写入者胜"全局规则 | append-only 日志天然抗并发；派生文件可重建；基线走 L3 串行 |
| 独立 ASM- 假设流（v2 已砍） | 与风险/决策重叠，编号膨胀 |
| 独立 成功指标.md（v2 已砍） | 与章程职责重叠 |
| 物理子目录 基线·控制面（v2 已砍） | 增加嵌套，违"简单优先" |

**保留观察项**（2 周后复审）：

| 项 | 观察指标 |
| --- | --- |
| `工作区现状.md` | 跨项目场景频率 |
| `.meta.md` | 缓存命中率 |
| `agent会话.md` | 跨会话续传频率 |
| 触发规则静默期 | PM 实际使用率 |

---

## 二十二、保留 / 改动 / 新增对照（v2 → v3）

| 处理 | 内容 |
| --- | --- |
| ✅ 保留 | 三段式、REQ- 主线、单一真相源、只追加、AI 最小权限、宪章角色边界、知识双层+晋升、基线/控制面标注、需求三件套边界、INDEX 按需生成 |
| 🔧 改动 | AGENTS.md 拆为人读 + 机读 contract.yaml；条目格式 prose → frontmatter+prose；编号分配加 git 锁 + 二次校验；现状.md 补更新协议；.meta vs 现状分工；TODO- 改派生视图（C+）；冲突处理换 git；勘误模式显式化 |
| ➕ 新增 | frontmatter schema、git 版本层+commit 规范、check.py 校验、`.agent/contract.yaml`、`.draft/` 草稿区、行动项派生视图、agent会话短时记忆、`.meta.md` 机读缓存、工作区现状.md、多 agent 角色边界、触发规则静默期、agent 自我回滚协议、schema 版本号、字段级敏感标记、6-会议模板、gen-index 脚本 |
| ❌ 砍 | 来源标记每条、时间戳全局到分钟、冲突"最后写入者胜"全局规则 |

---

## 二十三、迁移步骤（v2 → v3）

按依赖顺序，先地基后上层：

1. **地基三件套**
   - 全库条目补 frontmatter（按 §2.1 schema）
   - `scripts/check.py` + `.git/hooks/pre-commit` 接入
   - 立 commit 规范（§2.2），全库首次 commit 标 `[v3] schema 升级`
2. **机读契约层**
   - 建 `.agent/contract.yaml`（§五草案）
   - AGENTS.md 瘦身为概要 + 指 contract.yaml
   - 建 `.agent/schema_version.yaml`
3. **草稿区 + 派生层**
   - 各项目建 `.draft/`、`记忆/草稿/`
   - 建 `记忆/行动项.md`（派生模板）
   - 建 `记忆/agent会话.md`
   - 建 `.meta.md` 模板
4. **工作区层**
   - 根目录建 `工作区现状.md`
   - 建 `scripts/gen-index.sh`
5. **协议补齐**
   - `写入协议.md` 补编号分配流程 + 勘误模式 + 冲突处理
   - `PM工作宪章.md` 补多 agent 角色边界（或下沉 contract.yaml）
   - `_模板/文档库/06-会议/_模板.md`
6. **样例项目**
   - 建 `项目/PROJ-示例/`，填假数据，作 agent few-shot 参考 + check.py 回归夹具
7. **两周复审**
   - 上线 2 周后 PM 回答三问，砍观察项中三项皆负者

---

## 二十四、取舍说明（反冗余论证）

经多视角（agent 可托管性 / 单一真相源 / 简单优先 / 反膨胀元规则）复审，以下建议被**刻意否决或降级**：

| 否决项 | 理由 | 替代方案 |
| --- | --- | --- |
| `TODO-` 作新真相源 | 与只追加哲学冲突，行动项天天变状态 | C+ 方案：真相源字段结构化 + 派生视图 |
| hash 编号 `REQ-{yymmdd}-{hash}` | 破坏"按编号看时序"语义，PM 引用成本暴涨 | 保留递增 + git commit 作锁 |
| 来源标记每条 | git blame 已能溯源 | 砍 |
| 时间戳全局到分钟 | 仅高频日志需要 | 仅 `记忆/` 类文件加 `时:分` |
| 冲突"最后写入者胜"全局 | 对 append-only 有害 | git + 派生文件可重建 + 基线走 L3 |
| 独立 成功指标.md（继承 v2） | 与章程重叠 | 折入章程 |
| 独立 范围基线.md（继承 v2） | 与需求登记重叠 | 并入登记册 |
| 物理 基线·控制面 子目录（继承 v2） | 增加嵌套 | 逻辑标注 |
| 文档库物理拆 阶段/周期（继承 v2） | 与 REQ 命名重复 | 文件命名约定 |
| 新增 ASM- 假设流（继承 v2） | 与风险/决策重叠 | 折入决策"假设前提"字段 |
| `最后写入者胜` 全局冲突规则 | 对 append-only 有害 | git + 派生可重建 |

---

## 二十五、TL;DR

- **v2 → v3 的核心升级**：从"文件系统优先 + AI 旁路建议"到"agent 可托管 + 人在环确认"。
- **三层强制机制地基**（必补）：frontmatter schema + git 版本层 + check.py 校验。没有这三层，所有 SOP / 触发规则 / 派生视图都是纸面能力。
- **一条短时记忆层**（必补）：`记忆/agent会话.md`。没有它，PM-agent 协作不能跨会话延续。
- **一套编排协议**（必补）：contract.yaml 机读契约 + 工作流 SOP + 确认门四级 + `.draft/` 草稿区 + 行动项派生视图。
- **一条反膨胀元规则**（必立）：摩擦 < 维护 + 两周复审砍肥肉。
- **不动**：三段式、REQ- 主线、单一真相源、只追加、AI 最小权限——这套底子对 agent 是友好的，v3 只在其上加"强制机制 + 编排层"。
