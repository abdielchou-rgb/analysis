# yichen-web-research 与 last30day 对 2hao 的增强评估 + 同类项目盘点

**日期**：2026-09-01
**前提**：基于 2026-09-01 对 2hao-analyst 的深度审计（AUDIT_20260901_ultra.md）——2hao 的四大弱点：数据新鲜度（静态本地库）、引用粒度（报告级而非论断级）、覆盖广度（A股为主）、评估/回测闭环空白。

---

## 一、查证结果：两个项目是什么

### 1.1 last30day（正确名称 last30days-skill）——真实存在，且是现象级项目

| 维度 | 事实 |
|---|---|
| 仓库 | `mvanhorn/last30days-skill`（MIT） |
| 规模 | **60,778 stars** / 5,310 forks / 175 open issues，GitHub Trending 单日第一 |
| 定位 | AI 智能体驱动的"搜索真实用户而非编辑"的引擎：并行搜 Reddit/X/YouTube/TikTok/HN/Polymarket/GitHub/Bluesky/小红书等 18+ 平台，按真实互动（赞同/点赞/交易额）评分，合成有引用的简报 |
| 关键能力 | 30 天时间窗口、跨来源故事聚类、Best Takes 评分、pre-research（先解析账号/subreddit/话题标签）、`--hiring-signals`（招聘信号）、`--competitors`（竞品对比）、`--store`+`watchlist.py`（跨运行趋势监控+SQLite）、libraay feed（可订阅资料库）、JSON 结构化输出 |
| 工程状态 | 2700+ 测试、测试覆盖率 84%（CI 门槛 60% 起步已提到 84%）、OpenSSF Scorecard、Semgrep+OSV 扫描、175 PR 合并/52 贡献者 |
| 中国版本 | `Jesseovo/last30days-skill-cn`（1,683 stars）：搜微博/知乎/B站/抖音/小红书 8 大平台 |
| 部署形态 | Agent Skill/Plugin，支持 Claude Code/Codex/Cursor/Copilot/Gemini/OpenClaw 50+ 宿主 |

**一句话**：last30day 是"过去 30 天"的社交+预测市场舆情雷达，用真实互动信号解决"Google 搜不到的东西"。

### 1.2 yichen-web-research —— 存在，但不是独立仓库

| 维度 | 事实 |
|---|---|
| 实际位置 | `mcncarl/yichen-skills`（2,031 stars）下的一个子 Skill：`yichen-web-research/` |
| 家族 | 五件套总路由：`yichen-web-research`（横纵研究编排）→ `yichen-unified-search`（搜索）→ `yichen-content-archive`（已知链接归档）→ `yichen-bookmarks-export`（私人收藏导出）→ `yichen-asr`（音视频转写） |
| 核心模式 | **横纵研究协议**（hengzong-research）：纵向（发展史，按 `start_date` 边界）+ 横向（当前格局，按地理/语言有界覆盖）+ 证据账本 |
| 关键机制 | 离线计划器（`plan_hengzong_research.py`）→ 联网搜索 → 打开原文逐主张核对（**claim-source ledger**）→ 离线证据组装器（`assemble_hengzong_evidence.py`）→ 结构闸门（scope_complete/coverage/contradiction/三情景）全过才写报告；缺口输出 `blocking`，只有真实补搜过两条不同路径才能 `ready_with_disclosure` |
| 血缘 | 基于/扩展数字生命卡兹克（KKKKhazix）的 `hv-analysis`，MIT 归属清晰 |
| 工程质量 | 有 SKILL.md + 确定性脚本 + references 契约 + 安全边界（只读/限速/不碰登录态）——**不是套壳** |

**一句话**：yichen-web-research 是一套"**先定计划、再核证据、后过闸门**"的深度研究协议，最值钱的是 claim-level 证据账本与结构闸门设计。

> ⚠️ **明确不存在**：GitHub 上没有名为 `yichen-web-research` 的独立仓库（精确搜索 0 命中）；它挂在 `mcncarl/yichen-skills` 这个"个人技能全家桶"里。如果你在别处看到独立仓库，请以链接为准。

---

## 二、两个项目能否增强 2hao 的调研能力？

**结论：能，且互补性极强。** 但角色不同——last30day 补的是"信息新鲜度"，yichen 补的是"证据纪律"。且二者都**只解决调研前端**，不碰 2hao 的核心（计算/门禁/写作管线），所以是**加法不是替代**。

### 2.1 直接补位对照（对应审计弱项）

