## DB QIS Research Long-Only Factor Investing

#PositiveImpact

March 2024

Clayton Gillespie Gianpaolo Tomasi

Research Team

Vivek Anand Clayton Gillespie Caio Natividade Gianpaolo Tomasi

## Long-Only Multifactor Investing

## Introduction Aims of a Long-only Equity Investor

o Maximize the outperformance over the benchmark

➢ We seek to effectively capture factor premia systematically

o Realize similar (or less) volatility than the benchmark

➢ We use an MVO approach penalizing specific risk only

o Generate drawdowns lower than the benchmark

➢ We add a constraint on the portfolio’s historic drawdowns

<table><tr><td rowspan=1 colspan=1>Constraint</td><td rowspan=1 colspan=1>Value</td></tr><tr><td rowspan=1 colspan=1>Portfolio Size</td><td rowspan=1 colspan=1>Greater than or equal to 200 stocks</td></tr><tr><td rowspan=1 colspan=1>Tracking Error</td><td rowspan=1 colspan=1>Less than 4%</td></tr><tr><td rowspan=1 colspan=1>Individual Stock Weights</td><td rowspan=1 colspan=1>Between 0.2% and 2%</td></tr><tr><td rowspan=1 colspan=1>Region and Sector constraints</td><td rowspan=1 colspan=1>{Region, Sector} weight ±5% vs benchmark</td></tr><tr><td rowspan=1 colspan=1>Funding Constraints</td><td rowspan=1 colspan=1>Fully invested, prohibiting cash &amp; leverage</td></tr></table>

## Factor Selection Long-only demands a different approach

![](images/14402d42b1730d2b523709635e106bb17d20e287d88f890702695feeb11f839e.jpg)

We include Value, Quality and Momentum in line with academic research.

We find our PCA-based Reversion construction makes it profitable in net space and diversifying to other factors<sup>1</sup>.

We exclude Low Beta, because in an unlevered framework the portfolio will underperform due to a beta below 1

## Factor Implementation Quality and Value: Owner Series & Financials

Our Value and Quality scores utilize our “Owner Series” framework<sup>1</sup>, which makes accounting adjustments to familiar ratios in order to better reward cash generation and profitable growth.

![](images/edb111f3fd9ca53eaa442276d5f5118d6126db8d5cd58aac04567d8401f697ba.jpg)

• We augment these scores with our research into factors in Financials/Real Estate<sup>2</sup>, which proxies cash flow using dividends and buybacks and rewards low credit risk instead of profitability.

$$
[ 1 + \prod _ { i = 1 } + \pmb { + } \pmb { \cdot } ] ^ { - 1 } + \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } ] = \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb  \pmb { \cdot } \pmb { \cdot } \pmb { \cdot } \pmb { \pmb \cdot } \pmb { \pmb { \cdot } \pmb { \cdot } \pmb } \pmb { \pmb { \cdot } \pmb } \pmb  \pmb { \cdot } \pmb
$$

$$
\Sigma _ { F a c t o r s } = F ^ { \prime } . \Sigma _ { S t o c k s } . F\tag{1}
$$

$$
C o m p o s i t e A l p h a S c o r e _ { j , t } = \sum _ { i } w _ { i , t } F a c t o r _ { j , t }\tag{2}
$$

We prefer to use an ‘Integrated’ methodology at the score level and to combine scores using a risk-parity approach<sup>1</sup>.

This gives more weight to less volatile factors, but also considers correlations such that each factor’s contribution to total risk is equal.

## Risk Optimization Minimizing Specific Risk

Specific Risk

Total Risk

Systematic Risk

$$
\Sigma _ { s p e c i f i c } = \Sigma _ { T o t a l } \ - \Sigma _ { S y s t e m a t i c }\tag{3}
$$

$$
a r g m a x _ { w } \big ( \underbrace { w ^ { \prime } . \alpha - \lambda \times w ^ { \prime } . \Sigma _ { s p e c i f i c } . w \big ) } _ { \big \downarrow }\tag{4}
$$

Increasing function of factor exposure

Independent of factor exposure

• In our MVO approach we penalize only the stock’s specific risk, rather than total risk.

This prevents the optimizer from penalizing factor risk (allowing higher factor exposure).

![](images/d804215f3c0dc5806aabd98577ac2cacda173dd0241e2ddf1f2b75f20fee23e9.jpg)

