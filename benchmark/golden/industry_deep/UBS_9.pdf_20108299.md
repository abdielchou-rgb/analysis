# Quantitative Monographs Quantifying change in Japan: opportunities in the cross-shareholding network

## Japanese companies own \~12% of total JPX market cap

Cross-shareholdings have been a long-standing feature of the Japanese stock market. While holdings have been in decline since the Abenomics era, they are still significant, accounting for around JPY 120 trillion (\~US\$ 770bn) of market value, or approximately 12% of total market cap. We have created a dataset of monthly holdings across all listed companies in Japan going back to 2005.

## Cross-shareholdings come in many shapes and sizes

Cross-holdings impact both "holders" and "held" stocks. They can be unilateral or bilateral and range from small holdings to cement relationships to significant control positions. Currently, we see more than 42,000 total relationships, including over 900 significant relationships with holdings greater than 10%. They impact all sectors, though Financials are the largest cohort of holders, while holdings are most prevalent in Consumer Discretionary and Industrials.

## Recent top-down and bottom-up changes are set to disrupt the status quo

We believe that renewed policy focus, the structural shift out of deflation and increased investor-level pressure are likely to drive further shifts in the cross-holding landscape. We expect accelerated unwinding in the coming years. With major changes on the horizon for this fundamental feature of the market, we believe explicitly modelling the crossholding network will be increasingly important. Investors have largely had a negative view of cross-holdings, as they may entrench management, are typically viewed as an inefficient use of capital and increase market complexity/opacity. We estimate that net unwinds accelerated to JPY 6.6 trn (or US\$ 42bn) in 2023.

Japan Quantitative

## Quantifiable factors can help investors navigate the cross-holding landscape

At a macro level, we believe that a full unwinding of cross-holdings could be very beneficial for the Japanese market. That said, the plusses and minuses of cross-holdings are more nuanced on a cross-sectional basis. We have created a suite of cross shareholding factors to help investors navigate the shifting backdrop. Of particular note, we find that our Holding Percentage factor can be an improved form of Value and that cross-holding changes are attractive for stock picking.

## Figure 1: A high-level view of Japan's JPY 120 trillion cross-holding network

![](images/7fce9caafcf7a3a2fb7305f038f541330601c18872fc573f45dfd63f176135df.jpg)
Source: UBS Quant Research, FactSet. Based on value of holdings where >10% of shares are held by other listcos.

## Equities

Will Stephens Analyst will.stephens@ubs.com +852-3712 3892

Paul Winter Analyst paul-j.winter@ubs.com +61-2-9324 2080

Jia Li Mok, CFA Analyst jia-li.mok@ubs.com +65-6495 5772

Jessica SU Analyst jessica-hong.su@ubs.com +852-3712 2059

Aaron Guo, CFA Analyst aaron.guo@ubs.com +852-2971 7705

Cathy Fang, PhD Analyst S1460518100001 cathy.fang@ubs.com +86-21-3866 8891

Lynce Wang, FRM Analyst S1460522090001 lynce.wang@ubs.com +86-21-3866 8638

Oliver Antrobus, CFA Analyst
oliver.antrobus@ubs.com +61-3-9242 6467

Claire Jones Analyst claire-c.jones@ubs.com +44-20-7568 1873

Jaiwish Nolan Analyst jaiwish.nolan@ubs.com +1-212-713 1489

James Cameron Analyst james-a.cameron@ubs.com +61-2-9324 2074

Nozomi Moriya Strategist nozomi.moriya@ubs.com +81-3-5208 6260

This report has been prepared by UBS Securities Asia Limited. ANALYST CERTIFICATION AND REQUIRED DISCLOSURES, including information on the Quantitative Research Review published by UBS, begin on page 42. UBS does and seeks to do business with companies covered in its research reports. As a result, investors should be aware that the firm may have a conflict of interest that could affect the objectivity of this report. Investors should consider this report as only a single factor in making their investment decision.

## Contents

Executive Summary . . . . 3 Will Stephens
Analyst
will.stephens@ubs.com
A quick overview of the cross-holding network . . . . . 7 +852-3712 3892
Paul Winter
Analyst
Drivers of unwinding pressure. . . . . 9 paul-j.winter@ubs.com
+61-2-9324 2080
Jia Li Mok, CFA
Creating the dataset. . . 12 Analyst
jia-li.mok@ubs.com
Organizing cross-holdings data 12 +65-6495 5772
Jessica SU
Analyst
The impact of cross-shareholding unwinds (and additions). . . 14 jessica-hong.su@ubs.com
+852-3712 2059
Creating cross-shareholding factors. . . . . . . . . . . . . . . . . 18 Aaron Guo, CFA
Analyst
aaron.guo@ubs.com
Focus Factor: Holding Percentage 19 +852-2971 7705
Focus Factor: Change in Holding Percentage . . 22 Cathy Fang, PhD
Analyst
Focus Factor: Holding Shares Change. . 23 S1460518100001
cathy.fang@ubs.com
+86-21-3866 8891
Potential applications of the Japan cross-shareholding network Lynce Wang, FRM
Analyst
26 S1460522090001
lynce.wang@ubs.com
+86-21-3866 8638
Appendix. . . . . 27 Oliver Antrobus, CFA
Analyst
What are cross-holdings? 27 oliver.antrobus@ubs.com
+61-3-9242 6467
Why should investors care about cross-holdings? . . 28 Claire Jones
Analyst
Japan's cross-shareholding network in charts . . 29 claire-c.jones@ubs.com
+44-20-7568 1873
Jaiwish Nolan
Appendix: Other cross-shareholding factors performance Analyst
jaiwish.nolan@ubs.com
summary. . . . 37 +1-212-713 1489
Factor 1: Holdings Value . 37 James Cameron
Analyst
james-a.cameron@ubs.com
Factor 2: Held Percentage . 38 +61-2-9324 2074
Factor 3: Holdings Less Held Percentage . 39 Nozomi Moriya
Strategist
nozomi.moriya@ubs.com
Factor 4: Holding Shares Change (Banks and Insurance) . 40
+81-3-5208 6260

## Executive Summary

Cross-shareholdings, or instances where a a company holds shares in another listed company, have been a persistent feature of the Japanese stock market for decades. For many years, Japanese companies have been criticized by investors for inefficient use of capital, complicated structures and poor focus on returns. A key component of this has been cross-shareholdings, the complicated web of holdings that Japanese companies have in other listed stocks.

Figure 2: Total market value of cross-shareholdings relative to the overall market
![](images/c4c2ec5c13d8055ad1b7f63340f11a10d73fc4296194807886b706e72cb1cdd5.jpg)
Source: UBS Quant Research, FactSet

Figure 3: Around 12% of the market is held by other listed companies, down from 16% in the mid-2010's
![](images/34ed34ac7de821c281dc7eeb73b8bfb89ea51cd71a6533bfd59001518994c603.jpg)
Source: UBS Quant Research, FactSet

Cross-shareholdings are generally viewed negatively by investors. Common critiques include concerns around financial management (lower capital efficiency and return profiles, bloated balance sheets, persistent undervaluation of underlying holdings via holdco discounts), corporate governance (entrenchment of management across "group companies", de facto lower voting power for minority shareholders, friendly parties on the shareholder registry) and sub-standard operations (inefficient supply chains based around ownership rather than commercial principles, concerns around competitive practices). Our analysis suggests that the market may not be pricing crossshareholdings as negatively as conventional wisdom perceives.

Figure 4: Many of Japan's flagship companies are amongst the largest holders of cross-shareholdings
![](images/a37849c1862e133d8f97accd8b1dad5dcc4deabcfa885610bf3014d5266fc435.jpg)
Source: UBS Quant Research, FactSet

With the onset of Abenomics, more recently through measures enacted by the FSA and JPX and with the growing chorus of an increasingly vocal shareholder base, pressure is mounting to push for more significant rationalization of crossshareholdings. On the back of these changes, we have seen improved disclosure and overall ownership of the market by other listed companies has decreased from \~16% in the mid-2010's to the current level of around 12%. In recent months, we have seen renewed commitment from major players to accelerate cross-shareholding unwinds with notable announcements from the Toyota Group and affiliates, T&D Holdings and Mitsui Fudosan, amongst others. Such announcements have highlighted the re-rating benefits around plans and actions to reduce the number and value of cross-holdings. While major progress has been made, there is still a long way to go with over JPY 120 trn (or US\$ 770bn) in total market value held by other listed companies. While crossholdings are more prevalent in smaller cap stocks, they also impact Japan's most important companies such as Toyota Motor, MUFG, Softbank and NTT.

Figure 5: Around 42,000 cross-holding relationships in Japan
![](images/b9a0fefa5ef299fb0eebeb453751b36396eef9e351236ebaf096563b3406d86a.jpg)
Source: UBS Quant Research, FactSet

Figure 6: Out of \~3,500 stocks in Japan, more than 3,200 stocks have cross-holding relationships
![](images/8383a0afa179bb1ad470b39f207b04eb0cf980ca7fb3e51ba1e1745fae4e8e6f.jpg)
Source: UBS Quant Research, FactSet

To help investors navigate this critical and changing component of the Japanese market, we have created a dataset of monthly cross-shareholding relationships for the broad market. We assess different ways to analyse the relationships amongst cross-holdings by differentiating between "holders" and "held" shares / "holdings", unilateral and bilateral relationships and establish a hierarchy of significance based on relating ownership percentage to degrees of corporate control. We also assess different trends based on company size, as well as sector. Looking at the current network, we identify over 42,000 cross shareholder relationships between 3,223 stocks. Looking at changes in the network, we note that net cross-shareholding unwinds have accelerated in recent years, with JPY 25.6 trn of unwinds over the last 3 years, representing a 20% increase over the previous 3 years.

We create a suite of cross-shareholding factors that can help investors navigate the complex web of cross-holdings in Japan. Japan-specific cross-shareholding signals can help market participants understand their exposure to cross-holdings, take advantage of common risk factors associated with large intercompany positions, identify alpha opportunities and navigate the current environment of accelerating unwinding. A key takeaway from our analysis is that while companies that unwind crossholdings typically see post-event outperformance (especially in recent years), companies adding to or building up new cross-holding positions also have seen relative outperformance. Companies who are not proactive about their portfolios, i.e. those with no changes in holdings, appear to generally underperform in our event studies.

Figure 7: Performance statistics of our cross-holding factors
<table><tr><td>Factor</td><td>Annualised Return</td><td>Annualised Volatility</td><td>Sharpe Ratio</td><td>Maximum DD</td></tr><tr><td>Holding Percentage</td><td>3.2%</td><td>6.7%</td><td>0.474</td><td>-23.9%</td></tr><tr><td>Change in Holding Percentage</td><td>4.6%</td><td>8.0%</td><td>0.574</td><td>-15.2%</td></tr><tr><td>Holding Shares Change</td><td>1.6%</td><td>9.4%</td><td>0.173</td><td>-49.2%</td></tr><tr><td>Holding Shares Change (2019 - 2024)</td><td>7.4%</td><td>8.7%</td><td>0.850</td><td>-15.5%</td></tr><tr><td>Holding Shares Change (Banks &amp; Insurance)</td><td>3.3%</td><td>11.2%</td><td>0.297</td><td>-27.2%</td></tr></table>

Source: UBS Quant Research, FactSet

We find that our Holding Percentage factor is an attractive substitute for Value factors in Japan. It looks at the relative value of holdings compared to a holder's market cap. We also identify the Change in Holding Percentage and Holding Shares Change as attractive signals. We have tested a variety of other factors associated with cross-shareholdings, such as Value of Holdings (holder's perspective), Held Percentage (held stock or holding's perspective), Net Cross-holding Percentage (value of a company's holdings less the amount the company is held by other stocks), as well as how the periodic changes in these factors perform.

Understanding the dynamics of cross-shareholdings will remain critical in assessing Japanese stocks for the foreseeable future as pressure continues to build for further rationalization of holdings. Changes can impact secondary placements, potential M&A and MBO transactions, further flexibility for increased shareholder returns (as buybacks from "cross-held" companies are a typical mechanism for facilitating unwinds from holders) and impact profitability and return metrics. We believe that understanding the cross-shareholding network can benefit both systematic / quant-driven approaches in Japan, as well as provide additional points of conviction for fundamental stock pickers.

Latest top- and bottom-ranked stocks from our 3 cross-shareholding models can be seen below. The latest screens can be found below.

Figure 8: Latest screen for our Holding Percentage factor
<table><tr><td colspan="6"></td></tr><tr><td>Date</td><td>Ticker</td><td>Security Name</td><td>Sector</td><td>Holding Percentage</td><td>Holding Percentage Bucket</td></tr><tr><td>2024-04-30</td><td>2168-JP</td><td>Pasona Group Inc.</td><td>Industrials</td><td>206.8%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>8368-JP</td><td>Hyakugo Bank, Ltd.</td><td>Financials</td><td>172.2%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>8386-JP</td><td>Hyakujushi Bank, Ltd.</td><td>Financials</td><td>171.9%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>8522-JP</td><td>Bank of Nagoya, Ltd.</td><td>Financials</td><td>160.3%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>8361-JP</td><td>Ogaki Kyoritsu Bank, Ltd</td><td>Financials</td><td>155.2%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>9009-JP</td><td>Keisei Electric Railway Co., Ltd.</td><td>Industrials</td><td>150.0%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>9401-JP</td><td>TBS HOLDINGS INC.</td><td>Communication Services</td><td>133.3%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>5844-JP</td><td>Kyoto Financial Group,Inc.</td><td>Financials</td><td>131.2%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>8359-JP</td><td>Hachijuni Bank, Ltd.</td><td>Financials</td><td>117.1%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>8366-JP</td><td>Shiga Bank, Ltd.</td><td>Financials</td><td>114.4%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>4595-JP</td><td>Mizuho Medy Co., Ltd.</td><td>Health Care</td><td>0.0%</td><td>Q1</td></tr><tr><td>2024-04-30</td><td>4519-JP</td><td>Chugai Pharmaceutical Co., Ltd.</td><td>Health Care</td><td>0.0%</td><td>Q1</td></tr><tr><td>2024-04-30</td><td>4151-JP</td><td>Kyowa Kirin Co., Ltd.</td><td>Health Care</td><td>0.0%</td><td>Q1</td></tr><tr><td>2024-04-30</td><td>7187-JP</td><td>J-LEASE CO., LTD.</td><td>Financials</td><td>0.0%</td><td>Q1</td></tr><tr><td>2024-04-30</td><td>3844-JP</td><td>Comture Corporation</td><td>Information Technology</td><td>0.0%</td><td>Q1</td></tr><tr><td>2024-04-30</td><td>3475-JP</td><td>Good Com Asset Co.,Ltd.</td><td>Real Estate</td><td>0.0%</td><td>Q1</td></tr><tr><td>2024-04-30</td><td>6967-JP</td><td>Shinko Electric Industries Co., Ltd.</td><td>Information Technology</td><td>0.0%</td><td>Q1</td></tr><tr><td>2024-04-30</td><td>9450-JP</td><td>Fibergate, Inc.</td><td>Communication Services</td><td>0.0%</td><td>Q1</td></tr><tr><td>2024-04-30</td><td>3349-JP</td><td>COSMOS Pharmaceutical Corporation</td><td>Consumer Staples</td><td>0.0%</td><td>Q1</td></tr><tr><td>2024-04-30</td><td>7741-JP</td><td>HOYA CORPORATION</td><td>Health Care</td><td>0.0%</td><td>Q1</td></tr></table>

Source: UBS Quant Research, FactSet

