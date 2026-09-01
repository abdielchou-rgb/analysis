# Marvis 交接指令：3 项收尾操作

**日期**：2026-09-01
**交接来源**：2hao-analyst 审计会话（已核验 Marvis 工作总结）
**执行位置**：Windows 本机（沙箱无法执行）

---

## 背景

Marvis 的 51ebbaf 提交实际已成功（R rules 101/101 + claim inline + yfinance HK/US + 巨石拆解），但留下 3 个收尾项。以下操作需在 Windows 本机完成。

---

## 操作 1：删除 git 残锁

**原因**：`.git/index.lock` 残留（提交中断时留下），阻塞所有 git 写操作。

```bash
cd D:\Claude\projects\2hao-analyst

# 1. 确认无 git 进程在跑
tasklist | findstr git

# 2. 删除残锁
del .git\index.lock

# 3. 验证 git 恢复
git status
```

**验收**：`git status` 能正常输出（不再挂起）。

---

## 操作 2：提交 metrics.py 防锁修复

**原因**：我在沙箱给 `core/metrics.py` 加了 P1-1 防锁重试（`_write()` + `_fallback_db_path()`），修复 observability.db 被锁导致测量层停摆的问题。改动未提交。

```bash
cd D:\Claude\projects\2hao-analyst

# 1. 确认改动存在
git diff core/metrics.py | findstr "_write _fallback_db_path"

# 2. 提交
git add core/metrics.py
git commit -m "fix(P1-1): observability 防锁重试 — 主库被锁时切项目内副本写入

Windows 共享文件锁场景：observability.db 被其他进程占用时
SQLite 写报 disk I/O error → validate_history/quality_trends 停摆。
新增 _write() 重试 + _fallback_db_path() 副本兜底（data/observability_fallback/），
write-and-forget 不阻塞主流程。"
```

**验收**：`git log --oneline -1` 显示新提交。

---

## 操作 3：删除 forward_picks 旧残留

**原因**：`data/forward_picks.csv`（根目录）是 V51 旧格式，`data/forward_picks/forward_picks.csv`（子目录）才是现行（R63+ 带 pick_id/anchor_nav）。

```bash
cd D:\Claude\projects\2hao-analyst

# 1. 确认两个文件（子目录的是现行的，别删错）
dir data\forward_picks\forward_picks.csv   # 现行 ✅ 保留
dir data\forward_picks.csv                  # 旧残留 ❌ 删除

# 2. 删除旧残留
del data\forward_picks.csv

# 3. 验证
git status | findstr forward_picks
```

**验收**：`git status` 显示 `data/forward_picks.csv` 已删除。

---

## 完成后

1. 跑一次验证：`python -c "from core.forward_picks import ForwardPicksDB; print(len(ForwardPicksDB().load_all()), '条预测')"`
2. 在 `DELIVERY_LOG_20260901.md` 附录追加：
   > 2026-09-01 收尾：index.lock 已删、metrics.py 防锁已提交、forward_picks 旧残留已清。

---

## 注意事项

- **操作 1 必须最先做**——锁不删，2/3 无法执行
- 若 `tasklist | findstr git` 有进程，等它结束再删锁
- 不要动 `data\forward_picks\` 子目录（现行数据）
- 沙箱已验证 metrics.py 防锁逻辑正确（副本写入 trends=2 validate=18），提交后即生效
