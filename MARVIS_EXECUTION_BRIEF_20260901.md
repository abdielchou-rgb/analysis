# Marvis 执行指令：2hao 调研能力增强安装包

**交接对象**：Marvis（或任意新会话）
**交接来源**：2026-09-01 2hao-analyst 审计 + 增强评估（EVAL_20260901）
**目标**：把 last30days + yichen-web-research 两个调研 skill 安装到 2hao-analyst 项目，并验证接线
**项目根**：`D:\Claude\projects\2hao-analyst`

---

## 一、任务概述

给 2hao 分析师装上两个外部调研能力：

| Skill | 作用 | 安装位置 |
|---|---|---|
| **last30days-skill** | 近 30 天真实舆情（Reddit/X/YouTube/HN/Polymarket/小红书） | 本机 skills 目录 + 2hao 项目内 |
| **yichen-web-research** | 横纵深度研究协议（claim 级证据账本 + 结构闸门） | 本机 skills 目录 |

安装后，2hao 的 `pipeline/data_collector.py` 已内置的 `_last30days_search()` 桥接骨架（P3-1 已接进主采集链）将自动探测到 CLI 并开始工作。

---

## 二、环境前提检查（先跑这个）

```bash
cd D:\Claude\projects\2hao-analyst

# 1. Python 版本（last30days 需要 3.12+）
python --version

# 2. git 可用
git --version

# 3. node/npx 可用（skill 安装器需要）
node --version && npx --version

# 4. 确认用户 skills 目录（Windows）
#    Claude Desktop:  %USERPROFILE%\.claude\skills\
#    Claude Code:     %USERPROFILE%\.claude\skills\
echo %USERPROFILE%\.claude\skills\

# 5. 确认 2hao 项目可写
echo test > D:\Claude\projects\2hao-analyst\.marvis_write_test && del D:\Claude\projects\2hao-analyst\.marvis_write_test
```

**检查结果记录到 `output/marvis_setup_check.md`**，每项标注 ✅/❌。

---

## 三、任务 1：安装 last30days-skill

### 方式 A：官方安装器（推荐）

```bash
cd %USERPROFILE%\.claude\skills
npx skills add mvanhorn/last30days-skill -g
```

### 方式 B：手动 clone（A 失败时用）

```bash
cd %USERPROFILE%\.claude\skills
git clone --depth 1 https://github.com/mvanhorn/last30days-skill.git _tmp_l30
# skill 本体在 子目录，复制出来
xcopy _tmp_l30\skills\last30days last30days /E /I
rmdir /S /Q _tmp_l30
```

### 验证

```bash
# skill 目录存在
dir %USERPROFILE%\.claude\skills\last30days\SKILL.md

# CLI 可执行（Python 3.12+ 环境）
python %USERPROFILE%\.claude\skills\last30days\scripts\last30days.py --help

# doctor 健康检查（检查各平台凭据）
python %USERPROFILE%\.claude\skills\last30days\scripts\last30days.py doctor
```

**关键环境变量**（缺了部分平台不可用，但核心源仍工作）：
- `SCRAPECREATORS_API_KEY`（主源，Reddit/网页）
- `OPENAI_API_KEY`（摘要生成，可选）
- `OPENROUTER_API_KEY`（降级摘要，可选）

**注意**：如果本机 Python 是 3.10/3.11，需要装 Python 3.12+（`winget install Python.Python.3.12`），或用 `py -3.12` 调用。

---

## 四、任务 2：安装 yichen-web-research

yichen 是 `mcncarl/yichen-skills`（2031 星）下的子 skill 家族，需要装 5 个配套：

```bash
cd %USERPROFILE%\.claude\skills
git clone --depth 1 https://github.com/mcncarl/yichen-skills.git _tmp_yichen

# 复制 5 个子 skill（总路由 + 4 个执行器）
xcopy _tmp_yichen\yichen-web-research yichen-web-research /E /I
xcopy _tmp_yichen\yichen-unified-search yichen-unified-search /E /I
xcopy _tmp_yichen\yichen-content-archive yichen-content-archive /E /I
xcopy _tmp_yichen\yichen-bookmarks-export yichen-bookmarks-export /E /I
xcopy _tmp_yichen\yichen-asr yichen-asr /E /I

rmdir /S /Q _tmp_yichen
```

### 验证