Figure 9: Latest screen for our Change in Holding Percentage factor
<table><tr><td>Date</td><td>Ticker</td><td>Security Name</td><td>Sector</td><td>Change in Holding Percentage</td><td>Change in Holding Percentage Bucket</td></tr><tr><td>2024-04-30</td><td>2168-JP</td><td>Pasona Group Inc.</td><td>Industrials</td><td>39.3%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>9171-JP</td><td>Kuribayashi Steamship Co., Ltd.</td><td>Industrials</td><td>22.7%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>8386-JP</td><td>Hyakujushi Bank, Ltd.</td><td>Financials</td><td>8.3%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>4819-JP</td><td>Digital Garage, Inc.</td><td>Information Technology</td><td>8.1%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>3865-JP</td><td>Hokuetsu Corporation</td><td>Materials</td><td>7.3%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>8091-JP</td><td>NICHIMO CO., LTD.</td><td>Consumer Staples</td><td>7.0%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>8366-JP</td><td>Shiga Bank, Ltd.</td><td>Financials</td><td>6.8%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>6178-JP</td><td>JAPAN POST HOLDINGS Co., Ltd.</td><td>Financials</td><td>6.6%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>8388-JP</td><td>Awa Bank, Ltd.</td><td>Financials</td><td>6.3%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>3656-JP</td><td>KLab Inc.</td><td>Communication Services</td><td>6.2%</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>4112-JP</td><td>Hodogaya Chemical Co., Ltd.</td><td>Materials</td><td>-7.0%</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>6058-JP</td><td>VECTOR Inc.</td><td>Communication Services</td><td>-8.3%</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>9009-JP</td><td>Keisei Electric Railway Co., Ltd.</td><td>Industrials</td><td>-9.4%</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>8361-JP</td><td>Ogaki Kyoritsu Bank, Ltd.</td><td>Financials</td><td>-10.2%</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>3915-JP</td><td>TerraSky Co., Ltd.</td><td>Information Technology</td><td>-11.3%</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>8522-JP</td><td>Bank of Nagoya, Ltd.</td><td>Financials</td><td>-14.5%</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>9605-JP</td><td>Toei Company, Ltd.</td><td>Communication Services</td><td>-14.8%</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>9449-JP</td><td>GMO Internet Group, Inc.</td><td>Information Technology</td><td>-18.8%</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>4992-JP</td><td>Hokko Chemical Industry Co., Ltd.</td><td>Materials</td><td>-22.7%</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>3182-JP</td><td>Oisix ra daichi, Inc.</td><td>Consumer Staples</td><td>-71.6%</td><td>-Q3</td></tr></table>

Source: UBS Quant Research, FactSet

Figure 10: Latest screen for our Holding Shares Change factor
<table><tr><td colspan="4"></td><td>Holding Shares</td><td>Holding Shares</td></tr><tr><td>Date</td><td>Ticker</td><td>Security Name</td><td>Sector</td><td>Change</td><td>Change Bucket</td></tr><tr><td>2024-04-30</td><td>4005-JP</td><td>Sumitomo Chemical Co., Ltd.</td><td>Materials</td><td>(2,434,871,200)</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>8411-JP</td><td>Mizuho Financial Group, Inc.</td><td>Financials</td><td>(2,823,992,788)</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>9432-JP</td><td>Nippon Telegraph and Telephone Corporation</td><td>Communication Services</td><td>(2,950,582,600)</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>5192-JP</td><td>Mitsuboshi Belting Ltd.</td><td>Industrials</td><td>(3,466,400,000)</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>8242-JP</td><td>H2O Retailing Corporation</td><td>Consumer Staples</td><td>(18,496,496,328)</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>6902-JP</td><td>DENSO CORPORATION</td><td>Consumer Discretionary</td><td>(44,559,441,000)</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>8306-JP</td><td>Mitsubishi UFJ Financial Group, Inc.</td><td>Financials</td><td>(85,266,898,085)</td><td>-Q3</td></tr><tr><td>2024-04-30</td><td>3289-JP</td><td>Tokyu Fudosan Holdings Corp.</td><td>Real Estate</td><td>714,455,000</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>8308-JP</td><td>Resona Holdings, Inc.</td><td>Financials</td><td>1,500,958,200</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>8088-JP</td><td>Iwatani Corporation</td><td>Energy</td><td>1,892,250,000</td><td>Q3</td></tr><tr><td>2024-04-30</td><td>9435-JP</td><td>Hikari Tsushin, Inc.</td><td>Industrials</td><td>9,564,615,916</td><td>Q3</td></tr></table>

Source: UBS Quant Research, FactSet

# A quick overview of the cross-holding network

The prevalence of cross-holdings in Japan remains significant and is a unique and defining characteristic of the Japanese market, with around 12% of Japanese market cap, or JPY 120 trillion, held by other listed Japanese corporates. Cross-shareholdings impact over 3,200 of Japan's listed companies, and understanding where cross-holdings are most prevalent can help navigate different risks and opportunities amongst Japanese stocks. For a more detailed descriptive summary of the nature of Japanese crossholdings, please see the Appendix.

Figure 11: Large cross-holdings (>10%) sector network
![](images/5a311c78bf6e052f9e4db51947a6eee4d8234d83803d2fab98e115012e6c744f.jpg)
Source: UBS Quant Research, FactSet. From the perspective of Holders. Node sizes are proportionate to large cross-holdings market cap held by companies in each sector

Figure 12: All cross-holdings value sector split - Financials dominate as top holders
![](images/ad90331093a5cd249e4f16fa6adac106920c7458a3ae7ee2e245991959f62822.jpg)
Source: UBS Quant Research, FactSet. Calculated by taking the cross-holdings market cap held by companies in each sector divided by total cross-holdings market cap

Sector considerations. Cross-shareholdings impact every sector in Japan, with some notable differences observed across sectors. From a held stocks perspective, Industrials and Consumer Discretionary stand out as the sectors with the highest impact from crossholders. From a holders perspective, Financials dominate, with Industrials seeing the second largest concentration of value in cross-holdings. Over the last 5 years, Communication Services has seen the largest increase in cross-holding activity for any sector from both a held stocks and holders perspective. This likely reflects the Softbank / Softbank Corp restructuring in late 2018.

Size considerations. Looking at different company size bands, large caps are associated with a slightly lower impact from cross-shareholdings, with around 10% market cap held by other listed companies. Mid caps have around 14% of market cap cross-held, while small caps have the largest percentage held by other listed companies, at around 17%. The decline in the percentage of cross-holders on company registries from their highs in the mid-2010s has been more significant in the small- and mid-cap spaces, with declines of 7% and 6%, respectively. This compares to a decrease of only around 4% for large caps.

Holding size distribution. Looking at the distribution of cross-held stocks by the magnitude of combined holdings, stocks with less than 10% of their registry owned by other listed companies account for 73.5% of the total universe of cross-held stocks by number. Stocks with greater than 10% but less than 33.3% of market cap held by crossholders account for about 16.8% of total cross-held stocks, while those greater than 33.3% account for about 9.7% of total cross-held stocks by count.

Holding type split. There are more than 42,000 different relationships roughly split between bilateral and unilateral relationships, with unilateral holdings being more prevalent in significant cross-holdings. At the company level, around 60% of stocks have at least one bilateral cross-holding, while 30% have only unilateral holders and 10% have no cross holders.

Key stocks in the cross-holding network. We provide screens of different companies which stand out from a cross-shareholding perspective, highlighting the stocks with the largest portfolios of cross-holdings by market value (Toyota, MUFG, Japan Post), as well as leaders by count of holdings (MUFG, Mizuho, SMFG). We also highlight stocks that are the most held by other companies (Mitsubishi Logisnext, Toei Animation, Modec) and the holders with the largest holdings relative to their own market cap (Hyakugo Bank, Keisei Electric Railway, Okaya).

## Drivers of unwinding pressure

While discussion of unwinding of Japan's web of cross-shareholdings has been a topic amongst market participants on and off since the early 2000's, we think that various factors have now aligned to fuel further momentum for rationalization of holdings in the coming years. We believe a confluence of top-down regulatory measures, a more supportive macro environment and various bottom-up drivers are set to act as further catalysts.

## Top-down measures include:

JPX Cost of Capital Conscious Management initiative and the reform of the exchange boards. In April 2022, the Tokyo Stock Exchange (owned by JPX) restructured its somewhat fragmented market structure from 5 boards (TSE1, TSE2, JASDAQ Standard, JASDAQ Growth and Mothers) to 3 boards (Prime, Standard and Growth). At the same time, it increased listing requirements, most notably with explicit tradable share ratios which penalize cross-holdings in their calculation. They also applied these more stringent tradable share requirements in calculating Topix weightings. In 2023, with updates in early 2024, the JPX introduced its new Cost of Capital Conscious Management initiative to promote additional focus on returns from listed companies. This included significant guidance around various measures to consider the cost of capital, balance sheet efficiency and dialogue with shareholders. The JPX is also now updating a list of which companies have established clear capital efficiency plans. Many of these plans include direct reference to strategies for addressing cross-shareholdings.

Revisions to the CG / Stewardship Codes. Japan's Stewardship Code and Corporate Governance Code were introduced in 2014 and 2015, respectively. They both have since received various updates. The Stewardship Code promotes investors to push for companies that they hold to be proactive around targeting sustainable growth. The CG Code explicitly recommends that listed companies disclose their policies around cross-shareholdings, annually assess them with respect to cost of capital, as well as discuss any reduction plans. Furthermore, companies should outline their voting policies with respect to cross-holdings.

Increased FSA focus. Japan's Financial Services Agency, the primary securities regulator, has been increasingly proactive in promoting corporate governance in addition to its work on the two main Codes. They continue to release various studies and opinions outlining goals and best practices around corporate governance, including cross-holding recommendations. In 2019, annual securities reports (yuho) were amended to include increased disclosure around crossholdings, rationale for holding and policies with respect to holdings. In 2021, the FSA-convened Council of Experts also included more discussion with respect to the issues around listed subsidiaries, a special case of cross-shareholdings, in addition to cross-holdings generally.

Figure 13: The end of NIRP / YCC will increase the cost of capital for Japanese corporates
![](images/c5f24fe5084a444504d71bf83ab71d971faa9532a87b7b69f18fc29ec863ca71.jpg)
Source: UBS Quant Research, Bloomberg

Figure 14: Buyback announcement event window: the market rewards stocks making capital returns
![](images/50b2a66cb19f6fbe6351b2b7474dc7f4b30d5641e4a49fbc82eed235a03a0e3d.jpg)
Source: UBS Quant Research, FactSet, Bloomberg. Returns are Carhart 4-factor adjusted returns normalized around the 125 trading days pre-/post-announcement

## Key shifts in the macro backdrop include:

Increased cost of capital. With the recent move by the BoJ to exit the Negative Interest Rate Policy (NIRP) and the Yield Curve Control (YCC) program at their March policy meeting, interest rates in Japan have moved up. Depending on the tenor, we are now at levels that we have not seen since the early 2010's. While the BoJ does not appear to currently have a particularly hawkish stance, the end of the extraordinary measures put in place as part of the Qualitative and Quantitative Easing (QQE) program has increased the level and volatility of rates in Japan. This will naturally flow through to higher cost of capital for Japanese companies. With a higher required rate of return, holding other listed stocks may increasingly become a poor capital allocation decision for Japanese listcos.

End of deflation to spark proactive capital management. The BoJ's shift in policy was driven by what looks to be a structural end to Japan's years of deflation. Recent inflationary data points and the increasing wage pressure faced by corporates may see Japan having entered a new period of more stable inflation. Moving from deflation to inflation will radically change how Japanese corporates view idle balance sheet resources, in our view. The real cost of carry will increase and hoarding cash and holding "sleepy" cross-holdings may not meet increased return thresholds. Furthermore, we may see companies look to more proactively invest in their businesses (something lacking during the "lost decade(s)" period) which will require asset allocation decisions which may result in choosing to unwind cross-holdings to redeploy in core business activities.

Strong market reaction to capital return efforts. In recent years, we have seen the market more proactively reward efforts to improve capital management. This can be seen in the strong market returns to buybacks and increased dividends. At the same time, we have also seen strong market responses to cross-shareholding unwind announcements. We will discuss this at length later in this report. With the market rewarding announcements around unwinds, it may spark further rationalization of holdings. Furthermore, we may see companies engage in crossholding unwinding to facilitate buybacks and dividend increases. A typical approach used in Japan is for a company that is having its shares sold as part of a cross-holding unwind to conduct a buyback, often "off-market" via a ToSTNeT-3 buyback.

Figure 15: Japanese markets have finally rebounded to previous all-time highs last seen in 1989
![](images/06ac403e1272c779c375c5cd8fb7c843ef3a29eb261c411c89fb30ff44dc6717.jpg)
Source: UBS Quant Research, Bloomberg

Figure 16: Net unwinding value of cross-holdings has accelerated from 2020
![](images/ccf0f85937ec8f3f5e3e8ea4de54cf634f2b8ad9ffa2efb889a515eac7549560.jpg)
Source: UBS Quant Research, FactSet

## Bottom-up shifts pushing companies to change include:

Increasingly vocal shareholders / the rise of activism. The Stewardship Code has increased the level of engagement of shareholders in Japan, which along with shifts in the disclosure regime have likely put pressure on cross-holdings. At the same time, we continue to note the growing role of activist investors in Japan. This includes well-known international activist funds, as well as Japan's homegrown "engagement funds" which take a more management-inclusive approach to traditional activist strategies. Earlier this year, Bloomberg reported that the total market value of companies targeted by activist campaigns in Japan doubled in value to US\$252bn in 2023. Recently reported/announced activist stakes in Japan include Elliott Management/Sumitomo Corp, Oasis/Kao, and Silchester/Nikon, amongst others.

Higher valuations leading to significant mark-to-market gains. Many crossholdings are kept on corporate balance sheets at cost. With Japanese equities retesting all-time highs in early 2024, the value that companies can crystallize from unwinding holdings may look attractive. As we discuss later in this report, we estimate the total value of cross-holdings in Japan now sits at 20-year highs, despite the ongoing decrease in cross-shareholdings as a percentage of shares outstanding.

Follow-the-leader momentum. Japanese corporates have often been critiqued by international investors as overly cautious. This may be due to the fact that there was little impetus to be proactive during the deflationary "lost decade(s)". As more companies engage in rationalization of their cross-holdings, taking action may increasingly become the status quo. Companies may not want to seem to be the only ones not taking action. In recent years, we have seen a similar trend with the rise of buyback announcements. Furthermore, for the case of "bilateral" crossholdings, where company A holds company B and vice versa, if one party unwinds its holdings the rationale for the other company to maintain its holdings decreases significantly. A recent example can be seen in the respective unwind announcements from Toyota Motors and Denso, which each have held shares in the other. This phenomenon could add further momentum to cross-shareholding unwinds.

## Creating the dataset

We leverage FactSet's Ownership database to create a time series of Japanese holdings. Note that for this exercise we are strictly looking at ownership of other listed Japanese companies. While there are notable examples of significant holdings in non-Japanese stocks (e.g. Softbank/ARM/Alibaba; Nissan/Renault), we don't believe that these crossborder holdings face the same institutional pressure that Japanese cross-holdings do.

We take monthly snapshots of holdings going back to 2005 for the full Japan listed universe (over 3,500 active stocks and over 1,000 inactive stocks).

Figure 17: Examples of different relationships in our cross-holding network
![](images/fb484123d7f1eb3c6a70dd68babb1b2478bc0bcdc9bb9c73c1eb8954de85e66e.jpg)
Source: UBS Quant Research, FactSet

## Organizing cross-holdings data

Given the idiosyncrasies of cross-holdings in Japan, we utilize a few different terms to help describe the relationships in the network.

Ownership perspective. At different times we may be interested in looking at relationships from the holder's perspective and at other time's from the perspective of companies that are held.

. When we are looking at the holder's perspective, we are considering its specific dynamics. As discussed previously, holders are interesting as holding companies, as well as their position relative to their holdings of other listed stocks. Key considerations around holders are the relative value between holders and their holdings and whether their valuations and financial performance are negatively impacted by their cross-holding portfolios. Furthermore, we can also assess how they perform when they build-up or unwind cross-holdings.

. Held stocks refer to the perspective of stocks that are holdings of other listed companies (or holders). Key considerations include whether these are controlling stakes and whether significant unwinding could impact the performance of held stocks from a supply and demand perspective.

