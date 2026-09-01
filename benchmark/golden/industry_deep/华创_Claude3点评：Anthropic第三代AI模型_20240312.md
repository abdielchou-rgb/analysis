计算机行业重大事项点评

# Anthropic 第三代 AI 模型——Claude 3 点评

## 事项：

 2024 年 3 月 4 日，Anthropic 发布 Claude 3 系列模型，公司称这是迄今为止速度最快、功能最强大的人工智能模型。

## 评论：

 Claude 3 包含三个模型 Sonnet、Opus、Haiku。其中 Opus 能力最强但成本最高；Sonnet，则是性能与速度平衡的绝佳选择，相较之下，Opus 的性能虽然更强，但响应的速度模型却和旧模型大致相同；Haiku能力最弱，却是成本效益的轻量级选择。

Claude 3 在克服幻觉上有大幅度进步。Claude 3 Opus 在 100Q Hard 评测的准确率达到 46.5%，是 Claude 2 的近 2 倍；在 Multi-factual 评测中准确率提高到62.8%，而错误回答的比例减半。

 Claude 3 在拒答率上做了优化。其 Opus 的错误拒答率从 Claude 2 的 35%降到了 9%。通过人工反馈优化，Opus 能更好判断什么是真正有害的，什么是可以回答的。

 投资策略：Claude 3 具备长文本处理能力，实现多项突破，有望带动 AI 技术创新和商业世界的发展，涉及算力、大模型以及 AI+应用（绘图、视频）等领域。建议关注：1）算力基础：海光信息、寒武纪、龙芯中科；2）服务器：中科曙光、浪潮信息、紫光股份、高新发展、神州数码、拓维信息等；3）大模型：科大讯飞、商汤、三六零等；4）AI+应用：金山办公、万兴科技、美图、虹软科技、当虹科技。

 风险提示：多模态技术发展不及预期、算力基础设施建设不及预期、AI 应用需求不及预期。

## 华创证券研究所

证券分析师：吴鸣远

邮箱：wumingyuan@hcyjs.com

执业编号：S0360523040001

<sup>行</sup>单击此<sup>业基本数</sup>处输<sup>据</sup>入文 字。

## 相对指数表现

<table><tr><td>%</td><td>1M</td><td>6M</td><td>12M</td></tr><tr><td>绝对表现</td><td>22.9%</td><td>-12.6%</td><td>-14.7%</td></tr><tr><td>相对表现</td><td>16.0%</td><td>-8.2%</td><td>-5.4%</td></tr></table>

![](images/d89c546955e7ce4e6e5eaf64c0b7c15c7f66feae641f5b7138eeb8abaa1885f0.jpg)

## 相关研究报告

《两会系列专题二：数智两会：低空提速，促新质生产力发展》

2024-03-12

《计算机行业周报（20240304-20240308）：数智两会：AI+ 赋能产业智能升级》

2024-03-10

《AI+专题系列点评（七）：Gemini、Sora、V-JEPA三大模型对比点评》

2024-03-08

## 目 录

一、Claude 3 性能行业卓越领先...  
（一）Opus：AI 模型的领衔之作.  
（二）Sonnet：性能与速度平衡的绝佳选择.  
（三）Haiku：成本效益的轻量级的选择.  
二、Claude 3 三大亮点..  
（一）幻觉克服能力增强  
（二）缩小长文本理解准确率与人类的差距  
（三）拒答率大幅下降 8  
三、投资策略.  
四、风险提示.

## 图表目录

图表 1 Claude 3 性能行业卓越领先.  
图表 2 Claude 3 Opus 性能最强 .  
图表 3 Sonnet 响应速度快于 Opus.  
图表 4 Claude 3 Haiku 成本效益更高  
图表 5 Claude 3 准确性提高..  
图表 6 Claude 3 上下文窗口测试召回率近乎完美. . 8

## 一、Claude 3 性能行业卓越领先

Claude 3 性能行业卓越领先。Anthropic 推出 Claude 3 系列模型，包括 Claude 3 Opus、Claude 3 Sonnet 和 Claude 3 Haiku。官方公布的数据中，无论是在 MMLU 这样的通用推理任务，还是 MATH、APPS 等数学和编程任务，或是 RACE-H、QuALITY 等阅读理解和常识问答数据集测试，Claude 3 都取得了行业领先成绩，多次超越GPT-4、PaLM、Gemini1.0 Ultra 等强劲模型，展现了顶尖的综合能力。

