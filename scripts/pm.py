#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
keel v3.0 CLI 门面
用法: python scripts/pm.py <命令> [参数]

命令:
  init <项目名>      从 _模板/ 克隆新项目 + 补 proj_id + 自检(在 项目/ 下建子目录)
  new-req "标题"     扫项目最大 REQ 号 → 写 frontmatter(默认 draft:true)→ 建 PRD 草稿
  new <type> "标题"  泛化版,支持 dec/rsk/dep/com/prg/kb
  check              调 check.py + 打印人话报错 + "下一步"启发式
  commit "信息"      校验 + git commit + Approved-by trailer
  brief              重聚简报(三级回退锚点:SESSION→git log→mtime)
  doctor [--fix]      自检环境(Python/git/hook/schema),--fix 自动安装 pre-commit hook
  finalize <id>      draft:true → false,跑全量校验
  accept <REQ-XXXX>  需求验收:登记册 status → 已验收 + 建验收草稿
  gen-index          扫所有条目重建 INDEX.md(派生文件,可重建)

设计哲学(D4): pm.py 只放"生成便利",校验真理全部独占在 check.py。
agent 退化到裸写时,仍被 check.py 收敛到同一不变式——分叉只在"便利",不在"正确"。
"""

import sys
import os
import re
import subprocess
from pathlib import Path
from datetime import datetime, date

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = WORKSPACE_ROOT / "scripts"
CHECK_PY = SCRIPTS_DIR / "check.py"

# 条目类型 → 编号前缀
TYPE_PREFIX = {
    "req": "REQ", "prg": "PRG", "dec": "DEC", "com": "COM",
    "kb": "KB", "rsk": "RSK", "dep": "DEP", "gkb": "GKB",
}

# 各类型默认 status(P1-C 修复:覆盖全部 8 种,与 check.py ALLOWED_STATUS 对齐)
# 旧实现用三元表达式,com/kb/gkb 默认"进行中"——不在各自枚举里,导致 pm check 硬阻断
DEFAULT_STATUS = {
    "req": "待评审",
    "prg": "进行中",
    "dec": "评估中",
    "com": "待跟进",
    "kb": "本地",
    "rsk": "开放",
    "dep": "等待中",
    "gkb": "生效",
}

# 各类型对应的记忆文件名(单文件多条目)
# 注意:rsk/dep 在 项目管理/ 下(与 AGENTS.md 路由表一致),其余在 记忆/ 下
TYPE_FILE = {
    "req": "文档库/01-需求/REQ-{id}-PRD.md",  # PRD 独立文件
    "prg": "记忆/进度日志.md",
    "dec": "记忆/决策记录.md",
    "com": "记忆/沟通记录.md",
    "rsk": "项目管理/风险登记册.md",
    "dep": "项目管理/依赖登记册.md",
    "kb":  "记忆/知识库.md",
    "gkb": "_共享/知识库/全局知识库.md",  # GKB 是 workspace 级
}

# ============ 工具函数 ============

def find_project_dir():
    """从当前目录向上找项目根(含 项目章程.md 的目录)"""
    cwd = Path.cwd()
    for p in [cwd] + list(cwd.parents):
        if (p / "项目管理" / "项目章程.md").exists():
            return p
        # 也支持在工作区根通过 -p 指定
    return None

def get_project_arg():
    """从命令行 -p 参数获取项目路径,否则用 find_project_dir"""
    if "-p" in sys.argv:
        idx = sys.argv.index("-p")
        if idx + 1 < len(sys.argv):
            return Path(sys.argv[idx + 1]).resolve()
    return find_project_dir()

def run(cmd, cwd=None, capture=True):
    """跑子进程,返回 (returncode, stdout, stderr)。
    cmd 为字符串时 shell=True;为列表时 shell=False(避免命令注入)"""
    if isinstance(cmd, list):
        result = subprocess.run(
            cmd, shell=False, cwd=cwd,
            capture_output=capture, text=True, encoding="utf-8"
        )
    else:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=capture, text=True, encoding="utf-8"
        )
    return result.returncode, result.stdout, result.stderr

def parse_frontmatter_simple(content):
    """解析 frontmatter,返回 dict。
    委托给 check.py 的 parse_frontmatter(认 block 列表/True/yes,消除重复)"""
    from check import parse_frontmatter
    fm, _ = parse_frontmatter(content)
    return fm or {}

def is_derived_file(fpath):
    """检查是否是派生文件(豁免编号扫描)"""
    try:
        with open(fpath, encoding="utf-8") as fp:
            content = fp.read(500)
        return "derived: true" in content
    except:
        return False

def replace_draft_flag(content, target_id):
    """在含 target_id 的 frontmatter 块里把 draft: true → false。
    避免多条目文件里误改其他条目的 draft 字段(P0-1 修法)。
    返回 (new_content, replaced: bool)"""
    lines = content.split("\n")
    # 找 target_id 所在行
    id_line_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == f"id: {target_id}" or stripped == f"id:{target_id}":
            id_line_idx = i
            break
    if id_line_idx is None:
        return content, False
    # 向前找 --- (块开始)
    block_start = None
    for i in range(id_line_idx, -1, -1):
        if lines[i].strip() == "---":
            block_start = i
            break
    if block_start is None:
        return content, False
    # 向后找 --- (块结束)
    block_end = None
    for i in range(id_line_idx + 1, len(lines)):
        if lines[i].strip() == "---":
            block_end = i
            break
    if block_end is None:
        return content, False
    # 在 block_start 到 block_end 范围内替换 draft: true → false
    for i in range(block_start, block_end + 1):
        if "draft: true" in lines[i]:
            lines[i] = lines[i].replace("draft: true", "draft: false", 1)
            return "\n".join(lines), True
    return content, False

def scan_max_id(project_dir, prefix):
    """扫项目所有 .md,找某前缀的最大编号。

    P1-A 修复:额外扫 .draft/ 下的草稿**文件名**编号,
    防连续 pm new-req 时第二次编号与第一次相同(draft-req-0001-prd.md 被静默覆盖)。

    注意:.draft/ 下的**正文**仍不扫(草稿正文里的编号可能是引用,非自有编号)。
    """
    max_num = 0
    pattern = re.compile(rf"\b{prefix}-(\d{{4}})\b")
    for root, dirs, files in os.walk(project_dir):
        # .draft/ 内容跳过(草稿正文里的编号不算,防误扫引用)
        # 但 .draft/ 文件名编号在下方单独扫(P1-A)
        # 归档/ 不跳过——归档条目的编号仍是真编号,防重用
        if ".draft" in Path(root).parts:
            continue
        for f in files:
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(root, f)
            # 跳过派生文件(INDEX/现状 等,编号是示例非真条目)
            if is_derived_file(fpath):
                continue
            try:
                with open(fpath, encoding="utf-8") as fp:
                    content = fp.read()
                # 去掉代码块(避免代码块里的占位编号被误扫)
                content = re.sub(r"```[a-zA-Z]*\n.*?\n```", "", content, flags=re.DOTALL)
                for m in pattern.finditer(content):
                    num = int(m.group(1))
                    if num > max_num:
                        max_num = num
            except:
                pass
    # P1-A:扫 .draft/ 文件名编号(草稿文件名格式 draft-{prefix小写}-XXXX-*.md)
    # 防连续 new-req 时编号重用导致草稿被 open(..., "w") 覆盖
    # 注意:草稿文件名用小写前缀(draft-req-0001-prd.md),与条目编号(REQ-0001)大小写不同,
    # 用 IGNORECASE 兼容两种写法
    proj_path = Path(project_dir) if not isinstance(project_dir, Path) else project_dir
    draft_dir = proj_path / ".draft"
    if draft_dir.exists():
        fname_pattern = re.compile(rf"{prefix}-(\d{{4}})", re.IGNORECASE)
        for f in draft_dir.iterdir():
            if not f.name.endswith(".md") or f.name == "README.md":
                continue
            for m in fname_pattern.finditer(f.name):
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
    return max_num

def extract_entries_from_file(fpath):
    """从单文件提取所有条目(含 frontmatter)。

    P2-12 修法:复用 check.py 的 extract_frontmatter_blocks,
    修复旧 split 方式漏扫紧凑格式条目的 bug(详见该函数注释)。
    """
    from check import extract_frontmatter_blocks
    entries = []
    try:
        with open(fpath, encoding="utf-8") as fp:
            content = fp.read()
    except:
        return entries
    # 去掉代码块(避免代码块里的 frontmatter 被误解析为真条目)
    content = re.sub(r"```[a-zA-Z]*\n.*?\n```", "", content, flags=re.DOTALL)
    for fm, _body in extract_frontmatter_blocks(content):
        if "id" in fm:
            entries.append(fm)
    return entries

# ============ 命令实现 ============

def insert_entry_after_marker(content, fm_text, body):
    """把新条目(fm + body)插入到多条目文件的合适位置。
    优先级递减:
      ① 找 "<!-- 在此追加条目" 注释,在注释行之后插入
      ② fallback:用 extract_frontmatter_blocks 找第一个真实条目块(跳过文件头 FM),
         在它之前插入。比裸正则 \n---\s*\nid: 更健壮,能处理紧凑格式/带注释的格式。
      ③ 最后 fallback:追加到文件末尾(并打印警告,提示模板缺锚点)
    """
    marker = "<!-- 在此追加条目"
    if marker in content:
        marker_idx = content.index(marker)
        line_end = content.index("\n", marker_idx)
        insert_pos = line_end + 1
        return content[:insert_pos] + "\n" + fm_text + body + content[insert_pos:]
    # fallback:用 extract_frontmatter_blocks 找所有 FM 块
    # 跳过第一个(文件头 FM),在第二个块(第一个真实条目)开始位置插入
    from check import extract_frontmatter_blocks
    content_clean = re.sub(r"```[a-zA-Z]*\n.*?\n```", "", content, flags=re.DOTALL)
    blocks = list(extract_frontmatter_blocks(content_clean))
    if len(blocks) >= 2:
        # 第二个块是第一个真实条目,找它在原文中的位置
        # extract_frontmatter_blocks 返回 (fm, body),需要用 fm 内容定位
        # 用第一个条目的 id 字段定位(更精确)
        second_fm = blocks[1][0]
        if "id" in second_fm:
            # 在原文中找该 id 行,向前找 --- 块开始
            id_val = second_fm["id"]
            id_pattern = re.compile(rf"^id:\s*{re.escape(id_val)}\s*$", re.MULTILINE)
            m = id_pattern.search(content)
            if m:
                # 向前找 --- (块开始)
                before = content[:m.start()]
                block_start = before.rfind("\n---")
                if block_start != -1:
                    insert_pos = block_start + 1  # 跳过 \n
                    return content[:insert_pos] + "\n" + fm_text + body + content[insert_pos:]
    # 最后 fallback:追加到文件末尾
    print("⚠️  警告:模板缺 `<!-- 在此追加条目` 锚点,且无法定位条目块,已追加到文件末尾")
    print("   建议在模板中补 `<!-- 在此追加条目(最新在顶) -->` 注释作为显式锚点")
    return content + "\n" + fm_text + body

def cmd_init(args):
    """pm init <项目名>  从 _模板/ 克隆新项目 + 补 proj_id + 自检"""
    if not args:
        print("用法: pm init <项目名>  例: pm init PROJ-我的项目")
        print("  命名规范:建议 PROJ- 前缀 + 业务名(如 PROJ-Node-PoC)")
        return 1

    proj_name = args[0]

    # 命名校验
    if not proj_name.startswith("PROJ-"):
        print(f"⚠️  项目名建议以 'PROJ-' 开头(当前: {proj_name})")
        confirm = input("继续? (y/N): ").strip().lower()
        if confirm != "y":
            print("取消")
            return 1

    # 模板目录
    template_dir = WORKSPACE_ROOT / "_模板"
    if not template_dir.exists():
        print(f"错误: 模板目录不存在: {template_dir}")
        return 1

    # 目标目录
    projects_root = WORKSPACE_ROOT / "项目"
    projects_root.mkdir(exist_ok=True)
    target_dir = projects_root / proj_name
    if target_dir.exists():
        print(f"错误: 目标已存在: {target_dir}")
        return 1

    # 复制模板
    import shutil
    shutil.copytree(template_dir, target_dir)
    print(f"✅ 已克隆模板 → {target_dir}")

    # 在所有项目级 .md frontmatter 里补 proj_id(模板未带)
    # 同时更新项目章程的 updated/date 为当天(模板日期 → 实例化日期)
    # 遍历 target_dir 下所有 .md,跳过 _模板.md 和 .draft/
    proj_id_count = 0
    today_iso = date.today().isoformat()
    charter_path = target_dir / "项目管理" / "项目章程.md"
    for root, dirs, files in os.walk(target_dir):
        if ".draft" in Path(root).parts:
            continue
        for f in files:
            if not f.endswith(".md") or f == "_模板.md":
                continue
            fpath = Path(root) / f
            try:
                with open(fpath, encoding="utf-8") as fp:
                    content = fp.read()
            except:
                continue
            if not content.startswith("---"):
                continue
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue
            fm = parts[1]
            new_fm = fm
            # 补 proj_id(若未带)或替换 PROJ-XXX 占位符(P2-5/6:模板统一带占位)
            # P3-D:插到 date 之后(与模板字段顺序一致),旧实现插到 FM 最前
            m_proj = re.search(r"^proj_id:\s*(.+)$", new_fm, re.MULTILINE)
            if not m_proj:
                # 缺失,插入到 date 之后
                date_match = re.search(r"^date:\s*.*$", new_fm, re.MULTILINE)
                if date_match:
                    insert_at = date_match.end()
                    new_fm = new_fm[:insert_at] + "\nproj_id: " + proj_name + new_fm[insert_at:]
                else:
                    # 无 date 字段,追加到 FM 末尾
                    new_fm = new_fm.rstrip() + f"\nproj_id: {proj_name}\n"
                proj_id_count += 1
            else:
                # 已有 proj_id 字段,检查是否是 PROJ-XXX 占位符
                current_proj = m_proj.group(1).strip()
                if current_proj in ("PROJ-XXX", "PROJ-XXX-Placeholder"):
                    # 占位符,替换为实际项目名
                    new_fm = re.sub(
                        r"^(proj_id:\s*).*$",
                        rf"\g<1>{proj_name}",
                        new_fm,
                        flags=re.MULTILINE,
                    )
                    proj_id_count += 1
            # 章程文件:更新 updated 为当天
            # (updated 仅章程有,其余容器文件无此字段)
            if fpath == charter_path:
                # updated
                if re.search(r"^updated:\s*", new_fm, flags=re.MULTILINE):
                    new_fm = re.sub(
                        r"^(updated:\s*).*$",
                        rf"\g<1>{today_iso}",
                        new_fm,
                        flags=re.MULTILINE,
                    )
                else:
                    new_fm = new_fm.rstrip() + f"\nupdated: {today_iso}\n"
            # date(顶层必填,所有容器文件刷成当天)
            # P1 修法:旧实现只刷章程 date,导致记忆日志/登记册/路线图/干系人矩阵
            # 的 date 仍是模板创建日(如 2026-07-25),实例化后与项目实际创建日期不符。
            # 容器模板不能直接用 YYYY-MM-DD 占位符(check.py 校验日期格式会过不了,
            # CI 的 _模板/ 自校验会红),所以保持有效日期 + pm init 时刷新。
            if re.search(r"^date:\s*", new_fm, flags=re.MULTILINE):
                new_fm = re.sub(
                    r"^(date:\s*).*$",
                    rf"\g<1>{today_iso}",
                    new_fm,
                    flags=re.MULTILINE,
                )
            new_content = "---" + new_fm + "---" + parts[2]
            with open(fpath, "w", encoding="utf-8") as fp:
                fp.write(new_content)
    if proj_id_count:
        print(f"✅ 已为 {proj_id_count} 个文件补 proj_id: {proj_name}")
    if charter_path.exists():
        print(f"✅ 已刷新项目章程 updated: {today_iso}")
    print(f"✅ 已刷新所有容器文件 date: {today_iso}")

    # 确保 .draft/ 存在
    (target_dir / ".draft").mkdir(exist_ok=True)

    print()
    print("📋 下一步:")
    print(f"  1. 编辑 项目管理/项目章程.md:填项目定位/北极星/边界")
    print(f"  2. 编辑 现状.md §1:填本周焦点(agent 永不触碰此节)")
    print(f"  3. 用 pm new-req \"标题\" 创建首个需求(自动建 PRD 草稿)")
    print(f"  4. pm check 校验")
    print(f"  5. pm commit \"[{proj_name}] 项目初始化\"")
    print()
    print(f"💡 提示:在项目目录内运行 pm 命令,或用 -p {target_dir}")
    return 0

def cmd_new(args):
    """pm new <type> "标题"  或  pm new-req "标题"""
    if not args:
        print("用法: pm new <type> \"标题\"  或  pm new-req \"标题\"")
        print(f"  type ∈ {list(TYPE_PREFIX.keys())}")
        return 1

    # 处理 new-req 别名
    if args[0] == "new-req":
        entry_type = "req"
        title = " ".join(args[1:]) if len(args) > 1 else None
    else:
        entry_type = args[0]
        title = " ".join(args[1:]) if len(args) > 1 else None

    if entry_type not in TYPE_PREFIX:
        print(f"错误: 未知类型 '{entry_type}'")
        print(f"  允许: {list(TYPE_PREFIX.keys())}")
        return 1

    if not title:
        title = input(f"请输入{entry_type}标题: ").strip()
        if not title:
            print("取消: 标题为空")
            return 1

    project_dir = get_project_arg()
    # GKB 是 workspace 级,不需要 project_dir
    if not project_dir and entry_type != "gkb":
        print("错误: 未找到项目目录。请在项目内运行,或用 -p <项目路径>")
        return 1

    prefix = TYPE_PREFIX[entry_type]
    # GKB 用 WORKSPACE_ROOT 扫描和写入;其他用 project_dir
    base_dir = WORKSPACE_ROOT if entry_type == "gkb" else project_dir
    max_num = scan_max_id(base_dir, prefix)
    new_num = max_num + 1
    new_id = f"{prefix}-{new_num:04d}"
    today = date.today().isoformat()

    # 写 frontmatter
    fm_lines = [
        "---",
        f"id: {new_id}",
        f"type: {entry_type}",
        f"title: {title}",
        f"date: {today}",
        f"status: {DEFAULT_STATUS[entry_type]}",  # P1-C:用 DEFAULT_STATUS 映射,覆盖全部 8 种
        "related: []",
        "related_external: []",
        "draft: true",
    ]
    if entry_type == "req":
        # req 预填 scope + artifacts 路径(PM 友好,finalize 前可改)
        fm_lines.append("scope: 在范围")
        fm_lines.append(f"artifacts: [01-需求/REQ-{new_num:04d}-PRD.md]")
    if entry_type == "dec" or entry_type == "rsk":
        fm_lines.append("review_due: ")
    if entry_type == "rsk":
        fm_lines.append("level: 中")  # 默认中,PM 后续调整
    if entry_type == "dep":
        # dep 必填 expected_delivery,draft:true 时空值降级警告(check.py §4)
        # PM finalize 前必须填有效日期
        fm_lines.append("expected_delivery: ")
    fm_lines.append("---")
    fm_text = "\n".join(fm_lines)

    # TOCTOU 二次校验:写入前重跑 scan_max_id(防并发写入编号冲突,写入协议 §5)
    max_num_final = scan_max_id(base_dir, prefix)
    if max_num_final >= new_num:
        # 编号已被占用(并发写入),自动重新计算
        new_num = max_num_final + 1
        new_id = f"{prefix}-{new_num:04d}"
        fm_lines[1] = f"id: {new_id}"
        fm_text = "\n".join(fm_lines)
        print(f"⚠️  检测到编号冲突,已自动调整为 {new_id}")

    # 决定写入位置
    if entry_type == "req":
        # req 特殊处理:同时写两份
        # ① .draft/draft-req-XXXX-prd.md(PRD 草稿,doc 文件)
        # ② 项目管理/需求登记册.md(REQ 条目,真相源)
        # 两份都标 draft:true,pm finalize <REQ-ID> 时同时翻 draft
        draft_dir = project_dir / ".draft"
        draft_dir.mkdir(exist_ok=True)
        draft_file = draft_dir / f"draft-req-{new_num:04d}-prd.md"
        prd_body = f"\n### {new_id} — {today}\n{title}\n\n(待补全正文)\n"
        with open(draft_file, "w", encoding="utf-8") as fp:
            fp.write(fm_text + prd_body)
        print(f"✅ 已创建 PRD 草稿: {draft_file}")
        print(f"   编号: {new_id}")
        print(f"   状态: draft:true (PM 定稿时跑 pm finalize {new_id})")

        # ② 同步在需求登记册追加 REQ 条目(P1-1 修法)
        # 需求登记册条目正文与 PRD 不同(登记册只存条目级索引,详情在 PRD)
        registry_path = project_dir / "项目管理" / "需求登记册.md"
        if registry_path.exists():
            # 登记册条目正文:指向 PRD,不重复内容(单一真相源)
            registry_body = (
                f"\n### {new_id} — {today}\n"
                f"{title}\n\n"
                f"详见 [REQ-{new_num:04d}-PRD](../文档库/01-需求/REQ-{new_num:04d}-PRD.md)。\n\n---\n"
            )
            with open(registry_path, encoding="utf-8") as fp:
                reg_content = fp.read()
            new_reg_content = insert_entry_after_marker(reg_content, fm_text, registry_body)
            with open(registry_path, "w", encoding="utf-8") as fp:
                fp.write(new_reg_content)
            print(f"✅ 已在登记册追加条目: {registry_path}")
        else:
            print(f"⚠️  需求登记册不存在,跳过条目写入: {registry_path}")
            print(f"   PM 需手动在登记册追加 {new_id} 条目")

        print(f"   下一步: 编辑 PRD 草稿 → pm finalize {new_id} → pm commit")
    else:
        # 多条目文件,prepend 到顶部(最新在顶)
        rel_path = TYPE_FILE[entry_type]
        target_file = base_dir / rel_path
        if not target_file.exists():
            print(f"错误: 目标文件不存在: {target_file}")
            return 1
        with open(target_file, encoding="utf-8") as fp:
            content = fp.read()
        body = f"\n### {new_id} — {today}\n{title}\n\n(待补全正文)\n\n---\n"
        new_content = insert_entry_after_marker(content, fm_text, body)
        with open(target_file, "w", encoding="utf-8") as fp:
            fp.write(new_content)
        print(f"✅ 已添加: {new_id} → {target_file}")
        print(f"   状态: draft:true (PM 定稿时跑 pm finalize {new_id})")
        print(f"   下一步: 编辑正文 → pm finalize {new_id} → pm commit")
    return 0

