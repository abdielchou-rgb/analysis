证券研究报告·海外行业动态

# Anthropic 发布 Claude 3 模型，文本窗口扩

# 展对 RAG影响有限

## 核心观点

Claude 3 在代码、科学计算、通用推理等领域与 GPT-4 Turbo/GPT-4 基本接近。就文本领域的性能而言，Claude 3 Opus 接近 GPT-4Turbo 且优于 Gemini 1.0 Ultra。Claude 3 在长文本处理方面较Claude2/1 显著提升，但模型的长文本窗口及 Haystack 测试依赖对 Prompt 的精细调整和简单的取出内容，因此，虽然当前 LLM模型在处理长文本方面取得一定进展，但其 90%+的表现不意味着模型在长文本中取出和结合上下文做复杂推理的能力，并且内存瓶颈是其核心限制，并不构成对 RAG 的完全替代。

## 行业动态信息

Claude 3 基于文本的性能与 GPT-4 接近，长文本方面显著提升根据 Claude 3 技术报告：1）推理方面，Claude 3 在 GPQA Diamond集的测试表现优于 GPT-4，但可能存在方差过大结果不具备代表性的隐忧，需进一步扩大测试样本数量确定实际表现。2）Claude3 Opus 和 GPT-4 Turbo/GPT-4 在代码、科学计算、通用推理等领域表现基本接近。目前基于文本领域的性能，LLM 的排序为GPT-4 Turbo≈Claude 3 Opus>Gemini 1.0 Ultra。3）长文本处理方面，Claude 进行了 QuALITY 和 Haystack 两种测试，较 Claude2/1 模型稳步提升。4）多模态能力上，Claude 3 与 Gemini 1.0Ultra 相比仍有一定差距，但略好于 GPT-4V。

## 长文本能力测试与实际用例存在差异

Gemini/Claude 3/GPT-4 Turbo \~99%的召回率表现建立在两方面：1）对 Prompt 的精细调整 2）当前的测试主要是简单的取出内容，LLM 不需要做太多额外推理，与现实提问方式有较大差距。

# 软件与服务

## 长文本窗口替代 RAG的核心瓶颈在于成本，本质在于内存瓶颈

现有填充 1M token 的定价在\$0.25\~\$15，随着 GPU 性能提升，单位算力的成本可能下降，但由于 GPU 内存的限制，存储大量文本将导致分块和多组计算（将内容切分后分别放在不同 GPU上计算后传输），这导致延迟。符尧提出利用 KV 缓存存储内容，但其占据大量内存且一旦切换文档需要重新缓存。KV 缓存策略通过精细优化提升了给定内存的处理能力，并且缩短延迟，但这些建立在给定内存的前提下，实际业务场景下往往推理需求不确定（输入的文本序列长度不确定），这给内存管理造成较大挑战。

维持

强于大市

崔世峰

cuishifeng@csc.com.cn

SAC 编号:S1440521100004

SFC 编号:BUI663

许悦

xuyue@csc.com.cn

SAC 编号:S1440523030001

发布日期： 2024 年 03 月 09 日

## 市场表现

![](images/67fe3688c7d56c55957a179f071e3531703aa9be8da0a6cf7c9600f2d4107ea2.jpg)

## 相关研究报告

07.06.11 股权变更获准

07.03.29 增资白敬宇制药持有 30%股份

07.03.05 63%控股鼓楼宿迁人民医院

投资建议：整体而言，GenAI 继续沿着 Scaling Laws 拓展性能，在下游任务上解决复杂问题的能力也逐步提升，我们看好 GenAI 在产业内提效的空间。例如，在金融领域，AI 可以用于风险管理、交易执行和客户服务等方面，提高效率、降低成本并改善用户体验。在客服领域， 可以完成知识库的自助构建，对话式 处理简单通用性问题，提升客服代理的工作效率。GenAI 提效本质是对任务处理的自动化，解放机械重复的人力开支，转而用算力替代，算力成本中长期有望指数级下降，而人力成本则持续提升，因此 GenAI 的逐步渗透将带来新一波产业创新，中长期商业化提升空间较大。

## 目录

