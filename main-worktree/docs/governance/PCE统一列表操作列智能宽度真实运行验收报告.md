# PCE统一列表操作列智能宽度真实运行验收报告

- 版本：`V1.14.2.8.4.27.2.39`
- 验收日期：`2026-08-11`
- 验收方式：Codex In-app Browser 真实页面、真实后端 Provider、DOM 尺寸读取与全页截图
- 证据目录：`frontend/test-results/V1.14.2.8.4.27.2.39/`
- Browser Human Acceptance: PASS

## 1. 供应商资料

- URL：`http://localhost:5173/#/master-data/suppliers`
- 页面标题：`供应商数据`
- 列表区域名称：`供应商列表`
- 操作列位置：同一 `el-table` 最后一列，固定右侧，四档视口右边界误差均为 `0px`
- 按钮数量：`1`；按钮：`查看`
- 实际宽度：`96px`
- 期望结果：单动作列处于 80–100px，按钮完整，无大块空白
- 实际结果：符合
- 截图证据：`suppliers-1440x900.png`、`suppliers-1024x768.png`、`suppliers-768x1024.png`、`suppliers-375x812.png`

## 2. 物料资料

- URL：`http://localhost:5173/#/master-data/materials`
- 页面标题：`物料数据`
- 列表区域名称：`物料主数据列表`
- 操作列位置：同一 `el-table` 最后一列，固定右侧，四档视口右边界误差均为 `0px`
- 按钮数量：`2`；按钮：`查看/编辑`
- Runtime宽度：`152px`；浏览器实际宽度：`157px`（表格布局取整/分配后仍处于治理区间）
- 期望结果：双动作列处于 120–160px，按钮完整
- 实际结果：符合
- 截图证据：`materials-1440x900.png`、`materials-1024x768.png`、`materials-768x1024.png`、`materials-375x812.png`

## 3. 供应商物料价格

- URL：`http://localhost:5173/#/foundation/erp/supplier-material-prices`
- 页面标题：`供应商物料价格`
- 列表区域名称：供应商物料价格列表
- 操作列位置：同一 `el-table` 最后一列，固定右侧，四档视口右边界误差均为 `0px`
- 按钮数量：`3`；按钮：`查看/编辑/停用`
- 实际宽度：`208px`
- 期望结果：三动作列自动扩展，375px 下三个按钮仍完整显示
- 实际结果：符合
- 截图证据：`supplier-material-prices-1440x900.png`、`supplier-material-prices-1024x768.png`、`supplier-material-prices-768x1024.png`、`supplier-material-prices-375x812.png`

## 4. 物料供应商关系

- URL：`http://localhost:5173/#/foundation/erp/material-suppliers`
- 页面标题：`物料供应商关系`
- 列表区域名称：物料供应商关系事实列表
- 操作列位置：同一 `el-table` 最后一列，固定右侧，四档视口右边界误差均为 `0px`
- 按钮数量：`1`；按钮：`查看`
- 实际宽度：`96px`
- 期望结果：事实页只读动作自动使用 compact 宽度
- 实际结果：符合
- 截图证据：`material-suppliers-1440x900.png`、`material-suppliers-1024x768.png`、`material-suppliers-768x1024.png`、`material-suppliers-375x812.png`

## 5. 供应商价格分析

- URL：`http://localhost:5173/#/foundation/erp/supplier-price-analysis`
- 页面标题：`供应商价格分析`
- 列表区域名称：`历史价格明细`、`供应商价格比较`
- 操作列位置：两个列表均固定右侧，四档视口右边界误差均为 `0px`
- 按钮数量：每个列表 `1`；按钮：`查看`
- 实际宽度：两个列表均为 `96px`
- 期望结果：只读分析列表自动缩小，不产生固定大宽度空白
- 实际结果：符合
- 截图证据：`supplier-price-analysis-1440x900.png`、`supplier-price-analysis-1024x768.png`、`supplier-price-analysis-768x1024.png`、`supplier-price-analysis-375x812.png`

## 6. 供应商核价智能辅助

- URL：`http://localhost:5173/#/scm/price-review-assistant`
- 页面标题：`供应商核价智能辅助`
- 列表区域名称：`供应商比较`
- 操作列位置：同一 `el-table` 最后一列，固定右侧，四档视口右边界误差均为 `0px`
- 按钮数量：`1`；按钮：`查看`
- 实际宽度：`96px`
- 期望结果：复用价格比较 Metadata，操作列自动缩小
- 实际结果：符合
- 截图证据：`price-review-assistant-1440x900.png`、`price-review-assistant-1024x768.png`、`price-review-assistant-768x1024.png`、`price-review-assistant-375x812.png`

## 7. 响应式汇总

| 视口 | 页面数 | 按钮完整 | 操作列固定 | 大量空白 | 结果 |
|---|---:|---|---|---|---|
| `1440x900` | 6 | 是 | 是 | 否 | PASS |
| `1024x768` | 6 | 是 | 是 | 否 | PASS |
| `768x1024` | 6 | 是 | 是 | 否 | PASS |
| `375x812` | 6 | 是 | 是 | 否 | PASS |

浏览器控制台错误：`0`。24 个页面/视口组合均读取到 `ActionColumnWidthRuntime`；动作按钮数与 Schema Action Contract 数量一致。
