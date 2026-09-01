证券研究报告·行业动态

# Databricks 公司开源 1320 亿参数 DBRX 模

## 型，目前性能最领先的 MoE架构大模型

## 核心观点

1. 大数据 AI 公司 Databricks 于 3 月 27 日开源了一款拥有1320 亿参数、使用 MoE（专家混合模型）架构的 Decoder-Only 大模型 DBRX。

2. DBRX 模型正式开源后，Databricks 官网发布了 DBRX 模型与其他大模型的功能对比与评价。综合来看，DBRX 模型的多项性能优于马斯克开源的 Grok-1，DBRX 是目前在所有开源大模型中性能处于领先位置。

3. Databricks 官网同时也发布了 DBRX 模型与其他大模型的训练和推理效率的评价对比，在使用新的 MoE 架构与更好的预训练数据后，DBRX 在模型质量与效率之间达到了一个更好的平衡。

## 产业要闻

【微软亚研院新作：让大模型一口气调用数百万个 API】

【英伟达 AI 芯片 H200 开始供货，性能相比 H100 提升60%-90%】

【小米汽车 SU7 / Pro / Max 正式发布并上市】

【苹果 Vision Pro 头显新专利获批：Light Seal 内嵌触控传感器，带来更丰富交互方式】

持续关注：

GPU：英伟达、超威半导体、海光信息等；

FPGA：安路科技-U 等；

SoC：高通、全志科技等；

自然语言处理：科大讯飞等；

计算机视觉：格灵深瞳-U 等；

自动驾驶：德赛西威、中科创达、均胜电子、光庭信息；

智慧交通：千方科技、万集科技；

AI+工业：中控技术、华大九天、广立微、概伦电子等。

风险提示：北美经济衰退预期逐步增强，宏观环境存在较大的不确定性，国际环境变化影响供应链及海外拓展；芯片紧缺可能影响相关公司的正常生产和交付，公司出货不及预期。

# 人工智能

## 维持

强于大市

于芳博

yufangbo@csc.com.cn

010-86451607

SAC 编号:S1440522030001

发布日期： 2024 年 04 月 01 日

## 市场表现

![](images/2e536fc64cef4daeb03fda5c2c94cf54ac2a8366e11c0c32ea3cdfac488b9b0d.jpg)

## 相关研究报告

## 目录

一、行业变化 .......
1.1 大数据人工智能公司 Databricks 开源通用大模型 DBRX....................
1.2 Databricks 发布的 DBRX 模型与其他公司大模型的功能性对比...............................................................1
1.3 Databricks 发布的 DBRX 模型的训练与推理效率.....................................................................................5
二、持续关注标的........................................................................................................................................6
三、行情回顾 ........... ...........7
四、产业要闻 .......
五、重要公告 .......................................... ........12
六、风险提示 ...................................................

## 图表目录

图表 1： Databricks 官网的开源 DBRX 模型用户注册界面..
图表2： DBRX 模型与其他开源 AI大模型在语言理解、编程、数学三个方面的能力对比.... .. 2
图表3： DBRX 在不同基准下与其他开源大模型的能力对比.... .. 3
图表4： DBRX 与其他闭源大模型的性能基准对比.... .. 4
图表5： DBRX 与其他模型的长上下文基准测试比较..... . 4
图表 6： DBRX 在两个 RAG 基准（Natural Questions 和 HotPotQA）上的质量对比 .. ... 5
图表 7： Gemini 1.5 Pro 上下文窗口方面与其他模型对比 ... .. 5
图表 8： DBRX 推理效率对比 ........... .. 6
图表10： 人工智能（中证）个股周涨幅前十名（%） .. 7
图表11： 人工智能（中证）个股周涨幅后十名（%）.... . 7
图表12： 重点公司股票涨跌详情（盈利预测均为Wind一致预测） .... 8

## 一、行业变化

## 1.1 大数据人工智能公司 Databricks 开源通用大模型 DBRX

3 月 27 日，Databricks 公司宣布开源通用大模型 DBRX（图表 1），在综合所有的大模型评价标准后，DBRX 无疑是目前表现质量最高的开源大模型之一，Databricks 公司树立了一个新的开源大模型行业标杆。同时，DBRX 模型还开放了 API 的使用，开源社区与企业们可以自己去运行和调用 DBRX。根据 Databricks 公司自身公布的测评结果，DBRX 模型超越了 Open AI 的 GPT-3.5，可以和 Gemini 1.0 Pro 相竞争。除此之外，DBRX 还是一个在代码生成领域表现尤其优秀的模型，它在编程方面的能力超过了例如 CodeLLaMA-70B 此类的一些专注于编程领域的大模型。

图表1： Databricks 官网的开源 DBRX 模型用户注册界面
![](images/7e25ce665d307c7aed549572781353d9bb1951eb0d88e0a0b9b2b736b1df270f.jpg)
资料来源：Databricks官网，中信建投

根据 Databricks 官网，DBRX 是一个基于 transformer 的 Decoder-Only 大语言模型。DBRX 共有 1320 亿参数，其中 360 亿参数在面临输入时时刻保持活跃状态，剩余的 980 亿参数则为专家混合层。DBRX 模型采用了专家混合模型（MoE）架构，由 12T 文本和代码数据预训练而成。

更细粒度的 MoE:对比其他开源的 MoE 架构大模型，例如 Mixtral 和 Grok-1，DBRX 更加具有细粒度，这代表它使用了更多的小型专家模型。DBRX 从 16 个专家模型中选择 4 个，而类似 Mixtral 和 Grok-1 则从 8 个专家模型中选择两个。这额外提供了 65 倍可能的专家模型组合，Databricks 公司表示这种变化提升了模型的质量。此外，DBRX 还使用了 tiktoken 存储库中提供的 GPT-4 分词器。

## 1.2 Databricks 发布的 DBRX 模型与其他公司大模型的功能性对比

在本周三 DBRX 模型正式开源后，Databricks 公司官网也可查询到公司发布的 DBRX 模型与其他公司

（Meta、Mixtral AI、xAI 等）的大模型性能对比。图表 2 中直观的呈现了在语言理解，编程，数学三个方面DBRX模型比起其他开源大模型更为强大的能力。另外，官网不仅公布了DBRX与其他开源大模型的性能对比，还公布了 DBRX 与一些闭源大模型的能力对比。

图表2： DBRX模型与其他开源 AI大模型在语言理解、编程、数学三个方面的能力对比
![](images/03e5db62b51e455164eb96446a28051107e9424e3fd3f38986a35590caf60a3a.jpg)
资料来源：Databricks官网，中信建投

图表 3 详细显示了 DBRX 和其他公司的开源大模型在不同应用领域的比较结果。从图表 3 可以看出，DBRX 的指导分数在综合基准、编程与数学能力、MMLU 三个方面表现优越。综合基准方面，DBRX 在 theHugging Face Open LLM Leaderboard（ARC-Challenge、HellaSwag、MMLU、TruthfulQA、WinoGrande 和 GSM8k的平均值）和 Databricks Model Gauntlet（包含世界知识，语言理解，典型问题解决等 6 个领域的 30 个任务维度）。DBRX 在以上这两个综合基准方面的得分最高，在 Hugging Face 基准方面得分 74.5%，排名第二的模型Mixtral Instruct 得分为 72.7%；Databricks Gauntlet 基准方面的得分为 66.8% ，位于第二名的 Mixtral Instruct得分为 60.7%。同时，DBRX 还在编程与数学方面十分强力。在 HumanEval 和 GSM8k 基准上的得分结果也高于其他的开源模型。