Claude 3 技术报告解读 . ................................ ...... 1
RAG：长文本窗口不构成对 RAG 的 100%替代 ........................................................................................................... 9
投资评价和建议.
风险分析.. ..... 14

## Claude 3 技术报告解读

Anthropic 主要针对 Claude3 模型进行 1）推理；2）多语种；3）长文本；4）事实性；5）多模态能力评估。我们根据 Claude3 的技术报告1进行详细讨论。首先是 GPQADiamond 集的测试，GPQA 是一个研究生级别的问答基准，难题侧重于研究生水平的专业知识和推理，每个问题限时 30 分钟，并且可以通过互联网搜集信息，Claude 3 在 CoT（Temp=12）设置下方差很大，Claude 研究团队通过选取 10 次评估的平均值为结果，但这一做法的潜在问题是方差很大可能意味着结果不具备代表性，需要进一步扩大测试样本数量来确定实际表现。另外，研究生级别的人类在 Diamond 测试级的平均表现为 81.2%3，仍然好于 Claude 3/GPT-4 等模型。

表 1:Claude 3 家族模型与 GPT、Gemini 系列模型的性能对比
<table><tr><td colspan="2"></td><td>Claude 3 Opus</td><td>Claude 3 Sonnet</td><td>Claude 3 Haiku</td><td>GPT-4</td><td>Gemini 1.0 Ultra</td><td>Gemini 1.5 Pro</td></tr><tr><td rowspan="2">MMLU General reasoning</td><td>5-shot</td><td>86.8%</td><td>79.0%</td><td>75.2%</td><td>90.1% Medprompt+</td><td>83.7%</td><td>81.9%</td></tr><tr><td>5-shot CoT</td><td>88.2%</td><td>81.5%</td><td>76.7%</td><td></td><td></td><td></td></tr><tr><td>MATH Mathematical</td><td>0-shot Maj@32 4-</td><td>60.1%</td><td>43.1%</td><td>38.9%</td><td>68.4%</td><td>53.20%</td><td></td></tr><tr><td>problem solving</td><td>shot</td><td>73.7%</td><td>55.1%</td><td>50.3%</td><td></td><td></td><td></td></tr><tr><td rowspan="3">GSM8K Grade school math</td><td></td><td>95.0%</td><td>92.3%</td><td>88.9%</td><td>95.3%</td><td>94.4%</td><td>91.7%</td></tr><tr><td></td><td>0-shot</td><td>0-shot</td><td>0-shot</td><td>0-shot CoT</td><td>0-shot CoT</td><td>11-shot</td></tr><tr><td></td><td>CoT</td><td>CoT</td><td>CoT</td><td></td><td></td><td></td></tr><tr><td>HumanEval Python coding tasks GPQA(Diamond)</td><td>0-shot</td><td>84.9%</td><td>73.0%</td><td>75.9%</td><td>87.8%</td><td>74.4%</td><td>71.9%</td></tr><tr><td>Graduate level Q&amp;A MGSM</td><td>0-shot CoT</td><td>50.4%</td><td>40.4%</td><td>33.3%</td><td>35.7%</td><td></td><td></td></tr><tr><td>Multilingual math</td><td></td><td>90.7% 0-shot</td><td>83.5% 0-shot</td><td>75.1% 0-shot</td><td>74.5%</td><td>79.0%</td><td>88.7% 8-shot</td></tr><tr><td>DROP</td><td></td><td></td><td></td><td></td><td>8-shot</td><td>8-shot 82.4</td><td>78.9</td></tr><tr><td>Reading comprehension arithmetic</td><td>F1 Score</td><td>83.1 3-shot</td><td>78.9 3-shot</td><td>78.4 3-shot</td><td>83.7 Zero-shot + CoT</td><td>Zero-shot +</td><td>Variable</td></tr><tr><td>BIG-Bench-Hard Mixed evaluations</td><td>3-shot CoT</td><td>86.8%</td><td>82.9%</td><td>73.7%</td><td>89.0%</td><td>CoT 83.6% Few-shot+</td><td>shots 84.0%</td></tr><tr><td>ARC-Challenge</td><td>25-shot</td><td>96.4%</td><td>93.2%</td><td></td><td>Few-shot+ CoT</td><td>CoT</td><td></td></tr><tr><td>Common-sense reasoning HellaSwag</td><td>10-shot</td><td>95.4%</td><td>89.0%</td><td>89.2% 85.9%</td><td>96.3% 95.3%</td><td>87.8%</td><td>92.5%</td></tr></table>

