# 管伊佳ERP 二次开发记录

> 基于原版 [jshERP v3.6-SNAPSHOT](https://github.com/jishenghua/jshERP) 的定制化修改

---

## 修改总览

| # | 改动项 | 日期 | 涉及范围 |
|---|---|---|---|
| 1 | Docker 化部署 | 2026-08-10 | 基建 |
| 2 | 修复 AWT 验证码异常 | 2026-08-10 | 后端 |
| 3 | 批号功能默认开启 | 2026-08-10 | 前端 |
| 4 | 库存批次明细视图 | 2026-08-10 | 前后端 |
| 5 | 颜色字段改为封装 | 2026-08-10 | 前端 (全站) |
| 6 | **商品列表批次号列** | 2026-08-10 | 前后端 |
| 7 | **importExcel 支持批次号导入** | 2026-08-11 | 后端 |
| 8 | SQL 导入脚本修复 | 2026-08-11 | 脚本 |
| 9 | **导入模板静态文件更新** | 2026-08-11 | 前端 |
| 10 | 期初库存双算 bug 修复 | 2026-08-13 | 后端 + 脚本 |

---

## 改动 1: Docker 化部署

**背景**: 原项目无 Docker 支持，需要手动安装 MySQL、Redis、JDK、编译前后端。

**修改文件**:

| 文件 | 类型 | 说明 |
|---|---|---|
| `docker-compose.yml` | 新建 | 4个服务编排: MySQL 8 + Redis 6.2 + 后端 + 前端 |
| `Dockerfile.backend` | 新建 | 多阶段构建: Maven 3.6.3 编译 → OpenJDK 8 JRE 运行 |
| `Dockerfile.frontend` | 新建 | 多阶段构建: Node 20 编译 → Nginx 1.21 运行 |
| `default.conf` | 新建 | Nginx 代理配置 (/jshERP-boot/ → 后端:9999) |
| `application-docker.yml` | 新建 | Docker 网络环境配置，覆盖默认 application.yml |
| `docker-config/settings.xml` | 新建 | Maven 阿里云镜像加速 |

**关键配置**:
- MySQL 连接: `allowPublicKeyRetrieval=true` (MySQL 8 必须)
- Redis 密码: `1234abcd`
- 后端端口: `9999`，前端端口: `3000`
- 数据持久化: `mysql_data/`、`upload/`、`export/` 目录外挂

---

## 改动 2: 修复 AWT 验证码异常

**问题**: 登录页报"未知异常"，后端日志 `java.lang.NoClassDefFoundError: Could not initialize class sun.awt.X11FontManager`

**根因**: `eclipse-temurin:8-jre-alpine` 容器缺少 `libgcc`、`fontconfig`、`ttf-dejavu`，导致 Java AWT 字体渲染失败，验证码图片无法生成。

**修改文件**: `Dockerfile.backend`

```diff
FROM eclipse-temurin:8-jre-alpine
+ RUN apk add --no-cache libgcc fontconfig ttf-dejavu

- CMD ["java", "-jar", ...]
+ CMD ["java", "-Djava.awt.headless=true", "-jar", ...]
```

---

## 改动 3: 批号功能默认开启

**背景**: 电子元器件行业每个物料都需要批号管理，手动每次开启太麻烦。

**修改文件**: `jshERP-web/src/views/material/modules/MaterialModal.vue`

```diff
- this.edit({})
+ this.edit({ enableBatchNumber: '1' })
```

**影响范围**: 仅新建商品弹窗，默认选中"有"。

---

## 改动 4: 库存批次明细视图

**背景**: 系统原库存报表只有仓库维度汇总，没有批次维度。电子元器件行业需要查看同一物料的不同批次库存分布。

### 后端改动

| 文件 | 改动 |
|---|---|
| `DepotItemVoBatchNumberList.java` | 新增 `depotId`(Long)、`depotName`(String) 字段及 getter/setter |
| `DepotItemMapperEx.xml` - `batchNumberListMap` | 新增 `depot_id`、`depot_name` 映射 |
| `DepotItemMapperEx.xml` - `getBatchNumberList` | 新增 `materialId` 参数; `barCode` 改为可选; 新增 JOIN `jsh_depot`; GROUP BY 加仓库维度; ORDER BY 改为仓库+批次 |
| `DepotItemMapperEx.java` | Mapper 接口新增 `@Param("materialId") Long materialId` |
| `DepotItemService.java` | `getBatchNumberList()` 方法签名新增 `Long materialId` 参数，透传; `getOneBatchNumberStock()` 调用处补 `null` |
| `DepotItemController.java` | 接口新增可选参数 `materialId`; `barCode`/`depotId`/`depotItemId` 改为可选 |

### 前端改动

**修改文件**: `jshERP-web/src/views/report/modules/MaterialDepotStockList.vue`

- 仓库汇总表增加可展开行 (`expandedRowRender`)
- 点击展开后调用 `/depotItem/getBatchNumberList?materialId=xxx&depotId=xxx` 获取批次数据
- 展开区域显示批次明细表: 批次号、库存数量、单位、条码
- 支持缓存策略：已加载的仓库不会重复请求

**影响范围**:
- 库存报表 → 库存详情弹窗 → 点击展开仓库行即可看到批次明细
- 原有出库选批次功能不受影响（`barCode` 参数仍支持）

---

## 改动 5: 颜色字段改为封装

**背景**: 电子元器件行业不需要"颜色"，但需要"封装"（如 0603、SOT-23、LQFP-48）。

**原则**: 仅改前端 UI 标签，不改数据库字段名 (`color` 列保留)，不改后端 API 字段名。

### 修改文件清单 (约27个文件, ~60处)

**商品模块 (4个文件)**:

| 文件 | 改动处 |
|---|---|
| `MaterialList.vue` | 列头 `title: '颜色'` → `'封装'`；搜索框 label + placeholder |
| `MaterialModal.vue` | 表单 label + placeholder + data-intro 提示文字 + 注释 |
| `BatchSetInfoModal.vue` | 表单 label + placeholder |
| `JSelectMaterialModal.vue` | 列头 + 搜索框 label + placeholder |

**单据 Mixins (3个文件)**:

| 文件 | 改动处 |
|---|---|
| `BillListMixin.js` | 13处 `{ title: '颜色', dataIndex: 'color'}` → `'封装'` |
| `BillModalMixin.js` | 1处注释 `型号、颜色、扩展信息` → `封装` |
| `BillDetail.vue` | 14处列头 + 8处导出表头 `,颜色,` → `,封装,` |

**单据弹窗 (14个文件)**:

`PurchaseOrderModal`、`SaleOrderModal`、`PurchaseInModal`、`SaleOutModal`、`PurchaseBackModal`、`SaleBackModal`、`RetailOutModal`、`RetailBackModal`、`OtherInModal`、`OtherOutModal`、`AssembleModal`、`DisassembleModal`、`AllocationOutModal`、`PurchaseApplyModal` — 各 1 处列头

**报表 (11个文件)**:

`MaterialStock`、`InDetail`、`OutDetail`、`InMaterialCount`、`OutMaterialCount`、`AllocationDetail`、`StockWarningReport`、`BuyInReport`、`SaleOutReport`、`InOutStockReport`、`RetailOutReport` — 各 1 处列头 + 1 处导出表头

### 未改动的地方

- CSS 颜色相关注释 (背景颜色、主题颜色、颜色反转等) — 这些是真正的"颜色"
- `data-intro` 中关于 SKU 多属性功能的说明文字 ("配置具体的颜色、尺码之类的组合") — 该功能描述的是 SKU 概念本身
- 所有后端 Java 代码 — 数据库字段名 `color` 不变

---

## 改动 6: 商品列表批次号列

**背景**: 商品信息是日常销售查询最高频的模块，需要快速看到每个物料的批次号分布。

**实现方式**: Service 层后聚合（不改核心查询 SQL）

### 后端改动

| 文件 | 改动 |
|---|---|
| `MaterialVo4Unit.java` | 新增 `batchNumberStr`(String) 字段及 getter/setter |
| `DepotItemMapperEx.java` | 新增 `getBatchSummaryByMaterialIds(List<Long> materialIds)` 接口 |
| `DepotItemMapperEx.xml` | 新增 SQL: `GROUP_CONCAT(DISTINCT batch_number ORDER BY batch_number SEPARATOR ', ')` 按 materialId 聚合 |
| `MaterialService.java` | `select()` 方法中调用聚合查询填充 `batchNumberStr`；新增 `getBatchSummaryMapByMaterialList()` 方法 |

### 前端改动

| 文件 | 改动 |
|---|---|
| `MaterialList.vue` | `defColumns` 新增 `{ title:'批次', dataIndex:'batchNumberStr', width:120, ellipsis:true }`；`defDataIndex` 默认显示 |

### 显示效果

| 物料 | 批次列显示 |
|---|---|
| ADXL345BCCZ-RL7（单批次） | `26+` |
| EPM3512AFC256-7（多批次） | `12+13+` |
| EP4CE40F23C8N（多批次） | `18+, 19+` |
| 无批号物料 | 空白 |

### 设计考量

- **隔离性好**: 新查询独立于核心 `selectByConditionMaterial`，不影响分页性能
- **批量查询**: 一次 SQL 查整页所有物料的批次，非逐行 N+1
- **复用现有模式**: 与 `getCurrentStockMapByMaterialList` 相同的后处理模式

---

## 改动 7: importExcel 支持批次号导入

### 背景

商品物料导入 (`POST /material/importExcel`) 原有的"批号"列 (col 20) 仅支持设置 `enableBatchNumber` 开关 (0/1)，不支持导入具体批号值（如 `22+`、`25+` 等）。

实际业务需求：期初现货导入时需要将每个型号的批号值（`22+`）连同数量（4500）一起写入系统，形成 `depot_head` (期初入库单据) + `depot_item` (含批次号) 的完整记录。

### 改动方案

在 Excel 模板中新增独立"批号"列 (col 27)，仓库库存列整体右移一位 (28+)。导入时：

```
批号列有值（如 "22+"）→ 创建 depot_head (期初入库) + depot_item (含 batch_number) + 直接 SET current_stock
批号列为空 → 保持原有逻辑（直接 SET current_stock，不创建单据），完全向后兼容
```

### 后端改动

| 文件 | 改动 |
|---|---|
| `MaterialWithInitStock.java` | 新增 `batchNumber`(String) 字段，删除旧的 `BatchStock` 内部类和 `batchStockMap` |
| `MaterialService.exportExcel()` | 模板新增"批号"列 (col 27)，仓库库存列从 27 移至 28+ |
| `MaterialService.importExcel()` | 解析时读取 col 27 存入 `batchNumber`；批次模式创建 `depot_head` + `depot_item` |
| `MaterialService.getStockMapCache()` | 还原为原始签名（移除批次格式解析参数），depot 列偏移从 26 改为 27 |
| `MaterialService.parseStockCell()` | 删除（不再需要解析 "批号:数量" 混合格式） |

### Excel 模板格式

```
| ... | 备注(col 26) | 批号(col 27) | 仓库1(col 28) | ... | 深圳(col 31) |
| ... | 原装正品现货  | 22+          |               |     | 4500           |
```

### 幂等性设计

- **重复导入覆盖**：同物料+同仓库下旧的期初 `depot_item` 在导入时自动清理，防止货盘表更新后旧批次残留
- **current_stock 直接 SET**：不用 `updateCurrentStockFun`（该方法内部叠加 `initial_stock` 会导致库存翻倍）
- **initial_stock 保留**：物料维度的期初库存数正常写入，用于商品列表的"初始库存"列显示

---

## 改动 8: SQL 导入脚本修复

### 背景

`scripts/import_stock.py` 是早期的 SQL 管道导入脚本，通过 Python 生成 SQL → 管道直写 MySQL。测试中发现多个问题。

### 修复项

| 问题 | 现象 | 修复 | 位置 |
|------|------|------|------|
| 编码乱码 | 库存全为 0 | 用法注释加 `--default-character-set=utf8mb4` | [import_stock.py L7](file:///opt/jshERP/scripts/import_stock.py#L7) |
| 验证 SQL 中文报错 | 导入完成但验证失败 | 别名改为 ASCII (`'materials'`, `'stock_entries'`) | L251-254 |
| `depot_item` 重复删除 | 明细插入失败 | 删除第 5 节冗余的 DELETE 逻辑 | 已删除 |
| `basic_number` 为 NULL | 报表批号查不到 | INSERT 同时填入 `basic_number = oper_number` | L228-229 |
| 命令行支持 | 每次改硬编码路径 | `sys.argv[1]` 可选传 CSV 路径 | L31 |

### 适用场景

SQL 脚本适合纯数据初始化/迁移场景。日常运营建议使用 API (`POST /material/importExcel`)，走完整业务逻辑（日志、校验、库存重算等）。

---

## 改动 9: 导入模板动态化 + 字段标签修正

### 背景

1. **仓库名硬编码**: 原前端模板下载使用静态文件 `/doc/goods_template.xls`，仓库列写死为"仓库1~仓库5"。系统中新建/重命名仓库后模板不会更新。
2. **字段标签不一致**: 模板中"颜色"应为"封装"（与改动 #5 对齐），"批号"列（开关）与"批号"列（批次值）重名混淆，"型号"缺必填标记。
3. **改动 #7 的遗留问题**: 后端 `exportExcel` 新增了第27列"批号"，但静态模板未同步。

### 改造方案

后端 `exportExcel` 新增 `templateOnly=true` 参数，跳过数据查询，仅输出表头和操作说明，作为纯净导入模板。前端模板下载改为调用此 API，仓库列由后端动态读取数据库实时生成。

### 修改文件

| 文件 | 改动 |
|---|---|
| `MaterialService.java` | 新增重载方法 `exportExcel(..., boolean templateOnly)`: `true` 时跳过数据/副条码/期初库存查询，仅查仓库列表拼表头；`false` 时走原逻辑。原方法签名保留为委托调用。 |
| `MaterialService.java` | `nameStr` 标签修正: `颜色`→`封装`, `型号`→`型号*`, `批号`→`批号开关`（与 col 27"批号"区分） |
| `MaterialController.java` | 新增 `templateOnly` 可选参数（默认 `false`），透传至 Service |
| `MaterialList.vue` | 模板下载 URL 从 `/doc/goods_template.xls` 改为 `/jshERP-boot/material/exportExcel?templateOnly=true`（走同源 Nginx 代理，确保携带 Session Cookie） |

### 模板结构

```
名称* | 规格 | 型号* | 封装 | 品牌 | ... | 序列号 | 批号开关 | ... | 备注 | 批号 | 仓库1 | 仓库2 | 仓库3 | 深圳
```

- 仓库列名由后端 `depotService.getAllList()` 动态生成，新建仓库自动出现
- `模版下载` 与 `导出数据` 共用同一套列头逻辑，永不同步问题

### 影响范围

- 现有导出功能不受影响（`templateOnly` 默认 `false`）
- 不再依赖静态模板文件（`goods_template.xls` 可删除）

---

## 改动 10: 期初库存双算 bug 修复

### 背景

批号商品导入期初库存时，同一份期初数量被同时写入两处：

1. `jsh_material_initial_stock`（期初库存表）
2. `sub_type='期初'` 的入库单（`jsh_depot_head` + `jsh_depot_item`）

而库存汇总 SQL（`getStockByParamWithDepotList` / `getSkuStockByParamWithDepotList`）原先把「期初」入库单当作普通入库再加一遍，导致期初数量被重复计算。

**现象**: AD9364BBCZ 做「其他出库单」数量 2500 后，库存里仍显示 2500。

**根因**: `当前库存 = 期初(2500) + 期初入库单(2500) - 出库(2500) = 2500`，期初被加了两次。

### 修复方案

1. 库存汇总 SQL 排除期初入库单：`inTotal` 增加 `dh.sub_type != '期初'` 条件。
2. `import_stock.py` 补写期初库存表，与 ERP 界面 Excel 导入逻辑保持一致（两条期初导入路径统一）。
3. 新增一次性脚本 `recalc_batch_stock.sql`，重算所有存在期初入库单的批号商品当前库存。

### 修改文件

| 文件 | 改动 |
|---|---|
| `DepotItemMapperEx.xml` | `getSkuStockByParamWithDepotList` / `getStockByParamWithDepotList` 的 `inTotal` 增加 `and dh.sub_type!='期初'` |
| `scripts/import_stock.py` | 新增第 7 步写 `jsh_material_initial_stock`；当前库存汇总改为按本次期初单据 (`header_id`) 统计 |
| `scripts/recalc_batch_stock.sql` | 新增：一次性重算所有存在期初入库单的批号商品 `current_number` |

### 影响范围

- 库存查询（公式计算）与商品列表（`current_stock` 表）对批号期初商品不再重复计算。
- 期初导入的两条路径（ERP 界面 Excel 导入 / `import_stock.py`）行为一致。

---

## 后续可能的改动

- [ ] 批号与有效期解耦（当前开启批号强制显示有效期，需改 `BillModalMixin.js`）
- [ ] 数据库 `color` 字段注释改为"封装"（可选，影响小）
- [ ] 扩展字段1/2/3改为行业常用字段名（如"ESD等级"、"RoHS"等）
- [ ] 型号 → 料号（前端标签全局替换，与颜色→封装同理）
- [ ] 出库批号从弹窗选择改为自由文本输入（目前为食品/药品设计的按有效期选择模式）