图表3： DBRX在不同基准下与其他开源大模型的能力对比
<table><tr><td rowspan=1 colspan=1>Model</td><td rowspan=1 colspan=1>DBRX Instruct</td><td rowspan=1 colspan=1>Mixtral Instruct</td><td rowspan=1 colspan=1>Mixtral Base</td><td rowspan=1 colspan=1>LLaMA2-70B Chat</td><td rowspan=1 colspan=1>LLaMA2-70B Base</td><td rowspan=1 colspan=1>Grok-11</td></tr><tr><td rowspan=1 colspan=1>Open LLM Leaderboard²(Avg of next 6 rows)</td><td rowspan=1 colspan=1>74.5%</td><td rowspan=1 colspan=1>72.7%</td><td rowspan=1 colspan=1>68.4%</td><td rowspan=1 colspan=1>62.4%</td><td rowspan=1 colspan=1>67.9%</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>ARC-challenge 25-shot</td><td rowspan=1 colspan=1>68.9%</td><td rowspan=1 colspan=1>70.1%</td><td rowspan=1 colspan=1>66.4%</td><td rowspan=1 colspan=1>64.6%</td><td rowspan=1 colspan=1>67.3%</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>HellaSwag 10-shot</td><td rowspan=1 colspan=1>89.0%</td><td rowspan=1 colspan=1>87.6%</td><td rowspan=1 colspan=1>86.5%</td><td rowspan=1 colspan=1>85.9%</td><td rowspan=1 colspan=1>87.3%</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>MMLU 5-shot</td><td rowspan=1 colspan=1>73.7%</td><td rowspan=1 colspan=1>71.4%</td><td rowspan=1 colspan=1>71.9%</td><td rowspan=1 colspan=1>63.9%</td><td rowspan=1 colspan=1>69.8%</td><td rowspan=1 colspan=1>73.0%</td></tr><tr><td rowspan=1 colspan=1>Truthful QA 0-shot</td><td rowspan=1 colspan=1>66.9%</td><td rowspan=1 colspan=1>65.0%</td><td rowspan=1 colspan=1>46.8%</td><td rowspan=1 colspan=1>52.8%</td><td rowspan=1 colspan=1>44.9%</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>WinoGrande 5-shot</td><td rowspan=1 colspan=1>81.8%</td><td rowspan=1 colspan=1>81.1%</td><td rowspan=1 colspan=1>81.7%</td><td rowspan=1 colspan=1>80.5%</td><td rowspan=1 colspan=1>83.7%</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>GSM8k CoT 5-shot maj@13</td><td rowspan=1 colspan=1>66.9%</td><td rowspan=1 colspan=1>61.1%</td><td rowspan=1 colspan=1>57.6%</td><td rowspan=1 colspan=1>26.7%</td><td rowspan=1 colspan=1>54.1%</td><td rowspan=1 colspan=1>62.9% (8-shot)</td></tr><tr><td rowspan=1 colspan=1>Gauntlet v0.34(Avg of 30+ diverse tasks)</td><td rowspan=1 colspan=1>66.8%</td><td rowspan=1 colspan=1>60.7%</td><td rowspan=1 colspan=1>56.8%</td><td rowspan=1 colspan=1>52.8%</td><td rowspan=1 colspan=1>56.4%</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>HumanEval⁵0-Shot, pass@1(Programming)</td><td rowspan=1 colspan=1>70.1%</td><td rowspan=1 colspan=1>54.8%</td><td rowspan=1 colspan=1>40.2%</td><td rowspan=1 colspan=1>32.2%</td><td rowspan=1 colspan=1>31.0%</td><td rowspan=1 colspan=1>63.2%</td></tr></table>

Databricks

图表 4 显示了 DBRX Instruct 和领先的闭源模型比较结果。DBRX Instruct 超越了 GPT-3.5（如比较 GPT-4 参考图表 4 中所述），并且与 Gemini 1.0 Pro 和 Mistral Medium 相比相当具有竞争力。具体而言：

从每个Databricks 公司考虑到的指标来看，DBRX 即使是表现最差的指标也与GPT-3.5 相持平。与Gemini1.0Pro 和 Mistral Medium 比较，DBRX 在 Inflection Corrected MTBench、MMLU、HellaSwag 和 HumanEval 上的得分高于 Gemini 1.0 Pro，在 HumanEval、GSM8k 和 Inflection Corrected MTBench 上的得分高于 MistralMedium，即使 Gemini 1.0 Pro 在 GSM8k 上的得分比 DBRX Instruct 要比 DBRX 高，而 Mistral Medium 在Winogrande 和 MMLU 上更强，综合来看，比较 Gemini 1.0 Pro 和 Mistral Medium 模型，DBRX 有自己独特的优势。

图表4： DBRX与其他闭源大模型的性能基准对比
<table><tr><td rowspan=1 colspan=1>Model</td><td rowspan=1 colspan=1>DBRXInstruct</td><td rowspan=1 colspan=1>GPT-3.57</td><td rowspan=1 colspan=1>GPT-48</td><td rowspan=1 colspan=1>Claude 3Haiku</td><td rowspan=1 colspan=1>Claude 3Sonnet</td><td rowspan=1 colspan=1>Claude 3Opus</td><td rowspan=1 colspan=1>Gemini 1.0Pro</td><td rowspan=1 colspan=1>Gemini1.5 Pro</td><td rowspan=1 colspan=1>MistralMedium</td><td rowspan=1 colspan=1>MistralLarge</td></tr><tr><td rowspan=1 colspan=1>MT Bench(Inflectioncorrected, n=5)</td><td rowspan=1 colspan=1>8.39±0.08</td><td rowspan=1 colspan=1>一</td><td rowspan=1 colspan=1>一</td><td rowspan=1 colspan=1>8.41±0.04</td><td rowspan=1 colspan=1>8.54±0.09</td><td rowspan=1 colspan=1>9.03 ± 0.06</td><td rowspan=1 colspan=1>8.23±0.08</td><td rowspan=1 colspan=1>一</td><td rowspan=1 colspan=1>8.05 ± 0.12</td><td rowspan=1 colspan=1>8.90 ± 0.06</td></tr><tr><td rowspan=1 colspan=1>MMLU 5-shot</td><td rowspan=1 colspan=1>73.7%</td><td rowspan=1 colspan=1>70.0%</td><td rowspan=1 colspan=1>86.4%</td><td rowspan=1 colspan=1>75.2%</td><td rowspan=1 colspan=1>79.0%</td><td rowspan=1 colspan=1>86.8%</td><td rowspan=1 colspan=1>71.8%</td><td rowspan=1 colspan=1>81.9%</td><td rowspan=1 colspan=1>75.3%</td><td rowspan=1 colspan=1>81.2%</td></tr><tr><td rowspan=1 colspan=1>HellaSwag 10-shot</td><td rowspan=1 colspan=1>89.0%</td><td rowspan=1 colspan=1>85.5%</td><td rowspan=1 colspan=1>95.3%</td><td rowspan=1 colspan=1>85.9%</td><td rowspan=1 colspan=1>89.0%</td><td rowspan=1 colspan=1>95.4%</td><td rowspan=1 colspan=1>84.7%</td><td rowspan=1 colspan=1>92.5%</td><td rowspan=1 colspan=1>88.0%</td><td rowspan=1 colspan=1>89.2%</td></tr><tr><td rowspan=1 colspan=1>HumanEval 0-Shotpass@1(Programming)</td><td rowspan=1 colspan=1>70.1%temp=0, N=1</td><td rowspan=1 colspan=1>48.1%</td><td rowspan=1 colspan=1>67.0%</td><td rowspan=1 colspan=1>75.9%</td><td rowspan=1 colspan=1>73.0%</td><td rowspan=1 colspan=1>84.9%</td><td rowspan=1 colspan=1>67.7%</td><td rowspan=1 colspan=1>71.9%</td><td rowspan=1 colspan=1>38.4%</td><td rowspan=1 colspan=1>45.1%</td></tr><tr><td rowspan=1 colspan=1>GSM8k CoT maj@1</td><td rowspan=1 colspan=1>72.8% (5-shot)</td><td rowspan=1 colspan=1>57.1% (5-shot)</td><td rowspan=1 colspan=1>92.0% (5-shot)</td><td rowspan=1 colspan=1>88.9%</td><td rowspan=1 colspan=1>92.3%</td><td rowspan=1 colspan=1>95.0%</td><td rowspan=1 colspan=1>86.5%(maj1@32)</td><td rowspan=1 colspan=1>91.7% (11-shot)</td><td rowspan=1 colspan=1>66.7% (5-shot)</td><td rowspan=1 colspan=1>81.0% (5-shot)</td></tr><tr><td rowspan=1 colspan=1>WinoGrande 5-shot</td><td rowspan=1 colspan=1>81.8%</td><td rowspan=1 colspan=1>81.6%</td><td rowspan=1 colspan=1>87.5%</td><td rowspan=1 colspan=1>一</td><td rowspan=1 colspan=1>一</td><td rowspan=1 colspan=1>一</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>一</td><td rowspan=1 colspan=1>88.0%</td><td rowspan=1 colspan=1>86.7%</td></tr></table>

