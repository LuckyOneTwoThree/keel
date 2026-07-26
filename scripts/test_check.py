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


def test_file_location_req_correct(tmp_path):
    """P1-B:REQ 条目在 项目管理/ 下通过"""
    proj = tmp_path / "PROJ-X"
    pm_dir = proj / "项目管理"
    pm_dir.mkdir(parents=True)
    fpath = pm_dir / "需求登记册.md"
    fpath.write_text("---\nid: REQ-0001\ntype: req\n---\n", encoding="utf-8")
    entries = [{"entry_id": "REQ-0001", "entry_type": "req", "file": str(fpath)}]
    assert check_file_location(entries, "TEST", str(proj)) == []


def test_file_location_req_wrong(tmp_path):
    """P1-B:REQ 条目错放在 记忆/ 下报错"""
    proj = tmp_path / "PROJ-X"
    mem_dir = proj / "记忆"
    mem_dir.mkdir(parents=True)
    fpath = mem_dir / "需求登记册.md"
    fpath.write_text("---\nid: REQ-0001\ntype: req\n---\n", encoding="utf-8")
    entries = [{"entry_id": "REQ-0001", "entry_type": "req", "file": str(fpath)}]
    errs = check_file_location(entries, "TEST", str(proj))
    assert len(errs) == 1
    assert "REQ-0001" in errs[0]


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


# ========== P2-13/P2-14:全 subtype 夹具补全 ==========

# 参数化:5 种非 report subtype × filename/location 一致性
# (report 子类型不校验文件名/位置,见 SUBTYPE_NAMING)
SUBTYPE_FIXTURES = [
    # (subtype, expected_filename_fragment, expected_dir_name)
    ("prd",        "PRD",  "01-需求"),
    ("research",   "调研", "02-调研"),
    ("plan",       "方案", "03-方案"),
    ("review",     "评审", "04-评审"),
    ("acceptance", "验收", "05-验收"),
]


def test_doc_filename_subtype_all_match(tmp_path):
    """P2-13:全部 5 种非 report subtype 的文件名片段匹配通过(参数化夹具)"""
    from check import check_doc_filename_subtype
    for subtype, fragment, _ in SUBTYPE_FIXTURES:
        d = tmp_path / subtype
        d.mkdir()
        # 文件名含期望片段(如 REQ-0001-PRD.md / REQ-0001-调研.md)
        (d / f"REQ-0001-{fragment}.md").write_text(
            f"---\ntype: doc\nsubtype: {subtype}\n---\n# 标题\n", encoding="utf-8"
        )
    warns = check_doc_filename_subtype(tmp_path, "TEST")
    assert warns == [], f"应通过但报: {warns}"


def test_doc_filename_subtype_all_mismatch(tmp_path):
    """P2-13:全部 5 种 subtype 文件名缺片段时各产 1 条警告"""
    from check import check_doc_filename_subtype
    for subtype, fragment, _ in SUBTYPE_FIXTURES:
        d = tmp_path / subtype
        d.mkdir()
        # 文件名不含期望片段(用"文件.md"占位)
        (d / "REQ-0001-文件.md").write_text(
            f"---\ntype: doc\nsubtype: {subtype}\n---\n# 标题\n", encoding="utf-8"
        )
    warns = check_doc_filename_subtype(tmp_path, "TEST")
    assert len(warns) == 5
    # 每条警告应包含期望片段
    for _, fragment, _ in SUBTYPE_FIXTURES:
        assert any(fragment in w for w in warns), f"警告缺片段 '{fragment}'"


def test_doc_location_subtype_all_match(tmp_path):
    """P2-13:全部 5 种 subtype 在期望目录下通过(参数化夹具)"""
    from check import check_doc_location_subtype
    for subtype, fragment, expected_dir in SUBTYPE_FIXTURES:
        # 在 文档库/<expected_dir>/ 下放文件
        d = tmp_path / "文档库" / expected_dir
        d.mkdir(parents=True)
        (d / f"REQ-0001-{fragment}.md").write_text(
            f"---\ntype: doc\nsubtype: {subtype}\n---\n# 标题\n", encoding="utf-8"
        )
    warns = check_doc_location_subtype(tmp_path, "TEST")
    assert warns == [], f"应通过但报: {warns}"


