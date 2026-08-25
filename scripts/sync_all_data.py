#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2hao 综合数据同步脚本（R24/R25 合并）— 一键补全所有数据缺口

由 Marvis 在用户机执行（token 免费，akshare 可用）。覆盖：
  Stage 1: A 股名称映射生成（修柯力传感中文名→代码 bug）
  Stage 2: A 股全量财务/行情/资金面同步（复用 run_all_sync）
  Stage 3: 港股 Layer 1 核心标的同步（腾讯/美团/小米/阿里等）
  Stage 4: 行业数据补缺（industry_chain/penetration/drivers 传感器/仪器仪表/工控等）
  Stage 5: 柯力传感 enrich 数据准备（模板生成 + 提示待补）

用法：
  python scripts/sync_all_data.py                 # 全量执行
  python scripts/sync_all_data.py --stage 1       # 只跑某阶段
  python scripts/sync_all_data.py --dry-run       # 只预览不执行
  python scripts/sync_all_data.py --check         # 只检查缺口，不执行

所有数据写入离线底座，2hao 自动吸收。补充数据带 source，无 source 被拦截。
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_all")

# ── 港股 Layer 1 核心标的（港股通 + 已分析 + 常用龙头）──
HK_CORE_STOCKS = {
    "腾讯控股": "00700",
    "美团": "03690",
    "小米集团": "01810",
    "阿里巴巴": "09988",
    "京东集团": "09618",
    "网易": "09999",
    "快手": "01024",
    "理想汽车": "02015",
    "小鹏汽车": "09868",
    "比亚迪股份": "01211",
    "中芯国际": "00981",
    "华虹半导体": "01347",
    "药明生物": "02269",
    "百济神州": "06160",
    "信达生物": "01801",
    "海底捞": "06862",
    "农夫山泉": "09633",
    "安踏体育": "02020",
    "李宁": "02331",
    "中国移动": "00941",
    "中国平安": "02318",
    "招商银行": "03968",
    "建设银行": "00939",
    "工商银行": "01398",
    "汇丰控股": "00005",
}

# ── 行业数据补缺：需要补充的行业条目（Marvis 用 WebSearch 填充后写入）──
INDUSTRY_GAPS = {
    "chain": ["传感器", "仪器仪表", "工控", "机器人", "具身智能", "AI算力"],
    "penetration": ["传感器", "仪器仪表", "工控", "具身智能", "气体传感器"],
    "drivers": ["传感器", "具身智能", "AI算力"],
}

# ── 柯力传感 enrich 需要的数据点 ──
KELI_ENRICH_NEEDS = [
    "fig_revenue_trend: 营收趋势 2023/2024/2025",
    "fig_profitability: 净利趋势 2023/2024/2025",
    "fig_competitive_landscape: 称重传感器市占率/竞争格局",
    "fig_market_size_china: 中国称重/工业传感器市场规模",
    "fig_market_size_global: 全球传感器市场规模",
]


def log_path() -> Path:
    p = _ROOT / "logs" / f"sync_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    p.parent.mkdir(exist_ok=True)
    return p


def run_cmd(cmd: list, dry_run: bool = False) -> int:
    if dry_run:
        logger.info("[DRY] %s", " ".join(cmd))
        return 0
    logger.info("[RUN] %s", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(_ROOT))
    return r.returncode


# ── Stage 1: A 股名称映射生成 ──
def stage_name_map(dry_run: bool = False, check_only: bool = False) -> int:
    """用 akshare 生成全量 A 股名称→代码映射（修中文名匹配 bug）。"""
    logger.info("=" * 50)
    logger.info("[Stage 1] A 股名称映射")
    map_path = _ROOT / "data" / "a_stock_name_map.json"
    if check_only:
        if map_path.exists():
            try:
                d = json.loads(map_path.read_text(encoding="utf-8"))
                logger.info("[OK] 名称映射已存在: %d 条（含柯力传感=%s）", len(d), d.get("柯力传感", "缺"))
                return 0
            except Exception as e:
                logger.error("[FAIL] 映射文件损坏: %s", e)
                return 1
        logger.info("[缺] 映射文件不存在 → 需执行完整 Stage 1")
        return 1
    if dry_run:
        logger.info("[DRY] 将用 akshare stock_zh_a_spot_em 生成 5000+ 条映射 → %s", map_path)
        return 0
    try:
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        name_map = {str(r["名称"]): str(r["代码"]) for _, r in df.iterrows()}
        map_path.write_text(json.dumps(name_map, ensure_ascii=False, indent=1), encoding="utf-8")
        logger.info("[OK] 已写入 %d 条 A 股名称映射 → %s", len(name_map), map_path)
        return 0
    except Exception as e:
        logger.error("[FAIL] akshare 名称映射失败: %s", e)
        return 1


