"""Universe Building 节点。
在 data 采集后运行，基于 SAC 底座和非上市玩家数据库，
构建全量竞争玩家清单，产缺口列表供 enrich 补采。
解决 R63 发现的"上市公司偏见""品牌覆盖代替实体覆盖"系统性问题。
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 行业名 → unlisted_players.json 行业键的映射表
# R82（2026-08-06）：精确行业键映射——"液位传感器"不得落入"油位传感器"（串标根治）。
# 遍历按 key 长度降序，确保最长匹配优先（"油位传感器" 先于 "油位"，"液位传感器" 先于 "液位"）。
_INDUSTRY_KEY_MAP = {
    "油位传感器": "油位传感器",
    "液位传感器": "液位仪表",
    "物位传感器": "物位",
    "液位仪表": "液位仪表",
    "物位计": "物位",
    "油位液位计": "液位仪表",
    "加油设备": "加油设备",
    "传感器": "传感器",
    "气体传感器": "气体传感器",
    # R72（2026-08-05）：智慧物流/IoT 行业——久通物联正确行业归属
    "智慧物流": "智慧物流",
    "智能物流": "智慧物流",
    "物联网": "智慧物流",
    "IoT": "智慧物流",
    "箱联全球": "智慧物流",
    "物流IoT": "智慧物流",
    "智能集装箱": "智慧物流",
}

# 覆盖率阈值：低于此值建议 enrich 补采
# R77（2026-08-05 P0-2）：从硬编码改为从 framework_registry.json 读校准值
# （FP5 回测可回写；注册表缺失/异常时用默认 0.7）
_COVERAGE_ENRICH_THRESHOLD = 0.7
try:
    _REGISTRY_CFG = json.loads((_PROJECT_ROOT / "data" / "framework_registry.json").read_text(encoding="utf-8"))
    _calib = _REGISTRY_CFG.get("_meta", {}).get("calibration", {})
    _COVERAGE_ENRICH_THRESHOLD = float(_calib.get("coverage_enrich_threshold", _COVERAGE_ENRICH_THRESHOLD))
except Exception:
    pass  # 注册表异常时用默认 0.7

# R77（2026-08-05 P0-2）：数据底座时效性——超过此天数未刷新视为 stale
_STALE_DAYS = 90
# 报告涉及的行业在底座缺条目时，是否在 Gate 给 warning（在 iron_gate 接线）


class UniverseBuilder:
    """全量玩家清单构建器。"""

    def __init__(self):
        self.unlisted_players = {}
        self.brand_mapping = []
        self._load_data()

    def _load_data(self):
        """加载数据底座。"""
        self._data_mtime = {
            "unlisted_players": None,
            "brand_entity_mapping": None,
        }
        try:
            p1 = _PROJECT_ROOT / "data" / "unlisted_players.json"
            if p1.exists():
                self.unlisted_players = json.loads(p1.read_text(encoding="utf-8"))
                self._data_mtime["unlisted_players"] = p1.stat().st_mtime
                logger.info("[UniverseBuild] loaded unlisted_players: %d industries", len(self.unlisted_players))
        except Exception as e:
            logger.warning("[UniverseBuild] load unlisted_players failed: %s", e)
        try:
            p2 = _PROJECT_ROOT / "data" / "brand_entity_mapping.json"
            if p2.exists():
                raw = json.loads(p2.read_text(encoding="utf-8"))
                self.brand_mapping = raw.get("mappings", []) if isinstance(raw, dict) else []
                self._data_mtime["brand_entity_mapping"] = p2.stat().st_mtime
                logger.info("[UniverseBuild] loaded brand_entity_mapping: %d mappings", len(self.brand_mapping))
        except Exception as e:
            logger.warning("[UniverseBuild] load brand_entity_mapping failed: %s", e)

    @staticmethod
    def _to_text(collected_data) -> str:
        """把 collected_data 序列化为可匹配文本。"""
        if collected_data is None:
            return ""
        if isinstance(collected_data, dict):
            try:
                return json.dumps(collected_data, ensure_ascii=False)
            except Exception:
                return str(collected_data)
        return str(collected_data)

    def _extract_company_names(self, text: str) -> list:
        """从文本提取公司名/品牌名（品牌映射 + 玩家清单匹配）。"""
        found = set()
        if not text:
            return []
        for m in self.brand_mapping:
            brand = m.get("brand", "")
            entity = m.get("entity", "")
            if brand and brand in text:
                found.add(brand)
            if entity and entity in text:
                found.add(entity)
        for industry_data in self.unlisted_players.values():
            if not isinstance(industry_data, dict):
                continue
            for p in industry_data.get("players", []):
                name = p.get("name", "") if isinstance(p, dict) else ""
                if name and name in text:
                    found.add(name)
        return sorted(found)

    def _infer_industry_key(self, asset: str, collected_data: dict) -> str:
        """推断行业键名。"""
        # R82（2026-08-06）：精确行业键优先于泛关键词——"油位传感器"含"传感"
        # 但绝不能落入"传感器"行业（力/触觉传感器玩家清单），必须先按
        # _INDUSTRY_KEY_MAP 别名精确匹配资产名，再走泛关键词兜底。
        # 先查标的别名表（data/asset_alias.json，MDM 命名隔离）——最长别名优先
        try:
            _alias_db = json.loads((_PROJECT_ROOT / "data" / "asset_alias.json").read_text(encoding="utf-8"))
            _asset_str = str(asset)
            _best = None
            for _canon, _aliases in _alias_db.items():
                if _canon == "_meta":
                    continue
                for _a in _aliases:
                    if _a and _a.lower() in _asset_str.lower():
                        if _best is None or len(_a) > len(_best[0]):
                            _best = (_a, _canon)
            if _best:
                return _best[1]
        except Exception:
            pass
        # 最长匹配优先：按 key 长度降序遍历，避免"液位传感器"被"油位传感器"先命中
        for _alias, _key in sorted(_INDUSTRY_KEY_MAP.items(), key=lambda x: -len(x[0])):
            if _alias and _alias in str(asset):
                return _key
        # R72（2026-08-05）：资产名关键词优先匹配——久通物联含"物联"不应落入芯片行业
        _kw_map = {
            "物联": "智慧物流",
            "物流": "智慧物流",
            "集装箱": "智慧物流",
            "车联": "智慧物流",
            "交通": "智慧物流",
            "称重传感": "传感器",
            "力传感": "传感器",
            "触觉传感": "传感器",
        }
        for _kw, _ind in _kw_map.items():
            if _kw in str(asset):
                return _ind
        candidates = []
        if isinstance(collected_data, dict):
            # 优先行业标签
            ct = collected_data.get("chart_data", {})
            if not isinstance(ct, dict):
                ct = {}
            for k in ("industry_tags", "industry", "industry_hint", "sector"):
                val = collected_data.get(k) or ct.get(k)
                if isinstance(val, str):
                    candidates.append(val)
                elif isinstance(val, (list, tuple)):
                    candidates.extend([str(v) for v in val])
        candidates.append(str(asset))
        # 别名映射 + 直接键匹配
        for cand in candidates:
            if not cand:
                continue
            for alias, key in _INDUSTRY_KEY_MAP.items():
                if alias in cand:
                    return key
            if cand in self.unlisted_players:
                return cand
        # 兜底：全量文本扫描
        text = self._to_text(collected_data)
        for alias, key in _INDUSTRY_KEY_MAP.items():
            if alias and alias in text:
                return key
        for key in self.unlisted_players:
            if key and key in text:
                return key
        return ""

    def _build_brand_issues(self, industry_key: str, covered_names: set, text: str) -> list:
        """产品牌映射问题：品牌已被采集覆盖，但未关联到非上市玩家清单实体。"""
        issues = []
        player_names = set()
        if industry_key:
            industry_data = self.unlisted_players.get(industry_key, {})
            player_names = {p.get("name", "") for p in industry_data.get("players", []) if isinstance(p, dict)}
        for m in self.brand_mapping:
            brand = m.get("brand", "")
            entity = m.get("entity", "")
            if not brand:
                continue
            # 品牌被采集文本覆盖
            brand_covered = (brand in text) or (brand in covered_names)
            if not brand_covered:
                continue
            entity_covered = (entity in text) or (entity in covered_names)
            if entity_covered:
                continue
            # 品牌与实体均不在玩家清单中（无法对齐到实体）
            in_universe = any(brand in p or p in brand for p in player_names) or any(
                entity in p or p in entity for p in player_names
            )
            if not in_universe:
                issues.append(
                    {
                        "brand": brand,
                        "entity": entity,
                        "group": m.get("group", ""),
                        "issue": "品牌已被采集覆盖但未关联到非上市玩家实体清单，存在品牌/实体映射断裂",
                    }
                )
            else:
                issues.append(
                    {
                        "brand": brand,
                        "entity": entity,
                        "group": m.get("group", ""),
                        "issue": "品牌被覆盖但实体与玩家清单名称不一致，需确认归一化口径",
                    }
                )
        return issues

    def _build_group_notes(self, industry_key: str, text: str) -> list:
        """产集团归属热点：映射表中与当前行业相关的集团聚合备注。"""
        notes = []
        player_names = set()
        if industry_key:
            industry_data = self.unlisted_players.get(industry_key, {})
            player_names = {p.get("name", "") for p in industry_data.get("players", []) if isinstance(p, dict)}
        groups = {}
        for m in self.brand_mapping:
            group = m.get("group", "")
            if not group:
                continue
            info = groups.setdefault(group, {"brands": [], "entities": []})
            info["brands"].append(m.get("brand", ""))
            info["entities"].append(m.get("entity", ""))
        for group, info in groups.items():
            brands = list(dict.fromkeys(b for b in info["brands"] if b))
            entities = list(dict.fromkeys(e for e in info["entities"] if e))
            related = [b for b in brands if (b in text) or (b in player_names) or any(b in p for p in player_names)]
            if not related:
                continue
            notes.append(
                {
                    "group": group,
                    "brands": brands,
                    "entities": entities,
                    "note": (
                        f"集团 {group} 涉及品牌 {'/'.join(brands)}，"
                        f"按实体口径归一后统一归属 {group}，注意避免同一集团重复计数"
                    ),
                }
            )
        return notes

    def staleness_check(self) -> dict:
        """数据底座时效性检查：超过 _STALE_DAYS 天未刷新的底座 → 标记 stale_refresh。

        2026-08-05（R77 P0-2 覆盖意识）：覆盖检查从 checklist 升级为 staleness detection。
        数据底座可能"存在但过期"——unlisted_players.json / brand_entity_mapping.json
        超过 90 天未更新，说明 Marvis 采集已停摆，覆盖率的参考价值随之衰减。
        返回 { source: {age_days, stale, recommend_action} }
        """
        import time as _time

        now = _time.time()
        result = {}
        for source, mtime in self._data_mtime.items():
            if mtime is None:
                result[source] = {
                    "exists": False,
                    "age_days": None,
                    "stale": True,
                    "recommend_action": "missing_refresh",
                }
                continue
            age_days = (now - mtime) / 86400
            result[source] = {
                "exists": True,
                "age_days": round(age_days, 1),
                "stale": age_days > _STALE_DAYS,
                "recommend_action": "stale_refresh" if age_days > _STALE_DAYS else "ok",
            }
        return result

    def build(self, asset: str, collected_data: dict, report_type: str = "industry_deep") -> dict:
        """主入口：构建全量清单，产缺口报告。"""
        industry_key = self._infer_industry_key(asset, collected_data)
        # R82（2026-08-06）：行业键白名单校验——匹配到白名单外的键 → 数据底座缺失，
        # 返回 enrich 提示而非错误归并（防串标）。边界冲突检测：相近行业并存时告警。
        _valid_keys = set(self.unlisted_players.keys())
        if industry_key and industry_key not in _valid_keys:
            logger.warning("[UNIVERSE] 行业键 %s 不在白名单（数据底座缺该行业），返回 enrich 提示", industry_key)
            industry_key = ""
        _sim_map = {
            "油位传感器": ["液位仪表", "物位"],
            "液位仪表": ["油位传感器", "物位"],
            "物位": ["油位传感器", "液位仪表"],
        }
        if industry_key in _sim_map:
            logger.info(
                "[UNIVERSE] 行业 %s 的相近行业(可能混淆): %s——多报告并行注意数据底座隔离",
                industry_key,
                "/".join(_sim_map[industry_key]),
            )
        industry_display = industry_key or asset or "unknown"
        industry_data = self.unlisted_players.get(industry_key, {}) if industry_key else {}
        players = industry_data.get("players", []) if isinstance(industry_data, dict) else []
        total = len(players)

        text = self._to_text(collected_data)
        covered_names = set(self._extract_company_names(text))

        missing_players = []
        for p in players:
            if not isinstance(p, dict):
                continue
            name = p.get("name", "")
            if not name:
                continue
            if any((c and (c in name or name in c)) for c in covered_names):
                continue
            missing_players.append(
                {
                    "name": name,
                    "role": p.get("role", ""),
                    "threat_level": p.get("threat_level", "unknown"),
                }
            )

        brand_issues = self._build_brand_issues(industry_key, covered_names, text)
        group_notes = self._build_group_notes(industry_key, text)

        covered_players = total - len(missing_players)
        coverage_rate = round(covered_players / total, 2) if total > 0 else 0.0
        if total == 0:
            recommend_action = "enrich"
            note = "行业数据底座缺失（unlisted_players.json 无该行业键），建议补采全量玩家清单"
        elif coverage_rate >= _COVERAGE_ENRICH_THRESHOLD:
            recommend_action = "report"
            note = "覆盖率达标，可直接进入 enrich/write 阶段"
        else:
            recommend_action = "enrich"
            note = "存在未覆盖玩家，建议 enrich 补采"

        data_freshness = self.staleness_check()

        summary = {
            "industry": industry_display,
            "industry_key": industry_key,
            "total_players": total,
            "covered_players": covered_players,
            "missing_players": missing_players,
            "brand_issues": brand_issues,
            "group_notes": group_notes,
            "coverage_rate": coverage_rate,
            "recommend_action": recommend_action,
            "data_freshness": data_freshness,
            "note": note,
        }
        # 底座过期但不阻塞报告——只在 note 中提示（报告质量优先级高于提示）
        if any(v.get("stale") for v in data_freshness.values()):
            summary["stale_note"] = (
                "数据底座过期（unlisted_players/brand_entity_mapping 超过 "
                f"{int(_STALE_DAYS)} 天未刷新），覆盖率参考价值衰减，建议触发 refresh"
            )
        logger.info(
            "[UniverseBuild] %s: coverage=%s/%s (%s), %d missing",
            industry_display,
            covered_players,
            total,
            coverage_rate,
            len(missing_players),
        )
        return {"universe_summary": summary}


def universe_build_node(node_id: str, context: dict) -> dict:
    """Graph 节点入口。"""
    try:
        builder = UniverseBuilder()
        asset = context.get("asset", "")
        collected_data = context.get("collected_data", {})
        report_type = context.get("report_type", "industry_deep")
        result = builder.build(asset=asset, collected_data=collected_data, report_type=report_type)
        summary = result.get("universe_summary", {})
        logger.info(
            "[UniverseBuild] %s: coverage=%s/%s, %d missing",
            summary.get("industry", "unknown"),
            summary.get("covered_players", 0),
            summary.get("total_players", 0),
            len(summary.get("missing_players", [])),
        )
        context["universe_summary"] = summary
        return {"universe_summary": summary}
    except Exception as e:
        logger.warning("[UniverseBuild] node failed (不阻断管线): %s", e)
        context.setdefault("universe_summary", {})
        return {"universe_summary": {}}
