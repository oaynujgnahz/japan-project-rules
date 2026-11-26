#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给一个项目生成本地 project.json（规则仓库 init）。入口: ./init.sh

  ./init.sh <项目路径> <项目名> [--out <配置输出路径>] [--answers answers.json]
  ./init.sh <项目路径> <项目名> --emit-questions [questions.json]   # 只输出待确认问题（bot 在聊天里问用户）
  ./init.sh <项目路径> <项目名> --verify --out <配置>               # 重扫 locale，条数和配置里的指纹对不上就报错
  ./init.sh -  <项目名> --no-scan --answers a.json --out <配置>     # 不扫描，全部值来自 answers（读不到代码的机器）

做什么：
  1. 只读扫描项目：build 工具、模块、base package、locale 目录和语言、错误码正则候选（附命中条数和 文件:行号）。
     locale 不是 TS 的 'CODE': '文言' 格式时停下，说明需要新的读取器。
  2. 逐项确认：交互模式显示检测值和证据，回车接受；--answers 模式从 JSON 读回答。
     非交互终端又没给 --answers 时报错退出，不使用任何默认值。
  3. 以规则仓库的示例（"_example": true）为模板生成新配置，去掉 _example。示例文件永远不改。
     项目相关的键先全部换成占位符，再用扫描结果和回答填上；没填上的保留占位符，校验时报错。
  4. 输出在某个 git 仓库里时，先把路径写进该仓库的 .git/info/exclude，并用 git check-ignore 自检，失败就报错。
     不改、不提交任何已被 git 跟踪的文件。已有配置时：已确认的项不覆盖，只把变化项列成 diff 再确认。
  5. 自检：用确认的正则重扫 locale，条数必须和确认时一致；生成一条故意缺一个语言的错误码 UT case，lint 必须报出来。
  不 commit、不 push。
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TOOLS = Path(__file__).resolve().parent
KIT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import project_config as pc  # noqa: E402

PH = "<<未設定: {}>>"
SKIP_DIRS = {".git", "node_modules", "target", "dist", "build", "out", ".idea", ".vscode", "coverage", ".gradle",
             ".rules-backup", "__pycache__", ".next", "vendor"}
LOCALE_DIR_NAMES = {"locale", "locales", "i18n", "lang", "langs", "messages"}
LANG_RE = re.compile(r"^(?:[a-z]{2})(?:[-_][A-Za-z]{2,4})?$")
ANY_CODE_KEY = re.compile(r"""(['"])([A-Z][A-Za-z]{1,7}\d{3,5}-[A-Z])\1\s*:""")
TS_SUFFIXES = (".ts", ".js", ".mjs", ".cjs")
OTHER_LOCALE_SUFFIXES = (".json", ".properties", ".yml", ".yaml", ".po", ".xml", ".resx", ".arb")


def die(msg: str, code: int = 2):
    print(f"ERROR(init): {msg}", file=sys.stderr)
    sys.exit(code)


def info(msg: str = ""):
    print(msg, file=sys.stderr)


# ------------------------------------------------------------------ dotted access
def dget(d: dict, key: str, default=None):
    cur = d
    for p in key.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def dset(d: dict, key: str, value):
    parts = key.split(".")
    cur = d
    for p in parts[:-1]:
        if not isinstance(cur.get(p), dict):
            cur[p] = OrderedDict()
        cur = cur[p]
    cur[parts[-1]] = value


def is_unset(v) -> bool:
    return v is None or (isinstance(v, str) and v.startswith("<<未設定"))


# ------------------------------------------------------------------ scan (read only)
def _walk(root: Path, max_depth: int = 7):
    root_depth = len(root.parts)
    for dp, dns, fns in os.walk(root):
        d = Path(dp)
        dns[:] = sorted(x for x in dns if x not in SKIP_DIRS and not (x.startswith(".") and x not in (".github",)))
        if len(d.parts) - root_depth >= max_depth:
            dns[:] = []
        yield d, dns, sorted(fns)


