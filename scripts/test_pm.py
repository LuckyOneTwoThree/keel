#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pm.py 单元测试
用法: python -m pytest scripts/test_pm.py -v
或:   python scripts/test_pm.py  (直接跑,无需 pytest)
"""
import sys
import os
import tempfile
from pathlib import Path

# 让 test 能 import pm
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pm import replace_draft_flag, scan_max_id


# ========== replace_draft_flag ==========

def test_replace_draft_flag_single():
    """单条目文件:正确替换 draft: true → false"""
    content = (
        "---\n"
        "id: REQ-0001\n"
        "draft: true\n"
        "---\n"
        "正文"
    )
    new_content, replaced = replace_draft_flag(content, "REQ-0001")
    assert replaced is True
    assert "draft: false" in new_content
    assert "draft: true" not in new_content


def test_replace_draft_flag_multi():
    """多条目文件:只替换 target_id 所在块的 draft,不误改其他条目"""
    content = (
        "---\n"
        "id: REQ-0001\n"
        "draft: false\n"
        "---\n"
        "条目1\n"
        "\n---\n"
        "---\n"
        "id: REQ-0002\n"
        "draft: true\n"
        "---\n"
        "条目2"
    )
    # 定稿 REQ-0002
    new_content, replaced = replace_draft_flag(content, "REQ-0002")
    assert replaced is True
    # REQ-0002 的 draft 应改为 false
    # REQ-0001 的 draft 应保持 false(不变)
    assert new_content.count("draft: true") == 0
    assert new_content.count("draft: false") == 2


def test_replace_draft_flag_not_found():
    """target_id 不存在时返回 (content, False)"""
    content = (
        "---\n"
        "id: REQ-0001\n"
        "draft: true\n"
        "---\n"
        "正文"
    )
    new_content, replaced = replace_draft_flag(content, "REQ-9999")
    assert replaced is False
    assert new_content == content


def test_replace_draft_flag_no_draft_field():
    """target_id 存在但无 draft 字段时返回 (content, False)"""
    content = (
        "---\n"
        "id: REQ-0001\n"
        "status: 待评审\n"
        "---\n"
        "正文"
    )
    new_content, replaced = replace_draft_flag(content, "REQ-0001")
    assert replaced is False


# ========== scan_max_id ==========

def test_scan_max_id_basic(tmp_path):
    """正确扫描最大编号"""
    (tmp_path / "a.md").write_text(
        "---\nid: REQ-0003\n---\n", encoding="utf-8"
    )
    (tmp_path / "b.md").write_text(
        "---\nid: REQ-0007\n---\n", encoding="utf-8"
    )
    (tmp_path / "c.md").write_text(
        "---\nid: REQ-0001\n---\n", encoding="utf-8"
    )
    assert scan_max_id(tmp_path, "REQ") == 7


def test_scan_max_id_empty(tmp_path):
    """空目录返回 0"""
    assert scan_max_id(tmp_path, "REQ") == 0


def test_scan_max_id_skips_draft(tmp_path):
    """.draft/ 目录不被扫描"""
    (tmp_path / "a.md").write_text(
        "---\nid: REQ-0005\n---\n", encoding="utf-8"
    )
    draft_dir = tmp_path / ".draft"
    draft_dir.mkdir()
    (draft_dir / "draft.md").write_text(
        "---\nid: REQ-0099\n---\n", encoding="utf-8"
    )
    # .draft/ 里的 REQ-0099 不应被扫到
    assert scan_max_id(tmp_path, "REQ") == 5


def test_scan_max_id_skips_code_block(tmp_path):
    """代码块里的编号不被扫描"""
    (tmp_path / "a.md").write_text(
        "---\nid: REQ-0001\n---\n"
        "```yaml\n"
        "id: REQ-9999\n"
        "```\n",
        encoding="utf-8"
    )
    assert scan_max_id(tmp_path, "REQ") == 1


def test_scan_max_id_multiple_prefixes(tmp_path):
    """多前缀共存时只扫指定前缀"""
    (tmp_path / "a.md").write_text(
        "---\nid: REQ-0001\n---\n", encoding="utf-8"
    )
    (tmp_path / "b.md").write_text(
        "---\nid: DEC-0005\n---\n", encoding="utf-8"
    )
    assert scan_max_id(tmp_path, "REQ") == 1
    assert scan_max_id(tmp_path, "DEC") == 5


# ========== 兼容直接运行(无 pytest) ==========

if __name__ == "__main__":
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
        if "tmp_path" in sig.parameters:
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
