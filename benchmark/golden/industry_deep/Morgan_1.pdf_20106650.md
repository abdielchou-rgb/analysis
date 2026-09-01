Correction (first published 22 February 2024) (See disclosures for details)

# Global Equity Derivatives

## Systematic Dispersion Update

In this systematic dispersion update, we want to discuss about the performance impact on the systematic dispersion strategy of hedging through skew delta and the estimation of skew stickiness ratio.

Black Scholes delta is a good starting point for hedging the options delta. However, due to the volatility skew, the assumption of flat volatility in Black Scholes world is hardly met in practice. There are a couple of papers discussing how the volatility skew changes when the market moves and the corresponding affects on the pricing and risk management of volatility instruments. Two popular rules are sticky strike and sticky delta.

Sticky strike rule assumes that the implied volatility curve will not change if the spot moves, i.e. the volatility skew sticks to the strike price. As a result, BS delta should be used to hedge under this assumption. However, the ATMF vol moves along the original volatility curve when spot moves.

Sticky delta (or moneyness) rule assumes that the implied volatility curve will shift horizontally with the spot movement, and preserve the shape in terms of delta (or moneyness); for example, under sticky delta rule, the ATMF vol will be persistent.

Figure 1: Change of volatility skew based on sticky strike or sticky delta rules if spot moves down by 10%
![](images/eaff8d9cd028ba0708d27815ba32b0d20eb2570be4081444b924784b651f69cd.jpg)

Global Quantitative and Derivatives Strategy

Libin Cheng AC
(1-212) 270-1434
libin.cheng@jpmchase.com

Peng Cheng, CFA <sup>AC</sup> (1-212) 622-5036 peng.cheng@jpmorgan.com J.P. Morgan Securities LLC

## See page 12 for analyst certification and important disclosures.

J.P. Morgan does and seeks to do business with companies covered in its research reports. As a result, investors should be aware that the firm may have a conflict of interest that could affect the objectivity of this report. Investors should consider this report as only a single factor in making their investment decision.

The skew stickiness ratio is introduced to describe the joint dynamic between spot and volatility skew. As introduced in Bergomi 2009, the skew stickiness ratio (SSR) can be defined as:

$$
S S R = \frac { \Delta \sigma _ { A T M F } } { \Delta \ln ( S ) \times A T M S k e w }
$$

$$
A T M S k e w = \frac { d \sigma _ { K } } { d l n ( K ) } \bigg | _ { F }
$$

where K=Strike/Spot. As pointed out in the paper, the SSR is 1 and 0 under the sticky strike and sticky delta assumptions, respectively.

In addition, it is possible for us to estimate the SSR as the regression coefficient of the change of ATMF vol $\left( \begin{array} { l } { \Delta \sigma _ { A T M F } } \end{array} \right)$ on the change of log return of the spot in units of the ATMF skew $( \mathbf { \Gamma } _ { \Delta \ln ( S ) } \times A T M S k e w ) .$

We apply this method to estimate the historical 3m SPX SSR and current SSR below:

Figure 2: Historical 3m SPX SSR
![](images/4f4cf10af8e8b7606d8cb9d051a649014e8474eb93041313821ad634c3746d98.jpg)

Figure 3: Current 3m SPX SSR estimated by the regression with 1 year of data (estimated beta=1.08, slope of red dotted line=1)
![](images/b4c3c067240a66762bec34022ec16225f2d0b2172c45dee78f149a60070b2202.jpg)

As one can see above, historically speaking, 3m SPX SSR is generally larger than 1, indicating the empirical ATM vol movements are larger than the sticky strike (SSR=1) has suggested. Before 2022, the SSR is around 1.4, while after 2022, it reduces to the current estimation of 1.08.

We can apply the similar method to estimate the SSR for single stocks. Here are the 3m SSR estimation as of 12/15/2023 on some underlyings.

<table><tr><td>Ticker</td><td>Estimated SSR</td><td>Ticker</td><td>Estimated SSR</td></tr><tr><td>AAPL</td><td>1.21</td><td>SPX</td><td>1.08</td></tr><tr><td>GOOGL</td><td>0.69</td><td>VZ</td><td>1.49</td></tr><tr><td>GS</td><td>1.35</td><td>WMT</td><td>0.74</td></tr><tr><td>JNJ</td><td>0.76</td><td>XOM</td><td>1.21</td></tr></table>

## Dispersion performance with skew adjusted delta hedging

In the following sections, we show how hedging the options delta by using skew adjusted delta affects the dispersion performance. We start the analysis with the 3m ATM straddle dispersion benchmark. If the SSR=1, it means the strategy is using BS delta for hedging. Also, estimating SSR needs some efforts practically. We here use the assumption of SSR to be a fixed value (2 for example) across all underlyings for quick turnover, and the results are compared with estimating SSR dynamically via the regression method described above.

When we calculate the delta to hedge, we use the following formula:

$$
{ \begin{array} { l } { { S k e w D e l t a _ { t } } = . B S D e l t a _ { k } + { \frac { V e g a } { S } } \times ( S S R - 1 ) \times L o c a l S k e w } \\ { . L o c a l S k e w = } \\ { \left. { d l n ( K ) } \right| _ { K = k } } \end{array} }
$$

Figure 4: Dispersion 3m ATM straddle with different SSR assumptions
![](images/9616c33be2633ce0ec4b7266c42c1e89151f88fd1d1c6fdb74e3842562256243.jpg)

Figure 5: Dispersion 3m ATM straddle with different SSR assumptions and apply only on single stocks
![](images/f1da55d977703bd74539ec1d1f8e85847e67441fdf7b9da5b528944945cf7ad7.jpg)