def _rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def scan_build(root: Path) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    pom = root / "pom.xml"
    gradle = next((root / n for n in ("build.gradle.kts", "build.gradle") if (root / n).exists()), None)
    pkg = root / "package.json"
    if pom.exists():
        t = pom.read_text(encoding="utf-8", errors="replace")
        body = re.sub(r"<parent>.*?</parent>", lambda m: " " * len(m.group(0)), t, flags=re.S)
        body = re.sub(r"<(dependencies|build|dependencyManagement|profiles|modules)>.*?</\1>",
                      lambda m: " " * len(m.group(0)), body, flags=re.S)
        art = re.search(r"<artifactId>\s*([^<\s]+)\s*</artifactId>", body)
        mods = [(m.group(1), _line_of(t, m.start())) for m in re.finditer(r"<module>\s*([^<\s]+)\s*</module>", t)]
        jv = re.search(r"<(?:java\.version|maven\.compiler\.source|maven\.compiler\.release)>\s*([^<\s]+)\s*<", t)
        wrapper = "./mvnw" if (root / "mvnw").exists() else "mvn"
        out["scan.build_tool"] = {"value": "maven", "evidence": ["pom.xml"]}
        out["detect.file"] = {"value": "pom.xml", "evidence": ["pom.xml"]}
        out["detect.contains"] = {"value": art.group(1) if art else "",
                                  "evidence": [f"pom.xml:{_line_of(t, art.start())} <artifactId>{art.group(1)}</artifactId>"] if art else ["pom.xml: 根 artifactId 未找到"]}
        out["scan.modules"] = {"value": [m for m, _ in mods], "evidence": [f"pom.xml:{ln} <module>{m}</module>" for m, ln in mods[:5]]}
        out["build.backend_test"] = {"value": f"{wrapper} -pl <module> -am test -DskipTests=false", "evidence": ["pom.xml" + (" + mvnw" if wrapper != "mvn" else "")]}
        chk = {"name": "maven", "cmd": f"{wrapper} -v", "expect": jv.group(1) if jv else ""}
        out["env_checks"] = {"value": [chk], "evidence": [f"pom.xml:{_line_of(t, jv.start())} {jv.group(0).strip()}"] if jv else ["pom.xml（未写 Java 版本，只检查能运行）"]}
    elif gradle:
        t = gradle.read_text(encoding="utf-8", errors="replace")
        st = next((root / n for n in ("settings.gradle.kts", "settings.gradle") if (root / n).exists()), None)
        mods = []
        if st:
            s = st.read_text(encoding="utf-8", errors="replace")
            mods = [x.strip(":") for x in re.findall(r"""['"](:?[\w.-]+)['"]""", " ".join(re.findall(r"include\s*\(?([^\n]*)", s)))]
        wrapper = "./gradlew" if (root / "gradlew").exists() else "gradle"
        out["scan.build_tool"] = {"value": "gradle", "evidence": [gradle.name]}
        out["detect.file"] = {"value": gradle.name, "evidence": [gradle.name]}
        out["detect.contains"] = {"value": "", "evidence": [f"{gradle.name}（gradle 没有固定的识别字符串）"]}
        out["scan.modules"] = {"value": mods, "evidence": [st.name] if st else []}
        out["build.backend_test"] = {"value": f"{wrapper} :<module>:test", "evidence": [gradle.name]}
        out["env_checks"] = {"value": [{"name": "gradle", "cmd": f"{wrapper} -v", "expect": ""}], "evidence": [gradle.name]}
    elif pkg.exists():
        js = json.loads(pkg.read_text(encoding="utf-8", errors="replace") or "{}")
        out["scan.build_tool"] = {"value": "npm", "evidence": ["package.json"]}
        out["detect.file"] = {"value": "package.json", "evidence": ["package.json"]}
        out["detect.contains"] = {"value": f'"name": "{js.get("name")}"' if js.get("name") else "", "evidence": ["package.json name"]}
        out["scan.modules"] = {"value": [], "evidence": []}
        out["build.backend_test"] = {"value": "", "evidence": ["package.json（无后端构建）"]}
        out["env_checks"] = {"value": [], "evidence": []}
    # frontend
    fe = next((d for d in (root / "frontend", root) if (d / "package.json").exists()), None)
    if fe is not None:
        rel = _rel(root, fe)
        out["build.frontend"] = {"value": ("npm run build" if rel == "." else f"cd {rel} && npm run build"), "evidence": [f"{rel}/package.json"]}
        nv = next((fe / n for n in (".nvmrc", ".node-version") if (fe / n).exists()), None) or \
            next((root / n for n in (".nvmrc", ".node-version") if (root / n).exists()), None)
        ver = nv.read_text().strip() if nv else ""
        if ver and not ver.startswith("v"):
            ver = "v" + ver
        out.setdefault("env_checks", {"value": [], "evidence": []})
        out["env_checks"]["value"] = list(out["env_checks"]["value"]) + [{"name": "node", "cmd": "node -v", "expect": ver}]
        out["env_checks"]["evidence"] = list(out["env_checks"]["evidence"]) + ([f"{_rel(root, nv)}: {ver}"] if nv else [f"{rel}/package.json（无 .nvmrc，只检查能运行）"])
    else:
        out.setdefault("build.frontend", {"value": "", "evidence": ["无 package.json"]})
    # base package
    pk: Dict[str, Tuple[int, str]] = {}
    n = 0
    for d, _dns, fns in _walk(root, 14):
        if not re.search(r"src/main/(java|kotlin)(/|$)", d.as_posix()):
            continue
        for f in fns:
            if f.endswith((".java", ".kt")):
                p = d / f
                m = re.search(r"^\s*package\s+([\w.]+)", p.read_text(encoding="utf-8", errors="replace"), re.M)
                if m:
                    n += 1
                    c, ev = pk.get(m.group(1), (0, f"{_rel(root, p)}:{_line_of(p.read_text(encoding='utf-8', errors='replace'), m.start())}"))
                    pk[m.group(1)] = (c + 1, ev)
                if n > 3000:
                    break
    if pk:
        parts = [k.split(".") for k in pk]
        common = []
        for seg in zip(*parts):
            if len(set(seg)) == 1:
                common.append(seg[0])
            else:
                break
        out["scan.base_package"] = {"value": ".".join(common), "evidence": [f"{v[1]} package {k}" for k, v in sorted(pk.items(), key=lambda kv: -kv[1][0])[:3]] + [f"{n} 个源文件的公共前缀"]}
    else:
        out["scan.base_package"] = {"value": "", "evidence": ["src/main/java 下没有 package 声明"]}
    return out