Databricks

对于在长文本任务和 RAG基准的测试。DBRX Instruct 训练上下文窗口大小为 32K token。图表 5 将其性能与 Mixtral Instruct 以及最新版本的 GPT-3.5 Turbo 和 GPT-4 Turbo API 在一系列长上下文基准测试上进行了比较。结果显示，GPT-4Turbo 通常是执行这些任务的最佳模型。而 DBRX Instruct 表现比 GPT-3.5Turbo 好；DBRX Instruct 和 Mixtral Instruct 的整体性能相似。

对于在长文本任务和 RAG 基准方面的测试，Databricks 使用 32K token 大小的上下文窗口进行 DBRX 的训练。图表 5 将其这两个领域的性能与 Mixtral Instruct 以及最新版本的 GPT-3.5 Turbo 和 GPT-4 Turbo API 进行了比较。结果显示，GPT-4 Turbo 通常是执行这些任务的最佳模型。而 DBRX Instruct 表现比 GPT-3.5Turbo 好；和 Mixtral Instruct 的整体性能类似。

图表5： DBRX与其他模型的长上下文基准测试比较
<table><tr><td rowspan=1 colspan=1>Model</td><td rowspan=1 colspan=1>DBRX Instruct</td><td rowspan=1 colspan=1>Mixtral Instruct</td><td rowspan=1 colspan=1>GPT-3.5 Turbo (API)</td><td rowspan=1 colspan=1>GPT-4 Turbo (API)</td></tr><tr><td rowspan=1 colspan=1>Answer in Beginning Third of Context</td><td rowspan=1 colspan=1>45.1%</td><td rowspan=1 colspan=1>41.3%</td><td rowspan=1 colspan=1>37.3%*</td><td rowspan=1 colspan=1>49.3%</td></tr><tr><td rowspan=1 colspan=1>Answer in Middle Third of Context</td><td rowspan=1 colspan=1>45.3%</td><td rowspan=1 colspan=1>42.7%</td><td rowspan=1 colspan=1>37.3%*</td><td rowspan=1 colspan=1>49.0%</td></tr><tr><td rowspan=1 colspan=1>Answer in Last Third of Context</td><td rowspan=1 colspan=1>48.0%</td><td rowspan=1 colspan=1>44.4%</td><td rowspan=1 colspan=1>37.0%*</td><td rowspan=1 colspan=1>50.9%</td></tr><tr><td rowspan=1 colspan=1>2K Context</td><td rowspan=1 colspan=1>59.1%</td><td rowspan=1 colspan=1>64.6%</td><td rowspan=1 colspan=1>36.3%</td><td rowspan=1 colspan=1>69.3%</td></tr><tr><td rowspan=1 colspan=1>4K Context</td><td rowspan=1 colspan=1>65.1%</td><td rowspan=1 colspan=1>59.9%</td><td rowspan=1 colspan=1>35.9%</td><td rowspan=1 colspan=1>63.5%</td></tr><tr><td rowspan=1 colspan=1>8K Context</td><td rowspan=1 colspan=1>59.5%</td><td rowspan=1 colspan=1>55.3%</td><td rowspan=1 colspan=1>45.0%</td><td rowspan=1 colspan=1>61.5%</td></tr><tr><td rowspan=1 colspan=1>16K Context</td><td rowspan=1 colspan=1>27.0%</td><td rowspan=1 colspan=1>20.1%</td><td rowspan=1 colspan=1>31.7%</td><td rowspan=1 colspan=1>26.0%</td></tr><tr><td rowspan=1 colspan=1>32K Context</td><td rowspan=1 colspan=1>19.9%</td><td rowspan=1 colspan=1>14.0%</td><td rowspan=1 colspan=1>一</td><td rowspan=1 colspan=1>28.5%</td></tr></table>

资料来源：Databricks官网，中信建投

RAG 基准是一个十分流行的模型长文本任务性能测试方法。图表 6 显示了 DBRX 在两个 RAG 基准上的模型质量。DBRX Instruct 与 Mixtral Instruct、 LLaMA2-70B Chat 等开源模型、当前版本的 GPT-3.5 Turbo 相比也具有竞争力。

图表6： DBRX 在两个 RAG 基准（Natural Questions 和 HotPotQA）上的质量对比
<table><tr><td rowspan=1 colspan=1>Model</td><td rowspan=1 colspan=1>DBRX Instruct</td><td rowspan=1 colspan=1>Mixtral Instruct</td><td rowspan=1 colspan=1>LLaMa2-70B Chat</td><td rowspan=1 colspan=1>GPT 3.5 Turbo (API)</td><td rowspan=1 colspan=1>GPT 4 Turbo (API)</td></tr><tr><td rowspan=1 colspan=1>Natural Questions</td><td rowspan=1 colspan=1>60.0%</td><td rowspan=1 colspan=1>59.1%</td><td rowspan=1 colspan=1>56.5%</td><td rowspan=1 colspan=1>57.7%</td><td rowspan=1 colspan=1>63.9%</td></tr><tr><td rowspan=1 colspan=1>HotPotQA</td><td rowspan=1 colspan=1>55.0%</td><td rowspan=1 colspan=1>54.2%</td><td rowspan=1 colspan=1>54.7%</td><td rowspan=1 colspan=1>53.0%</td><td rowspan=1 colspan=1>62.9%</td></tr></table>

资料来源：Databricks官网，中信建投