<table><tr><td>Dispersion Performance (Since 2015)</td><td>3m ATM Straddle SSR=1 (BS Delta)</td><td>3m ATM Straddle SSR=2</td><td>3m ATM Straddle Dynamic SSR</td><td>3m ATM Straddle SSR=2 with skew adj delta on single stocks only</td><td>3m ATM Straddle Dynamic SSR with skew adj delta on single stocks</td></tr><tr><td>Annualized Return</td><td>4.3%</td><td>1.1%</td><td>4.3%</td><td>6.8%</td><td>only 5.9%</td></tr><tr><td>Annualized Volatility</td><td>7.3%</td><td>11.4%</td><td>7.8%</td><td>7.0%</td><td>6.9%</td></tr><tr><td>Sharpe Ratio</td><td>0.58</td><td>0.10</td><td>0.55</td><td>0.96</td><td>0.86</td></tr><tr><td>Max Drawdown</td><td>-11.2%</td><td>-33.4%</td><td>-15.3%</td><td>-5.9%</td><td>-7.7%</td></tr></table>

## Source: J.P. Morgan

Because the skew tends to be negative, the skew delta tends to be smaller than BS delta, and therefore, leading to long (short) bias when delta hedging long (short) options positions if compared with delta hedging through BS delta. One observation we have from Figure 4 is that the strategy with skew delta hedging has very negative carry although the performance during stress period is enhanced. One reason might be the skew adjusted term on SPX is dominating due to its higher skew slope compared to single stocks in general. To improve the performance, we introduce the versions that apply skew delta on single stocks only and use BS delta to hedge index leg. Although it might create a bit of long delta bias, it can potentially be offset by the long vol bias from the options side during the stress period. As one can see from Figure 5Disperon 3mATMtadl whf SRu y gck, the performance is improved significantly, and the Sharpe ratios are around 0.9, compared to the basic version of 0.58.

We continue our analysis on the vanilla var strip and optimal var strip implementation described before. Similarly, we see that the dispersion strategy using skew delta hedging on single stocks leg and BS delta hedging on index leg can outperform the one with BS delta hedging significantly.

## 3m vanilla var strip dispersions with skew adjusted delta hedging

Figure 6: Dispersion 3m vanilla var strip with different SSR assumptions

![](images/84b4fa60a4ec426b30a2e0ac5d054bddae11299a8bf1dfc0507fb034ca62ea7e.jpg)

Figure 7: Dispersion 3m vanilla var strip with different SSR assumptions and apply only on single stocks
![](images/c0edbef3c210711b4f31424cdcf2464a87406a87ef4f2ac0b89db834fbfbf2a8.jpg)

<table><tr><td>Dispersion Performance (Since 2015)</td><td>3m Vanilla Var Strip SSR=1 (BS Delta)</td><td>3m Vanilla Var Strip SSR=2</td><td>3m Vanilla Var Strip Dynamic SSR</td><td>3m Vanilla Var Strip SSR=2 with skew adj delta on single stocks</td><td>3m Vanilla Var Strip Dynamic SSR with skew adj delta on single stocks</td></tr><tr><td>Annualized Return</td><td>5.5%</td><td>4.6%</td><td>6.2%</td><td>only 8.6%</td><td>only 7.5%</td></tr><tr><td>Annualized Volatility</td><td>9.1%</td><td>10.7%</td><td>9.4%</td><td>10.1%</td><td>9.4%</td></tr><tr><td>Sharpe Ratio</td><td>0.60</td><td>0.43</td><td>0.66</td><td>0.86</td><td>0.80</td></tr><tr><td>Max Drawdown</td><td>-14.5%</td><td>-21.3%</td><td>-17.8%</td><td>-10.9%</td><td>-12.3%</td></tr></table>

Source: J.P. Morgan

## 3m optimal var strip dispersion skew adjusted delta hedging

Figure 8: Dispersion 3m optimal var strip with different SSR assumptions

![](images/0a9d521f6e202ad5b77720f5c0dac795dc18341c9dc72e890ce0ff7d09c0a6d5.jpg)

Figure 9: Dispersion 3m optimal var strip with different SSR assumptions and apply only on single stocks

![](images/efeeb08b2814a5539e2ad2be7ab72baa60aa9a5945ec67420688b5515c6eb320.jpg)

<table><tr><td>Dispersion Performance (Since 2015)</td><td>3m Optimal Var Strip SSR=1 (BS Delta)</td><td>3m Optimal Var Strip SSR=2</td><td>3m Optimal Var Strip Dynamic SSR</td><td>3m Optimal Var Strip SSR=2 with skew adj delta on single stocks</td><td>3m Optimal Var Strip Dynamic SSR with skew adj delta on single stocks</td></tr><tr><td>Annualized Return</td><td>5.7%</td><td>5.0%</td><td>6.6%</td><td>only 8.9%</td><td>only 7.8%</td></tr><tr><td>Annualized Volatility</td><td>9.1%</td><td>10.7%</td><td>9.5%</td><td>10.2%</td><td>9.5%</td></tr><tr><td>Sharpe Ratio</td><td>0.63</td><td>0.47</td><td>0.69</td><td>0.88</td><td>0.83</td></tr><tr><td>Max Drawdown</td><td>-15.2%</td><td>-21.4%</td><td>-18.5%</td><td>-11.2%</td><td>-12.9%</td></tr></table>

Source: J.P. Morgan

## Systematic Dispersion

## Benchmark Performance

Since the previous publication in mid November, our 3m and 6m benchmark dispersion strategies are down by -2.4% and -2.5%, respectively. The drawdown is mainly due to the shrinkage of realized volatility spread (or higher realized correlation), as the macro news of US rates pivoting and the expectation of Fed cutting in 2024 dominating the single stocks performance instead of their idiosyncratic risks. The 1 year performance of our dispersion benchmarks are in the negative territory.

In Figure 10Systemaic Dpron Bhk Pf (FulH) and Figure 11Systemaic Dpron Bhk Pf (L1Y), we show the historical performance of SPX dispersion benchmarks of 3M and 6M maturity.

Figure 10: Systematic Dispersion Benchmark Performance (Full History)
![](images/f1faa9776f3fff902583c5952d10f6f4b0c7fc4a8cd15edf010d183a9331c564.jpg)

