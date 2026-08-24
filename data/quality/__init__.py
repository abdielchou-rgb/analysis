"""Data Quality Gateway

分层校验体系：
  1. format_validator — 格式校验（类型/单位/时间戳）
  2. range_validator — 范围校验（合理值域）
  3. cross_validator — 交叉验证（多源冲突判定）

用法:
    from data.quality import QualityGateway
    qg = QualityGateway()
    result = qg.validate(data_points, source="eastmoney")
    if result.passed:
        # 数据可用
    else:
        # 数据被标记或阻断
"""
from data.quality.validators import (
    FormatValidator, RangeValidator, CrossValidator,
    QualityGateway, ValidationResult, ValidationIssue,
    quality_gateway,
)
