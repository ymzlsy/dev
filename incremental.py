#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
平台功能地图 · 增量重生成（换客户分支时省钱用）

背景：第 1 层 extract.py 是纯静态、秒级，换分支随便重跑；
      第 2 层 LLM 增强贵（全量 ~5M token / ~38min）。
      但不同客户定制分支之间，大部分 .vue 文件是相同的（共用基线 + 少量定制差异）。
      所以：只对【内容指纹变化 + 新增】的文件重跑 LLM，未变文件直接复用旧增强结果。

用法：
  1) 切到新客户分支，SRC 指向其 src，跑 extract.py  → 生成新的 data/sitemap.json（含 contentHash）
  2) 跑本脚本 incremental.py：
       - 对比 data/baseline/sitemap.json（上次全量的基线）与新 data/sitemap.json
       - 未变文件：把旧 enriched 条目写进 data/enriched/batch-reused.json（merge 时自动并入）
       - 变化+新增文件：生成只含它们的 data/batches.json（供 workflow 增量跑）
  3) 用 workflow 只跑这批增量（同 enrich workflow）
  4) 跑 merge.py 合并 → 完整 enriched.json
  5) 部署

首次（建立基线）：全量跑完后，把当前 sitemap.json + enriched.json 复制到 data/baseline/。
  python3 incremental.py --set-baseline
"""
import os, json, sys

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data")
SITEMAP = os.path.join(DATA, "sitemap.json")
ENRICHED = os.path.join(DATA, "enriched.json")
BASE_DIR = os.path.join(DATA, "baseline")
BASE_SITEMAP = os.path.join(BASE_DIR, "sitemap.json")
BASE_ENRICHED = os.path.join(BASE_DIR, "enriched.json")
ENR_DIR = os.path.join(DATA, "enriched")
BATCHES = os.path.join(DATA, "batches.json")
BATCH_SIZE = 12


def set_baseline():
    os.makedirs(BASE_DIR, exist_ok=True)
    import shutil
    shutil.copy(SITEMAP, BASE_SITEMAP)
    if os.path.exists(ENRICHED):
        shutil.copy(ENRICHED, BASE_ENRICHED)
    print(f"✅ 已把当前 sitemap.json + enriched.json 存为基线 → {BASE_DIR}")
    print("   下次换分支 extract 后跑 `python3 incremental.py` 即可只增强变化文件。")


def hashes(sitemap):
    return {p["file"]: p.get("contentHash", "") for p in sitemap["pages"]}


def incremental():
    if not os.path.exists(BASE_SITEMAP):
        print("❌ 没有基线（data/baseline/sitemap.json）。请先全量跑一次，再 `python3 incremental.py --set-baseline`。")
        sys.exit(1)
    new = json.load(open(SITEMAP, encoding="utf-8"))
    base = json.load(open(BASE_SITEMAP, encoding="utf-8"))
    base_enr = json.load(open(BASE_ENRICHED, encoding="utf-8")).get("byFile", {}) if os.path.exists(BASE_ENRICHED) else {}

    new_h, base_h = hashes(new), hashes(base)
    new_pages = {p["file"]: p for p in new["pages"]}

    changed, added, unchanged = [], [], []
    for f, h in new_h.items():
        if f not in base_h:
            added.append(f)
        elif base_h[f] != h:
            changed.append(f)
        else:
            unchanged.append(f)
    removed = [f for f in base_h if f not in new_h]

    need_llm = changed + added  # 只有这些要重新跑 LLM

    # 1) 未变文件：复用旧 enriched → 写成一个 batch-reused.json
    #    先清掉上一次的批次结果（增量场景下 enriched/ 只应保留 reused + 本次新批次）
    import glob
    os.makedirs(ENR_DIR, exist_ok=True)
    for old in glob.glob(os.path.join(ENR_DIR, "batch-*.json")):
        os.remove(old)
    reused_pages = []
    for f in unchanged:
        if f in base_enr:
            reused_pages.append({"file": f, **base_enr[f]})
    json.dump({"batchId": "reused", "module": "(复用基线)", "pages": reused_pages},
              open(os.path.join(ENR_DIR, "batch-reused.json"), "w", encoding="utf-8"),
              ensure_ascii=False)

    # 2) 需重跑文件：生成只含它们的 batches.json
    from collections import defaultdict
    bymod = defaultdict(list)
    for f in need_llm:
        bymod[new_pages[f]["module"]].append(new_pages[f])
    batches, bid = [], 0
    for mod, pages in bymod.items():
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

    total = len(new_h)
    print("=" * 56)
    print(f"  增量分析结果（共 {total} 页）")
    print(f"  ├─ 复用基线（未变，0 成本）: {len(unchanged)} 页 → batch-reused.json")
    print(f"  ├─ 内容变化需重跑 LLM      : {len(changed)} 页")
    print(f"  ├─ 新增需重跑 LLM          : {len(added)} 页")
    print(f"  └─ 已删除（剔除）          : {len(removed)} 页")
    print("-" * 56)
    saved = (1 - len(need_llm) / total) * 100 if total else 0
    print(f"  → 本次只需跑 {len(need_llm)} 页 LLM，生成 {len(batches)} 个增量批次")
    print(f"  → 相比全量节省约 {saved:.0f}% 的 token / 时间")
    print("=" * 56)
    print("\n下一步：")
    print(f"  1. 用 enrich workflow 跑 data/batches.json（仅 {len(batches)} 批）")
    print(f"  2. python3 merge.py   # 自动合并 batch-reused + 新增量")
    print(f"  3. 部署。确认无误后 python3 incremental.py --set-baseline 更新基线")


if __name__ == "__main__":
    if "--set-baseline" in sys.argv:
        set_baseline()
    else:
        incremental()