. While holdings are fundamentally the same as held stocks, and are thus interchangeable, we look to refer to stocks held by other listed companies as holdings when referring to them with respect to their holders.

Relationship perspective. As discussed previously, we see different types of crossholdings relationships in Japan. In this report, we don’t look to differentiate between vertical and horizontal relationships. We do differentiate between bilateral and holdings. We believe these are relevant criteria due to the different control relationships and unwind considerations.

Significance of stake perspective. Another important feature to consider with respect to cross-holdings is the size of the holding stakes. Different stakes afford different rights in Japan. While a detailed analysis of shareholder rights in Japan is beyond the scope of this report, the key thresholds are 33.3% (one third), 50% (simple majority) and 66.6% (two thirds). With 50% of the voting rights, a shareholder can approve ordinary resolutions such as appointing and removing directors. At 33.3%, a shareholder can block the passage of a special resolution, such as a merger or share issuance. At 66.6%, a shareholder can approve both ordinary and special resolutions.

Additionally, another important threshold is 5% ownership, whereby an investor must submit a Large Shareholder Report to the FSA.

Given the above, we have bucketed the significance of stakes into five bands, as follows:

< 5%, or small stakes of less than 5% but greater than zero.

5% - 10%, or non-significant stakes of greater than or equal to 5% but less than 10%.

10% - 33.3%, or strategic stakes greater than or equal to 10% but less than one third (33.3%).

33.3% - 50%, or controlling stakes greater than or equal to one third (33.3%) but less than a majority (50%). We refer to these as control stakes given the ability to block a special resolution.

>50%, or listed subsidiary stakes. We refer to these as listed subsidiaries as they will generally be consolidated and the holder will have effective ability to manage the company given its majority voting power.

We consider stakes above 10% as significant stakes generally, including our buckets of strategic stakes, controlling stakes and listed subsidiary stakes.

## The impact of cross-shareholding unwinds (and additions)

In the following section, we look more closely at trends in changes in cross-holdings over time, as well as how the market has responded to companies increasing and decreasing holdings in other listed stocks.

## Trends in additions and unwinds of cross-holdings

Looking at activity by year, the number of additions and unwinds in cross-holdings by transaction count largely tracked each other until 2016, when the number of unwinds has exceeded additions in most years. If we look at the annual trend in value terms, we can see that unwind value has exceeded build-ups in every year and strongly accelerated from 2017.

Figure 18: Unwinds / Build-up of cross-holdings - count by year
![](images/60f0d43c48b841efe489fcc7de5c0ae953858c740a26e4ccc994678cc3ea2c91.jpg)
Source: UBS Quant Research, FactSet

Figure 19: Unwinds / Build-up of cross-holdings - value by year
![](images/bf9d0882bcdee03857b2a659941f19d6c0393da421941b911c8bbad089af05d1.jpg)
Source: UBS Quant Research, FactSet. N.B. JPY trillions

One interesting trend that is revealed when looking closer at the data is the prevalence in unwinding from Banks and Insurance companies, which make up as much as one third to almost one half of unwind value in certain years. For other sectors, build-up and unwind trends have seen less clear-cut trends.

Figure 20: Annual buying value - Banks and Insurance relative to other companies
![](images/629c2a8576c2dd2749e0e8be768cf8a2a1ed9454bee4eeee69e0bd36beea526b.jpg)
Source: UBS Quant Research, FactSet. N.B. JPY trillions

Figure 21: Annual selling value - Banks and Insurance relative to other companies
![](images/e47a5184672d2a8b92213c9de5110bb2a83b4724dcebef49a473e14434967920.jpg)
Source: UBS Quant Research, FactSet. N.B. JPY trillion

## Stock performance and cross-shareholding changes

In the following event charts, we look to understand how the stock market penalizes and rewards changes in cross-holdings. We subdivide our analysis to look at differences over time, financials vs. non-financials and whether the value of cross-holding changes plays a role.

The below charts are "event windows" which look at the market-relative return of stocks holding other listed companies around cross-holding change events. We look at the holders' performance 3 months prior to an event (events occur at month 0 on the xaxis) and the following 12-month returns. Stocks labelled as No Change are all stocks that have not had an event for comparison purposes (including stocks without crossholdings). We look at cases for both the whole universe as well as focusing on just Banks and Insurance stocks, given their more proactive role in the cross-shareholding unwind process. For this analysis, we limit it to our tradable universe of stocks that have 6m ADV of US\$500k and greater.

Figure 22: Event window: all stocks, equal-weighted performance 2005 - 2023
![](images/ee20a52a25d759d4b2613d4ad90599c796546834d37da47818c38188a7cfe179.jpg)
Source: UBS Quant Research, FactSet. N.B. Excess returns in the months prior / post a cross-holding event

Figure 23: Event window: Banks and Insurance stocks, equal-weighted performance 2005 - 2023
![](images/59573f1847a0473ba778657624734fdbb4c6ed212a0523f7aab2f5d3c266b294.jpg)
Source: UBS Quant Research, FactSet. N.B. Excess returns in the months prior / post a cross-holding event

As expected, on average across the whole 2005 through 2023 period, companies that had gone through unwinding of cross-shareholdings outperformed relative to companies with build-ups or no changes. If we isolate Banks and Insurance companies, we see that this outperformance of cross-holding unwinds is amplified. In fact, there was some slight underperformance of cross-holding build-ups versus companies with no changes in this subsector. This may be due to the overwhelming prevalence of crossholdings amongst Financials and the less credible rationale for them to hold large portfolios of other listed stocks.

Interestingly, if we look at post-event returns for all sectors, we see that companies with increases in cross-holding stakes have actually slightly outperformed companies that have had no change. It appears that the market values activity. Prima facie, this may not be completely intuitive. That said, it is important to remember that while investors generally have negative views around cross-holdings, they have been pervasive and this period overlaps with Japan's "lost decade(s)" deflationary period. Given the longer-term backdrop, investors may have been rewarding companies that were taking action - either to unwind or build up positions.

If we break this analysis into different periods, we do see that the market return to unwind events has increased. We divided our dataset into 3 periods: 2005 through 2012, 2013 through 2018 and 2019 through 2023, separated by pre- and post-Abenomics and the period overlapping the COVID-19 pandemic through current.

Figure 24: All stocks, equal-weighted performance 2005 - 2012
![](images/d540fb788c22a84d8dbd6b0ddf592dc347f4123726ae463bf25ab5b88156a095.jpg)
Source: UBS Quant Research, FactSet

Figure 25: All stocks, equal-weighted performance 2013 - 2018
![](images/d01c2d864bb662cd66643809397d45ccfcb2bb4e0001f63ca16e4f986d8b1811.jpg)
Source: UBS Quant Research, FactSet

Figure 26: All stocks, equal-weighted performance 2019 - 2023
![](images/c755b7efe12d5eba4485067d0c9d9e6f753f2d972f4490162e23886531353ffd.jpg)
Source: UBS Quant Research, FactSet

Turning our analysis back to focusing on Banks and Insurance companies, we can see that unwinds have outperformed both build-ups and no changes in all of the three periods. The outperformance of unwinds had also gotten stronger in the 2019 through 2023 period.

Figure 27: Banks and Insurance stocks, equal-weighted performance 2005 - 2012
![](images/d1de5a503c24fde1a6eae13a8fda5704ba4846b74c10531ce96c96377b770252.jpg)
Source: UBS Quant Research, FactSet

Figure 28: Banks and Insurance stocks, equal-weighted performance 2013 - 2018
![](images/59ffe266f1f14bae44a40144ccfb80eccd1ca12d23b64c9067b523dd351e389e.jpg)
Source: UBS Quant Research, FactSet

Figure 29: Banks and Insurance stocks, equal-weighted performance 2019 - 2023
![](images/1b4e6f0e7e88c19bcd364bb1da32d448daa2f2c50bd42371d5328de9aebcc399.jpg)
Source: UBS Quant Research, FactSet

## Adjusting for holding value

If we adjust our analysis to take into account the size of the holdings unwound or built up, we see that performance of unwinds throughout our analysis period improves.

Figure 30: All stocks, size-of-change-weighted performance 2005 - 2023
![](images/74781c0996126a4a21a4872d97f622bf0a5405299267ecf2038aa354aa2d8543.jpg)
Source: UBS Quant Research, FactSet. N.B. Excess returns in the months prior / post a cross-holding event. Returns are weighted based on market cap unwound or built-up relative to their respective portfolio at each month end

Figure 31: Banks and Insurance stocks, size-of-changeweighted performance 2005 - 2023
![](images/0cea22ed387010acaf1039a3cda11639356c2ad6f13a584a9b2a0395ea6bf6be.jpg)
Source: UBS Quant Research, FactSet. N.B. Excess returns in the months prior / post a cross-holding event. Returns are weighted based on market cap unwound or built-up relative to their respective portfolio at each month end

Looking more closely at the data, we find that in our first two periods (2005-2012, 2013-2018) trends are roughly similar. If we look at the most recent period (2019 - 2023), we see significant uplift in unwind performance after adjusting for size of holdings unwound or built-up.

To adjust returns for holding value, we first calculate size of change in holdings by multiplying the absolute change in number of shares, and the end-of-month price of the held stock when a change is recorded. The weights on each holder at each month-end are then computed based on the magnitude of holding values unwound or built-up, relative to the portfolio of their respective change event. Holders that sold off larger cross-holdings market cap therefore have higher weights in the 'Unwind' portfolio, and similarly, holders that bought larger cross-holdings market cap have higher weights in the 'Build-up' portfolio.

Figure 32: All stocks, size-of-change-weighted performance 2019 - 2023
![](images/13a1fb7fae7d106a80610486e52b9295d6171abb9141bb3754a9a4a517e7d39c.jpg)
Source: UBS Quant Research, FactSet. N.B. Excess returns in the months prior / post a cross-holding event. Returns are weighted based on market cap unwound or built-up relative to their respective portfolio at each month end

Figure 33: Banks and Insurance stocks, size-of-changeweighted performance 2019 - 2023
![](images/5be9fc1a3f99de85b98fc1b375a34616c981be8d56421093c0384e0890034e69.jpg)
Source: UBS Quant Research, FactSet. N.B. Excess returns in the months prior / post a cross-holding event. Returns are weighted based on market cap unwound or built-up relative to their respective portfolio at each month end

Key takeaways from our event analysis include:

Before and during the Abenomics period we saw less differentiation around crossholding changes amongst non-financials.

Financials saw modest outperformance during that period.

On an equal-weighted basis, both stocks that added and unwound cross-holdings from 2019 - 2023 outperformed, while stocks with no change in holdings lagged.

Adjusting for size of change in holdings, we see that non-financials and financials performing unwinds show the strongest post-event performance. This is most notable in the latest period (2019 - 2023), especially for non-financials.

Given the broad market view that cross-holdings are seen as drags on performance, we view our results as somewhat surprising relative to conventional wisdom. It appears that inaction amongst Japanese companies with crossholdings is viewed more negatively than either unwinds or position additions.

## Creating cross-shareholding factors

In order to assess whether cross-shareholdings in Japan share any unique characteristics or risk dynamics, we can look to see if we can create a suite of cross-shareholding "factors" that allow us to differentiate stocks.

Given the nature of cross-holdings, there a number of ways that we could potentially look at this including:

Holdings Value: Total value of cross-holding portfolio.

Holding Percentage: Value of cross-holding portfolio relative to market cap.

Held Percentage: Percentage of shares outstanding held by other listed companies.

Holding less Held Percentage: The relative ratio of participation in the crossholding network.

Changes in Holdings: As indicated by our previous event study, there appear to be returns associated with action vs. inaction, and in recent years, a premium placed on holders conducting unwinds.

Factor deltas and cross-factor interactions: We can also consider the changes of the above factors, their interactions with each other (such as double sorting), as well as interactions with other standard risk factors in Japan.

In order to assess the above, we propose to break our universe down into four buckets: one "quantile" of stocks with no cross-holdings, and split the remaining stocks into terciles based on the chosen cross-holding "factor". For ease of discussion, we will call these Q0 (no cross-holdings), Q1 (low holdings), Q2 (medium holdings) and Q3 (high holdings).

To study the efficacy of this approach, we limit our analysis to exclude difficult to trade stocks by limiting our universe to names with 6m ADV of US\$500k or higher.

Figure 34: Distribution of stocks trading more than US \$500k per day, by Holding Percentage
![](images/95e904db4f5cb98749cad75dd72ed32dba0f768f25f75120a63ccb845bf64f03.jpg)
Source: UBS Quant Research, FactSet

Figure 35: Distribution of large cap stocks trading more than US\$500k per day, by Holding Percentage
![](images/3c97ca214565681d40e6dc3bc50a83af08963855168386ee5ab80be532d52b9b.jpg)
Source: UBS Quant Research, FactSet

In total, this reduces our universe to 1,860 stocks currently. For large cap stocks only, we have 40 stocks in each of the Holding Percentage terciles, but only 8 with no crossshareholdings.

In total, we conducted an initial assessment of 7 factors, the details of which can be found in Appendix: Other cross-shareholding factors performance summary. We identified 3 factors created from the cross-shareholding network that we think are interesting and can be of use to investors. We outline these in more detail in the following pages.

## Focus Factor: Holding Percentage

Below we show the performance of our three terciles (Q1, Q2, Q3) by Holding Percentage and the no cross-holding quantile (Q0). Interestingly, we find a strong monotonic relationship between the degree of a holder's cross-holding portfolio value relative to its market cap.

Rationale: We look at the monthly value of a holder's value of holdings relative to the holder's market cap. We rank this ratio into terciles and compare with stocks that have no cross-holdings. Q3 represents stocks with the largest value of holdings as a percentage of market cap, and Q1 consists of stocks with the least value of holdings to market cap. We view this as a proxy for attractively priced holders based on the relative value of their holdings. It can be considered as a simplified, but systematic, version of a holding company discount / stub approach.

