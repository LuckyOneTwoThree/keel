<div align="center">

# ⛵ keel

**给「人 + AI 协作的项目管理」装一根龙骨。**

不是文档模板集，而是一套**可被机器强制执行**的项目管理操作系统：<br>
纯 Markdown 当数据库 · Git 当审计日志 · Python 脚本当宪法执行者

[![CI](https://github.com/LuckyOneTwoThree/keel/actions/workflows/ci.yml/badge.svg)](https://github.com/LuckyOneTwoThree/keel/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.6%2B-blue.svg)]()
[![Dependencies](https://img.shields.io/badge/dependencies-0-green.svg)]()
[![Storage](https://img.shields.io/badge/storage-markdown%20%2B%20git-orange.svg)]()
[![Version](https://img.shields.io/badge/version-v3.0-blueviolet.svg)]()

</div>

---

> **新会话第一条命令**：`python scripts/pm.py brief -p 项目/PROJ-Node-PoC`
>
> **AI 协作者入口**：[`AGENTS.md`](AGENTS.md) → [`_共享/PM工作宪章.md`](_共享/PM工作宪章.md) → [`_共享/写入协议.md`](_共享/写入协议.md)

## 特性

|   |  |  |
| --- | --- | --- |
| 🧠 | **上下文不蒸发** | 一切结构化为带 frontmatter 的条目，`pm brief` 一条命令还原全部上下文 |
| 📌 | **决策不失忆** | `DEC-0001` 是永久主键；只追加不删改，勘误必须留痕 |
| 🛡️ | **AI 不越权** | 范围/优先级/资源字段进入 `confirmed_by` 门控，未确认条目标 `draft: true` |
| ⏳ | **草稿会老化** | 悬空 7 天警告、14 天硬阻断提交 —— 未决事项主动来找你，而非沉入历史 |
| 📦 | **零外部依赖** | 纯 Python 标准库手写 frontmatter 解析，AI 沙箱 / 裸机 / 临时容器直接跑 |
| 🔬 | **模板即夹具** | `_模板/` 自身进 CI 校验，`PROJ-Node-PoC` 永远是 100% 合规的活样例 |

---

## 快速上手（60 秒）

```bash
git clone https://github.com/LuckyOneTwoThree/keel
cd keel

# 1. 装钩子(或跑 python scripts/pm.py doctor --fix 自动安装)
cp scripts/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

# 2. 先看懂参考项目
python scripts/pm.py brief -p 项目/PROJ-Node-PoC

# 3. 创建自己的项目
python scripts/pm.py init PROJ-你的项目

# 4. 记第一条东西
python scripts/pm.py new prg "完成环境搭建" -p 项目/PROJ-你的项目

# 5. 校验并提交
python scripts/pm.py commit "feat: 初始化项目"
```

---

## 1. 为什么需要 keel

当 PM 开始把 AI 当协作者，而不只是当写作工具时，三个问题会立刻暴露：

| 痛点        | 具体表现                         | 传统方案为什么失效                             |
| --------- | ---------------------------- | ------------------------------------- |
| **上下文蒸发** | 每次开新会话，AI 都要重新问一遍「这个项目是干什么的」 | 把长文档粘进 prompt，成本高且容易超窗；关键信息埋在散文里，检索不到 |
| **决策失忆**  | 三周前定过的技术选型，这周又被重新讨论一遍        | 会议纪要里有，但没人知道在哪一篇的第几段                  |
| **AI 越权** | AI 自作主张改了需求范围、替 PM 拍了决策      | 靠 prompt 里写「请不要…」，没有任何强制力             |

> **keel 的答案**：不要求 AI 自律，而是让**违规操作在技术上无法提交**。
>
> - **上下文蒸发** → 结构化沉淀为带 frontmatter 的条目，`pm brief` 一条命令还原全部上下文
> - **决策失忆** → `DEC-0001` 是永久可引用的主键；决策只能追加、不能删改，勘误必须留痕
> - **AI 越权** → 涉及范围/优先级/资源的字段进入 `confirmed_by` 门控，未经 PM 确认的条目 `draft: true`，超期未定稿会**硬阻断**提交

**适合**：一个人（或小团队）+ 一个或多个 AI agent 长期推进多个项目，需要跨会话、跨月份保持记忆一致性，且愿意接受「结构化换效率」的约束。

**不适合**：需要多人实时协同编辑的场景（Git 冲突成本高）；需要甘特图、工时统计等重量级项目管理功能的场景。

---

## 2. 设计哲学：四条地基约束

这四条是整个系统的公理，所有具体设计都可以从它们推导出来。

> **1️⃣ 纯文本优先，零外部依赖。**
>
> 全部数据是 Markdown + YAML frontmatter。校验脚本用 Python 标准库手写 frontmatter 解析，**不引入 PyYAML** —— 因为工作区要能在任何一台裸机、任何一个 AI 沙箱里直接跑起来。可移植性优先于优雅。

> **2️⃣ 追加而非覆盖。**
>
> 条目一旦定稿，禁止原地修改语义。要纠正，就新增一条并把旧条目状态改为 `已作废(误)→DEC-0005`。这让 Git 历史成为真正可信的审计链，也让「为什么当初这么定」永远可回溯。

> **3️⃣ 人是唯一的决策者。**
>
> AI 可以起草、可以建议、可以整理，但涉及**范围、优先级、资源、对外承诺**的字段必须由 PM 确认。未确认状态在文件里显式标记为 `draft: true`，并且**会随时间恶化**（7 天警告，14 天硬阻断）—— 让悬而未决的事情无法被静静遗忘。

> **4️⃣ 约定必须可执行。**
>
> 写在文档里的规范如果没有脚本能检查它，就等于没写。因此每条规范都对应 `check.py` 里的一个检查函数；无法自动检查的规范会被明确标注为「人读约定」，不假装它有强制力。

---

## 3. 四层强制力模型

keel 把「规范」拆成四个层次，每层的强制力不同，读者（人和 AI）应当清楚知道自己在读哪一层。L0 是不可协商的人读宪法；L1–L3 是机器可执行的强制层。

| 层           | 载体                                 | 强制力     | 作用                                           |
| ----------- | ---------------------------------- | ------- | -------------------------------------------- |
| **L0 · 宪法** | `_共享/PM工作宪章.md`                    | 人读，不可协商 | 定义「人是决策者」这类根本原则，AI 不得援引任何理由绕过                |
| **L1 · 协议** | `_共享/写入协议.md`                      | 机器校验    | 完整 schema：字段全集、类型枚举、命名规范、文件归属、状态机。这是唯一的字段真相源 |
| **L2 · 模板** | `_模板/**`                           | 结构性约束   | 通过 `pm init` 复制，让新项目从第一秒就是合规的。模板本身也进 CI 校验   |
| **L3 · 脚本** | `scripts/check.py`、`scripts/pm.py` | 硬阻断     | 违规无法通过 pre-commit / CI。这是规范的最终执行者            |

**关键设计**：L1 的写入协议不是散文，而是一份**表格化的 schema 文档**。它用 §2.0 的 type 三层语义分层表明确定义了「哪些文件被全量校验、哪些只校验子类型、哪些完全不强制」，从而彻底消除「这个字段到底该不该填」的歧义。

---

## 4. 目录结构全景

```
keel/
├── AGENTS.md                  # AI 入口：读什么、按什么顺序读、禁止什么
├── CLAUDE.md / .cursorrules   # 各 AI 客户端的适配入口
├── README.md                  # 本文件
│
├── _共享/                      # 跨项目层
│   ├── PM工作宪章.md            # L0 宪法
│   ├── 写入协议.md              # L1 完整 schema（唯一字段真相源）
│   ├── 设计方案-v3.0.md         # 架构设计与取舍记录
│   └── 知识库/全局知识库.md      # GKB：已验证可跨项目复用的经验
│
├── _模板/                      # L2 母版，pm init 的复制源
│   ├── 项目管理/                # 项目章程、需求/风险/依赖登记册、干系人矩阵、路线图
│   ├── 记忆/                    # 进度日志、决策记录、沟通记录、知识库、agent会话
│   ├── 文档库/                  # 01-需求 … 07-报告，各含 _模板.md
│   ├── 原型/  归档/  .draft/
│   ├── 现状.md                  # 派生文件：高风险 + 阻塞依赖 + 待跟进
│   └── INDEX.md                 # 派生文件：全条目全景表
│
├── 项目/                       # 进行中的项目
│   └── PROJ-Node-PoC/          # 参考实现（同时是 CI 的合规夹具）
│
├── 已结项/                     # 结项归档
│
└── scripts/
    ├── pm.py                   # 全部写操作的唯一入口
    ├── check.py                # 校验引擎（17 项检查）
    ├── pre-commit              # Git 钩子
    └── test_check.py / test_pm.py
```

### 4.1 单个项目的内部结构

```
PROJ-Node-PoC/
├── 项目管理/          # 「契约层」：对外承诺、需要 PM 签字的东西
│   ├── 项目章程.md      # 目标、范围、边界、成功标准
│   ├── 需求登记册.md    # REQ 条目主表
│   ├── 风险登记册.md    # RSK 条目
│   ├── 依赖登记册.md    # DEP 条目
│   ├── 干系人矩阵.md    # 含「在场/已离场」状态列
│   └── 路线图.md        # 派生文件
│
├── 记忆/              # 「过程层」：AI 与 PM 的协作轨迹
│   ├── 进度日志.md      # PRG
│   ├── 决策记录.md      # DEC
│   ├── 沟通记录.md      # COM
│   ├── 知识库.md        # KB（项目本地）
│   └── agent会话.md     # SESSION，断点续传用
│
├── 文档库/            # 「交付层」：给人读的正式文档
│   ├── 01-需求/  02-调研/  03-方案/  04-评审/
│   ├── 05-验收/  06-会议/  07-报告/
│
├── 原型/  归档/  .draft/
├── 现状.md            # 派生：一眼看清当前风险与阻塞
└── INDEX.md           # 派生：全条目索引
```

> 💡 **为什么把「契约层」和「过程层」物理分开？**
>
> 因为它们的**修改权限不同**。`项目管理/` 里的东西改动需要 PM 确认，且改动本身值得被 review；`记忆/` 是高频追加区，AI 可以自由写入。物理隔离让权限差异变成目录差异，`check_file_location` 可以直接强制 RSK/DEP 只能出现在 `项目管理/` 下 —— 防止风险条目被悄悄塞进日志里稀释掉。

---

## 5. 核心数据模型

### 5.1 四类文件（写入协议 §2.0）

| 类别      | `type` 取值                                      | 是否有 `id`       | 校验强度                                   |
| ------- | ---------------------------------------------- | -------------- | -------------------------------------- |
| **条目级** | `req` `prg` `dec` `com` `kb` `rsk` `dep` `gkb` | ✅ 全局唯一         | 全量校验：必填字段、状态枚举、日期格式、类型特定字段、悬空引用、排序     |
| **文档级** | `doc` • `subtype`                              | ❌ 用 `ref` 指向条目 | 校验 `subtype` 枚举、`ref` 必填与有效性、文件名与位置一致性 |
| **容器级** | `charter` `req_log` `rsk_log` …                | ❌              | 不强制，仅供人和工具识别文件用途                       |
| **派生级** | `derived: true`（`index` / `现状` / `路线图`）        | ❌              | 跳过大部分检查（由脚本生成，不应手改）                    |

> 🔑 **这个分层解决了一个真实的主键冲突。**
>
> 早期设计里，PRD 文档和需求登记册条目都写 `id: REQ-0001`，导致「同一 ID 出现两次」被校验判为重复。新模型让文档不再持有 `id`，改用 `ref: REQ-0001` 做软关联 —— 主键唯一性回归干净，而且顺带获得了「一个需求可以有多份文档」的表达能力。

### 5.2 八种条目类型

| 前缀     | type  | 落地文件                        | 状态枚举                 | 类型特定必填               |
| ------ | ----- | --------------------------- | -------------------- | -------------------- |
| `REQ-` | `req` | `文档库/01-需求/REQ-XXXX-PRD.md` | 待评审 · 开发中 · 已验收 · 已砍 | —                    |
| `PRG-` | `prg` | `记忆/进度日志.md`                | 进行中 · 已完成 · 已阻塞      | —                    |
| `DEC-` | `dec` | `记忆/决策记录.md`                | 评估中 · 生效 · 待复审       | `review_due`         |
| `COM-` | `com` | `记忆/沟通记录.md`                | 已对齐 · 待跟进 · 失效       | —                    |
| `KB-`  | `kb`  | `记忆/知识库.md`                 | 本地 · 过时              | —                    |
| `RSK-` | `rsk` | `项目管理/风险登记册.md`             | 开放 · 已缓解 · 已关闭       | `level` `review_due` |
| `DEP-` | `dep` | `项目管理/依赖登记册.md`             | 等待中 · 已就绪 · 已逾期      | `expected_delivery`  |
| `GKB-` | `gkb` | `_共享/知识库/全局知识库.md`          | 生效 · 已归档             | —                    |

所有类型额外支持两个作废状态：

- `已作废(PM拒绝)` —— PM 明确否决
- `已作废(误)→DEC-0005` —— 记录有误，箭头**必须**指向正确条目

### 5.3 文档子类型

| `subtype`    | 文件名含 | 目录                              |
| ------------ | ---- | ------------------------------- |
| `prd`        | PRD  | `01-需求/`                        |
| `research`   | 调研   | `02-调研/`                        |
| `plan`       | 方案   | `03-方案/`                        |
| `review`     | 评审   | `04-评审/`                        |
| `acceptance` | 验收   | `05-验收/`                        |
| `report`     | —    | `07-报告/`（形如 `2026-07-26-周报.md`） |

`06-会议/` 有意不预建模板：会议纪要形态多变，强行结构化只会产生形式主义。该目录的 `README.md` 提供命名规范与 Markdown 脚手架，并明确「会议纪要不带 frontmatter」，同时给出域边界速记 —— **决议归 DEC、结论归 COM、进展归 PRG**，防止纪要变成信息黑洞。

### 5.4 字段全集

```yaml
# 通用
id, type, subtype, title, date, status, draft, proj_id, schema_version
# 关联
related, related_external, ref, blocks, artifacts
# 治理
confirmed_by, review_due, scope, derived, updated
# 风险专用
level, probability, impact, owner, mitigation
# 依赖专用
partner, expected_delivery
# 沟通专用
stakeholder, channel, participants
# 知识专用
category, domain, source
```

---

## 6. 生命周期

### 6.1 条目的一生

```
pm new  →  draft: true          # AI 起草,未经确认
   ↓
[PM 审阅补全]                    # 填 review_due / level / 修正 scope
   ↓
pm finalize  →  draft: false     # 确认生效,进入全量校验
   ↓
pm commit    →  Git 留痕         # 校验通过才能提交
   ↓
[状态流转]  开放 → 已缓解 → 已关闭
   ↓
[如需纠错]  已作废(误)→RSK-0007   # 追加新条目,不改旧的
```

### 6.2 草稿老化机制

| 天数     | 行为                        |
| ------ | ------------------------- |
| 0–6 天  | 静默                        |
| 7–13 天 | ⚠️ 警告：「该草稿已搁置 N 天，请确认或作废」 |
| ≥ 14 天 | 🚫 **硬阻断**，无法提交           |

这是整个系统里最重要的「反熵」设计：**未决事项会主动来找你，而不是沉入历史**。

### 6.3 确认门（`confirmed_by`）

涉及以下内容的条目必须携带 `confirmed_by: PM`：

- 需求范围的增减
- 优先级调整
- 资源与排期承诺
- 任何对外沟通的结论

`confirmed_by`（条目内字段）与 Git commit 的 `Approved-by` trailer（提交级签名）是两个不同粒度的确认，写入协议 §6.1 给出了判定规则。

### 6.4 KB → GKB 晋升

本地经验要升级为跨项目知识，需要满足判据并走完整流程（写入协议 §12）：

1. **判据**：已在 ≥ 2 个场景验证 / 与具体项目细节解耦 / 有明确适用边界
2. **步骤**：在 `全局知识库.md` 新增 GKB 条目 → 原 KB 状态改 `过时` 并加反向链接
3. **双向链接**：GKB 的 `source` 指回原 KB，KB 的 `related` 指向新 GKB

这个流程让知识库不会变成只增不减的垃圾场 —— 每一条 GKB 都有可追溯的实战出处。

---

## 7. CLI 完整参考

所有写操作都必须经由 `pm.py`，**不要手工编辑条目文件** —— 手写会绕过编号分配、插入锚点、默认字段填充与 TOCTOU 检查。

```bash
python scripts/pm.py <command> [args] [-p <项目路径>]
```

| 命令                | 作用             | 说明                                                              |
| ----------------- | -------------- | --------------------------------------------------------------- |
| `init <项目ID>`     | 从 `_模板/` 创建新项目 | 自动刷新所有容器文件的 `date`，章程刷 `updated`                                |
| `new-req "标题"`    | 新建需求           | 同时生成登记册条目与 PRD 文档骨架                                             |
| `new <type> "标题"` | 新建任意条目         | 自动分配下一个编号，带 TOCTOU 二次校验防并发撞号                                    |
| `finalize <ID>`   | 草稿定稿           | 精确定位 frontmatter 块翻 `draft` 标志                                  |
| `accept <REQ-ID>` | 走验收流程          | 生成验收文档并联动需求状态                                                   |
| `check`           | 运行全部校验         | 退出码 0 通过（可有警告）/ 1 硬阻断 / 2 运行异常                                   |
| `commit "msg"`    | 校验 + 提交        | 自动附 `Approved-by` / `Reviewed-by` trailer；GKB 变更时自动 add `_共享/`  |
| `brief [--all]`   | 重聚简报           | **新会话第一条命令**：三级回退锚点（SESSION → git log → mtime）+ 到期/警示项（高风险 RSK、DEP T-3/逾期、复审到期）+ 草稿区 + 超期条目草稿。`--all` 额外显示中/低风险开放项 |
| `gen-index`       | 重建派生文件         | 生成 `INDEX.md`（跨类全景索引，按路由表顺序分组）                                 |
| `doctor [--fix]`  | 环境自检           | 检查 Python / git / check.py / pre-commit hook / 章程 schema_version / .draft/。`--fix` 自动安装 hook |

### 7.1 每次新会话的标准开场

```bash
python scripts/pm.py brief -p 项目/PROJ-Node-PoC
```

输出包含：上次锚点（SESSION → git log → mtime 三级回退）、到期/警示项（高风险开放 RSK、DEP T-3 天内/已逾期、DEC/RSK 复审到期）、草稿区文件清单（含超期标注）、超期条目草稿（`draft: true` 超 7 天）。这一条命令替代了「把整个项目文档粘给 AI」。

---

## 8. 典型工作流

### 场景 A · 开一个新项目

```bash
python scripts/pm.py init PROJ-灯塔
# 编辑 项目管理/项目章程.md:填目标、范围、边界、成功标准
python scripts/pm.py commit "chore: 初始化 PROJ-灯塔"
```

### 场景 B · 记录一个需求并闭环

```bash
python scripts/pm.py new-req "支持批量导出" -p 项目/PROJ-灯塔
# → REQ-0003 + 文档库/01-需求/REQ-0003-PRD.md,draft: true
# PM 审阅 PRD,补全验收标准
python scripts/pm.py finalize REQ-0003 -p 项目/PROJ-灯塔
# ... 开发中 ...
python scripts/pm.py accept REQ-0003 -p 项目/PROJ-灯塔
# → 生成 05-验收/REQ-0003-验收.md,状态流转到 已验收
```

### 场景 C · 决策与勘误

```bash
python scripts/pm.py new dec "选用 SQLite 作为本地存储" -p 项目/PROJ-灯塔
# 填 review_due: 2026-10-25(三个月后复审)
python scripts/pm.py finalize DEC-0004 -p 项目/PROJ-灯塔

# 两周后发现记错了 ——不要改 DEC-0004,而是:
python scripts/pm.py new dec "选用 DuckDB 作为本地存储(修正 DEC-0004)"
# 然后把 DEC-0004 状态改为: 已作废(误)→DEC-0005
```

> ⚠️ **勘误必须一跳到位。** 不要形成「作废指向作废」的链条 —— 读者应当一次跳转就找到现行有效条目。

### 场景 D · 风险登记

```bash
python scripts/pm.py new rsk "上游 API 限流未知" -p 项目/PROJ-灯塔
# 必填:level(高/中/低)、review_due
# 建议同时填 probability / impact / owner / mitigation
```

高风险开放项会自动出现在 `pm brief` 和 `现状.md` 的第一张表里 —— **风险无处可藏**。

### 场景 E · 经验晋升为全局知识

```bash
# 项目内先沉淀
python scripts/pm.py new kb "中文路径需 URL 编码才能走 raw 接口"
# 在第二个项目再次验证后晋升
python scripts/pm.py new gkb "跨平台路径处理:中文与空格的统一编码策略"
# 原 KB 改 status: 过时,并加 related 指向新 GKB
```

### 场景 F · 结项

1. 清零所有 `draft: true` 条目（确认或作废）
2. 生成结项报告置于 `07-报告/`
3. 跑一次全量 `python scripts/pm.py check`
4. 目录移入 `已结项/`

---

## 9. 校验体系

`check.py` 目前实现 17 项检查，分两级：**硬阻断**先跑，一旦命中立即停止，避免用无效数据做后续推理。退出码：`0` 通过（可有警告）/ `1` 硬阻断 / `2` 运行异常。

### 9.1 硬阻断（退出码 1，禁止提交）

| 检查                      | 拦截什么                                                   |
| ----------------------- | ------------------------------------------------------ |
| `check_unique_ids`      | 同一 ID 出现多次                                             |
| `check_required_fields` | 缺 `id` / `type` / `title` / `date`（`status` 在草稿期降为警告）  |
| `check_type_fields`     | 缺类型特定必填字段（草稿期降警告）                                      |
| `check_status_enum`     | 状态值不在枚举内                                               |
| `check_date_format`     | 日期非 `YYYY-MM-DD`（含 `review_due` / `expected_delivery`） |
| `check_file_location`   | RSK / DEP 出现在 `项目管理/` 之外                               |
| `check_doc_files`       | 文档缺 `subtype` 或 `subtype` 不在枚举内                        |
| `check_draft_aging`     | 草稿搁置 ≥ 14 天                                            |

### 9.2 警告（仍退出码 0，允许提交但需知晓）

悬空引用（`related` / `blocks`）、`ref` 指向不存在的条目、`artifacts` 路径不存在、作废指向的目标不存在、条目排序错乱、草稿搁置 7–13 天、文档文件名与 `subtype` 不匹配、文档所在目录与 `subtype` 不匹配、`ref` 与文件名不一致、报告文件名格式不符。

### 9.3 值得一提的实现细节

- **frontmatter 提取用带 lookahead 的正则**（`(?=\S[^\n]*:)`），能正确处理紧凑格式与正文中的 `---` 分隔线
- **先剥离代码块再扫描**，避免把示例 YAML 误判为真实条目
- **`session` 类型显式跳过** —— 会话日志是高频追加的临时数据，不应承担条目级校验负担
- **派生文件通过解析 frontmatter 判定**（`derived: true` 或 `type in (现状, 路线图, index)`），而不是靠文件名猜测

---

## 10. 自动化

### 10.1 pre-commit

```bash
cp scripts/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

每次提交前自动跑 `check.py`，硬阻断则拒绝提交。

### 10.2 CI

`.github/workflows/ci.yml` 做三件事：

1. `pip install -r requirements-dev.txt`
2. **校验 `_模板/` 自身** —— 把模板目录克隆为临时项目再跑 check，防止母版带病传染给所有未来项目
3. `pytest scripts/test_check.py scripts/test_pm.py -v`

> 🧪 **参考项目 `PROJ-Node-PoC` 同时是测试夹具。** 它必须永远处于 100% 合规状态 —— 这意味着任何破坏性改动都会立刻被 CI 抓到，也意味着新用户永远有一个可信的正确样例可以对照。

---

## 11. 设计取舍 FAQ

**Q：为什么不用 Notion / Jira / 数据库？**

A：因为 AI 需要的是**可 grep、可 diff、可版本化**的文本。Git 天然提供审计链与时间旅行；纯文本让任何 AI agent 无需 API 权限就能读写。代价是失去实时协同 —— 这是有意接受的取舍。

**Q：为什么坚持不引入 PyYAML？**

A：为了让工作区在任何裸环境（包括 AI 沙箱、临时容器）里 `python check.py` 就能直接跑。手写解析器的维护成本远低于「用户装不上依赖导致校验被跳过」的风险。

**Q：为什么条目要全局唯一编号，而不是按项目重新计数？**

A：为了支持跨项目引用语法 `REQ-0007@PROJ-灯塔`。全局唯一意味着一个 ID 在任何上下文里都无歧义。

**Q：为什么草稿会「过期」？这不是很烦人吗？**

A：这正是设计意图。项目管理最大的失败模式不是决策错误，而是**决策悬空**。让悬空状态随时间产生越来越大的噪音，是唯一能对抗遗忘的机制。

**Q：AI 可以直接改文件吗？**

A：技术上可以，但规范上禁止 —— 必须走 `pm.py`。`AGENTS.md` 会在 AI 读到的第一屏就说明这一点，而 `check.py` 会在提交时抓住任何绕过工具产生的格式偏差。

**Q：keel 是什么意思？**

A：龙骨 —— 船体最底部那根贯穿首尾的主承力构件。它不好看、平时看不见，但**决定了整条船能承受多大的浪**。

---

## 12. 路线图

### 近期（进行中）

- [ ] 文档级 `related` 字段的悬空校验（当前仅 `ref` 被校验）
- [ ] `pm new` 为 `review_due` / `expected_delivery` 填入合理默认值，消除 `finalize` 后立刻硬阻断的流程死锁
- [ ] CI 真正覆盖 `_模板.md` 自身的 frontmatter（当前被按文件名跳过）
- [ ] `作废指向作废` 的链式警告

### 中期

- [ ] 抽出 `scripts/keel_schema.py` 作为唯一常量真相源，`check.py` 与 `pm.py` 共同 import
- [ ] 增加「写入协议表格 ↔ schema 常量」一致性测试，让文档与代码在 CI 层面永不分叉
- [ ] `draft_since` 字段，使草稿计龄不受历史回填的 `date` 干扰
- [ ] 派生文件 schema 定义（统一 `date` 与 `updated` 字段命名）

### 远期

- [ ] `pm close` —— 结项流程工具化
- [ ] `pm review` —— 到期复审批处理
- [ ] `pm link-check --cross` —— 跨项目引用校验
- [ ] 可选扫描 `已结项/`，消除归档区的校验盲区

---

<div align="center">

⛵

**规范不是用来贴在墙上的，是用来编译的。**

</div>