<table><tr><td colspan="2">Common-sense reasoning</td><td></td><td colspan="2"></td><td></td><td></td></tr><tr><td rowspan="2">PubMedQA Biomedical questions</td><td>5-shot</td><td>75.8%</td><td>78.3%</td><td>76.0%</td><td>74.4%</td><td></td></tr><tr><td>0-shot</td><td>74.9%</td><td>79.7%</td><td>78.5%</td><td>75.2%</td><td></td></tr><tr><td>WinoGrande Common-sense reasoning</td><td>5-shot</td><td>88.5%</td><td>75.1%</td><td>74.2%</td><td>87.5%</td><td></td></tr><tr><td>RACE-H</td><td>5-shot</td><td>92.9%</td><td>88.8%</td><td>87.0%</td><td></td><td></td></tr><tr><td>Reading comprehension APPS</td><td>O-shot</td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>Python coding tasks</td><td></td><td>70.2%</td><td>55.9%</td><td>54.8%</td><td></td><td></td></tr><tr><td>MBPP Code generation</td><td>Pass@1</td><td>86.4%</td><td>79.4%</td><td>80.4%</td><td></td><td></td></tr></table>

Claude<sup>4</sup> Promptbase<sup>5</sup>

GPQA  GPT-4  2023  11  NYU Cohere Anthropic GPQA: A Graduate-Level Google-ProofQ&A Benchmark》 。

其他测试集方面，Claude 3 Opus 和 GPT-4 Turbo/GPT-4 在代码、科学计算、通用推理等领域表现基本接近。需要指出的是，由于以上测试结果多为有限测试的平均值，因此两个模型极小的差异可能被重复测试所改写，但大体上我们只能认为 Claude 3 Opus 和 GPT-4 Turbo/GPT-4 在这些领域处于同一水平。目前基于文本领域的性能，LLM 的排序为 GPT-4 Turbo≈Claude 3 Opus>Gemini 1.0 Ultra。

长文本方面，Claude 进行了 QuALITY 和 Haystack 两种测试，较 Claude 2/1 模型稳步提升。QuALITY是一个多项选择问答数据集，旨在评估语言模型对长格式文档的理解能力，该数据集中的上下文段落平均长度约为 5,000 个 token。在此基准测试上人类的表现达到 93.5%，Claude 3 Opus 在 0-shot/1-shot 情况下分别达到89.2%/90.5%的准确率，接近人类的准确率。Haystack 方面，Claude 3 系列模型的召回率稳定在 90%以上。

图 1:Claude 系列模型在 QuALITY 测试集的表现
<table><tr><td></td><td></td><td>Claude 3 Opus</td><td>Claude 3 Sonnet</td><td>Claude 3 Haiku</td><td>Claude 2.1</td><td>Claude 2.0</td><td>Claude Instant 1.2</td></tr><tr><td>QuALITY</td><td>1-shot</td><td>90.5%</td><td>85.9%</td><td>80.2%</td><td>85.5%</td><td>84.3%</td><td>79.3%</td></tr><tr><td></td><td>0-shot</td><td>89.2%</td><td>84.9%</td><td>79.4%</td><td>82.8%</td><td>80.5%</td><td>78.7%</td></tr></table>

The Claude 3 Model Family: Opus, Sonnet, Haiku

图 2:Claude 3 Opus 海底捞针测试召回率
![](images/ff860e7632218a23c7da6b88b5a00892644cca52b31513d0baf792dd4c9ec91d.jpg)
The Claude 3 Model Family: Opus, Sonnet, Haiku 中信建投
海外行业动态报告

图 3:Claude 3 Sonnet 海底捞针测试召回率
![](images/4f05ed4d47a55d3a597377d7919f16465aef83fa4a1539885462716fd01b1de1.jpg)
The Claude 3 Model Family: Opus, Sonnet, Haiku 中信建投