图表 1 Claude 3 性能行业卓越领先
<table><tr><td></td><td>Claude 3 Opus</td><td>Claude 3 Sonnet</td><td>Claude 3 Haiku</td><td>GPT-4</td><td>GPT-3.5</td><td>Gemini 1.0 Ultra</td><td>Gemini 1.0 Pro</td></tr><tr><td>Undergraduate level knowledge MMLU</td><td>86.8% 5 shot</td><td>79.0% 5-shot</td><td>75.2% 5-shot</td><td>86.4% 5-shot</td><td>70.0% 5-shot</td><td>83.7% 5-shot</td><td>71.8% 5-shot</td></tr><tr><td>Graduate level reasoning GPQA, Diamond</td><td>50.4% 0-shot CoT</td><td>40.4% 0-shot CoT</td><td>33.3% 0-shot CoT</td><td>35.7% 0-shot CoT</td><td>28.1% 0-shot CoT</td><td>一</td><td></td></tr><tr><td>Grade school math GSM8K</td><td>95.0% 0-shot CoT</td><td>92.3% 0-shot CoT</td><td>88.9% 0-shot CoT</td><td>92.0% 5-shot CoT</td><td>57.1% 5-shot</td><td>94.4% Maj1@32</td><td>86.5% Maj1@32</td></tr><tr><td>Math problem-solving MATH</td><td>60.1% 0-shot CoT</td><td>43.1% 0-shot CoT</td><td>38.9% 0-shot CoT</td><td>52.9% 4-shot</td><td>34.1% 4-shot</td><td>53.2% 4-shot</td><td>32.6% 4-shot</td></tr><tr><td>Multilingual math MGSM</td><td>90.7% 0-shot</td><td>83.5% 0-shot</td><td>75.1% 0-shot</td><td>74.5% 8-shot</td><td>一</td><td>79.0% 8-shot</td><td>63.5% 8-shot</td></tr><tr><td>Code HumanEval</td><td>84.9% 0-shot</td><td>73.0% 0-shot</td><td>75.9% 0-shot</td><td>67.0% 0-shot</td><td>48.1% 0-shot</td><td>74.4% 0-shot</td><td>67.7% 0-shot</td></tr><tr><td>Reasoning over text DROP, F1 score</td><td>83.1 3-shot</td><td>78.9 3-shot</td><td>78.4 3-shot</td><td>80.9 3-shot</td><td>64.1 3-shot</td><td>82.4 Variable shots Variable shots</td><td>74.1</td></tr><tr><td>Mixed evaluations BIG-Bench-Hard</td><td>86.8% 3-shot CoT</td><td>82.9% 3-shot CoT</td><td>73.7% 3-shot CoT</td><td>83.1% 3-shot CoT</td><td>66.6% 3-shot CoT</td><td>83.6% 3-shot CoT</td><td>75.0% 3-shot CoT</td></tr><tr><td>Knowledge Q&amp;A ARC-Challenge</td><td>96.4% 25-shot</td><td>93.2% 25-shot</td><td>89.2% 25-shot</td><td>96.3% 25-shot</td><td>85.2% 25-shot</td><td>一</td><td></td></tr><tr><td>Common Knowledge HellaSwag</td><td>95.4% 10-shot</td><td>89.0% 10-shot</td><td>85.9% 10-shot</td><td>95.3% 10-shot</td><td>85.5% 10-shot</td><td>87.8% 10-shot</td><td>84.7% 10-shot</td></tr></table>

Anthropic

## （一）Opus：AI 模型的领衔之作

Claude 3Opus全面超越GPT-4等系列大模型。官方发布的数据显示，在知识测试 MMLU、推理测试 GPQA、基础数学测试 GSM8K 等一系列基准测试中，Claude 3 Opus 模型展现了卓越的性能，其每一项得分都全面超越了 GPT-4 以及 Gemini 1.0 Ultra。Anthropic 宣称，Claude 3 Opus为Claude 3 系列模型的最强版本，具有接近人类的理解能力，能够游刃有余地应对开放式问题，并巧妙解决各种复杂挑战。

