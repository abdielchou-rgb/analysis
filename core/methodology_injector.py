"""V51.6 投行方法论注入器

从137份估值培训课件 + 84份方法培训教材中提取方法论精华，
注入V51的protocol.py写作指令和研究协议。

核心来源:
  - BOA iQmethod: 全球统一估值方法论，5阶段框架
  - UBS Valuation Series: DCF/PE/PEG/Eval Method 标准
  - Goldman Sachs: 三种工具 (Returns/Multiple/DCF) 统一视角
  - 中金: 估值与财务模型6章结构
  - 中信金通: 绝对估值vs相对估值框架

注入方式: 不是加更多规则（规则已够多），是加"思考框架"
"""

PROTOCOL_INJECTION = """
### 投行方法论文档注入（来自UBS/BOA/高盛/中金培训材料）

以下是全球顶级投行在估值分析中使用的思考框架。它们不是规则——它们是"真正的方法论"。
在写作中自然地吸收这些思考方式，而不是机械地引用术语。

#### 一、BOA iQmethod 五阶段估值框架

每一份完整的估值分析都应该覆盖这五个阶段。不是按顺序写，是确保五者都在：

1. **Business Understanding**: 公司怎么赚钱？核心驱动因素是什么？竞争优势可持续吗？
   → 对应SAC中商业模式维度，但写法应该是"XX的生意本质是……"而非"商业模式分析如下"

2. **Financial Analysis**: 历史财务数据告诉了你什么？趋势、比率、质量。
   → "过去三年营收CAGR 18%，但现金流质量在下滑——应收账款周转天数从45天增至62天"

3. **Forecasting**: 未来会怎样？预测不是猜——是"基于明确假设的外推"。
   → 每个预测假设都要有来源或逻辑根："我们假设毛利率从28%逐步降至25%，原因是……"

4. **Valuation**: 用2-3种方法交叉验证，没有一种方法是绝对正确的。
   → DCF给一个区间，可比给一个区间，交集就是合理范围

5. **Conclusion**: 基于以上，给出明确的判断和风险。
   → "我们认为在当前价格水平上有15%的上行空间，核心风险是……"

#### 二、UBS 估值系列的核心洞察

**关于DCF**:
  DCF的价值不在于"算出一个精确的目标价"——在于它强迫你把所有的假设显性化。
  DCF对输入参数极度敏感：WACC变动1%，目标价可能变动15-20%。
  因此，DCF的"正确用法"是敏感性矩阵，而不是单个数字。
  正如UBS材料所言:"DCF is a very powerful tool for the scrupulous analyst,
  but the unscrupulous can use it to justify just about any price."

**关于PE**:
  PE不是"便宜的指标"——它是三个变量的函数：
    PE = f( growth, risk, return on equity )
  成长股PE高不只是因为"市场情绪"——是因为增长直接影响价值。
  跨行业比较PE是误导，必须在同行业内比较。

**关于估值方法论的选择**:
  UBS建立了估值方法评估框架，核心原则是：
  "There is a propensity to discard traditional techniques.
  However, new techniques should be assessed thoroughly."
  不要为了"显得专业"使用复杂方法——DCF够用时不需要LBO。

**关于PEG**:
  PEG假设增长和PE成比例——但这个假设在很多行业不成立。
  PEG作为筛选工具有用，作为定价工具危险。

#### 三、高盛三工具统一视角

  Goldman Sachs的核心观点：
  "三种最流行的估值工具——Returns-based Analysis, Multiple Analysis, DCF——
  它们不是三种不同的方法，它们是看待同一件事的三种不同方式。"

  这意味着：如果三种方法给出冲突的信号，不是"哪个方法错了"——
  是"对同一个公司的理解还不够深"。

  实际应用：
  - DCF说低估，可比说高估？→ 检查假设是否一致
  - 回报分析说ROIC > WACC，但市场给低估值？→ 市场在 discount 什么风险？

#### 四、中金估值与财务模型框架

  中金培训材料的六章结构是一个清晰的分析管线：
    1. 估值基本概念
    2. 可比公司法
    3. 历史交易法
    4. 现金流概念及DCF
    5. IPO估值vs M&A估值
    6. 建模过程和注意事项

  关键判断："没有一种估值方法是绝对正确的。每种方法都有其优缺点。
  通常会使用多种估值方法来相互验证，并最终确定一个价值区间。"

  这句话应该成为每份估值分析的底色——不把估值当结论，当区间。

#### 五、中信金通二元框架

  绝对估值法 (DCF/DDM) vs 相对估值法 (PE/PB/PEG/EV/EBITDA)
  两者不是"选哪个"的关系——是"先用哪个定位，再用哪个验证"的关系。

#### 总结：如何自然地应用这些方法论

  不要在报告中写"我们使用DCF和可比公司法进行估值"——这是AI写法。
  资深分析师这样写：
  "我们的估值区间基于两种方法交叉验证：
  DCF框架下假设WACC=11%(Beta 1.35, 无风险利率3%), 永续增长2.5%, 目标价45-52元；
  可比法参考同行PE 22-28x区间，当前估值处于下限。
  两种方法的交集在48-50元，构成了我们认为的合理估值锚点。"
"""