## 1.3 Databricks 发布的 DBRX 模型的训练与推理效率

Databricks 公司也同样对比了 DBRX 模型与其他大模型的训练和推理效率差异。Databricks 公司研究发现训练混合专家模型可以显著提高训练的计算效率（图表 7）。

图表7： Gemini 1.5 Pro 上下文窗口方面与其他模型对比
<table><tr><td rowspan=1 colspan=1>Model</td><td rowspan=1 colspan=1>Total Params</td><td rowspan=1 colspan=1>Active Params</td><td rowspan=1 colspan=1>Gauntlet Score</td><td rowspan=1 colspan=1>Relative FLOPs</td></tr><tr><td rowspan=1 colspan=1>DBRX MoE-A</td><td rowspan=1 colspan=1>7.7B</td><td rowspan=1 colspan=1>2.2B</td><td rowspan=1 colspan=1>30.5%</td><td rowspan=1 colspan=1>1x</td></tr><tr><td rowspan=1 colspan=1>MPT-7B (1T tokens)</td><td rowspan=1 colspan=1>I</td><td rowspan=1 colspan=1>6.7B</td><td rowspan=1 colspan=1>30.9%</td><td rowspan=1 colspan=1>3.7x</td></tr><tr><td rowspan=1 colspan=1>DBRX Dense-A (1T tokens)</td><td rowspan=1 colspan=1>I</td><td rowspan=1 colspan=1>6.7B</td><td rowspan=1 colspan=1>39.0%</td><td rowspan=1 colspan=1>3.7x</td></tr><tr><td rowspan=1 colspan=1>DBRX Dense-A (500B tokens)</td><td rowspan=1 colspan=1>一</td><td rowspan=1 colspan=1>6.7B</td><td rowspan=1 colspan=1>32.1%</td><td rowspan=1 colspan=1>1.85x</td></tr><tr><td rowspan=1 colspan=1>DBRX MoE-B</td><td rowspan=1 colspan=1>23.5B</td><td rowspan=1 colspan=1>6.6B</td><td rowspan=1 colspan=1>45.5%</td><td rowspan=1 colspan=1>1x</td></tr><tr><td rowspan=1 colspan=1>LLaMA2-13B</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>13.0B</td><td rowspan=1 colspan=1>43.8%</td><td rowspan=1 colspan=1>1.7x</td></tr></table>

资料来源：Databricks官网，中信建投

从单一因素讨论，预训练数据的质量对模型质量产生了重大影响。Databricks 公司使用 DBRX 预训练数据在 DBRX Dense-A 上训练了 7B 模型，它在 Databricks Gauntlet 上达到了 39.0%，对比之下 MPT-7B 模型虽然具有相同的 token 数，但 Gauntlet Score 得分只有 30.9%。Databricks 研究估计，新的预训练数据至少比用于训练 MPT-7B 的每一个 token 的数据好两倍，从另一角度讲，DBRX 达到相同模型质量只需要一半的 token 数量。Databricks 通过在 500B token 上训练 DBRX Dense-A 来确定了这一点；Dense-A 在 Databricks Gauntlet Score上的表现超过了 MPT-7B，达到了 32.1%。除了预训练数据的质量因素，另一方面讲，DBRX 使用的 GPT-4 的分词器可能也对模型的分数作出了重要贡献，因为它具有庞大的词汇量同时被认为尤其有效率。

图表 8 展示了 DBRX 及其类似使用 NVIDIA TensorRT-LLM 模型以及 Databricks 优化后的基础设施的模型的推理效率对比。一般来说，MoE 架构的模型的推理速度相比其他模型要快。DBRX 在这方面也不例外，DBRX 推理吞吐量比 132B 非 MoE 模型高 2-3 倍。

通常来说，推理效率和模型质量通常是矛盾的：较大的模型一般质量都会高，但较小的模型推理效率更高。使用 MoE 架构可以在模型质量和推理效率之间实现比其他模型更好的质量与效率平衡。例如，DBRX 的性能比 LLaMA2-70B 更高，并且由于激活参数数量约为 LLaMA2-70B 的一半，DBRX 推理量最高可提高 2 倍（图表 8）。此外，DBRX 比 Mixtral 小，质量相应较低，但推理量更高。

图表8： DBRX推理效率对比
![](images/c5846d531c4cd0d83b7ca2bb280bf1c61b9fbb6ed2befb3ad82db959eded44f7.jpg)
资料来源：Databricks官网，中信建投

## 二、持续关注标的

GPU：英伟达、超威半导体、海光信息等；

FPGA：安路科技-U 等；

SoC：高通、瑞芯微、晶晨股份、全志科技等；

自然语言处理：科大讯飞等；

计算机视觉：格灵深瞳-U 等；

自动驾驶：德赛西威、中科创达、均胜电子、光庭信息；

智慧交通：千方科技、万集科技；

AI+工业：中控技术、华大九天、广立微、概伦电子等。

## 三、行情回顾

上期，人工智能指数（中证）指数下跌 5.85%，本月份以来累计跌幅 0.35%。上期上证指数下跌0.23，，沪深 300 指数下跌 0.21%。

图表9： 中证人工智能指数、上证指数、沪深 300指数涨跌幅比较
![](images/49d9ee91f074d62472c496f18c3adc6cf422e82be09e5b9b83e487985d988f74.jpg)
资料来源：Wind，中信建投

中证人工智能指数板块个股方面，涨幅前五个股分别为：德赛西威（+11.60%）、四维图新（+9.51%）、北斗星通（+6.86%）、浪潮信息（+5.38%）、石头科技（+4.99%）；涨幅后五个股分别为：深信服（-21.32%）、国投智能（-14.88%）、安恒信息（-14.76%）、太极股份（-13.52%）、广联达（-12.91%）。

图表10： 人工智能（中证）个股周涨幅前十名（%）
![](images/4970f89c3fe5f97c0292c0a86d2f836775fc5c45aa1bb90bbd482aeb2ac89ec5.jpg)
资料来源：Wind，中信建投

图表11： 人工智能（中证）个股周涨幅后十名（%）
![](images/5000017649a7ec0137890fa8069c1c74ab3931f9f5f33539d079b8cc395ad851.jpg)
资料来源：Wind，中信建投

