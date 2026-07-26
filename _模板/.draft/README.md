# .draft/ 草稿区

> v3.0 §2.4 · agent 起草暂存区。PM 直写不经此目录。
>
> **不享受只追加保护**:PM 拒绝后直接删,不进 git 历史。
>
> **幂等键从意图派生**(A3 修法,非随机 uuid):
> - `draft-req-0007-prd.md` — 起草 REQ-0007 的 PRD
> - `draft-weekly-2026-07-25.md` — 起草 2026-07-25 周报
> - `draft-dec-0013.md` — 起草 DEC-0013
> - `draft-{类型}-{编号或日期}-{主题}.md` — 通用模式
>
> agent 崩溃重启后扫 `.draft/`,按文件名识别上次未完成的草稿,续传。
>
> **定稿流程**:
> 1. agent 在此起草 → PM 审阅
> 2. PM 确认 → `pm finalize <id>`(draft:true → false + 移到正式位 + 全量校验)
> 3. PM 拒绝 → 直接删草稿文件
>
> **draft 老化 forcing function**(D1):
> - 超 7 天 → `pm check` 警告
> - 超 14 天 → `pm check` 阻断(强制 finalize 或砍)
