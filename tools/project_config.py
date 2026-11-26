#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目配置（project.json）读取。tools/ 下各脚本和 install.sh 共用。

规则（不回落任何项目的默认值）：
  * 没指定配置文件 → 报错退出
  * 配置带 "_example": true（规则仓库里的示例）→ 报错退出，先跑 init.sh 生成本项目的配置
  * 必需键缺失或为空 → 报错退出
  * 值里还有占位符（<<…>>、整串 {…}、TODO）→ 报错退出
以 _ 开头的键是说明，读取时跳过。只用标准库。

  python3 project_config.py <project.json> get <dotted.key>     # 取一个值（list/dict 输出 JSON，list 可加 --lines）
  python3 project_config.py <project.json> check [--need k ...]  # 只做检查
  python3 project_config.py <project.json> render-payload <src_dir> <out_dir>
      # install.sh 用：把 payload/ 里的 {{占位符}}（文件内容和路径名）换成配置的值，写到 out_dir。
      # 占位符 → 配置键见 PAYLOAD_PLACEHOLDERS；缺键报错退出，不回落任何项目的值。路径名渲染成空的文件不装。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable, List, Optional

PLACEHOLDER_RE = re.compile(r"<<[^<>]*>>|^\{[^{}]+\}$|^TODO$")
MISSING = object()

# 各工具需要的键。末尾带 ? 的只要求存在（可以是空串/空列表），其余必须非空。
COMMON_KEYS = ["name", "ids.error_code", "i18n.locale_dir", "i18n.languages"]
NEEDS = {
    "design": COMMON_KEYS + ["design.system_name", "design.doc_no_format", "design.author?", "ids.screen_id", "ids.api_id"],
    "read_design": COMMON_KEYS + ["ids.screen_id", "ids.api_id"],
    "unit_test": COMMON_KEYS + ["ids.screen_id", "ids.api_id", "unit_test.locale_files.{lang}",
                                "unit_test.error_message_templates.{lang}", "unit_test.language_labels.{lang}"],
    "install": ["name", "detect.file", "detect.contains?", "local_only", "executable?", "env_checks?"],
}

# payload/ の {{占位符}} → 配置键（末尾 ? は空でも可）。install.sh が render-payload で置換する
PAYLOAD_PLACEHOLDERS = {
    "name": "name",                                   # 项目名（小写；e2e 包名、个人 skill 名、临时目录名）
    "system_name": "design.system_name",              # 规则文档里的项目/系统名
    "root_artifact": "payload.root_artifact",         # 根构建的 artifact（Maven parent 等）
    "repo_name": "payload.repo_name",                 # 项目仓库目录名
    "base_package": "payload.base_package?",          # Java 包根（非 Java 项目可空）
    "build_cmd": "payload.build_cmd",                 # 后端构建/测试命令（如 ./mvnw、mvn、./gradlew）
    "build_wrapper": "payload.build_wrapper?",        # payload/{{build_wrapper}}（Java 8 用 Maven 包装脚本）装成的文件名；空=不装
    "error_code_prefix": "payload.error_code_prefix",  # 错误码前缀（文档里的例子 XXXX0073-E）
    "error_code": "ids.error_code",                   # 错误码正则
}
# modules（顶层，必需）から作る占位符。各要素 {"name", "kind", "role"}，kind は MODULE_KINDS のどれか。
# kind=api のうち "main": true がちょうど 1 つ、kind=frontend がちょうど 1 つ必要。
MODULE_KINDS = ("api", "lib", "service", "frontend", "build")
MODULE_PLACEHOLDERS = {
    "modules_list": "AGENTS.md のモジュール一覧（各行「  - `name`: role」）",
    "modules_inline": "「`a` · `b` · …」",
    "modules_slash": "「a / b / …」",
    "main_module": "主 API モジュール（kind=api かつ main=true）",
    "other_api_modules": "主以外の API モジュール「a / b」",
    "other_api_test_cmds": "主以外の API モジュールのテストコマンド（1 行ずつ）",
    "frontend_module": "フロントエンドのモジュール（kind=frontend）",
    "base_package_path": "base_package の . を / にしたもの",
    "wrapper_sep_before": "「、<build_wrapper>」（空なら空）",
    "wrapper_sep_after": "「<build_wrapper>、」（空なら空）",
    "wrapper_code_before": "「、`<build_wrapper>`」（空なら空）",
}
NEEDS["install"] += list(dict.fromkeys(PAYLOAD_PLACEHOLDERS.values())) + ["modules"]
PH_TOKEN_RE = re.compile(r"\{\{([a-z_]+)\}\}")