图表12： 重点公司股票涨跌详情（盈利预测均为 Wind一致预测）
<table><tr><td colspan="3">重点公司股票涨跌详情</td><td colspan="3">归母净利润</td><td colspan="3">PE</td><td colspan="3">区间行情</td></tr><tr><td>股票代 码</td><td>公司名称</td><td>单 行业 位</td><td>2021</td><td>2022</td><td>2023E</td><td>2021</td><td>2022</td><td>2023E</td><td>本周</td><td>月初至 今</td><td>年初至 今</td></tr><tr><td>NVDA.0</td><td>英伟达 (NVIDIA)</td><td>GPU</td><td>亿 美 元</td><td>43.3</td><td>97.5 0.0</td><td>521.4</td><td>231.6</td><td>#DIV/0 !</td><td>9.8%</td><td>14.2%</td><td>82.5%</td></tr><tr><td>AMD.0</td><td>超威半导体 (AMD)</td><td>GPU</td><td>亿 美</td><td>31.6 13.2</td><td>8.3</td><td>92.3</td><td>221.0</td><td>352.2</td><td>一 10.9</td><td>-6.3%</td><td>22.4%</td></tr><tr><td>688041</td><td>海光信息</td><td>GPU</td><td>亿 元</td><td>3.3</td><td>8.0 16.8</td><td>549.0</td><td>223.5</td><td>107.1</td><td>11.7</td><td>-9.2%</td><td>8.8%</td></tr><tr><td>688107</td><td>安路科技</td><td>FPGA</td><td>亿</td><td>(0.3)</td><td>0.6 (0.2)</td><td>(324.2</td><td>167.2</td><td>(655.7</td><td>% – 22.8</td><td>-21.8%</td><td>–32.2%</td></tr><tr><td>688256</td><td>寒武纪-U</td><td>ASIC</td><td>亿 元</td><td>(8.2) (12.6)</td><td>(5.6)</td><td>(87.6)</td><td>(57.5)</td><td>(129.8</td><td>% 2.0%</td><td>2.8%</td><td>28.5%</td></tr><tr><td>QCOM.0</td><td>高通</td><td>SoC</td><td>亿 美</td><td>90.4 129.4</td><td>0.0</td><td>20.9</td><td>14.6</td><td>#DIV/0</td><td>3.8%</td><td>7.3%</td><td>17.7%</td></tr><tr><td>300458</td><td>全志科技</td><td>SoC</td><td>元 亿</td><td>4.9</td><td>2.1 1.7</td><td>24.8</td><td>58.1</td><td>71.3</td><td>2.5%</td><td>0.6%</td><td>-14.5%</td></tr><tr><td>603893</td><td>瑞芯微</td><td>SoC</td><td>亿 元</td><td>6.0</td><td>3.0 1.6</td><td>35.0</td><td>70.7</td><td>130.2</td><td>一 8.5%</td><td>-6.5%</td><td>-20.6%</td></tr><tr><td>688099</td><td>晶晨股份</td><td>SoC</td><td>亿 元</td><td>8.1</td><td>7.3 8.2</td><td>24.5</td><td>27.4</td><td>24.2</td><td>一 14.4</td><td>-15.0%</td><td>-24.0%</td></tr><tr><td>002036</td><td>联创电子</td><td>汽车摄</td><td>亿 元</td><td>1.1</td><td>0.9 (1.4)</td><td>74.9</td><td>90.7</td><td>(58.5)</td><td>1.7%</td><td>3.8%</td><td>-22.8%</td></tr><tr><td>2382.H</td><td>舜宇光学科</td><td>汽车摄</td><td>亿</td><td>49.9</td><td></td><td></td><td></td><td>#DIV/0</td><td></td><td>-21.4%</td><td>-43.6%</td></tr><tr><td>K</td><td>技</td><td>像头</td><td>元</td><td></td><td>24.1</td><td></td><td>18.2</td><td></td><td>21.5</td><td></td><td></td></tr><tr><td>603501</td><td>韦尔股份</td><td>CIS</td><td>亿 元</td><td>44.8</td><td>9.9</td><td>9.7 26.7</td><td>120.8</td><td>123.0</td><td>4.6%</td><td>2.5%</td><td>-7.8%</td></tr><tr><td>300691</td><td>联合光电</td><td>毫米波 雷达</td><td>亿 元</td><td>0.7</td><td>0.6</td><td>1.1</td><td>60.4 80.3</td><td>41.6</td><td></td><td>-3.0%</td><td>–28.1%</td></tr><tr><td>603197</td><td>保隆科技</td><td>毫米波</td><td>亿</td><td>2.7</td><td>2.1</td><td>4.2</td><td>36.0 45.1</td><td>23.1</td><td>6.1%</td><td>-6.0%</td><td>-19.2%</td></tr></table>