| 2hao 弱点（审计发现） | last30days 补位 | yichen-web-research 补位 |
|---|---|---|
| 数据新鲜度：静态本地库，Tavily 搜索无时效锚点 | **强补**：强制 30 天窗口、Reddit/X/Polymarket 实时信号；`--store`+watchlist 可做持续监控 | 中补：`as_of`+`start_date` 边界强制时间纪律 |
| 引用粒度：报告级标注率 ≥30%，inline_citations 常失败 | 中补：简报自带来源引用，但非 claim 级 | **强补**：claim-source ledger，逐主张对原文核对，`locator/event_date/scope` 必填——这正是 2hao 差的东西 |
| 覆盖广度：A股为主，无海外舆情/社交信号 | **强补**：18 平台多语言（含小红书中国版），补"公司/人物/技术 30 天动态"这一层 2hao 完全缺失的信号 | 中补：地理/语言有界覆盖矩阵 |
| 反方论证/证伪（FP2b）：靠 LLM 自生成 | 中补：Polymarket 真实概率可做反方锚 | **强补**：三情景+矛盾处理闸门+`invalidators`，证据驱动而非 LLM 想象 |
| 评估闭环：无独立验证 | 中补：`--store` 趋势库可积累 | 结构闸门是可测试的确定性代码 |

### 2.2 落地建议（怎么接进 2hao，符合 CLAUDE.md 双模宪法）

**合规红线**（FP7d/CLAUDE.md）：外部调研结果是"补充输入"，必须走 enrich-file 回流管线，**禁止直接写正文**。

推荐接入路径：

1. **last30days 作为新数据源（性价比最高，半天）**
   - 在 `data_collector.py` 增加 `_last30days_search()` 后端：调 `last30days.py "主题" --emit=json --store` 取结构化结果
   - 映射到 enrich-file 白名单键（`fig_sentiment/fig_news_recent/fig_polymarket_prob`），走既有桥接层
   - 用武之地：① 决策备忘录的"近期动态/市场情绪"段；② 行业报告的"催化剂跟踪"；③ 上市公司报告的"舆情与事件"
   - 价值点：**它给你的是"Google 上搜不到的 30 天动态"，正好补 2hao 最大的数据盲区**

2. **yichen-web-research 的协议作为"深度研究模式"的预处理（推荐）**
   - 2hao 已有 `research_planner.py`（LLM 生成问题），可把 yichen 的离线计划器接入：先产 `plan_id`+workstream+query_groups → 再走 2hao 的 data_collector
   - 把 claim-source ledger 并入 `data_provenance.py`——**这直接解决审计点出的"data_provenance 溯源太浅"**，并让 FP2a/FP6 从报告级升级到论断级
   - 结构闸门（blocking/ready_with_disclosure）可映射为 IronGate 新检查项

3. **不建议**：把两个项目的"报告生成"部分接进 2hao——它们都只做调研不做计算，2hao 的 compute/Gate 才是纵深，不要让外部 LLM 直接产正文。

### 2.3 注意事项（反方）

- last30days 需要平台凭据（X/YouTube/ScrapeCreators），中国版对微博/抖音依赖登录态——有合规与运维成本
- 两个项目都偏"叙事/舆情"，**不是财务数据源**；2hao 的数值计算仍靠 akshare/本地库
- 引入外部 Skill 需过提示注入审查（AUDIT 已点名此风险面）；yichen 的安全边界设计（只读/限速/不透传密钥）反而是好范本

---

## 三、类似项目盘点（AI 投研/深度调研 agent 全景）

### 3.1 直接竞品/可借鉴（AI 金融投研）

| 项目 | Stars | 定位 | 对 2hao 的启示 |
|---|---|---|---|
| **TauricResearch/TradingAgents** | 101,983 | 多 Agent LLM 金融交易框架（分析师/研究员/交易员/风控角色辩论） | 多角色辩论=2hao 的 debate_engine 的顶级参照；其可视化与 Agent 编排值得学 |
| **virattt/dexter** | 27,560 | 自治金融研究 agent：任务规划→自省→实时市场数据→自我校验 | 与 2hao 思路几乎一致（plan/execute/self-validate），印证 2hao 理念不落后 |
| **xbtlin/ai-berkshire** | 16,050 | 价值投资研究框架（巴菲特/芒格/段永平/李录方法论+多 Agent 并行） | 中文方法论工程化，与 2hao 同思路；其"大师方法论"库可借鉴 |
| **AI4Finance-Foundation/FinRobot** | 7,896 | 开源金融 AI Agent 平台（AI4Finance 生态，含 FinGPT） | 金融领域最全的开源平台，数据/模型/agent 三层；2hao 可吸收其架构分层 |
| **Microsoft/RD-Agent** | 14,385 | 微软因子挖掘/策略研究自演化 agent | FP5 演化闭环的顶级实现——2hao 的 learning_loop 正是缺这种"自演化-回测"回路 |
| **simonlin1212/TradingAgents-astock** | 3,121 | A股多 Agent 投研（龙虎榜/游资/解禁）+7 分析师辩论 | 中文投研+实时数据的最佳开源参照 |
| **simonlin1212/Vibe-Research** | 2,275 | 个人投研 agent：每日复盘/资讯雷达/个股数据/持仓/回测 | 2hao 缺的"日常跟踪+回测"闭环它做了 |
| **qusong0627/QuantMind** | 1,207 | Qlib+RD-Agent+TradingAgents 集成量化平台 | 三合一参考 |