Together these changes lead to back-tested CAGR improvements of 3.6% p.a. vs MSCI world, net of costs<sup>1</sup>, with the same volatility.

The same strategy only achieves a 1% p.a. CAGR improvement in a total risk framework.

## Results Impact of changing risk aversion

![](images/1ed4e71b888ac2842d8fcfe977b922e450f66f009085f4b68d09e7bf9194dae7.jpg)

![](images/56b08759fd5b813f4a8c2c0646e7d64047909ffcafab3a0b185efda96aeb8fd0.jpg)
• The figures show the impact of the risk aversion parameter, λ.

For total risk, all values of λ result in a strategy volatility far below the benchmark. However, minimizing specific risk allows the investor to achieve the same level of volatility.

• From here on we set λ=1 to equate the benchmark volatility.

## Results Impact of specific risk on portfolio characteristics

![](images/a926e745c970bff09f4a42c35a414b750f62936b118016f74624333ac51d6565.jpg)

![](images/472d3580c09b6c7aa00793b6572de8a8696d31515f441b6de8786e4c7708492f.jpg)

Using Axioma’s risk model, we show (left) that the specific risk approach results in higher Value, Size, Momentum and Market Beta exposures.

Furthermore, in the worst case scenario, the total risk approach generates very concentrated portfolios whereas specific risk results in a much smoother profile.

![](images/b3ce3cb5a2e4e6b7138dcdc9294074b52513284831d93c634385a949433b6bef.jpg)

![](images/f16f47d59ff16e97b7497433e303bca75f85089bf82689cfcbf0d2a89b8c0e7a.jpg)

We show the robustness of our results above by repeating the exercise with an independent set of multifactor scores.

Here we use the scores generated by a long-only construction of our machine learning factor rotation model (NLASR)<sup>1</sup>.

We again see specific risk resulting in the best performance, generating similar (if slightly better) results to our multifactor.

## Drawdown Control Adding to Explicit Constraints

Drawdowns are typically not included in the optimization phase.

Due to diversification, the drawdown (DDp) of a long-only portfolio is less than or equal to the weighted average of the DD of the underlying stocks.

DDp can be modelled as a set of constraints and then added either in the cost function or as constraints (we use the second approach).

Using 5y of historic monthly returns, we define the maximum fraction (φ) of the benchmark DD that the portfolio can exhibit.

This methodology is analogous to computing the covariance matrix and assuming that such a matrix will be a reliable guide to future covariance.

![](images/043e2c624ce408d5ca0269c5f88ed781cae474b263fd2b3bf7ecdcb74a2ee975.jpg)

## Results Drawdown Control

![](images/ee005a30f813159a9fde91f6c28fdd944dfc70b690734db375dd35af0f80fac2.jpg)

• Above we test values of φ between 60% and 90% for relative avgDD. We show that maxDD falls monotonically with φ.

The realized CAGR and volatility are quite similar, with the maximum differences in the 30-40bps region for our range of parameters.

• We note that a φ of 80% achieves a significant increase in returns, a significant reduction on maxDD and similar volatility to the benchmark.

More improvements could be made by considering shrinkage methods and regime-based estimates of drawdowns.

## Further Constraints

Unless they are discontinuous, we prefer a tilting methodology to adding further constraints, such as ESG. This is better suited to noisy signals as errors are more likely to cancel out when no stocks are explicitly excluded.

## Temporary Risk Factors

An investor looking to benefit from a well-defined theme, such as the “Magnificent Seven” should consider constraining the weights of such stocks either to a fixed value, or to a benchmark-relative weight (+/- 1%).

If the investor is trying to capture a more nebulous theme, we would recommend using NLP to identify relevant stocks<sup>1</sup> and to constrain on the exposure of the total portfolio, which again is more robust to noisy measurements of the exposure.

## Appendix

## Value Add of Factor Additions Adding Reversion and Financials

Cumulative additional returns from adding Reversion

![](images/6625540da91dd969dc8d6a01f101e40825be1e92d7bdf1a1101d2bc6cbcbec59.jpg)
Cumulative additional returns from adding Financials V/Q

![](images/bae87cbb8989b6d7da9ab42712633cd73d1345b932564cc2249975e1bf2a59ca.jpg)