Figure 11: Systematic Dispersion Benchmark Performance (Last 1 Year)
![](images/b13b87354f001801bd578cabba0cee53b4f371ab3494e27bbcd74a0ef25d1008.jpg)

Table 1: Dispersion strategy performance
<table><tr><td>Performance Statistics</td><td>3m ATM Straddle (Full History)</td><td>6m ATM Straddle (Full History)</td><td>3m ATM Straddle (1 Year)</td><td>6m ATM Straddle (1 Year)</td></tr><tr><td>Annual Return</td><td>4.3%</td><td>2.0%</td><td>-1.3%</td><td>-1.5%</td></tr><tr><td>Annual Volatility</td><td>7.3%</td><td>5.6%</td><td>4.3%</td><td>3.3%</td></tr><tr><td>Sharpe Ratio</td><td>0.58</td><td>0.36</td><td>-0.30</td><td>-0.45</td></tr><tr><td>Max Drawdown</td><td>-11.2%</td><td>-13.5%</td><td>-5.6%</td><td>-4.6%</td></tr></table>

Source: J.P. Morgan

The benchmarks are constructed as follows:

• Select top 50 SPX components by market caps.

• Long ATM Straddles with expiry closest to 3 months (6 months), with end-of-day delta hedging.

• Short SPX ATM Straddles with expiry closest to 3 months (6 months), with end-of-day delta hedging.

• New trades are Vega neutral with SPX rolling Vega target to be 1%, equivalent to 3.17 bps (1.58 bps) per day.

• All positions are held to maturity.

• The performance is net of transaction costs.

## Dispersion Analytics

Figure 12: Historical Implied Volatility Spread
![](images/c58e15a5219ec2289dfa68bfcd5be7804275dba1dc8ce25fe9cd0aa2bf794f0c.jpg)
Source: J.P. Morgan

Table 2: Historical Implied Volatility Spread Statistics
<table><tr><td>Current Entry Point</td><td>Percentile 1Y</td><td>Z-Score 1Y</td></tr><tr><td>3M Implied Volatility Spread</td><td>92.1%</td><td>1.29</td></tr><tr><td>6M Implied Volatility Spread</td><td>85.7%</td><td>1.10</td></tr></table>

Source: J.P. Morgan

Figure 13: Historical Carry
![](images/4c932d4e2cb259a0d9d3232e06fc2f0ac017d77af392a445bb2aecaa46d7c6eb.jpg)
Date
Source: J.P. Morgan

Carry is defined as the implied volatility spread minus the trailing realized volatility spread over the corresponding tenor.

Table 3: Historical Implied Volatility Spread Statistics
<table><tr><td>Current Entry Point</td><td>Percentile 1Y</td><td>Z-Score 1Y</td></tr><tr><td>3M Carry</td><td>23.8%</td><td>-0.97</td></tr><tr><td>6M Carry</td><td>0.4%</td><td>-2.31</td></tr></table>

Source: J.P. Morgan

Figure 14: SPX Top 50 ATM Implied Volatility Spread Term Structure vs. Trailing 6M Realized Volatility Spread
![](images/f05c6f1af37804c296d3c06e10d09b2ab90cba2fe79998ae7b7363c61721075f.jpg)

In Figure 14, the implied volatility spread for short dated (<3m) moved down since four weeks ago and reverted back compared to one week ago. The realized implied volatility spread (trailing 6m) is below the current implied volatility spread for all tenors, indicating a less appealing entry point.
Figure 15: SPX Top 50 Implied Volatility Spread Skew vs. Trailing 6M Realized Volatility Spread
![](images/0fa75001156dcf060bd33ca0884d17d1038f32bc17ccdaf0b0bfef0fb07f7f05.jpg)

Figure 16: SPX Top 50 ATM Implied Correlation Term Structure vs. Trailing 6M Realized Correlation
![](images/5af6e21dbdf67775252f13f1ce747b99c133fdd47f7a859f4da38bdf8dfaf167.jpg)

In Figure 16, the implied correlations remained largely unchanged in the past 4 weeks. The realized correlation was high comparing to the implied correlation with tenor less than 6m, indicating a less attractive entry point for tactical traders.
Figure 17: SPX Top 50 ATM Implied Correlation Skew vs. Trailing 6M Realized Correlation
![](images/5473ee20e15f28bec8d0843552db2c97e06971cd8b2b8d30d1b79d6e44cbe17d.jpg)

Figure 18: SPX 500 Reporting Calendar
% of SPX 500 Market Cap vs. # of Companies Reporting
![](images/3e31a27567ac8aaeebba695c6b16fc3413941d86d9a348d7ba08a55f408a8b17.jpg)
Source: J.P. Morgan

## Risks of Common Option Strategies

Risks to Strategies: Not all option strategies are suitable for investors; certain strategies may expose investors to significant potential losses. We have summarized the risks of selected derivative strategies. For additional risk information, please call your sales representative for a copy of “Characteristics and Risks of Standardized Options.<sup>”</sup> We advise investors to consult their tax advisors and legal counsel about the tax implications of these strategies. Please also refer to option risk disclosure documents.

Put Sale: Investors who sell put options will own the underlying asset if the asset<sup>’</sup>s price falls below the strike price of the put option. Investors, therefore, will be exposed to any decline in the underlying asset<sup>’</sup>s price below the strike potentially to zero, and they will not participate in any price appreciation in the underlying asset if the option expires unexercised.

Call Sale: Investors who sell uncovered call options have exposure on the upside that is theoretically unlimited.

Call Overwrite or Buywrite: Investors who sell call options against a long position in the underlying asset give up any appreciation in the underlying asset<sup>’</sup>s price above the strike price of the call option, and they remain exposed to the downside of the underlying asset in the return for the receipt of the option premium.