### 3.2 深度调研 agent（非金融，但方法论通用）

| 项目 | Stars | 定位 | 对 2hao 的启示 |
|---|---|---|---|
| **assafelovic/gpt-researcher** | 29,222 | 通用深度研究 agent（多 LLM 支持） | 深研 agent 范式；2hao 的 2hao-deep-research skill 可与其对标 |
| **Alibaba-NLP/DeepResearch** | 19,898 | 通义深度研究 agent（开源最强中文通用深研） | 中文深研 SOTA 参照；其问题生成/迭代收敛值得学 |
| **dzhng/deep-research** | 19,620 | 最简 deep research 实现（迭代+search+scrape+LLM） | 简约范本——2hao 与之对比更显"设计过剩、兑现不足" |
| **zilliztech/deep-searcher** | 8,230 | 私有数据上的深度研究（向量） | 若 2hao 接 kb_fts 向量化可参考 |
| **guy-hartstein/company-research-agent** | 2,255 | LangGraph+Tavily 公司尽调多 agent | company due diligence 场景的直接参照 |
| **nickscamara/open-deep-research** | 6,282 | Firecrawl 驱动的 open deep research clone | 抓取管线参照 |

### 3.3 中国市场的投研 Skill/框架（与 2hao 最同层）

| 项目 | Stars | 定位 |
|---|---|---|
| **Jesseovo/last30days-skill-cn** | 1,683 | 中国 8 大平台（微博/知乎/B站/抖音/小红书）30 天研究 |
| **lyra81604/zhengxi-views** | 1,393 | 易方达基金经理郑希的投研 agent（可溯源问答，绝不杜撰） |
| **mcncarl/yichen-skills** | 2,031 | 逸尘技能全家桶（含 yichen-web-research 横纵研究） |
| **tvytlx/ai-agent-deep-dive** | 5,826 | AI Agent 源码深度研究报告 |

### 3.4 商业/终端（对标"顶级项目"的上限）

- **Bloomberg Terminal / Wind**：实时数据+一致预期+评级-收益追踪——2hao 的"预测问责"差距的商业参照
- **AlphaSense / Tegus**：专家访谈+研报全文检索+claim 级引用——2hao 的"引用粒度"目标的商业参照
- **Perplexity Deep Research / Gemini Deep Research**：消费级深研，交互式迭代
- **中金/高盛 AI 辅助研究台**：机构内部，数据牌照+合规纪律

---

## 四、结论

**问题 1：两个项目能否增强 2hao？**

**能，而且是 2hao 当前最缺的两块拼图**：
- **last30days** 补"信息新鲜度与实时舆情"——2hao 的数据层是静态本地库+搜索，完全没有"过去 30 天人们真实在讨论什么"这一层；last30days 以真实互动信号排序，是 2hao 的 Tavily 搜索无法替代的
- **yichen-web-research** 补"证据纪律与 claim 级溯源"——2hao 审计的头号硬伤是引用粒度粗、data_provenance 浅；yichen 的 claim-source ledger + 结构闸门正是对症药方

接入方式是**桥接（enrich-file 回流）而非替代**，符合 2hao 宪法。

**问题 2：类似项目还有哪些？**

分三层：**金融投研 agent**（TradingAgents 10 万星、dexter 2.7 万星、ai-berkshire 1.6 万星、FinRobot、RD-Agent）、**通用深度调研**（gpt-researcher、通义 DeepResearch、dzhng/deep-research）、**中国市场同层**（TradingAgents-astock、Vibe-Research、last30days-cn、zhengxi-views）。**2hao 的设计理念在这些顶级项目里并不落后**——它缺的是把"方法论密度"兑现为"可稳定运行+可验证"的工程闭环（这正是上一轮审计的主结论）。
