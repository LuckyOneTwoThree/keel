#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pm.py 单元测试
用法: python -m pytest scripts/test_pm.py -v
或:   python scripts/test_pm.py  (直接跑,无需 pytest)
"""
import sys
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

# 让 test 能 import pm 和 check
SCRIPTS_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPTS_DIR.parent
TEMPLATE_DIR = WORKSPACE_ROOT / "_模板"
sys.path.insert(0, str(SCRIPTS_DIR))
import pm
import check
from pm import replace_draft_flag, scan_max_id, DEFAULT_STATUS, insert_entry_after_marker
from check import ALLOWED_STATUS


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


def test_scan_max_id_includes_draft_filenames(tmp_path):
    """P1-A 修复:.draft/ 下的草稿文件名编号被扫到,防连续 new-req 覆盖草稿。

    场景:已有 REQ-0005 草稿在 .draft/draft-req-0005-prd.md,
    再次 pm new-req 时新编号应为 0006,而非 0001(覆盖草稿)。
    """
    (tmp_path / "a.md").write_text(
        "---\nid: REQ-0003\n---\n", encoding="utf-8"
    )
    draft_dir = tmp_path / ".draft"
    draft_dir.mkdir()
    # 草稿文件名带 REQ-0005(P1-A 修复点:文件名编号应被扫到)
    (draft_dir / "draft-req-0005-prd.md").write_text(
        "---\nid: REQ-0005\ndraft: true\n---\n草稿正文", encoding="utf-8"
    )
    # 应扫到 5(文件名编号),不是 3(正文编号)
    assert scan_max_id(tmp_path, "REQ") == 5


def test_scan_max_id_draft_content_not_scanned(tmp_path):
    """P1-A 边界:.draft/ 下的草稿**正文**里的编号不被扫(防误扫引用)。

    场景:草稿正文里引用了 REQ-9999(尚未立的条目),
    该引用编号不应被误扫为最大编号(否则会跳号)。
    """
    (tmp_path / "a.md").write_text(
        "---\nid: REQ-0003\n---\n", encoding="utf-8"
    )
    draft_dir = tmp_path / ".draft"
    draft_dir.mkdir()
    # 草稿文件名无 REQ-XXXX 编号,但正文引用了 REQ-9999
    (draft_dir / "draft.md").write_text(
        "---\nid: REQ-0005\ndraft: true\n---\n相关: REQ-9999(未立条目)", encoding="utf-8"
    )
    # 应扫到 3(正文里 a.md 的 REQ-0003),不是 9999(草稿正文引用)
    assert scan_max_id(tmp_path, "REQ") == 3


# ========== insert_entry_after_marker(P1-1 修复) ==========

def test_insert_entry_with_marker():
    """P1-1:有 <!-- 在此追加条目 注释时,在注释行之后插入"""
    content = (
        "---\n"
        "type: req_log\n"
        "---\n"
        "# 需求登记册\n"
        "\n"
        "<!-- 在此追加条目 -->\n"
        "\n"
        "## 条目格式参考\n"
    )
    fm_text = "---\nid: REQ-0001\ndraft: true\n---"
    body = "\n### REQ-0001 — 2026-07-25\n标题\n\n---\n"
    new_content = insert_entry_after_marker(content, fm_text, body)
    # 新条目应插在注释行之后,"## 条目格式参考" 之前
    assert "在此追加条目 -->" in new_content
    assert "REQ-0001" in new_content
    # 注释在前,新条目在中,## 条目格式参考 在后
    marker_pos = new_content.index("在此追加条目 -->")
    entry_pos = new_content.index("REQ-0001")
    section_pos = new_content.index("## 条目格式参考")
    assert marker_pos < entry_pos < section_pos


def test_insert_entry_fallback_first_entry():
    """P1-1:无 marker 时 fallback 到第一个真实条目 FM 之前"""
    content = (
        "---\n"
        "type: req_log\n"
        "---\n"
        "# 需求登记册\n"
        "\n"
        "---\n"
        "id: REQ-0003\n"
        "type: req\n"
        "---\n"
        "### REQ-0003 — 2026-07-20\n"
        "已有条目\n"
    )
    fm_text = "---\nid: REQ-0004\ndraft: true\n---"
    body = "\n### REQ-0004 — 2026-07-25\n新条目\n\n---\n"
    new_content = insert_entry_after_marker(content, fm_text, body)
    # 新条目 REQ-0004 应在 REQ-0003 之前(最新在顶)
    req4_pos = new_content.index("id: REQ-0004")
    req3_pos = new_content.index("id: REQ-0003")
    assert req4_pos < req3_pos


def test_insert_entry_fallback_empty_file():
    """P1-1:无 marker 无现有条目时,追加到文件末尾"""
    content = (
        "---\n"
        "type: req_log\n"
        "---\n"
        "# 需求登记册\n"
    )
    fm_text = "---\nid: REQ-0001\ndraft: true\n---"
    body = "\n### REQ-0001 — 2026-07-25\n标题\n\n---\n"
    new_content = insert_entry_after_marker(content, fm_text, body)
    assert "REQ-0001" in new_content
    # 文件头 FM 应保持在前
    header_pos = new_content.index("type: req_log")
    entry_pos = new_content.index("id: REQ-0001")
    assert header_pos < entry_pos


# ========== DEFAULT_STATUS(P1-C 修复) ==========

def test_default_status_covers_all_types():
    """P1-C:DEFAULT_STATUS 覆盖全部 8 种条目类型"""
    expected_types = {"req", "prg", "dec", "com", "kb", "rsk", "dep", "gkb"}
    assert set(DEFAULT_STATUS.keys()) == expected_types


def test_default_status_all_valid():
    """P1-C:每种类型的默认 status 都在 check.py ALLOWED_STATUS 枚举里合法。

    旧实现 com/kb/gkb 默认"进行中"不在各自枚举,导致 pm check 硬阻断。
    """
    for entry_type, default_status in DEFAULT_STATUS.items():
        allowed = ALLOWED_STATUS.get(entry_type, set())
        assert default_status in allowed, (
            f"{entry_type} 默认 status '{default_status}' 不在 ALLOWED_STATUS {allowed} 里"
        )


# ========== P0 修法:PRD 是文档级条目,不是条目级 ==========

def test_is_prd_doc():
    """PRD 文件应被识别为文档级(type: doc + subtype: prd)。"""
    prd = "---\ntype: doc\nsubtype: prd\nref: REQ-0001\ndraft: true\n---\n\n正文\n"
    assert pm.is_prd_doc(prd) is True
    # 条目级文件(登记册里的 REQ 条目)不是 PRD doc
    req_entry = "---\nid: REQ-0001\ntype: req\ndraft: true\n---\n\n正文\n"
    assert pm.is_prd_doc(req_entry) is False
    # 代码块里的示例不应误判
    in_code = "---\ntype: kb\nid: KB-0001\n---\n\n```yaml\ntype: doc\nsubtype: prd\n```\n"
    assert pm.is_prd_doc(in_code) is False


def test_replace_draft_flag_ref_only():
    """P0 修法:文档级文件无 id,须按 ref 定位 frontmatter 块。

    默认(ref_only=False)按 id 定位,不应命中只带 ref 的 doc 文件——
    否则会把验收报告等同样 ref 指向该 REQ 的 doc 一并误翻。
    """
    content = "---\ntype: doc\nsubtype: prd\nref: REQ-0001\ndraft: true\n---\n\n正文\n"
    new, replaced = pm.replace_draft_flag(content, "REQ-0001", ref_only=True)
    assert replaced is True
    assert "draft: false" in new
    # 默认按 id 定位 → 文档级文件不命中
    _, replaced_by_id = pm.replace_draft_flag(content, "REQ-0001")
    assert replaced_by_id is False


def test_e2e_new_req_then_finalize_stays_committable(tmp_path):
    """E2E 回归:P0 —— new-req → finalize 闭环后项目必须仍然可提交。

    修复前该路径产出 `type: req` + `id: REQ-XXXX` 的 PRD,定稿搬到
    文档库/01-需求/ 后触发 2 个硬阻断:
      ① 编号重复(与需求登记册撞号) ② file_location 要求 req 必在 项目管理/ 下。
    此测试是当时唯一能抓住该逃逸的守卫(test_pm 原先只测 4 个辅助函数)。
    """
    proj = tmp_path / "PROJ-E2E"
    shutil.copytree(TEMPLATE_DIR, proj)
    # 清掉模板自带的 .draft/,让 cmd_new 走"按需创建"的真实路径
    if (proj / ".draft").exists():
        shutil.rmtree(proj / ".draft")

    orig = pm.get_project_arg
    pm.get_project_arg = lambda: proj
    try:
        assert pm.cmd_new(["req", "E2E 测试需求"]) == 0

        # ① 生成的 PRD 草稿必须是文档级 frontmatter
        prd_draft = proj / ".draft" / "draft-req-0001-prd.md"
        assert prd_draft.exists()
        fm, _ = check.parse_frontmatter(prd_draft.read_text(encoding="utf-8"))
        assert fm["type"] == "doc"
        assert fm["subtype"] == "prd"
        assert fm["ref"] == "REQ-0001"
        # 文档级不持有 id(持有就会与登记册条目撞号)
        assert "id" not in fm

        # ② 定稿:应同时翻登记册条目 + 把 PRD 搬到正式位
        assert pm.cmd_finalize(["REQ-0001"]) == 0
        prd = proj / "文档库" / "01-需求" / "REQ-0001-PRD.md"
        assert prd.exists()
        assert not prd_draft.exists()
        fm2, _ = check.parse_frontmatter(prd.read_text(encoding="utf-8"))
        assert fm2["draft"] == "false"
        assert fm2["subtype"] == "prd"

        # ③ 登记册条目也被翻成 draft: false
        reg = (proj / "项目管理" / "需求登记册.md").read_text(encoding="utf-8")
        reg_clean = re.sub(r"```[a-zA-Z]*\n.*?\n```", "", reg, flags=re.DOTALL)
        entry_fm = next(
            f for f, _ in check.extract_frontmatter_blocks(reg_clean)
            if f.get("id") == "REQ-0001"
        )
        assert entry_fm["draft"] == "false"

        # ④ 关键断言:整个项目必须能通过硬阻断校验(修复前这里是 2 个错误)
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check.py"), str(proj)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"finalize 后项目不可提交:\n{r.stdout}"
    finally:
        pm.get_project_arg = orig


def test_e2e_no_entry_project_still_checks_docs(tmp_path):
    """E2E 回归:P1 —— 无条目级 frontmatter 的项目,doc 校验不得被跳过。

    修复前 check_project 开头 `if not entries: return` 提前返回,导致
    "还没立任何 REQ 的新项目"整类 doc 校验静默失效(subtype 非法/ref 悬空
    全部报不出来)。而"PRD 先写、REQ 事后补"正是第 4 条地基约束鼓励的路径。
    """
    docs = tmp_path / "文档库"
    docs.mkdir()
    (docs / "bad.md").write_text(
        "---\n"
        "type: doc\n"
        "subtype: BOGUS\n"
        "title: bad\n"
        "date: 2026-09-16\n"
        "ref: REQ-9999\n"
        "draft: false\n"
        "---\n\n正文\n",
        encoding="utf-8",
    )
    errors, warnings = check.check_project(str(tmp_path), "probe")
    assert any("subtype" in e for e in errors), f"doc subtype 未校验: {errors}"
    assert any("ref 悬空" in w for w in warnings), f"doc ref 悬空未告警: {warnings}"


def test_is_derived_file_parity(tmp_path):
    """P1 修法:pm.is_derived_file 与 check.is_derived_file 行为必须一致。

    修复前 pm.py 仍是旧实现(读前 500 字节做子串匹配),正文出现
    `derived: true` 的文件会被整文件豁免 scan_max_id 编号扫描 → 可能撞号。
    """
    # 陷阱:正文含 "derived: true" 但 frontmatter 不是派生
    trap = tmp_path / "trap.md"
    trap.write_text(
        "---\ntype: kb\nid: KB-0001\n---\n\n"
        "derived: true 这几个字符出现在正文,不应让整文件被豁免。\n",
        encoding="utf-8",
    )
    assert pm.is_derived_file(str(trap)) is False
    assert check.is_derived_file(str(trap)) is False

    # 真派生文件:两者都应判 True
    real = tmp_path / "index.md"
    real.write_text("---\nderived: true\ntype: index\n---\n\n正文\n", encoding="utf-8")
    assert pm.is_derived_file(str(real)) is True
    assert check.is_derived_file(str(real)) is True


def test_scan_max_id_ignores_derived_trap(tmp_path):
    """P1 修法效果:正文含 "derived: true" 的文件不再被跳过编号扫描。"""
    (tmp_path / "a.md").write_text("---\nid: REQ-0003\n---\n", encoding="utf-8")
    trap = tmp_path / "trap.md"
    trap.write_text(
        "---\nid: REQ-0007\ntype: kb\n---\n\nderived: true 是派生文件标记。\n",
        encoding="utf-8",
    )
    # trap.md 不是派生文件 → REQ-0007 必须被扫到
    assert scan_max_id(tmp_path, "REQ") == 7


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