Figure 36: Time series performance of cross-holding buckets - Holding Percentage factor
![](images/b085dc6d3215c240177a5cd70de4290cb9eca1be3cf565e63e6f284f8467c7db.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 37: Average next month returns by cross-holding buckets - Holding Percentage factor
![](images/55a56158e29782bd573f593ec535a6804ea1a5b86ae876b3ef63c42f9c88e06c.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Holding Percentage appears to be a quite good factor for differentiating stocks. The different quantiles have relatively strong monotonic trends. Over the long term, long/ short performance has been relatively good, though appeared to not add much value from 2016 - 2019. We also see a meaningful drawdown in 2020. From 2021, the Holding Percentage factor has strongly outperformed.

Figure 38: Long/short performance of Q3-Q1 - Holding Percentage factor
![](images/571d89d75bbccb9bf67adaf77620e3ae52f51efbaae58c6e39961a473c48341f.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 39: Correlation with standard factors - Holding Percentage factor (L/S)
![](images/22bd3d9eecd6e728bb4b3ba426221edbb3c663be609edc8f1b44834089e67909.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

From a factor exposure perspective, we can see that the Holding Percentage factor has a relatively small correlation with the market, is short Growth, Quality and Momentum and has long exposure to Value. Intuitively, this make sense as we would view this as a cross-holding specific expression of Value. We can also consider this as a simplified proxy for holding company discount / premium, or so called "stub trades". These are typically considered "deep" value opportunities.

Below, we compare cross-shareholding Holding Percentage with other Value factors over time. Interestingly, despite trailing slightly behind in returns versus the best performing Value factor, Book Value Yield, the Holding Percentage factor exhibited lower volatility, resulting in a superior Sharpe ratio. In terms of risk-adjusted returns, it shows the second strongest Sharpe ratio, at 0.47, trailing only FCF Yield when compared to our suite of standard style factors. It also has the second smallest maximum drawdown.

Figure 40: Holding Percentage looks to be an attractive alternative in Japan to standard Value factors
![](images/576dcd74c5f5f2f1ae8acc43fc0edced058de78bd1db877dd803712938c43943.jpg)
Source: UBS Quant Research, FactSet

Figure 41: Holding Percentage performed second best on a risk-adjusted return basis when compared to standard style factors
<table><tr><td rowspan=2 colspan=5>Annualised AnnualisedFactor                       Return   Volatility Sharpe Ratio Maximum DD</td></tr><tr><td rowspan=1 colspan=1>Sharpe Ratio</td></tr><tr><td rowspan=1 colspan=1>Holding Percentage</td><td rowspan=1 colspan=1>3.2%</td><td rowspan=1 colspan=1>6.7%</td><td rowspan=1 colspan=1>0.474</td><td rowspan=1 colspan=1>-23.9%</td></tr><tr><td rowspan=1 colspan=1>EPS Growth (12m trailing)</td><td rowspan=1 colspan=1>-0.9%</td><td rowspan=1 colspan=1>9.1%</td><td rowspan=1 colspan=1>-0.097</td><td rowspan=1 colspan=1>-35.9%</td></tr><tr><td rowspan=1 colspan=1>Fundamental Growth</td><td rowspan=1 colspan=1>-1.7%</td><td rowspan=1 colspan=1>10.4%</td><td rowspan=1 colspan=1>-0.162</td><td rowspan=1 colspan=1>-44.0%</td></tr><tr><td rowspan=1 colspan=1>High Quality</td><td rowspan=1 colspan=1>1.0%</td><td rowspan=1 colspan=1>11.5%</td><td rowspan=1 colspan=1>0.084</td><td rowspan=1 colspan=1>-43.5%</td></tr><tr><td rowspan=1 colspan=1>Delta Quality</td><td rowspan=1 colspan=1>-4.5%</td><td rowspan=1 colspan=1>13.7%</td><td rowspan=1 colspan=1>-0.325</td><td rowspan=1 colspan=1>-71.6%</td></tr><tr><td rowspan=1 colspan=1>Momentum Composite</td><td rowspan=1 colspan=1>-1.3%</td><td rowspan=1 colspan=1>13.1%</td><td rowspan=1 colspan=1>-0.098</td><td rowspan=1 colspan=1>-53.5%</td></tr><tr><td rowspan=1 colspan=1>Revision to 12m fwd EPS FS (3m)</td><td rowspan=1 colspan=1>1.5%</td><td rowspan=1 colspan=1>10.5%</td><td rowspan=1 colspan=1>0.141</td><td rowspan=1 colspan=1>-33.7%</td></tr><tr><td rowspan=1 colspan=1>Price Momentum (12m)</td><td rowspan=1 colspan=1>-3.3%</td><td rowspan=1 colspan=1>13.6%</td><td rowspan=1 colspan=1>-0.244</td><td rowspan=1 colspan=1>-63.0%</td></tr><tr><td rowspan=1 colspan=1>Low Price Beta (12m)</td><td rowspan=1 colspan=1>-1.9%</td><td rowspan=1 colspan=1>16.0%</td><td rowspan=1 colspan=1>-0.116</td><td rowspan=1 colspan=1>-56.2%</td></tr><tr><td rowspan=1 colspan=1>Low Volatility (12m)</td><td rowspan=1 colspan=1>-3.6%</td><td rowspan=1 colspan=1>14.6%</td><td rowspan=1 colspan=1>-0.247</td><td rowspan=1 colspan=1>-67.0%</td></tr><tr><td rowspan=3 colspan=1>Composite Value (Sector Neutral)Earnings Yield FS (12m fwd)Dividend Yield (12m trailing)</td><td rowspan=1 colspan=1>2.3%</td><td rowspan=1 colspan=1>8.8%</td><td rowspan=1 colspan=1>0.261</td><td rowspan=1 colspan=1>-36.9%</td></tr><tr><td rowspan=1 colspan=1>2.2%</td><td rowspan=1 colspan=1>8.7%</td><td rowspan=1 colspan=1>0.252</td><td rowspan=1 colspan=1>-34.4%</td></tr><tr><td rowspan=1 colspan=1>2.0%</td><td rowspan=1 colspan=1>7.9%</td><td rowspan=1 colspan=1>0.255</td><td rowspan=1 colspan=1>-41.1%</td></tr><tr><td rowspan=2 colspan=1>Book Value Yield (12m trailing)FCF Yield (12m trailing)</td><td rowspan=1 colspan=1>3.4%</td><td rowspan=1 colspan=1>8.8%</td><td rowspan=1 colspan=1>0.381</td><td rowspan=1 colspan=1>-34.9%</td></tr><tr><td rowspan=1 colspan=1>2.8%</td><td rowspan=1 colspan=1>5.8%</td><td rowspan=1 colspan=1>0.483</td><td rowspan=1 colspan=1>-19.5%</td></tr><tr><td rowspan=1 colspan=1>Small Caps</td><td rowspan=1 colspan=1>-0.1%</td><td rowspan=1 colspan=1>7.4%</td><td rowspan=1 colspan=1>-0.011</td><td rowspan=1 colspan=1>-37.2%</td></tr></table>

Source: UBS Quant Research, FactSet

Another interesting takeaway is to look at the distribution of fundamental factors associated with our different buckets. While the no-cross-holding bucket appears to be in the middle of the pack, we see clear differentiation in terms of ROA, ROE, Quality and Leverage depending on the percentage of cross-holdings to market cap.

Figure 42: Rolling ROA by Holding Percentage bucket
![](images/e02e8463f19f42eaaaf123822f05736e0cc7c9f0b075250e379c1f676dc22c11.jpg)
Source: UBS Quant Research, FactSet

Figure 43: Rolling ROE by Holding Percentage bucket
![](images/b95a7d3ce8e2e542a55bd5f0b34ef41ed6527c3f97f661ec0023c3e409cd2926.jpg)
Source: UBS Quant Research, FactSet

For each, we see an inverse relationship between the scale of cross-holdings relative to market cap and ROA/ROE/Quality/Net debt to assets. The ROE spread between low holding percentage stocks and high percentage stocks currently sits at around 4%.

Figure 44: Rolling Quality by Holding Percentage bucket
![](images/48557f85ed6142697956a6dbfe5eee0c8271987946020fe03617f0ccb354547a.jpg)
Source: UBS Quant Research, FactSet

Figure 45: Rolling Net Debt to Assets by Holding Percentage bucket
![](images/731c1ff8028f398d8fa6f675fb7edd11a7509a45fdc669e0ed473bcc3991753f.jpg)
Source: UBS Quant Research, FactSet

While companies with lower holdings relative to market cap have better quality / financial returns, it seems that they tend to underperform over time, possibly due to mispricing of stocks that have a higher proportion of cross-holdings.

From a capacity perspective, we can see below that there are a significant number of stocks from our tradable universe in each quantile, which should facilitate the implementation potential of this factor.

Figure 46: Size distribution of Q1 by Holding Percentage
![](images/8e43fd99a27fe66d7e71cc4dfbb85bdaba4b61dc4c1bb9ea61e89c2b97c58ce6.jpg)
Source: UBS Quant Research, FactSet

Figure 47: Size distribution of Q2 by Holding Percentage
![](images/7f2d4d895cb7821a563e053ab78d60c758ad3f583fc17f755ff12f8c7a4f8923.jpg)
Source: UBS Quant Research, FactSet

Figure 48: Size distribution of Q3 by Holding Percentage
![](images/8c895cb061eb59384cbe4dc1b3b6fbc4273a95aa4e57a753575f9368f3249fb7.jpg)
Source: UBS Quant Research, FactSet

One other consideration around this metric is that it can be driven by multiple factors. Holding percentage can increase (decrease) because:

The holding company's market cap declined, all else held equal.

The held stock's market cap increased, all else held equal.

The company increased its holdings.

As we discuss below, we can also isolate the relative changes both including price effects, as well as removing price effects. This can give us different and interesting results.

## Focus Factor: Change in Holding Percentage

Building upon our previous discussion on Holdings Percentage as a cross-holding factor, in this section, we explore the additional insights we may obtain through analysis of its delta. The Change in Holding Percentage is simply the difference in stocks' Holding Percentage factor compared to their previous month's values. For the delta factor, we split our universe into two sets of terciles: Q3, Q2, and Q1 for stocks that have seen an increase over the last month in their Holding Percentage, and -Q3, -Q2 and -Q1 for stocks that have seen their Holding Percentage decrease over the past month. Similar to before, Q0 represents stocks with no cross-holdings.

One thing to note for this section is that there are two components in play in the Change in Holding Percentage factor. It not only captures the build-ups and unwinds of holders' cross-holdings, it also captures the relative price changes between holders and their holdings. In fact, we suspect that the latter dominates in this case. In other words, holders that have greater price movements in their holdings relative to their own, make up the majority of the increases in Holdings Percentage. Only a smaller subset of these increases comes from actual build-ups of cross-holdings by holders.

Figure 49: Time series performance of cross-holding buckets - Change in Holding Percentage factor
![](images/b796a67bddc0450a269f66ac9992fc151fd9a9c6aae4070cc86aa7ffbb1ff500.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 50: Average next-month returns by cross-holding buckets - Change in Holding Percentage factor
![](images/c2781d1e2d974ef5e4253af206a4561c49da8975d6ca9d9ba312beff671f1b52.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

On the side of positive changes in Holding Percentage, we see strong monotonic performance with Q3 outperforming both Q2/Q1. It also outperforms the negative changes (-Q3, -Q2, -Q1). On a long / short basis, we look at the Q3 less -Q3. This produces a quite attractive wealth curve, with 4.6% annualised return and a Sharpe ratio of 0.57. As stated above, we believe that the price effect is more relevant here than the change in actual underlying cross-holdings. Given that, the factor is "buying" stocks whose value of holdings has increased the most over the last month relative to their market cap (akin to the biggest change in discount to NAV) while "selling" stocks whose holdings value decreased the most relative to market cap (NAV has decreased relative to market cap).

From a factor exposure perspective, we notice relatively more negative correlation with Momentum factors, further signalling that the Change in Holding Percentage factor tends to load on stocks that have underperformed relative to their holdings. In general, correlations with other standard quant factors are not as significant as compared to the Holding Percentage factor.

Figure 51: Long/short performance of Q3 less -Q3 - Change in Holding Percentage factor
![](images/28f00c395a9fa8e7916ff55ebd813bbfff122aa791a74478d87cff1078ccd61b.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 52: Correlation with standard factors - Change in Holding Percentage factor (L/S)
![](images/db2c1223c5accfd3b7168491c43913fe9f4a4ed314147a2b1a2af6846730f2ed.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 53: Large caps - Number of stocks in each Change in Holding Percentage bucket
![](images/273851088bd8345b55be5d1be94fc8f7e71ea13bc257009d2837332c7ae4e73b.jpg)
Source: UBS Quant Research, FactSet

Figure 54: Mid caps - Number of stocks in each Change in Holding Percentage bucket
![](images/fc7c2d711b2ba0e8fd6702122256c52deb7ace52143399d695598a3074d81fd1.jpg)
Source: UBS Quant Research, FactSet

Figure 55: Small caps - Number of stocks in each Change in Holding Percentage bucket
![](images/f7fa16fec3330afa570acd1499f8a3c441944794d646bd190a625180b507dbc9.jpg)
Source: UBS Quant Research, FactSet

## Focus Factor: Holding Shares Change

In our previous section on Holdings Percentage Change factor, we noted that there are two components driving the delta factor: build-up and unwind activities of holders, as well as relative price changes of holders versus their holdings. In this section, we attempted to eliminate the price effect and isolate the performance of holders who have unwound their cross-holdings. Again, we split our universe into two sets of terciles every month, but except this time, Q3, Q2, and Q1 are for stocks that have built up stakes in other listed companies, with Q3 representing stocks that have bought the largest value. Conversely, -Q3, -Q2 and -Q1 are for stocks that have unwound their stakes in crossholdings, with -Q3 being stocks that have sold the largest value. Value of Holding Shares Change here is calculated by multiplying the change in the number of shares held and the end-of-month price of the held company. Q0 are all stocks with no change in crossholdings recorded in the past month.

To address our investigation into the benefits of cross-holding unwinding in Japan, we focus our study here on the terciles of stocks with decreases in cross-holdings positions, instead of increases. Given our expectation that cross-shareholding unwinds are set to increase and will continue to attract positive attention, we believe this factor has scope to improve going forward. Based on the results of our event study, which showed that stocks with no changes underperform relative to stocks with unwinds (as well as buildups), we think that we should compare the top tercile of unwindings (-Q3) with stocks that have had no change over the last month.

As we believe the benefits of cross-holdings unwinding tend to realise over a longerterm horizon, the portfolios for this factor are rebalanced monthly but held for 6 months.

Figure 56: Time series performance of cross-holding buckets - Holding Shares Change factor
![](images/f142de3639bbe1b3172b7da8b8674239f90e583aeab040ccf133e010f2ebd102.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 57: Average next month returns by cross-holding buckets - Holding Shares Change factor
![](images/8cb12bbaf24535e0d8264070411507d775b1a848ac8aa2eb134cccc2779ea636.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Over the entire backtesting period since 2005, the -Q2 tercile slightly outperformed the -Q3 tercile on average, but -Q3 outperformed both -Q1 as well as Q0. As we saw in our event study, if we focus on the last 5 years, we see a significant improvement in the relative performance, with -Q3 seeing 1.4% average monthly returns, while Q0 sees 0.8% average monthly returns. From a long/short perspective, this factor has seen periods of trending out- and underperformance. Returns have been especially strong since 2021. While it doesn't look like a consistent alpha factor, this aligns with our fundamental expectations around cross-holding unwind changes in the coming years and we believe the current backdrop should be favourable for a continued period of outperformance.

In terms of factor exposure, the Holding Shares Change factor has some correlation with the market. The factor is also short Growth, Quality, Momentum and Small Caps, while having higher positive exposure to Value factors.

Figure 58: Long/short performance of -Q3 less Q0 - Holding Shares Change Factor
![](images/e05836ab9be416653d781194152c23120c6fbd3539ab7ff6b4863e386c7daef2.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 59: Correlation with standard factors - Holding Shares Change Factor (L/S)
![](images/2444299f31f1b8dbf0ee32a60943aaf2369f6c4d1be3796df33ecf7417eb834e.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 60: Large caps - Number of stocks in each Holding Shares Change bucket
![](images/33957aca4425a34884575000ff1a350e72acb6f59d286975c93b3bd845e64eba.jpg)
Source: UBS Quant Research, FactSet

Figure 61: Mid caps - Number of stocks in each Holding Shares Change bucket
![](images/78ad6436ee7e806f9685720a0e33ec65e8006bcbf3f7a85808aadd2ae400ce1e.jpg)
Source: UBS Quant Research, FactSet

Figure 62: Small caps - Number of stocks in each Holding Shares Change bucket
![](images/51641c040c2f0cbb038fff19a17fadb4ec8f00e9f699940a303c4181ad64da78.jpg)
Source: UBS Quant Research, FactSet

As highlighted previously in our event study, when we constrained our universe to just Banks and Insurance companies, the relative outperformance of unwinds to no changes was amplified. We believe this could be due to the dominant presence of Financial companies as top holders of cross-shareholdings in Japan, as well as a potentially less credible rationale for large cross-holdings in the sector.

As such, we investigated the performance of the Holdings Share Change factor on only Banks and Insurance companies. Findings are summarised in this subsection in the Appendix: Factor 4: Holding Shares Change (Banks and Insurance).The difference between the average monthly returns of -Q3 and Q0 were 0.33% for this subset of the universe, compared to 0.17% for the entire universe. The long/short performance had an annualised return of 3.3%, and a Sharpe ratio of 0.3.

# Potential applications of the Japan cross-shareholding network

Given the breadth and depth of the cross-holding network in Japan, we believe it merits significant attention. There are a number of areas of additional analysis that are outside the focus of this report, which looks to introduce the general dynamics of crossholdings, that likely deserve additional focus. .

Areas where we could build on this analysis in future research include:

Text / sentiment analysis from yuho / company disclosure-based information. Many companies now disclose the rationale for their cross-holdings as part of the Corporate Governance Code disclosure regime and recent FSA/JPX guidance. This includes designation of certain holdings as "strategic holdings".

Inclusion of non-Japanese and private holdings. We have limited our analysis to Japanese listed stocks. While we don't believe foreign company or private holdings are prevalent in number, they are significant in a few cases, notably Softbank and Nissan.

Assessing relative shareholder returns of companies in the crossshareholding network. As noted previously, many unwinds are conducted by a holder selling into a held stock's buyback program. We have previously written on shareholder return predictions, which could be interesting with respect to the intersection with buyback and dividend targets. It would also be interesting to look at the relative shareholder return levels of companies with large crossshareholdings compared to those without.

Network analysis of cross-holdings. Applying explicit approaches from graph theory and network analysis could be alternative ways to assess cross-holdings and may yield additional insights.

Potential interesting applications of Japan's cross-shareholder network data include:

Combining our factors with a holdco / stub framework. Our Holdings Percentage factor could be considered as another version of a simple discount to NAV analysis that is popular amongst holding company relative value trades, or socalled stubs trades. We could formalize this by incorporating other parts of a company's net asset value / enterprise value.

Creating an alternate pairs trading universe. We could leverage the crossholding network as a pairs trading universe. It may provide a less explored opportunity set relative to traditional GICS industry approaches.

Leveraging the network to make predictions around future cross-holding unwinds. Given the large amount of data, we could examine the features of the stocks that have conducted unwinds and/or been unwound and look to predict future unwinds using machine-learning approaches. This could be applied to general cross-holdings, as well as significant stakes and listed subsidiaries. Over the last few years there has been a strong trend in privatizations, MBOs and third party sales of subsidiaries. These are often associated with large takeover premiums.

Assessing the interaction of cross-holdings with activist investors. Activist and "engagement" funds in Japan have been at the forefront of encouraging more unwinding of cross-holdings. A recent notable case can be seen in Elliott Management encouraging Mitsui Fudosan to reduce cross-holdings and conduct a large-scale buyback. Adding the presence of an activist may be an additional interesting dimension to analysing cross-holdings.

Based on the above inexhaustive list, we believe the cross-shareholding network is a very interesting data set and has many potential applications. We will look to further augment our analysis in follow-up research.

## Appendix

## What are cross-holdings?

The terms "cross-shareholding" and "cross-holdings" are often used in the market as catch-all terms for the fact that a significant number of listed companies own other listed companies in Japan. That said, we feel it is important to drill down a bit more to understand some of the nuances.

While the full history of the development of cross-holdings in Japan is outside the scope of this report, these type of relationships have a long history in Japan. Starting with the pre-war zaibatsu conglomerates (where famous names such as Mitsui, Sumitomo and Mitsubishi originated) to their transformation into the more modern keiretsu business alliances, tight-knit company relationships have been a long-standing feature of corporate Japan.

These interlinking holdings can appear in a number of ways. The most prevalent structures typically are:

Horizontal holdings. This is typified by business alliances across a range of sectors usually linked around a trading company or bank. Examples here would include the networks around the large trading companies.

Vertical holdings. This is typically arranged around a core holding or key operating company and often is tightly linked to supply chain relationships. Often the scale of holdings will be larger and consist of listed subsidiaries. Examples here would include the Toyota Group and Aeon, amongst others.

Figure 63: Mitsubishi Corp network
![](images/04b6ed0a254e188d2a9c17f969dc3e33d6931dc8afba5b3212395221f95ad883.jpg)
Source: UBS Quant Research, FactSet. Holdings > 10%

Figure 64: Toyota Group network
![](images/8e8d4784a9780cbfbdf7358e79463e60883aa450313c148986551ea482efc3d9.jpg)
Source: UBS Quant Research, FactSet. Holdings > 10%

As we move from group-level arrangements to the individual holding level, we also see different types of relationships. The most notable would be differentiating between bilateral and unilateral holdings. Bilateral relationships are seen when two companies own shares in each other. A notable example here would be Toyota Motor (7203 JP) and Toyota Industries (6201), where Toyota Motor owns 23.5% of Toyota Industries and

Toyota Industries, in turn, owns 7.3% of Toyota Motor. We also often see these in bankrelated cross-holdings. For example, Mitsubishi UFJ (8306 JP) owns 1.8% of Toyota Motor and Toyota, in turn, owns 1.2% of Mitsubishi UFJ. As seen in these two examples, bilateral holdings can represent significant stakes from a corporate control perspective (e.g. Toyota/Toyota Industries) or relatively insignificant stakes (Toyota / MUFG).

Unliteral holdings are seen when the holding relationship is only one way. For example, Aeon (8267 JP) owns 58.5% of Aeon Mall (8905 JP), but Aeon Mall does not own Aeon. For Aeon, this represents a special case of cross-holdings: the listed subsidiary. For holdings of insurance companies, we see a number of non-significant unilateral holdings. One example would be T&D Holding (8795 JP) which holds a 2.2% stake in Komatsu (6301 JP).

With the introduction of Japan's Corporate Governance and Stewardship Codes, as well as focus from the FSA and JPX, we continue to see top-down pressure to rectify and improve disclosure of cross-holdings. Under Japan's "comply and explain" framework, we now see disclosure of cross-shareholdings, or "strategic shareholdings" in the annual securities report (yuho), with increased disclosure around justification for holding and discussion around plans for cross-holding reduction. Currently, we are not taking this disclosure into our analysis, but may look to in the future.

## Why should investors care about cross-holdings?

The reason for much of the fanfare about the increasing activity around crossshareholding unwinding is that these intercompany holdings are largely seen as a drag on performance and valuation in the Japanese market.

Conventional wisdom around the key issues on cross-holdings include the following:

Capital inefficiency. While dividends have been increasing in recent years, companies holding stocks relative to investing in higher return projects or distributing cash back to shareholders tends to be perceived as an inefficient use of capital. The after-tax cash returns from cross-holdings will typically be a negative spread relative to cost of capital.

Holding company discounts. The persistent discount to NAV attributed to holding companies by the market is a largely understood phenomenon in financial markets. This is due to 1) the increased opacity of a holding company's net asset position, 2) the fact that allocation of the underlying business portfolio moves from investors to corporate managers, 3) cases where entrenched managers may not make efficient capital allocation decisions, and 4) concerns around less proactive capital management seen in holdcos, amongst others. Usually a company's holdings will be worth more on a "sumof-the-parts" basis.

Insulation of management. Other listed companies may be perceived as less proactive than other shareholders to hold management to account, leading to less accountable management. This could be seen to be the case especially in bilateral cross-holdings. Companies may face less pressure at AGMs and other special elections with an increased number of "friendly" shareholders.

Grossed-up shares outstanding. With share capital deployed into owning other companies' shares, many balance sheets may be viewed as "grossed-up". Were cross-holdings to be unwound, in theory that capital could be deployed more efficiently, or in many cases returned to shareholders through dividends or buybacks.

Supply chain inefficiency. Many cross-shareholdings relate to supply chain relationships, as can be most clearly seen through the Toyota network. Existing ownership relationships between customers and suppliers may risk muddling arm's length transactions between companies. This risk is a reason why many markets require explicit disclosure of related-party transactions, for instance. In recent years, Japanese authorities have also pointed to cross-shareholdings as potentially limiting fair competition, as seen in the administrative actions taken late last year in the Insurance sector.

As a result of the above, there may be a perception amongst market participants that companies with excessive cross-shareholdings tend to have depressed valuations, weaker shareholder returns and possibly weaker-than-expected margins, profitability and returns. As we discuss throughout this report, the actual situation is more complicated, though we do generally note weaker financial metrics amongst stocks with cross-holdings. Another concern around cross-holdings is increasing pressure for that money to be reallocated towards capital returns. As we have argued in our analysis around shareholder returns, Japanese companies have significant scope to expand buybacks and dividends. If we take into account cross-shareholdings, this could further accelerate.

## Japan's cross-shareholding network in charts

In the following section, we look at some descriptive data around cross-holdings in Japan.

## Where do we see the highest prevalence of cross-holdings?

We assess both the current situation to understand the opportunity set, as well as historical changes to get a sense for where cross-holdings are heading in Japan.

Figure 65: Total market cap held by other listed Japanese companies
![](images/7f16aa5ad0f934a78d0b0ec8f9052370230b6577e609de6fe2ad443cc3fbc508.jpg)
Source: UBS Quant Research, FactSet

Figure 66: Number of cross-held companies over time
![](images/753589ac58693124874bc411c009f5cbceddd0012b8669124dd4cb04f324411f.jpg)
Source: UBS Quant Research, FactSet

As discussed previously, the prevalence of cross-holdings in Japan remains significant and in many ways is a unique and defining characteristic of the Japanese market. We estimate that around 12% of Japanese market cap, or JPY 120 trillion, is held by other listed Japanese corporates. In total, we estimate that cross-shareholdings impact over 3,223 of Japan's listed companies, as can be seen above. Understanding where crossholdings are most prevalent can help navigate different opportunities amongst Japanese stocks, as we discuss when looking at cross-shareholdings as a "factor" and how their presence impacts the performance and risk characteristics of stocks.

## Sector considerations

Cross-shareholdings impact every sector in Japan, though we do observe some different trends across sectors.

Figure 67: Large cross-holdings (>10%) - the count of the current cross-holdings network is led by Industrials stocks

![](images/53dd4fd63aca3bf592a4aed27b3ec762f0cf871364b7a568d1ac91a254503bca.jpg)
Source: UBS Quant Research, FactSet. From the perspective of Holders

Figure 68: Large cross-holdings (>10%) - by value, we see a wider impact across a variety of sectors

![](images/791b562465be3c970f4f5577b8cc1d348d9c7e15fa998d91d846a8e101e3e1ed.jpg)
Source: UBS Quant Research, FactSet. From the perspective of Holders

Above, we look at the current network of large cross-holdings, defined as holders with stock holdings greater than 10%. We can see that there is a significant difference in the prevalence of cross-holdings by count and by value. From a count perspective, Industrials stand out as the sector with the most cross-holdings. When looking at value of holdings, we can see there is a lot more sector diversity, with Consumer Discretionary seeing the largest cross-holdings by value.

Figure 69: "Held stock" value sector split
![](images/72863d80da44f40f15325dfe3b5051bc65721d63f7d6775ae7689b2c10737c00.jpg)
Source: UBS Quant Research, FactSet. Calculated by taking the market cap of sector holdings held by other listed companies dividend by total market cap held by other listed companies

Figure 70: "Holder stock" value sector split
![](images/c9463d357988132074f5be75b7a0c1c4b9b7b8407227f2618df876aeace3b63c.jpg)
Source: UBS Quant Research, FactSet. Calculated by taking the cross-holdings market cap held by companies in each sector divided by total cross-holdings market cap

Looking at cross-holdings more broadly, we can separate the universe of stocks into "held" stocks and "holders". Held stocks are stocks that have ownership by other listed companies. Holder stocks are companies that have stakes in other listed companies. Here we include the full universe of cross-holdings.

For held stocks, we can see that Consumer Discretionary and Industrials are the most held stocks by market cap amongst cross-holdings. Interestingly, Communication Services has seen the largest increase in relevance in the cross-holding universe over the last few years. The restructuring of Softbank into Softbank Group and Softbank Corp in late 2018 is likely a primary driver of this. Looking at holders of other stocks on the righthand-side chart, we can see that far and away Financials dominate the holders landscape.

## Size considerations

As highlighted above, around 12% of listed market cap is held by other companies at the market level. These effects do differ as we look at different company size bands. Looking at large caps, which we define as the top 70% of free float market capitalization, we see that, unsurprisingly, they are associated with a slightly lower impact from cross-shareholdings. We estimate that around 10% of our large cap universe is held by other listed companies.

Figure 71: Around 12% of the total market is cross-held
![](images/51e24a260f6c4fa65fd1c8c5e7e9448d2aadbf4be3d4b52b45c5523a64ebd1f7.jpg)
Source: UBS Quant Research, FactSet. Held stock perspective

Figure 72: Large caps - Around 10% is cross-held
![](images/46b6e258ff6038185d821f0e3834b19f8a9d45b6b92b3bebe2c3ff5bf8e45167.jpg)
Source: UBS Quant Research, FactSet. Held stock perspective

As we move down the market cap spectrum, we find that a higher percentage of stocks are cross-held by other Japanese listcos. Looking at mid caps, which we define as the 15% of free float market cap following our large cap cohort, we see around 14% of market cap is cross-held. Small caps, which we define as the balance of free float market cap in our universe, see the largest percentage of market cap held by other listed companies, at around 17%.

Figure 73: Mid caps - Around 14% is cross-held
![](images/4480304866c4cb4db7a3f8da21c4d9d3646a4cbc00186a8c10faceba85a4237d.jpg)
Source: UBS Quant Research, FactSet. Held stock perspective

Figure 74: Small caps - Around 17% is cross-held
![](images/69a264c66f023b53dd774105a1f39258f7d47edc69d273682efee425a0774fb1.jpg)
Source: UBS Quant Research, FactSet. Held stock perspective

While we have seen the percentage of cross-holders on company registries decline across the board over the last decade plus, the decline has been more significant in the small- and mid-cap spaces. Interestingly, the decline from peak amongst our large cap cohort of stocks has been only around 4%, vs. 7% and 6% for mid and small caps, respectively.

## Holding size distribution

To better understand the distribution of these different magnitudes of holdings, we can look at the count of cross-held stocks arranged by how much of their market cap is cumulatively held by other corporates. We have divided our universe into five different bands. Looking at held stocks that have less than 5% and between 5% and 10% of their registry owned by other listed companies, we see this group accounts for 73.5% of the total universe of cross-held stocks by number.

At the other end of the spectrum, we can look at heavily cross-held companies based on cumulative cross-shareholder ownership. This will also include companies that have a large number of holders, as well as more concentrated ones (in which case we would view them as associates, listed subsidiaries and/or key strategic holdings). Stocks with greater than 10% but less than 33% of market cap held by cross-holders account for 16.8% of total cross-held stocks. For the two buckets greater than 33.3%, these are relatively small cohorts accounting for 9.7% of total cross-held stocks by count.

Figure 75: Breakdown of cross-held stocks by largest percentage of cross-holding ownership
![](images/8d2a1989c1ec60e95ae63ced28593f2561bbda34490499d45fe1325a1e8f0f0d.jpg)
Source: UBS Quant Research, FactSet

Figure 76: Cross-held stocks ownership stake distribution - large caps
![](images/105b192cc2535b8d6291f23b935f72d1852c7b5ad57002665ad84d140b932535.jpg)
Source: UBS Quant Research, FactSet

Further drilling down into the differences in cross-shareholder ownership stake by size of the cross-held company, we can see some differences across the size spectrum. The component of large cap stocks which are listed subsidiaries / affiliates is relatively small, standing currently only at 2 (Japan Post Bank and NTT Data). On the other hand, 87.4% of large cap stocks are cross-held by all small stakes (less than 5% holding).

Figure 77: Cross-held stocks ownership stake distribution - mid cap stocks
![](images/94bbeaf552680caf4bdbf1542b841bd9c2000abed9a7d573fd0f00b8c9c4b487.jpg)
Source: UBS Quant Research, FactSet

Figure 78: Cross-held stocks ownership stake distribution - small cap stocks
![](images/6c0a2186e1ae061032289c30deea180f1765eace44c4dc8723f208f26ddd1244.jpg)
Source: UBS Quant Research, FactSet

Mid-caps have a largely similar breakdown, with around 6 stocks that have other Japanese companies exerting a significant level of corporate control. Names here would include the likes of LY Corp, Nippon Sanso and Kyowa Kirin. Small stakes are also the majority of the biggest holders in the mid cap stocks. Looking at small cap stocks, we see a more spread out distribution.

## Holding type distribution

To better understand the dynamics of cross-holdings, we also feel that is important to try to look at different relationships between companies. One proxy for this is bilateral vs. unilateral cross-holding relationships. Typically, bilateral holdings are more representative of cross-holding relationships to cement business ties, while unilateral holdings may relate to holding / parent company and subsidiary relationships. As years have passed, these original relationships may have broken down or changed over time, but we can still capture some of these dynamics in the data.

Figure 79: Total number of cross-holding relationships broken down by bilateral and unilateral holdings
![](images/6b1253d6b29d42a0dde9983440a1eb6105747d394505b9817c0c64e3bade7073.jpg)
Source: UBS Quant Research, FactSet

Figure 80: Number of unilateral and bilateral relationships amongst stocks with >10% of market cap held by other listed companies
![](images/ec99386f7e5bfd236527c14e0e6cccdfe8a54307be40eca744476a1287b00b3d.jpg)
Source: UBS Quant Research, FactSet

In total, we have about 42,000 different relationships roughly split between bilateral and unilateral relationships. When we drill down into stocks that have "significant" crossholding stakes, which we define as >10%, we can see that the split is much more tilted towards unilateral relationships. We believe this is due to the historical dynamics of parent / child relationships and listed subsidiaries and affiliates.

Figure 81: Breakdown of universe by unilateral only held stocks, bilateral held stocks and stocks with no crossholdings
![](images/a41da3d00056b5105edf14daad0ffb9b83755637f2b8c907832e265e998a8c0f.jpg)
Source: UBS Quant Research, FactSet

Figure 82: Significant cross-holdings (>10%): Breakdown by unilateral and bilateral held stocks
![](images/0794cd1b9dba9bec7ae59f1645a6c62fc701c55c9d185d30d4b272e5110fd8aa.jpg)
Source: UBS Quant Research, FactSet

Moving from the total number of relationships to the company level, we can see that around two thirds of stocks have at least one bilateral cross-holding, while 30% have only unilateral holders and 10% have no cross-holders. If we strictly look at significant cross-holdings (>10%), we can see that the unilateral holdings are much more prevalent in this space, as highlighted in the chart above on the right.

## Cross-holding League Tables

To better understand the practical implications of different cross-shareholding relationships, we have created the below screens of different companies which stand out from a cross-shareholding perspective.

Figure 83: Biggest holders: largest portfolios of crossholdings by market value
![](images/56b1e4027c32d457b84ec3e8b6cf1d5814434dd021195e5ec03fa87e7b6c1e5e.jpg)
Source: UBS Quant Research, FactSet

Figure 84: Most holdings: largest number of cross-holdings by count
![](images/badab28701e0f3b56c3e0745c9ac190c2d29f3bb051db1fae40c448f3666e5fe.jpg)
Source: UBS Quant Research, FactSet

In the figures above, we highlight the stocks with the largest portfolios of cross-holdings by market value and count, respectively. By value, it is dominated by very large corporate groups such as Toyota and Softbank, as well Financials such as MUFG and Japan Post. If we look at count, we can see that it is dominated by mega Banks and Insurance companies. This is likely due to the maintenance of post-war keiretsu relationships which were often organised around various Financial entities.

Figure 85: Most non-significant stakes (holdings <10%)
![](images/14c405942a5fe912354d065df3522fe284d77c6529871e71c7293af2d7e6b9dd.jpg)
Source: UBS Quant Research, FactSet

Figure 86: Largest number of significant stakes (>10%)
![](images/c94621b673215599937d8c9468d50c744ba86cde22291420a6cf933071036d7d.jpg)
Source: UBS Quant Research, FactSet

If we break down holdings by stake size into non-significant (<10%) and significant (>10%), we can see that non-significant cross-holdings are dominated by Financial companies, while significant stakes are dominated by major corporates and trading companies. We can further drill down to look at the companies that have the largest number of listed subsidiaries, defined by holdings >50%. Aeon notably stands out, with 12 listed subsidiaries with greater than 50% ownership.

Figure 87: Parent holdings: largest number of controlling stakes (>33% ownership)
![](images/36b45248b103ad88ab7323bfa89d34e0da34ab5142f328d41228cd7857e19c21.jpg)
Source: UBS Quant Research, FactSet

Figure 88: Parent holdings: largest number of listed subsidiaries (>50% ownership)
![](images/382b547e9e28e7f1c64e78a5c412550c8e20faaa0397da662a375f9f4dfd4817.jpg)
Source: UBS Quant Research, FactSet. For stocks with market cap > US\$1bn

In addition to understanding who holds the most cross-holdings, we can also look at which companies are the most "cross-held"; that is, that have the highest percentage of their market cap held by other listed companies.

Figure 89: Most held: stocks with the largest percentage of other Japanese listed companies on their register

![](images/bb686bd6466ce875e0f525dcb2d3e582b856d500e84838bd0059532f6417bdee.jpg)
Source: UBS Quant Research, FactSet. For stocks with market cap > US\$1bn. N.B. Lawson and Benefit One are currently being acquired and may be delisted in the future.

Figure 90: Holdings relative to market cap
![](images/26e03c2ba28bb44ab97f94629856c965da545ed1350c7ebeab69b7f7348d43e8.jpg)
Source: UBS Quant Research, FactSet. For stocks with market cap > US\$1bn

Another instructive view is to look at the percentage of holdings relative to market cap. Here we can see that we have a large number of stocks where the value of their holdings accounts for more than 50% of their market cap. This covers a number of popular "stub" situations such as Keisei Electric Rail, Kyoto Financial and Toyota Industries, amongst others.

# Appendix: Other cross-shareholding factors performance summary

In the sections below, we conduct a simple assessment of other cross-holding related factors that we have proposed.

## Factor 1: Holdings Value

Perspective: Holders

Description and Rationale: We arrange the universe by the monthly value of holders' value of holdings into terciles and compare with stocks with no cross-holdings (Q0). Q3 represents stocks with the largest value of holdings, and Q1 consists of stocks with the least value of holdings. This is a relatively simple of way of assessing how the market treats stocks with a high and low value of holdings.

Figure 91: Holdings Value - Number of stocks in each bucket
![](images/f644dc9faa7f276cf32d9baf6f5fc26c8f27142d8b4f6a465e8d443b5c49f31e.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 92: Holdings Value - cumulative performance by bucket (equal weight)
![](images/81269ef4bd187582bc584120e0a9bf0c4a22419add0497d2cfdf5b458b9b87df.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Results: Q3 and Q2 don't see significant differentiation with each other, though do outperform Q1. Inter-tercile returns don't appear to have a strong trend.

Figure 93: Holdings Value - monthly return by bucket
![](images/2c286941b34722c028f9a9e870be4b2c4cc959dbe3c770f4e9d1eac2d6cc6713.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 94: Holdings Value - long / short returns (Q3 less Q1)
![](images/63b31379900381b29938567c360dea8aba8def104b756f568b20281d6e86f9de.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

## Factor 2: Held Percentage

## Perspective: Held Stocks

Description and Rationale: We arrange the universe by the monthly value of holdings on a held stock's register relative to the held stock's market cap. Q3 represents stocks with the largest percentage of ownership from cross-holders, while Q1 consists of stocks with the lowest percentage of ownership from cross-holders. Q0 represents stocks that are not held. This allows us to assess how the market differentiates stocks that are crossheld.

Figure 95: Held Percentage - Number of stocks in each bucket
![](images/2b92aa40cf13b4562abf4567befb58f0a6828344f2fe8e0eeb8ae92e31f49f8c.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 96: Held Percentage - cumulative performance by bucket (equal weight)
![](images/a953884c98872ca497dc303a4c2e9ad3215ee2af07a0cf492dfdb79bdf2cf409.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Results: Quantile performance looks relatively unintuitive, with Q2 showing stronger performance than either Q1 or Q3. Interestingly, Q0 shows very poor performance, though we suspect this may be a small cap effect as generally small caps are more likely to have no cross-holders on their registers.

Figure 97: Held Percentage - monthly return by bucket
![](images/85e1b7a601b711dacac0ddfddac0d7b162d74ebe61f1688a1562cede1bd3a6fc.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 98: Held Percentage - long / short returns (Q1 less Q3)
![](images/633a325386b7a81571a4f3507a70a7b423b42a8402b881e5e9e3ee74e5938340.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

## Factor 3: Holdings Less Held Percentage

## Perspective: Holders/ Held Stocks

Description and Rationale: In order to assess whether the market looks at the relative degree to which a stock is a cross-holder or cross-held, we look at each stock's Holding Percentage less its Held Percentage. Q3 represents stocks with more holdings relative to other companies holdings in it, on a percentage basis. Q1 consists of stocks that have a low percentage of holdings and/or are heavily cross-held.

Figure 99: Holdings Less Held Percentage - Number of stocks in each tercile
![](images/52a9eebda5266adb3010379148be15d8eab822c2e409893148ab3095c3f9b69b.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 100: Holdings Less Held Percentage - cumulative performance by tercile (equal weight)
![](images/168c4edfd5f5cfcaff1e1c388e8c6a01b560e296aabd62c6e22b340645ca659f.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Results: There were no significant differences between the terciles' performance, but Q3 marginally outperformed both Q2 and Q1. While the scale is low, the long/short performance does show a relatively consistent trend from 2009 onward. While it may risk over-engineering, this could mean that there is something interesting about the relative cross-holding positon of a stock. It may be worth revisiting in the future.

Figure 101: Holdings Less Held Percentage - monthly return by tercile
![](images/78d0c40292fd1901df305e643514c3befa3a5fa0e347b612e3d96784d7f15a21.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 102: Holdings Less Held Percentage - long / short returns (Q3 less Q1)
![](images/076c7a62e5ff1295743d8bbf31b1406ca374e347082481ac7ce8e7cd196478b2.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

# Factor 4: Holding Shares Change (Banks and Insurance)

Perspective: Holders (only for Banks and Insurance)

Description and Rationale: Expanding from our event study, we look at Holding Shares Change again, but this time solely focusing on Banks and Insurance, which have been ahead of the curve on unwinding. We believe the performance of this factor can potentially be indicative of what to expect in the broader environment as companies beyond Banks and Insurance increasingly embrace cross-shareholding unwinds.

Figure 103: Holdings Percentage Change - Number of stocks in each bucket
![](images/a73084e50cc2b292d333a627ae351324d0f7b18ab52576e0229a039dd8b75621.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 104: Holdings Percentage Change - Cumulative performance by bucket (equal weight)
![](images/982d5cdf3e79b39e8e4bbba9120008080024979d8184c181d9bdb7e03de058ae.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Results: There is no clear monotonic spread between the descending buckets, but the -Q3 bucket outperformed all other buckets. Long / short performance looks quite attractive with a largely upward trend since 2012. Drawdowns have been relatively shallow. We believe this could be an interesting preview of what to expect across the broader market as more companies and sectors engage in net cross-holding unwinds.

Figure 105: Holdings Percentage Change - monthly return by bucket
![](images/b3c7624de16a7a5b2dbb4feb385c9e02eb7b32e9ad9b7c9a5e2f3340056db01b.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

Figure 106: Holdings Percentage Change - long / short returns (Q3 less Q0)
![](images/ce696bb2b9afb4d860295bcf19ff7b99229c088408dde2b8d8f6899c56b327ed.jpg)
Source: UBS Quant Research, FactSet. For stocks with 6m ADV of at least US\$500k

## Valuation Method and Risk Statement

Our quantitative models rely on reported financial statement information, consensus earnings forecasts and stock prices. Errors in these numbers are sometimes impossible to prevent (as when an item is mis-stated by a company). Also, the models employ historical data to estimate the efficacy of stock selection strategies and the relationships among strategies, which may change in the future. Additionally, unusual company-specific events could overwhelm the systematic influence of the strategies used to rank and score stocks.

## Required Disclosures

This document has been prepared by UBS Securities Asia Limited, an affiliate of UBS AG. UBS AG, its subsidiaries, branches and affiliates, including Credit Suisse AG and its subsidiaries, branches and affiliates are referred to herein as "UBS".

For information on the ways in which UBS manages conflicts and maintains independence of its UBS Global Research product; historical performance information; certain additional disclosures concerning UBS Global Research recommendations; and terms and conditions for certain third party data used in research report, please visit https://www.ubs.com/disclosures. Unless otherwise indicated, information and data in this report are based on company disclosures including but not limited to annual, interim, quarterly reports and other company announcements. The figures contained in performance charts refer to the past; past performance is not a reliable indicator of future results. Additional information will be made available upon request. UBS Securities Co. Limited is licensed to conduct securities investment consultancy businesses by the China Securities Regulatory Commission. UBS acts or may act as principal in the debt securities (or in related derivatives) that may be the subject of this report. This recommendation was finalized on: 17 May 2024 07:17 PM GMT. UBS has designated certain UBS Global Research department members as Derivatives Research Analysts where those department members publish research principally on the analysis of the price or market for a derivative, and provide information reasonably sufficient upon which to base a decision to enter into a derivatives transaction. Where Derivatives Research Analysts coauthor research reports with Equity Research Analysts or Economists, the Derivatives Research Analyst is responsible for the derivatives investment views, forecasts, and/or recommendations. Quantitative Research Review: UBS Global Research publishes a quantitative assessment of its analysts' responses to certain questions about the likelihood of an occurrence of a number of short term factors in a product known as the 'Quantitative Research Review'. Views contained in this assessment on a particular stock reflect only the views on those short term factors which are a different timeframe to the 12-month timeframe reflected in any equity rating set out in this note. For the latest responses, please see the Quantitative Research Review Addendum at the back of this report, where applicable. For previous responses please make reference to (i) previous UBS Global Research reports; and (ii) where no applicable research report was published that month, the Quantitative Research Review which can be found at https://neo.ubs.com/ quantitative, or contact your UBS sales representative for access to the report or the Quantitative Research Team on qa@ubs.com. A consolidated report which contains all responses is also available and again you should contact your UBS sales representative for details and pricing or the Quantitative Research team on the email above.

## Analyst Certification:

Each research analyst primarily responsible for the content of this research report, in whole or in part, certifies that with respect to each security or issuer that the analyst covered in this report: (1) all of the views expressed accurately reflect his or her personal views about those securities or issuers and were prepared in an independent manner, including with respect to UBS, and (2) no part of his or her compensation was, is, or will be, directly or indirectly, related to the specific recommendations or views expressed by that research analyst in the research report.

UBS Global Research: Global Equity Rating Definitions
<table><tr><td rowspan=1 colspan=1>12-Month Rating</td><td rowspan=1 colspan=1>Definition</td><td rowspan=1 colspan=1>Coverage1</td><td rowspan=1 colspan=1>IB Services²</td></tr><tr><td rowspan=1 colspan=1>Buy</td><td rowspan=1 colspan=1>FSR is &gt; 6% above the MRA.</td><td rowspan=1 colspan=1>51%</td><td rowspan=1 colspan=1>36%</td></tr><tr><td rowspan=1 colspan=1>Neutral</td><td rowspan=1 colspan=1>FSR is between -6% and 6% of the MRA</td><td rowspan=1 colspan=1>40%</td><td rowspan=1 colspan=1>38%</td></tr><tr><td rowspan=1 colspan=1>Sell</td><td rowspan=1 colspan=1>FSR is &gt; 6% below the MRA.</td><td rowspan=1 colspan=1>8%</td><td rowspan=1 colspan=1>33%</td></tr><tr><td rowspan=1 colspan=1>Short-Term Rating</td><td rowspan=1 colspan=1>Definition</td><td rowspan=1 colspan=1>Coverage³</td><td rowspan=1 colspan=1>IB Services4</td></tr><tr><td rowspan=1 colspan=1>Buy</td><td rowspan=1 colspan=1>Stock price expected to rise within three months from the time therating was assigned because of a specific catalyst or event.</td><td rowspan=1 colspan=1>&lt;1%</td><td rowspan=1 colspan=1>&lt;1%</td></tr><tr><td rowspan=1 colspan=1>Sell</td><td rowspan=1 colspan=1>Stock price expected to fall within three months from the time therating was assigned because of a specific catalyst or event.</td><td rowspan=1 colspan=1>&lt;1%</td><td rowspan=1 colspan=1>&lt;1%</td></tr></table>

Source: UBS. Rating allocations are as of 31 March 2024.

2:Percentage of companies within the 12-month rating category for which investment banking (IB) services were provided within the past 12 months.

3:Percentage of companies under coverage globally within the Short-Term rating category.

4:Percentage of companies within the Short-Term rating category for which investment banking (IB) services were provided within the past 12 months.

KEY DEFINITIONS: Forecast Stock Return (FSR) is defined as expected percentage price appreciation plus gross dividend yield over the next 12 months. In some cases, this yield may be based on accrued dividends. Market Return Assumption (MRA) is defined as the one-year local market interest rate plus 5% (a proxy for, and not a forecast of, the equity risk premium). Under Review (UR) Stocks may be flagged as UR by the analyst, indicating that the stock's price target and/or rating are subject to possible change in the near term, usually in response to an event that may affect the investment case or valuation. Short-Term Ratings reflect the expected near-term (up to three months) performance of the stock and do not reflect any change in the fundamental view or investment case. Equity Price Targets have an investment horizon of 12 months.

EXCEPTIONS AND SPECIAL CASES: UK and European Investment Fund ratings and definitions are: Buy: Positive on factors such as structure, management, performance record, discount; Neutral: Neutral on factors such as structure, management, performance record, discount; Sell: Negative on factors such as structure, management, performance record, discount. Core Banding Exceptions (CBE): Exceptions to the standard +/-6% bands may be granted by the Investment Review Committee (IRC). Factors considered by the IRC include the stock's volatility and the credit spread of the respective company's debt. As a result, stocks deemed to be very high or low risk may be subject to higher or lower bands as they relate to the rating. When such exceptions apply, they will be identified in the Company Disclosures table in the relevant research piece.

Research analysts contributing to this report who are employed by any non-US affiliate of UBS Securities LLC are not registered/ qualified as research analysts with FINRA. Such analysts may not be associated persons of UBS Securities LLC and therefore are not subject to the FINRA restrictions on communications with a subject company, public appearances, and trading securities held by a research analyst account. The name of each affiliate and analyst employed by that affiliate contributing to this report, if any, follows.

UBS AG, Singapore Branch: Jia Li Mok, CFA.UBS AG Hong Kong Branch: Aaron Guo, CFA, Jessica SU, Will Stephens.UBS AG London Branch: Claire Jones.UBS Securities Australia Ltd: James Cameron, Oliver Antrobus, CFA, Paul Winter.UBS Securities Co. Limited: Cathy Fang, PhD, Lynce Wang, FRM.UBS Securities Japan Co., Ltd.: Nozomi Moriya.UBS Securities LLC: Jaiwish Nolan. The views in this report are based on UBS's proprietary quantitative models. These views are made independently of the recommendations of UBS's fundamental equity research analysts

Unless otherwise indicated, please refer to the Valuation and Risk sections within the body of this report. For a complete set of disclosure statements associated with the companies discussed in this report, including information on valuation and risk, please contact UBS Securities LLC, 1285 Avenue of Americas, New York, NY 10019, USA, Attention: Investment Research.

UBS is acting as buy side advisor for the consortium buyer which include Osaka Gas and Sumitomo Corporation to acquire 25% stake in AG&P LNG Marketing Pte Ltd, currently controlled by I Squared Capital (ISQ).

UBS Securities Japan Co., Ltd. has been appointed as the financial advisor to KDDI Corporation in relation to the acquisition of Lawson, Inc.

Additional Prices: Japan Post Bank, ¥1539.5 (17 May 2024); Japan Post Holdings, ¥1452.5 (17 May 2024); SoftBank Corp., ¥1919 (17 May 2024); Renault, €50.20 (17 May 2024); Toei Animation, ¥2390 (17 May 2024); Mitsubishi UFJ Financial Group, ¥1553.5 (17 May 2024); T&D Holdings, ¥2512 (17 May 2024); Benefit One, ¥2168 (17 May 2024); Denso, ¥2633 (17 May 2024); Komatsu, ¥4595 (17 May 2024); Mitsubishi Corporation, ¥3372 (17 May 2024); Sumitomo Mitsui Financial Group, ¥9723 (17 May 2024); Keisei Electric Railway, ¥5820 (17 May 2024); NTT, ¥152 (17 May 2024); Kyowa Kirin, ¥2613 (17 May 2024); LY Corp, ¥393 (17 May 2024); Mitsu Fudosan, ¥1455 (17 May 2024); SoftBank Group, ¥8550 (17 May 2024); Hyakugo Bank, ¥624 (17 May 2024); Aeon Co Ltd, US\$21.1 (16 May 2024); Toyota Industries Corporation, ¥14830 (17 May 2024); Nikon, ¥1667.5 (17 May 2024); Lawson, ¥10335 (17 May 2024); MODEC, ¥2804 (17 May 2024); Alibaba Group, US\$87.87 (17 May 2024); Nippon Sanso Holdings, ¥4600 (17 May 2024); Kao, ¥6944 (17 May 2024); Sumitomo Corporation, ¥4109 (17 May 2024); Nissan Motor, ¥552 (17 May 2024); Toyota Motor, ¥3436 (17 May 2024); Aeon, ¥3304 (17 May 2024); Mizuho Financial Group, ¥3134 (17 May 2024); NTT Data Group, ¥2283.5 (17 May 2024); Arms Holdings Plc, US\$114.27 (16 May 2024); Aeon Mall, ¥1818.5 (17 May 2024); Okaya & Co., ¥17470 (17 May 2024); Mitsubish Logisnext, ¥1687 (17 May 2024); Source: UBS. All prices as of local market close

## UBS Global Research Disclaimer

This document has been prepared by UBS Securities Asia Limited, an affiliate of UBS AG. UBS AG, its subsidiaries, branches and affiliates, including Credit Suisse AG and its subsidiaries, branches and affiliates are referred to herein as "UBS".

Any opinions expressed in this document may change without notice and are only current as of the date of publication. Different areas, groups, and personne within UBS may produce and distribute separate research products independently of each other. For example, research publications from UBS CIO are produced by UBS Global Wealth Management. UBS Global Research is produced by UBS Investment Bank. Research methodologies and rating systems of each separate research organization may differ, for example, in terms of investment recommendations, investment horizon, model assumptions, and valuation methods. As a consequence, except for certain economic forecasts (for which UBS CIO and UBS Global Research may collaborate), investment recommendations, ratings, price targets, and valuations provided by each of the separate research organizations may be different, or inconsistent. You should refer to each relevant research product for the details as to their methodologies and rating system. Not all clients may have access to all products from every organization. Each research product is subject to the policies and procedures of the organization that produces it.

This document is provided solely to recipients who are expressly authorized by UBS to receive it. If you are not so authorized you must immediately destroy the document.

UBS Global Research is provided to our clients through UBS Neo, and in certain instances, UBS.com and any other system or distribution method specifically identified in one or more communications distributed through UBS Neo or UBS.com (each a system) as an approved means for distributing UBS Global Research. It may also be made available through third party vendors and distributed by UBS and/or third parties via e-mail or alternative electronic means.

All UBS Global Research is available on UBS Neo. Please contact your UBS sales representative if you wish to discuss your access to UBS Neo. Where UBS Globa Research refers to "UBS Evidence Lab Inside" or has made use of data provided by UBS Evidence Lab and you would like to access that data please contact your UBS sales representative. UBS Evidence Lab data is available on UBS Neo. The level and types of services provided by UBS Global Research and UBS Evidence Lab to a client may vary depending upon various factors such as a client's individual preferences as to the frequency and manner of receiving communications, a client's risk profile and investment focus and perspective (e.g., market wide, sector specific, long-term, short-term, etc.), the size and scope of the overall client relationship with UBS Global Research and UBS Evidence Lab and legal and regulatory constraints.

When you receive UBS Global Research through a system, your access and/or use of such UBS Global Research is subject to this UBS Global Research Disclaimer and to the UBS Neo Platform Use Agreement (the "Neo Terms") together with any other relevant terms of use governing the applicable System.

When you receive UBS Global Research via a third party vendor, e-mail or other electronic means, you agree that use shall be subject to this UBS Global Research Disclaimer, the Neo Terms and where applicable the UBS Investment Bank terms of business (https://www.ubs.com/global/en/investment-bank/regulatory.html) and to UBS's Terms of Use/Disclaimer (https://www.ubs.com/global/en/legalinfo2/disclaimer.html). In addition, you consent to UBS processing your personal data and using cookies in accordance with our Privacy Statement (https://www.ubs.com/global/en/legalinfo2/privacy.html) and cookie notice (https://www.ubs.com/ global/en/legal/privacy/users.html).

If you receive UBS Global Research, whether through a System or by any other means, you agree that you shall not copy, revise, amend, create a derivative work, provide to any third party, or in any way commercially exploit any UBS research provided via UBS Global Research or otherwise, and that you shall not extract data from any research or estimates provided to you via UBS Global Research or otherwise, without the prior written consent of UBS.

In certain circumstances (including for example, if you are an academic or a member of the media) you may receive UBS Global Research otherwise than in the capacity of a client of UBS and you understand and agree that (i) the UBS Global Research is provided to you for information purposes only; (ii) for the purposes of receiving it you are not intended to be and will not be treated as a “client” of UBS for any legal or regulatory purpose; (iii) the UBS Global Research must not be relied on or acted upon for any purpose; and (iv) such content is subject to the relevant disclaimers that follow.

This document is for distribution only as may be permitted by law. It is not directed to, or intended for distribution to or use by, any person or entity who is a citizen or resident of or located in any locality, state, country or other jurisdiction where such distribution, publication, availability or use would be contrary to law or regulation or would subject UBS to any registration or licensing requirement within such jurisdiction.

This document is a general communication and is educational in nature; it is not an advertisement nor is it a solicitation or an offer to buy or sell any financia instruments or to participate in any particular trading strategy. Nothing in this document constitutes a representation that any investment strategy or recommendation is suitable or appropriate to an investor’s individual circumstances or otherwise constitutes a personal recommendation. By providing this document, none of UBS or its representatives has any responsibility or authority to provide or have provided investment advice in a fiduciary capacity or otherwise Investments involve risks, and investors should exercise prudence and their own judgment in making their investment decisions. None of UBS or its representatives is suggesting that the recipient or any other person take a specific course of action or any action at all. The recipient should carefully read this document in its entirety and not draw inferences or conclusions from the rating alone. By receiving this document, the recipient acknowledges and agrees with the intended purpose described above and further disclaims any expectation or belief that the information constitutes investment advice to the recipient or otherwise purports to meet the investment objectives of the recipient. The financial instruments described in the document may not be eligible for sale in all jurisdictions or to certain categories of investors.

Options, structured derivative products and futures (including OTC derivatives) are not suitable for all investors. Trading in these instruments is considered risky and may be appropriate only for sophisticated investors. Prior to buying or selling an option, and for the complete risks relating to options, you must receive a copy of "The Characteristics and Risks of Standardized Options." You may read the document at https://www.theocc.com/publications/risks/riskchap1.jsp or ask your salesperson for a copy. Various theoretical explanations of the risks associated with these instruments have been published. Supporting documentation for any claims, comparisons, recommendations, statistics or other technical data will be supplied upon request. Past performance is not necessarily indicative of future results. Transaction costs may be significant in option strategies calling for multiple purchases and sales of options, such as spreads and straddles. Because of the importance of tax considerations to many options transactions, the investor considering options should consult with his/her tax advisor as to how taxes affect the outcome of contemplated options transactions.

Mortgage and asset-backed securities may involve a high degree of risk and may be highly volatile in response to fluctuations in interest rates or other market conditions. Foreign currency rates of exchange may adversely affect the value, price or income of any security or related instrument referred to in the document. For investment advice, trade execution or other enquiries, clients should contact their local sales representative.

The value of any investment or income may go down as well as up, and investors may not get back the full (or any) amount invested. Past performance is not necessarily a guide to future performance. Neither UBS nor any of its directors, employees or agents accepts any liability for any loss (including investment loss) or damage arising out of the use of all or any of the Information.

Prior to making any investment or financial decisions, any recipient of this document or the information should take steps to understand the risk and return of the investment and seek individualized advice from his or her personal financial, legal, tax and other professional advisors that takes into account all the particular facts and circumstances of his or her investment objectives.

Any prices stated in this document are for information purposes only and do not represent valuations for individual securities or other financial instruments. There is no representation that any transaction can or could have been effected at those prices, and any prices do not necessarily reflect UBS's internal books and records or theoretical model-based valuations and may be based on certain assumptions. Different assumptions by UBS or any other source may yield substantially different results.

No representation or warranty, either expressed or implied, is provided in relation to the accuracy, completeness or reliability of the information contained in any materials to which this document relates (the "Information"), except with respect to Information concerning UBS. The Information is not intended to be a complete statement or summary of the securities, markets or developments referred to in the document. UBS does not undertake to update or keep current the Information. Any statements contained in this report attributed to a third party represent UBS's interpretation of the data, information and/or opinions provided by that third party either publicly or through a subscription service, and such use and interpretation have not been reviewed by the third party. In no circumstances may this document or any of the Information (including any forecast, value, index or other calculated amount ("Values")) be used for any of the following purposes:

(i) valuation or accounting purposes;

(ii) to determine the amounts due or payable, the price or the value of any financial instrument or financial contract; or

(iii) to measure the performance of any financial instrument including, without limitation, for the purpose of tracking the return or performance of any Value or of defining the asset allocation of portfolio or of computing performance fees.

By receiving this document and the Information you will be deemed to represent and warrant to UBS that you will not use this document or any of the Information for any of the above purposes or otherwise rely upon this document or any of the Information.

UBS has policies and procedures, which include, without limitation, independence policies and permanent information barriers, that are intended, and upon which UBS relies, to manage potential conflicts of interest and control the flow of information within divisions of UBS and among its subsidiaries, branches and affiliates. For further information on the ways in which UBS Global Research manages conflicts and maintains independence of its research products, historica performance information and certain additional disclosures concerning UBS Global Research recommendations, please visit https://www.ubs.com/disclosures.

UBS Global Research will initiate, update and cease coverage solely at the discretion of UBS Global Research Management, which will also have sole discretion on the timing and frequency of any published research product. The analysis contained in this document is based on numerous assumptions. All material information in relation to published research reports, such as valuation methodology, risk statements, underlying assumptions (including sensitivity analysis of those assumptions), ratings history etc. as required by the Market Abuse Regulation, can be found on UBS Neo. Different assumptions could result in materially different results.

The analyst(s) responsible for the preparation of this document may interact with trading desk personnel, sales personnel and other parties for the purpose of gathering, applying and interpreting market information. UBS relies on information barriers to control the flow of information contained in one or more areas within UBS into other areas, units, groups or affiliates of UBS. The compensation of the analyst who prepared this document is determined exclusively by UBS Global Research management and senior management (not including investment banking). Analyst compensation is not based on investment banking revenues; however, compensation may relate to the revenues of UBS and/or its divisions as a whole, of which investment banking, sales and trading are a part, and UBS as a whole.

For financial instruments admitted to trading on an EU regulated market: UBS (excluding UBS Securities LLC) acts as a market maker or liquidity provider (in accordance with the interpretation of these terms under English law or, if not carried out by UBS in the UK the law of the relevant jurisdiction in which UBS determines it carries out the activity) in the financial instruments of the issuer save that where the activity of liquidity provider is carried out in accordance with the definition given to it by the laws and regulations of any other EU jurisdictions, such information is separately disclosed in this document. For financial instruments admitted to trading on a non-EU regulated market: UBS may act as a market maker save that where this activity is carried out in the US in accordance with the definition given to it by the relevant laws and regulations, such activity will be specifically disclosed in this document. UBS may have issued a warrant the value of which is based on one or more of the financial instruments referred to in the document. UBS and its affiliates and employees may have long or short positions, trade as principal and buy and sell in instruments or derivatives identified herein; such transactions or positions may be inconsistent with the opinions expressed in this document.

Within the past 12 months UBS may have received or provided investment services and activities or ancillary services as per MiFID II which may have given rise to a payment or promise of a payment in relation to these services from or to this company.

United Kingdom: This material is distributed by UBS AG, London Branch to persons who are eligible counterparties or professional clients. UBS AG, London Branch is authorised by the Prudential Regulation Authority and subject to regulation by the Financial Conduct Authority and limited regulation by the Prudential Regulation Authority. Europe: Except as otherwise specified herein, these materials are distributed by UBS Europe SE, a subsidiary of UBS AG, to persons who are eligible counterparties or professional clients (as detailed in the Bundesanstalt fur Finanzdienstleistungsaufsicht (BaFin) Rules and according to MIFID) and are only available to such persons. The information does not apply to, and should not be relied upon by, retail clients. UBS Europe SE is authorised by the European Centra Bank (ECB) and regulated by the BaFin and the ECB. Germany, Luxembourg, the Netherlands, Belgium and Ireland: Where an analyst of UBS Europe SE has contributed to this document, the document is also deemed to have been prepared by UBS Europe SE. In all cases it is distributed by UBS Europe SE and UBS AG, London Branch. Turkey: Distributed by UBS AG, London Branch. No information in this document is provided for the purpose of offering, marketing and sale by any means of any capital market instruments and services in the Republic of Turkey. Therefore, this document may not be considered as an offer made or to be made to residents of the Republic of Turkey. UBS AG, London Branch is not licensed by the Turkish Capital Market Board under the provisions of the Capital Market Law (Law No. 6362). Accordingly, neither this document nor any other offering material related to the instruments/services may be utilized in connection with providing any capital market services to persons within the Republic of Turkey without the prior approval of the Capital Market Board. However, according to article 15 (d) (ii) of the Decree No. 32, there is no restriction on the purchase or sale of the securities abroad by residents of the Republic of Turkey. Poland: Distributed by UBS Europe SE (spolka z ograniczona odpowiedzialnoscia) Oddzial w Polsce regulated by the Polish Financial Supervision Authority. Where an analyst of UBS Europe SE (spolka z ograniczona odpowiedzialnoscia) Oddzial w Polsce has contributed to this document, the document is also deemed to have been prepared by UBS Europe SE (spolka z ograniczona odpowiedzialnoscia) Oddzial w Polsce. Russia: Prepared and distributed by UBS Bank (OOO). Should not be construed as an individual Investment Recommendation for the purpose of the Russian Law - Federal Law #39-FZ ON THE SECURITIES MARKET Articles 6.1- 6.2.Switzerland: Distributed by UBS AG to persons who are institutional investors only. UBS AG is regulated by the Swiss Financial Market Supervisory Authority (FINMA). Italy: Prepared by UBS Europe SE and distributed by UBS Europe SE and UBS Europe SE, Italy Branch. Where an analyst of UBS Europe SE, Italy Branch has contributed to this document, the document is also deemed to have been prepared by UBS Europe SE, Italy Branch. France: Prepared by UBS Europe SE and distributed by UBS Europe SE and UBS Europe SE, France Branch. Where an analyst of UBS Europe SE, France Branch has contributed to this document, the document is also deemed to have been prepared by UBS Europe SE, France Branch. Spain: Prepared by UBS Europe SE and distributed by UBS Europe SE and UBS Europe SE, Spain Branch. Where an analyst of UBS Europe SE, Spain Branch has contributed to this document, the document is also deemed to have been prepared by UBS Europe SE, Spain Branch. Sweden: Prepared by UBS Europe SE and distributed by UBS Europe SE and UBS Europe SE, Sweden Branch. Where an analyst of UBS Europe SE, Sweden Branch has contributed to this document, the document is also deemed to have been prepared by UBS Europe SE, Sweden Branch. South Africa: Distributed by UBS South Africa (Pty) Limited (Registration No. 1995/011140/07), an authorised user of the JSE and an authorised Financia Services Provider (FSP 7328). Saudi Arabia: This document has been issued by UBS AG (and/or any of its subsidiaries, branches or affiliates), a public company limited by shares, incorporated in Switzerland with its registered offices at Aeschenvorstadt 1, CH-4051 Basel and Bahnhofstrasse 45, CH-8001 Zurich. This publication has been approved by UBS Saudi Arabia (a subsidiary of UBS AG), a Saudi closed joint stock company incorporated in the Kingdom of Saudi Arabia under commercial register number 1010257812 having its registered office at Tatweer Towers, P.O. Box 75724, Riyadh 11588, Kingdom of Saudi Arabia. UBS Saudi Arabia is authorized and regulated by the Capital Market Authority to conduct securities business under license number 08113-37. UAE / Dubai: The information distributed by UBS AG Dubai Branch is only intended for Professional Clients and/or Market Counterparties, as classified under the DFSA rulebook. No other person should act upon this material/communication. The information is not for further distribution within the United Arab Emirates. UBS AG Duba Branch is regulated by the DFSA in the DIFC. UBS Investment Bank is not licensed to provide banking services in the UAE by the Central Bank of the UAE, nor is it licensed by the UAE Securities and Commodities Authority. Israel: This Material is distributed by UBS AG, London Branch. UBS Securities Israel Ltd is a licensed Investment Marketer that is supervised by the Israel Securities Authority (ISA). UBS AG, London Branch and its affiliates incorporated outside Israel are not licensed under the Israeli Advisory Law. UBS may engage among others in issuance of Financial Assets or in distribution of Financial Assets of other issuers for fees or other benefits. UBS AG, London Branch and its affiliates may prefer various Financial Assets to which they have or may have an Affiliation (as such term is defined under the Israeli Advisory Law). Nothing in this Material should be considered as investment advice under the Israeli Advisory Law. This Material is being issued only to and/or is directed only at persons who are Eligible Clients within the meaning of the Israeli Advisory Law, and this Material must not be furnished to, relied on or acted upon by any other persons. United States: Distributed to US persons by either UBS Securities LLC or by UBS Financial Services Inc., subsidiaries of UBS AG; or by a group, subsidiary or affiliate of UBS AG that is not registered as a US broker-dealer (a ‘non-US affiliate’) to major US institutional investors only. UBS Securities LLC or UBS Financial Services Inc. accepts responsibility for the content of a report prepared by another non-US affiliate when distributed to US persons by UBS Securities LLC or UBS Financial Services Inc. All transactions by a US person in the securities mentioned in this report must be effected through UBS Securities LLC or UBS Financial Services Inc., and not through a non-US affiliate. UBS Securities LLC is not acting as a municipal advisor to any municipal entity or obligated person within the meaning of Section 15B of the Securities Exchange Act (the "Municipal Advisor Rule"), and the opinions or views contained herein are not intended to be, and do not constitute, advice within the meaning of the Municipal Advisor Rule. Canada: Distributed by UBS Securities Canada Inc., a registered investment dealer in Canada and a Member-Canadian Investor Protection Fund, or by another affiliate of UBS AG that is registered to conduct business in Canada or is otherwise exempt from registration. Brazil: Except as otherwise specified herein, this Material is prepared by UBS Brasil Corretora de Câmbio, Títulos e Valores Mobiliários S.A. (UBS Brasil CCTVM) to persons who are eligible investors residing in Brazil, which are considered to be Professional Investors (Investidores Profissionais), as designated by the applicable regulation, mainly the CVM Resolution No. 30 from the 11th of May 2021 (determines the duty to verify the suitability of products, services and transactions with regards to the client´s profile). UBS Brasil CCTVM is a subsidiary of UBS BB Servicos de Assessoria Financeira e Participacoes S.A. (“UBS BB”). UBS BB is an association between UBS AG and Banco do Brasil (through its subsidiary BB – Banco de Investimentos S.A.), of which UBS AG is the majority owner and which provides investment banking services and coverage in Brazil, Argentina, Chile, Paraguay, Peru and Uruguay. UBS Brasil CCTVM is regulated by the Comissao de Valores Mobiliarios (CVM) and by the Central Bank of Brazil. Ombudsman: 0800-940-0266/ https:// www.ubs.com/br/pt/ubsbb-investment-bank/ombudsman.html. UBS may hold relevant financial and commercial interest in relation to the company subject to this Research report. Hong Kong: Distributed by UBS Securities Asia Limited. Please contact local licensed persons of UBS Securities Asia Limited in respect of any matters arising from, or in connection with, the analysis or document Singapore: Distributed by UBS Securities Pte. Ltd. [Co. Reg. No.: 198500648C] or UBS AG, Singapore Branch. Please contact UBS Securities Pte. Ltd., an exempt financial adviser under the Singapore Financial Advisers Act (Cap. 110); or UBS AG, Singapore Branch, an exempt financial adviser under the Singapore Financial Advisers Act (Cap. 110) and a wholesale bank licensed under the Singapore Banking Act (Cap. 19) regulated by the Monetary Authority of Singapore, in respect of any matters arising from, or in connection with, the analysis or document. The recipients of this document represent and warrant that they are accredited and institutional investors as defined in the Securities and Futures Act (Cap. 289) Japan: Distributed by UBS Securities Japan Co., Ltd. to professional investors (except as otherwise permitted). Where this report has been prepared by UBS Securities Japan Co., Ltd., UBS Securities Japan Co., Ltd. is the author, publisher and distributor of the report. Distributed by UBS AG, Tokyo Branch to Professional Investors (except as otherwise permitted) in relation to foreign exchange and other banking businesses when relevant. Australia: Clients of UBS AG: Distributed by UBS AG (ABN 47 088 129 613 and holder of Australian Financial Services License No. 231087). For all other recipients: Distributed by UBS Securities Australia Ltd (ABN 62 008 586 481 and holder of Australian Financial Services License No. 231098). This document contains general information and/or general advice only and does not constitute personal financial product advice. As such, the Information in this document has been prepared without taking into account any investor’s objectives, financial situation or needs, and investors should, before acting on the Information, consider the appropriateness of the Information, having regard to their objectives, financial situation and needs. If the Information contained in this document relates to the acquisition, or potential acquisition of a particular financial product by a ‘Retail’ client as defined by section 761G of the Corporations Act 2001 where a Product Disclosure Statement would be required, the retail client should obtain and consider the Product Disclosure Statement relating to the product before making any decision about whether to acquire the product. For clients of Credit Suisse AG, Sydney Branch: Credit Suisse AG, Sydney Branch (ABN 17 061 700 712, AFSL 226896) is a separately licensed, related body corporate of UBS AG, Australia Branch and UBS Securities Australia Ltd. Credit Suisse AG, Sydney Branch has entered into an arrangement with UBS

Securities Australia Ltd to allow Credit Suisse AG to provide UBS Global Research to certain Australian domiciled wholesale clients of Credit Suisse AG, Sydney Branch’s Wealth Management Division. If you are receiving UBS Global Research from Credit Suisse, Sydney Branch’s Wealth Management Division, this UBS Global Research is issued under the license of UBS Securities Australia Limited. All disclosures and disclaimers contained within this document relating to or provided by UBS Securities Australia Ltd also apply to UBS Global Research received by clients of Credit Suisse AG, Sydney Branch’s Wealth Management Division. New Zealand: Distributed by UBS New Zealand Ltd. UBS New Zealand Ltd is not a registered bank in New Zealand. You are being provided with this publication or material because you have indicated to UBS that you are a “wholesale client” within the meaning of section 5C of the Financial Advisers Act 2008 of New Zealand (Permitted Client). This publication or material is not intended for clients who are not Permitted Clients (non-permitted Clients). If you are a nonpermitted Client you must not rely on this publication or material. If despite this warning you nevertheless rely on this publication or material, you hereby (i) acknowledge that you may not rely on the content of this publication or material and that any recommendations or opinions in such this publication or materia are not made or provided to you, and (ii) to the maximum extent permitted by law (a) indemnify UBS and its associates or related entities (and their respective Directors, officers, agents and Advisors) (each a ‘Relevant Person’) for any loss, damage, liability or claim any of them may incur or suffer as a result of, or in connection with, your unauthorised reliance on this publication or material and (b) waive any rights or remedies you may have against any Relevant Person for (or in respect of) any loss, damage, liability or claim you may incur or suffer as a result of, or in connection with, your unauthorised reliance on this publication or material. Korea: Distributed in Korea by UBS Securities Pte. Ltd., Seoul Branch. This report may have been edited or contributed to from time to time by affiliates of UBS Securities Pte. Ltd., Seoul Branch. This material is intended for professional/institutional clients only and not for distribution to any retail clients. Malaysia: This material is authorized to be distributed in Malaysia by UBS Securities Malaysia Sdn. Bhd (Capital Markets Services License No.: CMSL/A0063/2007). This material is intended for professional/institutional clients only and not for distribution to any retail clients. India: Distributed by UBS Securities India Private Ltd. (Corporate Identity Number U67120MH1996PTC097299) 2/F, 3 North Avenue, Maker Maxity, Bandra Kurla Complex, Bandra (East), Mumbai (India) 400051. Phone: +912261556000. It provides brokerage services bearing SEBI Registration Number: INZ000259830; and Research Analyst services bearing SEB Registration Number: INH000001204. Name of Compliance Officer Mr. Parameshwaran Shivaramakrishnan, Phone : +912261556151, Email : parameshwaran.s@ubs.com, Name of Grievance Officer Parameshwaran Shivaramakrishnan, Phone : +912261556151, Email: ol-ubs-sec-compliance@ubs.com Registration granted by SEBI, and certification from NISM in no way guarantee performance of the intermediary or provide any assurance of returns to investors. UBS may have debt holdings or positions in the subject Indian company/companies. UBS may have financial interests (e.g. loan/derivative products, rights to or interests in investments, etc.) in the subject Indian company / companies from time to time. Within the past 12 months, UBS may have received compensation for non-investment banking securities-related services and/or non-securities services from the subject Indian company/companies. The subject company/companies may have been a client/clients of UBS during the 12 months preceding the date of distribution of the research report with respect to investment banking and/or non-investment banking securities-related services and/or non-securities services. With regard to information on associates, please refer to the Annual Report at: https://www.ubs.com/global/en/about\_ubs/investor\_relations/annualreporting.html Taiwan: Except as otherwise specified herein, this material may not be distributed in Taiwan. Information and material on securities/instruments that are traded in a Taiwan organized exchange is deemed to be issued and distributed by UBS Securities Pte. LTD., Taipei Branch, which is licensed and regulated by Taiwan Financial Supervisory Commission. Save for securities/instruments that are traded in a Taiwan organized exchange, this material should not constitute "recommendation" to clients or recipients in Taiwan for the covered companies or any companies mentioned in this document. No portion of the document may be reproduced or quoted by the press or any other person without authorisation from UBS. Indonesia: This report is being distributed by PT UBS Sekuritas Indonesia and is delivered by its licensed employee(s), including marketing/sales person, to its client. PT UBS Sekuritas Indonesia, having its registered office at Sequis Tower Level 22 unit 22-1,Jl.Jend. Sudirman, kav.71, SCBD lot 11B, Jakarta 12190. Indonesia, is a subsidiary company of UBS AG and licensed under Capital Market Law no. 8 year 1995, a holder of broker-dealer and underwriter licenses issued by the Capital Market and Financial Institution Supervisory Agency (now Otoritas Jasa Keuangan/OJK). PT UBS Sekuritas Indonesia is also a member of Indonesia Stock Exchange and supervised by Otoritas Jasa Keuangan (OJK). Neither this report nor any copy hereof may be distributed in Indonesia or to any Indonesian citizens except in compliance with applicable Indonesian capital market laws and regulations. This report is not an offer of securities in Indonesia and may not be distributed within the territory of the Republic of Indonesia or to Indonesian citizens in circumstance which constitutes an offering within the meaning of Indonesian capital market laws and regulations.

The disclosures contained in research documents produced by UBS AG, London Branch or UBS Europe SE shall be governed by and construed in accordance with English law.

UBS specifically prohibits the redistribution of this document in whole or in part without the written permission of UBS and in any event UBS accepts no liability whatsoever for any redistribution of this document or its contents or the actions of third parties in this respect. Images may depict objects or elements that are protected by third party copyright, trademarks and other intellectual property rights. © UBS 2024. The key symbol and UBS are among the registered and unregistered trademarks of UBS. All rights reserved.