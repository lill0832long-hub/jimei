"""Database module: fixed_asset domain"""

from .connection import get_conn, transaction, DB_PATH, clear_query_cache

def create_fixed_asset(ledger_id, asset_code, asset_name, original_value,
                       useful_life_months, category_id=None, purchase_date=None,
                       residual_rate=0.05, department=None, employee=None,
                       location=None, source_type='purchase',
                       depreciation_method='straight_line'):
    """创建固定资产卡片"""
    residual_value = int(original_value * residual_rate)
    net_value = original_value
    conn = get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO fixed_assets
            (ledger_id, asset_code, asset_name, category_id, purchase_date,
             original_value, residual_rate, residual_value, useful_life_months,
             depreciation_method, accumulated_depreciation, net_value,
             department, employee, location, source_type, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (ledger_id, asset_code, asset_name, category_id, purchase_date,
              original_value, residual_rate, residual_value, useful_life_months,
              depreciation_method, 0, net_value,
              department, employee, location, source_type, 'in_use'))
        asset_id = cur.lastrowid
        conn.commit()
        return asset_id
    finally:
        conn.close()
    clear_query_cache()

def get_fixed_assets(ledger_id, status=None):
    """获取固定资产列表"""
    conn = get_conn()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM fixed_assets WHERE ledger_id = ? AND status = ? ORDER BY asset_code",
                (ledger_id, status)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM fixed_assets WHERE ledger_id = ? ORDER BY asset_code",
                (ledger_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_fixed_asset(asset_id):
    """获取单个资产"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM fixed_assets WHERE id = ?", (asset_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def calculate_depreciation(asset_id, year, month):
    """计算单资产月折旧额（返回分值）"""
    asset = get_fixed_asset(asset_id)
    if not asset:
        return 0
    if asset['status'] != 'in_use':
        return 0
    remaining = asset['original_value'] - asset['accumulated_depreciation']
    residual = asset['residual_value']
    if remaining <= residual:
        return 0
    
    method = asset['depreciation_method']
    original = asset['original_value']
    life_months = asset['useful_life_months']
    
    if method == 'straight_line':
        monthly = (original - residual) / life_months
    elif method == 'double_declining':
        # 双倍余额递减法
        months_used = asset['accumulated_depreciation'] / ((original - residual) / life_months) if (original - residual) > 0 else 0
        remaining_life = life_months - months_used
        if remaining_life <= 24:
            # 最后两年改直线法
            monthly = (remaining - residual) / remaining_life if remaining_life > 0 else 0
        else:
            monthly = remaining * (2.0 / life_months)
    elif method == 'sum_of_years':
        # 年数总和法
        total_years = life_months / 12
        sum_years = total_years * (total_years + 1) / 2
        months_used = asset['accumulated_depreciation'] / ((original - residual) / life_months) if (original - residual) > 0 else 0
        current_year = int(months_used / 12) + 1
        remaining_years = total_years - current_year + 1
        monthly = (original - residual) * (remaining_years / sum_years) / 12
    else:
        monthly = (original - residual) / life_months
    
    # 确保不超过剩余可折旧金额
    depreciable = remaining - residual
    monthly = min(monthly, depreciable)
    return int(round(monthly))

def batch_calculate_depreciation(ledger_id, year, month):
    """批量计提折旧，返回 [(asset_id, amount), ...]"""
    assets = get_fixed_assets(ledger_id, status='in_use')
    results = []
    for asset in assets:
        amount = calculate_depreciation(asset['id'], year, month)
        if amount > 0:
            results.append((asset['id'], amount))
    return results

def dispose_asset(asset_id, dispose_type, proceeds=0):
    """资产处置"""
    asset = get_fixed_asset(asset_id)
    if not asset:
        return None

    net_value = asset['original_value'] - asset['accumulated_depreciation']
    gain_loss = proceeds - net_value  # 正数=收益，负数=损失

    conn = get_conn()
    try:
        conn.execute("""
            UPDATE fixed_assets SET status = 'disposed', net_value = 0, updated_at = datetime('now','localtime')
            WHERE id = ?
        """, (asset_id,))
        conn.execute("""
            INSERT INTO fa_changes (asset_id, change_type, change_date, old_value, new_value, reason)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (asset_id, f'dispose_{dispose_type}',
              f"{year}-{month:02d}-01" if 'year' in dir() else None,
              net_value, f"处置方式:{dispose_type}, 收入:{proceeds}"))
        conn.commit()
    finally:
        conn.close()
    clear_query_cache()

    return {
        'asset_id': asset_id,
        'original_value': asset['original_value'],
        'accumulated_depreciation': asset['accumulated_depreciation'],
        'net_value': net_value,
        'proceeds': proceeds,
        'gain_loss': gain_loss
    }
