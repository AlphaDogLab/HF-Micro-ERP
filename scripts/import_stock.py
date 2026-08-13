#!/usr/bin/env python3
"""
管伊佳ERP 现货库存导入脚本
读取 CSV → 清洗数据 → 生成 SQL → 通过管道导入 MySQL

用法:
    python3 import_stock.py | docker exec -i jsh-mysql mysql -uroot -p123456 --default-character-set=utf8mb4 jsh_erp

导入逻辑:
    0. 创建唯一索引(幂等), 确保型号不可重复
    1. 创建"深圳"仓库 / "IC类"分类
    2. 清理旧导入数据 (保留手工操作记录)
    3. 创建"期初入库"单据 (depot_head)
    4. UPSERT 物料 (型号唯一, 重复则更新封装/品牌/备注)
    5. 插入 depot_item (含批次号)
    6. 汇总写入 jsh_material_initial_stock (期初库存表)
    7. 汇总写入 jsh_material_current_stock (当前库存)
    8. 验证结果

幂等性:
    - 重复执行不会创建重复物料 (型号唯一)
    - 重复执行会先清理旧导入再创建新记录
    - 手工操作的出入库记录不受影响
    - 库存汇总覆盖式更新 (以最近一次导入为准)
"""

import csv
import re
import sys
from datetime import datetime

CSV_FILE = sys.argv[1] if len(sys.argv) > 1 else "/opt/深圳晶科芯现货库存0808.csv"
TENANT_ID = 63
UNIT_ID = 15    # "个"的ID
UNIT_NAME = "个"

# ============================================================
# 品牌标准化映射
# ============================================================
def standardize_brand(raw: str) -> str:
    """从 厂商 字段提取标准化品牌名"""
    raw = raw.strip()

    # 品牌名标准化映射 (CSV中出现的需统一)
    NAME_MAP = {
        "SILICON": "Silicon Labs",
        "SILICON LABS": "Silicon Labs",
        "SAMSUNG": "Samsung",
        "ADI": "ADI",
        "TI": "TI",
        "NXP": "NXP",
        "ST": "ST",
        "AKM": "AKM",
        "ONSEMI": "onsemi",
    }

    if "/" in raw:
        brand = raw.split("/")[0].strip()
    elif " " in raw:
        # 空格分隔的品牌如 "MURATA 村田"、"SAMSUNG 三星"
        brand = raw.split(" ")[0].strip()
    else:
        # 无分隔符的如 "Nexperia安世"、"Greenliant绿芯存储"
        m = re.match(r"^([A-Za-z0-9\-]+)", raw)
        if m:
            brand = m.group(1)
        else:
            brand = raw

    brand = brand.strip()

    # 查映射表
    upper = brand.upper()
    if upper in NAME_MAP:
        return NAME_MAP[upper]

    # 其他品牌首字母大写
    return brand[0].upper() + brand[1:].lower() if len(brand) > 1 else brand.upper()


def clean_batch(batch_raw: str) -> str:
    """清除Excel导出引号 `="26+"` → `26+`"""
    b = batch_raw.strip()
    b = re.sub(r'^="', '', b)
    b = re.sub(r'"$', '', b)
    return b


def escape_sql(s: str) -> str:
    """SQL字符串转义"""
    if s is None:
        return "NULL"
    s = s.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


def escape_nullable(s: str) -> str:
    if s is None or s == "":
        return "NULL"
    return escape_sql(s)


