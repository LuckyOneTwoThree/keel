# AGENTS — AI 协作入口

> 仓库根目录入口文件。完整协作契约见 [_共享/AGENTS.md](_共享/AGENTS.md)。
> 真正的强制力在 `scripts/check.py`(L3),本文件是建议层(L1)。

## 四条地基约束(不可动)

1. **单一真相源**:每类信息只在一个文件。路由表见下。
2. **只追加不回改**:记忆层新增条目,推翻只改状态字段(`已作废(误)→DEC-XXXX` / `已作废(PM拒绝)`)。
3. **时间轴优先**:同文件内最新在顶,按 `date` 降序。
4. **节点自给自足**:每个文件、每个阶段都可独立存在。agent 可串联,但不强制。

## 真相源路由表(精简版)

| 信息类型 | 唯一归属 | 引用 |
| --- | --- | --- |
| 需求主线 | `项目管理/需求登记册.md` | REQ- |
| 里程碑 | `项目管理/路线图.md` | — |
| 风险 | `项目管理/风险登记册.md` | RSK- |
| 依赖 | `项目管理/依赖登记册.md` | DEP- |
| 决策 | `记忆/决策记录.md` | DEC- |
| 沟通 | `记忆/沟通记录.md` | COM- |
| 进度 | `记忆/进度日志.md` | PRG- |
| 本地知识 | `记忆/知识库.md` | KB- |
| 通用知识 | `_共享/知识库/全局知识库.md` | GKB- |
| 短时记忆 | `记忆/agent会话.md` | SESSION- |

> 项目内工作时路径前缀为 `项目/PROJ-X/`;共享层在 `_共享/`。
> 完整路由表(含会议/报告/干系人等)见 [_共享/AGENTS.md](_共享/AGENTS.md)。

## 三条协作铁律

- **写入前出稿**:agent 写真相源前先出 `.draft/`,PM 直写不经草稿区。
- **引用优于复制**:跨文件用编号引用(如 `DEC-0005`),不复述内容。
- **写前自检**:写入前跑 `python scripts/check.py <项目目录>`,失败则不落盘。

## 确认门(L0-L3)

| 级别 | 操作 | agent 行为 |
| --- | --- | --- |
| L0 只读 | 读真相源 | 直接做 |
| L1 起草 | `.draft/` + 派生文件刷新 | 直接做,事后告知 PM |
| L2 写真相源 | 写条目(含周报落 `07-报告`) | PM 确认编号 + 内容后落盘 + commit |
| L3 改基线 | 改章程/范围/里程碑 | PM 显式授权 + 走 DEC- |

## 常用命令

```bash
python scripts/pm.py new-req "标题"     # 新建需求(自动编号 + 起 PRD 草稿)
python scripts/pm.py new dec "标题"     # 新建决策/风险/依赖等
python scripts/pm.py check              # 校验当前项目
python scripts/pm.py finalize <id>      # draft:true → false + 跑校验
python scripts/pm.py commit "信息"      # 校验 + git commit + Approved-by
python scripts/pm.py brief              # 重聚简报(三级回退锚点)
python scripts/pm.py doctor --fix       # 自检环境 + 自动装 pre-commit hook
```

## 不确定时

- 写哪里 → 查路由表 / [_共享/AGENTS.md](_共享/AGENTS.md)
- 怎么写 → [_共享/写入协议.md](_共享/写入协议.md)
- 为什么这么定 → [_共享/PM工作宪章.md](_共享/PM工作宪章.md)
- 校验规则 → `python scripts/check.py --help` 或读脚本头部注释