# ── Stage 2: A 股全量同步（复用 run_all_sync）──
def stage_a_share_sync(workers: int = 4, dry_run: bool = False) -> int:
    logger.info("=" * 50)
    logger.info("[Stage 2] A 股全量同步（财务/行情/资金面）")
    return run_cmd(["python", "scripts/run_all_sync.py", "--workers", str(workers)], dry_run)


# ── Stage 3: 港股 Layer 1 同步 ──
def stage_hk_sync(dry_run: bool = False) -> int:
    """同步港股核心标的财务数据 → financials.db（code 存 5 位，source 标 hk）。"""
    logger.info("=" * 50)
    logger.info("[Stage 3] 港股 Layer 1 同步（%d 只核心标的）", len(HK_CORE_STOCKS))
    if dry_run:
        logger.info("[DRY] 将同步 %d 只港股: %s", len(HK_CORE_STOCKS), ", ".join(list(HK_CORE_STOCKS.keys())[:6]))
        return 0
    try:
        import sqlite3

        import akshare as ak

        conn = sqlite3.connect(str(_ROOT / "data" / "financials.db"))
        ok, fail = 0, 0
        for name, code in HK_CORE_STOCKS.items():
            try:
                # akshare 港股财务：stock_financial_hk_analysis_indicator_em / 利润表
                # 先尝试利润表（营业收入/净利润）
                df = ak.stock_financial_hk_analysis_indicator_em(symbol=code)
                if df is None or len(df) == 0:
                    logger.warning("[HK] %s(%s) 无财务数据", name, code)
                    fail += 1
                    continue
                # 写入 financials.db：code 存 5 位，source='hk:akshare'
                for _, row in df.iterrows():
                    date_s = str(row.get("报告期", row.get("日期", "")))[:7].replace("-", "")
                    for field_key in ["基本每股收益", "营业收入", "净利润"]:
                        if field_key in row and row[field_key] is not None:
                            conn.execute(
                                "INSERT OR REPLACE INTO financials (code, quarter, table_name, field, value, source) VALUES (?,?,?,?,?,?)",
                                (code, date_s + "00", "hk_indicator", field_key, float(row[field_key]), "hk:akshare"),
                            )
                conn.commit()
                ok += 1
                logger.info("[HK] %s(%s) 同步 %d 行", name, code, len(df))
            except Exception as e:
                logger.warning("[HK] %s(%s) 失败: %s", name, code, str(e)[:80])
                fail += 1
        conn.close()
        logger.info("[Stage 3] 完成: 成功 %d / 失败 %d", ok, fail)
        return 0 if fail == 0 else 1
    except Exception as e:
        logger.error("[Stage 3] 港股同步失败: %s", e)
        return 1