def test_doc_location_subtype_all_mismatch(tmp_path):
    """P2-13:全部 5 种 subtype 错放在 06-会议/ 下各产 1 条警告"""
    from check import check_doc_location_subtype
    wrong_dir = tmp_path / "文档库" / "06-会议"
    wrong_dir.mkdir(parents=True)
    for subtype, fragment, expected_dir in SUBTYPE_FIXTURES:
        (wrong_dir / f"REQ-0001-{fragment}.md").write_text(
            f"---\ntype: doc\nsubtype: {subtype}\n---\n# 标题\n", encoding="utf-8"
        )
    warns = check_doc_location_subtype(tmp_path, "TEST")
    assert len(warns) == 5
    # 每条警告应包含期望目录名
    for _, _, expected_dir in SUBTYPE_FIXTURES:
        assert any(expected_dir in w for w in warns), f"警告缺目录 '{expected_dir}'"


def test_doc_subtype_report_skips_filename_and_location(tmp_path):
    """P2-13:report subtype 同时豁免 filename + location 校验

    场景:周报文件名不带 PRD/调研/方案/评审/验收 任意片段,
    且不在 01-需求~/05-验收/ 任意目录,仍应通过。
    """
    from check import check_doc_filename_subtype, check_doc_location_subtype
    # report 在 文档库/07-报告/ 下,文件名仅日期+周报
    d = tmp_path / "文档库" / "07-报告"
    d.mkdir(parents=True)
    (d / "2026-07-25-周报.md").write_text(
        "---\ntype: doc\nsubtype: report\n---\n# 周报\n", encoding="utf-8"
    )
    assert check_doc_filename_subtype(tmp_path, "TEST") == []
    assert check_doc_location_subtype(tmp_path, "TEST") == []


# ========== P2-14:gen-index 单元测试 ==========

def test_gen_index_basic(tmp_path, monkeypatch):
    """P2-14:gen-index 扫描条目并按路由表顺序输出表格"""
    import pm

    # 构造最小项目结构(带 项目章程.md 让 find_project_dir 能识别)
    (tmp_path / "项目管理").mkdir()
    (tmp_path / "项目管理" / "项目章程.md").write_text(
        "---\nschema_version: '3.0'\n---\n# 章程\n", encoding="utf-8"
    )
    # 几个条目(乱序,验证排序)
    (tmp_path / "记忆").mkdir()
    (tmp_path / "记忆" / "决策记录.md").write_text(
        "---\ntype: dec_log\n---\n# 决策记录\n\n<!-- 在此追加条目 -->\n"
        "---\nid: DEC-0002\ntype: dec\ntitle: 决策二\ndate: 2026-07-26\nstatus: 生效\nrelated: []\n---\n### DEC-0002\n\n---\n"
        "---\nid: DEC-0001\ntype: dec\ntitle: 决策一\ndate: 2026-07-25\nstatus: 评估中\nrelated: []\n---\n### DEC-0001\n\n---\n",
        encoding="utf-8"
    )
    (tmp_path / "项目管理" / "需求登记册.md").write_text(
        "---\ntype: req_log\n---\n# 需求登记册\n\n<!-- 在此追加条目 -->\n"
        "---\nid: REQ-0001\ntype: req\ntitle: 需求一\ndate: 2026-07-25\nstatus: 待评审\nrelated: [DEC-0001]\n---\n### REQ-0001\n\n---\n",
        encoding="utf-8"
    )

    # monkeypatch 让 find_project_dir 返回 tmp_path
    monkeypatch.setattr(pm, "find_project_dir", lambda: tmp_path)
    rc = pm.cmd_gen_index([])
    assert rc == 0

    index_path = tmp_path / "INDEX.md"
    assert index_path.exists()
    content = index_path.read_text(encoding="utf-8")
    # 应含 frontmatter
    assert "derived: true" in content
    assert "type: index" in content
    # 应含全部 3 个条目
    assert "REQ-0001" in content
    assert "DEC-0001" in content
    assert "DEC-0002" in content
    # 排序:REQ 在 DEC 之前(路由表顺序),组内 id 升序(DEC-0001 < DEC-0002)
    req_pos = content.index("REQ-0001")
    dec1_pos = content.index("DEC-0001")
    dec2_pos = content.index("DEC-0002")
    assert req_pos < dec1_pos < dec2_pos
    # related 应展开为逗号分隔
    assert "DEC-0001" in content  # REQ-0001 的 related 已展开