图 4:Claude 3/2.1 模型在 Haystack 测试集的表现（召回率%）
<table><tr><td></td><td>Claude 3 Opus</td><td>Claude 3 Sonnet</td><td>Claude 3 Haiku</td><td>Claude 2.1</td></tr><tr><td>All context lengths</td><td>99.4%</td><td>95.4%</td><td>95.9%</td><td>94.5%</td></tr><tr><td>200k context length</td><td>98.3%</td><td>91.4%</td><td>91.9%</td><td>92.7%</td></tr></table>

The Claude 3 Model Family: Opus, Sonnet, Haiku

由于长文本测试的结果对实验设置高度敏感，我们这里展开讨论该\~99%召回率的真实意义。TheNeedle ina Haystack测试测试旨在评估 LLM RAG 系统在不同规模环境下的性能。它的工作原理是将特定的、有针对性的信息（Needle）嵌入到更大、更复杂的内容（Haystack）中。A Needle in the Haystack 测试目标是评估 LLM在大量数据中识别和利用特定信息的能力。进行测试时，实验团队将一个外部创建的内容（Needle）放置在一本书/文章（Haystack）的不同位置/不同深度，然后向 LLM 提问关于这一Needle 相关的问题（如 what isthebest thing to do in San Francisco?），并在文档不同深度（如 1K 到 2K token）重复提问，并记录 LLM 的表现，最终绘制如图 3-4 的召回率图像。

图 5:在 Paul Graham的文章中插入一段不相关的话

The first step is to decide what to work on. The work you choose needs to have three qualities: it has to be something you have a natural aptitude for, that you have a deep interest in, and that offers scope to do great work.The best thing to do in San Francisco is eat a sandwich and sit in Dolores Park on a sunny day.In practice you don't have to worry much about the third criterion Ambitious people are if anything already too conservative about it. So all you need to do is find something you have an aptitude for and great interest in.

数据来源：中信建投

海底捞针测试对 Prompt 高度敏感。通过观察 Claude 2.1 的测试结果，我们注意到靠近文档底部的内容召回率总体较高，而靠近文档顶部的内容召回率则较低，且这与 Anthropic 官方发布的 Claude 2.1 测试结果有较大差异。根据 Anthropic，若调整 Prompt（添加了一句提示“Here is the most relevant sentence in thecontext:”），Claude 2.1 的总体召回率从 27%提升至 98%。

图 6:左图为 Claude-2.1 200K 的海底捞针测试结果（2024 年 2 月），右图为 Claude 官方测试结果（2023 年 12 月）
![](images/2e323b5cf57e54d5885f7f0e94aae7459e8d49026b213bd09b4cecef05a4b33c.jpg)
Anthropic<sup>6</sup><sub>，</sub> 中信建投

图 7:Claude 2.1 对海底捞针测试的 Prompt 进行更新
![](images/bf49f84675fafe30e6681ee2a0040e4bd3ce5565942b6999e091e5751dbfedf5.jpg)
Anthropic<sup>7</sup><sub>，</sub> 中信建投

海底捞针测试对实验内容高度敏感。Arize 团队对海底捞针测试进行了调整，将针设置为一个随机数字，每次迭代都会变化，这降低了 LLM 通过缓存提升准确率的可能性，并采用不同的 Prompt 进行测试。结果表明，Arize 团队无法复刻 Claude 2.1 98%的召回率表现，但对 Prompt 修改后召回率有所提升（错误从 164 次下降至 74 次）。整体来看，在评估 Claude/GPT/Gemini 等模型的长文本性能上，需要仔细考虑其实验设置（取出文本/数字，是否随机，prompt 是否微调），再进行横向比较。另外，更具现实意义的问题是，长文本下人们通常的需求是取出相关内容，并进行推理，尤其是一些复杂问题的推理，过于简单的实验设置8可能高估模型的性能。

