# Silent Business Defaults - Final Report

**Scan Date**: 2026-09-15
**Total Findings**: 347
**Core/Pipeline Critical**: 282 findings

## Summary

| Category | Count | Priority |
|----------|-------|----------|
| **CRITICAL** (core/pipeline) | 282 | MUST FIX |
| HIGH | ~50 | Should fix |
| MEDIUM | ~15 | Review |

---

## Top Priority Files to Fix

### 1. `core/workbench_executor.py` - 20+ silent defaults
- Line 106-110: capacity_units, unit_price, variable_cost, fixed_capex, fixed_opex_year
- Line 126-130: revenue, gross_margin, comparable_ps, founder_holding, pledged
- Line 148-162: founder background scores, product metrics

### 2. `pipeline/compute_engine.py` - 40+ silent defaults
- Multiple financial metrics with `.get(key, 0)` defaults
- Lines 320, 321, 334, 345, 346, 376-391, 401, 419, 429, 430, 464, 480, 503-504, 573-579, 588-591, 600-603, 624-626, 781, 1011-1015, 1049-1051, 1089, 1155-1157

### 3. `pipeline/engine_bridge.py` - 20+ silent defaults
- Lines 80, 132, 205-207, 212, 216, 226-227, 251, 268, 456-457, 600-603

### 4. `pipeline/engine_bridge.py` - 20+ silent defaults
- Lines 80, 132, 205-207, 212, 216, 226-227, 251, 268, 456-457, 600-603

### 5. `pipeline/section_writer.py` - 15+ silent defaults
- Lines 682, 683, 949, 996, 1013, 1827, 2010-2015, 2301

### 6. `pipeline/engine_bridge.py` - Multiple
- Lines 80, 132, 205-207, 212, 216, 226-227, 251, 268, 456-457, 600-603

### 7. Core module files
- `core/workbench_executor.py` - 20+ defaults
- `core/conviction.py` - target_price defaults
- `core/peer_matrix.py` - market data defaults
- `core/financial_extract.py` - financial metric defaults
- `core/data_universal.py` - market data defaults
- `core/data_contract.py` - financial data defaults
- `pipeline/compute_engine.py` - 40+ defaults
- `pipeline/engine_bridge.py` - 20+ defaults

---

## Fix Strategy

### Phase 1: Critical Core Files (Week 1)
1. `core/workbench_executor.py` - Replace all `.get(key, default)` with `accessor.require()` or `accessor.assume()`
2. `pipeline/compute_engine.py` - Critical financial calculations
3. `pipeline/engine_bridge.py` - Bridge between pipeline and engine

### Phase 2: Pipeline Files (Week 2)
1. `pipeline/compute_engine.py` - 40+ defaults
2. `pipeline/engine_bridge.py` - 20+ defaults
3. `pipeline/section_writer.py` - 15+ defaults

### Phase 3: Core Modules (Week 2-3)
1. `core/workbench_executor.py` - 20+ defaults
2. `core/financial_extract.py` - financial metrics
3. `core/conviction.py` - target prices
3. `core/peer_matrix.py` - market data

---

## Fix Pattern

```python
# BEFORE (Silent Business Default)
capacity = float(data.get("capacity", 50000))
price = data.get("price", 0)

# AFTER - using DataAccessor
accessor = DataAccessor(data, asset="company", source="2025_annual_report")
capacity = accessor.require("capacity")  # Raises if missing
price = accessor.require("price")  # Raises if missing

# For optional with explicit assumption
margin = accessor.assume("gross_margin", default=0.25, source="industry_average")

# For scenario analysis
price = accessor.scenario("target_price", value=300, scenario="base_case")

# For derived values
fcf = accessor.derive("fcf", formula="fcf = fcf_2024 * 1.1", parents=[fcf_2024])
```

---

## Priority Fix Order

### Week 1: Critical Pipeline Core
1. `pipeline/compute_engine.py` - 40+ fixes
2. `pipeline/engine_bridge.py` - 20+ fixes
3. `pipeline/workbench_executor.py` - 20+ fixes

### Week 2: Core Modules
1. `core/workbench_executor.py` - 20+ fixes
2. `core/financial_extract.py` - 20+ fixes
3. `core/conviction.py` - target price defaults
4. `core/peer_matrix.py` - market data

### Week 3: Pipeline Pipeline Files
1. `pipeline/compute_engine.py` - remaining
2. `pipeline/engine_bridge.py` - remaining
3. `pipeline/section_writer.py` - 15+ fixes

---

## Verification Checklist

After each file fix:
- [ ] All `.get(key, default)` replaced with `accessor.require()` or `accessor.assume()`
- [ ] No silent business defaults remain in the file
- [ ] Tests pass: `pytest tests/test_gate_095_fixes.py -v`
- [ ] Pipeline runs without Gate score regression
- [ ] Gate score >= 0.90 on test reports

---

## Next Steps

1. **Week 1**: Fix `pipeline/compute_engine.py` + `pipeline/engine_bridge.py`
2. **Week 2**: Fix `pipeline/workbench_executor.py` + `core/workbench_executor.py`
3. **Week 3**: Fix remaining pipeline/core files
4. **Integration Test**: Full pipeline run with Gate score >= 0.90