class ConfigError(SystemExit):
    pass


def die(msg: str):
    print(f"ERROR(project.json): {msg}", file=sys.stderr)
    raise ConfigError(2)


def get(cfg: dict, key: str, default: Any = MISSING) -> Any:
    cur: Any = cfg
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            if default is MISSING:
                die(f"必需键 {key} 不存在")
            return default
        cur = cur[part]
    return cur


def placeholders(node: Any, path: str = "") -> List[str]:
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if str(k).startswith("_"):
                continue
            out += placeholders(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += placeholders(v, f"{path}[{i}]")
    elif isinstance(node, str) and PLACEHOLDER_RE.search(node.strip()):
        out.append(f"{path} = {node!r}")
    return out


def _expand(keys: Iterable[str], cfg: dict) -> List[str]:
    out = []
    for k in keys:
        if "{lang}" in k:
            langs = get(cfg, "i18n.languages", [])
            out += [k.replace("{lang}", str(l)) for l in (langs if isinstance(langs, list) else [])]
        else:
            out.append(k)
    return list(dict.fromkeys(out))


def check(cfg: dict, need: Iterable[str] = (), source: str = "") -> dict:
    if not isinstance(cfg, dict):
        die(f"{source}: 顶层必须是 JSON object")
    if cfg.get("_example") is True:
        die(f"{source} 是规则仓库的示例配置（\"_example\": true），不能直接用来生成文档。"
            f"先跑 ./init.sh <项目路径> <项目名> 生成本项目自己的 project.json，再用 --config 指定它。")
    ph = placeholders(cfg)
    if ph:
        die(f"{source}: 还有没填的占位符（重跑 init.sh 补上）:\n  " + "\n  ".join(ph))
    missing, empty = [], []
    for k in _expand(need, cfg):
        opt = k.endswith("?")
        k = k.rstrip("?")
        v = get(cfg, k, None)
        if v is None:
            missing.append(k)
        elif not opt and (v == "" or v == [] or v == {}):
            empty.append(k)
    if missing or empty:
        die(f"{source}: " + "；".join(
            ([f"缺必需键 {', '.join(missing)}"] if missing else []) + ([f"必需键为空 {', '.join(empty)}"] if empty else [])))
    langs = cfg.get("i18n", {}).get("languages")
    if langs is not None and (not isinstance(langs, list) or not all(isinstance(x, str) and x for x in langs)):
        die(f"{source}: i18n.languages 必须是语言代码列表，如 [\"ja\", \"en\"]")
    ec = cfg.get("ids", {}).get("error_code")
    if ec:
        try:
            re.compile(ec)
        except re.error as e:
            die(f"{source}: ids.error_code 不是合法的正则: {e}")
    return cfg


def load(path: Optional[str], tool: str) -> dict:
    """读配置并按 tool（NEEDS 的键）检查。path 为空就报错退出，不找默认位置。"""
    if not path:
        die("没有指定项目配置。用 --config <project.json> 指定（由 init.sh 生成；规则仓库里的示例不能直接用）")
    p = Path(path)
    if not p.is_file():
        die(f"找不到配置文件 {p}")
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"{p} 不是合法 JSON: {e}")
    return check(cfg, NEEDS.get(tool, []), str(p))


def error_code_re(cfg: dict, anchored: bool = True) -> "re.Pattern":
    body = get(cfg, "ids.error_code")
    return re.compile(rf"(?<![\w-])(?:{body})(?![\w-])" if anchored else rf"(?:{body})")


def payload_values(cfg: dict) -> dict:
    vals = {}
    for name, key in PAYLOAD_PLACEHOLDERS.items():
        k = key.rstrip("?")
        v = get(cfg, k)  # 缺键 → 报错退出
        if not isinstance(v, str):
            die(f"{k} 必须是字符串（payload 占位符 {{{{{name}}}}} 用）")
        if not key.endswith("?") and not v:
            die(f"{k} 为空（payload 占位符 {{{{{name}}}}} 用）")
        vals[name] = v
    vals.update(module_values(get(cfg, "modules"), vals))
    return vals


