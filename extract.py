#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
平台功能地图 · 第 1 层提取脚本（纯静态分析，不调用 LLM）

产出 data/sitemap.json，包含：
- modules:  views 下的业务模块（目录）及其页面数
- pages:    每个 .vue 页面：路径、模块、调用的 API 函数、页面内中文标题候选
- apis:     每个 API 函数：所属文件、文件 description、函数注释、url、method
- endpoints: 每个后端 url 被哪些 API 函数定义、被哪些页面间接使用（数据血缘骨架）
- routes:   前端静态路由 path -> component -> meta.title（拿得到的菜单名）
"""
import os, re, json, sys, hashlib

SRC = os.environ.get("SRC") or \
    "/Users/apple/Desktop/ja_project/260506-shenyang/projects/项目源码/前端/intelligent-training-management/src"
CLIENT = os.environ.get("CLIENT", "main")
OUT = os.path.join(os.path.dirname(__file__), "map", "data", CLIENT, "sitemap.json")

# ---------- 1. 解析 API 文件 ----------
def parse_api_file(path, rel):
    txt = open(path, encoding="utf-8", errors="ignore").read()
    # 文件级 description
    desc = ""
    m = re.search(r"@description:?\s*(.+)", txt)
    if m:
        desc = m.group(1).strip()
        desc = re.sub(r"\s*\*/\s*$", "", desc).strip()  # 去掉行尾注释闭合符
        if desc in ("*/", "*"):
            desc = ""
    funcs = []
    # 逐行扫描，抓 export function + 其上方注释 + url + method
    lines = txt.split("\n")
    for i, line in enumerate(lines):
        fm = re.search(r"export\s+(?:const\s+)?function\s+(\w+)", line) or \
             re.search(r"export\s+const\s+(\w+)\s*=", line)
        if not fm:
            continue
        fname = fm.group(1)
        # 向上找最近的注释（// 或 /* */）
        comment = ""
        j = i - 1
        while j >= 0 and lines[j].strip() == "":
            j -= 1
        if j >= 0:
            cl = lines[j].strip()
            cm = re.match(r"//\s*(.+)", cl) or re.match(r"\*\s*(.+)", cl) or re.match(r"/\*\s*(.+?)\s*\*/", cl)
            if cm:
                comment = cm.group(1).strip()
        # 向下找 url 和 method（取函数体最近的）
        body = "\n".join(lines[i:i+25])
        um = re.search(r"url:\s*[`'\"]([^`'\"]+)[`'\"]", body)
        mm = re.search(r"method:\s*[`'\"](\w+)[`'\"]", body)
        url = um.group(1) if um else ""
        method = (mm.group(1) if mm else "").lower()
        funcs.append({"name": fname, "comment": comment, "url": url, "method": method})
    return {"file": rel, "description": desc, "functions": funcs}

# ---------- 2. 解析 Vue 页面 ----------
def parse_vue_file(path, rel):
    txt = open(path, encoding="utf-8", errors="ignore").read()
    # 提取 import { a, b } from '@/api/xxx'  和  import xx from '@/api/xxx'
    api_imports = []  # [(funcName, apiModulePath)]
    for m in re.finditer(r"import\s+(?:\{([^}]*)\}|(\w+)|\*\s+as\s+(\w+))\s+from\s+['\"]@/api/([^'\"]+)['\"]", txt):
        named, default, star, modpath = m.groups()
        if named:
            for fn in named.split(","):
                fn = fn.strip().split(" as ")[0].strip()
                if fn:
                    api_imports.append((fn, modpath))
        elif default:
            api_imports.append(("*" + default, modpath))
        elif star:
            api_imports.append(("*" + star, modpath))
    # 页面标题候选：<el-tab-pane label> / 页面 h 标题 / route title 注释 / 顶部中文
    titles = set()
    for m in re.finditer(r'label=["\']([一-龥][^"\']{0,18})["\']', txt):
        titles.add(m.group(1))
    for m in re.finditer(r'title=["\']([一-龥][^"\']{0,18})["\']', txt):
        titles.add(m.group(1))
    # 文件头 description
    desc = ""
    dm = re.search(r"@description:?\s*(.+)", txt)
    if dm:
        desc = dm.group(1).strip()
    return {
        "file": rel,
        "description": desc,
        "apiImports": api_imports,
        "titleCandidates": sorted(titles)[:12],
        "contentHash": hashlib.md5(txt.encode("utf-8", "ignore")).hexdigest(),  # 增量比对用
    }

# ---------- 3. 解析静态路由 meta.title ----------
def parse_routes():
    routes = []
    for fn in ["router/index.js", "router/modules/resources.js"]:
        p = os.path.join(SRC, fn)
        if not os.path.exists(p):
            continue
        txt = open(p, encoding="utf-8", errors="ignore").read()
        # 粗提取 path + component(views/...) + title 三元组（块内就近匹配）
        for m in re.finditer(r"path:\s*['\"]([^'\"]+)['\"]", txt):
            start = m.start()
            block = txt[start:start+400]
            comp = re.search(r"views/([\w/.-]+)", block)
            title = re.search(r"title:\s*['\"]([^'\"]+)['\"]", block)
            routes.append({
                "path": m.group(1),
                "component": ("views/" + comp.group(1)) if comp else "",
                "title": title.group(1) if title else "",
            })
    return routes

def main():
    api_dir = os.path.join(SRC, "api")
    views_dir = os.path.join(SRC, "views")

    apis = []
    func_index = {}   # (modpath, funcName) -> api func meta; modpath relative without .js
    endpoint_index = {}  # url -> {methods:set, definedBy:[file#func], usedByPages:set}

    for root, _, files in os.walk(api_dir):
        for f in files:
            if not f.endswith(".js"):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, api_dir).replace("\\", "/")
            modpath = rel[:-3]  # strip .js
            info = parse_api_file(full, rel)
            apis.append(info)
            for fn in info["functions"]:
                func_index[(modpath, fn["name"])] = {**fn, "apiFile": rel, "fileDesc": info["description"]}
                if fn["url"]:
                    ep = endpoint_index.setdefault(fn["url"], {"methods": set(), "definedBy": [], "usedByPages": set()})
                    ep["methods"].add(fn["method"])
                    ep["definedBy"].append(f"{rel}::{fn['name']}")

    pages = []
    for root, _, files in os.walk(views_dir):
        for f in files:
            if not f.endswith(".vue"):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, views_dir).replace("\\", "/")
            info = parse_vue_file(full, rel)
            module = rel.split("/")[0]
            # 把 import 的 api 函数解析到具体接口
            used_apis = []
            for fname, modpath in info["apiImports"]:
                key = (modpath, fname)
                meta = func_index.get(key)
                if meta:
                    used_apis.append({
                        "func": fname, "apiModule": modpath,
                        "comment": meta["comment"], "url": meta["url"], "method": meta["method"],
                        "fileDesc": meta["fileDesc"],
                    })
                    if meta["url"]:
                        endpoint_index.setdefault(meta["url"], {"methods": set(), "definedBy": [], "usedByPages": set()})["usedByPages"].add(rel)
                else:
                    used_apis.append({"func": fname, "apiModule": modpath, "comment": "", "url": "", "method": "", "fileDesc": ""})
            pages.append({
                "file": rel, "module": module, "description": info["description"],
                "titleCandidates": info["titleCandidates"], "usedApis": used_apis,
                "contentHash": info["contentHash"],
            })

    # 模块汇总
    modules = {}
    for p in pages:
        modules.setdefault(p["module"], {"name": p["module"], "pageCount": 0})
        modules[p["module"]]["pageCount"] += 1

    # endpoint 序列化
    endpoints = []
    for url, v in endpoint_index.items():
        endpoints.append({
            "url": url,
            "methods": sorted(v["methods"]),
            "definedBy": v["definedBy"],
            "usedByPages": sorted(v["usedByPages"]),
            "pageCount": len(v["usedByPages"]),
        })
    endpoints.sort(key=lambda e: -e["pageCount"])

    routes = parse_routes()

    out = {
        "meta": {
            "source": SRC,
            "moduleCount": len(modules),
            "pageCount": len(pages),
            "apiFileCount": len(apis),
            "apiFuncCount": len(func_index),
            "endpointCount": len(endpoints),
        },
        "modules": sorted(modules.values(), key=lambda m: -m["pageCount"]),
        "pages": pages,
        "apis": apis,
        "endpoints": endpoints,
        "routes": routes,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    m = out["meta"]
    print(f"✅ 提取完成 → {OUT}")
    print(f"   模块 {m['moduleCount']} · 页面 {m['pageCount']} · API文件 {m['apiFileCount']} · API函数 {m['apiFuncCount']} · 接口端点 {m['endpointCount']}")

if __name__ == "__main__":
    main()