图表 2 Claude 3 Opus 性能最强
<table><tr><td></td><td></td><td>Claude 3 Opus</td><td>Claude 3 Sonnet</td><td>Claude 3 Haiku</td><td>GPT-43</td><td>GPT-3.53</td><td>Gemini 1.0 Ultra4</td><td>Gemini 1.5 Pro4</td><td>Gemini 1.0 Pro4</td></tr><tr><td>MMLU</td><td>5-shot</td><td>86.8%</td><td>79.0%</td><td>75.2%</td><td>86.4%</td><td>70.0%</td><td>83.7%</td><td>81.9%</td><td>71.8%</td></tr><tr><td>General reasoning</td><td>5-shot CoT</td><td>88.2%</td><td>81.5%</td><td>76.7%</td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>MATH5 Mathematical</td><td>4-shot</td><td>61%</td><td>40.5%</td><td>40.9%</td><td>52.9% 6,7</td><td>34.1%</td><td>53.2%</td><td>58.5%</td><td>32.6%</td></tr><tr><td>problem solving</td><td>0-shot</td><td>60.1%</td><td>43.1%</td><td>38.9%</td><td>42.5% (from [39])</td><td></td><td></td><td></td><td></td></tr><tr><td></td><td>Maj@32 4-shot</td><td>73.7%</td><td>55.1%</td><td>50.3%</td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>GSM8K</td><td></td><td>95.0%</td><td>92.3%</td><td>88.9%</td><td>92.0%</td><td>57.1%</td><td>94.4%</td><td>91.7%</td><td>86.5%</td></tr><tr><td>Grade school math</td><td></td><td>0-shot CoT</td><td>0-shot CoT</td><td>0-shot CoT</td><td>SFT, 5-shot CoT</td><td>5-shot</td><td>Maj1@32</td><td>11-shot</td><td>Maj1@32</td></tr><tr><td>HumanEval Python coding tasks</td><td>0-shot</td><td>84.9%</td><td>73.0%</td><td>75.9%</td><td>67.0%6</td><td>48.1%</td><td>74.4%</td><td>71.9%</td><td>67.7%</td></tr><tr><td>GPQA (Diamond) Graduate level Q&amp;A</td><td>0-shot CoT</td><td>50.4%</td><td>40.4%</td><td>33.3%</td><td>35.7%</td><td>28.1% (from [1])</td><td></td><td></td><td></td></tr><tr><td></td><td>Maj@32 5-shot CoT</td><td>59.5%</td><td>46.3%</td><td>40.1%</td><td>(from [1])</td><td></td><td></td><td></td><td></td></tr><tr><td>MGSM Multilingual math</td><td></td><td>90.7% 0-shot</td><td>83.5% 0-shot</td><td>75.1% 0-shot</td><td>74.5%7</td><td></td><td>79.0% 8-shot</td><td>88.7% 8-shot</td><td>63.5% 8-shot</td></tr><tr><td>DROP</td><td></td><td></td><td></td><td></td><td>8-shot</td><td></td><td></td><td></td><td></td></tr><tr><td>Reading comprehension, arithmetic</td><td>F1 Score</td><td>83.1 3-shot</td><td>78.9 3-shot</td><td>78.4 3-shot</td><td>80.9 3-shot</td><td>64.1 3-shot</td><td>82.4 Variable shots</td><td>78.9 Variable shots</td><td>74.1 Variable shots</td></tr><tr><td>BIG-Bench-Hard Mixed evaluations</td><td>3-shot CoT</td><td>86.8%</td><td>82.9%</td><td>73.7%</td><td>83.1%7</td><td>66.6%</td><td>83.6%</td><td>84.0%</td><td>75.0%</td></tr><tr><td>ARC-Challenge Common-sense reasoning</td><td></td><td>96.4%</td><td></td><td></td><td>96.3%</td><td></td><td></td><td></td><td></td></tr><tr><td>HellaSwag</td><td></td><td>95.4%</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>Common-sense reasoning PubMedQA8</td><td></td><td>75.8%</td><td>89.0%</td><td>85.9%</td><td>95.3%</td><td>85.5%</td><td>87.8%</td><td></td><td></td></tr><tr><td>Biomedical questions</td><td>5-shot 0-shot</td><td>74.9%</td><td>78.3% 79.7%</td><td>76.0% 78.5%</td><td>74.4% 75.2%</td><td>60.2% 71.6%</td><td></td><td></td><td></td></tr><tr><td>WinoGrande Common-sense reasoning</td><td>5-shot</td><td>88.5%</td><td>75.1%</td><td>74.2%</td><td>87.5%</td><td></td><td></td><td></td><td></td></tr><tr><td>RACE-H Reading comprehension</td><td>5-shot</td><td>92.9%</td><td>88.8%</td><td>87.0%</td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>APPS</td><td>0-shot</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>Python coding tasks MBPP</td><td></td><td>70.2%</td><td>55.9%</td><td>54.8%</td><td></td><td></td><td></td><td></td><td></td></tr></table>