def cmd_check(args):
    """pm check  调 check.py + 打印人话报错"""
    project_dir = get_project_arg()
    if not project_dir:
        print("错误: 未找到项目目录")
        return 1
    rc, out, err = run([sys.executable, CHECK_PY, str(project_dir)])
    print(out)
    if err:
        print("stderr:", err)
    # 下一步启发式
    if rc == 1:
        print("\n💡 下一步:")
        if "悬空引用" in out:
            print("  - 有悬空引用:补建缺失条目,或把引用方改为 draft:true")
        if "必填字段缺失" in out:
            print("  - 必填字段缺失:编辑 frontmatter 补齐")
        if "状态枚举非法" in out:
            print("  - 状态非法:查 ALLOWED_STATUS 枚举表")
        if "draft 老化" in out and "阻断" in out:
            print("  - draft 超期:跑 pm finalize <id> 或删除草稿")
    else:
        print("\n✅ 校验通过")
    return rc

def cmd_commit(args):
    """pm commit "信息"  校验 + git commit + Approved-by trailer"""
    if not args:
        msg = input("请输入 commit 信息: ").strip()
    else:
        msg = " ".join(args)
    if not msg:
        print("取消: 信息为空")
        return 1

    project_dir = get_project_arg()
    if not project_dir:
        print("错误: 未找到项目目录")
        return 1

    # 先校验
    print("🔍 校验中...")
    rc, out, _ = run([sys.executable, CHECK_PY, str(project_dir)])
    if rc == 1:
        print("❌ 校验失败,拒绝 commit:")
        print(out)
        print("\n💡 修复后重试,或 pm finalize draft 条目")
        return 1

    # git add 当前项目变更(精准 add,不 add 全仓库——违反"一条条目=一个 commit"的根源修复)
    # 找项目相对仓库根的路径(git 需要 / 分隔符)
    project_rel = os.path.relpath(project_dir, WORKSPACE_ROOT).replace("\\", "/")
    add_paths = [project_rel]

    # P2-A:检测 _共享/ 是否有改动(GKB 晋升等场景涉及 _共享/知识库/全局知识库.md + 项目内 KB-)
    # 自动一并 add,避免 PM 手动敲 git add _共享/(违反"PM 永不敲裸 git"设计目标)
    rc, shared_status, _ = run(["git", "status", "--porcelain", "_共享"], cwd=WORKSPACE_ROOT)
    if rc == 0 and shared_status.strip():
        add_paths.append("_共享")
        print(f"📦 检测到 _共享/ 改动(可能为 GKB 晋升),一并 add")

    run(["git", "add"] + add_paths, cwd=WORKSPACE_ROOT)

    # commit(shell=False,避免命令注入)
    full_msg = f"{msg}\n\nApproved-by: PM\nReviewed-by: agent"
    rc, out, err = run(["git", "commit", "-m", full_msg], cwd=WORKSPACE_ROOT)
    if rc == 0:
        print(f"✅ 已 commit: {msg}")
        # 显示 commit hash
        rc2, hash_, _ = run(["git", "rev-parse", "--short", "HEAD"], cwd=WORKSPACE_ROOT)
        if rc2 == 0:
            print(f"   hash: {hash_.strip()}")
    else:
        print(f"❌ git commit 失败:")
        print(err or out)
    return rc

