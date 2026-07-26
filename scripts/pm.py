#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM-Playbook v3.0 CLI 门面
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
    """从单文件提取所有条目(含 frontmatter)"""
    entries = []
    try:
        with open(fpath, encoding="utf-8") as fp:
            content = fp.read()
    except:
        return entries
    # 去掉代码块(避免代码块里的 frontmatter 被误解析为真条目)
    content = re.sub(r"```[a-zA-Z]*\n.*?\n```", "", content, flags=re.DOTALL)
    # 按 --- 分块
    blocks = re.split(r"\n---\s*\n", content)
    for block in blocks:
        block = block.strip()
        if not block.startswith("---"):
            continue
        block_full = "---\n" + block[3:].lstrip() + "\n---\n"
        fm = parse_frontmatter_simple(block_full)
        if "id" in fm:
            entries.append(fm)
    return entries

# ============ 命令实现 ============

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
            # 补 proj_id(若未带)
            # P3-D:插到 date 之后(与模板字段顺序一致),旧实现插到 FM 最前
            if "proj_id:" not in fm:
                date_match = re.search(r"^date:\s*.*$", new_fm, re.MULTILINE)
                if date_match:
                    insert_at = date_match.end()
                    new_fm = new_fm[:insert_at] + "\nproj_id: " + proj_name + new_fm[insert_at:]
                else:
                    # 无 date 字段,追加到 FM 末尾
                    new_fm = new_fm.rstrip() + f"\nproj_id: {proj_name}\n"
                proj_id_count += 1
            # 章程文件:更新 updated / date / current_milestone 为当天
            # (date 字段对所有类型都必填,但模板日期是占位,实例化时刷成当天)
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
                # date(顶层必填,刷成当天)
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
        print(f"✅ 已刷新项目章程 updated/date: {today_iso}")

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
        # PRD 独立文件,先写草稿区
        draft_dir = project_dir / ".draft"
        draft_dir.mkdir(exist_ok=True)
        draft_file = draft_dir / f"draft-req-{new_num:04d}-prd.md"
        body = f"\n### {new_id} — {today}\n{title}\n\n(待补全正文)\n"
        with open(draft_file, "w", encoding="utf-8") as fp:
            fp.write(fm_text + body)
        print(f"✅ 已创建草稿: {draft_file}")
        print(f"   编号: {new_id}")
        print(f"   状态: draft:true (PM 定稿时跑 pm finalize {new_id})")
        print(f"   下一步: 编辑草稿正文 → pm finalize {new_id} → pm commit")
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
        # P1-B 修复:插入位置定位
        # 旧实现 re.search(r"\n---\s*\n", content) 匹配到文件头 frontmatter 结束符,
        # 新条目被插在文件头 FM 和 # 标题 之间,标题被推到新条目下方,人读结构破坏。
        #
        # 新策略(优先级递减):
        # ① 找 "<!-- 在此追加条目" 注释(模板里都有),在注释行之后插入
        # ② fallback:找第一个真实条目 FM(\n---\nid: 模式,区别于文件头 FM),
        #    在它之前插入(成为新的第一个条目)
        # ③ 最后 fallback:追加到文件末尾
        marker = "<!-- 在此追加条目"
        inserted = False
        if marker in content:
            marker_idx = content.index(marker)
            # 找注释所在行的结束位置
            line_end = content.index("\n", marker_idx)
            # 在该行之后插入(下一行开头)
            insert_pos = line_end + 1
            new_content = content[:insert_pos] + "\n" + fm_text + body + content[insert_pos:]
            inserted = True
        if not inserted:
            # fallback:找文件中第一个真实条目 FM(\n---\nid: 模式)
            # 文件头 FM 后紧跟 # 标题,条目 FM 后紧跟 id:——靠 id: 区分
            m = re.search(r"\n---\s*\nid:", content)
            if m:
                # m.start() 是 \n 的位置,在 \n 之前插入新条目(新条目 body 末尾带 ---\n 作分隔符)
                insert_pos = m.start()
                new_content = content[:insert_pos] + "\n" + fm_text + body + content[insert_pos:]
                inserted = True
        if not inserted:
            # 最后 fallback:追加到文件末尾
            new_content = content + "\n" + fm_text + body
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
    """pm brief  重聚简报(三级回退锚点)"""
    project_dir = get_project_arg()
    if not project_dir:
        print("错误: 未找到项目目录")
        return 1

    print(f"📋 重聚简报 — {project_dir.name}")
    print(f"   生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
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

    # 扫真相源,聚合到期项
    print("📅 到期/警示项:")
    today = date.today()
    found_alerts = False

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
                # 高风险开放(只报 level=高,中/低不进 brief)
                if fm.get("type") == "rsk" and fm.get("status") == "开放" and fm.get("level") == "高":
                    eid = fm.get("id", "?")
                    title = fm.get("title", "?")
                    print(f"  🔴 [高风险开放] {eid}: {title}")
                    found_alerts = True
                # 外部阻塞
                if fm.get("type") == "dep" and fm.get("status") == "等待中":
                    eid = fm.get("id", "?")
                    title = fm.get("title", "?")
                    ed = fm.get("expected_delivery", "")
                    if ed:
                        try:
                            ed_date = datetime.strptime(ed, "%Y-%m-%d").date()
                            days_left = (ed_date - today).days
                            if days_left <= 3:
                                print(f"  🟡 [DEP T-{days_left}天] {eid}: {title} (期望 {ed})")
                                found_alerts = True
                            elif days_left < 0:
                                print(f"  🔴 [DEP 已逾期 {-days_left}天] {eid}: {title} (期望 {ed})")
                                found_alerts = True
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
                                print(f"  🟡 [复审到期 {-days_left}天] {eid}: {title}")
                                found_alerts = True
                        except:
                            pass
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
                print(f"  - {d.name}")
            print()

    print("💡 下一步: 检查到期项 → 处理草稿 → pm check → pm commit")
    return 0

def cmd_doctor(args):
    """pm doctor [--fix]  自检环境,--fix 自动安装 pre-commit hook"""
    fix_mode = "--fix" in args
    print("🔧 PM-Playbook 环境自检")
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

    # 找条目所在文件
    found = False
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
                    print(f"✅ 已定稿: {target_id}")
                    print(f"   草稿 → {target_path}")
                    print(f"   draft: true → false")
                    found = True
                    break
            else:
                with open(fpath, "w", encoding="utf-8") as fp:
                    fp.write(new_content)
                print(f"✅ 已定稿: {target_id}")
                print(f"   文件: {fpath}")
                print(f"   draft: true → false")
                found = True
                break
    if not found:
        print(f"❌ 未找到 {target_id} 或它不是 draft:true")
        return 1

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
    elif cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        return 1

if __name__ == "__main__":
    sys.exit(main())