Anthropic

## （二）Sonnet：性能与速度平衡的绝佳选择

Claude 3 Sonnet 性价比最高。在大多数任务中，Sonnet 的速度是 Claude 2 和 Claude 2.1的 2 倍，且在智能处理能力上也实现了质的飞跃。擅长需要迅速响应的任务，例如知识检索和销售自动化。相较之下， Opus的性能虽然更强，但响应的速度模型却和旧模型大致相同。

图表 3 Sonnet 响应速度快于 Opus  
Near-instant results   
The Claude 3 models can power live customer chats, auto-completions, and data extraction tasks where responses   
must be immediate and in real-time.   
Haiku is the fastest and most cost-effective model on the market for its intelligence category. It can read an   
information and data dense research paper on arXiv (\~10k tokens) with charts and graphs in less than three   
seconds. Following launch, we expect to improve performance even further.   
For the vast majority of workloads, Sonnet is 2x faster than Claude 2 and Claude 2.1 with higher levels of   
intelligence. It excels at tasks demanding rapid responses, like knowledge retrieval or sales automation. Opus   
delivers similar speeds to Claude 2 and 2.1, but with much higher levels of intelligence.  
Anthropic

## （三）Haiku：成本效益的轻量级的选择

Claude 3Haiku 可作为轻量级的选择。Haiku模型响应速度最快且可作为轻量级选择。它能在不到三秒的时间内快速消化 arXiv 上的长达约10000个词汇的高密度研究论文及其图表。官方测试结果显示，Haiku 模型的性能水平介于GPT-4 和GPT-3.5 之间，然而在成本效益上，Haiku 模型的性价比远超GPT-4。

图表 4 Claude 3 Haiku 成本效益更高
<table><tr><td rowspan=1 colspan=1>产品名称</td><td rowspan=1 colspan=1>Input($/M)</td><td rowspan=1 colspan=1>Output($/M)</td><td rowspan=1 colspan=1>结论</td></tr><tr><td rowspan=1 colspan=1>Claude 3 Opus</td><td rowspan=1 colspan=1>15</td><td rowspan=1 colspan=1>75</td><td rowspan=2 colspan=1>Opus 相较 GPT-4 Turbo 更贵</td></tr><tr><td rowspan=1 colspan=1>GPT-4 Turbo</td><td rowspan=1 colspan=1>10</td><td rowspan=1 colspan=1>30</td></tr><tr><td rowspan=1 colspan=1>Claude 3 Sonnet</td><td rowspan=1 colspan=1>3</td><td rowspan=1 colspan=1>5</td><td rowspan=1 colspan=1>无对应 GPT 系列比较</td></tr><tr><td rowspan=1 colspan=1>Claude 3 Haiku</td><td rowspan=1 colspan=1>0.25</td><td rowspan=1 colspan=1>1.25</td><td rowspan=2 colspan=1>Turbo 相较 GPT-3.5 Turbo 更便宜</td></tr><tr><td rowspan=1 colspan=1>GPT-3.5 Turbo</td><td rowspan=1 colspan=1>0.5</td><td rowspan=1 colspan=1>1.5</td></tr><tr><td rowspan=1 colspan=4>资料来源：Anthropic官网、OpenAI官网、华创证券</td></tr></table>

## 二、Claude 3 三大亮点

## （一）幻觉克服能力增强

Claude 3 在克服幻觉上有大幅度进步。Anthropic 开发了几个内部评测来考察模型回答的事实准确程度，并与标准做对比。Claude 3 Opus在 100Q Hard评测（包含一些晦涩的开放式问题）的准确率达到 46.5%，是 Claude 2 的近 2 倍；在 Multi-factual 评测中准确率提高到 62.8%，而错误回答的比例减半。模型更多地表示“不确定”而不是给出错误信息。模型很大程度上学会了“不确定” 的中间状态，而不是给出生编硬造的错误答案。