<table><tr><td>688048</td><td>长光华芯</td><td>激光雷 达</td><td></td><td></td><td>1.2</td><td>1.2</td><td>63.8 61.7</td><td>63.5</td><td>8.8%</td><td></td><td>-4.7%</td><td>–33.4%</td></tr><tr><td>300620</td><td>光库科技</td><td>激光雷</td><td>亿</td><td>1.3</td><td>1.2</td><td>0.7</td><td>94.2</td><td>104.6</td><td>168.6</td><td>6.4%</td><td>14.0%</td><td>8.9%</td></tr><tr><td>603297</td><td>永新光学</td><td>达 激光雷</td><td>元 亿</td><td></td><td>2.8</td><td>2.7</td><td>34.1</td><td>32.0</td><td>33.1</td><td>4.0%</td><td>3.8%</td><td>-19.3%</td></tr><tr><td></td><td></td><td>达 激光雷</td><td>元 亿</td><td>2.6</td><td></td><td></td><td>47.7</td><td>36.6</td><td>27.0</td><td>31.0</td><td>34.7%</td><td>12.1%</td></tr><tr><td>002273</td><td>水晶光电</td><td>达 激光雷</td><td>元 亿</td><td>4.4 1.9</td><td>5.8</td><td>7.8</td><td></td><td></td><td></td><td>%</td><td></td><td></td></tr><tr><td>002222</td><td>福晶科技</td><td>达 激光雷</td><td>元 亿</td><td></td><td>2.3</td><td>2.9</td><td>62.3</td><td>52.6</td><td>41.8</td><td>0.6%</td><td>2.7%</td><td>–5.6%</td></tr><tr><td>688127</td><td>蓝特光学</td><td>达 数据服</td><td>元 亿</td><td>1.4</td><td>1.0</td><td>2.9</td><td>60.5</td><td>88.1 #DIV/0</td><td>29.1</td><td>1.2%</td><td>5.0%</td><td>–9.5%</td></tr><tr><td>688787</td><td>海天瑞声</td><td>务 语音处</td><td>元 亿</td><td>0.3</td><td>0.3</td><td>0.0</td><td>138.6</td><td>148.8</td><td>!</td><td>9.1%</td><td>25.3%</td><td>0.7%</td></tr><tr><td>002230</td><td>科大讯飞</td><td>理</td><td></td><td></td><td>5.6</td><td>8.1</td><td>72.5</td><td>201.0</td><td>139.2</td><td>7.3%</td><td>-1.4%</td><td>5.0%</td></tr><tr><td>002415</td><td>海康威视</td><td>计算机 视觉</td><td></td><td></td><td>128.4</td><td>170.2</td><td>17.9</td><td>23.4</td><td>17.6</td><td>– 9.9%</td><td>-8.0%</td><td>-7.4%</td></tr><tr><td>688207</td><td>格灵深瞳</td><td>计算机 视觉</td><td></td><td></td><td>0.3</td><td>0.3</td><td>(55.1)</td><td>115.5 144.9</td><td></td><td>– 8.3%</td><td>-2.0%</td><td>–30.6%</td></tr><tr><td>688003</td><td>天准科技</td><td>计算机 视觉</td><td>亿 元</td><td></td><td>1.5</td><td>2.8</td><td>53.4</td><td>47.1</td><td>25.7</td><td>5.7%</td><td>6.3%</td><td>-0.9%</td></tr><tr><td>002920</td><td>德赛西威</td><td>Tier1</td><td>亿 元</td><td>8.3</td><td>11.8</td><td>21.2</td><td>83.0</td><td>58.4</td><td>32.7</td><td>21.0 %</td><td>21.4%</td><td>-3.9%</td></tr><tr><td>002906</td><td>华阳集团</td><td>Tier1</td><td>亿</td><td>3.0</td><td>3.8</td><td>6.3</td><td>44.9</td><td>35.3</td><td>21.2</td><td>一</td><td>1.5%</td><td>–27.4%</td></tr><tr><td>688326</td><td>经纬恒润-W</td><td>Tier1</td><td>元 亿</td><td>1.5</td><td>2.3</td><td>2.5</td><td>63.7</td><td>39.7</td><td>37.9</td><td>0.2% 一</td><td>-0.6%</td><td>–33.1%</td></tr><tr><td>600699</td><td>均胜电子</td><td>Tier1</td><td>元 亿</td><td>(37.5)</td><td>3.9</td><td>14.3</td><td>(6.5)</td><td>61.8</td><td>17.0</td><td>1.7% 3.2%</td><td>3.7%</td><td>-3.8%</td></tr><tr><td>0285.H K</td><td>比亚迪电子</td><td>Tier1</td><td>元 亿</td><td>23.1</td><td>18.6</td><td>0.0</td><td>28.1</td><td>35.0</td><td>#DIV/0</td><td>–</td><td>-2.5%</td><td>-21.2%</td></tr><tr><td></td><td></td><td>汽车软</td><td>元 亿</td><td></td><td></td><td></td><td></td><td></td><td>!</td><td>6.6% –</td><td></td><td></td></tr><tr><td>300496</td><td>中科创达</td><td>件</td><td>元</td><td>6.5</td><td>7.7</td><td>8.1</td><td>36.4</td><td>30.7</td><td>29.3</td><td>18.3 %</td><td>-15.5%</td><td>–36.0%</td></tr><tr><td>301221</td><td></td><td>汽车软</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td>11.2</td><td></td><td></td></tr><tr><td></td><td>光庭信息</td><td>件</td><td>亿 元</td><td>0.7</td><td>0.3</td><td>0.7</td><td>59.7</td><td>137.4</td><td>62.9</td><td>%</td><td>15.1%</td><td>-19.0%</td></tr><tr><td></td><td></td><td>汽车软</td><td>亿</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>688088</td><td>虹软科技</td><td></td><td></td><td>1.4</td><td>0.6</td><td>2.0</td><td>94.0</td><td>228.9</td><td>66.0</td><td>0.1%</td><td>6.1%</td><td>-20.6%</td></tr><tr><td></td><td></td><td>件</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td></td><td></td><td>元</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td></td><td>汽车软</td><td>亿</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td>14.4</td><td></td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td></td></tr><tr><td rowspan="2">300353</td><td rowspan="2">东土科技</td><td rowspan="2">汽车软 件</td><td rowspan="2">亿</td><td colspan="7"></td><td rowspan="2">-2.1%</td><td rowspan="2">3.6%</td></tr><tr><td>元</td><td>0.1</td><td>0.2</td><td>0.5</td><td>1188.8 305.7</td><td>116.9</td><td>3.3%</td></tr><tr><td rowspan="2">002373</td><td>千方科技</td><td>智慧交</td><td>亿</td><td>7.2</td><td></td><td></td><td></td><td></td><td>27.7</td><td>一</td><td></td><td></td></tr><tr><td></td><td>通</td><td>元</td><td></td><td>(4.8)</td><td>6.0</td><td>23.0</td><td>(34.5)</td><td></td><td>1.1%</td><td>1.2%</td><td>-6.1%</td></tr><tr><td rowspan="2">300552</td><td>万集科技</td><td>智慧交</td><td>亿</td><td>0.4</td><td>(0.3)</td><td>(0.7)</td><td>150.3</td><td>(220.8</td><td>(94.6)</td><td>50.1</td><td>55.2%</td><td>1.5%</td></tr><tr><td></td><td>通</td><td>元</td><td></td><td></td><td></td><td></td><td>)</td><td></td><td>%</td><td></td><td></td></tr><tr><td rowspan="2">688777</td><td>中控技术</td><td>智慧工</td><td>亿</td><td>5.8</td><td>8.0</td><td>13.5</td><td>63.2</td><td>46.1</td><td>27.2</td><td></td><td>1.2%</td><td>2.6%</td></tr><tr><td></td><td>业</td><td>元</td><td></td><td></td><td></td><td></td><td></td><td></td><td>3.8%</td><td></td><td></td></tr><tr><td rowspan="2">000682</td><td>东方电子</td><td>智慧工</td><td>亿</td><td>3.5</td><td>4.4</td><td>5.5</td><td>35.2</td><td>27.9</td><td>22.2</td><td>6.2%</td><td>8.3%</td><td>13.3%</td></tr><tr><td></td><td>业</td><td>元</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td rowspan="3">301269</td><td>华大九天</td><td>智慧工</td><td>亿</td><td>1.4</td><td></td><td></td><td></td><td>245.0</td><td>191.4</td><td>一</td><td>-8.0%</td><td>-20.9%</td></tr><tr><td></td><td>业</td><td>元</td><td></td><td>1.9</td><td>2.4</td><td>326.2</td><td></td><td></td><td>8.6%</td><td></td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td>一</td><td></td><td></td></tr><tr><td rowspan="3">301095</td><td>广立微</td><td>智慧工</td><td>亿</td><td>0.6</td><td>1.2</td><td>1.8</td><td>172.2</td><td>89.7</td><td>61.1</td><td>15.8</td><td>-15.5%</td><td>–26.5%</td></tr><tr><td></td><td>业</td><td>元</td><td></td><td></td><td></td><td></td><td></td><td></td><td>%</td><td></td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td>–</td><td></td><td></td></tr><tr><td rowspan="2">688206</td><td>概伦电子</td><td>智慧工</td><td>亿</td><td>0.3</td><td>0.4</td><td>0.4</td><td>236.6</td><td>150.8</td><td>172.5</td><td>12.6</td><td>-11.6%</td><td>-28.4%</td></tr><tr><td></td><td>业</td><td>元</td><td></td><td></td><td></td><td></td><td></td><td></td><td>%</td><td></td><td></td></tr></table>

资料来源：Wind，中信建投

## 四、产业要闻

## 大模型

【微软亚研院新作：让大模型一口气调用数百万个 API】3月 28 日，微软为解决在特定领域任务上，由于专业数据的缺乏和可能的计算错误，普通AI大模型的表现并不理想的问题，发布TaskMatrix.AI。TaskMatrix.AI 是由微软（Microsoft）设计发布的新型 AI 生态系统。其核心技术近期在《科学》合作期刊 Intelligent Computing 上发表的论文 TaskMatrix.AI: Completing Tasks by ConnectingFoundation Models with Millions of APIs 中正式亮相，作者为微软亚洲研究院的段楠博士团队。（IT 之家）

【小艺大模型版本下放，华为 Mate 40 系列手机迎来首次众测更新】3 月 27 日，华为 Mate 40 系列手机现已开启小艺大模型版本众测，版本号为 12.1.2.400，大小为 65.1MB，日期为 2024/3/22-2024/4/30。华为 Mate 60/ 50 系列、P60/P50 系列手机此前已开启全新小艺大模型众测体验。据官方介绍，搭载了大模型能力的智慧助手小艺能够完成更复杂的任务。众测期间可体验文案辅助创作能力、资讯快速摘要和对话式问答能力等，可以对小艺说“你可以干什么”，或者根据自身使用习惯 挖掘更多玩法。（IT之家）