# ============================================================
# 生成 SQL
# ============================================================
def generate_sql():
    print("-- ========================================")
    print("-- 管伊佳ERP 现货库存导入 SQL")
    print(f"-- 生成时间: {datetime.now()}")
    print("-- ========================================")
    print()

    # ----- 解析 CSV -----
    products = []
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pn = row["型号"].strip().strip('"')  # 型号可能被引号包裹
            qty = int(row["数量"].strip())
            pkg = row["封装"].strip()
            batch = clean_batch(row["批号"])
            brand = standardize_brand(row["厂商"])
            remark = row["说明"].strip()
            warehouse = row["仓库"].strip()
            products.append({
                "pn": pn,
                "qty": qty,
                "pkg": pkg,
                "batch": batch,
                "brand": brand,
                "remark": remark,
                "warehouse": warehouse,
            })

    print(f"-- 共 {len(products)} 条记录")
    print()

    # ----- 0. 数据库迁移(幂等) -----
    print("-- 0. 创建唯一索引 (幂等, 已存在则跳过)")
    print(f"SET @sql = IF((SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema='jsh_erp' AND table_name='jsh_material' AND index_name='uk_model_tenant') = 0, 'ALTER TABLE jsh_material ADD UNIQUE INDEX uk_model_tenant (model, tenant_id)', 'SELECT 1');")
    print("PREPARE stmt FROM @sql;")
    print("EXECUTE stmt;")
    print("DEALLOCATE PREPARE stmt;")
    print()
    print(f"SET @sql = IF((SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema='jsh_erp' AND table_name='jsh_material_extend' AND index_name='uk_ext_material_barcode') = 0, 'ALTER TABLE jsh_material_extend ADD UNIQUE INDEX uk_ext_material_barcode (material_id, bar_code, tenant_id)', 'SELECT 1');")
    print("PREPARE stmt FROM @sql;")
    print("EXECUTE stmt;")
    print("DEALLOCATE PREPARE stmt;")
    print()

    # ----- 1. 创建仓库 -----
    print("-- 1. 创建深圳仓库")
    print("INSERT INTO jsh_depot (name, address, warehousing, truckage, type, sort, remark, principal, enabled, tenant_id, delete_Flag, is_default)")
    print(f"SELECT '深圳', '深圳', 0, 0, 0, '99', '期初库存导入', 131, 1, {TENANT_ID}, '0', 0")
    print("WHERE NOT EXISTS (SELECT 1 FROM jsh_depot WHERE name='深圳' AND tenant_id=" + str(TENANT_ID) + ");")
    print("SET @depot_id = (SELECT id FROM jsh_depot WHERE name='深圳' AND tenant_id=" + str(TENANT_ID) + ");")
    print(f"SELECT @depot_id AS depot_id;")
    print()

    # ----- 2. 创建分类 -----
    print("-- 2. 创建IC类分类")
    print("INSERT INTO jsh_material_category (name, category_level, sort, serial_no, remark, create_time, tenant_id, delete_flag)")
    print(f"SELECT 'IC类', NULL, '10', 'IC', '库存导入自动创建', NOW(), {TENANT_ID}, '0'")
    print(f"WHERE NOT EXISTS (SELECT 1 FROM jsh_material_category WHERE name='IC类' AND tenant_id={TENANT_ID});")
    print("SET @category_id = (SELECT id FROM jsh_material_category WHERE name='IC类' AND tenant_id=" + str(TENANT_ID) + ");")
    print(f"SELECT @category_id AS category_id;")
    print()

    # ----- 3. 清理旧导入数据 -----
    print("-- 3. 清理旧导入数据 (保留手工操作的出入库记录)")
    print("DELETE FROM jsh_depot_item")
    print("WHERE depot_id = @depot_id")
    print(f"  AND tenant_id = {TENANT_ID}")
    print("  AND header_id IN (SELECT id FROM jsh_depot_head WHERE sub_type='期初' AND tenant_id=" + str(TENANT_ID) + ");")
    print("DELETE FROM jsh_depot_head")
    print("WHERE sub_type='期初'")
    print(f"  AND tenant_id = {TENANT_ID};")
    print()

    # ----- 4. 创建期初入库单据头 -----
    bill_no = f"QC{datetime.now().strftime('%Y%m%d%H%M%S')}"
    print("-- 4. 期初入库单据")
    print("INSERT INTO jsh_depot_head (type, sub_type, number, create_time, oper_time, total_price, status, source, tenant_id, delete_flag)")
    print(f"VALUES ('入库', '期初', {escape_sql(bill_no)}, NOW(), NOW(), 0, '1', '0', {TENANT_ID}, '0');")
    print("SET @header_id = LAST_INSERT_ID();")
    print(f"SELECT @header_id AS header_id, '{bill_no}' AS bill_no;")
    print()

    # ----- 5. 按唯一型号插入物料 (UPSERT) -----
    # 去重
    unique_pns = {}
    for p in products:
        pn = p["pn"]
        if pn not in unique_pns:
            unique_pns[pn] = p

    print(f"-- 5. 插入/更新 {len(unique_pns)} 种物料 (型号唯一, 重复则更新)")
    print()

    for i, (pn, p) in enumerate(unique_pns.items()):
        var_mat = f"@mat_id_{i}"
        var_ext = f"@ext_id_{i}"

        print(f"-- 物料 #{i+1}: {pn}")
        print("INSERT INTO jsh_material (name, model, color, brand, mfrs, category_id, unit_id, unit, weight, expiry_num, enabled, enable_serial_number, enable_batch_number, remark, tenant_id, delete_flag)")
        print(f"VALUES ({escape_sql(pn)}, {escape_sql(pn)}, {escape_nullable(p['pkg'])}, {escape_sql(p['brand'])}, {escape_sql(p['brand'])}, @category_id, {UNIT_ID}, {escape_sql(UNIT_NAME)}, 0, 0, 1, '0', '1', {escape_nullable(p['remark'])}, {TENANT_ID}, '0')")
        print("ON DUPLICATE KEY UPDATE")
        print(f"  color = VALUES(color), brand = VALUES(brand), mfrs = VALUES(mfrs), remark = VALUES(remark), enabled = 1, delete_flag = '0';")
        # ON DUPLICATE KEY UPDATE 时 LAST_INSERT_ID 不可靠, 统一用 SELECT 获取 ID
        print(f"SET {var_mat} = (SELECT id FROM jsh_material WHERE model={escape_sql(pn)} AND tenant_id={TENANT_ID} AND delete_flag='0');")

        # 价格扩展 (同样 UPSERT)
        print("INSERT INTO jsh_material_extend (material_id, bar_code, commodity_unit, purchase_decimal, commodity_decimal, wholesale_decimal, low_decimal, tenant_id, delete_flag)")
        print(f"VALUES ({var_mat}, {escape_sql(pn)}, {escape_sql(UNIT_NAME)}, 0, 0, 0, 0, {TENANT_ID}, '0')")
        print("ON DUPLICATE KEY UPDATE")
        print(f"  commodity_unit = VALUES(commodity_unit), delete_flag = '0';")
        print(f"SET {var_ext} = (SELECT id FROM jsh_material_extend WHERE material_id={var_mat} AND bar_code={escape_sql(pn)} AND tenant_id={TENANT_ID});")
        print()

    print(f"-- 6. 插入 {len(products)} 条入库明细")
    print()

    for i, p in enumerate(products):
        pn_idx = list(unique_pns.keys()).index(p["pn"])
        var_mat = f"@mat_id_{pn_idx}"
        var_ext = f"@ext_id_{pn_idx}"

        print(f"-- 明细 #{i+1}: {p['pn']} 批号={p['batch']} 数量={p['qty']}")
        print("INSERT INTO jsh_depot_item (header_id, material_id, material_extend_id, depot_id, oper_number, basic_number, unit_price, all_price, batch_number, material_unit, material_type, remark, tenant_id, delete_flag)")
        print(f"VALUES (@header_id, {var_mat}, {var_ext}, @depot_id, {p['qty']}, {p['qty']}, 0, 0, {escape_sql(p['batch'])}, {escape_sql(UNIT_NAME)}, NULL, NULL, {TENANT_ID}, '0');")
        print()

    # ----- 7. 写入期初库存表 (与 ERP 界面导入一致) -----
    print("-- 7. 写入期初库存表 jsh_material_initial_stock")
    print("DELETE FROM jsh_material_initial_stock")
    print(f"WHERE depot_id = @depot_id AND tenant_id = {TENANT_ID};")
    print()
    print("INSERT INTO jsh_material_initial_stock (material_id, depot_id, number, tenant_id, delete_flag)")
    print("SELECT di.material_id, di.depot_id, SUM(di.basic_number), di.tenant_id, '0'")
    print("FROM jsh_depot_item di")
    print("WHERE di.header_id = @header_id")
    print("GROUP BY di.material_id, di.depot_id, di.tenant_id;")
    print()

    # ----- 8. 更新当前库存汇总 (以本次期初单据为准) -----
    print("-- 8. 更新商品库存汇总")
    print("DELETE FROM jsh_material_current_stock")
    print(f"WHERE depot_id = @depot_id AND tenant_id = {TENANT_ID};")
    print()
    print("INSERT INTO jsh_material_current_stock (material_id, depot_id, current_number, tenant_id, delete_flag)")
    print("SELECT di.material_id, di.depot_id, SUM(di.basic_number), di.tenant_id, '0'")
    print("FROM jsh_depot_item di")
    print("WHERE di.header_id = @header_id")
    print("GROUP BY di.material_id, di.depot_id, di.tenant_id;")
    print()

    # ----- 9. 验证 -----
    print("-- 9. 验证结果")
    print("SELECT 'materials' AS item, COUNT(*) AS cnt FROM jsh_material WHERE tenant_id=" + str(TENANT_ID) + ";")
    print("SELECT 'stock_entries' AS item, COUNT(*) AS cnt FROM jsh_material_current_stock WHERE tenant_id=" + str(TENANT_ID) + ";")
    print("SELECT 'depot_items' AS item, COUNT(*) AS cnt FROM jsh_depot_item WHERE header_id=@header_id;")
    print("SELECT 'total_qty' AS item, SUM(oper_number) AS cnt FROM jsh_depot_item WHERE header_id=@header_id;")

    print()
    print("-- 导入完成!")


if __name__ == "__main__":
    generate_sql()
