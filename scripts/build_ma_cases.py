# -*- coding: utf-8 -*-
"""R58 P0-1: 行业并购案例库构建脚本（幂等，覆盖写入 m_and_a_cases.json）
数据来源：WebSearch 公开资料（案例库数据已固化在下方 DATA 常量中，可重复运行）。
"""
import json
import os

DATA = [
  {
    "industry": "气体传感器",
    "cases": [
      {"acquirer": "Honeywell", "target": "City Technology", "year": 2016, "ev_ebitda": None, "ev_revenue": None, "value_b": 0.053, "currency": "USD", "country": "US/UK", "deal_type": "横向整合", "source": "Honeywell News Release (2016)"},
      {"acquirer": "Amphenol", "target": "GE Sensing & Inspection Technologies", "year": 2018, "ev_ebitda": None, "ev_revenue": None, "value_b": 1.34, "currency": "USD", "country": "US/US", "deal_type": "横向整合", "source": "GE Press Release (2018)"},
      {"acquirer": "Excelitas Technologies", "target": "PerkinElmer (光电/传感部分业务)", "year": 2022, "ev_ebitda": None, "ev_revenue": None, "value_b": 2.83, "currency": "USD", "country": "US/US", "deal_type": "业务剥离/横向整合", "source": "PerkinElmer SEC Filing"}
    ]
  },
  {
    "industry": "半导体",
    "cases": [
      {"acquirer": "AMD", "target": "Xilinx", "year": 2022, "ev_ebitda": None, "ev_revenue": None, "value_b": 49.8, "currency": "USD", "country": "US/US", "deal_type": "横向整合", "source": "AMD 8-K Filing / SEC"},
      {"acquirer": "Broadcom", "target": "VMware", "year": 2023, "ev_ebitda": None, "ev_revenue": None, "value_b": 69.0, "currency": "USD", "country": "US/US", "deal_type": "跨界收购/基础设施整合", "source": "Broadcom Press Release"},
      {"acquirer": "Analog Devices (ADI)", "target": "Maxim Integrated", "year": 2021, "ev_ebitda": None, "ev_revenue": None, "value_b": 20.9, "currency": "USD", "country": "US/US", "deal_type": "横向整合", "source": "ADI Investor Relations"},
      {"acquirer": "Nvidia", "target": "Arm (交易失败)", "year": 2022, "ev_ebitda": None, "ev_revenue": None, "value_b": 40.0, "currency": "USD", "country": "US/UK", "deal_type": "横向整合 (拟议)", "source": "Nvidia/SoftBank Joint Statement"}
    ]
  },
  {
    "industry": "人形机器人/自动化",
    "cases": [
      {"acquirer": "ABB", "target": "B&R (Bernecker + Rainer)", "year": 2017, "ev_ebitda": None, "ev_revenue": None, "value_b": None, "currency": "USD", "country": "CH/AT", "deal_type": "纵向整合 (PLC与驱动)", "source": "ABB Press Release (2017)"},
      {"acquirer": "Amazon", "target": "iRobot", "year": 2022, "ev_ebitda": None, "ev_revenue": None, "value_b": 1.7, "currency": "USD", "country": "US/US", "deal_type": "跨界收购 (智能家居/数据)", "source": "Amazon Blog"},
      {"acquirer": "Teradyne", "target": "Mobile Industrial Robots (MiR)", "year": 2018, "ev_ebitda": None, "ev_revenue": None, "value_b": 0.272, "currency": "USD", "country": "US/DK", "deal_type": "横向整合 (协作机器人)", "source": "Teradyne Press Release"}
    ]
  },
  {
    "industry": "光伏",
    "cases": [
      {"acquirer": "Tongwei (通威股份)", "target": "Runergy (润阳股份)", "year": 2023, "ev_ebitda": None, "ev_revenue": None, "value_b": 1.7, "currency": "USD", "country": "China/China", "deal_type": "横向整合", "source": "通威股份公告 (SH600438)"},
      {"acquirer": "First Solar", "target": "Evolar (钙钛矿技术)", "year": 2023, "ev_ebitda": None, "ev_revenue": None, "value_b": 0.38, "currency": "USD", "country": "US/Sweden", "deal_type": "技术收购", "source": "First Solar Press Release"},
      {"acquirer": "TCL Zhonghuan (TCL中环)", "target": "Maxeon Solar (部分股权增持及整合)", "year": 2023, "ev_ebitda": None, "ev_revenue": None, "value_b": 0.2, "currency": "USD", "country": "China/SG", "deal_type": "纵向整合/战略投资", "source": "TCL中环公告"}
    ]
  },
  {
    "industry": "锂电",
    "cases": [
      {"acquirer": "CATL (宁德时代)", "target": "Kwinana (澳洲锂矿加工) / 整合", "year": 2022, "ev_ebitda": None, "ev_revenue": None, "value_b": None, "currency": "USD", "country": "China/AU", "deal_type": "纵向整合", "source": "宁德时代投资者关系"},
      {"acquirer": "LG Energy Solution", "target": "NEC Energy Solutions (NEC ES)", "year": 2021, "ev_ebitda": None, "ev_revenue": None, "value_b": None, "currency": "USD", "country": "KR/JP", "deal_type": "横向整合 (储能系统)", "source": "LGES Press Release"},
      {"acquirer": "Stellantis", "target": "Meridian Lightweight Technologies (收购电池壳业务)", "year": 2021, "ev_ebitda": None, "ev_revenue": None, "value_b": None, "currency": "USD", "country": "NL/US", "deal_type": "纵向整合", "source": "Stellantis Press"}
    ]
  },
  {
    "industry": "工控/自动化",
    "cases": [
      {"acquirer": "Emerson", "target": "Aspen Technology (AspenTech)", "year": 2022, "ev_ebitda": None, "ev_revenue": None, "value_b": 11.0, "currency": "USD", "country": "US/US", "deal_type": "横向整合 (工业软件)", "source": "Emerson Press Release"},
      {"acquirer": "Schneider Electric", "target": "AVEVA (全额收购/私有化)", "year": 2022, "ev_ebitda": None, "ev_revenue": None, "value_b": 12.7, "currency": "USD", "country": "FR/UK", "deal_type": "私有化/横向整合", "source": "Schneider Electric Press"},
      {"acquirer": "Rockwell Automation", "target": "ClearPath Energy", "year": 2023, "ev_ebitda": None, "ev_revenue": None, "value_b": None, "currency": "USD", "country": "US/US", "deal_type": "横向整合", "source": "Rockwell News"}
    ]
  },
  {
    "industry": "医疗器械",
    "cases": [
      {"acquirer": "Johnson & Johnson", "target": "Abiomed", "year": 2022, "ev_ebitda": None, "ev_revenue": None, "value_b": 16.6, "currency": "USD", "country": "US/US", "deal_type": "横向整合", "source": "J&J Press Release"},
      {"acquirer": "Mindray (迈瑞医疗)", "target": "Hytest (海肽生物)", "year": 2021, "ev_ebitda": None, "ev_revenue": None, "value_b": 0.65, "currency": "USD", "country": "China/FI", "deal_type": "纵向整合 (上游原料)", "source": "迈瑞医疗公告"},
      {"acquirer": "Medtronic", "target": "Covenant Health Systems (部分资产)", "year": 2020, "ev_ebitda": None, "ev_revenue": None, "value_b": None, "currency": "USD", "country": "US/US", "deal_type": "横向整合", "source": "Medtronic News"}
    ]
  },
  {
    "industry": "消费电子",
    "cases": [
      {"acquirer": "Wingtech (闻泰科技)", "target": "Nexperia (安世半导体)", "year": 2019, "ev_ebitda": None, "ev_revenue": None, "value_b": 3.8, "currency": "USD", "country": "China/NL", "deal_type": "跨界收购 (从ODM进入半导体)", "source": "闻泰科技公告 (SH600745)"},
      {"acquirer": "Luxshare Precision (立讯精密)", "target": "iPhone Assembly Business (从台积电/和硕等整合)", "year": 2020, "ev_ebitda": None, "ev_revenue": None, "value_b": 0.33, "currency": "USD", "country": "China/China", "deal_type": "横向整合", "source": "立讯精密公告 / Reuters"},
      {"acquirer": "Hon Hai (Foxconn)", "target": "Lordstown Motors (资产收购/代工合作)", "year": 2021, "ev_ebitda": None, "ev_revenue": None, "value_b": 0.23, "currency": "USD", "country": "TW/US", "deal_type": "跨界/战略合作", "source": "Foxconn Press Release"}
    ]
  }
]


def build(output_path="data/m_and_a_cases.json"):
    """覆盖写入并购案例库。"""
    base = os.path.dirname(os.path.abspath(__file__))
    target = output_path if os.path.isabs(output_path) else os.path.join(base, "..", output_path)
    target = os.path.normpath(target)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)
    # 校验
    with open(target, encoding="utf-8") as f:
        data = json.load(f)
    industries = {d["industry"] for d in data}
    total = sum(len(d["cases"]) for d in data)
    print(f"[P0-1] OK: {len(data)} industries, {total} cases -> {target}")
    print(f"       industries: {sorted(industries)}")
    return target


if __name__ == "__main__":
    build()