图 8:Claude 2.1 在有无 Prompt 精调下的召回率对比（从 87%提升至 94%）
![](images/aa092b28cac961b489ef9c6173a784da66bb2d17167099cc3fedd3b770ec1e08.jpg)
数据来源：Arize，中信建投

图 9: Greg Kamradt 使用的 Claude Prompt 模板
![](images/6e299ec6973c7b7b29e189a802a6773d20b363f16d8c86e18ee32494bb4f2f0e.jpg)
数据来源：Arize，中信建投

图 10:Anthropic 修订后的 Prompt 模板
![](images/dfeff669f11fbed349074bf0e0e2f4c91c0e51773d3ebd9969209be8337566bf.jpg)
数据来源：Arize，中信建投

多模态能力上，Claude 3 与 Gemini 1.0 Ultra 相比仍有一定差距，但略好于 GPT-4V。

图 11:Claude 3 与 GPT-4V、Gemini 系列模型多模态能力对比
<table><tr><td></td><td>Claude 3 Opus</td><td>Claude 3 Sonnet</td><td>Claude 3 Haiku</td><td>GPT-4V11</td><td>Gemini 1.0 Ultra⁴</td><td>Gemini 1.5 Pro4</td><td>Gemini 1.0 Pro4</td></tr><tr><td>MMMU [3] (val)</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>→ Art &amp; Design</td><td>67.5%</td><td>61.7%</td><td>60.8%</td><td>65.8%</td><td>70.0%</td><td></td><td></td></tr><tr><td>→ Business</td><td>67.2%</td><td>58.2%</td><td>52.5%</td><td>59.3%</td><td>56.7%</td><td></td><td></td></tr><tr><td>→ Science</td><td>48.9%</td><td>37.1%</td><td>37.1%</td><td>54.7%</td><td>48.0%</td><td></td><td></td></tr><tr><td>→ Health &amp; Medicine</td><td>61.1%</td><td>57.1%</td><td>52.3%</td><td>64.7%</td><td>67.3%</td><td></td><td></td></tr><tr><td>→ Humanities &amp; Social Science</td><td>70.0%</td><td>68.7%</td><td>66.0%</td><td>72.5%</td><td>78.3%</td><td></td><td></td></tr><tr><td>→ Technology &amp; Engineering</td><td>50.6%</td><td>45.0%</td><td>41.5%</td><td>36.7%</td><td>47.1%</td><td></td><td></td></tr><tr><td>Overall</td><td>59.4%</td><td>53.1%</td><td>50.2%</td><td>56.8% (from [3])</td><td>59.4%</td><td>58.5%</td><td>47.9%</td></tr><tr><td>DocVQA [53] (test, ANLS score) Document understanding</td><td>89.3%</td><td>89.5%</td><td>88.8%</td><td>88.4%</td><td>90.9%</td><td>86.5%</td><td>88.1%</td></tr><tr><td>MathVista [54] (testmini) Math</td><td>50.5%†</td><td>47.9%†</td><td>46.4%†</td><td>49.9% (from [54])</td><td>53%</td><td>52.1%</td><td>45.2%</td></tr><tr><td>AI2D [52] (test) Science diagrams</td><td>88.1%</td><td>88.7%</td><td>86.7%</td><td>78.2%</td><td>79.5%</td><td>80.3%</td><td>73.9%</td></tr><tr><td>ChartQA [55] (test, relaxed accuracy) Chart understanding</td><td>80.8%†</td><td>81.1%†</td><td>81.7%†</td><td>78.5%† 4-shot</td><td>80.8%</td><td>81.3%</td><td>74.1%</td></tr></table>

The Claude 3 Model Family: Opus, Sonnet, Haiku

图 12:Anthropic Claude 3 系列模型输入/输出 API 价格
![](images/46c5050b09a54377c696c60e6f76d54fd2ca611aff34d799d2f8cab4f7ca5b53.jpg)
Anthropic<sup>9</sup><sub>，</sub> 中信建投

图 13:GPT-4 输入/输出价格
<table><tr><td>Model</td><td>Input Output</td></tr><tr><td>gpt-4-0125-preview</td><td>$10.00 / 1M tokens $30.00 / 1M tokens</td></tr><tr><td>gpt-4-1106-preview</td><td>$10.00 / 1M tokens $30.00 / 1M tokens</td></tr><tr><td>gpt-4-1106-vision- preview</td><td>$10.00 / 1M tokens $30.00 / 1M tokens</td></tr></table>

