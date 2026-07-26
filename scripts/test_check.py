#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check.py 单元测试
用法: python -m pytest scripts/test_check.py -v
或:   python scripts/test_check.py  (直接跑,无需 pytest)
"""
import sys
import os
import tempfile
from pathlib import Path

# 让 test 能 import check
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check import (
    parse_frontmatter, check_unique_ids, check_status_enum,
    check_dangling_refs, check_type_fields, find_entries,
    check_file_location, check_doc_files, DOC_SUBTYPE,
)


# ========== parse_frontmatter ==========

def test_parse_inline_list():
    """内联列表 [a, b] 正确解析"""
    content = "---\nid: REQ-0001\nrelated: [A, B]\n---\nbody"
    fm, body = parse_frontmatter(content)
    assert fm["id"] == "REQ-0001"
    assert fm["related"] == ["A", "B"]


def test_parse_block_list():
    """block 列表(缩进 -)正确解析"""
    content = "---\nid: REQ-0001\nrelated:\n- A\n- B\n---\nbody"
    fm, body = parse_frontmatter(content)
    assert fm["id"] == "REQ-0001"
    assert fm["related"] == ["A", "B"]


def test_parse_bool_normalization():
    """True/yes/false/no 归一化"""
    content = "---\ndraft: true\nlocked: yes\narchived: false\nhidden: no\n---\n"
    fm, _ = parse_frontmatter(content)
    assert fm["draft"] == "true"
    assert fm["locked"] == "true"
    assert fm["archived"] == "false"
    assert fm["hidden"] == "false"


def test_parse_no_frontmatter():
    """无 frontmatter 返回 (None, content)"""
    content = "# 标题\n正文"
    fm, body = parse_frontmatter(content)
    assert fm is None
    assert body == content


# ========== check_unique_ids ==========

def test_unique_ids_pass():
    """无重复编号通过"""
    entries = [
        {"entry_id": "REQ-0001", "file": "a.md"},
        {"entry_id": "REQ-0002", "file": "b.md"},
    ]
    assert check_unique_ids(entries, "TEST") == []


def test_unique_ids_dup():
    """重复编号报错"""
    entries = [
        {"entry_id": "REQ-0001", "file": "a.md"},
        {"entry_id": "REQ-0001", "file": "b.md"},
    ]
    errs = check_unique_ids(entries, "TEST")
    assert len(errs) == 1
    assert "REQ-0001" in errs[0]


# ========== check_status_enum ==========

def test_status_enum_valid():
    """合法状态通过"""
    entries = [
        {"entry_type": "req", "fm": {"status": "待评审"}, "entry_id": "REQ-0001", "file": "a"},
        {"entry_type": "dec", "fm": {"status": "生效"}, "entry_id": "DEC-0001", "file": "b"},
    ]
    assert check_status_enum(entries, "TEST") == []


def test_status_enum_invalid():
    """非法状态报错"""
    entries = [
        {"entry_type": "req", "fm": {"status": "定稿"}, "entry_id": "REQ-0001", "file": "a"},
    ]
    errs = check_status_enum(entries, "TEST")
    assert len(errs) == 1
    assert "定稿" in errs[0]


def test_status_enum_archived_exempt():
    """已作废(误)→ 前缀豁免"""
    entries = [
        {"entry_type": "dec", "fm": {"status": "已作废(误)→DEC-0002"}, "entry_id": "DEC-0001", "file": "a"},
    ]
    assert check_status_enum(entries, "TEST") == []


# ========== check_dangling_refs ==========

def test_dangling_ref_block():
    """非 draft 条目悬空引用 → 硬阻断"""
    entries = [
        {"entry_id": "REQ-0001", "fm": {"draft": "false", "related": ["DEC-0099"]}, "file": "a"},
    ]
    errs, warns = check_dangling_refs(entries, "TEST")
    assert len(errs) == 1
    assert len(warns) == 0


def test_dangling_ref_draft_warn():
    """draft 条目悬空引用 → 仅警告"""
    entries = [
        {"entry_id": "REQ-0001", "fm": {"draft": "true", "related": ["DEC-0099"]}, "file": "a"},
    ]
    errs, warns = check_dangling_refs(entries, "TEST")
    assert len(errs) == 0
    assert len(warns) == 1


def test_dangling_ref_cross_project_skip():
    """跨项目引用(@)不校验"""
    entries = [
        {"entry_id": "REQ-0001", "fm": {"draft": "false", "related": ["REQ-0001@PROJ-其他"]}, "file": "a"},
    ]
    errs, warns = check_dangling_refs(entries, "TEST")
    assert len(errs) == 0


# ========== check_type_fields (RSK level / draft 宽松) ==========

def test_rsk_level_valid():
    """RSK level 合法值 + review_due 齐全 通过"""
    entries = [
        {"entry_type": "rsk", "fm": {"status": "开放", "level": "高", "review_due": "2026-08-25"}, "entry_id": "RSK-0001", "file": "a"},
        {"entry_type": "rsk", "fm": {"status": "开放", "level": "中", "review_due": "2026-08-25"}, "entry_id": "RSK-0002", "file": "b"},
        {"entry_type": "rsk", "fm": {"status": "开放", "level": "低", "review_due": "2026-08-25"}, "entry_id": "RSK-0003", "file": "c"},
    ]
    errs, warns = check_type_fields(entries, "TEST")
    assert errs == [] and warns == []


def test_rsk_level_missing():
    """RSK level 缺失(draft:false)→ 硬阻断"""
    entries = [
        {"entry_type": "rsk", "fm": {"status": "开放", "review_due": "2026-08-25", "draft": "false"}, "entry_id": "RSK-0001", "file": "a"},
    ]
    errs, warns = check_type_fields(entries, "TEST")
    assert len(errs) == 1
    assert len(warns) == 0
    assert "level" in errs[0]


def test_rsk_review_due_missing():
    """RSK review_due 缺失(draft:false)→ 硬阻断"""
    entries = [
        {"entry_type": "rsk", "fm": {"status": "开放", "level": "高", "draft": "false"}, "entry_id": "RSK-0001", "file": "a"},
    ]
    errs, warns = check_type_fields(entries, "TEST")
    assert len(errs) == 1
    assert "review_due" in errs[0]


def test_rsk_level_invalid():
    """RSK level 非法值报错(无论 draft)"""
    entries = [
        {"entry_type": "rsk", "fm": {"status": "开放", "level": "严重", "review_due": "2026-08-25", "draft": "true"}, "entry_id": "RSK-0001", "file": "a"},
    ]
    errs, warns = check_type_fields(entries, "TEST")
    assert len(errs) == 1
    assert "严重" in errs[0]


def test_rsk_archived_exempt():
    """作废状态 RSK 豁免 level/review_due 校验"""
    entries = [
        {"entry_type": "rsk", "fm": {"status": "已作废(PM拒绝)"}, "entry_id": "RSK-0001", "file": "a"},
    ]
    errs, warns = check_type_fields(entries, "TEST")
    assert errs == [] and warns == []


def test_dec_review_due_required():
    """DEC review_due 缺失(draft:false)→ 硬阻断"""
    entries = [
        {"entry_type": "dec", "fm": {"status": "生效", "draft": "false"}, "entry_id": "DEC-0001", "file": "a"},
    ]
    errs, warns = check_type_fields(entries, "TEST")
    assert len(errs) == 1
    assert "review_due" in errs[0]


def test_dep_expected_delivery_required():
    """DEP expected_delivery 缺失(draft:false)→ 硬阻断"""
    entries = [
        {"entry_type": "dep", "fm": {"status": "等待中", "draft": "false"}, "entry_id": "DEP-0001", "file": "a"},
    ]
    errs, warns = check_type_fields(entries, "TEST")
    assert len(errs) == 1
    assert "expected_delivery" in errs[0]


def test_type_fields_draft_warn():
    """draft:true 时类型必填字段缺失降级为警告(写入协议 §4)"""
    entries = [
        {"entry_type": "dep", "fm": {"status": "等待中", "draft": "true"}, "entry_id": "DEP-0001", "file": "a"},
        {"entry_type": "dec", "fm": {"status": "评估中", "draft": "true"}, "entry_id": "DEC-0001", "file": "b"},
        {"entry_type": "rsk", "fm": {"status": "开放", "draft": "true"}, "entry_id": "RSK-0001", "file": "c"},
    ]
    errs, warns = check_type_fields(entries, "TEST")
    assert len(errs) == 0
    # dep.expected_delivery(1) + dec.review_due(1) + rsk.level(1) + rsk.review_due(1) = 4
    assert len(warns) == 4


# ========== check_required_fields (draft 宽松) ==========

def test_required_fields_hard_id():
    """id/type/title/date 缺失即使 draft:true 也硬阻断"""
    from check import check_required_fields
    entries = [
        {"entry_type": "req", "fm": {"draft": "true", "status": "待评审"}, "entry_id": "", "file": "a"},
    ]
    errs, warns = check_required_fields(entries, "TEST")
    assert len(errs) >= 1  # id/type/title/date 缺失


def test_required_fields_draft_status_warn():
    """draft:true 时 status 缺失降级为警告"""
    from check import check_required_fields
    entries = [
        {"entry_type": "req", "fm": {"draft": "true", "id": "REQ-0001", "type": "req", "title": "测试", "date": "2026-07-25"}, "entry_id": "REQ-0001", "file": "a"},
    ]
    errs, warns = check_required_fields(entries, "TEST")
    assert len(errs) == 0
    assert len(warns) == 1
    assert "status" in warns[0]


def test_required_fields_no_status_block():
    """draft:false 时 status 缺失硬阻断"""
    from check import check_required_fields
    entries = [
        {"entry_type": "req", "fm": {"draft": "false", "id": "REQ-0001", "type": "req", "title": "测试", "date": "2026-07-25"}, "entry_id": "REQ-0001", "file": "a"},
    ]
    errs, warns = check_required_fields(entries, "TEST")
    assert len(errs) == 1
    assert "status" in errs[0]


# ========== check_file_location (新增) ==========

def test_file_location_rsk_correct(tmp_path):
    """RSK 在 项目管理/ 下通过"""
    proj = tmp_path / "PROJ-X"
    pm_dir = proj / "项目管理"
    pm_dir.mkdir(parents=True)
    fpath = pm_dir / "风险登记册.md"
    fpath.write_text("---\nid: RSK-0001\ntype: rsk\n---\n", encoding="utf-8")
    entries = [{"entry_id": "RSK-0001", "entry_type": "rsk", "file": str(fpath)}]
    assert check_file_location(entries, "TEST", str(proj)) == []


def test_file_location_rsk_wrong(tmp_path):
    """RSK 错放在 记忆/ 下报错"""
    proj = tmp_path / "PROJ-X"
    mem_dir = proj / "记忆"
    mem_dir.mkdir(parents=True)
    fpath = mem_dir / "风险登记册.md"
    fpath.write_text("---\nid: RSK-0001\ntype: rsk\n---\n", encoding="utf-8")
    entries = [{"entry_id": "RSK-0001", "entry_type": "rsk", "file": str(fpath)}]
    errs = check_file_location(entries, "TEST", str(proj))
    assert len(errs) == 1
    assert "RSK-0001" in errs[0]


def test_file_location_dep_wrong(tmp_path):
    """DEP 错放在 记忆/ 下报错"""
    proj = tmp_path / "PROJ-X"
    mem_dir = proj / "记忆"
    mem_dir.mkdir(parents=True)
    fpath = mem_dir / "依赖登记册.md"
    fpath.write_text("---\nid: DEP-0001\ntype: dep\n---\n", encoding="utf-8")
    entries = [{"entry_id": "DEP-0001", "entry_type": "dep", "file": str(fpath)}]
    errs = check_file_location(entries, "TEST", str(proj))
    assert len(errs) == 1
    assert "DEP-0001" in errs[0]


# ========== check_doc_files (新增) ==========

def test_doc_files_valid_subtype(tmp_path):
    """doc 文件 subtype 合法通过"""
    f = tmp_path / "REQ-0001-PRD.md"
    f.write_text(
        "---\ntype: doc\nsubtype: prd\ntitle: 测试\ndate: 2026-07-25\n---\n# 标题\n",
        encoding="utf-8"
    )
    assert check_doc_files(str(tmp_path), "TEST") == []


def test_doc_files_missing_subtype(tmp_path):
    """doc 文件缺 subtype 报错"""
    f = tmp_path / "REQ-0001-PRD.md"
    f.write_text(
        "---\ntype: doc\ntitle: 测试\ndate: 2026-07-25\n---\n# 标题\n",
        encoding="utf-8"
    )
    errs = check_doc_files(str(tmp_path), "TEST")
    assert len(errs) == 1
    assert "subtype" in errs[0]


def test_doc_files_invalid_subtype(tmp_path):
    """doc 文件 subtype 非法报错"""
    f = tmp_path / "REQ-0001-PRD.md"
    f.write_text(
        "---\ntype: doc\nsubtype: unknown\ntitle: 测试\ndate: 2026-07-25\n---\n# 标题\n",
        encoding="utf-8"
    )
    errs = check_doc_files(str(tmp_path), "TEST")
    assert len(errs) == 1
    assert "unknown" in errs[0]


def test_doc_files_skips_non_doc(tmp_path):
    """非 doc 文件(如 INDEX,type: index)不被当 doc 校验"""
    f = tmp_path / "INDEX.md"
    f.write_text(
        "---\nderived: true\ntype: index\ntitle: 索引\n---\n# INDEX\n",
        encoding="utf-8"
    )
    assert check_doc_files(str(tmp_path), "TEST") == []


def test_doc_files_derived_doc_still_checked(tmp_path):
    """doc 文件(即使误带 derived:true)仍被 subtype 校验(P1-3 修法)"""
    f = tmp_path / "周报.md"
    f.write_text(
        "---\nderived: true\ntype: doc\nsubtype: bad_subtype\ntitle: 周报\n---\n# 标题\n",
        encoding="utf-8"
    )
    errs = check_doc_files(str(tmp_path), "TEST")
    assert len(errs) == 1
    assert "bad_subtype" in errs[0]


def test_doc_files_skips_template(tmp_path):
    """_模板.md 豁免 doc 校验"""
    f = tmp_path / "_模板.md"
    f.write_text(
        "---\ntype: doc\nsubtype: prd\n---\n# 模板\n",
        encoding="utf-8"
    )
    assert check_doc_files(str(tmp_path), "TEST") == []


# ========== find_entries (集成) ==========

def test_find_entries_skips_derived(tmp_path):
    """派生文件(derived: true)不被扫描"""
    f = tmp_path / "现状.md"
    f.write_text("---\nderived: true\n---\n# 现状\n", encoding="utf-8")
    entries = find_entries(tmp_path)
    assert len(entries) == 0


def test_find_entries_skips_template(tmp_path):
    """_模板.md 不被扫描"""
    f = tmp_path / "_模板.md"
    f.write_text("---\nid: REQ-0001\ntype: req\n---\n", encoding="utf-8")
    entries = find_entries(tmp_path)
    assert len(entries) == 0


def test_find_entries_skips_code_block(tmp_path):
    """代码块里的 frontmatter 不被误解析"""
    f = tmp_path / "doc.md"
    f.write_text(
        "# doc\n"
        "```yaml\n"
        "---\nid: FAKE-0001\ntype: req\n---\n"
        "```\n",
        encoding="utf-8"
    )
    entries = find_entries(tmp_path)
    assert len(entries) == 0


# ========== check_dangling_doc_refs (P3 新增) ==========

def test_doc_ref_exists_pass(tmp_path):
    """doc ref 指向存在的 REQ 通过"""
    from check import check_dangling_doc_refs
    f = tmp_path / "REQ-0001-PRD.md"
    f.write_text(
        "---\ntype: doc\nsubtype: prd\nref: REQ-0001\ndraft: false\n---\n# 标题\n",
        encoding="utf-8"
    )
    warns = check_dangling_doc_refs(tmp_path, "TEST", {"REQ-0001"})
    assert warns == []


def test_doc_ref_dangling_warn(tmp_path):
    """doc ref 指向不存在的 REQ 警告"""
    from check import check_dangling_doc_refs
    f = tmp_path / "REQ-0001-PRD.md"
    f.write_text(
        "---\ntype: doc\nsubtype: prd\nref: REQ-0099\ndraft: false\n---\n# 标题\n",
        encoding="utf-8"
    )
    warns = check_dangling_doc_refs(tmp_path, "TEST", {"REQ-0001"})
    assert len(warns) == 1
    assert "REQ-0099" in warns[0]


def test_doc_ref_draft_silent(tmp_path):
    """draft:true 的 doc ref 悬空静默(草稿期允许前向引用)"""
    from check import check_dangling_doc_refs
    f = tmp_path / "REQ-0001-PRD.md"
    f.write_text(
        "---\ntype: doc\nsubtype: prd\nref: REQ-0099\ndraft: true\n---\n# 标题\n",
        encoding="utf-8"
    )
    warns = check_dangling_doc_refs(tmp_path, "TEST", {"REQ-0001"})
    assert warns == []


def test_doc_ref_report_no_ref_ok(tmp_path):
    """report 子类型无 ref 合法(周报不绑特定 REQ)"""
    from check import check_dangling_doc_refs
    f = tmp_path / "2026-07-25-周报.md"
    f.write_text(
        "---\ntype: doc\nsubtype: report\ndraft: false\n---\n# 周报\n",
        encoding="utf-8"
    )
    warns = check_dangling_doc_refs(tmp_path, "TEST", {"REQ-0001"})
    assert warns == []


# ========== check_artifacts_path (P3 新增) ==========

def test_artifacts_path_exists_pass(tmp_path):
    """req artifacts 路径存在通过"""
    from check import check_artifacts_path
    docs = tmp_path / "文档库"
    (docs / "01-需求").mkdir(parents=True)
    (docs / "01-需求" / "REQ-0001-PRD.md").write_text("# PRD", encoding="utf-8")
    entries = [
        {"entry_type": "req", "fm": {"draft": "false", "artifacts": ["01-需求/REQ-0001-PRD.md"]},
         "entry_id": "REQ-0001", "file": "a"},
    ]
    warns = check_artifacts_path(entries, tmp_path, "TEST")
    assert warns == []


def test_artifacts_path_missing_warn(tmp_path):
    """req artifacts 路径不存在警告"""
    from check import check_artifacts_path
    entries = [
        {"entry_type": "req", "fm": {"draft": "false", "artifacts": ["01-需求/REQ-0099-PRD.md"]},
         "entry_id": "REQ-0001", "file": "a"},
    ]
    warns = check_artifacts_path(entries, tmp_path, "TEST")
    assert len(warns) == 1
    assert "REQ-0099-PRD.md" in warns[0]


def test_artifacts_path_draft_silent(tmp_path):
    """draft:true 的 req artifacts 路径不存在静默"""
    from check import check_artifacts_path
    entries = [
        {"entry_type": "req", "fm": {"draft": "true", "artifacts": ["01-需求/REQ-0099-PRD.md"]},
         "entry_id": "REQ-0001", "file": "a"},
    ]
    warns = check_artifacts_path(entries, tmp_path, "TEST")
    assert warns == []


# ========== check_archived_pointer (P3 新增) ==========

def test_archived_pointer_exists_pass():
    """作废指向存在的编号通过"""
    from check import check_archived_pointer
    entries = [
        {"entry_id": "DEC-0001", "fm": {"status": "已作废(误)→DEC-0002", "draft": "false"}, "file": "a"},
        {"entry_id": "DEC-0002", "fm": {"status": "生效", "draft": "false"}, "file": "b"},
    ]
    warns = check_archived_pointer(entries, "TEST")
    assert warns == []


def test_archived_pointer_dangling_warn():
    """作废指向不存在的编号警告"""
    from check import check_archived_pointer
    entries = [
        {"entry_id": "DEC-0001", "fm": {"status": "已作废(误)→DEC-0099", "draft": "false"}, "file": "a"},
    ]
    warns = check_archived_pointer(entries, "TEST")
    assert len(warns) == 1
    assert "DEC-0099" in warns[0]


def test_archived_pointer_promoted_to_gkb_skip():
    """已晋升→GKB-XXXX 跳过(GKB 在 workspace 级,项目内不校验,见写入协议 §12.4)"""
    from check import check_archived_pointer
    entries = [
        {"entry_id": "KB-0001", "fm": {"status": "已晋升→GKB-0099", "draft": "false"}, "file": "a"},
    ]
    warns = check_archived_pointer(entries, "TEST")
    assert warns == []


def test_archived_pointer_draft_silent():
    """draft:true 的作废指向悬空静默"""
    from check import check_archived_pointer
    entries = [
        {"entry_id": "DEC-0001", "fm": {"status": "已作废(误)→DEC-0099", "draft": "true"}, "file": "a"},
    ]
    warns = check_archived_pointer(entries, "TEST")
    assert warns == []


def test_archived_pointer_no_arrow_skip():
    """普通状态(无 →)不被校验"""
    from check import check_archived_pointer
    entries = [
        {"entry_id": "DEC-0001", "fm": {"status": "生效", "draft": "false"}, "file": "a"},
    ]
    warns = check_archived_pointer(entries, "TEST")
    assert warns == []


# ========== check_doc_filename_subtype (P3-A 新增) ==========

def test_doc_filename_subtype_match_pass(tmp_path):
    """P3-A:doc 文件名含期望片段通过(如 subtype=prd + 文件名含 PRD)"""
    from check import check_doc_filename_subtype
    f = tmp_path / "REQ-0001-PRD.md"
    f.write_text(
        "---\ntype: doc\nsubtype: prd\n---\n# 标题\n", encoding="utf-8"
    )
    assert check_doc_filename_subtype(tmp_path, "TEST") == []


def test_doc_filename_subtype_mismatch_warn(tmp_path):
    """P3-A:doc 文件名不含期望片段警告(如 subtype=prd 但文件名不含 PRD)"""
    from check import check_doc_filename_subtype
    f = tmp_path / "REQ-0001-需求文档.md"  # 不含 PRD
    f.write_text(
        "---\ntype: doc\nsubtype: prd\n---\n# 标题\n", encoding="utf-8"
    )
    warns = check_doc_filename_subtype(tmp_path, "TEST")
    assert len(warns) == 1
    assert "PRD" in warns[0]


def test_doc_filename_subtype_research_pass(tmp_path):
    """P3-A:subtype=research + 文件名含"调研"通过"""
    from check import check_doc_filename_subtype
    f = tmp_path / "REQ-0001-调研.md"
    f.write_text(
        "---\ntype: doc\nsubtype: research\n---\n# 标题\n", encoding="utf-8"
    )
    assert check_doc_filename_subtype(tmp_path, "TEST") == []


def test_doc_filename_subtype_report_skip(tmp_path):
    """P3-A:report 子类型不校验文件名(用日期命名)"""
    from check import check_doc_filename_subtype
    f = tmp_path / "2026-W30-周报.md"
    f.write_text(
        "---\ntype: doc\nsubtype: report\n---\n# 周报\n", encoding="utf-8"
    )
    assert check_doc_filename_subtype(tmp_path, "TEST") == []


# ========== check_doc_location_subtype (P3-B 新增) ==========

def test_doc_location_subtype_match_pass(tmp_path):
    """P3-B:subtype=prd 在 01-需求/ 下通过"""
    from check import check_doc_location_subtype
    docs = tmp_path / "文档库" / "01-需求"
    docs.mkdir(parents=True)
    (docs / "REQ-0001-PRD.md").write_text(
        "---\ntype: doc\nsubtype: prd\n---\n# 标题\n", encoding="utf-8"
    )
    assert check_doc_location_subtype(tmp_path, "TEST") == []


def test_doc_location_subtype_mismatch_warn(tmp_path):
    """P3-B:subtype=prd 但在 03-方案/ 下警告"""
    from check import check_doc_location_subtype
    docs = tmp_path / "文档库" / "03-方案"
    docs.mkdir(parents=True)
    (docs / "REQ-0001-PRD.md").write_text(
        "---\ntype: doc\nsubtype: prd\n---\n# 标题\n", encoding="utf-8"
    )
    warns = check_doc_location_subtype(tmp_path, "TEST")
    assert len(warns) == 1
    assert "01-需求" in warns[0]


def test_doc_location_subtype_acceptance_pass(tmp_path):
    """P3-B:subtype=acceptance 在 05-验收/ 下通过"""
    from check import check_doc_location_subtype
    docs = tmp_path / "文档库" / "05-验收"
    docs.mkdir(parents=True)
    (docs / "REQ-0001-验收.md").write_text(
        "---\ntype: doc\nsubtype: acceptance\n---\n# 标题\n", encoding="utf-8"
    )
    assert check_doc_location_subtype(tmp_path, "TEST") == []


# ========== check_doc_ref_filename_consistency (P3-C 新增) ==========

def test_doc_ref_filename_match_pass(tmp_path):
    """P3-C:doc ref 编号与文件名编号一致通过(REQ-0001-PRD.md + ref: REQ-0001)"""
    from check import check_doc_ref_filename_consistency
    f = tmp_path / "REQ-0001-PRD.md"
    f.write_text(
        "---\ntype: doc\nsubtype: prd\nref: REQ-0001\n---\n# 标题\n", encoding="utf-8"
    )
    assert check_doc_ref_filename_consistency(tmp_path, "TEST") == []


def test_doc_ref_filename_mismatch_warn(tmp_path):
    """P3-C:doc ref 编号与文件名编号不一致警告(REQ-0002-PRD.md 但 ref: REQ-0001)"""
    from check import check_doc_ref_filename_consistency
    f = tmp_path / "REQ-0002-PRD.md"  # 文件名编号 0002
    f.write_text(
        "---\ntype: doc\nsubtype: prd\nref: REQ-0001\n---\n# 标题\n", encoding="utf-8"
    )
    warns = check_doc_ref_filename_consistency(tmp_path, "TEST")
    assert len(warns) == 1
    assert "0001" in warns[0]
    assert "0002" in warns[0]


def test_doc_ref_filename_no_ref_skip(tmp_path):
    """P3-C:无 ref 的 doc 文件不校验(report 子类型)"""
    from check import check_doc_ref_filename_consistency
    f = tmp_path / "2026-W30-周报.md"
    f.write_text(
        "---\ntype: doc\nsubtype: report\n---\n# 周报\n", encoding="utf-8"
    )
    assert check_doc_ref_filename_consistency(tmp_path, "TEST") == []


def test_doc_ref_filename_no_num_in_name_skip(tmp_path):
    """P3-C:文件名无 4 位编号时跳过(中文命名如 调研.md)"""
    from check import check_doc_ref_filename_consistency
    f = tmp_path / "调研.md"  # 无 4 位编号
    f.write_text(
        "---\ntype: doc\nsubtype: research\nref: REQ-0001\n---\n# 标题\n", encoding="utf-8"
    )
    assert check_doc_ref_filename_consistency(tmp_path, "TEST") == []


# ========== 兼容直接运行(无 pytest) ==========

if __name__ == "__main__":
    # 简单跑法:收集所有 test_ 函数,手动调用
    import inspect
    mod = sys.modules[__name__]
    tests = [
        (name, fn) for name, fn in inspect.getmembers(mod, inspect.isfunction)
        if name.startswith("test_")
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        # 检查是否需要 tmp_path
        sig = inspect.signature(fn)
        if "tmp_path" in sig.parameters:
            # 跳过需要 tmp_path 的(无 pytest 时手动建临时目录)
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                try:
                    fn(tmp_path=Path(td))
                    passed += 1
                except Exception as e:
                    print(f"FAIL {name}: {e}")
                    failed += 1
        else:
            try:
                fn()
                passed += 1
            except Exception as e:
                print(f"FAIL {name}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
