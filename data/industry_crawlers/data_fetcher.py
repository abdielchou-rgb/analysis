"""Industry Crawlers — 行业数据抓取（基于akshare + requests）

提供 get_industry_data() 供 DataCollector 调用
"""

import logging
from typing import Optional

logger = logging.getLogger("2hao.industry_crawlers")


def get_industry_data(industry: str) -> Optional[dict]:
    """获取行业数据（通过akshare获取行业板块行情）"""
    try:
        import akshare as ak
        import pandas as pd
        
        result = {"industry": industry, "status": "ok", "data": [], "source": "akshare"}
        
        # 获取行业板块列表
        try:
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                # 过滤匹配的行业
                matched = df[df["board_name"].str.contains(industry[:3], na=False)]
                if not matched.empty:
                    board_name = matched.iloc[0]["board_name"]
                    result["data"].append({
                        "type": "industry_board",
                        "name": board_name,
                        "member_count": int(matched.iloc[0].get("num", 0)),
                        "source": "akshare(东方财富行业板块)"
                    })
                    
                    # 尝试获取行业成分股
                    try:
                        code = matched.iloc[0]["code"]
                        constituents = ak.stock_board_industry_cons_em(symbol=code)
                        if constituents is not None and not constituents.empty:
                            top5 = constituents.head(5).to_dict(orient="records")
                            result["data"].append({
                                "type": "constituents",
                                "top_5": [{k: str(v)[:30] for k, v in item.items()} for item in top5],
                                "source": "akshare(行业成分股)"
                            })
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Industry board fetch failed: {e}")
        
        # 获取宏观经济数据作为行业背景
        try:
            macro_cn = ak.macro_china_gdp_yearly()
            if macro_cn is not None and not macro_cn.empty:
                latest = macro_cn.head(3).to_dict(orient="records")
                result["data"].append({
                    "type": "macro_background",
                    "gdp_data": [{k: str(v)[:20] for k, v in item.items()} for item in latest],
                    "source": "akshare(中国GDP)"
                })
        except Exception:
            pass
        
        result["status"] = "available" if result["data"] else "unavailable"
        return result
        
    except ImportError:
        logger.warning("akshare not available for industry data")
        return None
    except Exception as e:
        logger.warning(f"Industry data fetch error: {e}")
        return None