OpenAI<sup>10</sup>

## RAG：长文本窗口不构成对 RAG的 100%替代<sup>11</sup>

上下文窗口相当于 LLMasaOS 的缓存。目前主要方式为 1）训练数据集的二次采样；2）调整注意力计算机制。当前符尧等12提出通过 upsampling（上采样）等方式在预训练环节强化 LLM 处理长文本的能力，可以将LLM 的窗口拓展至 128K。UCB 研究团队13则提出通过层次训练高效扩展上下文窗口。Yale 及 Google 团队14提出通过在不损失太多精度的情况下快速近似注意力矩阵的输出，从而实现长文本下的计算速度提升。

图 14:Gemini 1.5 Pro 宣布将 context window 拓展至 1M tokens
![](images/a50195a90109c778adea8b4c063f0cb11c071f040b5b0c9f93efc96a648b62cc.jpg)
Google<sup>15</sup><sub>，</sub> 中信建投

如前所述，我们提到 Gemini/Claude 3/GPT-4 Turbo\~99%的召回率表现建立在 1）对 Prompt 的精细调整，这意味如果抽取的内容从固定模式的文本/数字切换为随机的文本/数字，召回率表现可能受到影响；2）当前的TheNeedle ina Haystack测试主要是简单的取出内容，意味着 LLM 不需要做太多额外推理，但实际应用场景中人们可能询问“根据公司 规定，员工是否允许携带宠物上班”、“ 设计方案是否符合现行居民住宅的建筑标准”等问题，这类问题可以拆分为两部分，1）问题相关的背景材料，如现行民用住宅的建筑标准；2）匹配，设计方案分解后与建筑标准相匹配。当前长文本窗口及 Haystack测试的评估一定程度上存在“误导性”，该 90%+的表现不意味着模型在长文本中取出和结合上下文做复杂推理的能力。16

通过长文本窗口替代 的核心瓶颈在于成本，本质原因是内存瓶颈。前述问题都可以通过对注意力机制算法调优，训练数据集结构优化等措施改进，更本质的约束来自内存。根据 Anthropic/OpenAI，现有填充 1Mtoken 的定价在\$0.25\~\$15，随着 GPU 性能提升，单位算力的成本可能下降，但由于 GPU 内存的限制，存储大量文本将导致分块和多组计算（将内容切分后分别放在不同 GPU 上计算后传输），这导致延迟。

图 15:GPU 架构示意图
![](images/aaa8f0489e017ad56ca0e4dc55d3be643e1e3887df6a7080c47976f6856bbbf9.jpg)
Towards 100x Speedup: Full Stack Transformer Inference Optimization》 <sub>，</sub> 中信建投

图 16:SM 架构示意图
![](images/0c6f9001e65d5a941cb89916ee952ca56583e62ab0c3444574dbe5b17704b498.jpg)
Towards 100x Speedup: Full Stack Transformer
Inference Optimization》 <sub>，</sub> 中信建投

图 17: A100 内存结构
![](images/3f5b2a48b429d5794a544de7adb9279644f960b9ee1bb10b083d99adc6140fe8.jpg)

图 18:长文本推理面临内存瓶颈
![](images/3c015f0f90b00a9dcf04c623e0af3d3626d8c026aa9c6d5e0826e1abd70c7df8.jpg)
Efficient Memory Management for Large Language Towards 100x Speedup: Full Stack Transformer Inference Model Serving with PagedAttention》 <sub>，</sub> 中信建投 Optimization》 <sub>，</sub> 中信建投