def payload_install_keys() -> Dict[str, dict]:
    """local_only / executable：install.sh 会拷进项目的 payload 顶层条目（规则仓库自身，与项目无关）"""
    pay = KIT / "payload"
    lo, ex = [], []
    for p in sorted(pay.iterdir()):
        if p.name == ".github":
            lo += [f".github/{q.relative_to(p)}" for q in sorted(p.rglob("*")) if q.is_file()]
        elif p.is_dir():
            lo.append(p.name + "/")
        else:
            lo.append(p.name)
    for q in sorted(pay.rglob("*")):
        if q.is_file() and os.access(q, os.X_OK):
            ex.append(str(q.relative_to(pay)))
    return {"local_only": {"value": lo, "evidence": ["payload/ 顶层（install.sh 拷贝的内容）"]},
            "executable": {"value": ex, "evidence": ["payload/ 下带可执行位的文件"]}}


def find_locale(root: Path) -> Tuple[Optional[Path], List[str]]:
    cands = []
    for d, dns, fns in _walk(root, 8):
        if d.name.lower() in LOCALE_DIR_NAMES:
            hits = 0
            for p in d.rglob("*"):
                if p.is_file() and p.suffix in TS_SUFFIXES + OTHER_LOCALE_SUFFIXES:
                    t = p.read_text(encoding="utf-8", errors="replace")
                    hits += len(ANY_CODE_KEY.findall(t)) + len(re.findall(r"^[A-Z][A-Za-z]{1,7}\d{3,5}-[A-Z]\s*[=:]", t, re.M))
            cands.append((hits, d))
    cands.sort(key=lambda x: (-x[0], len(x[1].parts)))
    ev = [f"{_rel(root, d)}/: 错误码样式的键 {h} 个" for h, d in cands[:5]]
    return (cands[0][1] if cands else None), ev


def scan_locale(root: Path, loc: Path) -> Dict[str, Any]:
    """语言（子目录/文件名）、每个语言的文件、错误码候选。格式不是 TS 'CODE': '文言' 就停"""
    files = [p for p in sorted(loc.rglob("*")) if p.is_file()]
    by_lang: Dict[str, List[Path]] = OrderedDict()
    for p in files:
        rel = p.relative_to(loc)
        lang = None
        if len(rel.parts) > 1 and LANG_RE.match(rel.parts[0]):
            lang = rel.parts[0]
        else:
            m = re.match(r"^([a-z]{2}(?:[-_][A-Z]{2})?)(?:[._-]|$)", p.stem + ".")
            if m and LANG_RE.match(m.group(1)):
                lang = m.group(1)
        if lang:
            by_lang.setdefault(lang, []).append(p)
    if not by_lang:
        die(f"locale 目录 {_rel(root, loc)}/ 下认不出语言（既没有 ja/、en/ 这样的子目录，也没有 ja_*.ts 这样的文件名）。"
            f"请在 answers 里写 i18n.languages 和 unit_test.locale_files，或说明 locale 的组织方式。", 3)
    non_ts = [p for ps in by_lang.values() for p in ps if p.suffix not in TS_SUFFIXES]
    langs_files: Dict[str, List[str]] = OrderedDict()
    codes: Dict[str, List[Tuple[str, str, int]]] = {}  # code -> [(lang, file, line)]
    dq_only = []
    for lang, ps in by_lang.items():
        for p in ps:
            if p.suffix not in TS_SUFFIXES:
                continue
            t = p.read_text(encoding="utf-8", errors="replace")
            found = False
            for m in ANY_CODE_KEY.finditer(t):
                if m.group(1) == '"':
                    dq_only.append(f"{_rel(root, p)}:{_line_of(t, m.start())}")
                    continue
                found = True
                codes.setdefault(m.group(2), []).append((lang, str(p.relative_to(loc)), _line_of(t, m.start())))
            if found:
                langs_files.setdefault(lang, []).append(str(p.relative_to(loc)))
    if not codes:
        why = []
        if non_ts:
            why.append("locale 文件是 " + "、".join(sorted({p.suffix for p in non_ts})) + "（例: " + _rel(root, non_ts[0]) + "）")
        if dq_only:
            why.append("键是双引号 \"CODE\": 写法（例: " + dq_only[0] + "）")
        die("locale 不是 TS 的 'CODE': '文言' 格式，gen_ut_xlsx.py 现在的读取器读不了"
            + (f"（{'；'.join(why)}）" if why else "") + "。需要先给 gen_ut_xlsx.py 加一个对应格式的读取器，再跑 init。", 3)
    # candidates: prefix letters + digit count
    groups: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for code, occ in codes.items():
        m = re.match(r"^([A-Za-z]+)(\d+)-([A-Z])$", code)
        g = groups.setdefault((m.group(1), len(m.group(2))), {"suffix": set(), "codes": set(), "occ": []})
        g["suffix"].add(m.group(3))
        g["codes"].add(code)
        g["occ"] += occ
    cands = []
    for (pre, nd), g in sorted(groups.items(), key=lambda kv: -len(kv[1]["codes"])):
        rx = f"{pre}\\d{{{nd}}}-[{''.join(sorted(g['suffix']))}]"
        per_lang = OrderedDict((l, sum(1 for o in g["occ"] if o[0] == l)) for l in by_lang)
        ev = [f"{_rel(root, loc)}/{f}:{ln}" for (_l, f, ln) in g["occ"][:3]]
        cands.append({"regex": rx, "distinct_codes": len(g["codes"]), "hits_per_language": per_lang, "evidence": ev})
    return {"languages": [l for l in by_lang if l in langs_files] or list(by_lang),
            "all_languages": list(by_lang), "locale_files": langs_files, "candidates": cands,
            "non_ts": [_rel(root, p) for p in non_ts]}


