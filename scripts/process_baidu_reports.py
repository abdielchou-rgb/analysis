#!/usr/bin/env python
"""
Process Baidu Netdisk Reports — 从百度网盘下载的行业报告中提取券商研报
并按标准命名复制到 benchmark/golden_raw/{type}/
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

SOURCE_ROOT = Path(
    r"D:\BaiduNetdiskDownload\行业公司研究素材\行业公司\2024-2026年行业报告批量分享记录（已更新26年1月）（赠送ppt模版、excel公式等）"
)
TARGET_ROOT = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_raw")

# 券商关键词映射 → 标准 style
BROKER_MAP = {
    "中金": "cicc",
    "中金公司": "cicc",
    "中信": "cicc",
    "中信证券": "cicc",
    "中信建投": "cicc",
    "海通": "cicc",
    "海通证券": "cicc",
    "海通国际": "cicc",
    "国泰": "cicc",
    "国泰君安": "cicc",
    "华泰": "cicc",
    "华泰证券": "cicc",
    "安信": "cicc",
    "安信证券": "cicc",
    "东吴": "cicc",
    "东吴证券": "cicc",
    "民生": "cicc",
    "民生证券": "cicc",
    "申万": "cicc",
    "申万宏源": "cicc",
    "国联": "cicc",
    "国联证券": "cicc",
    "华创": "cicc",
    "华创证券": "cicc",
    "华鑫": "cicc",
    "华鑫证券": "cicc",
    "华金": "cicc",
    "华金证券": "cicc",
    "天风": "cicc",
    "天风证券": "cicc",
    "西部": "cicc",
    "西部证券": "cicc",
    "西南": "cicc",
    "西南证券": "cicc",
    "东方": "cicc",
    "东方证券": "cicc",
    "东方财富": "cicc",
    "光大": "cicc",
    "光大证券": "cicc",
    "广发": "cicc",
    "广发证券": "cicc",
    "国盛": "cicc",
    "国盛证券": "cicc",
    "红塔": "cicc",
    "红塔证券": "cicc",
    "江海": "cicc",
    "江海证券": "cicc",
    "开源": "cicc",
    "开源证券": "cicc",
    "联储": "cicc",
    "联储证券": "cicc",
    "平安": "cicc",
    "平安证券": "cicc",
    "山西": "cicc",
    "山西证券": "cicc",
    "世纪": "cicc",
    "世纪证券": "cicc",
    "首创": "cicc",
    "首创证券": "cicc",
    "太平洋": "cicc",
    "太平洋证券": "cicc",
    "信达": "cicc",
    "信达证券": "cicc",
    "兴业": "cicc",
    "兴业证券": "cicc",
    "长城": "cicc",
    "长城证券": "cicc",
    "长江": "cicc",
    "长江证券": "cicc",
    "招商": "cicc",
    "招商证券": "cicc",
    "浙商": "cicc",
    "浙商证券": "cicc",
    "中原": "cicc",
    "中原证券": "cicc",
    "中银": "cicc",
    "中银国际": "cicc",
    "高盛": "gs",
    "高盛高华": "gs",
    "Goldman": "gs",
    "摩根士丹利": "ms",
    "摩根": "ms",
    "Morgan": "ms",
    "摩根大通": "jpm",
    "JPM": "jpm",
    "J.P. Morgan": "jpm",
    "瑞银": "ms",
    "UBS": "ms",
    "花旗": "gs",
    "Citi": "gs",
    "德银": "ms",
    "Deutsche": "ms",
    "麦肯锡": "mck",
    "McKinsey": "mck",
    "波士顿": "bcg",
    "BCG": "bcg",
    "波士顿咨询": "bcg",
    "贝恩": "bcg",
    "Bain": "bcg",
    "罗兰贝格": "bcg",
    "Roland Berger": "bcg",
    "埃森哲": "mck",
    "Accenture": "mck",
    "德勤": "bcg",
    "Deloitte": "bcg",
    "普华永道": "bcg",
    "PwC": "bcg",
    "安永": "bcg",
    "EY": "bcg",
    "毕马威": "bcg",
    "KPMG": "bcg",
}

# 报告类型关键词
TYPE_KEYWORDS = {
    "listed_company": [
        "目标价",
        "评级",
        "买入",
        "增持",
        "持有",
        "减持",
        "卖出",
        "DCF",
        "估值",
        "个股",
        "深度",
        "公司研究",
        "事件点评",
        "业绩预告",
    ],
    "industry_deep": [
        "行业",
        "深度",
        "专题",
        "系列",
        "产业链",
        "供应链",
        "TAM",
        "渗透率",
        "竞争格局",
        "龙头",
        "市场规模",
        "发展趋势",
        "投资策略",
        "年度策略",
        "半年策略",
        "月度策略",
    ],
    "earnings_notes": [
        "业绩点评",
        "业绩快报",
        "业绩预告",
        "业绩会",
        "分拆",
        "指引",
        "季报",
        "半年报",
        "年报",
        "Q1",
        "Q2",
        "Q3",
        "Q4",
        "H1",
        "H2",
    ],
    "decision_memo": [
        "并购",
        "收购",
        "投资",
        "战略",
        "入股",
        "定增",
        "重组",
        "分拆",
        "IPO",
        "上市",
        "投入产出",
        "回收期",
        "战略卡位",
        "可行性",
    ],
    "unlisted_company": [
        "独角兽",
        "融资",
        "Pre-IPO",
        "Pre-A",
        "Pre-B",
        "种子轮",
        "天使轮",
        "A轮",
        "B轮",
        "C轮",
        "D轮",
        "Pre-IPO",
        "PE",
        "VC",
        "尽调",
        "尽职调查",
    ],
}

# 文件名中常见的券商名称（用于从文件名提取）
FILENAME_BROKERS = [
    "中金",
    "中信",
    "海通",
    "国泰",
    "华泰",
    "安信",
    "东吴",
    "民生",
    "申万",
    "国联",
    "华创",
    "华鑫",
    "华金",
    "天风",
    "西部",
    "西南",
    "东方",
    "光大",
    "广发",
    "国盛",
    "红塔",
    "江海",
    "开源",
    "联储",
    "平安",
    "山西",
    "世纪",
    "首创",
    "太平洋",
    "信达",
    "兴业",
    "长城",
    "长江",
    "招商",
    "浙商",
    "中原",
    "中银",
    "高盛",
    "Goldman",
    "摩根士丹利",
    "摩根",
    "Morgan",
    "摩根大通",
    "JPM",
    "J.P. Morgan",
    "瑞银",
    "UBS",
    "花旗",
    "Citi",
    "德银",
    "Deutsche",
    "麦肯锡",
    "McKinsey",
    "波士顿",
    "BCG",
    "波士顿咨询",
    "贝恩",
    "Bain",
    "罗兰贝格",
    "Roland Berger",
    "埃森哲",
    "Accenture",
    "德勤",
    "Deloitte",
    "普华永道",
    "PwC",
    "安永",
    "EY",
    "毕马威",
    "KPMG",
    "JPMorgan",
    "Barclays",
    "BofA",
    "Deutsche Bank",
    "CICC",
    "CITIC",
    "HTSC",
]


def extract_broker_from_filename(filename: str) -> tuple[str, str]:
    """从文件名提取券商名和style"""
    for broker in FILENAME_BROKERS:
        if broker in filename:
            style = BROKER_MAP.get(broker, "cicc")
            return broker, style
    return "", "cicc"


def extract_date(filename: str) -> str:
    """提取日期：支持 240716、20240716、2024-07-16、24.07.16 等格式"""
    patterns = [
        r"(\d{6})",  # 240716
        r"(\d{8})",  # 20240716
        r"(\d{4}[-.\s]\d{2}[-.\s]\d{2})",  # 2024-07-16
        r"(\d{2}[-.\s]\d{2}[-.\s]\d{2})",  # 24.07.16
    ]
    for pat in patterns:
        m = re.search(pat, filename)
        if m:
            d = m.group(1).replace(".", "").replace("-", "").replace(" ", "")
            if len(d) == 6:
                return "20" + d  # 240716 -> 20240716
            elif len(d) == 8:
                return d
    return datetime.now().strftime("%Y%m%d")


def classify_type(filename: str) -> str:
    """基于文件名分类报告类型"""
    scores = {t: 0 for t in TYPE_KEYWORDS}
    for t, kws in TYPE_KEYWORDS.items():
        for kw in kws:
            if kw in filename:
                scores[t] += 1
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    return "industry_deep"  # 默认


def clean_name(name: str) -> str:
    """清理文件名，提取核心标的"""
    # 去除页数、日期、券商名等噪声
    name = re.sub(r"-\d+页.*$", "", name)
    name = re.sub(r"\d{6,8}", "", name)
    name = re.sub(r"[_\-]{2,}", "_", name)
    name = re.sub(r"[()（）\[\]【】]", "", name)
    # 去除常见券商名
    for broker in FILENAME_BROKERS:
        name = name.replace(broker, "")
    name = re.sub(r"[_\-]{2,}", "_", name).strip("_-")
    # 提取核心：找最长的有意义片段
    parts = re.split(r"[_\-—]", name)
    meaningful = [p for p in parts if len(p) > 2 and not p.isdigit()]
    return meaningful[-1] if meaningful else name[:30]


def find_broker_folders(root: Path):
    """找到包含大量PDF的'券商研报'文件夹（文件名乱码版）"""
    broker_folders = []
    for root_path, dirs, files in os.walk(root):
        root_path = Path(root_path)
        pdfs = [f for f in files if f.lower().endswith(".pdf")]
        if len(pdfs) >= 50:  # 直接包含大量PDF的文件夹
            broker_folders.append((root_path, pdfs))
    return broker_folders


def process():
    stats = {"total": 0, "copied": 0, "skipped": 0, "errors": 0, "by_type": {}, "by_broker": {}}

    print("扫描券商研报文件夹...")
    broker_folders = find_broker_folders(SOURCE_ROOT)
    print(f"找到 {len(broker_folders)} 个券商研报文件夹")

    for folder_path, pdfs in broker_folders:
        print(f"\n处理文件夹: {folder_path} ({len(pdfs)} PDFs)")

        for f in pdfs:
            stats["total"] += 1
            src = folder_path / f

            broker, style = extract_broker_from_filename(f)
            if not broker:
                stats["skipped"] += 1
                continue

            rpt_type = classify_type(f)
            date_str = extract_date(f)
            core_name = clean_name(f)

            # 标准命名：{机构}_{标的}_{日期}.pdf
            new_name = f"{broker}_{core_name}_{date_str}.pdf"
            new_name = re.sub(r'[\\/:*?"<>|]', "_", new_name)  # Windows非法字符

            # 目标目录
            target_dir = TARGET_ROOT / rpt_type
            target_dir.mkdir(parents=True, exist_ok=True)
            dst = target_dir / new_name

            # 避免重名
            counter = 1
            while dst.exists():
                stem = dst.stem
                dst = target_dir / f"{stem}_{counter}.pdf"
                counter += 1

            try:
                shutil.copy2(src, dst)
                stats["copied"] += 1
                stats["by_type"][rpt_type] = stats["by_type"].get(rpt_type, 0) + 1
                stats["by_broker"][broker] = stats["by_broker"].get(broker, 0) + 1
            except Exception as e:
                stats["errors"] += 1
                print(f"  ✗ {f}: {e}")

            if stats["copied"] % 100 == 0:
                print(f"  已复制: {stats['copied']}/{stats['total']}")

    print("\n=== 处理完成 ===")
    print(f"总扫描: {stats['total']}")
    print(f"成功复制: {stats['copied']}")
    print(f"跳过(无券商): {stats['skipped']}")
    print(f"错误: {stats['errors']}")
    print(f"按类型: {stats['by_type']}")
    print(f"按券商: {dict(sorted(stats['by_broker'].items(), key=lambda x: -x[1])[:15])}")


if __name__ == "__main__":
    process()