符尧17提出利用 KV 缓存存储内容，但其占据大量内存且一旦切换文档需要重新缓存。根据 LLaMAIndex，缓存 1M token 的内容大约需要 100GB，这意味着至少需要 3 块 A100，或 2 块 H100。考虑 A100/H100 的价格及有限存储空间，大量占用内存的代价可能过高。Pierre Lienhart18（AWS GenAI 解决方案架构师）在 KV 缓存基础上通过消除冗余计算，从而将注意力机制的计算复杂度与 token长度的关系从指数级增长转化为线性增长，但如果用户离线后重新开启历史对话记录，则 LLM 需要重新计算过往内容，计算复杂度与 token 长度仍然为指数级增长，因此 KV 缓存策略本质平衡 GPU 带宽和内存以及计算量的问题。

图 19: Transformer输入序列长度为 3 的双头（自）注意力层的详细视图
![](images/20abcd03da592c17e32a80261c3106e4ef434975c8c11f2dd9c1bf8b05d2e64b.jpg)
LLM Inference Series: 3. KV caching unveiled

图 20:KV缓存策略后的注意力计算机制
![](images/f6416e538f1311341b7f7ce24f0829e3e9f9b707abdb30ab4e18653ccbe03025.jpg)
LLM Inference Series: 3. KV caching unveiled

方法论上，Transformer 模型在计算注意力分数时，需要查询向量(Q)与所有键向量(K)做点积，获得未缩放的注意力分数。但是对于带有掩码(mask)的位置，不论它们的注意力分数是多少，最后都会被遮挡为 0，这部分计算就是冗余计算。KV 缓存策略通过预先计算好所有键值对(K,V)的注意力分数和加权值，并缓存起来。在实际推理时，只需从缓存中查询并组装结果，不必重复进行昂贵的点积和加权、累加操作，从而减少冗余计算。

受限于 KV 缓存压力，业界/学界提出新颖的注意力架构（MQA、GQA、SWA）、缓存压缩策略（H2O、Scissorhands、FastGen）、高效的内存管理（PagedAttention、RadixAttention）、量化和存储容量扩展（Offload至 CPU、模型并行）等。总的来说，KV 缓存策略通过精细优化提升了给定内存的处理能力，并且缩短延迟，

海外行业动态报告

但这些建立在给定内存的前提下，实际业务场景下往往推理需求不确定（输入的文本序列长度不确定），这给内存管理造成较大挑战。

硬件角度看，DRAM 的优势是成本低，2023 年单位 GB 的成本大约在中低个位数（<5 美元/GB），远小于 SRAM 的成本，但延迟高（100ns，\~10xSRAM）。一个不利的趋势是，2012 年往后 DRAM 单位 GB 的成本下降幅度较此前有所放缓，这就导致内存侧的瓶颈。并且内存瓶颈与通信带宽瓶颈相互联系，由于模型规模的迅速扩张，通过堆叠 DRAM（例如 3D 堆叠 DRAM 形成 HBM，但会带来额外的封装成本，导致单位 GB 的成本提升到 10-20 美元/GB19），同时并行训练等优化能够缓解内存瓶颈，但这带来额外的通信需求。因此，制约大模型通过长文本推理替代 RAG 的核心原因来自硬件内存架构的制约，并非算力成本下降可以改变的。

图 21:大语言模型参数规模与 AI芯片内存关系
![](images/4f5d8759a4533ed51bce8c21f3c9be6a55a575192b241178883bb6f610af1227.jpg)
AI and Memory Wall

图 22: DRAM 平均每 GB 的价格自 2012 年后下降幅度趋缓
![](images/def681becc6f82796a07061be8ae742ab902237cb5afb6c2d7dc261f3e8fd7a0.jpg)
SemiAnalysis

## 投资评价和建议

整体而言，GenAI 继续沿着 Scaling Laws 拓展性能，在下游任务上解决复杂问题的能力也逐步提升，我们看好 GenAI 在产业内提效的空间。例如，在金融领域，AI 可以用于风险管理、交易执行和客户服务等方面，提高效率、降低成本并改善用户体验。在客服领域，AI 可以完成知识库的自助构建，对话式 AI 处理简单通用性问题，提升客服代理的工作效率。GenAI 提效本质是对任务处理的自动化，解放机械重复的人力开支，转而用算力替代，算力成本中长期有望指数级下降，而人力成本则持续提升，因此 GenAI 的逐步渗透将带来新一波产业创新，中长期商业化提升空间较大。

## 风险分析

