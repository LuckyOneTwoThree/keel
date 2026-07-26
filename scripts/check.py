#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM-Playbook v3.0 校验脚本
用法: python scripts/check.py [项目目录]
不传参数则校验所有项目。

校验规则(对应 v3.0 设计方案 §2.3):
  - 编号唯一(per-project 作用域): 硬阻断
  - 编号连续(建议 max+1): 仅警告(已降级为静默,见 check_continuity 注释)
  - 悬空引用(draft:false 时): 硬阻断
  - 悬空引用(draft:true 时): 仅警告
  - 状态枚举: 硬阻断(已作废/已推翻/已晋升 前缀豁免)
  - frontmatter schema:
      id/type/title/date 必填: 硬阻断(基本标识,即使 draft 也强制)
      status 必填: draft:false 硬阻断 / draft:true 警告(写入协议 §4)
  - 类型特定必填字段: draft:false 硬阻断 / draft:true 警告
      RSK: level, review_due
      DEC: review_due
      DEP: expected_delivery
  - RSK level 枚举(高/中/低): 硬阻断
  - 日期格式(ISO YYYY-MM-DD): 硬阻断
  - 文件位置(RSK/DEP 必在 项目管理/ 下): 硬阻断
  - doc 文件 subtype 枚举(prd/plan/research/review/acceptance/report): 硬阻断
  - 排序(同文件内最新在顶): 警告
  - draft 老化(D1): 超 7 天警告,超 14 天阻断
  - 跨项目引用(@PROJ 语法): 不校验(只校项目内)
  - doc ref 悬空(非 draft): 警告(软关联,允许先写 PRD 后立 REQ)
  - req artifacts 路径不存在(非 draft): 警告
  - 作废指向悬空(已作废(误)→XXX-XXXX 中 XXX-XXXX 不存在,非 draft): 警告

退出码:
  0 = 全部通过(可有警告)
  1 = 有硬阻断错误
  2 = 运行异常
