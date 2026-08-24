# V51 Code Audit Report

**Project**: 1hao Fen Xi Shi V51
**Audit Date**: 2026-07-24
**Actual Code Path**: E:/1hao-analyst-v51/
**Audit Scope**: 47 Python files + YAML config + docs, approx 4,500 lines
**Audit Method**: Structured per-module review, 5-dimension scoring (Correctness/Architecture/Code Quality/Test/Security)

---

## Overall Scores

| Dimension | Score | Notes |
|-----------|-------|-------|
| Architecture Consistency | 4.0/5 | T0->T1->T2->T3 clear, core rules followed |
| Code Correctness | 3.5/5 | Import path mix, data flow breaks, error handling gaps |
| Code Quality | 3.5/5 | Some modules long, mixed old/new paths |
| Test Coverage | 4.0/5 | 47 tests cover core paths |
| Security | 4.0/5 | SQLite local-only, XSS low threat |
| **Composite** | **3.8/5** | Excellent methodology, residual engineering issues |

## 1. Entry Layer
### 1.1 main.py (144 lines) - Conditional Pass
| ID | Type | Severity | Issue | Fix |
|----|------|----------|-------|-----|
| M01 | Correctness | Med | verify: len(applied)/len(applied) same | Use len(rules) |
| M02 | Arch | Low | benchmark missing args | Add --generated/--benchmark |
| M03 | Correctness | Med | Typo: ore vs orc | Fix to orc |
**P0**: M01/M03 runtime errors

### 1.2 workflow.py (83 lines) - Conditional Pass
| ID | Type | Severity | Issue | Fix |
|----|------|----------|-------|-----|
| W01 | Correctness | HIGH | from .core.conviction - not a package | from core.conviction |
| W02 | Arch | Med | _scaffold_to_text() coupled | Extract standalone |
| W03 | Correctness | Med | HypothesisVerifier() unused | Remove or integrate |
**P0**: W01 prevents runtime execution

## 2. core/ - Methodology
### 2.1 models.py (183) - Pass. C01: from_dict incomplete (P1). C02: no edge tests (P1).
### 2.2 protocol.py (172) - Pass. P01: duplicate ResearchOrchestrator (L118+L155) (P1).
### 2.3 argument.py (173) - Conditional. A01: dim ID mismatch with YAML (P1). A02: hardcoded keywords (P2).
### 2.4 style.py (105) - Pass. Reduced 10->3 rules wisely. S01: sentence splitting not robust (P2).
### 2.5 verify.py (123) - Conditional. V01: from data import pipeline implicit (P1). V02: keyword-only SAC match (P1).
### 2.6 conviction.py (135) - Conditional. CV01: V30 path via sys.path (HIGH). CV02: empty matrix on V30 miss (P1).
### 2.7 input.py (21) - Pass. Only 3/7 style maps. P2.
### 2.8 edit.py (291) - Pass. Imports OK. 6-type classification correct. P1.
### 2.9 learn.py (99) - Pass. Closed edit->learn->inject loop. P2.
### 2.10 evidence.py (25) - Pass. L0-L9 correct.
### 2.11 audit.py (43) - Pass. AU01: hardcoded data source map (P2).
### 2.12 metrics.py (223) - Conditional. MT01: SQLite f-string LIKE (P2). MT02: timezone boundary (P2).
### 2.13 plugin.py (187) - Pass. Complete SDK. Unused by V51. P2.
### 2.14 sacs/ (4 YAML) - Pass. SY01: evidence_min vs min_sources unclear (P2).
### 2.15 styles/ (2 YAML+1 py) - Conditional. ST01: 7 inst, 2 YAML (P1). ST02: STYLES_DIR -> T1_knowledge/ not found (**P0**).

## 3. data/ - Data Layer
### 3.1 engine.py (76) - Conditional. DE01: silent except (P1). DE02: no key check (P1). DE03: singleton hard to mock (P1).
### 3.2 verifier.py (73) - Pass. NLP hypothesis parsing. consensus empty. P2.
### 3.3 orchestrator.py (115) - Pass. DO01: silent import fail (P2). DO02: field uncertainty (P2).
### 3.4 akshare_connector.py (17) - **FAIL**. AK01: from schema_v50 -> from core.models (**P0**). AK02: from T1_knowledge -> from data.engine (**P0**).
### 3.5 east_money_connector.py (103) - **FAIL**. EM01: from schema_v50 -> from core.models (**P0**). EM02: no timeout (P2).