```bash
# 5 个 skill 目录都存在
dir %USERPROFILE%\.claude\skills\yichen-web-research\SKILL.md
dir %USERPROFILE%\.claude\skills\yichen-unified-search\SKILL.md

# 确定性脚本可跑（离线计划器，不联网）
python %USERPROFILE%\.claude\skills\yichen-web-research\scripts\plan_hengzong_research.py --help

# doctor 体检（检查后端可用性）
python %USERPROFILE%\.claude\skills\yichen-web-research\scripts\doctor_yichen.py
```

**yichen 的安全边界**（必须遵守）：
- 所有社交平台只读：不发帖、不评论、不点赞
- 小红书/抖音搜索有严格限速（单关键词 ≤20 条、串行、间隔 ≥5 秒）
- 私人收藏/书签导出必须当轮明确授权
- 匿名公开路线优先，不绕过验证码/登录墙

---

## 五、任务 3：验证 2hao 桥接接线（核心验收）

2hao 的 `data_collector.py` 已在 `collect()` 的并行采集链中调用 `_last30days_search()`（P3-1，2026-09-01）。安装后必须验证：

```bash
cd D:\Claude\projects\2hao-analyst

# 1. 确认桥接代码存在
findstr "last30days" pipeline\data_collector.py

# 2. 把 last30days 加入 PATH（临时）或配置环境变量
set PATH=%PATH%;%USERPROFILE%\.claude\skills\last30days\scripts

# 3. 跑一次最小采集（不联网的本地模式验证 CLI 探测）
python -c "from pipeline.data_collector import DataCollectorV5; dc=DataCollectorV5(); r=dc._last30days_search('宁德时代'); print('结果:', list(r.keys()) if r else 'CLI 未探测到（静默降级正常）')"
```

**验收标准**：
- CLI 安装成功 → `_last30days_search` 返回 `fig_recent_news`/`fig_sentiment`
- CLI 未探测到 → 返回空 dict（静默降级，不阻塞主流程）——**这是预期行为，不是错误**

---

## 六、可选增强（时间允许时调研，不强制安装）

| 项目 | Star | 价值 | 是否安装 |
|---|---|---|---|
| **同花顺 Financial-API** | 2094 | 官方 A 股数据（比 akshare 稳定），支持 MCP | 建议调研 |
| **FinnewsHunter** | 1488 | 多 agent 实时新闻情绪分析 | 建议调研 |
| **Stocksera** | 779 | 60+ 另类数据（散户持仓/做空） | 记录即可 |
| **akshare-one-mcp** | 226 | akshare 的 MCP 封装 | 建议调研 |
| **tradex-hub** | 35 | A 股 129 个 MCP 工具 + 多源降级 | 架构参考 |

**对每个调研项输出**：`output/marvis_enhance_<name>.md`，含：
- 一句话定位
- 与 2hao 的对接点（哪个数据键/哪个阶段）
- 安装成本评估（依赖/凭据/维护）
- 建议：接入 / 观望 / 不接（附理由）

---

## 七、完成标准（全部满足才算完成）

- [ ] `output/marvis_setup_check.md` 存在，环境检查 ✅
- [ ] last30days SKILL.md 存在，`last30days.py --help` 可运行，doctor 输出诊断
- [ ] yichen-web-research + 4 子 skill 的 SKILL.md 存在，`plan_hengzong_research.py --help` 可运行
- [ ] `_last30days_search('宁德时代')` 验证通过（返回数据 或 确认静默降级）
- [ ] 若本机 Python <3.12，已安装 Python 3.12 或用 py -3.12 调用并记录
- [ ] 所有操作走 git 提交（`chore(marvis): install last30days + yichen skills`）
- [ ] 本执行记录写入 `DELIVERY_LOG_20260901.md` 附录

---

## 八、注意事项

1. **沙箱限制**：2026-09-01 沙箱验证过——last30days 需要 Python 3.12+（沙箱 3.10 不满足）、skills 目录只读、无法全局安装。**必须在 Windows 本机执行**。
2. **API 凭据**：last30days 免费源（Reddit 公开/HN）不需要 key；增强源需 `SCRAPECREATORS_API_KEY`。不要让用户为测试付费。
3. **不要改 2hao 代码**：`data_collector.py` 的桥接已就绪，安装后自动生效。除非验证发现 bug，否则不动代码。
4. **遇到问题**：把错误输出完整记录到 `output/marvis_setup_errors.log`，先自查（PATH/Python 版本/网络代理），再决定是否求助。
5. **安全**：不打印任何 API key/Token；不绕过任何平台限制。