def module_values(mods, vals: dict) -> dict:
    if not isinstance(mods, list) or not mods:
        die("modules は空でないリスト（[{\"name\", \"kind\", \"role\"}, …]）")
    for i, m in enumerate(mods):
        if not isinstance(m, dict) or not all(isinstance(m.get(k), str) and m.get(k) for k in ("name", "kind", "role")):
            die(f"modules[{i}] に name / kind / role（空でない文字列）が要る: {m!r}")
        if m["kind"] not in MODULE_KINDS:
            die(f"modules[{i}].kind={m['kind']!r} は {list(MODULE_KINDS)} のどれか")
    main = [m for m in mods if m["kind"] == "api" and m.get("main") is True]
    fe = [m for m in mods if m["kind"] == "frontend"]
    if len(main) != 1:
        die(f"modules: kind=api かつ \"main\": true のモジュールがちょうど 1 つ要る（今 {len(main)} 個）")
    if len(fe) != 1:
        die(f"modules: kind=frontend のモジュールがちょうど 1 つ要る（今 {len(fe)} 個）")
    others = [m["name"] for m in mods if m["kind"] == "api" and m is not main[0]]
    bw = vals.get("build_wrapper", "")
    return {
        "modules_list": "\n".join(f"  - `{m['name']}`: {m['role']}" for m in mods),
        "modules_inline": " · ".join(f"`{m['name']}`" for m in mods),
        "modules_slash": " / ".join(m["name"] for m in mods),
        "main_module": main[0]["name"],
        "other_api_modules": " / ".join(others) or "-",
        "other_api_test_cmds": "\n".join(f"{vals['build_cmd']} -pl {n} -am test -DskipTests=false" for n in others),
        "frontend_module": fe[0]["name"],
        "base_package_path": vals.get("base_package", "").replace(".", "/"),
        "wrapper_sep_before": f"、{bw}" if bw else "",
        "wrapper_sep_after": f"{bw}、" if bw else "",
        "wrapper_code_before": f"、`{bw}`" if bw else "",
    }


def _render(text: str, vals: dict, where: str) -> str:
    unknown = sorted({m.group(1) for m in PH_TOKEN_RE.finditer(text) if m.group(1) not in vals})
    if unknown:
        die(f"{where}: 未定义的 payload 占位符 {unknown}（在 PAYLOAD_PLACEHOLDERS 里登记）")
    return PH_TOKEN_RE.sub(lambda m: vals[m.group(1)], text)


def render_payload(cfg: dict, src: Path, dst: Path) -> int:
    """src 下的文件渲染到 dst。文本文件只替换 {{name}}；二进制和没有占位符的文件原样复制（含权限位）。"""
    vals = payload_values(cfg)
    n = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for f in sorted(files):
            if f == ".DS_Store" or f.endswith(".pyc"):
                continue
            sp = Path(root) / f
            rel = sp.relative_to(src)
            parts = [_render(x, vals, str(rel)) for x in rel.parts]
            if any(not x for x in parts):
                continue  # 路径渲染成空（如 build_wrapper=""）→ 不装
            dp = dst.joinpath(*parts)
            dp.parent.mkdir(parents=True, exist_ok=True)
            data = sp.read_bytes()
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            if text is not None and PH_TOKEN_RE.search(text):
                dp.write_bytes(_render(text, vals, str(rel)).encode("utf-8"))
                shutil.copymode(sp, dp)
            else:
                shutil.copy2(sp, dp)
            n += 1
    return n


def _main(argv: List[str]) -> int:
    if len(argv) >= 4 and argv[1] == "render-payload":
        cfg = load(argv[0], "install")
        n = render_payload(cfg, Path(argv[2]), Path(argv[3]))
        print(n)
        return 0
    if len(argv) < 2 or argv[1] not in ("get", "check"):
        print(__doc__)
        return 2
    path, cmd, rest = argv[0], argv[1], argv[2:]
    if cmd == "check":
        need = []
        while rest:
            a = rest.pop(0)
            if a == "--need" and rest:
                need.append(rest.pop(0))
            elif a == "--tool" and rest:
                t = rest.pop(0)
                need += sum(NEEDS.values(), []) if t == "all" else NEEDS[t]
        cfg = load(path, "")
        check(cfg, need, path)
        print("OK")
        return 0
    cfg = load(path, "")
    key = rest[0]
    v = get(cfg, key)
    if isinstance(v, list) and "--lines" in rest:
        print("\n".join(json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x for x in v))
    elif isinstance(v, (list, dict)):
        print(json.dumps(v, ensure_ascii=False))
    else:
        print("" if v is None else v)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