图表 5 Claude 3 准确性提高  
![](images/f93aa08bf9a8a048cddb0c755a830a80981abf42a63ffa44ffba0b0f3b8bf58a.jpg)  
Anthropic

## （二） 缩小长文本理解准确率与人类的差距

Claude 3 长文本理解能力显著增强。QuALITY 阅读理解基准测试是平均 5000 个 token的长篇章，远超一般模型的输入长度。Claude 3 Opus 在 1-shot 下达到 90.5%的准确率，在0-shot下也有89.2%，相比人类 93.5%的表现，Claude 3 已大大缩小了在长文本理解准确率与人类的差距。同时，Claude 3 窗口长度再次翻倍，达到了 200k，并且接受超过100万Tokens的输入,在上下文窗口的测试中，Claude 3 Opus 实现了接近完美的召回率，准确率超过 99%。

图表 6 Claude 3上下文窗口测试召回率近乎完美  
![](images/a4c48dff3cd3d107308af567a412cd0d870b9e4ae4c05d9e8070b478ac05ca29.jpg)  
Anthropic

## （三）拒答率大幅下降

Claude 3在拒答率上做了优化。其在无害问题上拒答率大幅降低，而在有害问题上仍保持高拒答率。Opus 的错误拒答率从 Claude 的 35%降到了 9%。通过人工反馈优化，Opus能更好判断什么是真正有害的，什么是可以回答的。

## 三、投资策略

Claude 3 具备长文本处理能力，实现多项突破，有望带动 AI 技术创新和商业世界的发展，涉及算力、大模型以及 AI+应用（绘图、视频）等领域。建议关注：1）算力基础：海光信息、寒武纪、龙芯中科；2）服务器：中科曙光、浪潮信息、紫光股份、高新发展、神州数码、拓维信息等；3）大模型：科大讯飞、商汤、三六零等；4）AI+应用：金山办公、万兴科技、美图、虹软科技、当虹科技。

## 四、风险提示

多模态技术发展不及预期、算力基础设施建设不及预期、AI应用需求不及预期。

## 计算机组团队介绍

首席研究员、组长：吴鸣远

上海交通大学硕士，曾任职于东方证券、兴业证券研究所，所在团队于2020—2022年连续三年获得新财富最佳分析师第三名，2023年加入华创证券研究所。

研究员：胡昕安工学硕士，曾任职于海康威视，2023 年加入华创证券研究所。

助理研究员：梁佳上海财经大学经济学硕士，2022年加入华创证券研究所。

助理研究员：张宇凡香港大学会计学硕士。2023年加入华创证券研究所。

