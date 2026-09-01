# Navigating the Hedge Fund Maze

This is the forty-ninth edition of our Quantcraft series. This periodical outlines new trading and analytical models across different asset classes.

Today’s report navigates the complex landscape of hedge fund investing, unravelling insights into strategies, performance trends, and innovative portfolio construction methodologies.

We examine the Hedge Fund Research (HFR) database, discussing the intricacies of analysing hedge fund performance, risk measurement, manager selection and risk profiling.

We introduce a quantitative approach to construct portfolios tailored to specific investor goals—whether achieving market neutrality or mitigating drawdowns.

Additionally, we investigate the relationship between hedge funds and bank-based QIS strategies, showcasing their potential for synergistic portfolio enhancement through diversification.

In summary, this study provides a refined perspective to guide investors through the intricacies of this rewarding but complex alternative asset class.

Figure 1: Navigating the Hedge Fund Maze
![](images/b5e6ac64f03468d00d80b4c295e9612376781372380cca93398ea4ae71014582.jpg)
Source: Deutsche Bank.

## Deutsche Bank AG/London

IMPORTANT RESEARCH DISCLOSURES AND ANALYST CERTIFICATIONS LOCATED IN APPENDIX 1. Note to U.S. investors: US regulators have not approved most foreign listed stock index futures and options for US investors. Eligible investors may be able to get exposure through over-the-counter products. Deutsche Bank does and seeks to do business with companies covered in its research reports. Thus, investors should be aware that the firm may have a conflict of interest that could affect the objectivity of this report. Investors should consider this report as only a single factor in making their investment decision. MCI (P) 041/10/2023.

# Navigating the Hedge Fund Maze

## 1. Introduction

Hedge funds are a fundamental pillar of institutional investor portfolios and have demonstrated their value by providing diversification and reliable positive returns over time. But as aptly stated by George Soros, "Hedge funds are like a gold mine. If you know where to dig, you can make a lot of money. But if you don't, you can lose a lot of money." This study aims to provide a framework for investors to prudently “know where to dig” by evaluating various strategies, scrutinising fund managers, and constructing portfolios aligned with optimal investment objectives.

To unravel the complexities of hedge fund performance and enable informed investment decisions, this study has three primary objectives:

1. To offer crucial insights. Providing investors with essential insights involves deciphering the intricacies of hedge fund performance. This includes scrutinising return distributions across various styles, examining factor exposures, and evaluating persistency over time. This analysis aims to enhance investors comprehension of the dynamics inherent in hedge fund investments.

2. To introduce a quantitative framework for allocation. A significant contribution of this study is the introduction of a quantitative framework designed to construct optimal hedge fund portfolios tailored to specific investor goals, such as achieving market neutrality or providing convexity. By presenting a systematic approach to portfolio construction, investors are equipped with a robust tool to align their portfolios with precise investment objectives.

3. To evaluate hedge funds versus bank-based quantitative investment solutions (QIS) strategies. This study conducts a comparative analysis, assessing hedge funds against bank-based quantitative investment solutions (QIS) strategies to evaluate the potential cost-adjusted alpha that hedge funds can provide over standard QIS strategies; we also investigate the relationship between hedge funds and QIS strategies, showcasing their potential for synergistic portfolio enhancement through greater diversification.

This Quantcraft is structured as follows: Section 2 introduces the HFR database, emphasising its coverage, biases, and our approach to addressing them. Building on this foundation, Section 3 delves into the complexities of hedge fund performance, covering aspects such as return distributions across styles, factor exposures, and persistency. Next, Section 4 presents our quant framework for constructing hedge fund portfolios tailored to meet specific investor goals, featuring examples of market-neutral and CTA portfolios. Section 5 explores the relationships between hedge funds and QIS strategies. Finally, Section 6 concludes by summarising key insights and offering final thoughts. Additionally, Appendix I presents our approach to combining QIS strategies across asset classes and styles to maximise absolute return while maintaining market neutrality.

## 2. Introducing the HFR database

## 2.1 The dataset

In this study, we leverage the HFR database<sup>1</sup> to acquire managers' performance data. Hedge Fund Research (HFR) maintains a subscription-based database comprising over 6,000 funds (as of June 2022), providing monthly return data since 1990, though coverage is limited before that period. The HFR database offers a comprehensive repository of hedge fund performance and statistics, enabling us to undertake a rigorous industry analysis. Figure 2 depicts the coverage of all hedge funds within the HFR database. Notably, the number of hedge funds has experienced a decline in recent years from a peak of approximately 10,000.

Figure 2: The coverage of hedge funds in HFR
![](images/76d8c34f54b725227ef33a84550c2ee406c714f4cb91172befce64e0f7cf73e7.jpg)

In this study, we focus on five major strategy classifications differentiated by underlying approach -

Global Macro, Event-Driven, Relative Value, Equity Hedge, and Fund of Funds:

Global Macro fund managers utilise a discretionary top-down methodology to assess macroeconomic trends globally.

Event-driven specialists target opportunities around corporate events like mergers, restructurings, or bankruptcies to capture valuation discrepancies.

Relative Value funds aim to capitalise on pricing discrepancies through sophisticated arbitrage techniques.

Funds in the Equity Hedge category combine fundamental stock picking with quantitative alpha modelling, overlayed with variable net market exposure.

Finally, Fund of Funds offers bundled multi-manager vehicles to diversify manager-specific risks better.

As Figure 3 shows, Equity Hedge has traditionally constituted the majority share within the database by aggregated assets. Accessing the HFR database allows for deep analysis of these primary strategy classifications through their automated categorisation.