# 针对不同类型报告的差异化注入
SECTOR_SPECIFIC_VALUATION = {
    "金融": "金融股估值核心不是DCF——是账面价值和ROE的回归分析。\n参考中金方法论: 使用PB-ROE框架替代DCF。\n关键变量不是自由现金流——是资产质量、净息差趋势、资本充足率。",
    "科技": "科技股估值面临的核心挑战是: 高增长、多变的护城河、不确定的终局。\n参考UBS PE/PEG框架: 不能只看当期PE。\n如果增长驱动来自技术代差而不是资本投入,\n用PEG或EV/Sales替代PE可能更合理。\n参考Goldman Sachs回报分析: 高ROIC的科技公司应该享有估值溢价。",
    "医药": "医药股估值的特殊之处在于管线价值远大于当前利润。\n参考BOA iQmethod的阶段分析法: 不同临床阶段的管线需要不同的折现率。\nPipeline的DCF和现有业务的DCF应该分开计算再合并。\n关键假设: 各阶段成功率(临床I/II/III期各有不同)。",
    "消费": "消费股估值的锚不是增长——是稳定性和品牌溢价。\n参考中金方法论: 消费品适用DCF(因为现金流稳定可预测)。\n但也需警惕: 品牌价值在DCF中不直接体现,\n需要结合可比PE法中的品牌溢价倍数调整。",
    "周期": (
        '周期股在行业低谷时PE是"假高", 在行业高峰时PE是"假低"。\n'
        "正确做法: 使用正常化利润(normalized earnings)替代当前利润。\n"
        "参考中信金通方法论: 周期股适合EV/EBITDA、P/B和P/NAV,\n"
        "不适合当期PE。\n"
        "DCF在周期底部最有用(因为市场过度悲观时DCF给出理性基准)。"
    ),
    "房地产": "地产股估值的行业特定方法: NAV(净资产价值估值)。\n每块土地的开发价值 + 已建成物业的租金价值 - 净负债。\nNAV折价/溢价是市场对管理层的信任投票。\n参考Goldman Sachs回报分析: 地产股的ROE主要来自杠杆, 需关注杠杆质量。",
}

# 注入到T0.5假说验证器的"验证框架"
HYPOTHESIS_VERIFICATION_FRAMEWORK = """
### 假说验证的三层框架（来自投行方法论培训）

不是"验证一个假设"，是"从三个视角审视一个假设"：

**视角一（基本面）**：
  这个假设和公司的核心驱动因素一致吗？
  → 如果假设"直销占比突破50%，利润弹性释放"——先问：直销和批发的吨价差是多少？
    这个价差可持续吗？如果直销占比真的到50%，经销商体系会有什么反应？

**视角二（市场定价）**：
  如果这个假设是对的，市场已经在多大程度上price in了？
  → 假设超预期利润 → 当前PE处于历史什么位置？
    如果PE已经在历史P75以上，市场可能已经部分定价了乐观预期。

**视角三（风险对称性）**：
  如果这个假设是错的，损失有多大？如果是对的，收益有多大？
  → DCF是验证风险对称性最好的工具——改一个关键假设，
    目标价变动多少？这个变动是你愿意承受的吗？
"""

# 注入到Style Compiler的"人感"增强层
HUMAN_TOUCH_METHODOLOGY = """
### "像人"的深层规则（来自投行培训材料中资深分析师的写作方式）

不是格式规则——是思维方式：

1. **每一章开始先阐明这一章在整体论证中的角色**
   "在判断直销占比的利润弹性之前，我们需要先理解茅台的产能天花板在哪里"
   而不是直接扔出数据。
   → 这种"定位-展开-总结"的结构是顶级分析师的标准写法。

2. **证据的权重比数量重要**
   "我们有10个数据点支持这个判断"不如"我们有一个关键数据——它来自公司官方渠道
   且与独立第三方数据交叉验证一致"
   → UBS培训材料中反复提到: "One high-quality source is worth ten low-quality ones"

3. **在给出判断时，同时给出"为什么其他观点可能是错的"**
   "市场认为直销占比45%已近天花板——这个观点的核心论据是……
   但我们认为这个论据忽略了两个关键变量……"
   → 这是BOA iQmethod中"Challenge your assumptions"环节的具体体现。

4. **估值不是一个数字，是一个区间——两个方法交叉验证的交集**
   不写"目标价50元"——写"基于DCF和可比法的交叉验证，我们判断合理价值区间在45-55元"
   → 中金培训: "多种估值方法相互验证，确定价值区间"
"""


def get_protocol_injection_text(depth: str = "standard") -> str:
    """获取注入文本。"""
    return PROTOCOL_INJECTION


def get_sector_valuation_guide(sector: str) -> str:
    """获取行业特定估值指引。"""
    for key, value in SECTOR_SPECIFIC_VALUATION.items():
        if key in sector:
            return value
    return ""


def inject_into_protocol(protocol_text: str, sector: str = "", depth: str = "standard") -> str:
    """注入方法论到研究协议文本。"""
    lines = [protocol_text]
    lines.append("\n\n---\n")
    lines.append("### 投行方法论知识注入（系统自动附加）\n")
    lines.append("以下内容不是写作规则——是顶级投行培训材料中的思考框架。")
    lines.append("自然地吸收它们，而不是机械地引用。\n")

    if sector:
        sv = get_sector_valuation_guide(sector)
        if sv:
            lines.append(f"**行业特定估值建议:**\n{sv}\n")

    if depth in ("deep", "standard"):
        lines.append("**估值方法论:**")
        lines.append(
            "- BOA iQmethod: Business Understanding → Financial Analysis → Forecasting → Valuation → Conclusion"
        )
        lines.append("- UBS: DCF是假设显性化的工具，不是精确值。敏感性矩阵比单一目标价重要。")
        lines.append("- UBS: PE是growth, risk, ROE三个变量的函数——不要跨行业比较PE。")
        lines.append("- Goldman Sachs: Returns/Multiple/DCF是同一件事的三种视角——冲突时反思假设而非丢弃方法。")
        lines.append('- 中金: "没有一种方法是绝对正确的"——多种方法交叉验证确定区间。\n')

    return "\n".join(lines)
