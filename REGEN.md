# 换客户分支：低成本重生成功能地图

> 解决的问题：各客户项目定制不同（不同 git 分支），但全量重分析很贵
> （第 2 层 LLM 增强 ≈ 5M token / ≈38 分钟）。本方案让换分支时**只为变化的文件付费**。

## 为什么能省：两层成本不对称

| 层 | 脚本 | 成本 | 换分支策略 |
|---|---|---|---|
| 第 1 层 · 静态结构 | `extract.py` | 秒级、免费 | **直接重跑**（指向新分支的 src） |
| 第 2 层 · LLM 产品语言 | enrich workflow | 贵（~5M token） | **只跑变化的文件**，未变文件复用旧结果 |

不同客户分支之间，绝大多数 `.vue` 文件是相同的（共用产品基线 + 少量定制差异）。
`extract.py` 给每个文件算了内容指纹 `contentHash`，`incremental.py` 据此只挑出**变化 + 新增**的文件重跑 LLM。

## 首次：建立基线（每个"基准分支"做一次）

```bash
cd projects/platform-map
# 1. 指向基准分支源码，全量提取
SRC=/path/to/客户A分支/src python3 extract.py
# 2. 全量分批
python3 make_batches.py
# 3. 用 enrich workflow 跑 data/batches.json（全量，~38min）
#    （workflow 脚本见会话记录 / .claude 下 enrich-platform-map）
# 4. 合并
python3 merge.py
# 5. 把当前结果存为基线
python3 incremental.py --set-baseline
```

## 之后：换到新客户分支（增量，省 ~90%+）

```bash
cd projects/platform-map
# 1. 指向新分支源码，重新静态提取（秒级）
SRC=/path/to/客户B分支/src python3 extract.py
# 2. 增量比对：未变文件复用基线，只为变化文件生成批次
python3 incremental.py
#    输出会告诉你：复用 N 页、需重跑 M 页、节省百分比，并生成 data/batches.json（仅增量）
# 3. 用 enrich workflow 跑 data/batches.json（这次只有少量批次，很快很便宜）
# 4. 合并（自动并入 batch-reused + 新增量）
python3 merge.py
# 5. 部署
npx wrangler pages deploy . --project-name=dev
# 6. 确认无误后，把新结果设为该客户的基线（可选，按客户维护多套基线见下）
python3 incremental.py --set-baseline
```

## 多客户怎么管基线

`data/baseline/` 是单套基线。如果要同时维护多个客户：
- 简单做法：每个客户一个 platform-map 副本目录，各自 `data/baseline/`
- 进阶做法：把 `data/baseline/` 换成 `data/baseline-<客户>/`，`incremental.py` 加 `--client=<名>` 参数（按需扩展）

## 一句话总结

> 静态层随便重跑，LLM 层只为 diff 付费。换一个客户定制分支，通常只有几十个文件真正变了，
> 重生成成本从"全量 38 分钟"降到"几分钟"。

## 相关文件

- `extract.py` — 第 1 层静态提取（已带 contentHash）
- `make_batches.py` — 全量分批
- `incremental.py` — 增量比对 + 增量分批 + 基线管理
- `merge.py` — 合并 LLM 增强结果
- `data/baseline/` — 基线快照（sitemap + enriched）