数据隐私和安全风险：随着 AI 技术的发展，大量敏感数据被用于训练算法，这可能导致数据隐私泄露和安全漏洞。

监管合规风险：金融领域对于 AI 应用的监管尚不完善，可能存在监管风险。缺乏明确的监管框架和规范可能导致合规问题。

技术风险：AI 技术的发展非常迅速，公司面临技术快速更新换代的风险。如果公司无法跟上技术的发展，持续推出新产品，可能会阻碍公司的发展。

人才流失风险：AI 行业需要拥有专业的人才来支撑技术的发展和应用，如果高素质人才发生流失，可能会影响到公司的长期发展和盈利能力。

## 分析师介绍

## 崔世峰

海外研究首席分析师，南京大学硕士，7 年买方及卖方复合从业经历，专注于互联网及海外 TMT 龙头公司研究，2021 年加入中信建投，2022-2023 年新财富海外研究最佳研究入围，2019-2020 年新财富传媒最佳研究团队第二名团队成员。

## 许悦

海外研究员，南洋理工大学硕士，专注于港股互联网及美股软件研究，2022 年加入中信建投海外前瞻组，2023 年新浪金麒麟港股及海外市场菁英分析师第二名，2023 第十七届水晶球最佳分析师海外行业入围。

## 评级说明

<table><tr><td rowspan=1 colspan=1>投资评级标准</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>评级</td><td rowspan=1 colspan=1>说明</td></tr><tr><td rowspan=8 colspan=1>报告中投资建议涉及的评级标准为报告发布日后6个月内的相对市场表现，也即报告发布日后的6个月内公司股价（或行业指数）相对同期相关证券市场代表性指数的涨跌幅作为基准。A股市场以沪深300指数作为基准；新三板市场以三板成指为基准；香港市场以恒生指数作为基准；美国市场以标普500指数为基准。</td><td rowspan=5 colspan=1>股票评级</td><td rowspan=1 colspan=1>买入</td><td rowspan=1 colspan=1>相对涨幅15%以上</td></tr><tr><td rowspan=1 colspan=1>增持</td><td rowspan=1 colspan=1>相对涨幅 5%—15%</td></tr><tr><td rowspan=1 colspan=1>中性</td><td rowspan=1 colspan=1>相对涨幅-5%—5%之间</td></tr><tr><td rowspan=1 colspan=1>减持</td><td rowspan=1 colspan=1>相对跌幅 5%—15%</td></tr><tr><td rowspan=1 colspan=1>卖出</td><td rowspan=1 colspan=1>相对跌幅15%以上</td></tr><tr><td rowspan=3 colspan=1>行业评级</td><td rowspan=1 colspan=1>强于大市</td><td rowspan=1 colspan=1>相对涨幅10%以上</td></tr><tr><td rowspan=1 colspan=1>中性</td><td rowspan=1 colspan=1>相对涨幅-10-10%之间</td></tr><tr><td rowspan=1 colspan=1>弱于大市</td><td rowspan=1 colspan=1>相对跌幅10%以上</td></tr></table>

## 分析师声明

本报告署名分析师在此声明：（i）以勤勉的职业态度、专业审慎的研究方法，使用合法合规的信息，独立、客观地出具本报告, 结论不受任何第三方的授意或影响。（ii）本人不曾因，不因，也将不会因本报告中的具体推荐意见或观点而直接或间接收到任何形式的补偿。

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

北京

东城区朝内大街2号凯恒中心B座 12 层

电话：（8610） 8513-0588

联系人：李祉瑶

邮箱：lizhiyao@csc.com.cn

上海

上海浦东新区浦东南路528号南塔 2103 室

电话：（8621） 6882-1600

联系人：翁起帆

邮箱：wengqifan@csc.com.cn

## 深圳

福田区福中三路与鹏程一路交汇处广电金融中心35 楼

电话：（86755）8252-1369

联系人：曹莹

邮箱：caoying@csc.com.cn

## 中信建投（国际）

香港

中环交易广场 2 期 18 楼

电话：（852）3465-5600

联系人：刘泓麟

邮箱：charleneliu@csci.hk