# ------------------------------------------------------------------ locale hit count (= what gen_ut_xlsx.py reads)
def locale_hits(cfg: dict, project: Path) -> Dict[str, int]:
    sys.path.insert(0, str(TOOLS / "unit-test-xlsx" / "scripts"))
    import gen_ut_xlsx as g  # noqa
    g.configure(cfg)
    d = project / cfg["i18n"]["locale_dir"]
    if not d.is_dir():
        die(f"locale 目录不存在: {d}", 3)
    loc = g.Locale(d)
    return OrderedDict((l, len(loc.msgs[l])) for l in cfg["i18n"]["languages"])


# ------------------------------------------------------------------ questions
def build_questions(example: dict, scan: Dict[str, dict], loc_scan: Optional[dict], name: str) -> List[dict]:
    Q: List[dict] = []

    def q(key, kind, prompt, detected=None, evidence=None, allow_empty=False, ref=None, candidates=None):
        Q.append(OrderedDict([("key", key), ("kind", kind), ("prompt", prompt), ("detected", detected),
                              ("evidence", evidence or []), ("allow_empty", allow_empty),
                              ("example_value", ref), ("candidates", candidates)]))

    ex = lambda k: dget(example, k)  # noqa: E731
    q("design.system_name", "required", "システム名（表紙・各 sheet のヘッダー）", ref=ex("design.system_name"))
    q("design.author", "required", "作成者（可空）", allow_empty=True, ref=ex("design.author"))
    q("design.doc_no_format", "required", "文書番号の書式（表紙）", ref=ex("design.doc_no_format"))
    q("ids.screen_id", "required", "画面 ID の正則（前後の境界は不要）", ref=ex("ids.screen_id"))
    q("ids.api_id", "required", "API ID の正則（前後の境界は不要）", ref=ex("ids.api_id"))
    q("design.screen_template", "required", "公司模板（画面設計書）本地路径。只记路径，不复制进规则仓库", ref=ex("design.screen_template"))
    q("design.api_template", "required", "公司模板（API設計書）本地路径。只记路径，不复制进规则仓库", ref=ex("design.api_template"))
    q("design.body_lang", "required", "正文语言（设计书和单体 case 共用，如 ja）", ref=ex("design.body_lang"))
    if loc_scan:
        best = loc_scan["candidates"][0] if loc_scan["candidates"] else None
        q("i18n.languages", "confirm", "项目支持的语言（第一个是正文语言；每个错误码按这里的每个语言各要一条 case）",
          detected=loc_scan["languages"], evidence=[f"{l}: " + ", ".join(fs) for l, fs in loc_scan["locale_files"].items()])
        q("ids.error_code", "confirm", "错误码正则（命中条数见候选）", detected=best["regex"] if best else None,
          evidence=(best or {}).get("evidence", []), candidates=loc_scan["candidates"])
    else:
        q("i18n.languages", "confirm", "项目支持的语言（第一个是正文语言）", ref=ex("i18n.languages"))
        q("ids.error_code", "confirm", "错误码正则", ref=ex("ids.error_code"))
    det = ["i18n.locale_dir", "unit_test.locale_files", "detect.file", "detect.contains", "local_only", "executable",
           "env_checks", "build.backend_test", "build.frontend"]
    if scan:
        det += ["scan.build_tool", "scan.modules", "scan.base_package"]
    for k in det:
        s = scan.get(k)
        q(k, "detected", f"扫描结果: {k}", detected=s["value"] if s else None, evidence=s["evidence"] if s else [],
          allow_empty=k in ("detect.contains", "build.backend_test", "build.frontend", "scan.base_package"),
          ref=ex(k) if not k.startswith("scan.") else None)
    return Q