def test_gen_index_skips_session_and_derived(tmp_path, monkeypatch):
    """P2-14:gen-index 跳过 session 类型 + 派生文件"""
    import pm

    (tmp_path / "项目管理").mkdir()
    (tmp_path / "项目管理" / "项目章程.md").write_text(
        "---\nschema_version: '3.0'\n---\n# 章程\n", encoding="utf-8"
    )
    # session 类型条目(应被跳过)
    (tmp_path / "记忆").mkdir()
    (tmp_path / "记忆" / "agent会话.md").write_text(
        "---\ntype: session_log\n---\n# agent会话\n\n"
        "---\nid: SESSION-2026-07-25-0001\ntype: session\ntitle: 测试会话\ndate: 2026-07-25\nstatus: 进行中\n---\n### SESSION\n",
        encoding="utf-8"
    )
    # 真实条目
    (tmp_path / "项目管理" / "需求登记册.md").write_text(
        "---\ntype: req_log\n---\n# 需求登记册\n\n<!-- 在此追加条目 -->\n"
        "---\nid: REQ-0001\ntype: req\ntitle: 需求一\ndate: 2026-07-25\nstatus: 待评审\nrelated: []\n---\n### REQ-0001\n",
        encoding="utf-8"
    )
    # 派生文件(应被跳过)
    (tmp_path / "现状.md").write_text(
        "---\nderived: true\ntype: 现状\n---\n# 现状\n| REQ-9999 | 假条目 | 2026-01-01 | ? | |\n",
        encoding="utf-8"
    )

    monkeypatch.setattr(pm, "find_project_dir", lambda: tmp_path)
    rc = pm.cmd_gen_index([])
    assert rc == 0
    content = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    # 应只含 REQ-0001,不含 SESSION-XXXX 也不含 REQ-9999
    assert "REQ-0001" in content
    assert "SESSION-" not in content
    assert "REQ-9999" not in content


def test_gen_index_empty_project(tmp_path, monkeypatch):
    """P2-14:空项目生成 INDEX 含"暂无条目"占位"""
    import pm
    (tmp_path / "项目管理").mkdir()
    (tmp_path / "项目管理" / "项目章程.md").write_text(
        "---\nschema_version: '3.0'\n---\n# 章程\n", encoding="utf-8"
    )
    monkeypatch.setattr(pm, "find_project_dir", lambda: tmp_path)
    rc = pm.cmd_gen_index([])
    assert rc == 0
    content = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert "暂无条目" in content


def test_gen_index_preserves_proj_id(tmp_path, monkeypatch):
    """P2-14:已有 INDEX.md 时保留 proj_id,不强制覆盖"""
    import pm
    (tmp_path / "项目管理").mkdir()
    (tmp_path / "项目管理" / "项目章程.md").write_text(
        "---\nschema_version: '3.0'\n---\n# 章程\n", encoding="utf-8"
    )
    # 既有 INDEX.md,proj_id 已被 PM 改过
    existing = (
        "---\nderived: true\ntype: index\ntitle: 跨类全景索引\ndate: 2026-01-01\n"
        "proj_id: PROJ-Custom-Name\n---\n\n# INDEX\n\n| 编号 | 标题 | 日期 | 状态 | 关联 |\n| --- | --- | --- | --- | --- |\n"
    )
    (tmp_path / "INDEX.md").write_text(existing, encoding="utf-8")

    monkeypatch.setattr(pm, "find_project_dir", lambda: tmp_path)
    rc = pm.cmd_gen_index([])
    assert rc == 0
    content = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    # 既有 proj_id 应被保留,不被覆盖为 tmp_path.name
    assert "PROJ-Custom-Name" in content


# ========== 兼容直接运行(无 pytest) ==========

class _FakeMonkeyPatch:
    """无 pytest 时,模拟 monkeypatch fixture 的最小实现(setattr/undo)。"""
    def __init__(self):
        self._undo = []
    def setattr(self, target, name, value):
        # 支持 setattr(obj, name, value) 和 setattr(target_str, name, value) 两种形式
        # 这里只实现前者(本测试文件用到的形式)
        old = getattr(target, name)
        self._undo.append((target, name, old))
        setattr(target, name, value)
    def undo(self):
        for target, name, old in reversed(self._undo):
            setattr(target, name, old)
        self._undo.clear()


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
        sig = inspect.signature(fn)
        needs_tmp = "tmp_path" in sig.parameters
        needs_mp = "monkeypatch" in sig.parameters
        if needs_tmp or needs_mp:
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                mp = _FakeMonkeyPatch()
                kwargs = {}
                if needs_tmp:
                    kwargs["tmp_path"] = Path(td)
                if needs_mp:
                    kwargs["monkeypatch"] = mp
                try:
                    fn(**kwargs)
                    passed += 1
                except Exception as e:
                    print(f"FAIL {name}: {e}")
                    failed += 1
                finally:
                    if needs_mp:
                        mp.undo()
        else:
            try:
                fn()
                passed += 1
            except Exception as e:
                print(f"FAIL {name}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