"""

import sys
import os
import re
import glob
from datetime import datetime, date
from pathlib import Path

# ========== 配置 ==========

# 工作区根目录(脚本位于 scripts/check.py,根在上一级)
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# 条目类型 → 编号前缀
TYPE_PREFIX = {
    "req": "REQ",
    "prg": "PRG",
    "dec": "DEC",
    "com": "COM",
    "kb": "KB",
    "rsk": "RSK",
    "dep": "DEP",
    "gkb": "GKB",
}

# 各类型允许状态(对应 v3.0 §2.1.2)
ALLOWED_STATUS = {
    "req": {"待评审", "开发中", "已验收", "已砍",
            "已作废(PM拒绝)", "已作废(误)"},
    "prg": {"进行中", "已完成", "已阻塞",
            "已作废(PM拒绝)", "已作废(误)"},
    "dec": {"评估中", "生效", "待复审",
            "已作废(PM拒绝)", "已作废(误)"},
    "com": {"已对齐", "待跟进", "失效",
            "已作废(PM拒绝)", "已作废(误)"},
    "kb":  {"本地", "过时",
            "已作废(PM拒绝)", "已作废(误)"},
    "rsk": {"开放", "已缓解", "已关闭",
            "已作废(PM拒绝)", "已作废(误)"},
    "dep": {"等待中", "已就绪", "已逾期",
            "已作废(PM拒绝)", "已作废(误)"},
    "gkb": {"生效", "已归档",
            "已作废(PM拒绝)", "已作废(误)"},
}

# 必填字段(所有类型)
REQUIRED_FIELDS = ["id", "type", "title", "date", "status"]

# 类型特定必填字段
TYPE_REQUIRED_FIELDS = {
    "rsk": ["level", "review_due"],   # 风险等级 + 复审到期
    "dec": ["review_due"],            # 决策复审到期
    "dep": ["expected_delivery"],     # 依赖期望交付日
}

# RSK level 允许值
ALLOWED_LEVEL = {"高", "中", "低"}

# doc 文件子类型枚举(PRD/方案/调研/评审/验收/报告)
DOC_SUBTYPE = {"prd", "plan", "research", "review", "acceptance", "report"}

# 类型 → 应位于的子目录(用于文件位置校验,防 RSK/DEP 错放 记忆/)
TYPE_FILE_LOCATION = {
    "rsk": "项目管理",  # RSK 应在 项目管理/风险登记册.md
    "dep": "项目管理",  # DEP 应在 项目管理/依赖登记册.md
}

# 派生文件标记(豁免悬空校验)
DERIVED_MARKERS = ["derived: true", "type: 现状", "type: 路线图"]

# draft 老化阈值
DRAFT_WARN_DAYS = 7
DRAFT_BLOCK_DAYS = 14

# ========== 解析 ==========

def parse_frontmatter(content):
    """解析 YAML frontmatter。返回 (frontmatter_dict, body)。
    支持:内联列表 [a, b]、block 列表(缩进 - )、True/yes/False/no 归一化。
    不依赖 PyYAML(可移植性)。"""
    if not content.startswith("---"):
        return None, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content
    fm_text = parts[1].strip()
    body = parts[2]
    fm = {}
    lines = fm_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if ":" not in stripped:
            i += 1
            continue
        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "":
            # 值为空:检查下一行是否是 block 列表项
            if i + 1 < len(lines) and lines[i + 1].strip().startswith("- "):
                items = []
                j = i + 1
                while j < len(lines) and lines[j].strip().startswith("- "):
                    item_val = lines[j].strip()[2:].strip().strip("'\"")
                    items.append(item_val)
                    j += 1
                fm[key] = items
                i = j
                continue
            else:
                fm[key] = ""
                i += 1
                continue
        if val.startswith("[") and val.endswith("]"):
            # 内联列表 [a, b, c]
            inner = val[1:-1].strip()
            if inner:
                items = [x.strip().strip("'\"") for x in inner.split(",")]
                fm[key] = items
            else:
                fm[key] = []
        else:
            # 标量值:True/yes → "true",False/no → "false"
            # (保持字符串,与现有 check_draft_aging 等逻辑兼容)
            low = val.lower().strip("'\"")
            if low in ("true", "yes"):
                fm[key] = "true"
            elif low in ("false", "no"):
                fm[key] = "false"
            else:
                fm[key] = val.strip("'\"")
        i += 1
    return fm, body

def find_entries(project_dir):
    """扫描项目目录,找出所有带 frontmatter 的条目。
    返回 list of dict: {file, fm, body, entry_id, entry_type}"""
    entries = []
    md_files = []
    for root, dirs, files in os.walk(project_dir):
        # 跳过 .draft/ (草稿区,非真条目)
        # 归档/ 不跳过——归档条目仍是真相源,参与编号唯一性校验
        # (防分片归档后编号重用,详见设计方案 v3.0 §10)
        if ".draft" in Path(root).parts:
            continue
        for f in files:
            # 跳过 _模板.md(文档库母版,非真条目)
            if f.endswith(".md") and f != "_模板.md":
                md_files.append(os.path.join(root, f))
    for fpath in md_files:
        # 跳过派生文件(现状/INDEX 等,编号是示例非真条目)
        if is_derived_file(fpath):
            continue
        try:
            with open(fpath, encoding="utf-8") as fp:
                content = fp.read()
        except Exception as e:
            entries.append({"file": fpath, "error": f"读取失败: {e}"})
            continue
        # 去掉代码块(避免代码块里的 frontmatter 被误解析为真条目)
        content = re.sub(r"```[a-zA-Z]*\n.*?\n```", "", content, flags=re.DOTALL)
        # 一个文件可能含多个条目(v3.0 多条目文件)
        # 简化:用 --- 分块,每个含 id: 的块算一个条目
        blocks = re.split(r"\n---\s*\n", content)
        for block in blocks:
            block = block.strip()
            if not block.startswith("---"):
                continue
            # 重新加上开头 ---
            block_with_open = "---" + block if not block.startswith("---\n") else block
            fm, body = parse_frontmatter(block_with_open + "\n---\n")
            if fm and "id" in fm and "type" in fm:
                entries.append({
                    "file": fpath,
                    "fm": fm,
                    "body": body,
                    "entry_id": fm["id"],
                    "entry_type": fm.get("type", ""),
                })
    return entries

def is_derived_file(fpath):
    """检查是否是派生文件(豁免悬空校验)"""
    try:
        with open(fpath, encoding="utf-8") as fp:
            content = fp.read(500)  # 只读头部
        return any(m in content for m in DERIVED_MARKERS)
    except:
        return False

# ========== 校验 ==========

def check_unique_ids(entries, project_name):
    """编号唯一性(per-project 作用域)。硬阻断。"""
    errors = []
    seen = {}
    for e in entries:
        eid = e["entry_id"]
        if eid in seen:
            errors.append(
                f"[{project_name}] 编号重复: {eid}\n"
                f"  出现于: {e['file']}\n"
                f"  已存在于: {seen[eid]}"
            )
        else:
            seen[eid] = e["file"]
    return errors

def check_continuity(entries, project_name):
    """编号连续性(建议 max+1)。

    已降级为静默:作废/砍需求/草稿删除都会导致合法跳号,
    唯一性校验(check_unique_ids)已足够检测真问题(重复编号)。
    保留函数以备将来需要,但 check_project 不再调用。
    """
    return []

def check_status_enum(entries, project_name):
    """状态枚举。硬阻断。"""
    errors = []
    for e in entries:
        t = e["entry_type"]
        if t not in ALLOWED_STATUS:
            continue
        status = e["fm"].get("status", "")
        # 带后缀的状态(已作废/已推翻/已晋升 系列)豁免枚举校验
        if status.startswith("已作废(误)→"):
            continue
        if status.startswith("已作废(PM拒绝)"):
            continue
        if status.startswith("已推翻→"):
            continue
        if status.startswith("已晋升→"):
            continue
        if status not in ALLOWED_STATUS[t]:
            errors.append(
                f"[{project_name}] 状态枚举非法: {e['entry_id']}\n"
                f"  status: '{status}'\n"
                f"  允许: {ALLOWED_STATUS[t]}\n"
                f"  文件: {e['file']}"
            )
    return errors

def check_required_fields(entries, project_name):
    """必填字段校验(对应写入协议 §4 draft 宽松)。
    - id/type/title/date: 基本标识,即使 draft:true 也硬阻断(否则不知道是哪条)
    - status: draft:true 时缺失降级为警告;draft:false 硬阻断
    """
    errors = []
    warnings = []
    # 基本标识字段(即使 draft 也硬阻断)
    HARD_REQUIRED = ["id", "type", "title", "date"]
    for e in entries:
        is_draft = e["fm"].get("draft", "false") == "true"
        for field in HARD_REQUIRED:
            if field not in e["fm"] or not e["fm"][field]:
                errors.append(
                    f"[{project_name}] 必填字段缺失: {e['entry_id']}\n"
                    f"  缺失字段: {field}\n"
                    f"  文件: {e['file']}"
                )
        # status: draft:true 时降级为警告(与写入协议 §4 一致)
        if "status" not in e["fm"] or not e["fm"]["status"]:
            msg = (
                f"[{project_name}] 必填字段缺失: {e['entry_id']}\n"
                f"  缺失字段: status\n"
                f"  文件: {e['file']}"
            )
            if is_draft:
                warnings.append(msg + f"\n  (draft:true,仅警告)")
            else:
                errors.append(msg)
    return errors, warnings

def check_date_format(entries, project_name):
    """日期格式(ISO YYYY-MM-DD)。硬阻断。"""
    errors = []
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for e in entries:
        d = e["fm"].get("date", "")
        if d and not date_re.match(str(d)):
            errors.append(
                f"[{project_name}] 日期格式非法: {e['entry_id']}\n"
                f"  date: '{d}' (应为 YYYY-MM-DD)\n"
                f"  文件: {e['file']}"
            )
    return errors

def check_type_fields(entries, project_name):
    """类型特定字段校验(对应写入协议 §4 draft 宽松)。
    - draft:false → 硬阻断
    - draft:true → 类型必填字段缺失降级为警告(与 check_dangling_refs 一致)
    - RSK level 枚举:无论 draft 都硬阻断(格式问题,非缺失)
    - 作废状态豁免(与 check_status_enum 一致)
    """
    errors = []
    warnings = []
    for e in entries:
        t = e["entry_type"]
        status = e["fm"].get("status", "")
        is_draft = e["fm"].get("draft", "false") == "true"
        # 作废状态豁免
        if status.startswith("已作废"):
            continue
        # 类型特定必填字段
        required = TYPE_REQUIRED_FIELDS.get(t, [])
        for field in required:
            val = e["fm"].get(field, "")
            if not val:
                msg = (
                    f"[{project_name}] 类型字段缺失: {e['entry_id']}\n"
                    f"  {t} 类型必填字段: {field}\n"
                    f"  文件: {e['file']}"
                )
                if is_draft:
                    warnings.append(msg + f"\n  (draft:true,仅警告)")
                else:
                    errors.append(msg)
        # RSK level 枚举校验(无论 draft 都校验,枚举非法是格式问题)
        if t == "rsk":
            level = e["fm"].get("level", "")
            if level and level not in ALLOWED_LEVEL:
                errors.append(
                    f"[{project_name}] RSK level 枚举非法: {e['entry_id']}\n"
                    f"  level: '{level}'\n"
                    f"  允许: {ALLOWED_LEVEL}\n"
                    f"  文件: {e['file']}"
                )
    return errors, warnings

def check_dangling_refs(entries, project_name):
    """悬空引用校验。
  - draft: true → 仅警告
  - draft: false 或无 draft → 硬阻断
  - related_external → 不校验
  - 跨项目引用(含 @)→ 不校验