def lang_questions(langs: List[str], example: dict) -> List[dict]:
    out = []
    for l in langs:
        for k, p in (("unit_test.error_message_templates", "错误码 case 的予想結果书式（含 {text} 和 {code}）"),
                     ("unit_test.language_labels", "分岐2 里写的语言名")):
            if dget(example, f"{k}.{l}") is None:
                out.append(OrderedDict([("key", f"{k}.{l}"), ("kind", "required"), ("prompt", f"[{l}] {p}"),
                                        ("detected", None), ("evidence", []), ("allow_empty", False),
                                        ("example_value", dget(example, f"{k}.ja")), ("candidates", None)]))
    return out


# ------------------------------------------------------------------ config assembly
PROJECT_KEYS_EXTRA = ["unit_test.body_lang", "unit_test.error_message_templates", "unit_test.language_labels", "name"]


def template_from_example(example: dict, keys: List[str]) -> dict:
    cfg = copy.deepcopy(example)
    cfg.pop("_example", None)
    for k in keys:
        if k.startswith("scan."):
            continue
        dset(cfg, k, PH.format(k))
    return cfg


def finalize_lang_maps(cfg: dict, example: dict, answers: Dict[str, Any], existing: Optional[dict]):
    langs = cfg["i18n"]["languages"]
    for k in ("unit_test.error_message_templates", "unit_test.language_labels"):
        m = OrderedDict()
        for l in langs:
            v = answers.get(f"{k}.{l}")
            if v is None and not is_unset(dget(cfg, f"{k}.{l}")):
                v = dget(cfg, f"{k}.{l}")
            if v is None and existing is not None:
                v = dget(existing, f"{k}.{l}")
            if v is None:
                v = dget(example, f"{k}.{l}")
            m[l] = v if v is not None else PH.format(f"{k}.{l}")
        dset(cfg, k, m)
    cfg["unit_test"]["body_lang"] = cfg["design"]["body_lang"]


def ask_tty(qq: dict, current) -> Any:
    info("")
    info(f"■ {qq['key']}  — {qq['prompt']}")
    for e in qq.get("evidence") or []:
        info(f"    证据: {e}")
    for c in qq.get("candidates") or []:
        info(f"    候选: {c['regex']}  不同错误码 {c['distinct_codes']} 个  命中 {dict(c['hits_per_language'])}  例: {'; '.join(c['evidence'][:2])}")
    if qq.get("example_value") is not None:
        info(f"    （参考：示例里的值 {json.dumps(qq['example_value'], ensure_ascii=False)}，仅供参考，不是默认值）")
    default = current
    while True:
        shown = json.dumps(default, ensure_ascii=False) if default is not None else ""
        info(f"  [{shown}] 回车接受，或输入新值（列表/对象用 JSON）: ")
        line = sys.stdin.readline()
        if line == "":
            die("输入中断（EOF）。没有回答就不生成配置。")
        line = line.strip()
        if not line:
            if default is None or (default == "" and not qq["allow_empty"]):
                if qq["allow_empty"]:
                    return ""
                info("  这一项必须填写。")
                continue
            return default
        try:
            v = json.loads(line) if line[:1] in "[{\"" else line
        except json.JSONDecodeError:
            v = line
        return v


def same(a, b) -> bool:
    return json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(b, ensure_ascii=False, sort_keys=True)