【阿里云 x 联发科，天玑 9300 等手机芯片适配端侧通义千问大模型】3 月 28 日，联发科宣布已成功在天玑 9300 等旗舰芯片上部署通义千问大模型，首次实现大模型在手机芯片端深度适配。通义千问在离线情况下运行多轮 AI 对话。阿里云方面表示，将和联发科深度合作，向全球手机厂商提供端侧大模型解决方案。通义千问目前已开源 18 亿、70 亿、140 亿、720 亿参数等大语言模型，以及视觉理解、音频理解多模态大模型。阿里云在去年 10 月还发布了通义千问 2.0，模型参数达到千亿级别。（IT之家）

## 芯片

【打破国际垄断，提高体外诊断技术水平：量子点液态芯片实现中国造】3 月 26 日，上海交通大学宣布，该校材料科学与工程学院、张江高等研究院研究员李万万领衔的团队与企业开展合作，历时 18年，最终实现完整全链条技术突破，研发出量子点液态生物芯片多指标体外检测系统，创建了具有自主知识产权的量子点液态生物芯片技术平台。官方介绍称，液态生物芯片对核酸和蛋白类标志物均适用，其检测通量大，检测灵敏高，可同时分析单管样本中的数十种目标物，检测效率显著提升，对临床实验室检测具有革命性推动作用。该成果不仅有利于提高中国的体外诊断技术水平，还打破了国际垄断。（IT 之家）

【英伟达 AI 芯片 H200 开始供货，性能相比 H100 提升 60%-90%】3 月 28 日消息，据日本经济新闻今日报道，英伟达的尖端图像处理半导体（GPU）H200 现已开始供货。H200 为面向 AI 领域的半导体，性能超过当前主打的 H100。根据英伟达方面公布的性能评测结果，以 Meta 公司旗下大语言模型 Llama 2 处理速度为例，H200 相比于 H100，生成式 AI 导出答案的处理速度最高提高了 45％。英伟达当地时间 3 月 18 日在开发者大会上宣布，年内将推出新一代 AI 半导体“B200”，B200 和 CPU（中央运算处理装置）组合的新产品用于最新的 LLM 上。“最强 AI 加速卡”GB200 包含了两个 B200Blackwell GPU 和一个基于 Arm 的 Grace CPU ，推理大语言模型性能比 H100 提升 30 倍，成本和能耗降至 25 分之一。（IT 之家）

【分析称苹果 M3 Ultra 将成为独立芯片，性能有望大幅提升】3 月 28 日消息，据科技频道 MaxTech 的 Vadim Yuryev 称，苹果的 M3 Ultra 芯片可能将采用全新设计，成为独立芯片，而非像此前M1 Ultra 和 M2 Ultra 一样由两颗 M3 Max 芯片组合而成。目前有关 M3 Ultra 的确切信息尚少，但有消息称其将采用台积电的 N3E 制程工艺，和即将于下半年发布的 iPhone 16 系列所搭载的 A18 芯片相同。这也意味着这将是苹果首款采用 N3E 制程的芯片，传闻称 M3 Ultra 将于 2024 年年中随新款 MacStudio 一起发布。（IT 之家）

## 智能驾驶

【小米汽车 SU7 /Pro / Max 正式发布并上市】3 月 28 日消息，小米首款汽车小米汽车 SU7 正式发布并上市，小米汽车 SU7 提供三款车型，标准版搭载单电机、5.28s 零百加速、CLTC 续航 700 公里、19 寸米其林轮胎、73.6kWh 磷酸铁锂刀片电池、15 分钟补能 350km、小米智驾 Pro 纯视觉智驾终生免费、小米澎湃智能座舱，售价 21.59 万元。新车定位于“C 级高性能生态科技轿车”，售价 21.59 万元-29.99 万元。（IT 之家）

## 传感器

【苹果 Vision Pro 头显新专利获批：Light Seal 内嵌触控传感器，带来更丰富交互方式】3 月 26日消息，根据美国商标和专利局（USPTO）近日公示的清单，苹果公司获得了一项关于 Vision Pro 头显的技术专利，暗示苹果计划未来在 Light Seal 中嵌入触控传感器，从而为佩戴者提供更丰富的交互体验。IT 之家报导，苹果公司此前的专利中，就考虑在 Light Seal 中嵌入各种传感器，测量佩戴者体温、汗液、心率、心脏电信号（如心电图、心电图等）、额叶活动等指标，从而进一步分析佩戴者的反应或者参与度。（IT 之家）

## 五、重要公告

本期重点公告包括销售合同、股权激励、对外投资、股权质押等。天准科技发布销售合同相关公告，中控技术发布股权激励相关公告，经纬润恒发布对外投资相关公告，广立微发布股权质押相关公告。

人工智能行业一周重要公告
<table><tr><td></td><td>公司简称发布日期公告内容</td><td></td></tr><tr><td>四维图新</td><td>2024/2/5</td><td>近日，北京四维图新科技股份有限公司（以下简称“公司”）子公司北京图迅丰达信息技术 有限公司（以下简称“图迅丰达”）收到北京市科学技术委员会、北京市财政局、国家税务 总局北京市税务局联合颁发的《高新技术企业证书》（证书编号：GR202311004043），发证 日期为2023年11月30日，有效期三年。</td></tr><tr><td>联创电子</td><td>2024/2/7</td><td>联创电子科技股份有限公司关于控股股东股份补充质押的公告：联创电子科技股份有限公司 （以下简称“公司”）近日收到控股股东江西鑫盛投资有限公司（以下简称“江西鑫盛”） 的告知函，获悉江西鑫盛将所持有公司的部分股份进行股份补充质押。</td></tr><tr><td>德赛西威</td><td>2024/2/7</td><td>惠州市德赛西威汽车电子股份有限公司(以下简称“公司”)于2023年10月24日召开了第三 届董事会第二十次会议，审议通过了《关于公司全资子公司拟与专业投资机构共同投资设立 产业基金暨关联交易的议案》，同意公司的全资子公司深圳市德赛西威产业投资有限公司与 广东粤财基金管理有限公司、广东粤财创业投资有限公司、广州白云金融控股集团有限公 司、惠州产业投资发展母基金有限公司及惠州市创新投资有限公司共同投资设立广东粤财西 威汽车创业投资合伙企业（有限合伙）。基金计划认缴规模为人民币3亿元，已确定投资意</td></tr><tr><td>均胜电子</td><td>2024/2/7</td><td>宁波均胜电子股份有限公司关于控股股东股份解除质押的公告：公司于2024年2月7日收到 控股股东均胜集团通知，均胜集团将原质押给浙商银行股份有限公司宁波分行（以下简称 “浙商银行宁波分行”）的公司合计20,000,000股无限售流通股解除质押。</td></tr><tr><td>经纬恒润</td><td>2024/2/7 对象资格，其所持有的已获授但尚未解除限售的限制性股票应予以回购注销。公司同意按照</td><td>北京经纬恒润科技股份有限公司（以下简称“公司”）于2024年2月6日分别召开第二届董 事会第六次会议、第二届监事会第五次会议，审议通过了《关于回购注销2023年限制性股票 激励计划部分激励对象所持已获授但尚未解除限售的限制性股票的议案》。根据《上市公司 股权激励管理办法》（以下简称“《管理办法》”）以及《北京经纬恒润科技股份有限公司 2023年限制性股票激励计划（草案）》（以下简称“《激励计划（草案）》”或“本激励计 划”）的相关规定，鉴于4名激励对象因离职而不再具备《激励计划（草案）》规定的激励</td></tr></table>

