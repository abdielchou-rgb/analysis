"""
统一资产解析层（Asset Resolver）— R26 全量修复缺陷1

**问题**：13 个模块各自从原始输入解析 asset（正则提取 6 位代码 / split 取名字），
导致"柯力传感"、"603662"、"603662.SH"、"柯力传感(603662.SH)"四种叫法
被不同模块解析出不同结果，猜不到就静默返回空。

**方案**：所有模块统一调用 `resolve_asset(input)` 获得规范化资产对象：
  {name, code, market, raw, normalized, has_code, has_name}

**标识规则**：
  - 代码：6 位数字（A股）/ 5 位（港股）/ 带前缀 SH/SZ/HK/688 等
  - 名字：中文名（优先查 a_stock_name_map.json，其次从括号/前缀剥离）
  - market：CN / HK / US / UNLISTED

所有模块从 `asset.name` / `asset.code` 取标识，禁止自行解析。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# 已分析标的 + 常用龙头的名称→代码映射（Marvis 用 akshare 全量生成后覆盖）
_NAME_MAP_CACHE: dict | None = None
# 反查表 name→code（2026-09-04 修复方向 bug 时引入，懒加载）
_REV_NAME_MAP_CACHE: dict | None = None


@dataclass
class Asset:
    """规范化资产对象。"""

    raw: str = ""
    name: str = ""  # 中文名（规范化）
    code: str = ""  # 6 位代码（A股）/ 5 位（港股）
    market: str = ""  # CN / HK / US / UNLISTED / UNKNOWN
    full_ticker: str = ""  # 带前缀（如 SH603662 / 00700.HK）
    has_code: bool = False
    has_name: bool = False
    normalized: str = ""  # 统一形态（优先 code，否则 name）
    aliases: list = field(default_factory=list)

    def __bool__(self):
        return bool(self.has_code or self.has_name)


def _load_name_map() -> dict:
    """加载名称→代码映射（带缓存）。"""
    global _NAME_MAP_CACHE
    if _NAME_MAP_CACHE is not None:
        return _NAME_MAP_CACHE
    path = _ROOT / "data" / "a_stock_name_map.json"
    try:
        if path.exists():
            _NAME_MAP_CACHE = json.loads(path.read_text(encoding="utf-8"))
        else:
            _NAME_MAP_CACHE = {}
    except Exception:
        _NAME_MAP_CACHE = {}
    return _NAME_MAP_CACHE


def _strip_code_prefix(code: str) -> str:
    """去掉 SH/SZ/BJ/HK 前缀，或 .HK/.SH 后缀。"""
    c = code.strip()
    c = re.sub(r"^(SH|SZ|BJ|HK|US|N|CYB|B)\s*", "", c, flags=re.I)
    c = re.sub(r"\.(HK|SH|SZ|SS|T|O)$", "", c, flags=re.I)
    return c


def _detect_market(code: str, name: str = "") -> str:
    """从代码/名字推断市场。"""
    if code:
        if len(code) == 5 and (code.startswith("0") or code.startswith("1")):
            return "HK"
        if len(code) == 6:
            return "CN"
        if len(code) in (4,) or (len(code) <= 5 and not code.startswith("0")):
            return "US"
        return "UNKNOWN"
    if name and name in (
        "腾讯控股",
        "美团",
        "小米集团",
        "阿里巴巴",
        "京东集团",
        "网易",
        "快手",
        "理想汽车",
        "小鹏汽车",
        "比亚迪股份",
    ):
        return "HK"
    return "UNKNOWN"


def _lookup_code_by_name_here(name: str) -> str:
    """名称→代码。

    注：a_stock_name_map.json 的方向是 code→name（"603662": "柯力传感"），
    此前本函数直接按 name_map[name] 查——方向反了，中文名永远解析不出代码。
    修复（2026-09-04）：先构建反查表 name→code（带缓存），再精确/模糊匹配。
    """
    global _REV_NAME_MAP_CACHE
    if _REV_NAME_MAP_CACHE is None:
        base = _load_name_map()
        # 反转 code→name 为 name→code（值冲突时保留首个，同名校罕见）
        rev: dict = {}
        for _code, _name in base.items():
            _name = str(_name).strip()
            if _name and _name not in rev:
                rev[_name] = str(_code).strip()
        _REV_NAME_MAP_CACHE = rev
    rev = _REV_NAME_MAP_CACHE
    # 精确
    if name in rev:
        return rev[name]
    # 去括号后缀（"柯力传感(603662.SH)" → "柯力传感"；兼容全/半角括号）
    core = re.sub(r"[（(][^）)]*[）)]$", "", name).strip()
    if core and core in rev:
        return rev[core]
    for n, c in rev.items():
        if core and (core in n or n in core):
            return c
    return ""


def resolve_asset(raw: str) -> Asset:
    """统一资产解析入口。

    Args:
        raw: 任意形态输入（"柯力传感" / "603662" / "603662.SH" /
             "柯力传感(603662.SH)" / "腾讯控股" / "00700.HK"）

    Returns:
        Asset 对象（无匹配时 has_code/has_name 均 False，normalized=raw 兜底）
    """
    a = Asset(raw=raw or "", normalized=raw or "")
    s = (raw or "").strip()
    if not s:
        return a

    # 1. 提取 6 位数字代码（A股）/ 5 位（港股 0xxxx）/ 美式（4位或字母）
    code_match = re.search(r"\b(\d{6})\b", s)
    hk_match = re.search(r"\b(0\d{4})\b", s) if not code_match else None
    us_match = re.search(r"\b([A-Z]{1,5})\b", s) if not (code_match or hk_match) else None

    code = ""
    if code_match:
        code = code_match.group(1)
    elif hk_match:
        code = hk_match.group(1)
    elif us_match:
        # 避免把名字字母当代码
        if not re.search(r"[一-鿿]", s) and us_match.group(1) not in ("A", "B", "C"):
            code = us_match.group(1)

    if code:
        a.code = _strip_code_prefix(code)
        a.has_code = True
        a.full_ticker = code

    # 2. 提取中文名
    name_match = re.search(r"([一-鿿][一-鿿·]{1,20})", s)
    if name_match:
        a.name = name_match.group(1)
        a.has_name = True

    # 2.5 用代码反查名字（R26：纯代码输入也能拿到中文名）
    # 注：name_map 方向就是 code→name，直接正查即可，无需反转
    if a.has_code and not a.has_name:
        name_map = _load_name_map()
        _n = name_map.get(a.code)
        if _n:
            a.name = str(_n)
            a.has_name = True

    # 3. 用名字补代码（A股/港股映射）
    if a.has_name and not a.has_code:
        mapped = _lookup_code_by_name_here(a.name)
        if mapped:
            a.code = _strip_code_prefix(mapped)
            a.has_code = True

    # 4. 市场判断
    a.market = _detect_market(a.code, a.name)

    # 5. 统一形态
    a.normalized = a.code if a.has_code else (a.name if a.has_name else a.raw)
    a.aliases = list({x for x in [a.name, a.code, a.full_ticker, a.raw] if x})
    return a


def asset_to_aliases(a: Asset) -> list[str]:
    """返回该资产的所有可能叫法（供文件名匹配等）。"""
    return a.aliases


# 便捷函数：兼容现有模块调用
def get_code(asset_input: str) -> str:
    """取 6 位代码，兼容所有形态输入。"""
    return resolve_asset(asset_input).code


def get_name(asset_input: str) -> str:
    """取中文名。"""
    return resolve_asset(asset_input).name


def get_name_or_code(asset_input: str) -> str:
    """取规范化标识（优先名字，无名字用代码）。"""
    a = resolve_asset(asset_input)
    return a.name or a.code or a.raw


if __name__ == "__main__":
    for test in [
        "柯力传感",
        "603662",
        "603662.SH",
        "柯力传感(603662.SH)",
        "芯联集成",
        "688469",
        "腾讯控股",
        "00700.HK",
        "韦尔股份",
    ]:
        a = resolve_asset(test)
        print(
            f"{test!r:>22} → name={a.name!r} code={a.code!r} market={a.market} "
            f"norm={a.normalized!r} has_name={a.has_name} has_code={a.has_code}"
        )