Booster : In a sell-off, the maximum realized downside potential of a double-up booster is the net premium paid. In a rally, option losses are potentially unlimited as the investor is net short a call. When overlaid onto a long position in the underlying asset, upside losses are capped (as for a covered call), but downside losses are not.

Collar: Locks in the amount that can be realized at maturity to a range defined by the put and call strike. If the collar is not costless, investors risk losing 100% of the premium paid. Since investors are selling a call option, they give up any price appreciation in the underlying asset above the strike price of the call option.

Call Purchase: Options are a decaying asset, and investors risk losing 100% of the premium paid if the underlying asset<sup>’</sup>s price is below the strike price of the call option.

Put Purchase: Options are a decaying asset, and investors risk losing 100% of the premium paid if the underlying asset<sup>’</sup>s price is above the strike price of the put option.

Straddle or Strangle: The seller of a straddle or strangle is exposed to increases in the underlying asset<sup>’</sup>s price above the call strike and declines in the underlying asset<sup>’</sup>s price below the put strike. Since exposure on the upside is theoretically unlimited, investors who also own the underlying asset would have limited losses should the underlying asset rally. Covered writers are exposed to declines in the underlying asset position as well as any additional exposure should the underlying asset decline below the strike price of the put option. Having sold a covered call option, the investor gives up all appreciation in the underlying asset above the strike price of the call option.

Put Spread: The buyer of a put spread risks losing 100% of the premium paid. The buyer of higher-ratio put spread has unlimited downside below the lower strike (down to zero), dependent on the number of lower-struck puts sold. The maximum gain is limited to the spread between the two put strikes, when the underlying is at the lower strike. Investors who own the underlying asset will have downside protection between the higher-strike put and the lower-strike put. However, should the underlying asset<sup>’</sup>s price fall below the strike price of the lower-strike put, investors regain exposure to the underlying asset, and this exposure is multiplied by the number of puts sold.

Call Spread: The buyer risks losing 100% of the premium paid. The gain is limited to the spread between the two strike prices. The seller of a call spread risks losing an amount equal to the spread between the two call strikes less the net premium received. By selling a covered call spread, the investor remains exposed to the downside of the underlying asset and gives up the spread between the two call strikes should the underlying asset rally.

Butterfly Spread: A butterfly spread consists of two spreads established simultaneously – one a bull spread and the other a bear spread. The resulting position is neutral, that is, the investor will profit if the underlying is stable. Butterfly spreads are established at a net debit. The maximum profit will occur at the middle strike price; the maximum loss is the net debit.

Pricing Is Illustrative Only: Prices quoted in the above trade ideas are our estimate of current market levels, and are not indicative trading levels.

Correction: Corrected wording of definitions on page 1; corrected the formula on page 3; corrected Figure 4, 5, 6, 7, 8, 9, and the stats and commentary that follow the exhibits.

Analyst Certification: The Research Analyst(s) denoted by an “AC<sup>”</sup> on the cover of this report certifies (or, where multiple Research Analysts are primarily responsible for this report, the Research Analyst denoted by an “AC<sup>”</sup> on the cover or within the document individually certifies, with respect to each security or issuer that the Research Analyst covers in this research) that: (1) all of the views expressed in this report accurately reflect the Research Analyst<sup>’</sup>s personal views about any and all of the subject securities or issuers; and (2) no part of any of the Research Analyst's compensation was, is, or will be directly or indirectly related to the specific recommendations or views expressed by the Research Analyst(s) in this report. For all Korea-based Research Analysts listed on the front cover, if applicable, they also certify, as per KOFIA requirements, that the Research Analyst<sup>’</sup>s analysis was made in good faith and that the views reflect the Research Analyst<sup>’</sup>s own opinion,

without undue influence or intervention.

All authors named within this report are Research Analysts who produce independent research unless otherwise specified. In Europe, Sector Specialists (Sales and Trading) may be shown on this report as contacts but are not authors of the report or part of the Research Department.

## Important Disclosures

Company-Specific Disclosures: Important disclosures, including price charts and credit opinion history tables, are available for compendium reports and all J.P. Morgan–covered companies, and certain non-covered companies, by visitinghttps://www.jpmm.com/research/disclosures, calling 1-800-477-0406, or e-mailing research.disclosure.inquiries@jpmorgan.com with your request.

## Explanation of Equity Research Ratings, Designations and Analyst(s) Coverage Universe:

