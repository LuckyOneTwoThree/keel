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


# ========== check_type_fields (RSK level) ==========

def test_rsk_level_valid():
    """RSK level 合法值通过"""
    entries = [
        {"entry_type": "rsk", "fm": {"status": "开放", "level": "高"}, "entry_id": "RSK-0001", "file": "a"},
        {"entry_type": "rsk", "fm": {"status": "开放", "level": "中"}, "entry_id": "RSK-0002", "file": "b"},
        {"entry_type": "rsk", "fm": {"status": "开放", "level": "低"}, "entry_id": "RSK-0003", "file": "c"},
    ]
    assert check_type_fields(entries, "TEST") == []


def test_rsk_level_missing():
    """RSK level 缺失报错"""
    entries = [
        {"entry_type": "rsk", "fm": {"status": "开放"}, "entry_id": "RSK-0001", "file": "a"},
    ]
    errs = check_type_fields(entries, "TEST")
    assert len(errs) == 1
    assert "level" in errs[0]


def test_rsk_level_invalid():
    """RSK level 非法值报错"""
    entries = [
        {"entry_type": "rsk", "fm": {"status": "开放", "level": "严重"}, "entry_id": "RSK-0001", "file": "a"},
    ]
    errs = check_type_fields(entries, "TEST")
    assert len(errs) == 1
    assert "严重" in errs[0]


def test_rsk_archived_exempt():
    """作废状态 RSK 豁免 level 校验"""
    entries = [
        {"entry_type": "rsk", "fm": {"status": "已作废(PM拒绝)"}, "entry_id": "RSK-0001", "file": "a"},
    ]
    assert check_type_fields(entries, "TEST") == []


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