华创证券机构销售通讯录
<table><tr><td rowspan=1 colspan=1>地区</td><td rowspan=1 colspan=1>姓名</td><td rowspan=1 colspan=1>职务</td><td rowspan=1 colspan=1>办公电话</td><td rowspan=1 colspan=1>企业邮箱</td></tr><tr><td rowspan=9 colspan=1>北京机构销售部</td><td rowspan=1 colspan=1>张昱洁</td><td rowspan=1 colspan=1>副总经理、北京机构销售总监</td><td rowspan=1 colspan=1>010-63214682</td><td rowspan=1 colspan=1>zhangyujie@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>张菲菲</td><td rowspan=1 colspan=1>北京机构副总监</td><td rowspan=1 colspan=1>010-63214682</td><td rowspan=1 colspan=1>zhangfeifei@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>刘懿</td><td rowspan=1 colspan=1>副总监</td><td rowspan=1 colspan=1>010-63214682</td><td rowspan=1 colspan=1>liuyi@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>侯春钰</td><td rowspan=1 colspan=1>资深销售经理</td><td rowspan=1 colspan=1>010-63214682</td><td rowspan=1 colspan=1>houchunyu@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>过云龙</td><td rowspan=1 colspan=1>高级销售经理</td><td rowspan=1 colspan=1>010-63214682</td><td rowspan=1 colspan=1>guoyunlong@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>蔡依林</td><td rowspan=1 colspan=1>资深销售经理</td><td rowspan=1 colspan=1>010-66500808</td><td rowspan=1 colspan=1>caiyilin@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>刘颖</td><td rowspan=1 colspan=1>资深销售经理</td><td rowspan=1 colspan=1>010-66500821</td><td rowspan=1 colspan=1>liuying5@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>顾翎蓝</td><td rowspan=1 colspan=1>资深销售经理</td><td rowspan=1 colspan=1>010-63214682</td><td rowspan=1 colspan=1>gulinglan@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>车一哲</td><td rowspan=1 colspan=1>销售经理</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>cheyizhe@hcyjs.com</td></tr><tr><td rowspan=5 colspan=1>深圳机构销售部</td><td rowspan=1 colspan=1>张娟</td><td rowspan=1 colspan=1>副总经理、深圳机构销售总监</td><td rowspan=1 colspan=1>0755-82828570</td><td rowspan=1 colspan=1>zhangjuan@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>汪丽燕</td><td rowspan=1 colspan=1>高级销售经理</td><td rowspan=1 colspan=1>0755-83715428</td><td rowspan=1 colspan=1>wangliyan@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>张嘉慧</td><td rowspan=1 colspan=1>高级销售经理</td><td rowspan=1 colspan=1>0755-82756804</td><td rowspan=1 colspan=1>zhangjiahui1@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>董姝彤</td><td rowspan=1 colspan=1>销售经理</td><td rowspan=1 colspan=1>0755-82871425</td><td rowspan=1 colspan=1>dongshutong@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>王春丽</td><td rowspan=1 colspan=1>高级销售经理</td><td rowspan=1 colspan=1>0755-82871425</td><td rowspan=1 colspan=1>wangchunli@hcyjs.com</td></tr><tr><td rowspan=11 colspan=1>上海机构销售部</td><td rowspan=1 colspan=1>许彩霞</td><td rowspan=1 colspan=1>总经理助理、上海机构销售总监0</td><td rowspan=1 colspan=1>21-20572536</td><td rowspan=1 colspan=1>xucaixia@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>官逸超</td><td rowspan=1 colspan=1>上海机构销售副总监</td><td rowspan=1 colspan=1>021-20572555</td><td rowspan=1 colspan=1>guanyichao@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>黄畅</td><td rowspan=1 colspan=1>上海机构销售副总监</td><td rowspan=1 colspan=1>021-20572257-2552</td><td rowspan=1 colspan=1>huangchang@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>吴俊</td><td rowspan=1 colspan=1>资深销售经理</td><td rowspan=1 colspan=1>021-20572506</td><td rowspan=1 colspan=1>wujun1@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>张佳妮</td><td rowspan=1 colspan=1>资深销售经理</td><td rowspan=1 colspan=1>021-20572585</td><td rowspan=1 colspan=1>zhangjiani@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>蒋瑜</td><td rowspan=1 colspan=1>高级销售经理</td><td rowspan=1 colspan=1>021-20572509</td><td rowspan=1 colspan=1>jiangyu@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>施嘉玮</td><td rowspan=1 colspan=1>高级销售经理</td><td rowspan=1 colspan=1>021-20572548</td><td rowspan=1 colspan=1>shijiawei@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>朱涨雨</td><td rowspan=1 colspan=1>高级销售经理</td><td rowspan=1 colspan=1>021-20572573</td><td rowspan=1 colspan=1>zhuzhangyu@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>李凯月</td><td rowspan=1 colspan=1>高级销售经理</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>likaiyue@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>易星</td><td rowspan=1 colspan=1>销售经理</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>yixing@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>张玉恒</td><td rowspan=1 colspan=1>销售经理</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>zhangyuheng@hcyjs.com</td></tr><tr><td rowspan=3 colspan=1>广州机构销售部</td><td rowspan=1 colspan=1>段佳音</td><td rowspan=1 colspan=1>广州机构销售总监</td><td rowspan=1 colspan=1>0755-82756805</td><td rowspan=1 colspan=1>duanjiayin@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>周玮</td><td rowspan=1 colspan=1>销售经理</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>zhouwei@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>王世韬</td><td rowspan=1 colspan=1>销售经理</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>wangshitao1@hcyjs.com</td></tr><tr><td rowspan=5 colspan=1>私募销售组</td><td rowspan=1 colspan=1>潘亚琪</td><td rowspan=1 colspan=1>总监</td><td rowspan=1 colspan=1>021-20572559</td><td rowspan=1 colspan=1>panyaqi@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>汪子阳</td><td rowspan=1 colspan=1>副总监</td><td rowspan=1 colspan=1>021-20572559</td><td rowspan=1 colspan=1>wangziyang@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>江赛专</td><td rowspan=1 colspan=1>副总监</td><td rowspan=1 colspan=1>0755-82756805</td><td rowspan=1 colspan=1>jiangsaizhuan@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>汪戈</td><td rowspan=1 colspan=1>高级销售经理</td><td rowspan=1 colspan=1>021-20572559</td><td rowspan=1 colspan=1>wangge@hcyjs.com</td></tr><tr><td rowspan=1 colspan=1>宋丹玙</td><td rowspan=1 colspan=1>销售经理</td><td rowspan=1 colspan=1>021-25072549</td><td rowspan=1 colspan=1>songdanyu@hcyjs.com</td></tr></table>

