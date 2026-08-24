# R82 provider 路由优化——执行记录

> 修复："反复要求 DeepSeek key / Marvis 没被启动"两个 LLM 路由问题
> 日期：2026-08-06

## 问题根因

1. **反复要 key**：run_reports 子进程 `env = dict(os.environ)` 继承父进程环境，但父进程（Claude/终端）没加载 .env → 空 key
2. **Marvis 没启动**：responder 跑在宿主机，管线跑在 Linux 沙箱，两边不互通 → agent_provider 心跳不新鲜 → 快速失败回退 DeepSeek

## 已落地（3 项）

### 1. run_reports 子进程加载 .env（scripts/run_reports.py）
- subprocess 前主动读项目 .env 补进 os.environ（不覆盖已有）
- 根治"父进程没加载 .env → 子进程空 key → 反复要 key"

### 2. scheduler 启动 provider 诊断（pipeline/scheduler.py）
- 明确打印：LLM_PROVIDER（deepseek/agent_provider）+ DeepSeek key 状态 + responder 心跳状态
- agent_provider 模式但 responder 不在线 → 告警"需在本环境运行 watch"

### 3. 行业键白名单+边界冲突检测（pipeline/universe_build.py build）
- 匹配白名单外 → enrich 提示不错误归并
- 油位/液位/物位 并存会话 → 告警相近行业防串

## 回归
- 48 pytest 全绿

## 用户操作指引（现在会明确提示）
- 用 DeepSeek：确保 .env key 有效，scheduler 会打印"DeepSeek key: OK"
- 用 Marvis：`LLM_PROVIDER=agent_provider` + **同环境** `python scripts/agent_llm_responder.py watch`
- 若 DeepSeek 挂了想兜底 Marvis：必须同环境 responder + agent_provider