## Appendix 1 Important Disclosures \*Other information available upon request

\*Prices are current as of the end of the previous trading session unless otherwise indicated and are sourced from local exchanges via Reuters, Bloomberg and other vendors . Other information is sourced from Deutsche Bank, subject companies, and other sources. For disclosures pertaining to recommendations or estimates made on securities other than the primary subject of this research, please see the most recently published company report or visit our global disclosure look-up page on our website at https://research.db.com/Research/Disclosures/EquityResearchDisclosures. Aside from within this report, important risk and conflict disclosures can also be found at https://research.db.com/Research/Disclosures/Disclaimer. Investors are strongly encouraged to review this information before investing.

## Analyst Certification

The views expressed in this report accurately reflect the personal views of the undersigned lead analyst(s). In addition, the undersigned lead analyst(s) has not and will not receive any compensation for providing a specific recommendation or view in this report. Clayton Gillespie, Gianpaolo Tomasi.

The information and opinions in this report were prepared by Deutsche Bank AG or one of its affiliates (collectively 'Deutsche Bank'). Though the information herein is believed to be reliable and has been obtained from public sources believed to be reliable, Deutsche Bank makes no representation as to its accuracy or completeness. Hyperlinks to third-party websites in this report are provided for reader convenience only. Deutsche Bank neither endorses the content nor is responsible for the accuracy or security controls of those websites.

Effective 13 October 2023, Deutsche Bank AG acquired Numis Corporation Plc and its subsidiaries (the "Numis Group"). Numis Securities Limited ("NSL") is a member of the Numis Group and a firm authorised and regulated by the Financial Conduct Authority (Firm Reference Number: 144822). Deutsche Bank AG provides clients with, amongst other services, Investment Research services. NSL provides clients with, amongst other services, non-independent research services.

During an initial integration process, the research departments of Deutsche Bank AG and NSL will remain operationally distinct. Consequently, disclosures relating to conflicts of interest that may exist for Deutsche Bank AG and/or its affiliates do not currently take into account the business and activities of the Numis Group. The conflicts of interest that may exist for the Numis Group, in relation to the provision of research, can be found on the Numis website at https://www.numis.com/legal-and-regulatory/conditions-and-disclaimers-thatgovern-research-contained-in-the-research-pages-of-this-website. The disclosures on this Numis webpage do not currently take into account the business and activities of Deutsche

Additionally, any detailed conflicts of interest disclosures pertaining to a specific recommendation or estimate made on a security mentioned in this report or which have been included in our most recently published company report or found on our global disclosure look-up page, do not currently take into account the business and activities of the Numis Group. Instead, details of detailed conflicts of interest disclosures for the Numis Group, relating to specific issuers or securities, can be found at: https://library.numis.com/regulatory\_notice. The issuer/security-specific conflict of interest disclosures on this Numis webpage do not take into account the business and activities of Deutsche Bank and/or its affiliates which are not members of the Numis Group.

If you use the services of Deutsche Bank in connection with a purchase or sale of a security that is discussed in this report, or is included or discussed in another communication (oral or written) from a Deutsche Bank analyst, Deutsche Bank may act as principal for its own account or as agent for another person.

Deutsche Bank may consider this report in deciding to trade as principal. It may also engage in transactions, for its own account or with customers, in a manner inconsistent with the views taken in this research report. Others within Deutsche Bank, including strategists, sales staff and other analysts, may take views that are inconsistent with those taken in this research report. Deutsche Bank issues a variety of research products, including fundamental analysis, equity-linked analysis, quantitative analysis and trade ideas. Recommendations contained in one type of communication may differ from recommendations contained in others, whether as a result of differing time horizons, methodologies, perspectives or otherwise. Deutsche Bank and/or its affiliates may also be holding debt or equity securities of the issuers it writes on. Analysts are paid in part based on the profitability of Deutsche Bank AG and its affiliates, which includes investment banking, trading and principal trading revenues.

