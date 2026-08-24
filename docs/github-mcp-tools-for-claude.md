# GitHub 精选工具清单 — Claude Desktop 能力提升

> 筛选标准：本机已有配置 + 投研管线场景适配 + 高信号低噪音
> 更新日期：2026-08-05

## 一、本机已部署（6个MCP + 1个浏览器）

| 名称 | 用途 | 状态 |
|------|------|------|
| tavily-mcp | Web搜索 | ✅ |
| akshare-mcp | A股/财务数据 | ✅ |
| browser-rendering | Cloudflare浏览器截图/导航/调试 | ✅ 刚部署 |
| composio | 100+工具集成网关 | ✅ |
| headroom | 本地AI计算 | ✅ |
| crawl4ai | 网页抓取 | ✅ |

## 二、推荐部署（6个高价值MCP）

### 1. Sequential Thinking — 强制分步推理（必装）
- **仓库**: [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking)
- **命令**: `npx -y @modelcontextprotocol/server-sequential-thinking`
- **价值**: 复杂推理时强制分步输出中间结论，防跳步——直接针对圆桌审计发现的分析深度不足问题

### 2. GitHub MCP — 代码仓库操作
- **仓库**: [github/github-mcp-server](https://github.com/github/github-mcp-server)
- **命令**: `npx -y @modelcontextprotocol/server-github` + GitHub PAT
- **价值**: 当前无法直接git操作——每次commit/PR/查issues都要手动。接上后可直接查GitHub issues、创建PR、管理workflows

### 3. Puppeteer MCP — 本地浏览器自动化
- **仓库**: [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers/tree/main/src/puppeteer)
- **命令**: `npx -y @modelcontextprotocol/server-puppeteer`
- **价值**: 补充Cloudflare浏览器——本地无头Chrome可处理需要登录/复杂交互的页面，不受Cloudflare keep_alive限制

### 4. Context7 — 实时最新文档查询
- **仓库**: [upstash/context7](https://github.com/upstash/context7)
- **命令**: `npx -y @upstash/context7-mcp`
- **价值**: 查询最新SDK/库文档时不用过期训练数据；投研场景下查最新API文档、政策法规

### 5. SQLite MCP — 本地数据库直连
- **仓库**: [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite)
- **命令**: `npx -y @modelcontextprotocol/server-sqlite /path/to/db`
- **价值**: financials.db（535万行）和 predict db 能直接用SQL查询，不用Python脚本。复杂join/聚合一条MCP调用完成

### 6. Playwright MCP — 更强浏览器自动化
- **仓库**: [executeautomation/mcp-playwright](https://github.com/executeautomation/mcp-playwright)
- **命令**: `npx -y @executeautomation/playwright-mcp-server`
- **价值**: Playwright截图质量高于Puppeteer，支持多Tab并行操作——数据采集时同时开多个页面抓不同来源

## 三、Claude Code Plugin 推荐（2个高价值）

### 1. Build System Plugin — 把Claude Code当构建系统
- **仓库**: [vscarpenter/claude-code-build-system](https://github.com/vscarpenter/claude-code-build-system)
- **价值**: 把CLAUDE.md + Makefile/Justfile整合，每次编辑后自动跑lint/test/build——当前iron_gate脚本需手动python3调用

### 2. Prompt Intercept Pattern — Hook拦截指令模式
- **仓库**: [kylesnowschwartz/prompt-intercept-pattern](https://github.com/kylesnowschwartz/prompt-intercept-pattern)
- **价值**: 在prompt发送LLM前注入标准前缀/后缀——可替代当前CLAUDE.md中大量"原则/铁律"文本，减少每次会话的token消耗

## 四、Skills 推荐（3个高价值）

### 1. Debug-Gen Skill — 从错误日志生成修复代码
- 将2hao-root-cause的"四阶段调试法"升级为自动生成修复方案

### 2. Memory-Bank Skill — 结构化上下文记忆
- 比当前MEMORY.md更结构化——自动跟踪项目状态、决策、约束，而非手动写memory

### 3. Tdd-Workflow Skill — 测试驱动开发流水线
- 自动red-green-refactor循环——写测试→跑失败→写最小实现→跑通过→重构

## 五、部署优先级

| 优先级 | 名称 | 理由 |
|--------|------|------|
| P0 | Sequential Thinking | 零配置，直接强化推理质量 |
| P0 | GitHub MCP | 解开git操作瓶颈 |
| P1 | SQLite MCP | 直连数据库，省掉Python脚本中转 |
| P1 | Context7 | 实时文档，不再被知识截止日期限制 |
| P2 | Puppeteer MCP | 浏览器功能增强 |
| P2 | Playwright MCP | 多页面并行采集 |