#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全量分批：把 sitemap.json 的所有页面切成 batches.json（供 enrich workflow 全量跑）。
增量场景请改用 incremental.py（只对变化文件生成批次）。
"""
import os, json
from collections import defaultdict

HERE = os.path.dirname(__file__)
CLIENT = os.environ.get("CLIENT", "main")
SITEMAP = os.path.join(HERE, "map", "data", CLIENT, "sitemap.json")
BATCHES = os.path.join(HERE, "map", "data", CLIENT, "batches.json")
BATCH_SIZE = 12
SKIP = {"index.vue", "404.vue", "login.vue", "redirect.vue", "routerView"}

d = json.load(open(SITEMAP, encoding="utf-8"))
bymod = defaultdict(list)
for p in d["pages"]:
    bymod[p["module"]].append(p)

batches, bid = [], 0
for mod in [m["name"] for m in d["modules"]]:
    if mod in SKIP:
        continue
    pages = sorted(bymod[mod], key=lambda x: x["file"])
    for i in range(0, len(pages), BATCH_SIZE):
        chunk = pages[i:i + BATCH_SIZE]
        batches.append({
            "id": bid, "module": mod,
            "files": [{"file": p["file"],
                       "apis": [{"c": a["comment"], "u": a["url"], "m": a["method"]} for a in p["usedApis"]],
                       "fields": p["titleCandidates"]} for p in chunk],
        })
        bid += 1

json.dump(batches, open(BATCHES, "w", encoding="utf-8"), ensure_ascii=False)
print(f"✅ 全量分批 → {BATCHES}")
print(f"   {len(batches)} 批 · {sum(len(b['files']) for b in batches)} 页")