Opinions, estimates and projections constitute the current judgment of the author as of the date of this report. They do not necessarily reflect the opinions of Deutsche Bank and are subject to change without notice. Deutsche Bank provides liquidity for buyers and sellers of securities issued by the companies it covers. Deutsche Bank research analysts sometimes have shorter-term trade ideas that may be inconsistent with Deutsche Bank's existing longer-term ratings. Some trade ideas for equities are listed as Catalyst Calls on the Research Website (https://research.db.com/Research/), and can be found on the general coverage list and also on the covered company's page. A Catalyst Call represents a high-conviction belief by an analyst that a stock will outperform or underperform the market and/or a specified sector over a time frame of no less than two weeks and no more than three months. In addition to Catalyst Calls, analysts may occasionally discuss with our clients, and with Deutsche Bank salespersons and traders, trading strategies or ideas that reference catalysts or events that may have a near- term or medium-term impact on the market price of the securities discussed in this report, which impact may be directionally counter to the analysts' current 12-month view of total return or investment return as described herein. Deutsche Bank has no obligation to update, modify or amend this report or to otherwise notify a recipient thereof if an opinion, forecast or estimate changes or becomes inaccurate. Coverage and the freguency of changes in market conditions and in both general and companyspecific economic prospects make it difficult to update research at defined intervals. Updates are at the sole discretion of the coverage analyst or of the Research Department Management, and the majority of reports are published at irregular intervals. This report is provided for informational purposes only and does not take into account the particular investment objectives, financial situations, or needs of individual clients. It is not an offer or a solicitation of an offer to buy or sell any financial instruments or to participate in any particular trading strategy. Target prices are inherently imprecise and a product of the analyst's judgment. The financial instruments discussed in this report may not be suitable for all investors, and investors must make their own informed investment decisions. Prices and availability of financial instruments are subject to change without notice, and investment transactions can lead to losses as a result of price fluctuations and other factors. If a financial instrument is denominated in a currency other than an investor's currency, a change in exchange rates may adversely affect the investment. Past performance is not necessarily indicative of future results. Performance calculations exclude transaction costs, unless otherwise indicated. Unless otherwise indicated, prices are current as of the end of the previous trading session and are sourced from local exchanges via Reuters, Bloomberg and other vendors. Data is also sourced from Deutsche Bank, subject companies, and other parties