def cmd_brief(args):
    """pm brief [--all]  重聚简报(三级回退锚点)

    --all: 显示全量开放 RSK(默认只报 level=高)
    """
    show_all = "--all" in args
    project_dir = get_project_arg()
    if not project_dir:
        print("错误: 未找到项目目录")
        return 1

    print(f"📋 重聚简报 — {project_dir.name}")
    print(f"   生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if show_all:
        print(f"   模式: --all(显示全量开放 RSK)")
    print()

    # 三级回退找锚点
    anchor = None
    anchor_source = None

    # ① 最后一条 SESSION
    session_file = project_dir / "记忆" / "agent会话.md"
    if session_file.exists():
        with open(session_file, encoding="utf-8") as fp:
            content = fp.read()
        # 找最后一条 SESSION- 行
        sessions = re.findall(r"SESSION-(\d{4}-\d{2}-\d{2}-\d{4})", content)
        if sessions:
            anchor = sessions[-1]
            anchor_source = "agent会话.md"

    # ② git log 最后 commit
    if not anchor:
        rc, out, _ = run(f'git log -1 --format="%cd" --date=short -- "{project_dir}"', cwd=WORKSPACE_ROOT)
        if rc == 0 and out.strip():
            anchor = out.strip()
            anchor_source = "git log"

    # ③ 最新文件 mtime
    if not anchor:
        latest_mtime = None
        latest_file = None
        for root, dirs, files in os.walk(project_dir):
            if ".draft" in Path(root).parts:
                continue
            for f in files:
                if not f.endswith(".md"):
                    continue
                fpath = os.path.join(root, f)
                mtime = os.path.getmtime(fpath)
                if latest_mtime is None or mtime > latest_mtime:
                    latest_mtime = mtime
                    latest_file = fpath
        if latest_mtime:
            anchor = datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M")
            anchor_source = f"文件 mtime ({os.path.basename(latest_file)})"

    if anchor:
        print(f"🕐 上次锚点: {anchor} (来源: {anchor_source})")
    else:
        print(f"🕐 上次锚点: 无(首次会话)")
    print()

    # 扫真相源,聚合到期项(P2-10:全量 RSK 分组)
    today = date.today()
    rsk_high = []     # level=高 + status=开放
    rsk_mid_low = []  # level=中/低 + status=开放(--all 才显示)
    dep_alerts = []   # DEP T-3/已逾期
    review_alerts = []  # DEC/RSK 复审到期
    draft_aging = []  # 超期草稿(>7天警告/>14天阻断)

    # 扫所有条目
    for root, dirs, files in os.walk(project_dir):
        if ".draft" in Path(root).parts or "归档" in Path(root).parts:
            continue
        for f in files:
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(root, f)
            entries = extract_entries_from_file(fpath)
            for fm in entries:
                # 跳过 session 类型(P1-4 一致)
                if fm.get("type") == "session":
                    continue
                # RSK 开放项
                if fm.get("type") == "rsk" and fm.get("status") == "开放":
                    eid = fm.get("id", "?")
                    title = fm.get("title", "?")
                    level = fm.get("level", "?")
                    entry = (eid, title, level)
                    if level == "高":
                        rsk_high.append(entry)
                    else:
                        rsk_mid_low.append(entry)
                # 外部阻塞
                if fm.get("type") == "dep" and fm.get("status") == "等待中":
                    eid = fm.get("id", "?")
                    title = fm.get("title", "?")
                    ed = fm.get("expected_delivery", "")
                    if ed:
                        try:
                            ed_date = datetime.strptime(ed, "%Y-%m-%d").date()
                            days_left = (ed_date - today).days
                            if days_left <= 3 or days_left < 0:
                                dep_alerts.append((eid, title, ed, days_left))
                        except:
                            pass
                # 复审到期
                if fm.get("type") in ("dec", "rsk"):
                    rd = fm.get("review_due", "")
                    if rd and fm.get("status") in ("生效", "开放", "待复审"):
                        try:
                            rd_date = datetime.strptime(rd, "%Y-%m-%d").date()
                            days_left = (rd_date - today).days
                            if days_left <= 0:
                                eid = fm.get("id", "?")
                                title = fm.get("title", "?")
                                review_alerts.append((eid, title, days_left))
                        except:
                            pass
                # draft 老化(P2-10:brief 也扫条目级 draft,不只 .draft/ 草稿区)
                if fm.get("draft") == "true":
                    d = fm.get("date", "")
                    if d:
                        try:
                            entry_date = datetime.strptime(str(d), "%Y-%m-%d").date()
                            age = (today - entry_date).days
                            if age > 7:
                                eid = fm.get("id", "?")
                                draft_aging.append((eid, age))
                        except:
                            pass

    print("📅 到期/警示项:")
    found_alerts = False
    # 高风险开放
    for eid, title, level in rsk_high:
        print(f"  🔴 [高风险开放] {eid}: {title}")
        found_alerts = True
    # 中低风险开放(--all 才显示)
    if show_all:
        for eid, title, level in rsk_mid_low:
            icon = "🟠" if level == "中" else "🟡"
            print(f"  {icon} [{level}风险开放] {eid}: {title}")
            found_alerts = True
    elif rsk_mid_low:
        print(f"  ℹ️  另有 {len(rsk_mid_low)} 条中/低开放 RSK(--all 查看)")
    # 外部阻塞
    for eid, title, ed, days_left in dep_alerts:
        if days_left < 0:
            print(f"  🔴 [DEP 已逾期 {-days_left}天] {eid}: {title} (期望 {ed})")
        else:
            print(f"  🟡 [DEP T-{days_left}天] {eid}: {title} (期望 {ed})")
        found_alerts = True
    # 复审到期
    for eid, title, days_left in review_alerts:
        print(f"  🟡 [复审到期 {-days_left}天] {eid}: {title}")
        found_alerts = True
    if not found_alerts:
        print("  (无到期项)")
    print()

    # 扫草稿区
    draft_dir = project_dir / ".draft"
    if draft_dir.exists():
        drafts = [f for f in draft_dir.iterdir() if f.suffix == ".md" and f.name != "README.md"]
        if drafts:
            print(f"📝 草稿区({len(drafts)} 个未完成):")
            for d in drafts:
                # 计算草稿龄(从文件名提取日期 draft-XXX-YYYY-MM-DD-XXX.md,或用 mtime)
                age_str = ""
                m_date = re.search(r"(\d{4}-\d{2}-\d{2})", d.name)
                if m_date:
                    try:
                        d_date = datetime.strptime(m_date.group(1), "%Y-%m-%d").date()
                        age = (today - d_date).days
                        if age > 14:
                            age_str = f" ⛔ {age}天(超期阻断)"
                        elif age > 7:
                            age_str = f" ⚠️  {age}天(超期警告)"
                        else:
                            age_str = f" ({age}天)"
                    except:
                        pass
                print(f"  - {d.name}{age_str}")
            print()

    # 条目级 draft 老化(P2-10:不仅扫 .draft/,也扫条目级 draft:true)
    if draft_aging:
        print(f"⏰ 超期条目草稿({len(draft_aging)} 个 draft:true 超 7 天):")
        for eid, age in draft_aging:
            if age > 14:
                print(f"  ⛔ {eid}: {age}天(超期阻断,需 finalize 或砍)")
            else:
                print(f"  ⚠️  {eid}: {age}天(超期警告)")
        print()

    print("💡 下一步: 检查到期项 → 处理草稿 → pm check → pm commit")
    return 0

def cmd_doctor(args):
    """pm doctor [--fix]  自检环境,--fix 自动安装 pre-commit hook"""
    fix_mode = "--fix" in args
    print("🔧 keel 环境自检")
    print()

    issues = []

    # Python 版本
    py_ver = sys.version.split()[0]
    if sys.version_info >= (3, 6):
        print(f"  ✅ Python: {py_ver}")
    else:
        print(f"  ❌ Python: {py_ver} (需 3.6+)")
        issues.append("python")

    # git
    rc, out, _ = run(["git", "--version"])
    if rc == 0:
        print(f"  ✅ git: {out.strip()}")
    else:
        print(f"  ❌ git: 未安装")
        issues.append("git")

    # check.py 存在
    if CHECK_PY.exists():
        print(f"  ✅ check.py: {CHECK_PY}")
    else:
        print(f"  ❌ check.py: 不存在 {CHECK_PY}")
        issues.append("check.py")

    # git hook
    hook_path = WORKSPACE_ROOT / ".git" / "hooks" / "pre-commit"
    source_hook = WORKSPACE_ROOT / "scripts" / "pre-commit"
    if hook_path.exists():
        print(f"  ✅ pre-commit hook: 已安装")
    else:
        if fix_mode and source_hook.exists():
            import shutil
            try:
                hook_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_hook, hook_path)
                # Unix 设置可执行权限(Windows 不需要)
                import stat
                os.chmod(hook_path, os.stat(hook_path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
                print(f"  ✅ pre-commit hook: 已自动安装(--fix)")
            except Exception as e:
                print(f"  ❌ pre-commit hook: 安装失败 {e}")
                issues.append("hook")
        else:
            print(f"  ⚠️  pre-commit hook: 未安装")
            if source_hook.exists():
                print(f"     自动安装: pm doctor --fix")
                print(f"     手动安装: cp scripts/pre-commit .git/hooks/pre-commit")
            else:
                print(f"     scripts/pre-commit 不存在")
            issues.append("hook")

    # 当前项目
    project_dir = get_project_arg()
    if project_dir:
        print(f"  ✅ 当前项目: {project_dir.name}")
        # 章程存在
        charter = project_dir / "项目管理" / "项目章程.md"
        if charter.exists():
            with open(charter, encoding="utf-8") as fp:
                content = fp.read(500)
            m = re.search(r"schema_version:\s*\"?([0-9.]+)\"?", content)
            if m:
                print(f"  ✅ schema 版本: {m.group(1)}")
            else:
                print(f"  ⚠️  schema 版本: 章程未标")
                issues.append("schema")
        # 草稿区
        if (project_dir / ".draft").exists():
            print(f"  ✅ .draft/: 存在")
        else:
            print(f"  ⚠️  .draft/: 不存在(运行时按需创建)")
    else:
        print(f"  ⚠️  未在项目目录内")

    print()
    if issues:
        print(f"❌ 发现 {len(issues)} 个问题: {issues}")
        if "hook" in issues and not fix_mode:
            print("💡 跑 `pm doctor --fix` 可自动安装 pre-commit hook")
        return 1
    else:
        print("✅ 环境就绪")
        return 0

def cmd_accept(args):
    """pm accept <REQ-XXXX>  需求验收:登记册 status → 已验收 + 建验收草稿

    步骤:
    ① 在 需求登记册.md 把该 REQ 条目的 status 改为 已验收
    ② 在 .draft/draft-req-XXXX-验收.md 建验收报告草稿(若已存在跳过)
    ③ 跑全量校验
    """
    if not args:
        print("用法: pm accept <REQ-XXXX>  例: pm accept REQ-0007")
        return 1
    target_id = args[0].strip().upper()
    if not target_id.startswith("REQ-"):
        print(f"错误: {target_id} 不是 REQ- 编号(只支持需求验收)")
        return 1
    project_dir = get_project_arg()
    if not project_dir:
        print("错误: 未找到项目目录")
        return 1

    # ① 在登记册翻 status
    registry_path = project_dir / "项目管理" / "需求登记册.md"
    if not registry_path.exists():
        print(f"错误: 需求登记册不存在: {registry_path}")
        return 1
    with open(registry_path, encoding="utf-8") as fp:
        content = fp.read()
    if target_id not in content:
        print(f"错误: {target_id} 不在需求登记册")
        return 1
    # 按块定位:把 target_id 所在 FM 的 status 改为 已验收
    # 复用 replace_draft_flag 的块定位思路,但改 status
    lines = content.split("\n")
    id_line_idx = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s == f"id: {target_id}" or s == f"id:{target_id}":
            id_line_idx = i
            break
    if id_line_idx is None:
        print(f"错误: 找不到 {target_id} 的 id 行")
        return 1
    # 向前找 ---
    block_start = None
    for i in range(id_line_idx, -1, -1):
        if lines[i].strip() == "---":
            block_start = i
            break
    if block_start is None:
        print(f"错误: 找不到 {target_id} 的 frontmatter 开始 ---")
        return 1
    # 向后找 ---
    block_end = None
    for i in range(id_line_idx + 1, len(lines)):
        if lines[i].strip() == "---":
            block_end = i
            break
    if block_end is None:
        print(f"错误: 找不到 {target_id} 的 frontmatter 结束 ---")
        return 1
    # 在 block 范围内替换 status 行
    status_replaced = False
    for i in range(block_start, block_end + 1):
        m = re.match(r"^(\s*status:\s*)(.+)$", lines[i])
        if m:
            lines[i] = f"{m.group(1)}已验收"
            status_replaced = True
            break
    if not status_replaced:
        print(f"错误: {target_id} 缺 status 字段")
        return 1
    with open(registry_path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))
    print(f"✅ 登记册 {target_id} status → 已验收")

    # ② 建验收报告草稿(若不存在)
    m_num = re.match(r"REQ-(\d{4})", target_id)
    if m_num:
        num = m_num.group(1)
        draft_dir = project_dir / ".draft"
        draft_dir.mkdir(exist_ok=True)
        draft_file = draft_dir / f"draft-req-{num}-验收.md"
        if draft_file.exists():
            print(f"ℹ️  验收草稿已存在,跳过创建: {draft_file}")
        else:
            today = date.today().isoformat()
            # 从登记册读 PRD 路径
            prd_path = f"01-需求/REQ-{num}-PRD.md"
            accept_fm = (
                "---\n"
                f"type: doc\n"
                f"subtype: acceptance\n"
                f"title: {target_id} 验收报告\n"
                f"date: {today}\n"
                f"ref: {target_id}\n"
                f"related: []\n"
                f"related_external: []\n"
                f"draft: true\n"
                "---\n"
            )
            accept_body = (
                f"\n# {target_id} — 验收\n\n"
                f"> 对照 PRD §5 验收标准 逐项检查。\n\n"
                f"## 1. 验收范围\n"
                f"详见 [REQ-{num}-PRD](../文档库/{prd_path})。\n\n"
                f"## 2. 验收标准(引 PRD §5)\n"
                f"## 3. 验收结果(通过 / 部分通过 / 不通过)\n"
                f"## 4. 遗留问题(关联 RSK-)\n"
                f"## 5. 验收结论\n"
            )
            with open(draft_file, "w", encoding="utf-8") as fp:
                fp.write(accept_fm + accept_body)
            print(f"✅ 已建验收草稿: {draft_file}")
            print(f"   定稿时: pm finalize {target_id} (注:验收 doc 与 REQ 条目在不同文件,需手动翻 doc 的 draft)")

    # ③ 跑校验
    print("\n🔍 全量校验中...")
    rc, out, _ = run([sys.executable, CHECK_PY, str(project_dir)])
    print(out)
    if rc == 1:
        print("⚠️  校验失败,请修复后 pm commit")
    return rc

def cmd_gen_index(args):
    """pm gen-index  扫描项目所有条目,生成 INDEX.md(跨类全景索引)

    行为:
    ① 扫所有非 .draft/ 非 归档/ 的 .md,提取条目(过滤 derived/_模板/session)
    ② 按 AGENTS 路由表顺序(REQ → DEC → PRG → RSK → DEP → COM → KB → GKB)分组
    ③ 组内按 id 升序(与既有 INDEX.md 一致)
    ④ 写到 项目根/INDEX.md,frontmatter derived:true + 当天 date
    ⑤ 若 INDEX.md 已存在,只重建表格区,保留既有 frontmatter 的 proj_id(若已写)
    """
    project_dir = get_project_arg()
    if not project_dir:
        print("错误: 未找到项目目录")
        return 1

    # 扫所有条目
    all_entries = []
    for root, dirs, files in os.walk(project_dir):
        if ".draft" in Path(root).parts or "归档" in Path(root).parts:
            continue
        for f in files:
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(root, f)
            # 跳过 INDEX.md 自身(避免把旧索引里的"示例行"误扫成条目)
            if os.path.basename(fpath) == "INDEX.md":
                continue
            # 跳过派生文件(现状/路线图 等——它们 FM 里没 id,自然会被 extract 过滤,
            # 但提前跳避免误把示例编号扫进去)
            if is_derived_file(fpath):
                continue
            fms = extract_entries_from_file(fpath)
            for fm in fms:
                # 过滤 session 类型(与 cmd_brief 一致)
                if fm.get("type") == "session":
                    continue
                if "id" not in fm:
                    continue
                all_entries.append(fm)

    # 按 AGENTS 路由表顺序分组
    # 顺序:REQ → DEC → PRG → RSK → DEP → COM → KB → GKB
    TYPE_ORDER = ["req", "dec", "prg", "rsk", "dep", "com", "kb", "gkb"]
    type_order_map = {t: i for i, t in enumerate(TYPE_ORDER)}

    def sort_key(fm):
        prefix = fm.get("type", "zzz")
        # 未知类型排到最后
        type_idx = type_order_map.get(prefix, 99)
        # id 升序(用编号数字)
        eid = fm.get("id", "")
        m = re.match(r"^[A-Z]+-(\d{4})$", eid)
        id_num = int(m.group(1)) if m else 0
        return (type_idx, id_num)

    all_entries.sort(key=sort_key)

    # 构建表格行
    rows = []
    for fm in all_entries:
        eid = fm.get("id", "?")
        title = fm.get("title", "?")
        # 标题里若含 |,转义避免破坏表格
        if isinstance(title, str) and "|" in title:
            title = title.replace("|", "\\|")
        d = fm.get("date", "?")
        # date 可能是 date 对象或字符串
        d_str = str(d) if d else "?"
        status = fm.get("status", "?")
        # related 可能是 list 或字符串
        related = fm.get("related", [])
        if isinstance(related, list):
            related_str = ", ".join(str(r) for r in related) if related else ""
        else:
            related_str = str(related) if related else ""
        rows.append(f"| {eid} | {title} | {d_str} | {status} | {related_str} |")

    # 读既有 INDEX.md 取 proj_id(若存在)
    index_path = project_dir / "INDEX.md"
    proj_id = None
    if index_path.exists():
        try:
            with open(index_path, encoding="utf-8") as fp:
                old = fp.read()
            m = re.search(r"^proj_id:\s*(.+)$", old, re.MULTILINE)
            if m:
                proj_id = m.group(1).strip()
        except:
            pass
    if not proj_id:
        proj_id = project_dir.name

    today = date.today().isoformat()
    fm_text = (
        "---\n"
        "derived: true\n"
        "type: index\n"
        "title: 跨类全景索引\n"
        f"date: {today}\n"
        f"proj_id: {proj_id}\n"
        "---\n"
    )
    body = (
        "\n# INDEX(轻量·按需)\n\n"
        "> 本文件**不是需手工维护的常驻文件**。\n"
        "> - 日常检索优先用 grep + 需求登记册。\n"
        "> - 仅当需要跨类全景视图时,由脚本/AI 按需生成。\n"
        "> - 生成物标 `derived: true`,**可重建·非真相源**。\n\n"
        "| 编号 | 标题 | 日期 | 状态 | 关联 |\n"
        "| --- | --- | --- | --- | --- |\n"
    )
    if rows:
        body += "\n".join(rows) + "\n"
    else:
        body += "| (暂无条目) | — | — | — | — |\n"

    with open(index_path, "w", encoding="utf-8") as fp:
        fp.write(fm_text + body)
    print(f"✅ 已生成 INDEX: {index_path}")
    print(f"   条目数: {len(rows)}")
    # 分组统计
    type_counts = {}
    for fm in all_entries:
        t = fm.get("type", "?")
        type_counts[t] = type_counts.get(t, 0) + 1
    if type_counts:
        summary = ", ".join(f"{t.upper()}: {n}" for t, n in type_counts.items())
        print(f"   分布: {summary}")
    return 0

def cmd_finalize(args):
    """pm finalize <id>  draft:true → false,跑全量校验"""
    if not args:
        print("用法: pm finalize <id>  例: pm finalize REQ-0007")
        return 1
    target_id = args[0]
    project_dir = get_project_arg()
    if not project_dir:
        print("错误: 未找到项目目录")
        return 1

    # 扫所有文件,翻所有含 target_id 且 draft:true 的条目
    # (P1-1:REQ 类型同时有 PRD 草稿 + 登记册条目两份 draft,需同时翻)
    found_files = []
    for root, dirs, files in os.walk(project_dir):
        # 归档里的条目不应再定稿(归档=已完成)
        if "归档" in Path(root).parts:
            continue
        for f in files:
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(root, f)
            try:
                with open(fpath, encoding="utf-8") as fp:
                    content = fp.read()
            except:
                continue
            if target_id not in content:
                continue
            if "draft: true" not in content:
                continue
            # 按块定位替换(避免多条目文件里误改其他条目,P0-1 修法)
            new_content, replaced = replace_draft_flag(content, target_id)
            if not replaced:
                continue
            # 如果是 .draft/ 下的 PRD,移到正式位
            if ".draft" in fpath and "-req-" in f:
                # draft-req-0007-prd.md → REQ-0007-PRD.md
                m = re.search(r"draft-req-(\d{4})-prd\.md", f)
                if m:
                    num = m.group(1)
                    new_name = f"REQ-{num}-PRD.md"
                    target_dir = project_dir / "文档库" / "01-需求"
                    target_dir.mkdir(parents=True, exist_ok=True)
                    target_path = target_dir / new_name
                    # 覆盖检查:目标已存在则拒绝(避免静默覆盖,P1-F 修法)
                    if target_path.exists():
                        print(f"❌ 目标已存在,拒绝覆盖: {target_path}")
                        print(f"   先手动处理现有文件再 finalize")
                        return 1
                    with open(target_path, "w", encoding="utf-8") as fp:
                        fp.write(new_content)
                    os.remove(fpath)
                    print(f"✅ 已定稿(草稿→正式位): {target_path}")
                    found_files.append(target_path)
            else:
                with open(fpath, "w", encoding="utf-8") as fp:
                    fp.write(new_content)
                print(f"✅ 已定稿(就地翻 draft): {fpath}")
                found_files.append(fpath)
    if not found_files:
        print(f"❌ 未找到 {target_id} 或它不是 draft:true")
        return 1
    print(f"   翻动文件数: {len(found_files)}(REQ 等多条目场景同时翻 PRD+登记册)")

    # 定稿后跑校验
    print("\n🔍 全量校验中...")
    rc, out, _ = run([sys.executable, CHECK_PY, str(project_dir)])
    print(out)
    if rc == 1:
        print("⚠️  定稿后校验失败(可能含悬空引用等),请修复后 pm commit")
    return rc

# ============ 主入口 ============

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 0

    cmd = sys.argv[1]
    args = sys.argv[2:]
    # 过滤 -p 参数(不传给子命令)
    if "-p" in args:
        idx = args.index("-p")
        args = [a for i, a in enumerate(args) if i not in (idx, idx + 1)]

    if cmd == "init":
        return cmd_init(args)
    elif cmd == "new-req":
        return cmd_new(["new-req"] + args)
    elif cmd == "new":
        return cmd_new(args)
    elif cmd == "check":
        return cmd_check(args)
    elif cmd == "commit":
        return cmd_commit(args)
    elif cmd == "brief":
        return cmd_brief(args)
    elif cmd == "doctor":
        return cmd_doctor(args)
    elif cmd == "finalize":
        return cmd_finalize(args)
    elif cmd == "accept":
        return cmd_accept(args)
    elif cmd == "gen-index":
        return cmd_gen_index(args)
    elif cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        return 1

if __name__ == "__main__":
    sys.exit(main())
