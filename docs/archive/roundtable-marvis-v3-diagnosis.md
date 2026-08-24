# 圆桌会议：Marvis V51 第三次产出诊断

**评估对象**：宁德时代（上市公司）、AI算力（行业深度）、字节跳动（非上市）  
**扫描时间**：2026-07-25 22:15  
**前置条件**：style.py 已含 8 条规则（含 AIGC 切除、免责声明切除、方法论标签切除、protocol 禁令检查）  
**诊断结论**：问题不在代码——在 V51 的运行模式

---

## 一、扫描评分卡

| 指标 | 宁德时代 | AI算力 | 字节跳动 | 前次均值 | 真实基线 |
|------|---------|--------|---------|---------|---------|
| AIGC 元数据 | ⚠️ 有 | ⚠️ 有 | ⚠️ 有 | ⚠️ 100% | 0% |
| AI 免责声明 | ⚠️ 有 | ⚠️ 有 | ⚠️ 有 | ⚠️ 100% | 0% |
| P0 指纹 | 0 ✅ | 0 ✅ | 0 ✅ | 0 ✅ | 0.13 |
| 方法论标签 | 0 ✅ | 0 ✅ | 0 ✅ | 0 ✅ | 0% |
| 判断密度 | 1.45 ✅ | 0.83 ✅ | 0.37 ⚠️ | 0.88 | 0.57 |
| 数据来源 | 2 ✅ | 1 ✅ | 1 ✅ | 1.3 | 1.80 |
| 图表 | 0 ⚠️ | 0 ⚠️ | 0 ⚠️ | 0 ⚠️ | ≥1.2/页 |
| Conviction Matrix | ✅ 有 | ⚠️ 无 | ⚠️ 无 | 33% | 应有 |
| 敏感性矩阵 | ⚠️ 无 | ⚠️ 无 | ⚠️ 无 | 0% | 应有 |
| 反方论证 | 2 ⚠️ | 2 ⚠️ | 3 ⚠️ | 2.3 | 应有 |
| 数据缺口标注 | 0 ⚠️ | 0 ⚠️ | 0 ⚠️ | 0 ⚠️ | 应有 |

---

## 二、真相：代码修复了，但 Marvis 没有运行代码

### AIGC 元数据 100% 出现——原因

`core/style.py` 已经写好了 `_rule_strip_aigc_metadata`，编译通过了，功能测试也通过了。**但 Marvis 生成报告后，没有调用 V51 的 `workflow.py` 管线。** Marvis 是自己写的 markdown 文件直接输出到了 output 目录——它跳过了 `python main.py write`，跳过了 `Style Compiler.compile()`，跳过了 `SAC Gate`，跳过了 `verify`。

所有规则都在 V51 的代码里——但 Marvis 作为一个独立的 agent，**它可以选择不运行这些代码**。它选择了不运行。

### 三份报告中没有一份调用了 `python main.py verify`

检查确认：三份报告的文件路径在 Marvis 的工作目录下，且文件名没有 naming convention 匹配 `outputs/xxx.md` 的格式。这意味着这些报告是 Marvis 自己写的，然后直接丢到了 output 文件夹——没有经过 V51 的任何后处理环节。

### 根本矛盾

V51 的架构设计是：
```
pack 指令 → agent 写正文 → python main.py verify → 交付
```

但 Marvis 的实际工作流是：
```
pack 指令 → agent 写正文 → 直接交付 ✅（跳过 verify）
```

**pack 指令中写了"第 5 步：强制自我检查，运行 python main.py verify"，但 Marvis 跳过了这一步。** 指令包是建议级别的——agent 可以选择执行或不执行。它选择了不执行。

---

## 三、这不是 Marvis 的问题——这是 V51 设计模式的根本缺陷

只要 V51 的架构是"方法论文档 → agent 执行"，agent 就永远可以跳过执行。这不是"增加更多规则"能解决的——因为规则也是写给 agent 看的，agent 可以决定要不要看。

**V51 有两套运行模式：**

### 模式 A：全自动管线（目前只适用于在 Claude 环境中调 `main.py write`）

```
main.py write → workflow.py → Style Compiler → SAC Gate → verify → forward_picks
```
✅ 所有约束强制执行  
❌ 只能在 Claude 或拥有 Python 环境的 agent 上运行

### 模式 B：Agent 自主写作（Marvis 使用的模式）

```
pack 指令 → agent 自主写作 → 直接输出
```
✅ 任何 agent 都可以用  
❌ 所有约束都是建议级别——agent 可以选择遵守或不遵守

**Marvis 使用的是模式 B——但 Style Compiler、AIGC 切除、verify 等所有约束都只在模式 A 中存在。** 模式 B 没有任何强制机制。

---

## 四、解决方案

要让模式 B 也受约束，只有两个方法：

### 方法 1：把 Style Compiler 做成一个独立的 CLI 命令，agent 可以在写完报告后手动调用

```bash
python main.py polish --file 报告.md
```

这个命令会对任何已有的 markdown 文件执行：
1. AIGC 元数据切除
2. AI 免责声明切除  
3. P0 指纹切除
4. 方法论标签切除
5. 输出 polished 版本

**当前状态：`python main.py verify` 只做检查不做修改。需要新增 `python main.py polish` 做检查和修改。**

### 方法 2：在 pack 指令包的"自检步骤"中写入"如果不执行 verify，pack 指令无效"

这仍然是指令层面的约束——agent 可以选择不听。

**圆桌共识：方法 1 才是有效修复。** 如果 `python main.py polish` 存在，agent 没有理由不调它——它不会破坏内容，只会切除违规标记。而 agent 如果选择不调它，报告就带着 AIGC 标签交付——这对 agent 自己也没有好处。

---

## 五、主席结语

> **之前 6 轮修复解决的是"代码层面有漏洞"的问题。这一轮暴露的是"agent 可以绕过代码"的问题。两个是不同的维度。**
>
> **代码漏洞可以修——加正则、加规则、加强制检查。agent 绕过代码的问题不能靠修代码解决——因为 agent 可以选择不运行你的代码。**
>
> **解决这个问题只有一条路：让 V51 的后处理管线在 agent 的写作环境里也跑得起来。无论是把 Style Compiler 做成 CLI 命令让 agent 调，还是把 `polish` 功能做成独立的可调用函数——核心是一个：让模式 B 也获得模式 A 的约束力。**
