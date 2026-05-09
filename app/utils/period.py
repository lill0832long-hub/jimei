"""期间计算工具"""


def generate_periods(year, month, count=12):
    """生成从当前月份往前推 count 个月的期间列表

    Args:
        year: 基准年
        month: 基准月 (1-12)
        count: 生成月数，默认12

    Returns:
        [(year, month), ...] 从最早到最近的期间列表
    """
    periods = []
    for i in range(count - 1, -1, -1):
        pm = month - i
        py = year
        while pm <= 0:
            pm += 12
            py -= 1
        periods.append((py, pm))
    return periods


def format_period(year, month):
    """格式化期间为字符串 YYYY-MM"""
    return f"{year}-{month:02d}"


def period_labels(periods):
    """将期间列表转换为标签列表"""
    return [f"{p[0]}-{p[1]:02d}" for p in periods]