行业动态报告

中科创达

2024/2/7

中科创达软件股份有限公司（以下称“公司”）近日接到控股股东赵鸿飞先生告知，获悉赵鸿飞先生已将其所持有的公司部分股份办理了补充质押。

千方科技

2024/2/8

北京千方科技股份有限公司（以下简称“公司”、“本公司”）近日接到公司控股股东、实际控制人夏曙东先生及其一致行动人、公司持股 5%以上股东北京千方集团有限公司（以下简称“千方集团”）以及夏曙锋先生的通知，获悉其所持有本公司的部分股份被质押。

资料来源：Wind，中信建投

## 六、风险提示

北美经济衰退预期逐步增强，宏观环境存在较大的不确定性，国际环境变化影响供应链及海外拓展；芯片紧缺可能影响相关公司的正常生产和交付，公司出货不及预期；下游需求不及预期影响公司正常生产和交付，导致收入及增速不及预期；信息化和数字化方面的需求和资本开支不及预期；市场竞争加剧，导致毛利率快速下滑；主要原材料价格上涨，导致毛利率不及预期；汇率波动影响外向型企业的汇兑收益与毛利率；人工智能技术进步不及预期；汽车与工业智能化进展不及预期。

## 分析师介绍

## 于芳博

中信建投人工智能组首席分析师，北京大学空间物理学学士、硕士，2019 年 7月加入中信建投，主要覆盖人工智能等方向，下游重点包括智能汽车、CPU/GPU/FPGA/ASIC、EDA 和工业软件等方向。

## 评级说明

<table><tr><td rowspan=1 colspan=1>投资评级标准</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>评级</td><td rowspan=1 colspan=1>说明</td></tr><tr><td rowspan=8 colspan=1>报告中投资建议涉及的评级标准为报告发布日后6个月内的相对市场表现，也即报告发布日后的6个月内公司股价（或行业指数）相对同期相关证券市场代表性指数的涨跌幅作为基准。A股市场以沪深300指数作为基准；新三板市场以三板成指为基准；香港市场以恒生指数作为基准；美国市场以标普500指数为基准。</td><td rowspan=5 colspan=1>股票评级</td><td rowspan=1 colspan=1>买入</td><td rowspan=1 colspan=1>相对涨幅15%以上</td></tr><tr><td rowspan=1 colspan=1>增持</td><td rowspan=1 colspan=1>相对涨幅 5%—15%</td></tr><tr><td rowspan=1 colspan=1>中性</td><td rowspan=1 colspan=1>相对涨幅-5%—5%之间</td></tr><tr><td rowspan=1 colspan=1>减持</td><td rowspan=1 colspan=1>相对跌幅 5%—15%</td></tr><tr><td rowspan=1 colspan=1>卖出</td><td rowspan=1 colspan=1>相对跌幅15%以上</td></tr><tr><td rowspan=3 colspan=1>行业评级</td><td rowspan=1 colspan=1>强于大市</td><td rowspan=1 colspan=1>相对涨幅10%以上</td></tr><tr><td rowspan=1 colspan=1>中性</td><td rowspan=1 colspan=1>相对涨幅-10-10%之间</td></tr><tr><td rowspan=1 colspan=1>弱于大市</td><td rowspan=1 colspan=1>相对跌幅10%以上</td></tr></table>

## 分析师声明

本报告署名分析师在此声明：（i）以勤勉的职业态度、专业审慎的研究方法，使用合法合规的信息，独立、客观地出具本报告,结论不受任何第三方的授意或影响。（ii）本人不曾因，不因，也将不会因本报告中的具体推荐意见或观点而直接或间接收到任何形式的补偿。

## 法律主体说明

本报告由中信建投证券股份有限公司及/或其附属机构（以下合称“中信建投”）制作，由中信建投证券股份有限公司在中华人民共和国（仅为本报告目的，不包括香港、澳门、台湾）提供。中信建投证券股份有限公司具有中国证监会许可的投资咨询业务资格，本报告署名分析师所持中国证券业协会授予的证券投资咨询执业资格证书编号已披露在报告首页。

在遵守适用的法律法规情况下，本报告亦可能由中信建投（国际）证券有限公司在香港提供。本报告作者所持香港证监会牌照的中央编号已披露在报告首页。

## 一般性声明

本报告由中信建投制作。发送本报告不构成任何合同或承诺的基础，不因接收者收到本报告而视其为中信建投客户。

本报告的信息均来源于中信建投认为可靠的公开资料，但中信建投对这些信息的准确性及完整性不作任何保证。本报告所载观点、评估和预测仅反映本报告出具日该分析师的判断，该等观点、评估和预测可能在不发出通知的情况下有所变更，亦有可能因使用不同假设和标准或者采用不同分析方法而与中信建投其他部门、人员口头或书面表达的意见不同或相反。本报告所引证券或其他金融工具的过往业绩不代表其未来表现。报告中所含任何具有预测性质的内容皆基于相应的假设条件，而任何假设条件都可能随时发生变化并影响实际投资收益。中信建投不承诺、不保证本报告所含具有预测性质的内容必然得以实现。

本报告内容的全部或部分均不构成投资建议。本报告所包含的观点、建议并未考虑报告接收人在财务状况、投资目的、风险偏好等方面的具体情况，报告接收者应当独立评估本报告所含信息，基于自身投资目标、需求、市场机会、风险及其他因素自主做出决策并自行承担投资风险。中信建投建议所有投资者应就任何潜在投资向其税务、会计或法律顾问咨询。不论报告接收者是否根据本报告做出投资决策，中信建投都不对该等投资决策提供任何形式的担保，亦不以任何形式分享投资收益或者分担投资损失。中信建投不对使用本报告所产生的任何直接或间接损失承担责任。

在法律法规及监管规定允许的范围内，中信建投可能持有并交易本报告中所提公司的股份或其他财产权益，也可能在过去 12 个月、目前或者将来为本报告中所提公司提供或者争取为其提供投资银行、做市交易、财务顾问或其他金融服务。本报告内容真实、准确、完整地反映了署名分析师的观点，分析师的薪酬无论过去、现在或未来都不会直接或间接与其所撰写报告中的具体观点相联系，分析师亦不会因撰写本报告而获取不当利益。

本报告为中信建投所有。未经中信建投事先书面许可，任何机构和/或个人不得以任何形式转发、翻版、复制、发布或引用本报告全部或部分内容，亦不得从未经中信建投书面授权的任何机构、个人或其运营的媒体平台接收、翻版、复制或引用本报告全部或部分内容。版权所有，违者必究。

## 中信建投证券研究发展部

## 中信建投（国际）

北京

东城区朝内大街2 号凯恒中心

上海

深圳

香港

B 座 12 层

上海浦东新区浦东南路 528 号南塔 2103 室

福田区福中三路与鹏程一路交

中环交易广场2期18 楼

电话：（8610）8513-0588

汇处广电金融中心35 楼

电话：（8621）6882-1600

电话：（86755）8252-1369

电话：（852）3465-5600

联系人：李祉瑶

联系人：翁起帆

邮箱：lizhiyao@csc.com.cn

邮箱：wengqifan@csc.com.cn

联系人：曹莹

邮箱：caoying@csc.com.cn

联系人：刘泓麟

邮箱：charleneliu@csci.hk