## 华创行业公司投资评级体系

基准指数说明：

A股市场基准为沪深 300指数，香港市场基准为恒生指数，美国市场基准为标普 500/纳斯达克指数。

公司投资评级说明：

强推：预期未来 6个月内超越基准指数 20%以上；

推荐：预期未来 6个月内超越基准指数 10%－20%；

中性：预期未来 6个月内相对基准指数变动幅度在-10%－10%之间；

回避：预期未来 6个月内相对基准指数跌幅在 10%－20%之间。

## 行业投资评级说明：

推荐：预期未来 3-6个月内该行业指数涨幅超过基准指数 5%以上；

中性：预期未来 3-6个月内该行业指数变动幅度相对基准指数-5%－5%；

回避：预期未来 3-6个月内该行业指数跌幅超过基准指数 5%以上。

## 分析师声明

每位负责撰写本研究报告全部或部分内容的分析师在此作以下声明：

分析师在本报告中对所提及的证券或发行人发表的任何建议和观点均准确地反映了其个人对该证券或发行人的看法和判断；分析师对任何其他券商发布的所有可能存在雷同的研究报告不负有任何直接或者间接的可能责任。

## 免责声明

本报告仅供华创证券有限责任公司（以下简称“本公司”）的客户使用。本公司不会因接收人收到本报告而视其为客户。

本报告所载资料的来源被认为是可靠的，但本公司不保证其准确性或完整性。本报告所载的资料、意见及推测仅反映本公司于发布本报告当日的判断。在不同时期，本公司可发出与本报告所载资料、意见及推测不一致的报告。本公司在知晓范围内履行披露义务。

报告中的内容和意见仅供参考，并不构成本公司对具体证券买卖的出价或询价。本报告所载信息不构成对所涉及证券的个人投资建议，也未考虑到个别客户特殊的投资目标、财务状况或需求。客户应考虑本报告中的任何意见或建议是否符合其特定状况，自主作出投资决策并自行承担投资风险，任何形式的分享证券投资收益或者分担证券投资损失的书面或口头承诺均为无效。本报告中提及的投资价格和价值以及这些投资带来的预期收入可能会波动。

本报告版权仅为本公司所有，本公司对本报告保留一切权利。未经本公司事先书面许可，任何机构和个人不得以任何形式翻版、复制、发表、转发或引用本报告的任何部分。如征得本公司许可进行引用、刊发的，需在允许的范围内使用，并注明出处为“华创证券研究”，且不得对本报告进行任何有悖原意的引用、删节和修改。

证券市场是一个风险无时不在的市场，请您务必对盈亏风险有清醒的认识，认真考虑是否进行证券交易。市场有风险，投资需谨慎。

## 华创证券研究所

<table><tr><td>北京总部</td><td>广深分部</td><td>上海分部</td></tr><tr><td>地址：北京市西城区锦什坊街26号 恒奥中心 C 座 3A</td><td>地址：深圳市福田区香梅路1061号中投国 际商务中心A 座19楼</td><td>地址：上海市浦东新区花园石桥路33号 花旗大厦 12 层</td></tr><tr><td>邮编：100033 传真：010-66500801</td><td>邮编：518034</td><td>邮编：200120</td></tr><tr><td>会议室：010-66500900</td><td>传真：0755-82027731</td><td>传真：021-20572500</td></tr><tr><td></td><td>会议室：0755-82828562</td><td>会议室：021-20572522</td></tr></table>