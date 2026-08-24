# 解决"Agent 反复确认下载/引入文件"——顶级解法

> 问题：Marvis 跑管线时反复找你确认"下载未知风险文件"，打断流程
> 本质：权限确认疲劳（Permission Fatigue）——安全机制过于频繁触发，拖慢正常任务
> 日期：2026-08-06

---

## 一、问题本质

Agent 每个"下载/执行未知文件"动作都弹确认 = **权限粒度太细 + 无信任基线**。顶级做法不是"取消安全"，而是**"建立信任层级，让已信任的动作自动执行"**。

---

## 二、顶级解法（按层级）

### 解法 1：允许列表（Allowlist）——最核心

**原理**：明确声明"哪些路径/操作永远允许"，命中即自动执行，不确认。

**Claude Code 落地**（`~/.claude/settings.json` 或项目 `.claude/settings.json`）：

```json
{
  "permissions": {
    "allow": [
      "Bash(python:*)",
      "Bash(pip:*)",
      "Bash(python scripts/run_reports.py:*)",
      "Read(D:/2hao-analyst/data/*)",
      "Read(D:/2hao-analyst/output/*)",
      "Write(D:/2hao-analyst/output/*)"
    ],
    "deny": [
      "Bash(rm -rf:*)",
      "Bash(curl:*)",
      "Bash(wget:*)",
      "Bash(eval:*)"
    ]
  }
}
```

**效果**：`python scripts/run_reports.py` 这类管线命令命中 allow → 自动执行，不弹确认。

### 解法 2：自动批准模式（Auto-approve）——针对信任场景

**原理**：对整个会话/任务开启自动批准，跳过所有确认。

**Claude Code 落地**：
```bash
# 启动时带 auto-approve（权限由 allow 列表控制）
claude --permission-mode acceptEdits --allowedTools "Bash(python:*)"
# 或环境变量
CLAUDE_CODE_ALLOWED_TOOLS="Bash(python:*)"
```

**Codex CLI 落地**（config.toml）：
```toml
[sandbox_workspace_write]
network_access = false
write_paths = ["/sessions/*/mnt/2hao-analyst/output"]
```

### 解法 3：路径白名单 + 沙箱（Sandbox）——从源头减少未知

**原理**：把 Agent 限制在**可信目录**内，只有目录外的操作才需确认。

**落地**：
- 声明 `write_paths`（只允许写 output/ data/）
- 网络下载默认拦截（`network_access=false`），除非显式 allow 某域
- 下载文件先校验（hash/来源），不在白名单域内的 URL 自动拒绝

### 解法 4：命令分类授权（Granular Permissions）

**原理**：按命令类别分级，高频安全命令自动放行，危险命令必须确认。

| 命令类别 | 策略 | 示例 |
|---------|------|------|
| 管线运行 | ✅ 自动 | `python scripts/run_reports.py` |
| 依赖安装 | ✅ 自动 | `pip install` |
| 数据读写 | ✅ 自动（output/内） | Read/Write output/* |
| 网络下载 | ⚠️ 白名单域自动，其他确认 | curl 官方源 ✓，未知域 ✗ |
| 危险操作 | ❌ 永远确认 | rm -rf / eval / 任意shell |

### 解法 5：可信源清单（Trusted Sources）

**原理**：维护一份可信域名/仓库清单，命中即自动下载。

```json
{
  "trusted_sources": [
    "pypi.org", "github.com", "files.pythonhosted.org",
    "akshare.com", "eastmoney.com", "baostock.com"
  ]
}
```
下载 URL 命中可信源 → 自动；否则确认。

### 解法 6：分阶段信任升级（Progressive Trust）

**原理**：新命令第一次确认，跑过 N 次后自动加入 allow 列表。

- Marvis 跑 `python scripts/run_reports.py` 第一次确认
- 3 次成功后自动记录到 allow 列表
- 之后永远自动执行

---

## 三、给 2hao/Marvis 的具体建议

### 最简方案（10 分钟落地）

1. **给 Claude Code 配 allow 列表**（`D:/2hao-analyst/.claude/settings.json`）：
   - allow `Bash(python:*)`、`Bash(pip:*)`、Read/Write `output/*` `data/*`
   - deny `curl`/`wget`/`eval`（防未知下载）
2. **可信源清单**：pypi/github/eastmoney/akshare 自动放行
3. **管线命令封装**：把 `run_reports.py` 设为最高信任

### 理想方案（配合沙箱）

- Codex 沙箱：`write_paths` 限 output/data，`network_access` 白名单
- 下载只在可信源，未知域自动拒绝

---

## 四、为什么这样能根治"反复确认"

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| 跑管线 | 每次都确认 | allow `python scripts/run_reports.py` → 自动 |
| pip 装依赖 | 确认 | allow `Bash(pip:*)` → 自动 |
| 读 output 数据 | 确认 | allow `Read(output/*)` → 自动 |
| 下载未知源 | 确认 | 不在可信源 → 自动拒绝（不用问） |
| 危险操作 | 确认 | deny 列表 → 直接拒绝 |

**核心**：不是"取消确认"，而是"**把高频安全动作变成默认允许，把真正的危险动作变成默认拒绝**"——确认只在"不确定"时出现，正常任务零打断。

---

## 五、一句话总结

**权限确认疲劳的解 = 允许列表 + 可信源 + 沙箱三层**：已信任的（管线/依赖/数据）自动执行，真正危险的（未知下载/rm）自动拒绝，确认只留给中间地带。给 Marvis 配一个 `settings.json` 的 allow 列表 + 可信源清单，10 分钟让管线零打断运行。