J.P. Morgan uses the following rating system: Overweight (over the duration of the price target indicated in this report, we expect this stock will outperform the average total return of the stocks in the Research Analyst<sup>’</sup>s, or the Research Analyst<sup>’</sup>s team<sup>’</sup>s, coverage universe); Neutral (over the duration of the price target indicated in this report, we expect this stock will perform in line with the average total return of the stocks in the Research Analyst<sup>’</sup>s, or the Research Analyst<sup>’</sup>s team<sup>’</sup>s, coverage universe); and Underweight (over the duration of the price target indicated in this report, we expect this stock will underperform the average total return of the stocks in the Research Analyst<sup>’</sup>s, or the Research Analyst<sup>’</sup>s team<sup>’</sup>s, coverage universe. NR is Not Rated. In this case, J.P. Morgan has removed the rating and, if applicable, the price target, for this stock because of either a lack of a sufficient fundamental basis or for legal, regulatory or policy reasons. The previous rating and, if applicable, the price target, no longer should be relied upon. An NR designation is not a recommendation or a rating. In our Asia (ex-Australia and ex-India) and U.K. small- and mid-cap Equity Research, each stock<sup>’</sup>s expected total return is compared to the expected total return of a benchmark country market index, not to those Research Analysts<sup>’</sup> coverage universe. If it does not appear in the Important Disclosures section of this report, the certifying Research Analyst<sup>’</sup>s coverage universe can be found on J.P. Morgan<sup>’</sup>s Research website, https://www.jpmorganmarkets.com.

## J.P. Morgan Equity Research Ratings Distribution, as of January 01, 2024

<table><tr><td></td><td>Overweight (buy)</td><td>Neutral (hold)</td><td>Underweight (sell)</td></tr><tr><td>J.P. Morgan Global Equity Research Coverage*</td><td>47%</td><td>39%</td><td>13%</td></tr><tr><td rowspan="2">IB clients** JPMS Equity Research Coverage*</td><td>48%</td><td>43%</td><td>32%</td></tr><tr><td>46%</td><td>42%</td><td>12%</td></tr><tr><td>IB clients**</td><td>68%</td><td>63%</td><td>46%</td></tr></table>

\*Please note that the percentages may not add to 100% because of rounding.

\*\*Percentage of subject companies within each of the "buy," "hold" and "sell" categories for which J.P. Morgan has provided investment banking services within the previous 12 months.

For purposes of FINRA ratings distribution rules only, our Overweight rating falls into a buy rating category; our Neutral rating falls into a hold rating category; and our Underweight rating falls into a sell rating category. Please note that stocks with an NR designation are not included in the table above. This information is current as of the end of the most recent calendar quarter.

Equity Valuation and Risks: For valuation methodology and risks associated with covered companies or price targets for covered companies, please see the most recent company-specific research report at http://www.jpmorganmarkets.com, contact the primary analyst or your J.P. Morgan representative, or email research.disclosure.inquiries@jpmorgan.com. For material information about the proprietary models used, please see the Summary of Financials in company-specific research reports and the Company Tearsheets, which are available to download on the company pages of our client website, http://www.jpmorganmarkets.com. This report also sets out within it the material underlying assumptions used.

A history of J.P. Morgan investment recommendations disseminated during the preceding 12 months can be accessed on the Research & Commentary page of http://www.jpmorganmarkets.com where you can also search by analyst name, sector or financial instrument.

Analysts' Compensation:The research analysts responsible for the preparation of this report receive compensation based upon various factors, including the quality and accuracy of research, client feedback, competitive factors, and overall firm revenues.

## Other Disclosures

J.P. Morgan is a marketing name for investment banking businesses of JPMorgan Chase & Co. and its subsidiaries and affiliates worldwide.

UK MIFID FICC research unbundling exemption: UK clients should refer to UK MIFID Research Unbundling exemption for details of J.P.
Morgan<sup>’</sup>s implementation of the FICC research exemption and guidance on relevant FICC research categorisation.

All research material made available to clients are simultaneously available on our client website, J.P. Morgan Markets, unless specifically permitted by relevant laws. Not all research content is redistributed, e-mailed or made available to third-party aggregators. For all research material available on a particular stock, please contact your sales representative.

Any long form nomenclature for references to China; Hong Kong; Taiwan; and Macau within this research material are Mainland China; Hong

Kong SAR (China); Taiwan (China); and Macau SAR (China).

J.P. Morgan Research may, from time to time, write on issuers or securities targeted by economic or financial sanctions imposed or administered by the governmental authorities of the U.S., EU, UK or other relevant jurisdictions (Sanctioned Securities). Nothing in this report is intended to be read or construed as encouraging, facilitating, promoting or otherwise approving investment or dealing in such Sanctioned Securities. Clients should be aware of their own legal and compliance obligations when making investment decisions.

Any digital or crypto assets discussed in this research report are subject to a rapidly changing regulatory landscape. For relevant regulatory advisories on crypto assets, including bitcoin and ether, please see https://www.jpmorgan.com/disclosures/cryptoasset-disclosure.

The author(s) of this research report may not be licensed to carry on regulated activities in your jurisdiction and, if not licensed, do not hold themselves out as being able to do so.

Exchange-Traded Funds (ETFs): J.P. Morgan Securities LLC (“JPMS<sup>”</sup>) acts as authorized participant for substantially all U.S.-listed ETFs. To the extent that any ETFs are mentioned in this report, JPMS may earn commissions and transaction-based compensation in connection with the distribution of those ETF shares and may earn fees for performing other trade-related services, such as securities lending to short sellers of the ETF shares. JPMS may also perform services for the ETFs themselves, including acting as a broker or dealer to the ETFs. In addition, affiliates of JPMS may perform services for the ETFs, including trust, custodial, administration, lending, index calculation and/or maintenance and other services.

Options and Futures related research: If the information contained herein regards options- or futures-related research, such information is available only to persons who have received the proper options or futures risk disclosure documents. Please contact your J.P. Morgan Representative or visit https://www.theocc.com/components/docs/riskstoc.pdf for a copy of the Option Clearing Corporation's Characteristics and Risks of Standardized Options or http://www.finra.org/sites/default/files/Security\_Futures\_Risk\_Disclosure\_Statement\_2018.pdf for a copy of the Security Futures Risk Disclosure Statement.

Changes to Interbank Offered Rates (IBORs) and other benchmark rates: Certain interest rate benchmarks are, or may in the future become, subject to ongoing international, national and other regulatory guidance, reform and proposals for reform. For more information, please consult: https://www.jpmorgan.com/global/disclosures/interbank\_offered\_rates

Private Bank Clients: Where you are receiving research as a client of the private banking businesses offered by JPMorgan Chase & Co. and its subsidiaries (“J.P. Morgan Private Bank<sup>”</sup>), research is provided to you by J.P. Morgan Private Bank and not by any other division of J.P. Morgan, including, but not limited to, the J.P. Morgan Corporate and Investment Bank and its Global Research division.

Legal entity responsible for the production and distribution of research: The legal entity identified below the name of the Reg AC Research Analyst who authored this material is the legal entity responsible for the production of this research. Where multiple Reg AC Research Analysts authored this material with different legal entities identified below their names, these legal entities are jointly responsible for the production of this research. Research Analysts from various J.P. Morgan affiliates may have contributed to the production of this material but may not be licensed to carry out regulated activities in your jurisdiction (and do not hold themselves out as being able to do so). Unless otherwise stated below, this material has been distributed by the legal entity responsible for production. If you have any queries, please contact the relevant Research Analyst in your jurisdiction or the entity in your jurisdiction that has distributed this research material.

## Legal Entities Disclosures and Country-/Region-Specific Disclosures:

Argentina: JPMorgan Chase Bank N.A Sucursal Buenos Aires is regulated by Banco Central de la República Argentina (“BCRA<sup>”</sup>- Central Bank of Argentina) and Comisión Nacional de Valores (“CNV<sup>”</sup>- Argentinian Securities Commission - ALYC y AN Integral N°51). Australia: J.P. Morgan Securities Australia Limited (“JPMSAL<sup>”</sup>) (ABN 61 003 245 234/AFS Licence No: 238066) is regulated by the Australian Securities and Investments Commission and is a Market Participant of ASX Limited, a Clearing and Settlement Participant of ASX Clear Pty Limited and a Clearing Participant of ASX Clear (Futures) Pty Limited. This material is issued and distributed in Australia by or on behalf of JPMSAL only to "wholesale clients" (as defined in section 761G of the Corporations Act 2001). A list of all financial products covered can be found by visiting https://www.jpmm.com/research/disclosures. J.P. Morgan seeks to cover companies of relevance to the domestic and international investor base across all Global Industry Classification Standard (GICS) sectors, as well as across a range of market capitalisation sizes. If applicable, in the course of conducting public side due diligence on the subject company(ies), the Research Analyst team may at times perform such diligence through corporate engagements such as site visits, discussions with company representatives, management presentations, etc. Research issued by JPMSAL has been prepared in accordance with J.P. Morgan Australia<sup>’</sup>s Research Independence Policy which can be found at the following link: J.P. Morgan Australia - Research Independence Policy. Brazil: Banco J.P. Morgan S.A. is regulated by the Comissao de Valores Mobiliarios (CVM) and by the Central Bank of Brazil. Ombudsman J.P. Morgan: 0800-7700847 / 0800-7700810 (For Hearing Impaired) / ouvidoria.jp.morgan@jpmorgan.com. Canada: J.P. Morgan Securities Canada Inc. is a registered investment dealer, regulated by the Canadian Investment Regulatory Organization and the Ontario Securities Commission and is the participating member on Canadian exchanges. This material is distributed in Canada by or on behalf of J.P.Morgan Securities Canada Inc. Chile: Inversiones J.P. Morgan Limitada is an unregulated entity incorporated in Chile. China: J.P. Morgan Securities (China) Company Limited has been approved by CSRC to conduct the securities investment consultancy business. Dubai International Financial Centre (DIFC): JPMorgan Chase Bank, N.A., Dubai Branch is regulated by the Dubai Financial Services Authority (DFSA) and its registered address is Dubai International Financial Centre - The Gate, West Wing, Level 3 and 9 PO Box 506551, Dubai, UAE. This material has been distributed by JP Morgan Chase Bank, N.A., Dubai Branch to persons regarded as professional clients or market counterparties as defined under the DFSA rules. European Economic Area (EEA): Unless specified to the contrary, research is distributed in the EEA by J.P. Morgan SE (“JPM SE<sup>”</sup>), which is authorised as a credit institution by the Federal Financial Supervisory Authority (Bundesanstalt für Finanzdienstleistungsaufsicht, BaFin) and jointly supervised by the

BaFin, the German Central Bank (Deutsche Bundesbank) and the European Central Bank (ECB). JPM SE is a company headquartered in Frankfurt with registered address at TaunusTurm, Taunustor 1, Frankfurt am Main, 60310, Germany. The material has been distributed in the EEA to persons regarded as professional investors (or equivalent) pursuant to Art. 4 para. 1 no. 10 and Annex II of MiFID II and its respective implementation in their home jurisdictions (“EEA professional investors<sup>”</sup>). This material must not be acted on or relied on by persons who are not EEA professional investors. Any investment or investment activity to which this material relates is only available to EEA relevant persons and will be engaged in only with EEA relevant persons. Hong Kong: J.P. Morgan Securities (Asia Pacific) Limited (CE number AAJ321) is regulated by the Hong Kong Monetary Authority and the Securities and Futures Commission in Hong Kong, and J.P. Morgan Broking (Hong Kong) Limited (CE number AAB027) is regulated by the Securities and Futures Commission in Hong Kong. JP Morgan Chase Bank, N.A., Hong Kong Branch (CE Number AAL996) is regulated by the Hong Kong Monetary Authority and the Securities and Futures Commission, is organized under the laws of the United States with limited liability. Where the distribution of this material is a regulated activity in Hong Kong, the material is distributed in Hong Kong by or through J.P. Morgan Securities (Asia Pacific) Limited and/or J.P. Morgan Broking (Hong Kong) Limited. India: J.P. Morgan India Private Limited (Corporate Identity Number - U67120MH1992FTC068724), having its registered office at J.P. Morgan Tower, Off. C.S.T. Road, Kalina, Santacruz - East, Mumbai – 400098, is registered with the Securities and Exchange Board of India (SEBI) as a <sup>‘</sup>Research Analyst<sup>’</sup> having registration number INH000001873. J.P. Morgan India Private Limited is also registered with SEBI as a member of the National Stock Exchange of India Limited and the Bombay Stock Exchange Limited (SEBI Registration Number – INZ000239730) and as a Merchant Banker (SEBI Registration Number - MB/INM000002970). Telephone: 91-22-6157 3000, Facsimile: 91-22- 6157 3990 and Website: http://www.jpmipl.com . JPMorgan Chase Bank, N.A. - Mumbai Branch is licensed by the Reserve Bank of India (RBI) (Licence No. 53/ Licence No. BY.4/94; SEBI - IN/CUS/014/ CDSL : IN-DP-CDSL-444-2008/ IN-DP-NSDL-285-2008/ INBI00000984 INE231311239) as a Scheduled Commercial Bank in India, which is its primary license allowing it to carry on Banking business in India and other activities, which a Bank branch in India are permitted to undertake. For non-local research material, this material is not distributed in India by J.P. Morgan India Private Limited. Compliance Officer: Spurthi Gadamsetty; spurthi.gadamsetty@jpmchase.com; +912261573225. Grievance Officer: Ramprasadh K, jpmipl.research.feedback@jpmorgan.com; +912261573000.

Investment in securities market are subject to market risks. Read all the related documents carefully before investing. Registration granted by SEBI and certification from NISM in no way guarantee performance of the intermediary or provide any assurance of returns to investors.

Indonesia: PT J.P. Morgan Sekuritas Indonesia is a member of the Indonesia Stock Exchange and is registered and supervised by the Otoritas Jasa Keuangan (OJK). Korea: J.P. Morgan Securities (Far East) Limited, Seoul Branch, is a member of the Korea Exchange (KRX). JPMorgan Chase Bank, N.A., Seoul Branch, is licensed as a branch office of foreign bank (JPMorgan Chase Bank, N.A.) in Korea. Both entities are regulated by the Financial Services Commission (FSC) and the Financial Supervisory Service (FSS). For non-macro research material, the material is distributed in Korea by or through J.P. Morgan Securities (Far East) Limited, Seoul Branch. Japan: JPMorgan Securities Japan Co., Ltd. and JPMorgan Chase Bank, N.A., Tokyo Branch are regulated by the Financial Services Agency in Japan. Malaysia: This material is issued and distributed in Malaysia by JPMorgan Securities (Malaysia) Sdn Bhd (18146-X), which is a Participating Organization of Bursa Malaysia Berhad and holds a Capital Markets Services License issued by the Securities Commission in Malaysia. Mexico: J.P. Morgan Casa de Bolsa, S.A. de C.V. and J.P. Morgan Grupo Financiero are members of the Mexican Stock Exchange and are authorized to act as a broker dealer by the National Banking and Securities Exchange Commission. New Zealand: This material is issued and distributed by JPMSAL in New Zealand only to "wholesale clients" (as defined in the Financial Markets Conduct Act 2013). JPMSAL is registered as a Financial Service Provider under the Financial Service providers (Registration and Dispute Resolution) Act of 2008. Philippines: J.P. Morgan Securities Philippines Inc. is a Trading Participant of the Philippine Stock Exchange and a member of the Securities Clearing Corporation of the Philippines and the Securities Investor Protection Fund. It is regulated by the Securities and Exchange Commission. Singapore: This material is issued and distributed in Singapore by or through J.P. Morgan Securities Singapore Private Limited (JPMSS) [MCI (P) 030/08/2023 and Co. Reg. No.: 199405335R], which is a member of the Singapore Exchange Securities Trading Limited, and/or JPMorgan Chase Bank, N.A., Singapore branch (JPMCB Singapore), both of which are regulated by the Monetary Authority of Singapore. This material is issued and distributed in Singapore only to accredited investors, expert investors and institutional investors, as defined in Section 4A of the Securities and Futures Act, Cap. 289 (SFA). This material is not intended to be issued or distributed to any retail investors or any other investors that do not fall into the classes of “accredited investors,<sup>”</sup> “expert investors<sup>”</sup> or “institutional investors,<sup>”</sup> as defined under Section 4A of the SFA. Recipients of this material in Singapore are to contact JPMSS or JPMCB Singapore in respect of any matters arising from, or in connection with, the material. South Africa: J.P. Morgan Equities South Africa Proprietary Limited and JPMorgan Chase Bank, N.A., Johannesburg Branch are members of the Johannesburg Securities Exchange and are regulated by the Financial Services Conduct Authority (FSCA). Taiwan: J.P. Morgan Securities (Taiwan) Limited is a participant of the Taiwan Stock Exchange (company-type) and regulated by the Taiwan Securities and Futures Bureau. Material relating to equity securities is issued and distributed in Taiwan by J.P. Morgan Securities (Taiwan) Limited, subject to the license scope and the applicable laws and the regulations in Taiwan. According to Paragraph 2, Article 7-1 of Operational Regulations Governing Securities Firms Recommending Trades in Securities to Customers (as amended or supplemented) and/or other applicable laws or regulations, please note that the recipient of this material is not permitted to engage in any activities in connection with the material that may give rise to conflicts of interests, unless otherwise disclosed in the “Important Disclosures<sup>”</sup> in this material. Thailand: This material is issued and distributed in Thailand by JPMorgan Securities (Thailand) Ltd., which is a member of the Stock Exchange of Thailand and is regulated by the Ministry of Finance and the Securities and Exchange Commission, and its registered address is 3rd Floor, 20 North Sathorn Road, Silom, Bangrak, Bangkok 10500. UK: Unless specified to the contrary, research is distributed in the UK by J.P. Morgan Securities plc (“JPMS plc<sup>”</sup>) which is a member of the London Stock Exchange and is authorised by the Prudential Regulation Authority and regulated by the Financial Conduct Authority and the Prudential Regulation Authority. JPMS plc is registered in England & Wales No. 2711006, Registered Office 25 Bank Street, London, E14 5JP. This material is directed in the UK only to: (a) persons having professional experience in matters relating to investments falling within article 19(5) of the Financial Services and Markets Act 2000 (Financial Promotion) (Order) 2005 (“the FPO<sup>”</sup>); (b) persons outlined in article 49 of the

FPO (high net worth companies, unincorporated associations or partnerships, the trustees of high value trusts, etc.); or (c) any persons to whom this communication may otherwise lawfully be made; all such persons being referred to as "UK relevant persons". This material must not be acted on or relied on by persons who are not UK relevant persons. Any investment or investment activity to which this material relates is only available to UK relevant persons and will be engaged in only with UK relevant persons. Research issued by JPMS plc has been prepared in accordance with JPMS plc's policy for prevention and avoidance of conflicts of interest related to the production of Research which can be found at the following link: J.P. Morgan EMEA - Research Independence Policy. U.S.: J.P. Morgan Securities LLC (“JPMS<sup>”</sup>) is a member of the NYSE, FINRA, SIPC, and the NFA. JPMorgan Chase Bank, N.A. is a member of the FDIC. Material published by non-U.S. affiliates is distributed in the U.S. by JPMS who accepts responsibility for its content.

General: Additional information is available upon request. The information in this material has been obtained from sources believed to be reliable. While all reasonable care has been taken to ensure that the facts stated in this material are accurate and that the forecasts, opinions and expectations contained herein are fair and reasonable, JPMorgan Chase & Co. or its affiliates and/or subsidiaries (collectively J.P. Morgan) make no representations or warranties whatsoever to the completeness or accuracy of the material provided, except with respect to any disclosures relative to J.P. Morgan and the Research Analyst's involvement with the issuer that is the subject of the material. Accordingly, no reliance should be placed on the accuracy, fairness or completeness of the information contained in this material. There may be certain discrepancies with data and/or limited content in this material as a result of calculations, adjustments, translations to different languages, and/or local regulatory restrictions, as applicable. These discrepancies should not impact the overall investment analysis, views and/or recommendations of the subject company(ies) that may be discussed in the material. J.P. Morgan accepts no liability whatsoever for any loss arising from any use of this material or its contents, and neither J.P. Morgan nor any of its respective directors, officers or employees, shall be in any way responsible for the contents hereof, apart from the liabilities and responsibilities that may be imposed on them by the relevant regulatory authority in the jurisdiction in question, or the regulatory regime thereunder. Opinions, forecasts or projections contained in this material represent J.P. Morgan's current opinions or judgment as of the date of the material only and are therefore subject to change without notice. Periodic updates may be provided on companies/industries based on company-specific developments or announcements, market conditions or any other publicly available information. There can be no assurance that future results or events will be consistent with any such opinions, forecasts or projections, which represent only one possible outcome. Furthermore, such opinions, forecasts or projections are subject to certain risks, uncertainties and assumptions that have not been verified, and future actual results or events could differ materially. The value of, or income from, any investments referred to in this material may fluctuate and/or be affected by changes in exchange rates. All pricing is indicative as of the close of market for the securities discussed, unless otherwise stated. Past performance is not indicative of future results. Accordingly, investors may receive back less than originally invested. This material is not intended as an offer or solicitation for the purchase or sale of any financial instrument. The opinions and recommendations herein do not take into account individual client circumstances, objectives, or needs and are not intended as recommendations of particular securities, financial instruments or strategies to particular clients. This material may include views on structured securities, options, futures and other derivatives. These are complex instruments, may involve a high degree of risk and may be appropriate investments only for sophisticated investors who are capable of understanding and assuming the risks involved. The recipients of this material must make their own independent decisions regarding any securities or financial instruments mentioned herein and should seek advice from such independent financial, legal, tax or other adviser as they deem necessary. J.P. Morgan may trade as a principal on the basis of the Research Analysts<sup>’</sup> views and research, and it may also engage in transactions for its own account or for its clients<sup>’</sup> accounts in a manner inconsistent with the views taken in this material, and J.P. Morgan is under no obligation to ensure that such other communication is brought to the attention of any recipient of this material. Others within J.P. Morgan, including Strategists, Sales staff and other Research Analysts, may take views that are inconsistent with those taken in this material. Employees of J.P. Morgan not involved in the preparation of this material may have investments in the securities (or derivatives of such securities) mentioned in this material and may trade them in ways different from those discussed in this material. This material is not an advertisement for or marketing of any issuer, its products or services, or its securities in any jurisdiction.

Confidentiality and Security Notice: This transmission may contain information that is privileged, confidential, legally privileged, and/or exempt from disclosure under applicable law. If you are not the intended recipient, you are hereby notified that any disclosure, copying, distribution, or use of the information contained herein (including any reliance thereon) is STRICTLY PROHIBITED. Although this transmission and any attachments are believed to be free of any virus or other defect that might affect any computer system into which it is received and opened, it is the responsibility of the recipient to ensure that it is virus free and no responsibility is accepted by JPMorgan Chase & Co., its subsidiaries and affiliates, as applicable, for any loss or damage arising in any way from its use. If you received this transmission in error, please immediately contact the sender and destroy the material in its entirety, whether in electronic or hard copy format. This message is subject to electronic monitoring: https://www.jpmorgan.com/disclosures/email

MSCI: Certain information herein (“Information<sup>”</sup>) is reproduced by permission of MSCI Inc., its affiliates and information providers (“MSCI<sup>”</sup>) ©2024. No reproduction or dissemination of the Information is permitted without an appropriate license. MSCI MAKES NO EXPRESS OR IMPLIED WARRANTIES (INCLUDING MERCHANTABILITY OR FITNESS) AS TO THE INFORMATION AND DISCLAIMS ALL LIABILITY TO THE EXTENT PERMITTED BY LAW. No Information constitutes investment advice, except for any applicable Information from MSCI ESG Research. Subject also to msci.com/disclaimer

"Other Disclosures" last revised February 03, 2024.

Copyright 2024 JPMorgan Chase & Co. All rights reserved. This material or any portion hereof may not be reprinted, sold or redistributed without the written consent of J.P. Morgan. It is strictly prohibited to use or share without prior written consent from J.P. Morgan any research material received from J.P. Morgan or an authorized third-party (“J.P. Morgan Data”) in any third-party artificial intelligence (“AI”) systems or models when such J.P. Morgan Data is accessible by a third-party. It is permissible to use J.P.

Morgan Data for internal business purposes only in an AI system or model that protects the confidentiality of J.P. Morgan Data so as to prevent any and all access to or use of such J.P. Morgan Data by any third-party.

Completed 22 Feb 2024 02:20 AM EST

Disseminated 22 Feb 2024 07:00 AM EST