The Deutsche Bank Research Department is independent of other business divisions of the Bank. Details regarding our organizational arrangements and information barriers we have to prevent and avoid conflicts of interest with respect to our research are available on our website (https://research.db.com/Research/) under Disclaimer.

Macroeconomic fluctuations often account for most of the risks associated with exposures to instruments that promise to pay fixed or variable interest rates. For an investor who is long fixed-rate instruments (thus receiving these cash flows), increases in interest rates naturally lift the discount factors applied to the expected cash flows and thus cause a loss. The longer the maturity of a certain cash flow and the higher the move in the discount factor, the higher will be the loss. Upside surprises in inflation, fiscal funding needs, and FX depreciation rates are among the most common adverse macroeconomic shocks to receivers. But counterparty exposure, issuer creditworthiness, client segmentation, regulation (including changes in assets holding limits for different types of investors), changes in tax policies, currency convertibility (which may constrain currency conversion, repatriation of profits and/or liquidation of positions), and settlement issues related to local clearing houses are also important risk factors. The sensitivity of fixed-income instruments to macroeconomic shocks may be mitigated by indexing the contracted cash flows to inflation, to FX depreciation, or to specified interest rates - these are common in emerging markets. The index fixings may - by construction - lag or mis-measure the actual move in the underlying variables they are intended to track. The choice of the proper fixing (or metric) is particularly important in swaps markets, where floating coupon rates (i.e., coupons indexed to a typically short-dated interest rate reference index) are exchanged for fixed coupons. Funding in a currency that differs from the currency in which coupons are denominated carries FX risk. Options on swaps (swaptions) the risks typical to options in addition to the risks related to rates movements.

Derivative transactions involve numerous risks including market, counterparty default and illiquidity risk. The appropriateness of these products for use by investors depends on the investors' own circumstances, including their tax position, their regulatory environment and the nature of their other assets and liabilities; as such, investors should take expert legal and financial advice before entering into any transaction similar to or inspired by the contents of this publication. The risk of loss in futures trading and options, foreign or domestic, can be substantial. As a result of the high degree of leverage obtainable in futures and options trading, losses may be incurred that are greater than the amount of funds initially deposited - up to theoretically unlimited losses. Trading in options involves risk and is not suitable for all investors. Prior to buying or selling an option, investors must review the 'Characteristics and Risks of Standardized Options", at http://www.optionsclearing.com/about/publications/character-risks.jsp. If you are unable to access the website, please contact your Deutsche Bank representative for a copy of this important document.

Participants in foreign exchange transactions may incur risks arising from several factors, including the following: (i) exchange rates can be volatile and are subject to large fluctuations; (ii) the value of currencies may be affected by numerous market factors, including world and national economic, political and regulatory events, events in equity and debt markets and changes in interest rates; and (iii) currencies may be subject to devaluation or government-imposed exchange controls, which could affect the value of the currency. Investors in securities such as ADRs, whose values are affected by the currency of an underlying security, effectively assume currency risk.

Unless governing law provides otherwise, all transactions should be executed through the Deutsche Bank entity in the investor's home jurisdiction. Aside from within this report, important conflict disclosures can also be found at https://research.db.com/Research/ on each company's research page. Investors are strongly encouraged to review this information before investing.

Deutsche Bank (which includes Deutsche Bank AG, its branches and affiliated companies) is not acting as a financial adviser, consultant or fiduciary to you or any of your agents (collectively, "You" or "Your") with respect to any information provided in this report. Deutsche Bank does not provide investment, legal, tax or accounting advice, Deutsche Bank is not acting as your impartial adviser, and does not express any opinion or recommendation whatsoever as to any strategies, products or any other information presented in the materials. Information contained herein is being provided solely on the basis that the recipient will make an independent assessment of the merits of any investment decision, and it does not constitute a recommendation of, or express an opinion on, any product or service or any trading strategy.

The information presented is general in nature and is not directed to retirement accounts or any specific person or account type, and is therefore provided to You on the express basis that it is not advice, and You may not rely upon it in making Your decision. The information we provide is being directed only to persons we believe to be financially sophisticated, who are capable of evaluating investment risks independently, both in general and with regard to particular transactions and investment strategies, and who understand that Deutsche Bank has financial interests in the offering of its products and services. If this is not the case, or if You are an IRA or other retail investor receiving this directly from us, we ask that you inform us immediately.

In July 2018, Deutsche Bank revised its rating system for short term ideas whereby the branding has been changed to Catalyst Calls ("CC") from SOLAR ideas; the rating categories for Catalyst Calls originated in the Americas region have been made consistent with the categories used by Analysts globally; and the effective time period for CCs has been reduced from a maximum of 180 days to 90 days.

United States: Approved and/or distributed by Deutsche Bank Securities Incorporated, a member of FINRA, NFA and SIPC. Analysts located outside of the United States are employed by non-US affiliates that are not subject to FINRA regulations.

European Economic Area (exc. United Kingdom): Approved and/or distributed by Deutsche Bank AG, a joint stock corporation with limited liability incorporated in the Federal Republic of Germany with its principal office in Frankfurt am Main. Deutsche Bank AG is authorized under German Banking Law and is subject to supervision by the European Central Bank and by BaFin, Germany's Federal Financial Supervisory Authority.

United Kingdom: Approved and/or distributed by Deutsche Bank AG acting through its London Branch at 21 Moorfields, London EC2Y 9DB. Deutsche Bank AG in the United Kingdom is authorised by the Prudential Regulation Authority and is subject to limited regulation by the Prudential Regulation Authority and Financial Conduct Authority. Details about the extent of our authorisation and regulation are available on request.

Hong Kong SAR: Distributed by Deutsche Bank AG, Hong Kong Branch except for any research content relating to futures contracts within the meaning of the Hong Kong Securities and Futures Ordinance Cap. 571. Research reports on such futures contracts are not intended for access by persons who are located, incorporated, constituted or resident in Hono Kong. The author(s) of a research report may not be licensed to carry on regulated activities in Hong Kong and, if not licensed, do not hold themselves out as being able to do so. The provisions set out above in the 'Additional Information' section shall apply to the fullest extent permissible by local laws and regulations, including without limitation the Code of Conduct for Persons Licensed or Registered with the Securities and Futures Commission. This report is intended for distribution only to 'professional investors' as defined in Part 1 of Schedule of the SFO. This document must not be acted or relied on by persons who are not professional investors. Any investment or investment activity to which this document relates is only available to professional investors and will be engaged only with professional investors.

India: Prepared by Deutsche Equities India Private Limited (DEIPL) having CIN: U65990MH2002PTC137431 and registered office at 14th Floor, The Capital, C-70, G Block, Bandra Kurla Complex, Mumbai (India) 400051. Tel: + 91 22 7180 4444. It is registered by the Securities and Exchange Board of India (SEBI) as a Stock broker bearing registration no.: INZ000252437; Merchant Banker bearing SEBI Registration no.: INM000010833 and Research Analyst bearing SEBI Registration no.: INH000001741. DEIPL's Compliance / Grievance officer is Ms. Rashmi Poddar (Tel: +91 22 7180 4929, email ID: complaints.deipl@db.com). Registration granted by SEBI and certification from NISM in no way guarantee performance of DEIPL or provide any assurance of returns to investors. Investment in securities market are subject to market risks. Read all the related documents carefully before investing. DEIPL may have received administrative warnings from the SEBI for breaches of Indian regulations. Deutsche Bank and/or its affiliate(s) may have debt holdings or positions in the subject company. With regard to information on associates, please refer to the "Shareholdings" section in the Annual Report at: https://www.db.com/ir/en/annual-reports.htm.

Japan: Approved and/or distributed by Deutsche Securities Inc.(DSI). Registration number - Registered as a financial instruments dealer by the Head of the Kanto Local Finance Bureau (Kinsho) No. 117. Member of associations: JSDA, Type II Financial Instruments Firms Association and The Financial Futures Association of Japan. Commissions and risks involved in stock transactions - for stock transactions, we charge stock commissions and consumption tax by multiplying the transaction amount by the commission rate agreed with each customer. Stock transactions can lead to losses as a result of share price fluctuations and other factors. Transactions in foreign stocks can lead to additional losses stemming from foreign exchange fluctuations. We may also charge commissions and fees for certain categories of investment advice, products and services. Recommended investment strategies, products and services carry the risk of losses to principal and other losses as a result of changes in market and/or economic trends, and/or fluctuations in market value. Before decidino on the purchase of financial products and/or services, customers should carefully read the relevant disclosures, prospectuses and other documentation.

'Moody's', 'Standard Poor's', and 'Fitch' mentioned in this report are not registered credit rating agencies in Japan unless Japan or 'Nippon' is specifically designated in the name of the entity. Reports on Japanese listed companies not written by analysts of DSI are written by Deutsche Bank Group's analysts with the coverage companies specified by DSI. Some of the foreign securities stated on this report are not disclosed according to the Financial Instruments and Exchange Law of Japan. Target prices set by Deutsche Bank's equity analysts are based on a 12-month forecast period.

Korea: Distributed by Deutsche Securities Korea Co.

South Africa: Deutsche Bank AG Johannesburg is incorporated in the Federal Republic of Germany (Branch Register Number in South Africa: 1998/003298/10).

Singapore: This report is issued by Deutsche Bank AG, Singapore Branch (One Raffles Quay #18-00 South Tower Singapore 048583, 65 6423 8001), which may be contacted in respect of any matters arising from, or in connection with, this report. Where this report is issued or promulgated by Deutsche Bank in Singapore to a person who is not an accredited investor, expert investor or institutional investor (as defined in the applicable Singapore laws and regulations), they accept legal responsibility to such person for its contents.

Taiwan: Information on securities/investments that trade in Taiwan is for your reference only. Readers should independently evaluate investment risks and are solely responsible for their investment decisions. Deutsche Bank research may not be distributed to the Taiwan public media or quoted or used by the Taiwan public media without written consent. Information on securities/instruments that do not trade in Taiwan is for informational purposes only and is not to be construed as a recommendation to trade in such securities/instruments.

Qatar: Deutsche Bank AG in the Qatar Financial Centre (registered no. 00032) is regulated by the Qatar Financial Centre Regulatory Authority. Deutsche Bank AG - QFC Branch may undertake only the financial services activities that fall within the scope of its existing QFCRA license. Its principal place of business in the QFC: Qatar Financial Centre, Tower, West Bay, Level 5, PO Box 14928, Doha, Qatar. This information has been distributed by Deutsche Bank AG. Related financial products or services are only available only to Business Customers, as defined by the Qatar Financial Centre Regulatory Authority.

Ru6ssia: The information, interpretation and opinions submitted herein are not in the context of, and do not constitute, any appraisal or evaluation activity requiring a license in the Russian Federation.

Kingdom of Saudi Arabia: Deutsche Securities Saudi Arabia (DSSA) is a closed joint stock company authorized by the Capital Market Authority of the Kingdom of Saudi Arabia with a license number (No. 37-07073) to conduct the following business activities: Dealing, Arranging, Advising, and Custody activities. DSSA registered office is Faisaliah Tower, 17th Floor, King Fahad Road - Al Olaya District Riyadh, Kingdom of Saudi Arabia P.O. Box 301806.

United Arab Emirates; Deutsche Bank AG in the Dubai International Financial Centre (registered no. 00045) is regulated by the Dubai Financial Services Authority. Deutsche Bank AG - DIFC Branch may only undertake the financial services activities that fall within the scope of its existing DFSA license. Principal place of business in the DIFC: Dubai International Financial Centre, The Gate Village, Building 5, PO Box 504902, Dubai, U.A.E. This information has been distributed by Deutsche Bank AG. Related financial products or services are available only to Professional Clients, as defined by the Dubai Financial Services Authority.

Australia and New Zealand: This research is intended only for 'wholesale clients' within the meaning of the Australian Corporations Act and New Zealand Financial Advisors Act, respectively. Please refer to Australia-specific research disclosures and related information at htps://www.dbresearch.com/PROD/RPS EN-PROD/PROD0000000000521304.xhtml. Where research refers to any particular financial product recipients of the research should consider any product disclosure statement, prospectus or other applicable disclosure document before making any decision about whether to acquire the product. In preparing this report, the primary analyst or an individual who assisted in the preparation of this report has likely been in contact with the company that is the subject of this research for confirmation/clarification of data, facts, statements, permission to use company-sourced material in the report, and/or site-visit attendance. Without prior approval from Research Management, analysts may not accept from current or potential Banking clients the costs of travel, accommodations, or other expenses incurred by analysts attending site visits, conferences, social events, and the like. Similarly, without prior approval from Research Management and Anti-Bribery and Corruption ("ABC") team, analysts may not accept perks or other items of value for their personal use from issuers they cover.

Additional information relative to securities, other financial products or issuers discussed in this report is available upon request. This report may not be reproduced, distributed or published without Deutsche Bank's prior written consent.

Backtested, hypothetical or simulated performance results have inherent limitations. Unlike an actual performance record based on trading actual client portfolios, simulated results are achieved by means of the retroactive application of a backtested model itself designed with the benefit of hindsight. Taking into account historical events the backtesting of performance also differs from actual account performance because an actual investment strategy may be adjusted any time, for any reason, including a response to material, economic or market factors. The backtested performance includes hypothetical results that do not reflect the reinvestment of dividends and other earnings or the deduction of advisory fees, brokerage or other commissions, and any other expenses that a client would have paid or actually paid. No representation is made that any trading strategy or account will or is likely to achieve profits or losses similar to those shown. Alternative modeling techniques or assumptions might produce significantly different results and prove to be more appropriate. Past hypothetical backtest results are neither an indicator nor guarantee of future returns. Actual results will vary, perhaps materially, from the analysis

The method for computing individual E,S,G and composite ESG scores set forth herein is a novel method developed by the Research department within Deutsche Bank AG, computed using a systematic approach without human intervention, Different data providers, market sectors and geographies approach ESG analysis and incorporate the findings in a variety of ways. As such, the ESG scores referred to herein may differ from equivalent ratings developed and implemented by other ESG data providers in the market and may also differ from equivalent ratings developed and implemented by other divisions within the Deutsche Bank Group. Such ESG scores also differ from other ratings and rankings that have historically been applied in research reports published by Deutsche Bank AG. Further, such ESG scores do not represent a formal or official view of Deutsche Bank AG. It should be noted that the decision to incorporate ESG factors into any investment strategy may inhibit the ability to participate in certain investment opportunities that otherwise would be consistent with your investment objective and other principal investment strategies. The returns on a portfolio consisting primarily of sustainable investments may be lower or higher than portfolios where ESG factors, exclusions, or other sustainability issues are not considered, and the investment opportunities available to such portfolios may differ. Companies may not necessarily meet high performance standards on all aspects of ESG or sustainable investing issues; there is also no guarantee that any company will meet expectations in connection with corporate responsibility, sustainability, and/or impact performance.

Copyright © 2024 Deutsche Bank AG