Figure 3: The coverage of hedge funds in HFR
![](images/e2bfeaec527b737657ae31505f0303b9c0ef47999b2a14263d90c81e1cc8a94f.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

## 2.2 Hedge fund metrics in the HFR database

The comprehensive HFR database provides researchers with an expansive set of manager metrics spanning two broad classifications - static and temporal attributes. Static characteristics encapsulate fixed details that remain invariant since the fund's inception date. This includes unchanging identifiers, initiation year, management fee structure disclosed, use of high watermark incentive provisions, precise inception date tracked by HFR, and other contractual terms established at origination. As Figure 4 exhibits, these transparent static descriptors offer initial perspectives into funds' operational approaches.

<table><tr><td colspan="2">Figure 4: Static descriptors within the HFR database</td></tr><tr><td>Field</td><td>Definition</td></tr><tr><td>Code</td><td>Unique code specific to each fund</td></tr><tr><td>Fund</td><td>Fund name</td></tr><tr><td>Money Manager</td><td>Money Management firm</td></tr><tr><td>Structure</td><td>Legal structure (Caymans Corporation, Delaware LP, etc.)</td></tr><tr><td>Country</td><td>Country of Money Manager base</td></tr><tr><td>Inception</td><td>Inception date for the specific fund</td></tr><tr><td>Main Strategy</td><td>Main investment strategy</td></tr><tr><td>Sub-Strategy</td><td>Investment sub-strategy</td></tr><tr><td>Fund Assets</td><td>Total assets in the fund (updated</td></tr><tr><td>Fund Assets Currency</td><td>monthly or quarterly) Currency denomination of fund assets</td></tr><tr><td>Leverage</td><td>Fund Leverage Range</td></tr><tr><td>Returns Denomination</td><td>Currency base for the fund performance (i.e. USD, EUR, GBP, etc)</td></tr><tr><td>Management Fee</td><td>Annual management fee percentage</td></tr><tr><td>Incentive Fee</td><td>Annual incentive fee percentage (if available)</td></tr><tr><td>High Watermark</td><td>Specifies if fees are taken only after a</td></tr><tr><td>Minimum Investment</td><td>high watermark Minimum investment for the fund</td></tr><tr><td>Minimum Investment Denomination</td><td>Currency base for minimum investment of fund</td></tr><tr><td>Additional Investments</td><td>Additional investments allowed in the</td></tr><tr><td>Redemptions</td><td>fund after the initial investment Redemption intervals from the fund</td></tr><tr><td>Lockup</td><td>(i.e. monthly, quarterly, annually) Lockup interval (length of time that</td></tr><tr><td>Advanced Days Notice</td><td>new investor cannot redeem assets) Indicates advance notice, in days,</td></tr><tr><td>In HFRI</td><td>required for Redemptions Indicates if a fund is included in HFRI</td></tr><tr><td>In HFRX</td><td>Monthly Indices Indicates if a fund is included within</td></tr><tr><td>Date Added to DB</td><td>the HFRX Indices Reflects the date a fund became</td></tr><tr><td></td><td>active in the HFR Database</td></tr><tr><td>Domicile Firm SEC Registered</td><td>Location of Fund registration Indicates if the Firm is an SEC-</td></tr><tr><td></td><td>Registered Investment Advisor</td></tr><tr><td>Fund Status</td><td>Indicates if the Fund is Active or Liquidated/No Longer Reporting</td></tr><tr><td>Source: Deutsche Bank, HFR.</td><td></td></tr></table>

Complementing the static descriptors, HFR also provides time-variant temporal statistics across four useful categorisations:

Performance: Performance data for hedge funds at each period in time.

Asset: Specifies the assets held over time for each hedge fund.

Region: Specifies a fund’s regional investment allocation (i.e., Canada, USA, etc.).

Instrument: Specifies a fund’s instrument investment allocation (i.e., bonds, equities, etc).

Figure 5 shows some key temporal data items provided within the HFR database.
<table><tr><td colspan="3">Figure 5: Temporal descriptors within the HFR database</td></tr><tr><td>Group</td><td>Field</td><td>Description</td></tr><tr><td>Performance Code</td><td></td><td>Unique code specific to each fund</td></tr><tr><td rowspan="4"></td><td>Fund</td><td>Fund Name</td></tr><tr><td>Date</td><td>Date for performance figure</td></tr><tr><td>Performance</td><td>Percentage performance for fund for month or quarter</td></tr><tr><td>NAV</td><td>Net Asset Value for the fund for this period</td></tr><tr><td>Asset</td><td>Date</td><td>Date for asset figure</td></tr><tr><td></td><td>Assets</td><td>Assets for this period in millions of currency units</td></tr><tr><td rowspan="4">Region</td><td>Date</td><td>Date for Region figure</td></tr><tr><td>Region</td><td>Region of investment (Canada, USA, Eastern Europe, etc.)</td></tr><tr><td>Long</td><td>Long allocation in percent</td></tr><tr><td>Short</td><td>Short allocation in percent</td></tr><tr><td rowspan="6">Instrument</td><td>Net</td><td>Net allocation in percent</td></tr><tr><td>Code</td><td>Unique code specific to each underlying fund</td></tr><tr><td>Date</td><td>Date for instrument figure</td></tr><tr><td>Instrument</td><td>Instrument invested (corporate bonds, equities, etc.)</td></tr><tr><td>Long</td><td>Long allocation in percent</td></tr><tr><td>Short</td><td>Short allocation in percent</td></tr><tr><td></td><td>Net</td><td>Net allocation in percent</td></tr><tr><td colspan="3">Source: Deutsche Bank, HFR.</td></tr></table>

Initially, our dataset comprises information on 28,344 hedge funds, both defunct <sup>2</sup> and live <sup>3</sup> . However, duplications arise due to funds reporting returns in various currencies. We exclude non-US dollar-based hedge funds to ensure data accuracy, resulting in a refined sample of 19,799 distinct hedge funds.

Next, we investigate potential biases in hedge fund studies and detail our approach to addressing them.

## 2.3 Biases in Hedge Fund Databases

Hedge fund studies are susceptible to data biases, some of which are well-known and have been extensively covered in the literature<sup>4</sup>.

The first example is the survivorship bias that arises when only hedge funds still operating at the end of the sample period are included in the analysis. This can lead to hedge fund performance being overestimated, as the failed funds were excluded. We mitigate this bias by incorporating active and defunct funds from the HFR database (Figure 6).

![](images/efeecbb3905cfe5516bc7b8eb99e61abc9407062af58037b9b879ea48da283b1.jpg)

Another critical data bias in hedge fund studies is the backfill or instant-history bias. This bias appears when new fund additions retroactively add historical returns, creating an inflated early track record as typically only successful funds report initial performance. The HFR database provides the date on which funds are added to the database, as well as the date of their first reported performance. On average, 18 months pass between the database inclusion date and the first reported performance date, because funds typically provide approximately 1.5 years of backfilled historical returns when initially onboarded. Thus, to avoid backfill bias in our analysis, we omit the first 18 months of returns for all funds in our database. Figure 7 displays the coverage of backfilled versus non-backfilled data within the HFR database.

Figure 7: Backfilled coverage of hedge funds
![](images/3a90425d2a75bf689053cd944b8bee5652b47db35551bedc3fab86eeb2571d3f.jpg)

Next is the selection bias. This occurs in hedge fund databases because reporting is voluntary, creating a nonrepresentative sample. Superior performers likely participate to attract capital, skewing reported returns upwards. However, some strong funds may avoid reporting if they do not need investment, biasing returns downwards by excluding top non-reporters. While quantifying the net effect is challenging given the unobservable full population, we acknowledge the potential impact. We aimed to mitigate this issue by using the robust HFR database, which captures information on most hedge funds despite this prevalent industry-wide voluntary reporting bias.

Finally, hedge fund databases also face a multi-period sampling bias stemming from funds lacking adequate return history. Including funds with a limited return history can bias results. Investors may overestimate future performance if only short track records are provided. Additionally, small sample sizes hinder robust statistical analysis due to insufficient observations. To mitigate this look-ahead bias, we impose a 24-month minimum return history requirement, excluding newer funds with insufficient data.

A final data cleansing step involves removing outliers, and to that effect, we exclude funds with long-term volatility outside the 1st and 99th percentiles.

From an initial universe of 19,799 USD-denominated funds, our comprehensive bias-removal process yields a bias-free subset of 13,274 funds, representing a 32% reduction in sample size. Figure 8 illustrates the original and "scrubbed" universe.

Figure 8: Coverage of narrowed universe
![](images/7b5559c6abe551baa0ceb8212296274db93c93f8e8024258596db19bc07dcdec.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

In summary, to ensure an accurate evaluation of hedge fund performance drivers in the following sections, we refine the universe by:

Incorporating inactive funds to reduce survivorship bias.

Excluding backfilled returns to minimise instant history bias.

Excluding funds with less than a two-year history to reduce multi-period sampling bias.

Removing outliers based on volatility to eliminate distortions.

This data-scrubbing process yields an unbiased, representative subset suitable for subsequent intricate analysis of the determinants of hedge fund performance over time.

## 3. Intricacies of Hedge Fund Performance

In the previous section, we discussed common biases in hedge fund databases and our approaches to mitigate them through comprehensive data filtering. Building on that filtered foundation, we now delve into the intricacies of hedge fund performance. Our analysis evaluates return distributions across main and sub-strategies, assessing relationships over time through correlation and principal component lenses. These quantitative evaluations of performance patterns across strategies serve as a gateway to bias-free manager selection later in the report.

## 3.1 Return distributions, correlations, and PCA analysis

We start the analysis by observing the annual return distribution of hedge funds over time. Figure 9 plots the 75th percentile, median, and 25th percentile annual performance across funds.

The downward trend in median hedge fund returns (Figure 9, top chart) suggests performance has become increasingly challenging, especially during and following the Financial Crisis. Potential drivers include higher cross-asset correlations, more frequent mini-crises, and growing macro influence on asset returns and volatility. Nevertheless, the results highlight that hedge fund manager selection is becoming increasingly important.

Adding further colour, Figure 9 (bottom chart) shows the performance spread between the 75th percentile and 25th percentile of annual hedge fund returns over time. Interestingly, this interquartile range exhibits a tightening trend, implying hedge fund returns are becoming less differentiated and likely more correlated in recent periods relative to history.

Analysing the distribution of return correlations between hedge fund pairs offers another lens into performance homogeneity across the universe. As depicted in Figure 10, the average correlation coefficient between funds increased over the evaluation period. This further confirms that return convergence has accelerated in recent periods, reiterating that manager selection could have diminishing differentiation potential in the current era relative to history.

Figure 9: Percentile distribution of annual hedge fund returns, showing trend line (top) and spread (bottom)
![](images/956736f1ee470f2f0231075dc694bf44d2d4be0fa1219992956e1af48fb02054.jpg)

![](images/d535267a5472b855b6fcfc1f0119d9ebca2babb725c11003fd1812c3377b7c46.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

Our principal component analysis (PCA) on hedge fund returns provides additional revelations. As depicted in Figure 11, we estimated the number of principal components (PCs) required to explain two-thirds of return variation over time. Also, we represented it as a percentage of active funds.

Figure 10: 2Y rolling pairwise correlation of hedge funds
![](images/9b9a810e79e249f271e465db2556f600b387be1fed408b64bd99741aa7d3c4e6.jpg)

We observe a small set between 10 and 40 PCs consistently explains over two-thirds, further demonstrating an inherent performance correlation structure that binds the hedge fund universe. Moreover, in periods of market turbulence, this explanatory subset shrinks as underlying funds become more systematically correlated amid crises.

While already limited historically, the tightening eigenvector set combined with the prior correlation analysis reaffirms that turbulence-induced systemic linkages dominate hedge fund variation, leaving diminishing room for diversification.

Figure 11: Number of PCs to explain two-thirds of hedge funds variations
![](images/f57f19b77d2185f1ab57509c9ed973cb19426d69b6fdb3aeff3f36045a8fe2e8.jpg)

In summary, median hedge fund returns have broadly declined over time, while performance convergence has simultaneously reduced differentiation across underlying managers. These joint dynamics highlight intensifying challenges in manager selection and the quest for truly uncorrelated alpha generation.

Moving forward, we shift the analysis to evaluating relative performance across higher-level hedge fund categories, recognising meaningful dispersion also exists at the more granular strategy sub-classifications shown previously in Figure 3.

## 3.2 Performance across hedge fund categories

Thus far, we have focused our analysis on hedge fund performance at an aggregate level. This section delves into performance specifics across different hedge fund strategies and sub-strategies.

Figure 12 (top) depicts the median performance trends over time across different strategies, while Figure 12 (bottom) provides insight into the return dispersion between the top and bottom quartile funds within each strategy. Figure 13 then presents the overall averages and standard deviations of these performance metrics for each strategy.

Figure 12: Median (top) and dispersion (bottom) of hedge fund returns by style
![](images/36df6a83837fd330526df9a47411896676066896122ac428e990952dd8d8cd51.jpg)

![](images/1e74f86b2d31d54bffbf19cf1ed34cd82c6f355e5845358f7ee24c65cd437042.jpg)

Our key observations are as follows:

The Equity Hedge category consistently exhibits the highest average returns over time, with a notable variation in median performance among its underlying strategies. This likely stems from funds taking net long positions amidst equity bull markets in recent decades. Additionally, Equity Hedge displays the widest dispersion between top and bottom quartile returns across categories, presenting an especially attractive selection opportunity for identifying top managers.

As expected, Funds of Funds demonstrated more steady and consistent performance over time, except amidst the 2008 Financial Crisis. This category evidenced the lowest return dispersion between underlying managers compared to other strategies, exemplifying a diversification effect. However, the minimal variability also indicates limited potential for further value-add from selective picking between Funds of Funds, which aggregate multiple funds internally.

Figure 13: Average (top) and standard deviation (bottom) of median hedge fund returns and dispersion
![](images/7b6b43aa46ddb80bb365bee6aa2dca5b0bcf0edff22a980284dd2b4769c367e5.jpg)

![](images/1de9b2cb665dd87292e9296d02ce1225357980dd1e5c1e1198237ab9050a3d8a.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

Global Macro funds weathered the 2008 Financial Crisis better than most other hedge fund strategies, as evidenced by their relative outperformance during this tumultuous period. This showcased Global Macro’s diversification benefits for portfolios seeking non-correlated exposures across varying environments. However, median performance for the category has declined in post-crisis periods, presenting challenges for tactical macro managers more recently as cross-asset correlations have risen.

The extensive analyses on performance trends and dispersion validated notable variations in hedge fund outcomes across both main and sub-strategies over time. Quantifying these strategy-level differentiations, Figures 14 and 15 show summary performance and risk statistics classified along HFR's methodology by primary hedge fund category and more detailed sub-strategy.

Figure 14: Summary statistics by main strategy
<table><tr><td rowspan="2">Main strategy</td><td rowspan="2">Number of Funds</td><td rowspan="2">Annual Return</td><td rowspan="2">Annual Volatility</td><td rowspan="2">Sharpe Ratio</td><td rowspan="2">Sortino</td><td rowspan="2">Omega Ratio</td><td rowspan="2">Skew</td><td rowspan="2">Excess Kurtosis</td><td rowspan="2">Max DD</td></tr><tr><td></td></tr><tr><td>Event-Driven</td><td>1079</td><td>7.7%</td><td>8.9%</td><td>0.86</td><td>1.38</td><td>2.08</td><td>-0.47</td><td>4.34</td><td>19.5%</td></tr><tr><td>Equity Hedge</td><td>5195</td><td>7.7%</td><td>13.9%</td><td>0.59</td><td>0.93</td><td>1.59</td><td>-0.16</td><td>1.73</td><td>25.6%</td></tr><tr><td>Macro</td><td>2432</td><td>6.2%</td><td>12.3%</td><td>0.52</td><td>0.85</td><td>1.50</td><td>0.19</td><td>1.31</td><td>20.9%</td></tr><tr><td>Relative Value</td><td>1986</td><td>6.5%</td><td>7.5%</td><td>0.85</td><td>1.31</td><td>2.12</td><td>-0.71</td><td>5.35</td><td>15.2%</td></tr><tr><td>Fund of Funds</td><td>2582</td><td>4.6%</td><td>6.7%</td><td>0.68</td><td>1.00</td><td>1.70</td><td>-0.77</td><td>2.72</td><td>19.3%</td></tr></table>

Source: Deutsche Bank, Bloomberg Finance LP, HFR

Figure 15: Summary statistics by sub-strategy
<table><tr><td rowspan="2">Main Strategy</td><td rowspan="2">Sub Strategy</td><td rowspan="2">Number of Funds</td><td rowspan="2">Annual Return</td><td rowspan="2">Annual Volatility</td><td rowspan="2">Sharpe Ratio</td><td rowspan="2">Sortino</td><td rowspan="2">Omega Ratio</td><td rowspan="2">Skew</td><td rowspan="2">Excess Kurtosis</td><td rowspan="2">Max DD</td></tr><tr><td></td></tr><tr><td rowspan="7">Event-Driven</td><td>Merger Arbitrage</td><td>172</td><td>5.9%</td><td>5.9%</td><td>1.18</td><td>1.71</td><td>2.58</td><td>-0.72</td><td>4.58</td><td>7.9%</td></tr><tr><td>Distressed/Restructuring</td><td>293</td><td>9.1%</td><td>10.9%</td><td>1.02</td><td>1.47</td><td>2.15</td><td>-0.44</td><td>4.78</td><td>22.2%</td></tr><tr><td>Private Issue/Regulation D</td><td>37</td><td>16.9%</td><td>13.3%</td><td>1.63</td><td>2.83</td><td>3.79</td><td>0.62</td><td>5.39</td><td>19.2%</td></tr><tr><td>Special Situations</td><td>330</td><td>9.2%</td><td>12.2%</td><td>0.90</td><td>1.33</td><td>1.95</td><td>-0.47</td><td>3.49</td><td>22.2%</td></tr><tr><td>Activist</td><td>51</td><td>10.6%</td><td>18.9%</td><td>0.63</td><td>1.01</td><td>1.69</td><td>-0.36</td><td>2.54</td><td>29.5%</td></tr><tr><td>Credit Arbitrage</td><td>84</td><td>6.6%</td><td>9.3%</td><td>0.90</td><td>0.99</td><td>2.09</td><td>-1.78</td><td>13.22</td><td>21.4%</td></tr><tr><td>Multi-Strategy</td><td>112</td><td>7.4%</td><td>10.4%</td><td>0.81</td><td>1.08</td><td>1.84</td><td>-0.62</td><td>4.20</td><td>19.9%</td></tr><tr><td rowspan="8">Equity Hedge</td><td>Equity Market Neutral</td><td>613</td><td>5.9%</td><td>8.7%</td><td>0.77</td><td>1.12</td><td>1.71</td><td>-0.02</td><td>1.33</td><td>13.8%</td></tr><tr><td>Fundamental Growth</td><td>1346</td><td>8.7%</td><td>18.7%</td><td>0.54</td><td>0.81</td><td>1.51</td><td>-0.17</td><td>1.82</td><td>33.2%</td></tr><tr><td>Fundamental Value</td><td>1898</td><td>8.9%</td><td>15.3%</td><td>0.66</td><td>0.96</td><td>1.62</td><td>-0.19</td><td>1.94</td><td>26.8%</td></tr><tr><td>Sector - Energy/Basic Materials</td><td>173</td><td>9.1%</td><td>20.4%</td><td>0.49</td><td>0.60</td><td>1.36</td><td>-0.26</td><td>2.14</td><td>35.2%</td></tr><tr><td>Sector -Technology</td><td>210</td><td>11.7%</td><td>17.9%</td><td>0.78</td><td>1.14</td><td>1.72</td><td>0.15</td><td>1.11</td><td>22.8%</td></tr><tr><td>Short Bias</td><td>61</td><td>3.4%</td><td>21.1%</td><td>0.13</td><td>0.26</td><td>1.15</td><td>0.15</td><td>1.33</td><td>49.0%</td></tr><tr><td>Quantitative Directional</td><td>424</td><td>13.2%</td><td>17.4%</td><td>0.77</td><td>1.21</td><td>1.76</td><td>-0.06</td><td>1.52</td><td>23.4%</td></tr><tr><td>Multi-Strategy</td><td>283</td><td>7.3%</td><td>13.9%</td><td>0.58</td><td>0.76</td><td>1.50</td><td>-0.23</td><td>2.11</td><td>22.9%</td></tr><tr><td rowspan="10">Macro</td><td>Sector - Healthcare Discretionary Thematic</td><td>187 446</td><td>11.8% 8.0%</td><td>17.5% 14.5%</td><td>0.74 0.63</td><td>1.18 0.92</td><td>1.71 1.59</td><td>0.31 0.01</td><td>1.26 1.93</td><td>23.0% 20.2%</td></tr><tr><td>Systematic Diversified</td><td>1025</td><td>8.0%</td><td>15.2%</td><td>0.54</td><td>0.86</td><td>1.47</td><td>0.26</td><td>0.91</td><td></td></tr><tr><td>Currency - Systematic</td><td>192</td><td>7.6%</td><td>12.5%</td><td>0.68</td><td>1.00</td><td>1.58</td><td>0.52</td><td>1.43</td><td>21.6%</td></tr><tr><td>Multi-Strategy</td><td>287</td><td>6.4%</td><td>13.0%</td><td>0.56</td><td>0.76</td><td>1.48</td><td>0.04</td><td>1.79</td><td>16.9%</td></tr><tr><td>Currency - Discretionary</td><td>66</td><td>5.9%</td><td>9.1%</td><td>0.58</td><td>0.71</td><td>1.41</td><td>0.25</td><td>2.18</td><td>19.7%</td></tr><tr><td>Active Trading</td><td>97</td><td></td><td>12.4%</td><td>0.68</td><td>1.03</td><td>1.62</td><td>-0.11</td><td>1.31</td><td>15.4%</td></tr><tr><td>Commodity - Agriculture</td><td>54</td><td>7.1%</td><td>17.2%</td><td>0.56</td><td>0.81</td><td>1.49</td><td>0.46</td><td></td><td>20.5%</td></tr><tr><td>Commodity - Energy</td><td>49</td><td>7.8% 7.9%</td><td>18.7%</td><td>0.43</td><td>0.81</td><td>1.49</td><td>0.24</td><td>1.78 2.51</td><td>21.8%</td></tr><tr><td>Commodity - Metals</td><td></td><td>5.2%</td><td>22.9%</td><td>0.19</td><td>0.32</td><td>1.17</td><td>0.20</td><td></td><td>29.8%</td></tr><tr><td>Commodity - Multi</td><td>38 178</td><td>5.4%</td><td>14.1%</td><td>0.42</td><td>0.70</td><td>1.42</td><td>0.32</td><td>0.47 1.53</td><td>48.1%</td></tr><tr><td rowspan="7">Relative Value</td><td>Fixed Income - Convertible Arbitrage</td><td>233</td><td>7.3%</td><td>8.8%</td><td>1.10</td><td>1.54</td><td>2.32</td><td>-1.00</td><td>4.91</td><td>23.2%</td></tr><tr><td>Volatility</td><td>187</td><td>8.0%</td><td>14.2%</td><td>0.67</td><td>0.95</td><td>1.77</td><td>-0.59</td><td>6.33</td><td>17.6%</td></tr><tr><td>Multi-Strategy</td><td>536</td><td>6.9%</td><td>8.4%</td><td>1.11</td><td>1.52</td><td>2.21</td><td>-0.80</td><td>3.87</td><td>20.6% 12.8%</td></tr><tr><td>Fixed Income - Asset Backed</td><td>358</td><td>8.6%</td><td>7.3%</td><td>1.60</td><td>2.14</td><td>3.59</td><td>-1.86</td><td>10.86</td><td>10.8%</td></tr><tr><td>Fixed Income - Corporate</td><td>420</td><td>5.5%</td><td>8.2%</td><td>0.90</td><td>1.20</td><td>2.04</td><td>-1.22</td><td>6.64</td><td>14.0%</td></tr><tr><td>Fixed Income - Sovereign</td><td>111</td><td>5.1%</td><td>8.1%</td><td>0.80</td><td>0.99</td><td>1.82</td><td>-1.00</td><td>4.10</td><td>15.6%</td></tr><tr><td>Yield Alternatives - Energy Infrastructure</td><td>69</td><td>7.7%</td><td>18.3%</td><td>0.52</td><td>0.55</td><td>1.39</td><td>-0.51</td><td>2.24</td><td>46.5%</td></tr><tr><td rowspan="4">Fund of Funds</td><td>Yield Alternatives - Real Estate</td><td>72</td><td>7.2%</td><td>13.2%</td><td>0.67</td><td>0.97</td><td>1.64</td><td>-0.37</td><td>2.53</td><td>19.6%</td></tr><tr><td>Conservative</td><td>485</td><td>4.3%</td><td>5.1%</td><td>1.06</td><td>1.28</td><td>2.13</td><td>-1.65</td><td>5.09</td><td>15.5%</td></tr><tr><td>Diversified</td><td>1138</td><td>4.9%</td><td>7.1%</td><td>0.77</td><td>1.07</td><td>1.76</td><td>-0.85</td><td>2.82</td><td>18.4%</td></tr><tr><td>Market Defensive Strategic</td><td>125 834</td><td>4.6% 4.9%</td><td>9.2% 10.7%</td><td>0.74 0.56</td><td>1.18 0.77</td><td>1.69 1.51</td><td>-0.10 -0.62</td><td>1.16 2.26</td><td>14.0% 23.8%</td></tr></table>

Source: Deutsche Bank, Bloomberg Finance LP, HFR

The figures exhibit significant performance variation across main strategies and between more specialised sub-strategies within each category. This performance heterogeneity underscores the breadth within the asset class, encompassing specialised approaches with distinct return profiles. These insights help investors to make more informed strategy allocations based on historical performance intricacies.

Building on these strategy-level insights, we delve into the factors driving hedge fund returns.

## 3.3 Hedge fund factor exposures

This section examines hedge fund exposure to common risk factors. As a necessary prerequisite, we must create a factor-based model that concisely explains hedge fund performance with reasonable efficacy. However, developing a parsimonious yet adequately exhaustive model poses inherent complexity given the diversity of hedge fund strategies.

The rationale is such a model allows for properly gauging managers’ skills through risk adjustment. It facilitates precise performance attribution to systematic market drivers versus manager value-add. This factor lens enables the formulation of optimal hedge fund portfolio allocations tailored to investor goals based on strategy exposures.

We focus our analysis on three core strategies with distinct return drivers – Equity Hedge, Global Macro, and Relative Value – excluding Event-Driven<sup>5</sup> and Funds of Funds<sup>6</sup>. These categories form the universe for designing portfolios tailored to specific investor objectives later.

While various single and multi-factor models have been proposed <sup>7</sup> in academic studies to explain hedge fund performance, a consensus remains elusive given the diverse strategy universe. With our analysis focused on Equity Hedge, Global Macro, and Relative Value categories, we employ two complementary models aligned with their specialised exposures:

Axioma Equity Factor Model<sup>9</sup>: Captures key stock market dynamics for equity-centric managers.

Deutsche Bank Macro Factor Model<sup>10</sup>: Encompasses macroeconomic and policy drivers traded by macro specialists.

We employ a stepwise regression framework to estimate exposures, treating fund returns as the dependent variable and factor returns as independent variables in a linear model. The equation takes the form:

$$
\begin{array} { r } { r _ { t } = \alpha + \sum _ { k } \beta _ { k } f _ { t , k } + \varepsilon _ { t } } \end{array}\tag{1}
$$

Where, $r _ { t }$ is the return of the fund, $f _ { t , k }$ is the return of factor 𝑘 , $\beta _ { k }$ is the exposure (aka Beta) of the fund to factor 𝑘 , $\varepsilon _ { t }$ is the fund residual return and 𝛼 (aka Alpha) is the return of the fund net of the factors.

## 3.3.1 Equity Hedge Exposures

We begin by analysing Equity Hedge exposures using the Axioma equity risk factors. Figure 16 shows the volatilityadjusted average exposures <sup>11</sup> of each sub-category inside Equity Hedge to the Axioma equity factors.

On aggregate, Equity Hedge funds exhibit significant market exposure and favour stocks with smaller market capitalisation, higher volatility, cheaper valuation, higher earnings growth, and stronger one-year performance.

That said, Equity Market-Neutral funds differ significantly, with lower market and style factor exposures than all other sub-strategies. Their market exposure is also lower than their total style exposure, contrasting other subgroups. This aligns with market-neutral funds targeting alpha generation with minimal broad market exposure.

Figure 16: Average factor exposures (vol. adjusted)
![](images/c2cad1d62f857383a655f9e3a78f205babfc8951cdeb74ee3851ef18b82bd7f0.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

To simplify our analysis and maintain analytical depth, we segment Equity Hedge into Equity Directional (four directional sub-strategies) and Equity Market Neutral. This segmentation reduces congestion as we examine exposures over time.

Following the analysis of aggregate exposures, we now delve into their temporal variations, uncovering additional insights. Funds adjust exposures dynamically, responding to evolving expectations, environments, and opportunities rather than rigidly adhering to static rulesbased strategies.

For example, Figure 17 illustrates equity directional funds average style factor exposures over time, revealing regime-dependent fluctuations in market and style exposures. Similarly, Figure 18 portrays equity marketneutral funds' exposures over time, showcasing the dominance of styles in most periods, with a recent growth in market exposure.

Figure 17: Factor exposures: Equity market directional funds
![](images/a873fa5bde5cd675fa3ce6ae3a3518c20bb1470cae7a7bc7a62822566f3e0d24.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

Expanding on the time-varying exposure analysis, we now examine how alpha, capturing returns from manager skill beyond Axioma systematic factor exposures, has changed over time. As depicted in Figures 19 and 20, both market-neutral and equity-directional strategies exhibit a steady multi-year decline in alpha. This trend indicates a deteriorating environment for generating outperformance through active management, even across strategies with distinct factor profiles and exposures.

Figure 18: Factor exposures: Equity market neutral funds
![](images/cce45ee00daa775aa5d6961d5fada9547c4548d09dab6d22ac0f82ed26a4ba92.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

Figure 19: Average alpha: Equity market directional funds
![](images/04d250b48c7924df392d55da84ef5f5db54b2d2d3a641762d8366c3862db54a1.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

Figure 20: Average alpha: Equity market neutral funds
![](images/842dd8e5c71b06b8b9d82f424389abe79a5bc736dd095e47cd6ff360ae182263.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

## 3.3.2 Global Macro Exposures

Having explored Equity Hedge, our analysis now shifts to Global Macro strategies, examining exposures through our macro risk factors. Figure 21 outlines average exposures across various Global Macro sub-strategies, revealing distinctive patterns.

Systematic diversified, discretionary thematic, and multistrategy funds have exhibited net positive exposure to equities, duration, energy, and precious metals over time, which is unsurprising given that these exposures have generally paid off over the sample period. In contrast, FX funds — both discretionary and systematic — have been generally uncorrelated to these factors, given their focus on a different asset class.

Figure 21: Average factor exposures (vol. adjusted)
![](images/73ac26a2f5944ac4e6812cca0ed84d7867e21153ce1b27d5cdedf5b8723a3926.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

Figure 22: Factor exposures: Global macro funds
![](images/55986332df69eca20f5a2bb45a1a2e6d7e9fa76d158f49e8190f64204fde5e62.jpg)
Source: Deutsche Bank, Bloomberg Finance LP. HFR

The temporal analysis in Figure 22, which focuses on the aggregate Global Macro category, further confirms this pro-cyclical exposure over time, as witnessed through a number of risk factors. That said, bond exposures also saw a considerable increase post-2014, which we attribute to the rising influence of central bank policies on cross-asset volatility and correlations.

Mirroring the trend within Equity Hedge, Global Macro strategies experienced a steady decline in alpha generation (Figure 23). This diminishing alpha reflects a challenging return environment for active management despite Global Macro funds' flexible risk positioning and tactical dynamic adjustments to market conditions.

![](images/a078d67c14563169afc0e085be566c92bea6350cee06b4e808ced4f3fdce8599.jpg)

## 3.3.3 Relative Value Exposures

Transitioning from Global Macro analysis, we now examine Relative Value strategy exposures through the lens of our macroeconomic risk factors. As Figure 24 illustrates, distinct patterns emerge across various substyles within this diverse strategy.

Figure 24: Average factor exposures (vol. adjusted)
![](images/5353d979edd6e97d97a4373a864e6450337238d3dd0b2157a4d320a76049e5d5.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

Broadly, Relative Value funds demonstrate positive correlations with growth, inflation, EM FX, credit, and duration factors. Drilling down, however, sub-strategies orient along specific exposures mirroring underlying instruments and approaches - Fixed Income Sovereign/Convertible Arbitrage funds favour inflation and duration while Asset-backed/Corporate substrategies, targeting structured products and corporate bonds, exhibit larger credit factor affinity. As expected, Volatility and Multi-Strategy funds capture more episodic idiosyncratic returns evidenced through relatively muted systematic factor linkages.

Time series analysis (Figure 25) further emphasises this dynamic behaviour. Before 2008, minimal market connections existed, suggesting strategies primarily harnessed idiosyncratic forces. However, factors intensely spiked during the Global Financial Crisis, remaining elevated for years due to crisis aftershocks and opportunistic strategy expansion. This elevated exposure moderated with market stabilisation but resurfaced during recent crises. This profile supports an opportunistic strategy, substantially increasing exposures and risk budget amidst periods of market dislocations while contracting leverage during relatively calm regimes to isolate alpha.

Finally, Figure 26 paints a familiar picture of steadily declining alpha within the Relative Value universe. This downward trajectory underscores the need for meticulous fund selection as alpha generation becomes increasingly scarce.

Figure 25: Factor exposures: Global macro funds
![](images/3e324bf5b71aa2f0fd5bfaf7a9054af42660f779f90185e6c70e50aee28c5670.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

Figure 26: Average alpha: Relative Value funds
![](images/1d79e0e29d473f4bacebc22b821ad78c1da613416e498eb005c670e43635b8d3.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

With hedge fund exposures to systematic risk factors analysed extensively, as well as historical alpha trends examined, we next evaluate whether past topperforming hedge funds persistently outperform going forward or instead regress toward the mean—seeking to quantify true manager skill versus luck.

## 3.4 Hedge Fund Performance Persistence Analysis

We now focus on performance persistence, crucial for distinguishing between durable manager edge versus temporary luck. This analysis directly tackles the pivotal question of genuine differentiation in hedge fund outcomes over long horizons.

To evaluate performance persistence, we follow a fourstep approach:

1. We analyse Sharpe ratios for hedge funds over 1-to 5- year historical trailing windows.

2. We rank funds by Sharpe ratios calculated over a specific lookback period.

3. We re-rank funds based on actual Sharpe ratios from the subsequent one-year period.

4. Finally, we estimate rank correlations between the initial and subsequent fund rankings.

In this setup, correlations near 1 indicate stability in performance rankings, while lower correlations point to an increased reshuffling of ranks. Overall, more persistent funds demonstrate skilled rather than lucky return generation.

Figure 27 displays the rolling rank correlations using 1- year (short-term) and 5-year (long-term) lookback windows for estimating initial Sharpe ratios. Figure 28 then summarises the average rank correlation and standard deviation across the different potential evaluation periods, spanning 1-to-5 year lookback windows. We observe the following:

Moderate average rank correlations exhibit a degree of return consistency - funds initially highly ranked based on historical risk-adjusted returns tended to maintain their standout performance standings over subsequent periods. However, specific periods with negatively correlated values definitively indicate prior return hierarchies can completely invert at times.

Encouragingly, rank correlations only marginally differ between short-term and long-term evaluation windows. This finding reduces result sensitivity to the precise historical window periods used to estimate initial relative performance rankings.

The rank correlation metrics from short-term trailing windows demonstrate higher volatility and variability. This provides helpful adaptability in rapidly evolving market conditions compared to more stable but slower-moving metrics from longer-term windows.

Figure 27: Rank correlations over time
![](images/95cc54816594f83d07965a69ea7d1d35ec08dd065718f3427088a4e338140cb4.jpg)

![](images/4cf8ff47d6402c137f5c03622f4629ad662f2f9da71af2ff92294aac2a42b3d3.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

With analysis revealing some persistence in hedge fund performance, we incorporate both long-term and shortterm performance metrics within our fund selection framework (detailed in Section 4). This facilitates optimally ranking funds for portfolio inclusion.

Next, we tackle a key consideration in portfolio construction - determining the ideal number of funds to own for an efficient, diversified hedge fund allocation. Adding too few managers risks concentration while excessive diversity can dampen returns. We analyse this tradeoff next.

## 3.5 Determining the optimal number of hedge funds

After evaluating consistency in hedge fund performance over time, we now determine the optimal number of funds - the right fund count selection - for building an efficient and adequately diversified portfolio.

The fund count serves several critical purposes: efficiently diversifying manager risk, avoiding overdiversification that erodes returns through fees, enabling meaningful capital allocation, meeting due diligence bandwidth, and balancing volatility with return consistency.

In the search for optimal fund count, our methodology evaluated portfolios across the 1 to 100 fund range through simulation. The key steps are:

Simulate portfolios holding between 1 to 100 funds by incrementally increasing the number of equally weighted funds per portfolio.

For each portfolio size point, randomly sample and evaluate 1,000 different fund combinations to minimise results relying on specific manager selections.

Keep individual fund weighting fixed at equal notional allocations rather than optimising weights.

Assess the impact of increasing the number of funds on key portfolio metrics, including returns, volatility, risk-adjusted ratios, drawdowns, etc.

The simulation process provides an unbiased view into incremental benefits from further portfolio diversification by adding funds beyond minimising manager-specific risks. The results will reveal where marginal improvements diminish, finding the sweet spot between concentration risks and over-diversification.

Indeed, the results in Figure 29 indicate diversification gains diminish beyond around 20 funds, with minimal efficiency upside for larger portfolios. This aligns with our principal component analysis finding circa 25 funds explain most strategy variations.

Figure 29: Average Sharpe ratio of randomly selected funds
![](images/e03bdecd17f07a975c0e408bfbc9d08db7dbfcf263b72c4e8bd5dd5d5e54c4f6.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

In essence, hedge fund allocations beyond 20-25 funds seem to offer very limited diversification upside. As we advance in our analysis, we will utilise this empirically validated range as a starting assumption for an optimally sized portfolio, but it may vary based on strategy mix and homogeneity.

Having explored performance intricacies, persistence, and optimal hedge fund portfolio scale, we now transition to demonstrating a quantitative approach for constructing customised portfolios to meet specific investor objectives.

## 4. Building a fund of Hedge funds

This section introduces a quantitative framework for constructing hedge fund portfolios tailored to specific investor goals. We focus on two goals: a market-neutral portfolio, covered in Section 4.1, and a convex portfolio, covered in Section 4.2.

## 4.1 Market-neutral portfolio

We define the market-neutral portfolio as one striving for consistent performance across various macroeconomic scenarios, specifically focusing on the four growthinflation combinations resulting in reflation, recovery, stagflation, and recession periods. These regimes are delineated using a median split on monthly returns for the DB Macro growth and inflation factors<sup>12</sup> in alignment with our prior framework<sup>13</sup>.

For example, the reflation scenario encompasses all periods where returns for both the growth and inflation factors exceed their historical medians, indicative of concurrently expanding demand and prices. The marketneutral mandate involves balancing exposures to mitigate risks from shifting cycles between these varying growth/inflation paradigms over long horizons.

As per earlier analyses (Section 3.3 onwards), our hedge fund universe spans three categories: Equity Hedge, Global Macro, and Relative Value strategies. Building on Section 3.5’s size optimisation, we construct a 21-fund portfolio, effectively selecting 7 funds from each of the three core strategies to ensure robust strategy diversification<sup>14</sup>.

Next, with funds segmented into strategic buckets, we detail our process for data-driven selection and iterative reviews, enabling adaptation to changing market conditions over long horizons.

## 4.1.1 Selection of funds

Within each strategic hedge fund bucket, we systematically select managers by applying the following structured process every six months at scheduled portfolio rebalancing dates:

## Step 1 - Initial fund screening:

We begin by screening active funds based on two criteria:

Criterion 1: We reject the funds whose stressed Sharpe ratio (SSR) does not test significantly positive in any of the four growth-inflation scenarios up to the rebalancing date. The SSRs are defined using scenario-based factor beta sensitivities<sup>15</sup>, as opposed to just empirical return observations, to isolate regime dependencies and reduce false positives. In essence, qualifying funds should not have negative expectancy in the macro regimes covered.

Criterion 2: We reject funds with either negative or statistically insignificant (p-value exceeding 10%) alpha estimates from model regressions (Axioma equity factors for Equity Hedge, DB macro factors for Global Macro and Relative Value). Qualifying funds exhibit an edge in producing positive idiosyncratic returns unexplained by systematic risk factors.

## Step 2 - Performance ranking:

Having identified qualified funds demonstrating scenario efficacy and positive alpha significance, we now progress to select the highest potential funds across each core strategy for inclusion in our portfolio.

Specifically, and in line with Section 3.4, we rank the qualified funds based on the following metrics:

Short-term: Sharpe and Sortino ratios evaluated over 1 year,

Long-term Sharpe, Sortino, and Omega <sup>16</sup> ratios evaluated over 5 years,

<sup>▪</sup> The alpha p-value from the risk factor model.

We then combine these rankings with varied weights<sup>17</sup> to obtain a final aggregated ranking of qualified funds.

## Step 3 - Fund Selection:

With the combined rankings of funds within each main strategy group, we now select the top seven funds within each group to construct a strategy-specific portfolio. The choice for seven may look arbitrary, but it is intuitive; it combines the optimal fund count analysis from Section 3.5 with our aim to have each category – Global Macro, Equity Hedge and Relative Value –equally represented.

## Step 4 - Capital Allocation:

Having identified the top funds within each sub-strategy, we turn to the crucial step of capital allocation. Our key objective is to construct balanced portfolios by distributing capital based on measured risk exposure. This approach complements our fund selection process, which prioritises return potential.

Specifically, within each sub-portfolio, capital is allocated across funds inversely proportional to long-term volatility estimates <sup>18</sup> . This means funds with lower historical volatility receive a larger share of capital.

Also, we didn’t integrate correlations directly at this stage as its dynamic and fast-evolving nature could spur unnecessary turnover. However, the rigorous selection process indirectly accounts for correlations through metrics assessing risk-adjusted returns across environments.

Next, we discuss our fund review process, which is as critical as our fund selection process since it enables us to adapt our approach depending on shifting market conditions.

![](images/542cdc2e7c52558c4f8b2ba45564535b1f6da05983bf65838701eba888458f5a.jpg)
Source: Deutsche Bank

## 4.1.2 Rebalancing Process

To maintain the market-neutral portfolio's robust performance and consistent macro regime resilience over long investment horizons, we follow a structured rebalancing process to replace funds no longer qualifying or consistently underperforming peers regularly. The specific rebalancing steps, conducted every 6 months in line with the portfolio review schedule, are:

Rerun the fund selection algorithm (outlined in Steps 1-3 earlier) to identify the latest pool of top 10 qualifying funds across each strategy bucket, demonstrating both statistical efficacy and strong risk-adjusted returns based on updated data.

Compare the newly selected funds against existing market-neutral portfolio holdings, retaining current funds in the latest selection list to provide continuity.

Individually review non-overlapping existing funds, replacing them with higher-potential funds from the new selection list if:

Fund is inactive, liquidated or discontinued operations.

<sup>▪</sup> Fund no longer passes scenario efficacy or alpha significance criteria.

Fund remains statistically qualifying, but its recent short-term performance is negative and falls below the 50th percentile of peers.

This dynamic rebalancing process, introduced to adapt to evolving market conditions and the hedge fund universe, ensures the portfolio's adaptability and ongoing robustness. Figure 30 summarises the end-to-end construction and rebalancing methodology.

## 4.1.3 Backtesting and results

We conducted a backtest analysis to quantify the historical performance of our market-neutral portfolio of hedge funds.

We initiated the fund selection process in January 2001 and periodically reviewed the portfolio every six months. As mentioned in Section 2.3, we included both active and inactive funds in our backtesting process. Moreover, we also filtered out the funds whose notice period was more than 30 days, and the lock-up period was more than 6 months<sup>19</sup>.

The in and out funds charges (or fund swing pricing) are not given in the HFR database, so we have assumed a rebalance cost of 20 basis points in this exercise. We acknowledge that swing prices vary across funds and can impact performance. However, our primary focus here is to demonstrate the effectiveness of our fund selection framework.

Employing our fund selection framework, we built three distinct market-neutral sub-portfolios, and then, utilising a clustered-based risk-parity approach, we aggregated them together to construct the final 21-fund portfolio of hedge funds.

Figures 31-38 illustrate our backtest results, whose main conclusions are as follows:

## Historical performance

All 3 sub-portfolios and the aggregate portfolio delivered an attractive return trajectory since 2001 inception per Figures 31 and 32, despite drawdowns for the Equity Hedge and Relative Value buckets isolated to the 2020 COVID crash and 2008 global financial crisis periods, attributable to their long-term growth market exposure.

Additionally, Figure 33 illustrates resilience across growth/inflation regimes over the backtest timeline. Furthermore, it merits highlighting that the lower monthly reporting frequency dampens some short-term shock visibility, partially contributing to the smoothed performance profiles observed.

Figure 31: Performance of market-neutral hedge fund sub-portfolios
![](images/d591e98c54fa6496897c13735cc48defc650ee1bdbc1c4dafcb41f8fdd16a104.jpg)

Figure 32: Performance of market-neutral HF portfolio
![](images/ef5f75be019e57d049b961dd42db49f397f98648e4c9e55b98f753dc5a6ba099.jpg)

Figure 33: Performance of the HF market-neutral subportfolios and the combined portfolio across growthinflation scenarios
![](images/6665ca91e20b99bb0b5397535bc770c9709e2e47f775c97ed7b4aba772316083.jpg)

## Relationship among sub-portfolios

The long-term correlation between Equity Hedge and Relative Value sub-portfolios is \~62%, while their correlation with the Global Macro sub-portfolio is \~3.5%. This observation suggests that similar factors drive Equity Hedge and Relative Value market-neutral funds over the long term, but then it raises the question of whether it is consistent over time or episodic.

To understand that, we estimated the pair-wise correlations between three sub-portfolios over time (Figure 34) and found that, on average, their correlations are \~15%, which suggests that Equity Hedge and Relative Value do not exhibit higher correlation consistently over time.

However, we observed that they show a higher correlation at tails, especially during the 2008 GFC and 2020 COVID crises. Figure 35, showing their relationship with global equities, further supports this point that Equity Hedge and Relative Value funds are driven by a common factor during crises.

It is not unintuitive as we understand that hedge funds are known for tail risk exposure, which we have attempted to alleviate through our fund selection framework but haven’t eliminated. Figures 33 and 36 also show that the aggregated fund suffers at the left tail, while it has a very low correlation during normal market conditions.

Later in Section 5.4, we will show how we can improve hedge funds portfolio’s tail behaviour through QIS.

Figure 34: Sub-portfolios’ relationship with equities
![](images/392ffb86035660342355b4ffb985405c4ce9b910c000ea48e0b068294ad21d84.jpg)

Figure 35: Sub-portfolios’ relationship with equities
![](images/753e50345a898b3bce8aad9d4ef0e0108d05132c58b79537bb9e62d2fddd73c5.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

Figure 36: Market neutral portfolio vs MSCI World equities
![](images/57ec8084109f9dfe704036d1f8e305f64d4f5bf9486fe70d3f4d33621574291e.jpg)

## Portfolio size over time

We initiated the fund (in January 2001) with 21 managers in the portfolio. In this analysis, we aimed to keep the same number of funds throughout the backtest period. So, at every review date (six monthly in this study), we replace funds, if needed, with new ones so that the total fund size remains at 21.

Figure 37 shows the number of funds and the percentage of active funds that have satisfied our selection criteria – positive significant SSR across growth-inflation scenarios and positive significant alpha. It shows that the number of qualifying funds has declined over the years, which is in sync with the declining alpha trend (as depicted in Figures 20, 23, and 26). So, it means that over the years, it has become challenging to identify funds that show resilience across market conditions.

## Portfolio new funds turnover

We also looked at the progression of new funds added to the hedge fund portfolio at each review date, as shown in Figure 38. It shows that the percentage of new funds added to the portfolio remained below 20% on average, with more fluctuations around 2008 and the 2020 COVID crisis. This is mainly because many hedge funds either didn’t pass the selection criteria or got liquidated, indicating that funds deviate from their profile (market neutral in this case) during market regime shifts.

Figure 37: Progression of the number of selected active funds
![](images/092d89157456f9648867071c274ecc2a5bdbd5322cd7b6ff75eb5f6690d5d89b.jpg)

Figure 38: Progression of addition of new funds
![](images/84c3ccce700ce8bbd3994054865e402cc995575a6c8985c4f026107097717afb.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

## Prevalent strategies

We also analysed the prevalent strategies within each sub-portfolio. Equity Market Neutral funds featured most in the Equity Hedge portfolio, Multi-strategy funds prevailed in Global Macro, and Fixed Income – Asset Backed led in the Relative Value category. This finding is intuitive as these sub-strategies are expected to be resilient in diverse macro scenarios and comforting at the same time as well, as it implies low model risk.

## Performance benchmarking

We analysed whether our optimised hedge fund selection and rebalancing methodology provides consistent valueadd versus simply allocating across random manager combinations without structured rules.

To quantify this, we built 100 random hedge fund portfolios as per the following steps:

1. For each sub-category, initiate a portfolio by randomly selecting 7 funds from that category.

2. Build the aggregated portfolio by combining three sub-portfolios through cluster-based inverse volatility weighting.

3. Review funds in the portfolio semi-annually and replace them if they are inactive.

Figure 39 (top chart) depicts the performance curves of all 100 random hedge fund portfolios alongside the highlighted performance curve of the market-neutral portfolio. This allows for a clear comparison of their trajectories.

Figure 39: The market-neutral portfolio vs 100 random hedge fund portfolios
![](images/0d27b1e3d52156bd793c0c8efeb981ce1864b6936d8c45ed3175edcaf0f0a82a.jpg)

![](images/a999871cff7fc7d801bd77752984891f78d59265613d09c34163b30ea7fe7724.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

Overall, the market-neutral portfolio outperformed the average random portfolio, with its long-term CAGR and risk-adjusted return placing it at the 86th and 100th percentiles, respectively. However, as Figure 39 (top chart) shows, its relative performance fluctuates over time.

Figure 39 (bottom chart) further reveals the marketneutral portfolio’s return percentile relative to these 100 random portfolios over time. Notably, it underperformed in 2004 and 2011 but outperformed in 2009 and also post 2015 onwards. Nevertheless, the results suggest that the selection rule does add value in designing a marketneutral portfolio compared to a randomly constructed one.

In conclusion, this analysis validates that structured funds selection and proactive reviewing can consistently improve portfolio performance and risk-adjusted returns relative to random manager selection processes without structured rules.

Next, we move to build a diversified convex portfolio of hedge funds.

## 4.2 Convex portfolio

Expanding on the market-neutral portfolio construction methodology, we now detail the steps for building a defensive-focused portfolio of hedge funds. The objective is to provide a cushion during equity market drawdowns without sacrificing returns under normal market conditions.

As with the market-neutral portfolio, the fund universe consists of Equity Hedge, Global Macro and Relative Value strategies. We opted to draw from the full range of strategies rather than limit ourselves to a narrow subset, using our selection algorithm to filter for those meeting the defensive criteria.

## 4.2.1 Selection of funds

We now outline the steps for selecting funds for the defensive portfolio:

## Step 1 - Initial Fund Screening:

We start by screening active funds across Equity Hedge, Global Macro, and Relative Value funds at the rebalance date with three criteria tailored to capturing defensive properties. These are:

Criterion 1: We reject funds without a significantly positive scenario-specific Sharpe ratio (SSR) in either of the falling growth scenarios - Recession or Stagflation.

Criterion 2: We reject funds lacking a significantly positive SSR spread, estimated by taking the differential between the SSRs of the declining growth scenarios and their opposite counterparts<sup>20</sup>.

Criterion 3: We remove funds without a significantly positive alpha (estimated per Equation 1). This ensures non-negative return potential under normal market conditions, enhancing overall portfolio attractiveness.

## Step 2 - Performance Ranking:

After filtering for funds exhibiting the required defensive properties and alpha significance, we select from those a subset to include in our portfolio.

The qualified funds undergo ranking based on the following:

Returns and return spread during recessionary and stagflation scenarios - prioritising strong downside mitigation during equity drawdowns

Alpha p-value significance from the applied risk factor model - emphasising consistency of outperformance

These rankings receive equal weighting in a composite score used to rank the eligible funds. This process

culminates in a final performance-ranked list of defensive funds eligible for portfolio inclusion.

## Step 3 - Fund Selection:

With the combined performance-ranked list of qualified defensive funds, we now select the top ten funds to construct a final defensive portfolio.

The allocation to ten funds aligns with the size analysis conducted specifically for defensive hedge fund portfolios (similar to Section 3.5). Limiting to ten funds enables an appropriately sized portfolio whilst ensuring quality, given the number of funds remaining after the initial qualification screening.

## Step 4 - Capital Allocation:

The top ten selected defensive funds receive capita allocations inversely weighted to their trailing long-term volatility estimates.

Allocating based on inverse volatility balances both return enhancement and risk mitigation objectives. Higher volatility funds may provide greater convexity during drawdowns but can also experience larger bleed. This would erode portfolio attractiveness over time. Lower volatility funds with significant alphas exhibit better bleed characteristics but become underrepresented without inverse volatility weighting.

Ultimately, inverse volatility weighting creates an optimal balance between return potential in declining markets and bleed risk across varying conditions for the overall portfolio. This approach aligns with the defensive portfolio objectives.

While more advanced capital allocation methodologies exist, the intent here is to demonstrate the efficacy of the selection framework itself. There remains an opportunity to optimise the allocation methodology further in future enhancements.

## 4.2.2 Rebalancing Process

To maintain the portfolio's robust defensive properties over time, we follow a rebalancing process, similar to Section 4.1.2, by replacing funds no longer qualifying or underperforming peers.

The rebalancing steps, conducted every 6 months, are:

1. Rerun the fund selection algorithm (Steps 1-3) to identify the current top 10 funds.

2. Compare new funds with existing holdings. Retain overlapping selections.

3. Review non-overlapping funds individually per the following criteria and replace them with the latest qualifying fund if:

<sup>▪</sup> Fund is inactive or liquidated,

Fund is no longer passing the initial criteria (Step 1).

Recent short-term performance is negative and falls below the 50th percentile of peers.

This semi-annual rebalancing approach, consistent with the market-neutral portfolio, preserves the integrity and resilience of the defensive fund portfolio over market cycles.

## 4.2.3 Backtesting analysis and results

Mirroring the process for the market-neutral hedge fund portfolio, we performed a backtest analysis to evaluate the performance of our defensive portfolio. The fund selection process was initiated in January 2001, with periodic reviews and rebalancing conducted every six months.

We utilised the same assumptions around transaction fees, redemption notice periods, and lock-up terms as implemented in the market-neutral portfolio backtest for consistency.

Over the 21-year backtest, the portfolio yielded a 7.1% CAGR at 4.8% volatility, resulting in a 1.48 risk-adjusted return ratio. This significantly outpaced the CTA benchmark in both absolute and risk-adjusted terms (Figure 40).

Figure 40: Performance of the HF defensive portfolio and a CTA benchmark
![](images/398488bc2e968c34b28ef0dabd4e4851fbd6e22b170e0b993234d123e8c9d285.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

Further analysis confirms the portfolio’s defensive properties:

Demonstrated resilience during market drawdowns while limiting bleed during normal conditions (Figures 41, 42)

Outperformed the benchmark in recessionary/stagflation scenarios while generating higher total returns (Figures 41, 42)

Figure 41: Performance across growth-inflation scenarios
![](images/3a1aecdc04cc2c6ab835540d27019fc1f014aab84608e292ea0f7d348353a8ea.jpg)

Figure 42: Portfolios’ relationship with equities
![](images/45555daa7d4c069b1ef0ca88dcec5e759543a7bd0dc0e7342789176086999dff.jpg)

Analysis of the prevalent strategies selected reveals that Systematic Diversified (CTA) strategies were most commonly chosen within Global Macro, while Equity Market Neutral and Short-Bias funds dominated Equity Hedge selections. Meanwhile, Relative Value exposure came largely from Volatility, Multi-Strategy, and Fixed Income Asset-Backed funds. This is logical, as Systematic Diversified, Equity Short-Bias, and Volatility strategies explicitly target defense. Equity Market Neutral and Multi-Strat offset the bleeding risk of those defensive strategies, improving the portfolio’s overall risk-return profile.

The defensive portfolio exhibited a higher average new fund turnover of 44% - much higher than the marketneutral portfolio (less than 20%), as shown in Figure 43. This increased replacement rate arises from incorporating alpha as a fund selection factor, which was intentionally included to improve the portfolio's bleed profile over market cycles.

Figure 43: Progression of addition of new funds
![](images/1c0a3f3611dc0cb464ed8a420f2a35f8aae74cfe16ad01c3a113d83cb0a513d8.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

## 4.2.3 Convex portfolio: other variations

However, while beneficial in offsetting bleeding risk, the higher turnover contributes to greater maintenance costs over time. So, to analyse this tradeoff, we conducted an analysis removing alpha from the fund selection criteria and reran the portfolio construction exercise. This reduced average turnover to 16% but led to a far worse bleed profile, resulting in a 0.4% CAGR over the backtest horizon at a 17% volatility (Figures 44 and 45).

![](images/de45c5a38da74d40a9da97735974667983359159a4f1206990b1997d12e5e124.jpg)

This solution is optimal for investors solely seeking an equity hedge without regard for "bleed" risks. However, cheaper and more transparent alternatives exist. Our Defensive CTA strategy <sup>21</sup> (BBG ticker: DBCOREGU Index), buying/selling assets that reduce equity market risk, provides similar protection.

Figure 45: Portfolios’ relationship with equities
![](images/b33b979f8f1f9ea22e153a952b99eddbd792bc70232bfc73711b139fe3438304.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

Figure 46 compares the two portfolios, revealing a progressively stronger relationship, particularly during stress episodes. Their long-term correlation is 70%.

Figure 47 plots their relationship with equities. Notably, the Defensive CTA strategy (vol-matched) exhibits a nearly identical risk-return profile and equity drawdown cushioning as the alpha-removed defensive portfolio.

In conclusion, for investors solely prioritising equity drawdown mitigation without bleed concerns, cheaper and more transparent hedge portfolios exist, like our Defensive CTA index.

However, for investors focused on balancing both drawdown resilience and bleeding across varying market cycles, the alpha-enhanced defensive portfolio achieves both aims more comprehensively, albeit with higher maintenance costs.

Figure 46: Performance of the CTA benchmark and HF CTA portfolio
![](images/37065f491cf007e14295311a47574b927a5920c7e2c5ad8a3acbd3a13f9f7e66.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

Figure 47: Portfolios’ relationship with equities
![](images/bd3ba534180f9d9eb6c342c5652d92ca026d5bc2b14cf1d48420966932727835.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

In summary, this section presents a structured process for building hedge fund portfolios tailored to investor objectives. Two examples—market-neutral and convex portfolios— demonstrate the framework’s adaptability across diverse investment goals. This approach facilitates efficient access to the hedge fund universe, allowing investors to capitalise on return potential while mitigating risks.

The subsequent section delves into the dynamic interplay between hedge funds and Quantitative Investment Solutions (QIS) strategies, offering insights into their complementary roles within portfolios, which can be blended to enhance overall portfolio efficiency.

## 5. Hedge funds vs QIS strategies

Having demonstrated the construction of hedge fund portfolios tailored to investor goals, the focus now shifts towards understanding the distinctiveness of hedge fund alpha over transparent, liquid Quantitative Investment Solution (QIS) strategies.

In a financial landscape, where costs are deterministic and returns are stochastic, systematic QIS strategies, recognised for their cost-effective factor exposures, prompt a fundamental question: How do hedge funds, renowned for their high fees, contribute beyond these strategies in a portfolio context?

This section tackles assessing hedge funds’ value-add versus QIS alternatives through two approaches:

1. Regressing net-of-fee hedge fund returns against investable QIS benchmarks now incorporated into risk models to quantify excess alpha.

2. Constructing a resilient multi-scenario hedge fund portfolio and comparing its performance to the market-neutral allocation previously developed in Section 4.1.

Together, these analyses quantify the excess return edge of various hedge fund strategies versus QIS strategies available at fraction-of-cost. We also discuss how certain QIS strategies may serve as valuable complements alongside an existing market-neutral hedge fund allocation, improving portfolio resilience across environments.

Our Quantitative Investment Solutions (QIS) universe encompasses more than 40 independent return streams across diverse asset classes and strategy types (Figure 48).

Figure 48: Overview of our comprehensive offering across styles and asset classes
<table><tr><td></td><td>Value</td><td>Ccary</td><td>onnnum</td><td>Volitity</td><td>Idosatic</td><td>Smat Bmaeta</td><td>Hen</td></tr><tr><td>Equities</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>Rates</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>Commodities</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>FX</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>Credit</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>Inflation</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr></table>

Source: Deutsche Bank, Bloomberg Finance LP.

While it's mathematically feasible to incorporate all these strategies into the risk factor model, doing so introduces the risk of overfitting and generating unreliable estimates. Therefore, to ensure the robustness of our analysis, we choose to reduce dimensionality. In simpler terms, we aim to categorise the QIS strategies into distinct clusters for inclusion in our risk factor models.

In the subsequent section, we elaborate on how we construct sub-portfolios of QIS strategies, which play a crucial role later in estimating hedge funds' alpha and complementing a market-neutral hedge fund portfolio.

## 5.1 Constructing representative QIS sub-portfolios

Traditionally, QIS return streams are categorised into three segments – defensive, market-neutral, and procyclical – aligning with different parts of the core portfolio's distribution. The defensive focuses on the left side, market-neutral on the middle, and pro-cyclical on the right side.

An alternative approach to classifying QIS strategies leverages data-driven hierarchical agglomerative clustering tailored to our focused universe under consideration<sup>22</sup>.

Rather than relying solely on default correlation-based clustering, this specialised workflow groups strategies exhibiting similar performance behaviour across macro environments instead of just pairing on static correlations. We quantify similarity through regime-based analysis focusing on sensitivity to core factors - economic growth, inflation, and interest rates.

Specifically, we estimate scenario-specific strategy returns across varying environments per the robust methodology detailed in Anand (2020) and summarised in Footnote 15. Strategies clustered together indicate consistent outperformance or underperformance specific to certain economic regimes based on their responses to prevailing risk factor movements.

By linking correlated outcomes to risk exposures under different scenarios, this approach circumvents limitations of tracking unstable inter-strategy correlations across cycles. The similarity metric underpins consistent clustering aligned to performance under forward-looking conditions.

Figure 49 depicts the output clusters that emerge from the algorithm - pro-cyclical, balanced (or market-neutral), and defensive. As hypothesised, the data-driven clusters align broadly with the conceptual style categories of traditional classification frameworks, providing some model validation.

Specifically, VRP strategies across equities, commodities and rates, FX carry, and credit curve form the pro-cyclical cluster given their positive correlation to steadily growing environments.

Market-neutral strategies, such as commodities risk premia and equity long/short, emerge as an independent cluster given their structural indifference to growth cycles or the rate environment.

Finally, strategies exhibiting defense in downturns while tolerating relative underperformance in rallies, like trendfollowing, long volatility and FX value strategies, form the defensive cluster.

Figure 49: Dendrogram showing the hierarchical clustering of QIS strategies
![](images/7dd0206174fd9336626b9c34147441f5024d3a35aa329ac2c823f6f56fc40c28.jpg)
Source: Deutsche Bank

Next, we select strategies in these three buckets. However, we avoid relying solely on clustering outputs, recognising that this default choice may not be optimal, as it overlooks the significance of similarity measures and fails to account for false discovery.

Instead, we employ a basket selection methodology introduced by Anand (2021) based on the following steps:

1. Evaluate scenario-specific Sharpe ratios (SSR) for each strategy to assess their factor sensitivity and return efficiency across different environments.

2. Filter strategies exhibiting significantly positive SSRs specifically for the scenarios most relevant to a given basket's objectives:

Pro-cyclical: Reflation, Recovery and positive equity/bond return scenarios.

Defensive: Recession, Stagflation and negative equity/bond return scenarios.

Balanced basket: All scenarios implied from growth and inflation, and equities and bonds.

3. To further ensure consistency within Pro-cyclical and Defensive baskets, we filter out strategies with a significant positive spread between their SSR in target market scenarios and their opposite environments. This step helps eliminate strategies that qualify for inclusion incidentally.

These steps provide an initial list of qualifying strategies; however, we apply a discretionary overlay to refine the list based on expert judgement, considering factors not captured by the quantitative process.

Following the outlined selection methodology, we choose strategies for the three baskets, categorised as follows:

<table><tr><td colspan="3">Figure 50: Basket constituents</td></tr><tr><td>Market-neutral</td><td>Defensive</td><td>Pro-cyclical</td></tr><tr><td>factor portfolio</td><td>Equity dynamic multi- Equity Defensive Cash USD swaption VRP Factor</td><td></td></tr><tr><td>Equity cross-sectional Equity Dynamic reversion</td><td>Intraday Trend</td><td>SPX tactical VRP</td></tr><tr><td>Commodity Carry</td><td>Equity Dynamic long put option</td><td>Commodity diversified VRP</td></tr><tr><td>Commodities Curve</td><td>Commodity short-term FX carry trend</td><td></td></tr><tr><td>Commodity Congestion</td><td>FX Value</td><td>FX carry (cross currency)</td></tr><tr><td>Commodity Value</td><td>FX EM Tail Hedge</td><td>Europe long-term dividends</td></tr><tr><td rowspan="4"></td><td>Rates Breakout</td><td>Credit Curve - Main 5yr</td></tr><tr><td>momentum Rates Long Volatility</td><td>vs10yr Credit Carry (HY vs IG)</td></tr><tr><td>Credit long/short Hedge (CDX IG)</td><td></td></tr><tr><td>Cross-asset defensive CTA</td><td></td></tr><tr><td>Source: Deutsche Bank</td><td></td><td></td></tr></table>

Next, we combine these strategies into sub-portfolios using a cluster-based risk parity scheme. Figures 51-52 illustrate the unique return profiles of these QIS subportfolios.

The defensive sub-portfolio effectively shields against equity drawdowns with a negative market correlation. In contrast, the pro-cyclical basket provides diversified returns during market rallies, showing a positive correlation. Lastly, the market-neutral portfolio consistently generates returns across diverse macro environments, staying uncorrelated with the markets.

Figure 51: Performance of sub-portfolios
![](images/dd8fce1bf0d24922c62a24122a47e86b276cd8573dad8235b6f50d40888ce8e0.jpg)

Figure 52: Relationship with global equities
![](images/a27cdbc7f5a3d11d617132b8a788bf692a72dc52f6df8157d318b5cdf32a6e16.jpg)
Source: Deutsche Bank, Bloomberg Finance LP.

Building on our insights from constructing representative QIS sub-portfolios, we transition to examining hedge funds’ systematic alignments and idiosyncratic alpha generation potential after incorporating the QIS subportfolios as additional factors in the risk models.

## 5.2 Hedge fund factor exposures after incorporating QIS strategies

In this section, we quantify hedge fund exposures and alpha by regressing their returns against the aforementioned QIS sub-portfolios. Extending our equity and macro factor models involves incorporating three additional explanatory return streams - the pro-cyclical, market-neutral, and defensive QIS baskets detailed previously.

With these QIS sub-portfolio returns now included as additional factors, we re-estimate the regression model per Equation 1 to solve for the residual alpha and factor exposure coefficients, specifically measuring incremental exposures of hedge funds beyond these QIS building blocks.

Starting with exposures, Figures 53, 54, and 55 showcase the average volatility-adjusted exposures for Equity Hedge and Global Macro/Relative Value funds, revealing the systematic exposures upheld by hedge funds. Key observations include:

Equity Hedge funds display positive exposures to pro-cyclical sub-portfolios, primarily influenced by their net positive equity exposure.

Global Macro, particularly systematic diversified funds, exhibit positive exposure to Defensive subportfolios, highlighting their diversifying characteristics and resilience during stress episodes.

Notably, Relative Value funds demonstrate positive exposure to pro-cyclical and negative exposure to defensive QIS sub-portfolios. This suggests that under normal risk conditions, Relative Value funds tend to perform optimally.

Having analysed hedge funds' exposures to the QIS subportfolios, we now examine the impact of incorporating these QIS exposures on estimated manager alpha. Suppose QIS strategies significantly explain a portion of returns beyond what is already captured by systematic risk factors. In that case, the average alpha across strategies will decline in the enhanced model relative to the baseline.

Figures 56, 57, and 58 depict the average alpha across three main strategies, both with and without QIS subportfolios in the factor models.

Figure 53: Equity Hedge: Average factor exposures
![](images/3f4cf1e266ae8478cc734e645dc76ba8dd1c3a16d1ae591c32ade551ad41638a.jpg)

Figure 54: Global Macro: Average factor exposures
![](images/6726d0ee8ed4a6c62f24f6602704fa4ce7a94bf74d06d86e584ae90aeab51d68.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR

Figure 55: Relative Value: Average factor exposures
![](images/f3871111b5ef2d46b95d139ac2e52c44c7fb7ff256caac0c1ed0fe67c36f691c.jpg)

Figure 56: Equity Hedge alpha with and without QIS sub-portfolios in the risk model
![](images/d4ff61692ba4cd2451475aada9718c8e5e5824e7b71bdfda1183d0d2870af668.jpg)

While there is a consistent decline in alpha across categories, the average alpha does not show a significant difference between models. The progression of active funds with positively significant alpha follows a similar pattern (Figure 59), indicating that, on average, hedge funds deliver comparable alpha with or without QIS factors.

In essence, this suggests the QIS strategies provide limited marginal explanatory power for hedge fund returns above what is already captured by the original risk factors.

Figure 57: Global Macro alpha with and without QIS sub-portfolios in the risk model
![](images/a8e84b35247347e968daeec9392cf70c16fecfbbb9967ca92563aaa91a8f5e20.jpg)

Figure 58: Relative Value alpha with and without QIS sub-portfolios in the risk model
![](images/7a8c0563a800520eb82e259448150ac7866762ab5d8b153bdbb64b5c5f2fee62.jpg)

Figure 59: % of active funds with +ve significant alpha
![](images/cbf238c08a7c7a807141c09432687070316761a8b7c31aef179b57f5ddcfa100.jpg)

## 5.3 Hedge fund portfolio after incorporating QIS strategies

The above findings raise a logical follow-up question - how would incorporating QIS strategies impact hedge fund selection and resulting portfolio efficiency in our framework? The preceding findings reveal minimal alpha erosion after including QIS strategies in factor models. Therefore, we expect a similarly limited portfolio impact from this model alteration.

To quantify the effects, we reconstruct a hedge fund market-neutral portfolio per the framework in Section 4. However, instead of using the traditional multi-factor model<sup>23</sup> for alpha estimates, we now leverage the QISaugmented model, incorporating exposures to the procyclical, market-neutral, and defensive baskets as additional factors.

This reconstructed hedge fund market-neutral portfolio mirrors the performance of the previous version without QIS exposures (Figure 60) but posts a slightly higher riskadjusted return, indicating a marginal improvement in manager selection attributed to the inclusion of QIS exposures.

These findings suggest QIS exposures provide limited marginal explanatory power for hedge fund returns atop drivers already captured by the baseline Axioma or DB macro risk models. This raises a subsequent question - how might QIS strategies complement an existing hedge fund allocation?

We understand QIS offers efficient, low-cost factor exposures while hedge funds provide differentiated alpha potential. Yet, despite the ability to attributionally separate alpha and beta streams, these components cannot be isolated into long/short building blocks in practice. An investor cannot outsource only the beta exposure to QIS while retaining purely alpha from hedge funds. The solution lies in recognising their complementary strengths.

Blending hedge fund alpha opportunities with QIS’s inexpensive factor exposures can theoretically improve portfolio efficiency. This leads to the research question - for a given hedge fund allocation, what is the optimal QIS blend to maximise risk-adjusted return? The focus becomes supplementing, rather than replacing, hedge funds through integrated portfolio construction using both alpha-seeking and factor-based building blocks.

Figure 60: Portfolios built using QIS-augmented model vs original model
![](images/cf129da291295c9814c22862cc2a57c69978e6cd0357e5e31d7174082b9ce3a8.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

5.4 Integrating hedge funds portfolio and QIS strategies Having demonstrated the limited alpha impact of incorporating QIS exposures into hedge fund selection models directly, we next examine the potential for QIS strategies to complement an existing market-neutral hedge fund allocation.

However, for investors focused solely on constructing market-neutral or macro-agnostic portfolios fully from QIS building blocks, our methodology for aggregating the three QIS sub-portfolios into a standalone market-neutral allocation is detailed in Appendix I.

In this section, we focus on a portfolio construction framework that integrates hedge fund managers and QIS strategies in a mutually beneficial approach. This caters to most investors holding existing hedge fund stakes, which cannot be traded against or replaced outright by long-only QIS allocations.

Earlier analysis (Figure 36) revealed the market-neutral hedge fund portfolio exhibits asymmetric sensitivity - demonstrating positive correlation during equity market drawdowns while remaining uncorrelated across most regimes. Effectively, the portfolio risks underperformance in left-tail markets.

Hence, the aim becomes improving the resilience of this existing allocation by supplementing it with complementary QIS strategies. Specifically, we solve for the optimal blend of QIS components that maximises absolute alpha generated from the combined portfolio while enforcing zero equity beta over the evaluation period.

## Methodology:

1. Start with a fixed 100% allocation to the marketneutral hedge fund portfolio.

2. Run optimisations, allocating capital across the three QIS sub-portfolios (pro-cyclical, market-neutral, defensive) to solve for the precise blend that maximises alpha based on regression against global equities, with the constraint of portfolio beta equal to 0 on both the upside and downside.

3. Apply the constraint of total portfolio allocation of less than 200%.

## 5.4.1 Backtesting and results

To assess the effectiveness of this portfolio optimisation methodology, we conducted a backtest starting in January 2002. The combined hedge fund plus QIS portfolio was rebalanced every six months, mirroring the underlying hedge fund review timeline. A one-way 5 basis point transaction cost was incorporated for the QIS exposures on each rebalance trade.

Figure 61 plots the performance curve over the full period, revealing the blended portfolio’s superior risk-adjusted return of 4.5 compared to 3.65 for the hedge fund-only allocation. This shows that strategically supplementing the market-neutral hedge funds with QIS exposures enhances the portfolio’s risk/return profile.

Analysing equity market sensitivity in Figure 62, the combined portfolio demonstrates substantially improved convexity during equity tail events versus the standalone hedge fund allocation. Integrating the defense-oriented QIS exposures provided meaningful diversification, driving the long-term equity correlation down from 37.2% to 18.2%.

Figure 63 confirms this risk improvement across macro regimes. The combined portfolio generated more balanced returns across growth/inflation environments than the hedge fund market-neutral portfolio. This indicates the QIS blend enhanced resiliency across market conditions.

Figure 64 demonstrates the time series progression of optimal capital allocations to each QIS sub-portfolio over the backtest period.

We observe the Balanced QIS basket received the highest average allocation at approximately 50% over the last 10 years, as it contributes the most marginal alpha. The Defensive QIS component obtains a 25% average allocation over the same period, improving left tail convexity. However, the Pro-cyclical QIS basket does not receive direct allocation since the hedge fund portfolio already delivers uncorrelated returns in normal market conditions.

Figure 61: Performance of sub-portfolios
![](images/55e0da2e48d515b25c9833a0d14ed78cbf2b25e1d68ab61db92ea59bbdf111d3.jpg)

Figure 62: Relationship with global equities
![](images/37d7c23f911944e617c2c014aa73885d61061406c22c233d37d9b1fe7cd8068e.jpg)
Source: Deutsche Bank, Bloomberg Finance LP, HFR.

Figure 63: Performance across growth-inflation scenarios
![](images/750aeb700f7af3866a2658152e44106ba69ba6af5425b9439219329e83d2ccdb.jpg)

Figure 64: QIS sub-portfolio allocations
![](images/6aabae0acdd922784e6d50ced3928ac4fa309f3a0bf9d92501855cddc7479feb.jpg)
Source: Deutsche Bank, Bloomberg Finance LP.

In conclusion, this analysis demonstrates that complementing an existing market-neutral hedge fund allocation with lower-cost, factor-based QIS exposures can unlock meaningful improvements in portfolio efficiency. Strategically blending these complementary return streams diversifies tail risks and performance drivers, creating portfolios with superior reward-to-risk properties compared to a hedge fund-only allocation.

## 6. Conclusion

In this paper, we conducted an in-depth analysis of hedge fund investing, providing insights for investors on strategies, performance, portfolio construction, and relationships with QIS strategies.

The introduction framed key questions around demystifying drivers of hedge fund returns and their role in modern portfolios. We discussed methodologies for strategy analysis using the HFR database while mitigating biases that necessitate data refinement for robust evaluation.

Performance analysis revealed decreasing differentiation over time - evidenced by declining median returns, rising correlations, and concentrated variability explained by shrinking principal components. This highlighted the expanding importance of manager selection amid converging strategies.

We introduced a quantitative portfolio construction framework adaptable to specific investor goals like market neutrality or drawdown resilience. The methodology screens, ranks, and combines hedge funds in customised portfolios, demonstrated via backtested cases.

Finally, we assessed relationships with QIS strategies to isolate sources of incremental hedge fund alpha beyond systematic exposures. While some overlap exists, incorporating both dynamic hedge funds and rules-based QIS can provide portfolio diversification benefits.

Through this study, we aim to equip investors with a multifaceted understanding of the asset class, thereby demystifying hedge fund investing for informed decisionmaking.

## 7. Bibliography

Agarwal, V. and Naik, N. (2000) “On taking the Alternative Route: Risks, Rewards and Performance Persistence of Hedge Funds”, Journal of Alternative Investments 2-4, p. 6-23.

Alexander, C., and Dimitriu, A. (2004), “The Art of Investing in Hedge Funds: Fund Selection and Optimal Allocations (January 2004)”. Available at SSRN: https://ssrn.com/abstract=494404.

Alvarez, M., Jussa, J., Luo, Y., Wang, S., Wang, A. (2014), ”Hedge Funds: Selecting the Best of the Best”, Portfolios Under Construction, 29<sup>th</sup> July 2014.

Anand, V. and Zhang, G. (2020), “Keep Calm and Stay Market Neutral" Deutsche Bank Quantcraft, 24th March 2020.

Anand, V. (2021), “Inflation. Stagflation? Relax”, Deutsche Bank Quantcraft, 22<sup>nd</sup> June 2021.

Anand, V. (2022), ”An alternative to fixed income”, Deutsche Bank Quantcraft, 16<sup>th</sup> August 2022.

Anand, V. (2023), “Building a cross-asset carry portfolio”, Deutsche Bank Quantitative Musing, 5<sup>th</sup> July 2023.

Brown, S., W. Goetzmann and Ibbotson, R. (1999), “Offshore Hedge Funds: Survival and Performance 1989- 1995”, Journal of Business 72, p. 91-117.

Edwards, F.R. and Caglayan, M.O. (2001) “Hedge Fund Performance and Manager Skill”, Journal of Futures Markets 21-11, p. 1003– 1028.

Fung, W. and Hsieh, D. (2000), “Performance Characteristics of Hedge Funds and Commodity Funds: Natural vs. Spurious Biases”, Journal of Financial and Quantitative Analysis 35, p. 291-307.

Liang, B. (2000), “Hedge Funds: the Living and the Dead”, Journal of Financial and Quantitative Analysis 35, p. 309- 326.

Liang, B. (2001), “Hedge Fund Performance: 1990-1999”, Financial Analysts Journal 57, p. 11-18.

Natividade, C., Stanescu, S., Anand, V., Ward, P., Carter, S., Finelli, P. and Mesomeris, S. (2017), Volatility Risk Premium: New Dimensions, Deutsche Bank Quantitative Research.

Zhang, G. and Anand, V. (2020), Understand Your Risk, Deutsche Bank Quantcraft, 20th November 2020.

## 8. Appendix I: Building an all-weather QIS portfolio

While Section 5.4 demonstrated blending QIS strategies to improve the efficiency of hedge fund allocation, we understand many investors desire portfolios comprised solely of transparent, low-cost QIS building blocks either supplementary to existing hedge fund stakes or as partial substitutes. This appendix details constructing optimised market-neutral portfolios from QIS strategies alone.

## 8.1 Clustering QIS strategies

The first step involves clustering the QIS universe into groups sharing similar expected performance drivers and responses to shifting market contexts. Our methodology, per Section 5.1, categorises strategies into Defensive, Balanced, and Pro-cyclical baskets based on return patterns across scenarios for core macro risk factors – economic growth, inflation, and interest rates.

Figure 65 details the constituent strategies within each basket, while Figure 66 plots their respective performance curves over the sample period. Figure 67 demonstrates their sensitivity relationships to global equities. The Defensive cluster provides convexity during equity market drawdowns, while the Pro-cyclical group outperforms amid rallies. The Balanced basket delivers alpha through normal market periods. These complementary return profiles form the foundation for an optimised, resilient portfolio combination targeting market neutrality.

<table><tr><td colspan="3">Figure 65: Basket constituents</td></tr><tr><td>Market-neutral</td><td>Defensive</td><td>Pro-cyclical</td></tr><tr><td>factor portfolio</td><td>Equity dynamic multi- Equity Defensive Cash USD swaption VRP Factor</td><td></td></tr><tr><td>Equity cross-sectional Equity Dynamic reversion</td><td>Intraday Trend</td><td>SPX tactical VRP</td></tr><tr><td>Commodity Carry</td><td>Equity Dynamic long put option</td><td>Commodity diversified VRP</td></tr><tr><td>Commodities Curve</td><td>Commodity short-term FX carry trend</td><td></td></tr><tr><td>Commodity Congestion</td><td>FX Value</td><td>FX carry (cross currency)</td></tr><tr><td rowspan="6">Commodity Value</td><td>FX EM Tail Hedge</td><td>Europe long-term dividends</td></tr><tr><td>Rates Breakout momentum</td><td>Credit Curve - Main 5yr</td></tr><tr><td>Rates Long Volatility</td><td>vs10yr Credit Carry (HY vs IG)</td></tr><tr><td>Credit long/short Hedge (CDX IG)</td><td></td></tr><tr><td>Cross-asset defensive</td><td></td></tr><tr><td>CTA</td><td></td></tr><tr><td colspan="2">Source: Deutsche Bank</td><td></td></tr></table>

Figure 66: Performance of sub-portfolios
![](images/bb9aa639954dbbc5597aa73acde41f769d3e660a74f999e02838b42b8adf4551.jpg)

Figure 67: Relationship with global equities
![](images/32bf5689ee11e76f5894012260d101b9425c9a73987ea8fe87f651a8793f4df8.jpg)
Source: Deutsche Bank, Bloomberg Finance LP

## 8.2 Aggregating QIS sub-portfolios

Having clustered the QIS universe into groups with specialised return profiles, the next step involves combining them towards a specific portfolio objective. The precise composition depends on the desired outcome.

As one example detailed in Anand (2022), an investor could blend defensive and balanced clusters into a defensive-income portfolio, cushioning drawdowns but limiting bleeding across normal markets. In such cases, the Balanced allocation helps offset Defensive bleeding risk.

Our focus here, however, is constructing an optimal market-neutral portfolio maximising risk-adjusted alpha with equity beta exposure constrained to 0 on both the upside and downside, as depicted in Figure 68. This leads to aggregating clusters to build a portfolio uncorrelated on average with net positive excess returns across the economic cycle.

Source: Deutsche Bank, Bloomberg Finance LP.

Figure 68: An ideal market-neutral portfolio
![](images/2f24adf70836ab5e76fe4c20567c253664f1ef15af98a0ab58d1c4fea7718b28.jpg)

There are multiple ways to construct an optimised market-neutral portfolio. The Balanced cluster alone generates a near-zero equity beta over long periods alongside positive excess returns, representing one feasible single-basket solution.

However, as Figure 69 shows, it demonstrates some concavity during extreme tail events, underperforming as markets plummet. Potential reasons range from increased risk model error to certain premia fading in crises.

Figure 69: Relationship with global equities
![](images/440094071d9cadd01cab9e24e8c7aff0aa9b1a9f9f72186ccc23cb3f72ce4c50.jpg)

An alternative involves blending the Defensive and Procyclical baskets. However, due to their negative correlation, gains in one basket may not offset losses from the other across certain environments. Moreover, both may fail to deliver positive returns simultaneously across certain market periods.

Markets are complex and unpredictable, so we opt to maximise diversification by combining exposure across all three specialised QIS strategy baskets - Defensive, Balanced, and Pro-Cyclical. Our objective becomes finding the precise portfolio recipe blending these complementary return streams that deliver maximum achievable alpha while strictly maintaining 0% net equity beta exposure over time. This diversified approach helps to reduce risk and improve portfolio stability.

## 8.2.1 Random portfolio exercise

To demonstrate the efficacy of different construction methodologies described earlier, we conducted an analysis looping through all possible weight combinations allocating to the three underlying QIS baskets. Each iterative portfolio was assessed for its risk-adjusted alpha generation and net equity beta.

The analysis constraints ensure portfolio weights sum to 100% and maximum single basket allocation is 100%. This covers the range of prior referenced approaches - standalone Balanced portfolio, Defensive/Pro-cyclical blends, and more diversified combinations.

Figure 70: Efficient frontier analysis of QIS sub-portfolio combinations
![](images/c954f490dc61800488d97dea3fc4468454b40ba16ba63ae3a13f44c864fcf96c.jpg)
Source: Deutsche Bank, Bloomberg Finance LP.

Figure 70 plots the array of possible sub-portfolio combinations, depicting the efficient frontier in the riskreturn space. The x-axis represents each iterative portfolio's net equity beta over the period. The y-axis charts the risk-adjusted alpha - defined as the excess return over global equities divided by portfolio downside volatility. Observed results across the spectrum of allocation blends include:

The green curve depicts blends comprised solely of the Defensive and Pro-cyclical baskets, with no allocation to the Balanced subgroup. As highlighted previously, combinations along this frontier can achieve 0 equity beta at local maxima points for riskadjusted alpha. This verifies that diversifying across Defensive and Pro-cyclical exposures can construct market-neutral portfolios with solid absolute riskadjusted returns. However, there exist other allocation combinations producing higher alpha at the same 0 equity beta level, revealing this subset of two-basket portfolios as suboptimal solutions.

The red triangle, positioned along the frontier for Defensive/Pro-cyclical blends, represents a 100% allocation to the standalone Balanced basket. This single-basket portfolio demonstrates near-zero equity beta with solid absolute risk-adjusted returns, though still below the local maxima for that twocluster frontier. This verifies the Balanced-only option as a suboptimal but feasible market-neutral solution.

The orange efficient frontier depicts combinations allocating 50% to the Balanced basket, with the remainder split between Defensive and Pro-cyclical baskets. Portfolios along this line exhibit maximised risk-adjusted alpha across the spectrum of net equity betas. Notably, certain precise combinations along this frontier simultaneously deliver the maximum achievable alpha at 0 equity market beta. This reveals the diversified three-basket recipes as the optimised market-neutral portfolios.

Based on the preceding analysis and observations around Figure 70, we conclude the optimised market-neutral QIS portfolio solution combines all three specialised baskets rather than adopting a single Balanced allocation or two baskets Defensive/Pro-cyclical blend.

While the standalone Balanced basket and certain combinations solely of Defensive and Pro-Cyclical demonstrate feasible market-neutrality and absolute riskadjusted returns, diversifying across all three clusters allows for the highest achievable alpha at 0 equity beta over the backtest period.

The Balanced group provides persistent alpha generation to anchor returns. The Defensive and Pro-cyclical baskets help mitigate Balanced's conditional tail risks while also contributing incremental alpha. Altogether, the three baskets allow the portfolio to maintain resilience across varied market conditions.

Next, we discuss the methodology of allocating the capital among three QIS baskets.

## 8.2.2 Capital allocation methodology

We utilise the same objective function to distribute capital among sub-portfolio that we introduced in Section 5.4. So, we solve for basket weights by maximising portfolio riskadjusted alpha subject to 0% upside and downside equity beta constraints, as shown in Figure 68. An additiona constraint sets total allocation at 100% across clusters.

In setting allocation boundaries for the optimisation, a default approach would allow 0-100% for each basket. However, recognising results can be sensitive to uncertainties in the estimates (alpha and beta), we instead constrain ranges where observed alpha historically persists at elevated levels on average.

Specifically, Figures 71, 72, and 73 plot portfolio weights on the x-axis and risk-adjusted alpha of that respective portfolio on the y-axis. From these empirical tests, we understand the ranges where alpha persists at higher levels historically. Therefore, boundaries are set as follows:

Balanced Portfolio: 40-60%

<sup>▪</sup> Defensive & Pro-Cyclical: 0-50% each

Constraining to these narrower average elevated alpha bands per empirical analysis helps ameliorate potential statistical errors impacting optimisation results.

Figure 71: Risk-adjusted alpha sensitivity by QIS subportfolio (Balanced)
![](images/93b6a3f0574072bac48fbfb1d40616462db515de8fa30b7cfd8adbecc3ead6b1.jpg)
Source: Deutsche Bank, Bloomberg Finance LP.

Figure 72: Risk-adjusted alpha sensitivity by QIS subportfolio (Pro-cyclical)
![](images/e0da6e80e72633f85382e1d642bca44f3e7128bf6d040936622d082dc6b6a6f8.jpg)
Source: Deutsche Bank, Bloomberg Finance LP.

Figure 73: Risk-adjusted alpha sensitivity by QIS subportfolio (Defensive)
![](images/4ee297225b09a9bcabdf8b81d355930c0f792c0c7c748b4d5e04883abee60cba.jpg)
Source: Deutsche Bank, Bloomberg Finance LP.

## 8.2.3 Backtest analysis and results

Starting in January 2002, we backtested a strategy optimising capital allocation across three QIS subportfolios. Rebalancing and weight adjustments occur quarterly, with a one-way transaction cost of 5 basis points for sub-portfolio trades.

Figure 74 plots the performance curve of the optimised market-neutral QIS portfolio over the 22-year backtest horizon. The portfolio generated a CAGR of 3.95 with a volatility (unleveraged) of 1.6%, resulting in a riskadjusted return of 2.45 over this timeframe.

![](images/e9968a17e4a16b9a3aafa9a06f8d85cd903c5eb2ae5964dd7531d40546bab563.jpg)
Assessing sensitivity, Figures 75 and 76 plot the portfolio's relationship with global equities and 10-year US Treasuries, respectively. The portfolio exhibits more balanced tails relative to a standalone Balanced allocation. Further, the portfolio exhibited a long-term correlation of 11% with equities and -0.5% with Treasury over the full timeframe.

Figure 75: Relationship with equities
![](images/d4af0dd29a3e6e16679803ce302f8ac4b8a62b266f719664138132eb49d4222a.jpg)

Figure 76: Relationship with US Treasuries
![](images/37c97a350cb29a96e52316fa4c78b5d7357f8e7e22a567251c70c46a3be97d6a.jpg)

Figure 77 plots the scenario-specific risk-adjusted returns across the three constituent QIS baskets alongside the combined optimised portfolio. The blended portfolio shows balanced performance across the range of market scenarios - another validation of diversification efficacy.

Figure 77: Scenario-specific risk-adjusted return
![](images/6261386fc93a0be95a63a8944650d4e7f2232b4822b834b9d9f98ccaca5962e0.jpg)

Figure 78 also shows the progression of allocations over time. As expected, the Balanced basket empirically received the highest allocation, averaging approximately 55% over the backtest timeline. The Defensive portfolio obtained a 25% average allocation, followed by Procyclical at 20% on average within the market-neutral combination.

This section details our approach to constructing an optimised market-neutral portfolio solely from transparent, low-cost QIS exposures.

Now, a logical follow-on question arises - how does this standalone QIS portfolio complement an existing hedge fund allocation? To address this query, we plotted the monthly returns of the hedge fund portfolio against the QIS portfolio, as shown in Figure 79.

Figure 78: QIS sub-portfolio allocations
![](images/92da2196c9c96f70ca1835a1aef1f55cc9d577eb1396caca97b5cb95cc4733d9.jpg)
It exhibits that the optimised QIS combination demonstrates minimal long-term correlation to the hedge fund market-neutral portfolio developed previously. This finding indicates the blended QIS basket's viability as a diversifying complement alongside alpha-focused hedge fund holdings.

Figure 79: HF Market-neutral portfolio vs QIS Marketneutral portfolio
![](images/abfce069fb4efb246f8fb3e4fb48b45bb07f0fefe8526c984a3edf1e25becb65.jpg)
In essence, the optimised QIS market-neutral portfolio can serve as an underlying factor exposure layer while the hedge fund allocation targets deeper value add.

## 9. Appendix II

Below is the list of 40 return streams used in our study. All costs associated with trading these streams are included in our analysis.

<table><tr><td colspan="3">Figure 80: List of return streams used</td></tr><tr><td>Name</td><td>Asset Class</td><td>Investment Type</td></tr><tr><td>Equity Momentum Factor</td><td>Equities</td><td>Strategy</td></tr><tr><td>Equity Low Beta Factor</td><td>Equities</td><td>Strategy</td></tr><tr><td>Equity Quality Factor</td><td>Equities</td><td>Strategy</td></tr><tr><td>Equity Value Factor</td><td>Equities</td><td>Strategy</td></tr><tr><td>NLASR Global Long Short</td><td>Equities</td><td>Strategy</td></tr><tr><td>Defensive Equity factor</td><td>Equities</td><td>Strategy</td></tr><tr><td>Equity (SPX) VRP</td><td>Equities</td><td>Strategy</td></tr><tr><td>Equity dynamic intraday trend</td><td>Equities</td><td>Strategy</td></tr><tr><td>Equity dynamic long put option</td><td>Equities</td><td>Strategy</td></tr><tr><td>Equity VIX call delta replication</td><td>Equities</td><td>Strategy</td></tr><tr><td>Equity Europe long-term dividends</td><td>Equities</td><td>Strategy</td></tr><tr><td>Equity NDX put carry</td><td>Equities</td><td>Strategy</td></tr><tr><td>Equity Europe Put carry</td><td>Equities</td><td>Strategy</td></tr><tr><td>Rates VRP (Implied vs Realised Vol)</td><td>Fixed Income</td><td>Strategy</td></tr><tr><td>Rates Diversified Long Vol Basket</td><td>Fixed Income</td><td>Strategy</td></tr><tr><td>Rates Break out Momentum</td><td>Fixed Income</td><td>Strategy</td></tr><tr><td>Rates Curve</td><td>Fixed Income</td><td>Strategy</td></tr><tr><td>Rates Beta Neutral Carry</td><td>Fixed Income</td><td>Strategy</td></tr><tr><td>Credit Carry - HY vs IG</td><td>Fixed Income</td><td>Strategy</td></tr><tr><td>Credit Curve - Main 5yr vs10yr</td><td>Fixed Income</td><td>Strategy</td></tr><tr><td>Credit Momentum</td><td>Fixed Income</td><td>Strategy</td></tr><tr><td>Credit AlphaHedge (CDX IG)</td><td>Fixed Income</td><td>Strategy</td></tr><tr><td>Credit Hedge (CDX IG)</td><td>Fixed Income</td><td>Strategy</td></tr><tr><td>Commodities Curve</td><td>Commodities</td><td>Strategy</td></tr><tr><td>Commodities Carry (Backwardation)</td><td>Commodities</td><td>Strategy</td></tr><tr><td>Commodities Short-Term Trend</td><td>Commodities</td><td>Strategy</td></tr><tr><td>Commodities Trend</td><td>Commodities</td><td>Strategy</td></tr><tr><td>Commodities Congestion</td><td>Commodities</td><td>Strategy</td></tr><tr><td>Commodities Value</td><td>Commodities</td><td>Strategy</td></tr><tr><td>Diversified Commodity VRP</td><td>Commodities</td><td>Strategy</td></tr><tr><td>EM FX Tail Index</td><td>FX</td><td>Strategy</td></tr><tr><td>FX Trend</td><td>FX</td><td>Strategy</td></tr><tr><td>FX Carry</td><td>FX</td><td>Strategy</td></tr><tr><td>FX Value</td><td>FX</td><td>Strategy</td></tr><tr><td>FX Momentum</td><td>FX</td><td>Strategy</td></tr><tr><td>FX Carry (cross-currency)</td><td>FX</td><td>Strategy</td></tr><tr><td>DB Cross Asset CORE Global Equity Overlay Index</td><td>Cross-Assets</td><td>Strategy</td></tr><tr><td>Equity Proxy Put Replication Index</td><td>Cross-Assets</td><td>Strategy</td></tr><tr><td>Cross Asset Trends 2.0 Index</td><td>Cross-Assets</td><td>Strategy</td></tr><tr><td>Cross Asset Carry Index Source: Deutsche Bank</td><td>Cross-Assets</td><td>Strategy</td></tr></table>

## Appendix 1

## Important Disclosures

Additional information available upon request

\*Prices are current as of the end of the previous trading session unless otherwise indicated and are sourced from local exchanges via Reuters, Bloomberg and other vendors . Other information is sourced from Deutsche Bank, subject companies, and other sources. For disclosures pertaining to recommendations or estimates made on securities other than the primary subject of this research, please see the most recently published company report or visit our global disclosure look-up page on our website at https://research.db.com/Research/Disclosures/EquityResearchDisclosures. Aside from within this report, important risk and conflict disclosures can also be found at https://research.db.com/Research/Disclosures/Disclaimer. Investors are strongly encouraged to review this information before investing.

## Analyst Certification

The views expressed in this report accurately reflect the personal views of the undersigned lead analyst(s). In addition, the undersigned lead analyst(s) has not and will not receive any compensation for providing a specific recommendation or view in this report. Vivek Anand

## Hypothetical Disclaimer

Backtested, hypothetical or simulated performance results have inherent limitations. Unlike an actual performance record based on trading actual client portfolios, simulated results are achieved by means of the retroactive application of a backtested model itself designed with the benefit of hindsight. Taking into account historical events the backtesting of performance also differs from actual account performance because an actual investment strategy may be adjusted any time, for any reason, including a response to material, economic or market factors. The backtested performance includes hypothetical results that do not reflect the reinvestment of dividends and other earnings or the deduction of advisory fees, brokerage or other commissions, and any other expenses that a client would have paid or actually paid. No representation is made that any trading strategy or account will or is likely to achieve profits or losses similar to those shown. Alternative modeling techniques or assumptions might produce significantly different results and prove to be more appropriate. Past hypothetical backtest results are neither an indicator nor guarantee of future returns. Actual results will vary, perhaps materially, from the analysis.

## Additional Information

The information and opinions in this report were prepared by Deutsche Bank AG or one of its affiliates (collectively 'Deutsche Bank'). Though the information herein is believed to be reliable and has been obtained from public sources believed to be reliable, Deutsche Bank makes no representation as to its accuracy or completeness. Hyperlinks to third-party websites in this report are provided for reader convenience only. Deutsche Bank neither endorses the content nor is responsible for the accuracy or security controls of those websites.

Effective 13 October 2023, Deutsche Bank AG acquired Numis Corporation Plc and its subsidiaries (the "Numis Group"). Numis Securities Limited ("NSL") is a member of the Numis Group and a firm authorised and regulated by the Financial Conduct Authority (Firm Reference Number: 144822). Deutsche Bank AG provides clients with, amongst other services, Investment Research services. NSL provides clients with, amongst other services, non-independent research services.

During an initial integration process, the research departments of Deutsche Bank AG and NSL will remain operationally distinct. Consequently, disclosures relating to conflicts of interest that may exist for Deutsche Bank AG and/or its affiliates do not currently take into account the business and activities of the Numis Group. The conflicts of interest that may exist for the Numis Group, in relation to the provision of research, can be found on the Numis website at https://www.numis.com/legaland-regulatory/conditions-and-disclaimers-that-govern-research-contained-in-the-research-pages-of-this-website. The disclosures on this Numis webpage do not currently take into account the business and activities of Deutsche Bank AG and/or its affiliates which are not members of the Numis Group.

Additionally, any detailed conflicts of interest disclosures pertaining to a specific recommendation or estimate made on a security mentioned in this report or which have been included in our most recently published company report or found on our global disclosure look-up page, do not currently take into account the business and activities of the Numis Group. Instead, details of detailed conflicts of interest disclosures for the Numis Group, relating to specific issuers or securities, can be found at: https://library.numis.com/regulatory\_notice. The issuer/security-specific conflict of interest disclosures on this Numis webpage do not take into account the business and activities of Deutsche Bank and/or its affiliates which are not members of the Numis Group.

If you use the services of Deutsche Bank in connection with a purchase or sale of a security that is discussed in this report, or is included or discussed in another communication (oral or written) from a Deutsche Bank analyst, Deutsche Bank may act as principal for its own account or as agent for another person.

Deutsche Bank may consider this report in deciding to trade as principal. It may also engage in transactions, for its own account or with customers, in a manner inconsistent with the views taken in this research report. Others within Deutsche Bank, including strategists, sales staff and other analysts, may take views that are inconsistent with those taken in this research report. Deutsche Bank issues a variety of research products, including fundamental analysis, equity-linked analysis, quantitative analysis and trade ideas. Recommendations contained in one type of communication may differ from recommendations contained in others, whether as a result of differing time horizons, methodologies, perspectives or otherwise. Deutsche Bank and/or its affiliates may also be holding debt or equity securities of the issuers it writes on. Analysts are paid in part based on the profitability of Deutsche Bank AG and its affiliates, which includes investment banking, trading and principal trading revenues.

Opinions, estimates and projections constitute the current judgment of the author as of the date of this report. They do not necessarily reflect the opinions of Deutsche Bank and are subject to change without notice. Deutsche Bank provides liquidity for buvers and sellers of securities issued by the companies it covers. Deutsche Bank research analysts sometimes have shorter-term trade ideas that may be inconsistent with Deutsche Bank's existing longer-term ratings. Some trade ideas for equities are listed as Catalyst Calls on the Research Website (https://research.db.com/Research/) , and can be found on the general coverage list and also on the covered company's page. A Catalyst Call represents a high-conviction belief by an analyst that a stock will outperform or underperform the market and/or a specified sector over a time frame of no less than two weeks and no more than three months. In addition to Catalyst Calls, analysts may occasionally discuss with our clients, and with Deutsche Bank salespersons and traders, trading strategies or ideas that reference catalysts or events that may have a nearterm or medium-term impact on the market price of the securities discussed in this report, which impact may be directionally counter to the analysts' current 12-month view of total return or investment return as described herein. Deutsche Bank has no obligation to update, modify or amend this report or to otherwise notify a recipient thereof if an opinion, forecast or estimate changes or becomes inaccurate. Coverage and the frequency of changes in market conditions and in both general and company-specific economic prospects make it difficult to update research at defined intervals. Updates are at the sole discretion of the coverage analyst or of the Research Department Management, and the majority of reports are published at irregular intervals. This report is provided for informational purposes only and does not take into account the particular investment objectives, financial situations, or needs of individual clients. It is not an offer or a solicitation of an offer to buy or sell any financial instruments or to participate in any particular trading strategy. Target prices are inherently imprecise and a product of the analyst's judgment. The financial instruments discussed in this report may not be suitable for all investors, and investors must make their own informed investment decisions. Prices and availability of financial instruments are subiect to change without notice, and investment transactions can lead to losses as a result of price fluctuations and other factors. If a financial instrument is denominated in a currency other than an investor's currency, a change in exchange rates may adversely affect the investment. Past performance is not necessarily indicative of future results. Performance calculations exclude transaction costs, unless otherwise indicated. Unless otherwise indicated, prices are current as of the end of the previous trading session and are sourced from local exchanges via Reuters, Bloomberg and other vendors. Data is also sourced from Deutsche Bank, subject companies, and other parties.

The Deutsche Bank Research Department is independent of other business divisions of the Bank. Details regarding our organizational arrangements and information barriers we have to prevent and avoid conflicts of interest with respect to our research are available on our website (https://research.db.com/Research/) under Disclaimer.

Macroeconomic fluctuations often account for most of the risks associated with exposures to instruments that promise to pay fixed or variable interest rates. For an investor who is long fixed-rate instruments (thus receiving these cash flows), increases in interest rates naturally lift the discount factors applied to the expected cash flows and thus cause a loss. The longer the maturity of a certain cash flow and the higher the move in the discount factor, the higher will be the loss. Upside surprises in inflation, fiscal funding needs, and FX depreciation rates are among the most common adverse macroeconomic shocks to receivers. But counterparty exposure, issuer creditworthiness, client segmentation, regulation (including changes in assets holding limits for different types of investors), changes in tax policies, currency convertibility (which may constrain currency conversion, repatriation of profits and/or liquidation of positions), and settlement issues related to local clearing houses are also important risk factors. The sensitivity of fixed-income instruments to macroeconomic shocks may be mitigated by indexing the contracted cash flows to inflation, to FX depreciation, or to specified interest rates - these are common in emerging markets. The index fixings may - by construction - lag or mis-measure the actual move in the underlying variables they are intended to track. The choice of the proper fixing (or metric) is particularly important in swaps markets, where floating coupon rates (i.e., coupons indexed to a typically short-dated interest rate reference index) are exchanged for fixed coupons. Funding in a currency that differs from the currency in which coupons are denominated carries FX risk. Options on swaps (swaptions) the risks typical to options in addition to the risks related to rates movements.

Derivative transactions involve numerous risks including market, counterparty default and illiquidity risk. The appropriateness of these products for use by investors depends on the investors' own circumstances, including their tax position, their regulatory environment and the nature of their other assets and liabilities; as such, investors should take expert legal and financial advice before entering into any transaction similar to or inspired by the contents of this publication. The risk of loss in futures trading and options, foreign or domestic, can be substantial. As a result of the high degree of leverage obtainable in futures and options trading, losses may be incurred that are greater than the amount of funds initially deposited - up to theoretically unlimited losses. Trading in options involves risk and is not suitable for all investors. Prior to buying or selling an option, investors must review the 'Characteristics and Risks of Standardized Options", at http://www.optionsclearing.com/ about/publications/character-risks.jsp. If you are unable to access the website, please contact your Deutsche Bank representative for a copy of this important document.

Participants in foreign exchange transactions may incur risks arising from several factors, including the following: (i) exchange rates can be volatile and are subject to large fluctuations; (ii) the value of currencies may be affected by numerous market factors, including world and national economic, political and regulatory events, events in equity and debt markets and changes in interest rates; and (iii) currencies may be subject to devaluation or government-imposed exchange controls, which could affect the value of the currency. Investors in securities such as ADRs, whose values are affected by the currency of an underlying security, effectively assume currency risk.

Unless governing law provides otherwise, all transactions should be executed through the Deutsche Bank entity in the investor's home jurisdiction. Aside from within this report, important conflict disclosures can also be found at https:// research.db.com/Research/ on each company's research page. Investors are strongly encouraged to review this information before investing.

Deutsche Bank (which includes Deutsche Bank AG, its branches and affiliated companies) is not acting as a financial adviser, consultant or fiduciary to you or any of your agents (collectively, "You" or "Your") with respect to any information provided in this report. Deutsche Bank does not provide investment, legal, tax or accounting advice, Deutsche Bank is not acting as your impartial adviser, and does not express any opinion or recommendation whatsoever as to any strategies, products or any other information presented in the materials. Information contained herein is being provided solely on the basis that the recipient will make an independent assessment of the merits of any investment decision, and it does not constitute a recommendation of, or express an opinion on, any product or service or any trading strategy.

The information presented is general in nature and is not directed to retirement accounts or any specific person or account type, and is therefore provided to You on the express basis that it is not advice, and You may not rely upon it in making Your decision. The information we provide is being directed only to persons we believe to be financially sophisticated, who are capable of evaluating investment risks independently, both in general and with regard to particular transactions and investment strategies, and who understand that Deutsche Bank has financial interests in the offering of its products and services. If this is not the case, or if You are an IRA or other retail investor receiving this directly from us, we ask that you inform us immediately.

In July 2018, Deutsche Bank revised its rating system for short term ideas whereby the branding has been changed to Catalyst Calls ("CC") from SOLAR ideas; the rating categories for Catalyst Calls originated in the Americas region have been made consistent with the categories used by Analysts globally; and the effective time period for CCs has been reduced from a maximum of 180 days to 90 days.

United States: Approved and/or distributed by Deutsche Bank Securities Incorporated, a member of FINRA, NFA and SIPC.
Analysts located outside of the United States are employed by non-US affiliates that are not subject to FINRA regulations.

European Economic Area (exc. United Kingdom): Approved and/or distributed by Deutsche Bank AG, a joint stock corporation with limited liability incorporated in the Federal Republic of Germany with its principal office in Frankfurt am Main. Deutsche Bank AG is authorized under German Banking Law and is subject to supervision by the European Central Bank and

by BaFin, Germany's Federal Financial Supervisory Authority.

United Kingdom: Approved and/or distributed by Deutsche Bank AG acting through its London Branch at 21 Moorfields, London EC2Y 9DB. Deutsche Bank AG in the United Kingdom is authorised by the Prudential Regulation Authority and is subject to limited regulation by the Prudential Regulation Authority and Financial Conduct Authority. Details about the extent of our authorisation and regulation are available on request.

Hong Kong SAR: Distributed by Deutsche Bank AG, Hong Kong Branch except for any research content relating to futures contracts within the meaning of the Hong Kong Securities and Futures Ordinance Cap. 571. Research reports on such futures contracts are not intended for access by persons who are located, incorporated, constituted or resident in Hong Kong. The author(s) of a research report may not be licensed to carry on regulated activities in Hong Kong and, if not licensed, do not hold themselves out as being able to do so. The provisions set out above in the 'Additional Information' section shall apply to the fullest extent permissible by local laws and regulations, including without limitation the Code of Conduct for Persons Licensed or Registered with the Securities and Futures Commission. This report is intended for distribution only to 'professional investors' as defined in Part 1 of Schedule of the SFO. This document must not be acted or relied on by persons who are not professional investors. Any investment or investment activity to which this document relates is only available to professional investors and will be engaged only with professional investors.

India: Prepared by Deutsche Equities India Private Limited (DEIPL) having CIN: U65990MH2002PTC137431 and registered office at 14th Floor, The Capital, C-70, G Block, Bandra Kurla Complex, Mumbai (India) 400051. Tel: + 91 22 7180 4444. It is registered by the Securities and Exchange Board of India (SEBI) as a Stock broker bearing registration no.: INZ000252437; Merchant Banker bearing SEBI Registration no.: INM000010833 and Research Analyst bearing SEBI Registration no.: INH000001741. DEIPL's Compliance / Grievance officer is Ms. Rashmi Poddar (Tel: +91 22 7180 4929, email ID: complaints.deipl@db.com). Registration granted by SEBI and certification from NISM in no way guarantee performance of DEIPL or provide any assurance of returns to investors. Investment in securities market are subject to market risks. Read all the related documents carefully before investing. DEIPL may have received administrative warnings from the SEBI for breaches of Indian regulations. Deutsche Bank and/or its affiliate(s) may have debt holdings or positions in the subject company. With regard to information on associates, please refer to the "Shareholdings" section in the Annual Report at: https:// www.db.com/ir/en/annual-reports.htm.

Japan: Approved and/or distributed by Deutsche Securities Inc.(DSI). Registration number - Registered as a financia instruments dealer by the Head of the Kanto Local Finance Bureau (Kinsho) No. 117. Member of associations: JSDA, Type II Financial Instruments Firms Association and The Financial Futures Association of Japan. Commissions and risks involved in stock transactions - for stock transactions, we charge stock commissions and consumption tax by multiplying the transaction amount by the commission rate agreed with each customer. Stock transactions can lead to losses as a result of share price fluctuations and other factors. Transactions in foreign stocks can lead to additional losses stemming from foreign exchange fluctuations. We may also charge commissions and fees for certain categories of investment advice, products and services. Recommended investment strategies, products and services carry the risk of losses to principal and other losses as a result of changes in market and/or economic trends, and/or fluctuations in market value. Before deciding on the purchase of financial products and/or services, customers should carefully read the relevant disclosures, prospectuses and other documentation. 'Moody's', 'Standard Poor's', and 'Fitch' mentioned in this report are not registered credit rating agencies in Japan unless Japan or 'Nippon' is specifically designated in the name of the entity. Reports on Japanese listed companies not written by analysts of DSI are written by Deutsche Bank Group's analysts with the coverage companies specified by DSI. Some of the foreign securities stated on this report are not disclosed according to the Financial Instruments and Exchange Law of Japan. Target prices set by Deutsche Bank's equity analysts are based on a 12-month forecast period.

Korea: Distributed by Deutsche Securities Korea Co.

South Africa: Deutsche Bank AG Johannesburg is incorporated in the Federal Republic of Germany (Branch Register Number in South Africa: 1998/003298/10).

Singapore: This report is issued by Deutsche Bank AG, Singapore Branch (One Raffles Quay #18-00 South Tower Singapore 048583, 65 6423 8001), which may be contacted in respect of any matters arising from, or in connection with, this report. Where this report is issued or promulgated by Deutsche Bank in Singapore to a person who is not an accredited investor, expert investor or institutional investor (as defined in the applicable Singapore laws and regulations), they accept legal responsibility to such person for its contents.

Taiwan: Information on securities/investments that trade in Taiwan is for your reference only. Readers should independently evaluate investment risks and are solely responsible for their investment decisions. Deutsche Bank research may not be distributed to the Taiwan public media or quoted or used by the Taiwan public media without written consent. Information on securities/instruments that do not trade in Taiwan is for informational purposes only and is not to be construed as a recommendation to trade in such securities/instruments.

Qatar: Deutsche Bank AG in the Qatar Financial Centre (registered no. 00032) is regulated by the Qatar Financial Centre Regulatory Authority. Deutsche Bank AG - QFC Branch may undertake only the financial services activities that fall within the scope of its existing QFCRA license. Its principal place of business in the QFC: Qatar Financial Centre, Tower, West Bay, Level 5, PO Box 14928, Doha, Qatar. This information has been distributed by Deutsche Bank AG. Related financial products or services are only available only to Business Customers, as defined by the Qatar Financial Centre Regulatory Authority.

Russia: The information, interpretation and opinions submitted herein are not in the context of, and do not constitute, any appraisal or evaluation activity requiring a license in the Russian Federation.

Kingdom of Saudi Arabia: Deutsche Securities Saudi Arabia (DSSA) is a closed joint stock company authorized by the Capital Market Authority of the Kingdom of Saudi Arabia with a license number (No. 37-07073) to conduct the following business activities: Dealing, Arranging, Advising, and Custody activities. DSSA registered office is Faisaliah Tower, 17th Floor, King Fahad Road - Al Olaya District Riyadh, Kingdom of Saudi Arabia P.O. Box 301806.

United Arab Emirates: Deutsche Bank AG in the Dubai International Financial Centre (registered no. 00045) is regulated by the Dubai Financial Services Authority. Deutsche Bank AG - DIFC Branch may only undertake the financial services activities that fall within the scope of its existing DFSA license. Principal place of business in the DIFC: Dubai International Financial Centre, The Gate Village, Building 5, PO Box 504902, Dubai, U.A.E. This information has been distributed by Deutsche Bank AG. Related financial products or services are available only to Professional Clients, as defined by the Dubai Financial Services Authority.

Australia and New Zealand: This research is intended only for 'wholesale clients' within the meaning of the Australian Corporations Act and New Zealand Financial Advisors Act, respectively. Please refer to Australia-specific research disclosures and related information at https://www.dbresearch.com/PROD/RPS\_EN-PROD/PROD0000000000521304.xhtml . Where research refers to any particular financial product recipients of the research should consider any product disclosure statement, prospectus or other applicable disclosure document before making any decision about whether to acquire the product. In preparing this report, the primary analyst or an individual who assisted in the preparation of this report has likely been in contact with the company that is the subject of this research for confirmation/clarification of data, facts, statements, permission to use company-sourced material in the report, and/or site-visit attendance. Without prior approval from Research Management, analysts may not accept from current or potential Banking clients the costs of travel, accommodations, or other expenses incurred by analysts attending site visits, conferences, social events, and the like. Similarly, without prior approval from Research Management and Anti-Bribery and Corruption ("ABC") team, analysts may not accept perks or other items of value for their personal use from issuers they cover.

Additional information relative to securities, other financial products or issuers discussed in this report is available upon request. This report may not be reproduced, distributed or published without Deutsche Bank's prior written consent.

Backtested, hypothetical or simulated performance results have inherent limitations. Unlike an actual performance record based on trading actual client portfolios, simulated results are achieved by means of the retroactive application of a backtested model itself designed with the benefit of hindsight. Taking into account historical events the backtesting of performance also differs from actual account performance because an actual investment strategy may be adjusted any time, for any reason, including a response to material, economic or market factors. The backtested performance includes hypothetical results that do not reflect the reinvestment of dividends and other earnings or the deduction of advisory fees, brokerage or other commissions, and any other expenses that a client would have paid or actually paid. No representation is made that any trading strategy or account will or is likely to achieve profits or losses similar to those shown. Alternative modeling techniques or assumptions might produce significantly different results and prove to be more appropriate. Past hypothetical backtest results are neither an indicator nor guarantee of future returns. Actual results will vary, perhaps materially, from the analysis.

The method for computing individual E,S,G and composite ESG scores set forth herein is a novel method developed by the Research department within Deutsche Bank AG, computed using a systematic approach without human intervention. Different data providers, market sectors and geographies approach ESG analysis and incorporate the findings in a variety of ways. As such, the ESG scores referred to herein may differ from equivalent ratings developed and implemented by other ESG data providers in the market and may also differ from equivalent ratings developed and implemented by other divisions within the Deutsche Bank Group. Such ESG scores also differ from other ratings and rankings that have historically been applied in research reports published by Deutsche Bank AG. Further, such ESG scores do not represent a formal or official view of Deutsche Bank AG. It should be noted that the decision to incorporate ESG factors into any investment strategy may inhibit the ability to participate in certain investment opportunities that otherwise would be consistent with your investment objective and other principal investment strategies. The returns on a portfolio consisting primarily of sustainable investments may be lower or higher than portfolios where ESG factors, exclusions, or other sustainability issues are not considered, and the investment opportunities available to such portfolios may differ. Companies may not necessarily meet high performance standards on all aspects of ESG or sustainable investing issues; there is also no guarantee that any company will meet expectations in connection with corporate responsibility, sustainability, and/or impact performance.

Copyright © 2024 Deutsche Bank AG

David Folkerts-Landau Group Chief Economist and Global Head of Research
<table><tr><td>Pam Finelli Global Chief Operating Officer Research</td><td>Steve Pollard Global Head of Company Research and Sales</td><td>Jim Reid Global Head of Macro and Thematic Research</td><td>Tim Rokossa Head of Germany Research</td></tr><tr><td>Gerry Gallagher Head of European</td><td>Matthew Barnard Head of Americas</td><td>Peter Milliken Head of APAC</td><td>Debbie Jones Global Head of</td></tr><tr><td>Company Research</td><td>Company Research</td><td>Company Research</td><td>Company Research ESG</td></tr><tr><td>Sameer Goel Global Head of EM &amp; APAC Research</td><td>Francis Yared Global Head of Rates Research</td><td>George Saravelos Global Head of FX Research</td><td>Peter Hooper Vice-Chair of Research</td></tr></table>

## International Production Locations

<table><tr><td>Deutsche Bank AG</td><td>Deutsche Bank AG</td><td>Deutsche Bank AG</td><td>Deutsche Securities Inc.</td></tr><tr><td>Deutsche Bank Place</td><td>Equity Research</td><td>Filiale Hongkong</td><td>2-11-1 Nagatacho</td></tr><tr><td>Level 16</td><td>Mainzer Landstrasse 11-17</td><td>International Commerce Centre,</td><td>Sanno Park Tower</td></tr><tr><td>Corner of Hunter &amp; Phillip Streets</td><td>60329 Frankfurt am Main</td><td>1 Austin Road West,Kowloon,</td><td>Chiyoda-ku, Tokyo 100-6171</td></tr><tr><td>Sydney, NSW 2000</td><td>Germany</td><td>Hong Kong</td><td>Japan</td></tr><tr><td>Australia</td><td>Tel: (49) 69 910 00</td><td>Tel: (852) 2203 8888</td><td>Tel: (81) 3 5156 6000</td></tr><tr><td colspan="4">Tel: (61) 2 8258 1234</td></tr></table>