"""
    errors = []
    warnings = []
    # 收集本项目所有 id
    all_ids = {e["entry_id"] for e in entries}
    for e in entries:
        is_draft = e["fm"].get("draft", "false") == "true"
        related = e["fm"].get("related", [])
        if isinstance(related, str):
            related = [related]
        for ref in related:
            # 跨项目引用不校验
            if "@" in ref:
                continue
            if ref not in all_ids:
                msg = (
                    f"[{project_name}] 悬空引用: {e['entry_id']}\n"
                    f"  related: '{ref}' 不存在\n"
                    f"  文件: {e['file']}"
                )
                if is_draft:
                    warnings.append(msg + f"\n  (draft:true,仅警告)")
                else:
                    errors.append(msg)
    return errors, warnings

def check_draft_aging(entries, project_name, today=None):
    """draft 老化(D1)。超 7 天警告,超 14 天阻断。"""
    if today is None:
        today = date.today()
    errors = []
    warnings = []
    for e in entries:
        if e["fm"].get("draft", "false") != "true":
            continue
        d = e["fm"].get("date", "")
        if not d:
            continue
        try:
            entry_date = datetime.strptime(str(d), "%Y-%m-%d").date()
        except:
            continue
        age = (today - entry_date).days
        if age > DRAFT_BLOCK_DAYS:
            errors.append(
                f"[{project_name}] draft 老化超 {DRAFT_BLOCK_DAYS} 天: {e['entry_id']}\n"
                f"  草稿龄: {age} 天\n"
                f"  请 finalize 或删除\n"
                f"  文件: {e['file']}"
            )
        elif age > DRAFT_WARN_DAYS:
            warnings.append(
                f"[{project_name}] draft 老化超 {DRAFT_WARN_DAYS} 天: {e['entry_id']}\n"
                f"  草稿龄: {age} 天\n"
                f"  文件: {e['file']}"
            )
    return errors, warnings

def check_sorting(entries, project_name):
    """同文件内最新在顶。仅警告。"""
    warnings = []
    # 按文件分组,检查每个文件内条目顺序
    by_file = {}
    for e in entries:
        by_file.setdefault(e["file"], []).append(e)
    for fpath, file_entries in by_file.items():
        if len(file_entries) < 2:
            continue
        # 按 date 降序应为最新在顶
        dates = []
        for e in file_entries:
            d = e["fm"].get("date", "")
            try:
                dates.append(datetime.strptime(str(d), "%Y-%m-%d").date())
            except:
                dates.append(date.min)
        # 检查是否降序
        is_desc = all(dates[i] >= dates[i+1] for i in range(len(dates)-1))
        if not is_desc:
            warnings.append(
                f"[{project_name}] 排序警告: {fpath}\n"
                f"  条目未按日期降序(最新应在顶)"
            )
    return warnings

def check_file_location(entries, project_name, project_dir):
    """RSK/DEP 必须在 项目管理/ 下(防错放 记忆/)。硬阻断。"""
    errors = []
    for e in entries:
        t = e["entry_type"]
        if t not in TYPE_FILE_LOCATION:
            continue
        required_dir = TYPE_FILE_LOCATION[t]
        fpath = e["file"]
        try:
            rel = os.path.relpath(fpath, project_dir)
        except ValueError:
            continue
        # 拆分路径组件,精确匹配(避免子串误判)
        parts = Path(rel).parts
        if required_dir not in parts:
            errors.append(
                f"[{project_name}] 文件位置错误: {e['entry_id']}\n"
                f"  {t} 类型应在 {required_dir}/ 下,实际: {rel}\n"
                f"  路由表:{required_dir}/风险登记册.md 或 {required_dir}/依赖登记册.md"
            )
    return errors

def check_doc_files(project_dir, project_name):
    """校验 doc 类型文件的 frontmatter。
    doc 文件不参与唯一性校验(无 id),但校验 subtype 必填且枚举。硬阻断。"""
    errors = []
    md_files = []
    for root, dirs, files in os.walk(project_dir):
        if ".draft" in Path(root).parts:
            continue
        for f in files:
            if f.endswith(".md") and f != "_模板.md":
                md_files.append(os.path.join(root, f))
    for fpath in md_files:
        try:
            with open(fpath, encoding="utf-8") as fp:
                content = fp.read()
        except Exception:
            continue
        # 去掉代码块(避免模板里的 frontmatter 示例被误解析)
        content_clean = re.sub(r"```[a-zA-Z]*\n.*?\n```", "", content, flags=re.DOTALL)
        if not content_clean.startswith("---"):
            continue
        fm, _ = parse_frontmatter(content_clean)
        # 只校验 type: doc 的文件(非 doc 文件如 INDEX/现状/章程 都跳过)
        if not fm or fm.get("type") != "doc":
            continue
        subtype = fm.get("subtype", "")
        if not subtype:
            errors.append(
                f"[{project_name}] doc 文件缺 subtype: {fpath}\n"
                f"  允许: {DOC_SUBTYPE}"
            )
        elif subtype not in DOC_SUBTYPE:
            errors.append(
                f"[{project_name}] doc subtype 枚举非法: {fpath}\n"
                f"  subtype: '{subtype}'\n"
                f"  允许: {DOC_SUBTYPE}"
            )
    return errors

def check_dangling_doc_refs(project_dir, project_name, all_ids):
    """校验 doc 文件的 ref 字段是否指向存在的 REQ- 条目。仅警告。

    doc 文件无 id,用 ref 关联 REQ-XXXX。ref 悬空通常是:
    - PRD 写好了但 REQ 条目还没立(允许,因为是软关联)
    - REQ 编号写错(应该警告)

    draft:true 的 doc 文件降级为静默(草稿期允许前向引用)。
    """
    warnings = []
    md_files = []
    for root, dirs, files in os.walk(project_dir):
        if ".draft" in Path(root).parts:
            continue
        for f in files:
            if f.endswith(".md") and f != "_模板.md":
                md_files.append(os.path.join(root, f))
    for fpath in md_files:
        try:
            with open(fpath, encoding="utf-8") as fp:
                content = fp.read()
        except Exception:
            continue
        content_clean = re.sub(r"```[a-zA-Z]*\n.*?\n```", "", content, flags=re.DOTALL)
        if not content_clean.startswith("---"):
            continue
        fm, _ = parse_frontmatter(content_clean)
        if not fm or fm.get("type") != "doc":
            continue
        ref = fm.get("ref", "")
        if not ref:
            continue  # report 子类型无 ref 是合法的
        # draft 的 doc 不校验 ref(草稿期允许前向引用)
        if fm.get("draft", "false") == "true":
            continue
        # report 子类型无 ref 合法(周报不绑特定 REQ)
        if fm.get("subtype") == "report":
            continue
        if ref not in all_ids:
            warnings.append(
                f"[{project_name}] doc ref 悬空: {fpath}\n"
                f"  ref: '{ref}' 不存在\n"
                f"  (doc 与 REQ 是软关联,允许先写 PRD 后立 REQ,但定稿后应补齐)"
            )
    return warnings

def check_artifacts_path(entries, project_dir, project_name):
    """校验 req 条目的 artifacts 路径是否存在。仅警告。

    artifacts 是相对 文档库/ 的路径列表。
    路径不存在通常是:
    - PRD 还没建(REQ 立了但 PRD 未起)
    - 路径写错(应该警告)

    draft:true 的 req 降级为静默。
    """
    warnings = []
    docs_dir = project_dir / "文档库"
    for e in entries:
        if e["entry_type"] != "req":
            continue
        if e["fm"].get("draft", "false") == "true":
            continue
        artifacts = e["fm"].get("artifacts", [])
        if isinstance(artifacts, str):
            artifacts = [artifacts]
        if not artifacts:
            continue
        for art_path in artifacts:
            if not art_path:
                continue
            # artifacts 路径相对 文档库/
            full_path = docs_dir / art_path
            if not full_path.exists():
                warnings.append(
                    f"[{project_name}] req artifacts 路径不存在: {e['entry_id']}\n"
                    f"  artifacts: '{art_path}'\n"
                    f"  期望位置: {full_path}\n"
                    f"  文件: {e['file']}"
                )
    return warnings

def check_archived_pointer(entries, project_name):
    """校验"已作废(误)→XXX" 状态指向的编号是否存在。仅警告。

    作废指向应是同项目内的有效编号。指向不存在通常是:
    - 写错了指向编号
    - 指向的条目还没建(前向引用)

    draft:true 降级为静默。

    例外:已晋升→GKB-XXXX 不校验(GKB 在 workspace 级 _共享/ 下,
    项目内通常找不到,见写入协议 §12.4)。
    """
    warnings = []
    all_ids = {e["entry_id"] for e in entries}
    for e in entries:
        status = e["fm"].get("status", "")
        if e["fm"].get("draft", "false") == "true":
            continue
        # 匹配 "已作废(误)→XXX-XXXX" 或 "已推翻→XXX-XXXX" 或 "已晋升→GKB-XXXX"
        m = re.search(r"→\s*([A-Z]+-\d{4})", status)
        if not m:
            continue
        target = m.group(1)
        # GKB 指向跳过(workspace 级,项目内不校验,见写入协议 §12.4)
        if target.startswith("GKB-"):
            continue
        if target not in all_ids:
            warnings.append(
                f"[{project_name}] 作废指向悬空: {e['entry_id']}\n"
                f"  status: '{status}'\n"
                f"  指向的 {target} 不存在\n"
                f"  文件: {e['file']}"
            )
    return warnings

# ========== 主入口 ==========

def check_project(project_dir, project_name=None):
    """校验单个项目。返回 (errors, warnings)。"""
    if project_name is None:
        project_name = os.path.basename(project_dir)
    errors = []
    warnings = []

    entries = find_entries(project_dir)
    if not entries:
        return errors, warnings

    # 硬阻断校验
    errors += check_unique_ids(entries, project_name)
    req_err, req_warn = check_required_fields(entries, project_name)
    errors += req_err
    warnings += req_warn
    type_err, type_warn = check_type_fields(entries, project_name)
    errors += type_err
    warnings += type_warn
    errors += check_status_enum(entries, project_name)
    errors += check_date_format(entries, project_name)
    errors += check_file_location(entries, project_name, project_dir)
    errors += check_doc_files(project_dir, project_name)
    dangling_err, dangling_warn = check_dangling_refs(entries, project_name)
    errors += dangling_err
    warnings += dangling_warn
    draft_err, draft_warn = check_draft_aging(entries, project_name)
    errors += draft_err
    warnings += draft_warn

    # 警告级校验
    warnings += check_continuity(entries, project_name)
    warnings += check_sorting(entries, project_name)
    # P3 新增:ref/artifacts/作废指向 悬空校验(警告级)
    all_ids = {e["entry_id"] for e in entries}
    warnings += check_dangling_doc_refs(Path(project_dir), project_name, all_ids)
    warnings += check_artifacts_path(entries, Path(project_dir), project_name)
    warnings += check_archived_pointer(entries, project_name)

    return errors, warnings

def main():
    projects_dir = WORKSPACE_ROOT / "项目"
    target = sys.argv[1] if len(sys.argv) > 1 else None

    if target:
        # 单项目模式
        target_path = Path(target)
        if not target_path.is_absolute():
            target_path = WORKSPACE_ROOT / target
        if not target_path.exists():
            print(f"错误: 路径不存在: {target_path}")
            return 2
        projects = [(target_path.name, target_path)]
    else:
        # 扫描所有项目
        if not projects_dir.exists():
            print(f"错误: 项目目录不存在: {projects_dir}")
            return 2
        projects = [(d.name, d) for d in projects_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        # 加上 workspace 级 GKB(全局知识库,在 _共享/知识库/ 下)
        gkb_dir = WORKSPACE_ROOT / "_共享" / "知识库"
        if gkb_dir.exists():
            projects.append(("_共享(全局知识库)", gkb_dir))

    all_errors = []
    all_warnings = []

    for name, pdir in projects:
        print(f"\n=== 校验项目: {name} ===")
        errs, warns = check_project(str(pdir), name)
        if errs:
            print(f"  ❌ {len(errs)} 个错误(硬阻断):")
            for e in errs:
                print(f"     - {e}")
        if warns:
            print(f"  ⚠️  {len(warns)} 个警告:")
            for w in warns:
                print(f"     - {w}")
        if not errs and not warns:
            print(f"  ✅ 通过")
        all_errors += errs
        all_warnings += warns

    print(f"\n=== 汇总 ===")
    print(f"  错误: {len(all_errors)}")
    print(f"  警告: {len(all_warnings)}")

    return 1 if all_errors else 0

if __name__ == "__main__":
    sys.exit(main())