# ── Stage 4: 行业数据补缺 ──
def stage_industry_gaps(dry_run: bool = False) -> int:
    """检查并报告行业数据缺口（chain/penetration/drivers）。"""
    logger.info("=" * 50)
    logger.info("[Stage 4] 行业数据补缺检查")
    gaps_found = []
    for fname, needed in [
        ("industry_chain.json", INDUSTRY_GAPS["chain"]),
        ("industry_penetration.json", INDUSTRY_GAPS["penetration"]),
        ("industry_drivers.json", INDUSTRY_GAPS["drivers"]),
    ]:
        path = _ROOT / "data" / fname
        if not path.exists():
            gaps_found.append(f"{fname}: 文件缺失")
            continue
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            if fname == "industry_chain.json":
                inds = [x.get("name", "") for x in d.get("industries", [])]
                missing = [n for n in needed if not any(n in i for i in inds)]
            elif fname == "industry_penetration.json":
                ps = d if isinstance(d, list) else d.get("penetration", [])
                inds = set(x.get("industry", "") for x in ps if isinstance(x, dict))
                missing = [n for n in needed if not any(n in i for i in inds)]
            else:  # drivers
                missing = [n for n in needed if not any(n in k for k in d)]
            if missing:
                gaps_found.append(f"{fname}: 缺 {missing}")
            else:
                logger.info("[OK] %s 已覆盖所需行业", fname)
        except Exception as e:
            gaps_found.append(f"{fname}: 读取失败 {e}")
    if gaps_found:
        logger.info("行业缺口清单:")
        for g in gaps_found:
            logger.info("  - %s", g)
        logger.info(
            "提示: 用 WebSearch 搜索各行业产业链结构/渗透率/供需，按 docs/marvis-data-backfill-20260802.md §2 格式写入"
        )
        return 1
    logger.info("[OK] 行业数据无缺口")
    return 0


# ── Stage 5: 柯力传感 enrich 准备 ──
def stage_keli_enrich(dry_run: bool = False) -> int:
    """生成柯力传感 enrich 模板 + 提示待补数据点。"""
    logger.info("=" * 50)
    logger.info("[Stage 5] 柯力传感 enrich 数据准备")
    try:
        from pipeline.data_enrichment import make_enrich_template

        tpl = make_enrich_template("柯力传感", Path(str(_ROOT / "data" / "backlog" / "柯力传感_enrich_template.json")))
        logger.info("[OK] enrich 模板: %s", tpl)
    except Exception as e:
        logger.warning("[SKIP] enrich 模板生成失败: %s", e)
    logger.info("柯力传感待补数据点（每条带 source）:")
    for n in KELI_ENRICH_NEEDS:
        logger.info("  - %s", n)
    if not dry_run:
        logger.info(
            '提示: 填充模板后执行 → python pipeline/scheduler.py "柯力传感" --type listed_company --enrich-file <tpl>'
        )
    return 0


STAGES = {
    1: ("A股名称映射", stage_name_map),
    2: ("A股全量同步", stage_a_share_sync),
    3: ("港股Layer1同步", stage_hk_sync),
    4: ("行业数据补缺检查", stage_industry_gaps),
    5: ("柯力传感enrich准备", stage_keli_enrich),
}


def main():
    parser = argparse.ArgumentParser(description="2hao 综合数据同步（Marvis 执行）")
    parser.add_argument("--stage", type=int, choices=list(STAGES.keys()), default=None, help="只跑某阶段")
    parser.add_argument("--workers", type=int, default=4, help="A股同步并发数")
    parser.add_argument("--dry-run", action="store_true", help="只预览不执行")
    parser.add_argument("--check", action="store_true", help="只检查缺口（stage 1/4/5）")
    args = parser.parse_args()

    log_fp = log_path()
    logger.info("综合数据同步开始 → %s", log_fp)
    stages = [args.stage] if args.stage else list(STAGES.keys())
    exit_code = 0
    for sid in stages:
        name, fn = STAGES[sid]
        logger.info("")
        logger.info("#" * 60)
        logger.info("# Stage %d: %s", sid, name)
        logger.info("#" * 60)
        try:
            if args.check and sid not in (1, 4, 5):
                logger.info("[SKIP] --check 模式跳过 stage %d", sid)
                continue
            if sid == 1 and args.check:
                rc = stage_name_map(check_only=True)
            elif sid == 2:
                rc = fn(workers=args.workers, dry_run=args.dry_run)
            else:
                rc = fn(dry_run=args.dry_run)
            if rc != 0:
                exit_code = rc
        except Exception as e:
            logger.error("[Stage %d] 异常: %s", sid, e)
            exit_code = 1
    logger.info("")
    logger.info("综合数据同步完成，exit=%d", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