## 4. compute/
### __init__.py (68) - Conditional. CO01: V30 path confirm (P1). CO02: dataclasses.asdict() fragile (P2).

## 5. export/
### __init__.py (66) - Conditional. EX01: V30 sys.path dep (P1).
### expandable_report.py (104) - Conditional. XR01: f-string HTML XSS (P1). XR02: chart_path injection (P2).

## 6. tests/
### run_all.py (132) - Pass. T01: relative import path (P1). 47 tests across core.
### test_e2e.py (116) - Pass. 3 benchmarks. TE01: or True no-op (P1).
### test_sac_gate.py (118) - Pass. 6 tests, all paths.
### test_schema.py (95) - Pass. 7 tests, all models.
### test_style_compiler.py (76) - Pass. 8 tests, SKIPs marked.
### test_regression.py (127) - Pass. V22 baseline, 40% threshold.
### benchmark_full.py (194) - Pass. FinRpt 5-dim. TB01: score ceiling (P2). TB02: regex noise (P2).

## 7. utils/
### ocr_engine.py (331) - Conditional. OCR01: import in conditional (P1). OCR02: hardcoded path (P1). OCR03: duplicate degradation code (P2).
### ocr_engine_config.py (36) - Pass. Centralized. Docker doc complete.

## 8. Global Issue Summary
### P0: Must Fix (7)
1. AK01: data/akshare_connector.py -> schema_v50 not found
2. AK02: data/akshare_connector.py -> T1_knowledge path not found
3. EM01: data/east_money_connector.py -> schema_v50 not found
4. W01: workflow.py -> .core.conviction relative import
5. M01: main.py -> verify stat denominator wrong
6. M03: main.py -> ore typo
7. ST02: core/styles/profiles.py -> STYLES_DIR non-existent

### P1: Should Fix (8)
1. T01: tests/run_all.py relative import path
2. A01: core/argument.py dim ID vs YAML mismatch
3. CV01: core/conviction.py V30 path dependency
4. DE01: data/engine.py silent failures
5. XR01: export/expandable_report.py XSS risk
6. ST01: core/styles/ 5 YAML missing
7. OCR02: utils/ocr_engine.py hardcoded path
8. EX01: export/__init__.py V30 sys.path dep

### P2: Future (8)
C01 models.py from_dict / P01 protocol.py duplicate class / S01 style.py splitting / MT01 SQLite params / SY01 evidence_min vs min_sources / TB01 score ceiling / AU01 hardcoded mapping / TB02 regex

## 9. Critical Issues
**Data Flow Breaks**: main.py -> workflow.py -> orchestrator.py -> akshare_connector.py (FAIL) + east_money_connector.py (FAIL) + engine.py (OK)
**Root Cause**: schema_v50 was V50. V51 moved models to core/models.py
**Import Mix**: 3 styles (relative / V50 legacy import / V50 legacy path)

## 10. Priority Fixes
### P0
1. data/akshare_connector.py: from schema_v50 -> from core.models
2. data/akshare_connector.py: from T1_knowledge -> from data.engine
3. data/east_money_connector.py: from schema_v50 -> from core.models
4. workflow.py: from .core.conviction -> from core.conviction
5. main.py L31: ore -> orc
6. main.py verify: fix denominator
7. profiles.py: STYLES_DIR -> core/styles/

### P1
8. Unify import style (absolute throughout)
9. Add logging to data/engine.py except blocks
10. html.escape() in expandable_report.py
11. Create 5 missing YAML files in core/styles/
12. Fix tests/run_all.py import

### P2
13. models.py from_dict completion
14. Remove duplicate class in protocol.py
15. Robust style.py sentence splitting
16. SQLite parameterized query consistency

---

## Appendix
Broken imports: akshare (2), east_money (1), workflow (1), run_all (1), profiles (1) = 6 fixes
SQLite: all parameterized, local-only. Risk: Low
V30 code: ~17 files / ~4,300 lines. Scope: interface only

*Audit complete. 2026-07-24 | Engine: Codex*