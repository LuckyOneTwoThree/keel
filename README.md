# PM 工作区

> v3.0 · PM 中心化 + agent 可托管 · pull-based 上线。
>
> **⚠️ 本仓库是工作区框架本身**(协议层 + 模板层 + 脚本层),不是某个真实项目的工作区。
> - `_共享/` `_模板/` `scripts/` = 框架本体,所有使用者共享同一份规则与脚本
> - `项目/PROJ-Node-PoC/` = **示例夹具**,仅验证 v3.0 协议可跑通,非真实业务数据
> - 真实使用方式:克隆本框架 → `pm init PROJ-你的项目名` → 在 `项目/PROJ-你的项目名/` 内干活

## 核心心智
**四条地基约束**(详见 [_共享/PM工作宪章.md](_共享/PM工作宪章.md)):
1. 单一真相源(派生文件标 `derived: true`,可重建)
2. 只追加不回改(推翻只改状态字段)
3. 时间轴优先(ISO 日期,最新在顶)
4. **节点自给自足**(agent 是连接器不是必经路径,关联是软的、节点是硬的)

## 三段式结构
- `_共享/`  全局规则与通用知识(唯一一份)
- `_模板/`  项目骨架母版(克隆用)
- `项目/`   各项目独立实例;`已结项/` 下线归档

## v3.0 核心设施
- `scripts/check.py` 校验层(唯一强制力,pre-commit hook 调用)
- `scripts/pm.py` CLI 门面(PM 永不敲裸 git/frontmatter)
- `scripts/pre-commit` git hook(首次使用跑 `pm doctor --fix` 自动安装)
- 项目根 `.draft/` 草稿区(agent 起草用,PM 直写不经)
- `记忆/agent会话.md` 短时记忆(跨会话延续)
- 条目 frontmatter schema(正文不重复字段,详见 [写入协议.md](_共享/写入协议.md))

## 快速开始(5 分钟跑通)

```bash
# 1. 克隆本框架(或 fork 后 clone 自己的)
git clone <repo-url> pm-playbook && cd pm-playbook

# 2. 自检环境 + 自动装 pre-commit hook(只需一次)
python scripts/pm.py doctor --fix

# 3. 从模板创建你的第一个项目
python scripts/pm.py init PROJ-我的项目

# 4. 进入项目目录干活
cd 项目/PROJ-我的项目

# 5. 创建第一条需求(自动起 PRD 草稿)
python scripts/pm.py new-req "用户登录双因子认证"
# → 草稿落到 .draft/draft-req-0001-prd.md,draft:true

# 6. 编辑 PRD 草稿正文,然后定稿(草稿→正式位 + 全量校验)
python scripts/pm.py finalize REQ-0001
# → 落到 文档库/01-需求/REQ-0001-PRD.md

# 7. 同时在 项目管理/需求登记册.md 手动追加 REQ-0001 条目(PRD 是 doc,登记册才是 REQ 真相源)

# 8. 校验整个项目
python scripts/pm.py check

# 9. 看重聚简报(下次回到项目时跑)
python scripts/pm.py brief

# 10. commit(校验 + git commit + Approved-by trailer)
python scripts/pm.py commit "[REQ-0001] 新增需求"
```

> 真实使用时:PM 直写不经草稿区,直接在登记册/章程/路线图编辑,然后 `pm check && pm commit`。
> `pm new-req`/`pm new <type>` 是 agent 起草路径,PM 也可用。

## 我要做 X,该去哪?
| 我想… | 去… |
| --- | --- |
| 记新需求 | `项目管理/需求登记册.md` (REQ-) 或 `pm new-req "标题"` |
| 写 PRD | `文档库/01-需求/REQ-XXXX-PRD.md` |
| 写方案 | `文档库/03-方案/REQ-XXXX-方案.md` |
| 记进展 | `记忆/进度日志.md` (PRG-) |
| 记决策 / 看决策 | `记忆/决策记录.md` (DEC-) |
| 记沟通 | `记忆/沟通记录.md` (COM-) |
| 记风险 | `项目管理/风险登记册.md` (RSK-) |
| 记外部依赖 | `项目管理/依赖登记册.md` (DEP-) |
| 记本地知识 / 看本地知识 | `记忆/知识库.md` (KB-) |
| 查方法论 | `_共享/知识库/全局知识库.md` (GKB-) |
| 看现状 | `现状.md` |
| 看重聚简报 | `pm brief` |
| 校验工作区 | `pm check` |
| 自检环境 | `pm doctor` |
| 安装 pre-commit hook | `pm doctor --fix` |

## 编号速查
REQ 需求 / PRG 进度 / DEC 决策 / COM 沟通 / KB 本地知识 / RSK 风险 / DEP 依赖 / GKB 全局知识。
前缀+4 位,各类独立递增(per-project 作用域)。跨项目用 `REQ-0007@PROJ-灯塔`。
不确定写哪里时先查根目录 [AGENTS.md](AGENTS.md) 路由表(完整契约见 [_共享/AGENTS.md](_共享/AGENTS.md))。

## 确认门(L0-L3)
| 级别 | 操作 | agent 行为 | PM 行为 |
| --- | --- | --- | --- |
| L0 只读 | 读真相源 | 直接做 | 直接做 |
| L1 起草 | `.draft/` + 派生文件 | 直接做,事后告知 | 不适用 |
| L2 写真相源 | 写条目 | PM 确认后落盘 | 直接写,无需确认 |
| L3 改基线 | 改章程/范围/里程碑 | PM 显式授权 + DEC- | 直接写(建议走 DEC-) |
