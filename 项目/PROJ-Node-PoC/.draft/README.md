# .draft/ 草稿区

> agent 起草时用,PM 直写不经此区。草稿不享受只追加保护,PM 拒绝后直接删。

## 命名规则(幂等键从意图派生)

| 类型 | 文件名格式 | 例 |
| --- | --- | --- |
| 起草 PRD | `draft-req-{编号}-prd.md` | `draft-req-0007-prd.md` |
| 起草方案 | `draft-req-{编号}-方案.md` | `draft-req-0007-方案.md` |
| 起草决策 | `draft-dec-{编号}.md` | `draft-dec-0013.md` |
| 起草周报 | `draft-weekly-{YYYY-MM-DD}.md` | `draft-weekly-2026-07-25.md` |

## 生命周期

1. agent 起草 → 写入 `.draft/draft-{意图}.md`
2. PM 审 → 修改或要求 agent 修改
3. PM 确认 → agent 将草稿 rename/移动到正式位 + 写入真相源 + commit
4. 清空草稿 → 删除 `.draft/` 下对应文件

## 拒绝处理

PM 拒绝 → 直接删草稿文件(草稿区不享受只追加保护,不进 git 审计)。

## 续传

agent 重启后扫 `.draft/` 按文件名识别意图续传。草稿文件存在 = 工作流断点。