# ------------------------------------------------------------------ git safety
def git(cwd: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def guard_out_path(out: Path, example_path: Path) -> Optional[Path]:
    """输出在 git 仓库里时写 .git/info/exclude 并 check-ignore 自检。返回仓库根（不在仓库里返回 None）"""
    if out.resolve() == example_path.resolve():
        die("输出路径就是规则仓库的示例文件，init 永远不改示例。请用 --out 指定别的路径。")
    d = out.parent
    d.mkdir(parents=True, exist_ok=True)
    r = git(d, "rev-parse", "--show-toplevel")
    if r.returncode != 0:
        return None
    top = Path(r.stdout.strip()).resolve()
    rel = out.resolve().relative_to(top).as_posix()
    if git(top, "ls-files", "--error-unmatch", "--", rel).returncode == 0:
        die(f"{out} 已经被 git 跟踪（{top}），init 不改已跟踪的文件。请换一个 --out 路径。")
    gd = git(top, "rev-parse", "--git-common-dir").stdout.strip()
    excl = (top / gd / "info" / "exclude") if not os.path.isabs(gd) else Path(gd) / "info" / "exclude"
    if git(top, "check-ignore", "-q", "--no-index", "--", rel).returncode != 0:
        excl.parent.mkdir(parents=True, exist_ok=True)
        old = excl.read_text(encoding="utf-8") if excl.exists() else ""
        line = "/" + rel
        if line not in old.splitlines():
            with excl.open("a", encoding="utf-8") as f:
                f.write(("" if old.endswith("\n") or not old else "\n") + "# japan-project-rules init: local project config (never commit)\n" + line + "\n")
        info(f"  .git/info/exclude に追加: {line}（{top}）")
    if git(top, "check-ignore", "-q", "--no-index", "--", rel).returncode != 0:
        die(f"git check-ignore で {rel} が無視されていない（{top}）。配置を書かずに終了します。")
    info(f"  git check-ignore OK: {rel} は {top} で無視される")
    return top


# ------------------------------------------------------------------ self test
def self_test(cfg_path: Path, cfg: dict, project: Optional[Path], confirmed_hits: Optional[Dict[str, int]]) -> List[str]:
    log = []
    if project is None:
        log.append("自检 1/2 跳过：--no-scan（读不到代码）。到能读到代码的机器上跑 --verify 补指纹。")
        return log
    hits = locale_hits(pc.load(str(cfg_path), "unit_test"), project)
    if confirmed_hits is not None and not same(dict(hits), dict(confirmed_hits)):
        die(f"自检 1 失败：用写出的配置重扫 locale，条数 {dict(hits)} ≠ 确认时 {dict(confirmed_hits)}", 4)
    log.append(f"自检 1 OK：用配置里的正则重扫 locale，条数 {dict(hits)} 与确认时一致")
    langs = cfg["i18n"]["languages"]
    if len(langs) < 2:
        log.append("自检 2 跳过：只有一种语言，不要求多语言 case")
        return log
    sys.path.insert(0, str(TOOLS / "unit-test-xlsx" / "scripts"))
    import gen_ut_xlsx as g  # noqa
    g.configure(cfg)
    loc = g.Locale(project / cfg["i18n"]["locale_dir"])
    code = sorted(loc.primary)[0] if loc.primary else None
    if not code:
        die("自检 2 失败：正文语言的 locale 里一个错误码都没读到", 4)
    gen = TOOLS / "unit-test-xlsx" / "scripts" / "gen_ut_xlsx.py"
    results = {}
    for pair in (False, True):
        case = {"meta": {"feature": "init-selftest", "lang": langs[0]},
                "check": [{"section": "【selftest】", "ref": "SCR-SELFTEST", "cases": [
                    {"viewpoint": "例外処理の網羅", "field": "selftest", "screen": "selftest", "branch1": "未入力",
                     "code": code, "pair": pair, "ref": "AC-01", "verify": "JUnit"}]}]}
        with tempfile.TemporaryDirectory() as td:
            cp = Path(td) / "cases.json"
            cp.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run([sys.executable, str(gen), str(cp), "--lint-only", "--config", str(cfg_path),
                                "--locale-dir", str(project / cfg["i18n"]["locale_dir"])], capture_output=True, text=True)
        if r.returncode not in (0, 1):
            die(f"自检 2 失败：gen_ut_xlsx.py --lint-only 异常终了\n{r.stdout}\n{r.stderr}", 4)
        results[pair] = [l for l in r.stdout.splitlines() if "Case が無いエラーコード" in l and code in l]
    if not results[False]:
        die(f"自检 2 失败：故意只写 {langs[0]} 一条的 {code}，lint 没有报出缺 {', '.join(langs[1:])} 的 case", 4)
    if results[True]:
        die(f"自检 2 失败：{code} 各语言都写了，lint 仍报缺语言（{results[True]}）", 4)
    log.append(f"自检 2 OK：{code} 故意缺 {', '.join(langs[1:])} 时 lint 报出「{results[False][0].strip()}」；补齐后不再报")
    return log


# ------------------------------------------------------------------ main
def find_example(arg: Optional[str]) -> Path:
    if arg:
        p = Path(arg)
    else:
        exs = [p for p in sorted((KIT / "projects").glob("*/project.json"))
               if json.loads(p.read_text(encoding="utf-8")).get("_example") is True]
        if len(exs) != 1:
            die(f"规则仓库 projects/ 下带 \"_example\": true 的示例应恰好 1 份，实际 {len(exs)} 份。用 --example 指定。")
        p = exs[0]
    d = json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    if d.get("_example") is not True:
        die(f"{p} 不是示例（没有 \"_example\": true），不能当模板。")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", help="项目路径（只读扫描）；--no-scan 时写 -")
    ap.add_argument("name", help="项目名（写进配置的 name）")
    ap.add_argument("--out", help="配置输出路径（默认 <项目路径>/.japan-project-rules/project.json）")
    ap.add_argument("--answers", help="回答 JSON（键是 dotted key，如 \"design.system_name\"）")
    ap.add_argument("--emit-questions", nargs="?", const="-", metavar="FILE", help="只输出待确认问题 JSON（- 为标准输出）")
    ap.add_argument("--verify", action="store_true", help="重扫 locale，条数和配置里的 fingerprint 对比")
    ap.add_argument("--no-scan", action="store_true", help="不扫描项目，所有项目相关值都从 --answers 取")
    ap.add_argument("--example", help="模板示例（默认 projects/ 下唯一带 _example 的 project.json）")
    a = ap.parse_args()

    if not (a.answers or a.emit_questions or a.verify) and not sys.stdin.isatty():
        die("不是交互终端，也没有 --answers。bot 请先 --emit-questions 拿问题、在聊天里问用户，再用 --answers 传回答。"
            "不会用任何默认值生成配置。")
    project = None if a.no_scan else Path(a.project).resolve()
    if project is not None and not project.is_dir():
        die(f"项目路径不存在: {a.project}")
    if a.out:
        out = Path(a.out).expanduser()
    elif project is not None:
        out = project / ".japan-project-rules" / "project.json"
    else:
        die("--no-scan 时必须用 --out 指定配置输出路径")

    if a.verify:
        if project is None:
            die("--verify 要扫描项目，不能和 --no-scan 一起用")
        cfg = pc.load(str(out), "unit_test")
        fp = cfg.get("fingerprint")
        if not fp:
            die(f"{out} 里没有 fingerprint（可能是 --no-scan 生成的）。在能读到代码的地方重跑一次 init 补上。", 1)
        if fp.get("error_code") != cfg["ids"]["error_code"]:
            die(f"fingerprint.error_code {fp.get('error_code')!r} ≠ ids.error_code {cfg['ids']['error_code']!r}（配置被手改过？重跑 init）", 1)
        hits = locale_hits(cfg, project)
        if not same(dict(hits), dict(fp.get("locale_hits") or {})):
            die(f"locale 条数变了：现在 {dict(hits)} ≠ 配置记录 {fp.get('locale_hits')}。先重跑 init 确认，再生成文档。", 1)
        print(f"verify OK: {cfg['ids']['error_code']} 命中 {dict(hits)}，与 fingerprint 一致")
        return

    example_path = find_example(a.example)
    example = json.loads(example_path.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)

    # ---- scan (read only)
    scan: Dict[str, dict] = {}
    loc_scan = None
    if project is not None:
        info(f"扫描（只读）: {project}")
        scan.update(scan_build(project))
        scan.update(payload_install_keys())
        loc_dir, loc_ev = find_locale(project)
        if loc_dir is None:
            die("没找到 locale 目录（locale/locales/i18n/lang/messages）。请在 answers 里写 i18n.locale_dir，或说明多语言怎么实现。", 3)
        scan["i18n.locale_dir"] = {"value": _rel(project, loc_dir), "evidence": loc_ev}
        loc_scan = scan_locale(project, loc_dir)
        scan["unit_test.locale_files"] = {"value": loc_scan["locale_files"],
                                          "evidence": [f"{l}: {', '.join(v)}" for l, v in loc_scan["locale_files"].items()]}

    answers: Dict[str, Any] = {}
    if a.answers:
        answers = json.loads(Path(a.answers).read_text(encoding="utf-8"))
        if not isinstance(answers, dict):
            die("--answers 必须是 JSON object（dotted key → 值）")
    if out.resolve() == example_path.resolve():
        die("输出路径就是规则仓库的示例文件，init 永远不改示例。请用 --out 指定别的路径。")
    if out.parent.is_dir():
        r = git(out.parent, "rev-parse", "--show-toplevel")
        if r.returncode == 0 and git(Path(r.stdout.strip()), "ls-files", "--error-unmatch", "--",
                                     out.resolve().relative_to(Path(r.stdout.strip()).resolve()).as_posix()).returncode == 0:
            die(f"{out} 已经被 git 跟踪，init 不改已跟踪的文件。请换一个 --out 路径。")
    existing = None
    if out.exists():
        try:
            existing = json.loads(out.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
        except json.JSONDecodeError as e:
            die(f"{out} 已存在但不是 JSON（{e}），不覆盖。请换一个 --out 路径。")
        if existing.get("_example") is True:
            die(f"{out} 是示例文件，init 不改示例。")

    questions = build_questions(example, scan, loc_scan, a.name)
    langs_guess = answers.get("i18n.languages") or dget(existing or {}, "i18n.languages") or (loc_scan or {}).get("languages") or []
    questions += lang_questions(langs_guess, example)

    if a.emit_questions:
        for qq in questions:
            qq["current"] = dget(existing, qq["key"]) if existing else None
        doc = OrderedDict([("project", str(project) if project else None), ("name", a.name), ("out", str(out)),
                           ("example", str(example_path)), ("questions", questions),
                           ("answers_template", OrderedDict((qq["key"], qq["current"] if qq.get("current") is not None else qq["detected"])
                                                            for qq in questions if qq["kind"] != "detected" or project is None))])
        s = json.dumps(doc, ensure_ascii=False, indent=2)
        (print(s) if a.emit_questions == "-" else Path(a.emit_questions).write_text(s + "\n", encoding="utf-8"))
        return

    interactive = not a.answers
    if interactive and not sys.stdin.isatty():
        die("不是交互终端，也没有 --answers。bot 请先 --emit-questions 拿问题、在聊天里问用户，再用 --answers 传回答。"
            "不会用任何默认值生成配置。")

    # ---- decide each value
    keys = [qq["key"] for qq in questions]
    if existing is not None:
        cfg = copy.deepcopy(existing)
    else:
        cfg = template_from_example(example, keys + PROJECT_KEYS_EXTRA)
    if existing is not None:
        for k in keys:  # 新增的问题键（旧配置里没有）先放占位符
            if dget(cfg, k) is None and not k.startswith("scan."):
                dset(cfg, k, PH.format(k))
    cfg["name"] = a.name
    missing, diffs, unconfirmed = [], [], []
    confirmed_hits = None
    for qq in questions:
        k = qq["key"]
        cur = dget(existing, k) if existing is not None else None
        cur = None if is_unset(cur) else cur
        has_ans = k in answers
        cand = answers[k] if has_ans else (qq["detected"] if qq["kind"] == "detected" and project is not None else None)
        if qq["kind"] == "confirm" and not has_ans and interactive:
            cand = qq["detected"]
        if cur is not None:
            if cand is None or same(cand, cur):
                dset(cfg, k, cur)
                continue
            diffs.append((k, cur, cand))
            if interactive:
                info(f"\n△ 变化: {k}\n    现在: {json.dumps(cur, ensure_ascii=False)}\n    新值: {json.dumps(cand, ensure_ascii=False)}")
                dset(cfg, k, ask_tty(dict(qq, detected=cand), cand))
            elif has_ans:
                dset(cfg, k, cand)
            else:
                unconfirmed.append(k)
            continue
        if interactive:
            v = ask_tty(qq, cand if qq["kind"] != "required" else None)
        elif has_ans:
            v = cand
        elif qq["kind"] == "detected" and project is not None:
            v = cand
        else:
            missing.append(k)
            continue
        if v is None or (v == "" and not qq["allow_empty"]):
            missing.append(k)
            continue
        dset(cfg, k, v)
    if diffs:
        info("\n与现有配置的差异:")
        for k, o, n in diffs:
            info(f"  {k}: {json.dumps(o, ensure_ascii=False)} → {json.dumps(n, ensure_ascii=False)}")
    if unconfirmed:
        die("以下项扫描结果和已确认的值不同，但 answers 里没有确认：" + ", ".join(unconfirmed) + "。把新值写进 answers 再跑。")
    if missing:
        die("以下项没有回答（--answers 里缺，也不能用默认值）: " + ", ".join(missing))

    # scan-only info / language maps / fingerprint
    if project is not None:
        for k in ("scan.build_tool", "scan.modules", "scan.base_package"):
            if dget(cfg, k) is None and k in scan:
                dset(cfg, k, scan[k]["value"])
    finalize_lang_maps(cfg, example, answers, existing)
    try:
        re.compile(cfg["ids"]["error_code"])
    except (re.error, TypeError) as e:
        die(f"ids.error_code 不是合法正则: {e}")
    if project is not None:
        langs = cfg["i18n"]["languages"]
        lf = cfg["unit_test"]["locale_files"]
        if isinstance(lf, dict) and any(l not in lf for l in langs):
            die(f"unit_test.locale_files 里没有这些语言的文件: {[l for l in langs if l not in lf]}（locale 里没找到）")
        if not pc.placeholders(cfg):
            confirmed_hits = locale_hits(cfg, project)
            info(f"\n确认的正则 {cfg['ids']['error_code']} 在 locale 里的命中（gen_ut_xlsx.py 能读到的错误码数）: {dict(confirmed_hits)}")
            exp = answers.get("_expect_hits")
            if exp is not None and not same(dict(exp), dict(confirmed_hits)):
                die(f"命中条数 {dict(confirmed_hits)} ≠ 回答里确认的 _expect_hits {exp}（正则或 locale 变了？）")
            if interactive:
                info("  条数对吗？回车继续，Ctrl-C 中止。")
                if sys.stdin.readline() == "":
                    die("输入中断")
            old_fp = dget(existing or {}, "fingerprint.locale_hits")
            if old_fp is not None and not same(dict(old_fp), dict(confirmed_hits)):
                info(f"  △ 变化: fingerprint.locale_hits {dict(old_fp)} → {dict(confirmed_hits)}")
                if not interactive and exp is None:
                    die("locale 命中条数和已确认的指纹不同。确认后在 answers 里写 \"_expect_hits\": "
                        + json.dumps(dict(confirmed_hits)) + " 再跑。")
            if any(v == 0 for v in confirmed_hits.values()):
                die(f"有语言一个错误码都没读到: {dict(confirmed_hits)}（正则或 locale_files 不对）")
            cfg["fingerprint"] = OrderedDict([("error_code", cfg["ids"]["error_code"]),
                                              ("locale_dir", cfg["i18n"]["locale_dir"]),
                                              ("locale_hits", confirmed_hits)])
    pc.check(cfg, sum((pc.NEEDS[t] for t in pc.NEEDS), []), "生成的配置")

    # ---- write (temp → self test → exclude → final)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "project.json"
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logs = self_test(tmp, cfg, project, confirmed_hits)
        top = guard_out_path(out, example_path)
        out.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
    for l in logs:
        info(l)
    print(f"written: {out}" + (f"（{top} 内、.git/info/exclude 済み）" if top else ""))
    print("不会 commit / push。规则仓库和项目仓库都由你自己维护。")


if __name__ == "__main__":
    main()
