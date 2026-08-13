-- =====================================================================
-- 一次性脚本：重算所有受影响的批号商品当前库存
-- =====================================================================
-- 背景：
--   批号商品导入期初库存时，同一份期初数量被同时写入了：
--     1) jsh_material_initial_stock（期初库存表）
--     2) sub_type='期初' 的入库单（jsh_depot_head + jsh_depot_item）
--   而库存汇总 SQL 原先会把「期初」入库单当作普通入库再加一遍，
--   导致后续发生出入库重算时，期初数量被重复计算。
--
-- 修复后库存公式（与 DepotItemService.getStockByParamWithDepotList 一致，
--   但 inTotal 已排除 sub_type='期初'）：
--   当前库存 = 期初库存表 + 盘点复盘 + 入库(不含期初) - 出库(不含调拨)
--             + 调拨转入 - 调拨转出 + 组装入 - 组装出 + 拆卸入 - 拆卸出
--
-- 本脚本只修正 current_number（数量），不动 current_unit_price（单价）。
-- 幂等：未发生出入库的批号商品，重算结果与当前值一致，不会被改动。
-- =====================================================================

UPDATE jsh_material_current_stock mcs
JOIN (
    SELECT
        d.material_id,
        d.depot_id,
        COALESCE(init.init_stock, 0)
        + COALESCE(cs.check_sum, 0)
        + COALESCE(s.in_total, 0)       - COALESCE(s.out_total, 0)
        + COALESCE(ti.transf_in, 0)     - COALESCE(s.transf_out, 0)
        + COALESCE(s.assem_in, 0)       - COALESCE(s.assem_out, 0)
        + COALESCE(s.disassem_in, 0)    - COALESCE(s.disassem_out, 0) AS correct_number
    FROM (
        -- 受影响集合：存在「期初」入库明细的批号商品（按 商品+仓库 去重）
        SELECT DISTINCT di.material_id, di.depot_id
        FROM jsh_depot_item di
        JOIN jsh_depot_head dh ON dh.id = di.header_id
        JOIN jsh_material m ON m.id = di.material_id AND m.enable_batch_number = '1'
        WHERE dh.sub_type = '期初'
          AND IFNULL(dh.delete_flag, '0') <> '1'
          AND IFNULL(di.delete_flag, '0') <> '1'
    ) d
    LEFT JOIN (
        -- 期初库存表
        SELECT material_id, depot_id, SUM(number) AS init_stock
        FROM jsh_material_initial_stock
        WHERE IFNULL(delete_flag, '0') <> '1'
        GROUP BY material_id, depot_id
    ) init ON init.material_id = d.material_id AND init.depot_id = d.depot_id
    LEFT JOIN (
        -- 盘点复盘变动
        SELECT di.material_id, di.depot_id, SUM(di.basic_number) AS check_sum
        FROM jsh_depot_item di
        JOIN jsh_depot_head dh ON dh.id = di.header_id
        WHERE dh.sub_type = '盘点复盘'
          AND IFNULL(dh.delete_flag, '0') <> '1'
          AND IFNULL(di.delete_flag, '0') <> '1'
        GROUP BY di.material_id, di.depot_id
    ) cs ON cs.material_id = d.material_id AND cs.depot_id = d.depot_id
    LEFT JOIN (
        -- 普通出入库 / 组装 / 拆卸 / 调拨转出（按 depot_id 归集）
        SELECT
            di.material_id,
            di.depot_id,
            SUM(CASE WHEN dh.type = '入库' AND dh.sub_type <> '期初' THEN di.basic_number ELSE 0 END) AS in_total,
            SUM(CASE WHEN dh.type = '出库' AND dh.sub_type <> '调拨' THEN di.basic_number ELSE 0 END) AS out_total,
            SUM(CASE WHEN dh.sub_type = '调拨' THEN di.basic_number ELSE 0 END) AS transf_out,
            SUM(CASE WHEN dh.sub_type = '组装单' AND di.material_type = '组合件' THEN di.basic_number ELSE 0 END) AS assem_in,
            SUM(CASE WHEN dh.sub_type = '组装单' AND di.material_type = '普通子件' THEN di.basic_number ELSE 0 END) AS assem_out,
            SUM(CASE WHEN dh.sub_type = '拆卸单' AND di.material_type = '普通子件' THEN di.basic_number ELSE 0 END) AS disassem_in,
            SUM(CASE WHEN dh.sub_type = '拆卸单' AND di.material_type = '组合件' THEN di.basic_number ELSE 0 END) AS disassem_out
        FROM jsh_depot_item di
        JOIN jsh_depot_head dh ON dh.id = di.header_id
        WHERE IFNULL(dh.delete_flag, '0') <> '1'
          AND IFNULL(di.delete_flag, '0') <> '1'
        GROUP BY di.material_id, di.depot_id
    ) s ON s.material_id = d.material_id AND s.depot_id = d.depot_id
    LEFT JOIN (
        -- 调拨转入（按 another_depot_id 归入目标仓库）
        SELECT di.material_id, di.another_depot_id AS depot_id, SUM(di.basic_number) AS transf_in
        FROM jsh_depot_item di
        JOIN jsh_depot_head dh ON dh.id = di.header_id
        WHERE dh.sub_type = '调拨'
          AND IFNULL(dh.delete_flag, '0') <> '1'
          AND IFNULL(di.delete_flag, '0') <> '1'
        GROUP BY di.material_id, di.another_depot_id
    ) ti ON ti.material_id = d.material_id AND ti.depot_id = d.depot_id
) calc ON calc.material_id = mcs.material_id AND calc.depot_id = mcs.depot_id
SET mcs.current_number = calc.correct_number
WHERE IFNULL(mcs.delete_flag, '0') <> '1'
  AND calc.correct_number <> mcs.current_number;
