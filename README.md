# 平台功能地图 · 沈阳客运职培管理系统

> 面向**产品经理**的功能理解工具。把前端源码 `intelligent-training-management`（vue-element-admin 体系，909 文件）
> 翻译成「页面 → 功能 → 数据 → 来源」的产品视角，专治"菜单太多、菜单名和页面字段名对不上"。
>
> 与 understand-anything 的区别：那个是**程序员视角**（文件依赖/调用图）；这个是**产品视角**（人话说明 + 字段术语 + 数据血缘）。

## 怎么用

```bash
# 起本地服务
node serve.js          # http://localhost:5566
# 或在 Claude 里 preview_start("platform-map")
```

三种用法：
1. **按页面**：左侧 25 模块中文树 → 点页面 → 右侧看：产品说明（这页干嘛/给谁用）、页面类型、**字段术语对照表**（界面叫法 ↔ 代码字段 ↔ 含义）、**数据从哪来/在哪配**、调用的接口。
2. **按数据接口**：看每个后端接口被哪些页面共用 = "数据在 A 菜单配、在 B 菜单展示"的血缘。
3. **全局搜索**：输中文（告警/考勤/排课…）跨全平台定位页面和接口，不管它叫什么名字。

## 数据怎么来的（两层）

**第 1 层 · 静态提取（`extract.py`）** — 纯脚本、100% 客观：
- 扫 `src/api/**`：每个接口的 url/method/中文注释/文件 description
- 扫 `src/views/**`：每个 .vue 页面 import 了哪些 api、模板里的中文 label/title
- 建立 页面↔接口↔页面 的复用关系（数据血缘骨架）
- 产出 `data/sitemap.json`（25 模块 · 699 页 · 1328 接口函数 · 1167 端点）

**第 2 层 · LLM 增强（workflow + `merge.py`）** — 逐页读源码提炼产品语言：
- 66 批并行 agent，每批读 ~12 页源码 → `data/enriched/batch-*.json`
- `merge.py` 合并 → `data/enriched.json`（694 页：productTitle / summary / pageType / terms / dataSource）

`index.html` 同时加载这两份 JSON 渲染。

## 源码更新 / 换客户分支后怎么重新生成

各客户项目定制不同（不同分支），全量重分析很贵（第 2 层 ~5M token）。
**换分支只为变化的文件付费** —— 详见 **[REGEN.md](./REGEN.md)**。

```bash
# 全量（首次/基准分支）
SRC=/path/to/分支/src python3 extract.py   # 第1层静态提取（秒级，已带文件指纹）
python3 make_batches.py                      # 全量分批
# → 用 enrich workflow 跑 data/batches.json（~38min）
python3 merge.py                             # 合并
python3 incremental.py --set-baseline        # 存为基线

# 增量（换到新客户分支，省 ~90%+）
SRC=/path/to/新分支/src python3 extract.py
python3 incremental.py                        # 只为变化文件生成批次，未变的复用基线
# → 用 workflow 跑 data/batches.json（这次很少）
python3 merge.py
```

## 文件结构

```
platform-map/
├── index.html              # 交互式功能地图（主入口）
├── serve.js                # 本地静态服务 (5566)
├── extract.py              # 第1层：静态结构提取
├── merge.py                # 第2层：合并 LLM 增强结果
└── data/
    ├── sitemap.json        # 第1层产物（结构/接口/血缘）
    ├── batches.json        # LLM 增强的分批清单
    ├── enriched.json       # 第2层产物（合并后的产品语言）
    └── enriched/           # 66 个分批原始结果
```

## 注意

- 菜单是**后端动态下发**的（`getRouters`），前端代码里没有写死完整菜单树。本工具的"模块"是按 `views/` 目录划分的，与后端实际菜单名可能不完全一致 —— 如需 100% 对齐菜单名，需从后端菜单表导出后再做一层映射。
- 第 2 层是 LLM 基于源码的推断，`dataSource` 字段属于"合理推测"，关键结论建议与研发确认。
