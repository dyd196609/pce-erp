# PCE统一列表操作列智能宽度规范

- 规则编号：`PCE-LIST-ACTION-WIDTH-001`
- 生效版本：`V1.14.2.8.4.27.2.39`
- 上位规范：`PCE-ERP智能化开发总纲.md`
- 适用范围：使用 `PceEnterpriseListTable` 的企业级列表

## 1. 唯一运行入口

操作列宽度由既有 `tableActionColumnEngine.js` 扩展出的 `ActionColumnWidthRuntime` 统一解析。动作链固定为：

```text
Metadata Registry -> Schema actionPolicy -> ListActionColumnRuntime -> ActionColumnWidthRuntime -> PceEnterpriseListTable
```

页面不得直接声明动作按钮、按钮名称或固定操作列宽度，不得复制表格组件或建立第二套列表 Runtime。

## 2. 宽度规则

| 可见动作数 | 密度 | 默认宽度 | 约束 |
|---:|---|---:|---|
| 1 | compact | 96px | 必须处于 80–100px |
| 2 | normal | 152px | 必须处于 120–160px |
| 3及以上 | expanded | 按动作数量和最长标签扩展 | 不得使用固定大宽度 |

长标签由 Runtime 根据字符长度扩展；最终宽度限制在 88–520px。空数据列表使用 Schema Action Contract 作为回退事实，不能依赖首行业务数据。

## 3. 动作来源

动作编码、名称、顺序和数量来自 Metadata/Schema 的 `actionPolicy`。`listActionColumnRuntime.js` 的受治理动作目录将动作编码解析为 Action Contract；页面只处理 `row-action` 结果，不得在 template 中重复创建通用查看、编辑、删除或启停按钮。

供应商正式主数据页面当前为只读主数据入口，Schema 声明 `readonlyMaster`，仅展示“查看”。物料主数据使用 `master`，展示“查看/编辑”；配置类页面使用 `config`，展示“查看/编辑/启停”。

## 4. 响应式与滚动

操作列继续属于同一个 `el-table`，固定在右侧；横向滚动所有权仍属于表格内部。1440px、1024px、768px、375px 均必须保持操作列按钮完整、右侧固定且宽度与 Runtime 输出一致。

## 5. 验收门禁

- `ACTION-COLUMN-WIDTH-001`：1/2/3+动作宽度符合区间与自动扩展规则。
- `LIST-ACTION-SOURCE-001`：动作来自 Schema Action Contract。
- `NO-HARDCODE-ACTION-WIDTH-001`：目标页面没有固定操作列宽度。
- `METADATA-DRIVEN-LIST-001`：列与动作由 Metadata Registry 驱动。
- `REAL-BROWSER-EVIDENCE-001`：六个目标页面完成真实浏览器与截图验收。

任一门禁失败时禁止签发 READY。
