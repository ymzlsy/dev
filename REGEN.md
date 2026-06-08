# 加客户 / 换分支：低成本生成功能地图

> dev.karaithy.com 是「多客户看板」：每个客户一个分支 → 一套数据 `map/data/<客户key>/`，
> 在 `map/data/clients.json` 登记，dev 主页和功能地图切换器自动显示。
> 各客户定制不同（不同 git 分支），但全量重分析很贵（第 2 层 LLM ≈ 5M token/≈38min）。
> 本方案让每个客户**按 CLIENT 隔离数据**，换分支时**只为变化的文件付费**。

## 目录结构（重组后）

```
platform-map/                 (= dev 仓库 ymzlsy/dev)
├── index.html                # dev 主页（客户看板，读 clients.json 渲染卡片）
├── map/
│   ├── index.html            # 功能地图（顶部客户切换器；支持 ?c=<key> 直达）
│   └── data/
│       ├── clients.json      # 客户索引（加客户要在这登记）
│       └── <客户key>/        # 每个客户一套
│           ├── sitemap.json
│           ├── enriched.json
│           ├── baseline/      # 该客户的增量基线
│           └── enriched/      # 中间批次（gitignore，不部署）
├── functions/_middleware.js  # 全站 Basic Auth
└── extract.py / make_batches.py / merge.py / incremental.py   # 都认 CLIENT 环境变量
```

## 为什么省：两层成本不对称

| 层 | 脚本 | 成本 | 策略 |
|---|---|---|---|
| 第 1 层 · 静态结构 | `extract.py` | 秒级、免费 | 直接重跑（指向新分支 src） |
| 第 2 层 · LLM 产品语言 | enrich workflow | 贵（~5M token） | 只跑变化文件，未变复用 |

`extract.py` 给每个文件算 `contentHash`，`incremental.py` 据此只挑**变化+新增**文件重跑 LLM。

## 加一个新客户（首次，建立该客户基线）

```bash
cd projects/platform-map
export CLIENT=beijing                       # 客户 key（英文，做目录名）
# 1. 指向该客户分支源码，全量提取（秒级）
SRC=/path/to/北京分支/src CLIENT=$CLIENT python3 extract.py
# 2. 全量分批
CLIENT=$CLIENT python3 make_batches.py
# 3. 用 enrich workflow 跑 map/data/$CLIENT/batches.json（全量，~38min）
#    （workflow 脚本见 .claude 下 enrich-platform-map；把路径里的 main 换成 $CLIENT）
# 4. 合并
CLIENT=$CLIENT python3 merge.py
# 5. 存为该客户基线
CLIENT=$CLIENT python3 incremental.py --set-baseline
# 6. 在 map/data/clients.json 的 clients[] 里加一条：
#    {"key":"beijing","name":"北京XX","branch":"1.2.3-bj4","pageCount":...,"updatedAt":"..."}
# 7. git push → 自动部署。dev 主页就会多一张「北京」卡片。
```

## 同一客户拉了最新代码（增量，省 ~90%+）

```bash
cd projects/platform-map
export CLIENT=beijing
# 1. 拉最新代码后，重新静态提取（秒级）
SRC=/path/to/北京分支/src CLIENT=$CLIENT python3 extract.py
# 2. 增量比对：未变文件复用基线，只为变化文件生成批次
CLIENT=$CLIENT python3 incremental.py
#    会告诉你：复用 N 页、需重跑 M 页、省多少；生成 map/data/$CLIENT/batches.json（仅增量）
# 3. 用 enrich workflow 跑那批增量（很快很便宜）
# 4. 合并（自动并入复用 + 新增量）
CLIENT=$CLIENT python3 merge.py
# 5. 更新 clients.json 的 updatedAt；git push 自动部署
# 6. 确认无误后更新基线：CLIENT=$CLIENT python3 incremental.py --set-baseline
```

## 一句话总结

> 静态层随便重跑，LLM 层只为 diff 付费。每个客户数据按 CLIENT 隔离，互不干扰。
> 拉一次某客户最新代码，几分钟就能在看板上看到它当前的功能全貌。

## 提示

- 不设 `CLIENT` 时默认 `main`（当前主干 master 的数据）。
- 部署是 `git push`（dev 已连 ymzlsy/dev 自动部署），不用 wrangler。
- 看板含客户系统细节，已加 Basic Auth（凭证见 SSOT / progress.txt）。

## 每次更新别忘了：刷一条状态记录

每次对这个看板做改动（加客户、改功能、修问题）后，往 `status.json` 的 `timeline[]` 顶部加一条：
`{"date":"YYYY-MM-DD","type":"新功能|优化|安全|修复","title":"一句话","items":["做了啥","做了啥"]}`
并更新 `current` 里的指标和 `updatedAt`。这样 dev.karaithy.com 的「📊 项目状态」页就会自动刷新。
（实际操作里：你让我更新看板时，我会顺手帮你加这条记录。）
