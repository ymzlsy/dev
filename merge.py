#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并 enriched/batch-*.json → enriched.json（file -> 产品语言信息）"""
import json, glob, os

HERE = os.path.dirname(__file__)
CLIENT = os.environ.get("CLIENT", "main")
ENR = os.path.join(HERE, "map", "data", CLIENT, "enriched")
OUT = os.path.join(HERE, "map", "data", CLIENT, "enriched.json")

byFile = {}
nbatch = 0
for f in sorted(glob.glob(os.path.join(ENR, "batch-*.json"))):
    nbatch += 1
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception as e:
        print("跳过损坏文件", f, e); continue
    for p in d.get("pages", []):
        fp = p.get("file")
        if not fp:
            continue
        byFile[fp] = {
            "productTitle": p.get("productTitle", ""),
            "summary": p.get("summary", ""),
            "pageType": p.get("pageType", ""),
            "terms": p.get("terms", []),
            "dataSource": p.get("dataSource", ""),
        }

json.dump({"byFile": byFile}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"✅ 合并 {nbatch} 批 → {OUT}")
print(f"   覆盖页面 {len(byFile)} 个")
# pageType 分布
from collections import Counter
c = Counter(v["pageType"] for v in byFile.values())
print("   页面类型分布:", dict(c))
