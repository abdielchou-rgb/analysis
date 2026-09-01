## Interest Rate Derivatives

## Term Funding Premium and the Term Structure of SOFR Swap Spreads

In a post-Libor world with SOFR as the floating rate benchmark, swap spreads are - to a considerable extent - a reflection of a kind of term premium. This is because the swap rate reflects the annualized return that can be locked in today from a strategy of rolling overnight risk-free loans over some horizon (say, 10 years), while the corresponding Treasury yield reflects the return on a term risk-free loan to that same horizon. The swap spread, being the difference between the two, is a reflection of the premium associated with committing funding to term

● Term Funding Premium is directly visible in the case of Treasury FRNs, which are floating rate notes that are linked to 3M Tbills but typically price and trade at a positive spread over that benchmark. This positive spread is the investor<sup>’</sup>s compensation for lending for a 2Y period, rather than rolling 3M Tbills - Term Funding Premium, in other words. In the much broader nominal Treasury market, Term Funding Premium is less directly visible, but nevertheless observable through swap spreads

● Of course, there are other factors that drive swap spreads in various different tenors. But this “Term Funding Premium<sup>”</sup> (or TFP for short) is a key determinant of the term structure of swap spreads - the higher the TFP on any given day, the more steeply inverted the term structure of spreads

• Motivated by this observation, we can measure the TFP on any given day as the negative of the slope of a regression line that fits maturity matched swap spreads on benchmark tenors (2s, 3s, 5s, 7s, 10s, 20s and 30s) versus their corresponding modified durations

• The intercept of this same fit also has an interpretation, as the maturity matched swap spread of a Treasury with zero duration. We call this the zero-duration swap spread

● Our new empirical fair value framework for swap spreads begins with the term structure. Specifically, we start by developing empirical models for the Term Funding Premium and zero-duration swap spreads. This gives us a way to project the slope and the intercept of the term structure of swap spreads …

● … but we cannot stop here. Swap spreads can, and do, deviate from the baseline value that would be indicated by the linear fit of the term structure. Moreover, these deviations are not noise-like, and can be systematic in nature. Therefore, we build a family of secondary empirical models (one for each major tenor, i.e., 2s, 5s, 10s and 30s) that explain much of the deviation in swap spreads from the term structure

● We describe all of these empirical models in this piece. Collectively, they define a 2-step empirical fair value framework for swap spreads across different maturities, but in a way that puts the term structure front and center. In principle, this should lead to better projections of swap spreads, when compared to individual fair value models for swap spreads in each sector that are calibrated without recognition of systematic term structure impacts

● Armed with these models, and projections for all the drivers, we project swap spreads in major benchmark tenors over the near term (\~1H24 horizon) as well as the medium term (YE24). Our current projections from such a framework point to wider swap spreads across much of the curve, except for the long end

## Term Funding Premium and the Term Structure of SOFR Swap Spreads

Since benchmark transition, swap spreads have become more tricky to model in stable fashion. To a considerable extent, this is because SOFR rates do not contain a credit element like Libor did, and that has made SOFR swap spreads somewhat less "macro" in nature. Instead, swap spreads - which now represent a differential between a risk free Treasury bond yield and expectations of a risk free benchmark rate - have become much more nuanced. Thankfully, it has not been entirely resistant to modeling, and we have indeed been able to find workable models for swap spreads in various sectors. We have described these models in detail (see, for instance, Interest Rate Derivatives 2024 Outlook) and they have proven reasonably useful in helping us to take forward looking views on swap spreads in each sector. But somewhat interestingly, it has been our experience that these models have been less accurate when it comes to taking views on the spread curve between two different maturity points. Said differently, there appear to be macro phenomena that impact all swap spreads in a way that is not fully captured by focusing on swap spreads in individual maturity sectors. This suggests that a more holistic approach is needed to understand the behavior of swap spreads across the curve.

To address this current limitation, we describe here a fundamentally different and novel way to think about swap spreads across the curve. Our approach begins with the very essence of what swap spreads represent in a world with risk free benchmark rates. We then add in sector specific elements to fully capture the effects of all the drivers of swap spreads in each maturity sector.

## The term structure of swap spreads embeds term funding premium

We begin by noting that swap spreads are essentially a form of term premium. Taking the 10-year sector as an example, it is worth noting that the maturity matched swap spread (defined as 10Y swap yield minus 10Y UST yield) reflects the difference in returns between (i) rolling 1-day risk-free loans in repo markets for ten years, and (ii) a risk-free 10-year term investment in the form of a US Treasury note. Thus, the negative of the swap spread (as we normally define it in the US) can be thought of as a form of term premium.

This notion of term premium is different from the term premium that is sought to be measured by metrics such as ACM term premium. Conceptually, the 10Y UST yield, which reflects the market's currently demanded return on a 10-year risk free term investment, can be thought of as the sum of three parts (see Figure 1):

• (a) the (unobservable) expected compounded average of risk free overnight returns over a ten year period,

• (b) the (also unobservable) compensation for fixing the borrower's rate for ten years, thereby absorbing interest rate risk that would otherwise rest with the borrower, and finally

• (c) a separate compensation for guaranteeing the borrower term funding for ten years, rather than being subject to rolling overnight borrowings for ten years.

Common measures of term premium attempt to estimate (b) plus (c) in the context of some model. But in a sense the last component (just (c) alone) here is also a form of term premium - or perhaps we can more appropriately call it a term funding premium (TFP), since it represents the market's price for guaranteeing term funding to the borrower.

One place where this term funding premium is directly observable is in the case of Treasury FRNs. These 2-year term floating rate notes (FRNs are currently issued only with 2-year maturity) pay coupons that are linked to 3M T-bill yields plus a spread. Thus, they produce returns that are similar to a strategy of rolling 3M T-bills over a 2-year horizon, but the (generally positive) spread represents the investor<sup>’</sup>s compensation for pre-committing to lend for 2 years, as opposed to only lending for 3 months at a time. To be sure, there are other elements that go into the FRN spread, such as scarcity and/or liquidity premia. But they do represent a rare case of term funding premia that is directly visible.

Of course, the bulk of the Treasury market is not FRNs. Fortunately, TFP is still somewhat observable from swap spreads. This is because the 10Y SOFR swap yield (in our example) reflects the sum of (a) and (b). Thus, the maturity matched swap spread gives us information about the term funding premium (or more specifically, the negative of term funding premium). To be sure, swap spreads are not pure measures of term funding premium. They can also reflect idiosyncratic factors such as recent flows in the market, liquidity preference for certain USTs over others, and more. But recognizing the link between swap spreads and TFP is our starting point for modeling swap spreads.

Figure 1: A conceptual illustration of term premium and term funding premium, and their connection to Treasury and SOFR swap rates

Diagram illustrating the breakdown of 10Y UST yields into its conceptual components

![](images/6d7a9cbb8cb437d232acf0e9dc581c1cc4ef061fda672f15d8565d0507366f47.jpg)
Source: J.P. Morgan.

In particular, even though the swap spread on any particular tenor can include various other effects, we note that the full term structure of swap spreads on any given day sheds light on term funding premium on that day. We illustrate this in Figure 2, which shows OTR maturity matched swap spreads (for 2s, 3s, 5s, 7s, 10s, 20s and 30s) plotted versus the modified duration of each OTR bond, as of two different selected dates. As can be seen, this term structure was fairly flat in late 2021, with a slope of minus 2.3. We can interpret this to mean that the market's term funding premium on that day was 2.3bp for each year of duration. Thus, all else equal, 10-year notes (with a duration of \~9 years) would need to deliver returns that are \~16bp higher than 2-year notes (with a duration of \~2 years) on a swap spread basis. The same term structure as of today is much steeper - the current term structure has a slope of -4.8, which implies a TFP of 4.8bp per year of duration risk. Thus, the slope of the fitted term structure, times minus 1, can be thought of as a measure of Term Funding Premium. A time series of this measure is shown in Figure 3.

Philip Michaelides (1-212) 834-2096philip.michaelides@jpmchase.comJ.P. Morgan Securities LLCArjun Parikh (1-212) 834-4436arjun.parikh@jpmchase.comJ.P. Morgan Securities LLC

Figure 2: The term structure of maturity matched swap spreads on any given day sheds light on Term Funding Premium

Maturity matched swap spread values in the 2Y, 5Y, 7Y, 10Y, 20Y, and 30Y sectors (yaxis, bp) versus the respective modified durations (x axis, years) as of two different selected dates (Dec 2021 and current), cross-sectional regression statistics and Term Funding Premium\* (bp/yr) values indicated in each period

![](images/376c1f9a913ef0a32af87bdc8c24a45e854936076c96cf095ca097fc3352b3f9.jpg)
Source: J.P. Morgan.
\* Term Funding Premium is defined as the negative of the slope of a regression of maturity matched swap spreads versus modified duration in benchmark sectors (2Y, 3Y, 5Y, 7Y, 10Y, 20Y and 30Y) on any given day

Figure 3: Term Funding Premium has risen considerably in recent years Term funding premium\*, Apr 2021 - Apr 2024; bp/year
![](images/5df5a9f413e2c29fb0d41c109956eeefa50108467a32832b85cdb23d6cf9dc92.jpg)
Source: J.P. Morgan.
\* Term Funding Premium is defined in the Figure 2 footnote

## Modeling Term Funding Premium

Thus far this measure of term funding premium is merely a distilled version of the term structure of swap spreads. We must find a way to model this based on underlying fundamental drivers for it to become a useful framework for modeling swap spreads themselves. We do this below.

One might logically expect this term funding premium to depend on factors that reflect supply and demand. This is indeed the case, and we include four factors that help to explain the variation in TFP over the past three years. The underlying drivers that we use are:

UST monthly duration supply, measured in 10Y equivalents. We use a 6-week moving average for smoothing purposes. We would expect TFP to depend on this with a positive coefficient.

The size of the Fed balance sheet, to capture QE/QT and its effect on term premia. We would expect TFP to depend on this with a negative coefficient as a result.

The aggregate AUM at core bond funds. As we have noted elsewhere (see 2024 Interest Rate Derivatives Outlook, 11/21/2023), bond funds are typically benchmarked to an index, and AUM growth has a fairly natural and passive demand-side effect of compressing term premia. Here too, we would expect TFP to depend on this factor with a negative coefficient.

Lastly, we use the RRP balance (in \$Tn) as a fourth factor. The sign of the dependence here is not obvious a priori. But it appears to matter through a substitution channel. A larger RRP balance, all else equal, has the effect of draining cash that would otherwise be available for deployment into bond markets. As such, higher RRP balances have an empirical partial beta that is positive.

Our model for term funding premium, based on these four factors, explains a significant portion of the variation over the past three years (Figure 4). In addition, as visually demonstrated in Figure 5, these factors appear to have been successful in capturing swings in term funding premia over this period of time.

Figure 4: An empirical model for Term Funding Premium
Statistics from regressing\* term funding premium (TFP)\*\* versus its drivers (units as indicated)
<table><tr><td></td><td>Coefficient</td><td>T-stat</td></tr><tr><td rowspan="3">Fed balance sheet size ($Tn) AUM at top 20 core bond funds ($bn) Monthly UST supply ($bn 10s) RRP ($Tn)</td><td>-1.42</td><td>-20.5</td></tr><tr><td>-0.0145</td><td>-19.4</td></tr><tr><td>0.0077 0.836</td><td>7.4 15.8</td></tr><tr><td colspan="2">Intercept Model stats R-sqrd Std. error</td><td>53.7 88%</td></tr></table>

Source: J.P. Morgan.
\* Regression period from Apr 2021 - Apr 2024
\*\* Term Funding Premium is defined in the Figure 2 footnote

Figure 5: Our empirical model for Term Funding Premium has been reasonably effective in tracking its target in recent years Term Funding Premium (TFP)\*, actual versus fair value\*\*, Apr 2021 - Apr 2024; bp/year
![](images/17476b7ee152b9db1f5bb32b9a6d01048823aad191e6ea07defc08790d1c2ad2.jpg)
Source: J.P. Morgan.
\* Term Funding Premium is defined in the Figure 2 footnote
\*\* Fair value for TFP is calculated as per the model detailed in the previous exhibit.

## Modeling zero duration swap spreads

The next step in our journey towards modeling the term structure of swap spreads is to find an empirical model for the intercept from the regression shown in Figure 2, since knowing the intercept as well as the slope of that regression gives us a first approximation of the term structure of swap spreads. As we have already discussed, the slope of that regression can be interpreted as term funding premium. Similarly, the intercept also has a natural interpretation - it represents the value of swap spreads on a hypothetical zero-duration Treasury.

Our model for this zero duration swap spread is shown in Figure 6. We use three factors to explain much of the variation in this quantity. The first of these is term funding premium itself, and it reflects a substitution effect - rising term funding premium would likely reflect an environment where investors are shortening spread duration, which would have the consequence of richening zero duration swap spreads. In other words, as the term structure becomes more inverted, the intercept tends to increase. A second factor in our model is the RRP balance - given its positive correlation to term funding premium, it is unsurprisingly also positively correlated to zero duration swap spreads. Finally, front end yield levels also appear to matter for zero duration swap spreads, with higher front end yields causing a decline in zero duration swap spreads. This model has been quite effective in tracking zero duration swap spreads, as shown in Figure 7.

Figure 6: Our empirical model for zero-duration swap spreads …
Statistics from regressing\* zero duration swap spreads\*\* versus its drivers (units as indicated)
<table><tr><td></td><td>Coeff</td><td>T-stat</td></tr><tr><td>Term funding premium (bp/year) RRP ($Tn) 3Mx3M OIS rate Intercept</td><td>8.09 4.23 -3.35</td><td>37.8 31.5 -37.0</td></tr><tr><td>Model stats R-sqrd Std. Error</td><td>-27.3 73% 2.21</td><td>-46.6</td></tr></table>

Source: J.P. Morgan.
\* Regression period from Apr 2021 - Apr 2024
\*\* Zero-duration swap spread is defined as the intercept from a regression of maturity matched swap spreads versus modified duration in benchmark sectors (2Y, 3Y, 5Y, 7Y, 10Y, 20Y and 30Y) on any given day
Figure 7: … has also been reasonably effective in tracking the actual value in recent years
Zero duration swap spreads\*, actual versus fair value\*\*; bp

![](images/246931021c8c418cb425071d88fbd4af670d378d702ed326965ffccbdb181a1a.jpg)
Source: J.P. Morgan.
\* Zero-duration swap spread is defined in the Figure 6 footnote
\*\* Fair value for the zero duration swap spread is calculated as per the model detailed in the previous exhibit.

We now have empirical models for projecting the slope as well as the intercept of the term structure of maturity matched swap spreads versus duration. Having parametrized the shape of the term structure of swap spreads, we can estimate a baseline value for swap spreads of any tenor. But we cannot stop here - as we noted above, swap spreads in any given tenor can deviate from this term structure baseline, due to factors that are idiosyncratic to that sector. Thus, what remains is to find ways to project deviations from this baseline, using sector-specific empirical models for each maturity point. We do this below, by sector.

## Swap spread deviation from the term structure in the 2Y sector

Deviations between 2Y maturity matched swap spreads and the baseline value from the term structure model can be significant as well as persistent over reasonably lengthy periods - as seen in Figure 8, swap spreads in the 2Y sector widened by as much as 10-15 bp relative to the fitted term structure of swap spreads in the first year of this hiking cycle. Thus, it is important to understand the factors that can cause such deviations, and use projected deviations as an additional overlay in arriving at a final estimate of the fair value for 2Y maturity matched swap spreads.

Our model for 2Y swap spread deviations from the fitted term structure is shown in Figure 9. The factors in our model are:

RRP balances, although we have already used RRP balances in modeling the term structure<sup>’</sup>s parameters, front end spreads retain a residual dependence on RRP balances making this factor necessary here

• 2Y UST yield levels, and medium term Fed expectations (which we measure as the 3Mx3M / 15Mx3M forward swap curve)

• T-bill issuance, which we measure as simply the rolling 3M percentage change in the stock of outstanding T-bills

• 1Yx1Y swaption implied volatility, to account for impact that volatility can have on

## leverage, and therefore swap spreads

As can be seen, the dependence on all these factors has the intuitively expected sign where applicable, and the variables have all been significant over the 3Y history used in this fit. Lastly, Figure 10 shows that the residual from the model is fairly tight and mean reverting - this suggests that adding a modeled deviation to the term-structure baseline ought to produce a reasonably good fair value estimate for 2-year swap spreads.

Figure 8: In the first year of this hiking cycle, maturity matched swap spreads in the 2Y sector widened significantly relative to the term structure of swap spreads …
2Y swap spread deviation\* relative to the term structure of swap spreads, Apr 2021 - Apr 2024
![](images/815112b28b1bc845f1fd52e9a4864fb33c667d72cc19ec0a2726e4a31f062024.jpg)
Source: J.P. Morgan.

Figure 9: … making it important to build an empirical model for deviations Statistics from regressing\* 2Y swap spread deviations relative to the term structure of swap spreads\*\* versus its drivers (units as indicated)
<table><tr><td></td><td>Coeff.</td><td>T-Stat</td></tr><tr><td>RRP ($Tn)</td><td>4.1</td><td>19.8</td></tr><tr><td>1Yx1Y imp. Vol (bp/day)</td><td>-0.7</td><td>-7.2</td></tr><tr><td>T-bill stock, 3M pct chg</td><td>-0.3</td><td>-19.6</td></tr><tr><td rowspan="3">2Y UST yield (%) 1st/5th 3M SOFR futures curve, %</td><td>3.2</td><td>16.2</td></tr><tr><td>2.8</td><td>15.6</td></tr><tr><td>-4.2</td><td>-13.5</td></tr><tr><td rowspan="3">Model stats</td><td></td><td></td></tr><tr><td>R-sqr Std. error</td><td>67%</td></tr><tr><td></td><td>2.5</td></tr></table>

\* 2Y swap spread deviation relative to the term structure of swap spreads is calculated for any given day as the actual 2Y maturity matched swap spread minus the fitted value as of that day. The fitted value is calculated from a cross sectional regression of maturity matched swap spreads at benchmark tenors (2s, 3s, 5s, 7s, 10s, 20s, 30s) versus their modified durations, and evaluated at the OTR 2Y note’s modified duration.
Source: J.P. Morgan.
\* Regression period from Apr 2021 - Apr 2024
\*\* 2Y swap spread deviation relative to term structure of swap spreads is calculated for every day in this historical period, using the definition in Figure 8

Figure 10: After accounting for the systematic deviation in 2Y swap spreads from the term structure, the residual is relatively contained and mean reverting

Residual from the regression of 2Y swap spread deviation\* relative to the term structure of swap spreads versus their drivers\*\*, Apr 2021 - Apr 2024

![](images/af1aaca637bd149372aa412d60346f1546888b72afea31939a1c4432431df0f4.jpg)
Source: J.P. Morgan.
\* 2Y swap spread deviation relative to the term structure of swap spreads is defined in Figure 8 \*\* Drivers are detailed in Figure 9

## Swap spread deviation from the term structure in the 5-year sector

Here too, maturity matched swap spreads have deviated from the fitted term structure in systematic ways (Figure 11), making it necessary to model these deviations separately like we did in the 2Y sector . To model these deviations, we use an empirical model estimated over 3 years of history using 2 factors: (i) 2Yx2Y implied volatility (to account for the impact that volatility can have on leverage, and therefore swap spreads) and (ii) near-term Fed expectations (which we measure as 6Mx1M minus 1M OIS yields), which can affect the demand for fixed income assets from various different investor types. Details of the model are shown in Figure 12, and as Figure 13 shows, the residual that remains after accounting for these factors is no longer trending and/or persistent, but much more noiselike.

Figure 11: Maturity matched swap spreads in the 5Y sector have deviated from the fitted term structure in recent years
5Y swap spread deviation\* relative to the term structure of swap spreads, Apr 2021 - Apr 2024
Figure 12: An empirical model for the deviation in 5Y spreads from the fitted term structure
![](images/fddccaa0cfb4785dfa255847b92a75d38740690ff86b365362d85bd7181267fe.jpg)
Statistics from regressing\* 5Y swap spread deviations relative to the term structure of swap spreads\*\* versus its drivers (units as indicated)
Source: J.P. Morgan.

<table><tr><td></td><td>Coeff</td><td>T-stat</td></tr><tr><td>2Yx2Y implied vol (bp/day) 6Mx1M - 1M OIS rate (%) Intercept</td><td>-0.6 -2.6</td><td>-16.9 -32.6</td></tr><tr><td>Model stats</td><td>2.3</td><td>9.5</td></tr><tr><td>R-sqr</td><td>70%</td><td></td></tr><tr><td>Std. error</td><td>1.5</td><td></td></tr></table>

\* 5Y swap spread deviation relative to the term structure of swap spreads is calculated for any given day as the actual 5Y maturity matched swap spread minus the fitted value as of that day. The fitted value is calculated from a cross sectional regression of maturity matched swap spreads at benchmark tenors (2s, 3s, 5s, 7s, 10s, 20s, 30s) versus their modified durations, and evaluated at the OTR 5Y note’s modified duration.
Source: J.P. Morgan.
\* Regression period from Apr 2021 - Apr 2024
\*\* 5Y swap spread deviation relative to term structure of swap spreads is defined in Figure 11
Residual from the regression of 5Y swap spread deviation\* relative to the term structure of swap spreads versus its drivers\*\*, Apr 2021 - Apr 2024

Figure 13: The residual deviation in 5Y spreads that remains after accounting for its drivers is both mean-reverting and smaller in size

![](images/e2e0b2651c85ab4f874d8615a68b03ae2b65f993098ce4ed02a9a225be9da0d2.jpg)
Source: J.P. Morgan.
\*\* Drivers are detailed in Figure 12

## Modeling 10Y maturity matched swap spread deviations from the term structure

In the 10Y sector as well, maturity matched swap spreads have deviated from the fitted term structure by significant amounts and in non-mean-reverting ways (Figure 14). To model these deviations, we use an empirical model estimated over 3 years of history, that is based on 3 factors - (i) monthly duration supply in USTs (measured in 10Y equivalents) to capture any remaining supply-side impacts, (ii) 10Y UST yield levels, to account for directional exposure in spreads, and (iii) the overnight SOFR minus IOER differential (we use a 6 week moving average for smoothing). The last of these factors seeks to capture the inverse relationship between sharp increases in financing costs (perhaps because of rising cost of balance sheet, Reserve scarcity or other related phenomena) and swap spreads. Details of our model are shown in Figure 15, and this model's usefulness is seen in the fact that after accounting for these factors, the residual deviation that remains is both smaller and mean reverting (Figure 16).

Figure 14: Maturity matched swap spreads in the 10Y sector can significantly deviate from the fitted term structure
10Y swap spread deviation\* relative to the term structure of swap spreads, Apr 2021 - Apr 2024
![](images/7e63ed1bfba97f9b39a943ae722309359f49aefc6758dbfea8f451482017ed82.jpg)
Source: J.P. Morgan.

Figure 15: An empirical model for the deviation in 10Y swap spreads from the fitted term structure
<table><tr><td></td><td>Coeff</td><td>T-stat</td></tr><tr><td>Monthly UST supply ($bn 10s) 10Y UST yield, % SOFR minus IOER (6wk movavg.), bp</td><td>-0.036 0.92 -1.0</td><td>-8.7 7.6 -18.0</td></tr><tr><td>Intercept Model stats R-sqrd Std. Error</td><td>-0.5 62% 2.0</td><td>-0.3</td></tr></table>

Statistics from regressing\* 10Y swap spread deviations relative to the term structure of swap spreads\*\* versus its drivers (units as indicated)
\* 10Y swap spread deviation relative to the term structure of swap spreads is calculated for any given day as the actual 10Y maturity matched swap spread minus the fitted value as of that day. The fitted value is calculated from a cross sectional regression of maturity matched swap spreads at benchmark tenors (2s, 3s, 5s, 7s, 10s, 20s, 30s) versus their modified durations, and evaluated at the OTR 10Y note’s modified duration
Source: J.P. Morgan.

Figure 16: The residual deviation in 10Y swap spreads that remains after accounting for systematic factors is both smaller and mean reverting

Residual from the regression of 10Y swap spread deviation\* relative to the term structure of swap spreads versus its drivers\*\*, Apr 2021 - Apr 2024

![](images/bb50230db345edbe7f901129f60d25db2c7696760680a028b641ff566c7b2f65.jpg)
Source: J.P. Morgan.
\*\* Drivers are detailed in Figure 15

## Modeling 30Y maturity matched swap spread deviations from the term structure

As with all the other previously discussed sectors on the spread curve, 30Y maturity matched spreads have also deviated from the fitted term structure. As Figure 17 shows these deviations have consistently been large (to the tune of 5-10bp) and have not been mean-reverting. Our empirical model for modeling these deviations uses 2 factors:

Fed balance sheet size. As the Fed balance sheet grows, this works to increase demand for USTs, thus widening spreads and as expected this factor comes in with a positive coefficient

The aggregate duration of the Variable Annuity universe. While duration needs from the VA hedger community have been muted lately due to the rally in equities over the past year and higher rates, this factor can become very significant at lower yields and at lower equity market prices. It is in part for this reason that we use an expanded history for modeling this sector

Details of the model are shown in Exhibit Figure 18, and Figure 19 shows the residual after we account for these two factors. As can be seen, the residual is much more mean-reverting, and smaller in size. Finally, we note that while we have used 3 years of history to estimate all the other models seen so far, we use a slightly expanded 4-year window for this mode. This is because swap spreads in the 30-year sector can be significantly impacted by receiving flows from variable annuity hedgers, but these demands only pick up significantly when equity valuations are much lower. Therefore, given the strength of equities in recent years, we use an expanded window to capture the effects of this factor over a wider range of equity valuations and yield levels.

Figure 17: Maturity matched swap spreads in the 30Y sector have persistently deviated from the fitted term structure in recent years 30Y swap spread deviation\* relative to the term structure of swap spreads, Apr 2021 - Apr 2024
![](images/4f323f8516c503d3dcefed89fb8ebc1d57f42a1d691e9f470f6f68a1ad7861d5.jpg)
Source: J.P. Morgan.
\* 30Y swap spread deviation relative to the term structure of swap spreads is calculated for any given day as the actual 30Y maturity matched swap spread minus the fitted value as of that day. The fitted value is calculated from a cross sectional regression of maturity matched swap spreads at benchmark tenors (2s, 3s, 5s, 7s, 10s, 20s, 30s) versus their modified durations, and evaluated at the OTR 30Y bond’s modified duration

Figure 18: An empirical model for the deviation in 30Y spreads from the fitted term structure
Statistics from regressing\* 30Y swap spread deviations relative to the term structure of swap spreads\*\* versus its drivers (units as indicated)
<table><tr><td></td><td>Coeff</td><td>T-stat</td></tr><tr><td>Fed balance sheet size ($tn) VA hedging needs ($bn20s)</td><td>2.9 0.0</td><td>35.4 -17.3</td></tr><tr><td rowspan="2">Intercept Model stats R-sqr</td><td>-17.3</td><td>-22.2</td></tr><tr><td>82%</td><td></td></tr><tr><td>Std. error</td><td>1.2</td><td></td></tr></table>

Source: J.P. Morgan.

\* Regression period from Apr 2020 - Apr 2024. Aggregate Variable Annuity duration, in \$bn 20s, is estimated using an approach developed and described in a separate JPMorgan Research Note - Inter est Rate Risk in Variable Annuities, Sep 2011. Available upon request

\*\* 30Y swap spread deviation relative to term structure of swap spreads is defined in Figure 17

Figure 19: The residual deviation in 30Y spreads that remains after accounting for the drivers is both mean-reverting and smaller in size

Residual from the regression of 30Y swap spread deviation\* relative to the term structure of swap spreads versus its drivers\*\*, Apr 2020 - Apr 2024

![](images/e260360b42ed1b79e77ce6bb94483766befa7daab999b8dece88d2e35e3a542d.jpg)
Source: J.P. Morgan.
\* 30Y swap spread deviation relative to the term structure of swap spreads is defined in Figure 17
\*\* Drivers are detailed in Figure 18

## Implications for swap spreads

To recap, we have noted the connection between the slope of the swap spread term structure and Term Funding Premium. We have also observed that the intercept from the same regression (i.e., a cross-sectional regression on any given day of maturity matched swap spreads in different benchmark sectors versus the modified duration of the corresponding bonds) can be interpreted as zero-duration swap spreads. These two quantities are important parametric descriptors of the term structure of swap spreads, and we have developed empirical fair-value models that allow us to take views on both of these.

In practice, swap spreads in any given maturity sector can (and do) deviate from such a term structure in ways that can be large as well as non-mean reverting. Therefore, it is necessary to develop secondary models for the deviation from term structure in each sector, and we have done this for major benchmark sectors (2s, 5s, 10s and 30s).

Armed with all of these empirical models, as well as near term as well as medium term projected/assumed values for all the drivers, we can project the parameters of the term structure of spreads, as well as deviations, to form a view on swap spreads going forward. First, we estimate that term funding premium will modestly rise further in the near term, before retracing to still-elevated but lower levels by year end (Figure 20). It is worth highlighting that even relatively small moves in TFP can mean large impacts on 10- and 30-year swap spreads - the 0.35 decline in TFP that we project over 2H24 translates into \~3bp and \~6bp impacts on swap spreads in those sectors, respectively. We also note that in these projections, we assume that one fourth of the actual-versus-model difference for TFP and zero-duration spreads will converge by 1H24, and these differences will fully converge to zero by year end.

Figure 20: We estimate a modest increase in term funding premium in the near term, before retracement to still-elevated but lower levels by year end

Current, 1st half 2024, and year end 2024 forecasts for Term Funding Premium\* (bp/year), Zero-duration swap spread \*\*(bp), and Term structure baseline swap spreads\*\*\* (bp) in the 2Y, 5Y, 10Y, and 30Y sectors, current as of 4/25/2024
<table><tr><td rowspan="3"></td><td colspan="3">Term Structure Parameter Projections</td></tr><tr><td>Current</td><td>Near term fair value</td><td>Medium term fair value</td></tr><tr><td>4.91</td><td>(1H24) 5.10</td><td>(YE24) 4.74</td></tr><tr><td>Term Funding Premium (bp/year) Zero-duration swap spread (bp)</td><td>-0.74</td><td>2.41</td><td>-0.21</td></tr><tr><td>Term structure baseline swap spread</td><td></td><td></td><td></td></tr><tr><td>2Y</td><td>-10.0</td><td>-7.2</td><td>-9.1</td></tr><tr><td>5Y</td><td>-22.4</td><td>-20.1</td><td>-21.1</td></tr><tr><td>10Y</td><td>-39.5</td><td>-37.9</td><td>-37.7</td></tr><tr><td>30Y</td><td>-79.3</td><td>-79.2</td><td>-76.1</td></tr></table>

Source: J.P. Morgan.
\* Term Funding Premium (TFP) is defined as the negative of the slope of a regression of maturity matched swap spreads versus modified duration in benchmark sectors (2Y, 3Y, 5Y, 7Y, 10Y, 20Y and 30Y) on any given day
\*\* Zero-duration swap spread is defined as the intercept from a regression of maturity matched swap spreads versus modified duration in benchmark sectors (2Y, 3Y, 5Y, 7Y, 10Y, 20Y and 30Y) on any given day
\*\*\* Term structure baseline swap spreads is defined as minus 1 times TFP times the respective sector’s bond’s modified duration plus the zero-duration swap spreads

Second, again using projected values for our drivers in each sector, we can project the deviations between actual swap spreads and the baseline value from the term structure. Current deviations, as well as projected deviations at 1H24 and YE24 horizons are shown in Figure 21. Finally, we can add the deviations projected in Figure 21 to the baseline from the swap spread term structure that is presented in Figure 20, to arrive at our final projections for swap spreads going forward. We show this in Figure 22. As can be seen, these projections argue in favor of a swap spread widening view in the near term across much of the curve, with the impact likely to be more muted at the very long end. Therefore, we maintain our widening bias on swap spreads across much of the curve, except at the long end where we remain neutral.

Figure 21: We look for near term widening in swap spread deviations relative to the term structure across much of the curve by the end of the first half of 2024

Current, 1st half 2024, and year end 2024 forecasts for selected swap spread deviation relative to the term structure of swap spreads\*, current as of 4/25/2024; bp

<table><tr><td rowspan="2"></td><td colspan="3">Deviation from term structure baseline</td></tr><tr><td>Current</td><td>Near term fair value (1H24)</td><td>Medium term fair value (YE24)</td></tr><tr><td>2Y</td><td>2.7</td><td>3.0</td><td>2.4</td></tr><tr><td>5Y</td><td>-1.2</td><td>-0.1</td><td>-0.6</td></tr><tr><td>10Y</td><td>2.2</td><td>3.7</td><td>3.6</td></tr><tr><td>30Y</td><td>3.5</td><td>2.6</td><td>1.4</td></tr></table>

Source: J.P. Morgan.

\* Swap spread deviation relative to the term structure of swap spreads is calculated for any given day as the actual maturity matched swap spread for a particular sector minus the fitted value as of that day. The fitted value is calculated from a cross sectional regression of maturity matched swap spreads at benchmark tenors (2s, 3s, 5s, 7s, 10s, 20s, 30s) versus their modified durations, and evaluated at the selected swap spread sector’s bond’s modified duration

Figure 22: We look for near term widening in swap spreads across much of the curve by the end of the first half of 2024, with the long end being the exception

Current, 1st half 2024, and year end 2024 forecasts\* for selected maturity matched swap spreads, current as of 4/25/2024; bp

<table><tr><td rowspan="2"></td><td colspan="3">Swap spread projections</td></tr><tr><td>Current</td><td>Near term fair value (1H24)</td><td>Medium term fair value (YE24)</td></tr><tr><td>2Y</td><td>-7.3</td><td>-4.2</td><td>-6.7</td></tr><tr><td>5Y</td><td>-23.7</td><td>-20.2</td><td>-21.7</td></tr><tr><td>10Y</td><td>-37.4</td><td>-34.2</td><td>-34.1</td></tr><tr><td>30Y</td><td>-75.9</td><td>-76.7</td><td>-74.7</td></tr></table>

Source: J.P. Morgan.

\*Forecasts are calculated by adding the forecasts for the baseline term structure, as detailed in Figure 20, and forecasts for the deviations from this term structure, as detailed in Figure 21

Srini Ramaswamy <sup>AC</sup> (1-415) 315-8117 srini.ramaswamy@jpmorgan.com J.P. Morgan Securities LLC Ipek Ozil (1-212) 834-2305 ipek.ozil@jpmorgan.com J.P. Morgan Securities LLC

Philip Michaelides (1-212) 834-2096
philip.michaelides@jpmchase.com
J.P. Morgan Securities LLC
Arjun Parikh (1-212) 834-4436
arjun.parikh@jpmchase.com
J.P. Morgan Securities LLC
North America Fixed Income
Strategy
Interest Rate Derivatives
29 April 2024

Analyst Certification: The Research Analyst(s) denoted by an “AC<sup>”</sup> on the cover of this report certifies (or, where multiple Research Analyst are primarily responsible for this report, the Research Analyst denoted by an “AC<sup>”</sup> on the cover or within the document individually certifies, with respect to each security or issuer that the Research Analyst covers in this research) that: (1) all of the views expressed in this report accurately reflect the Research Analyst<sup>’</sup>s personal views about any and all of the subject securities or issuers; and (2) no part of any of the Research Analyst's compensation was, is, or will be directly or indirectly related to the specific recommendations or views expressed by the Research Analyst(s) in this report. For all Korea-based Research Analysts listed on the front cover, if applicable, they also certify, as per KOFIA requirements, that the Research Analyst<sup>’</sup>s analysis was made in good faith and that the views reflect the Research Analyst<sup>’</sup>s own opinion, without undue influence or intervention.

All authors named within this report are Research Analysts who produce independent research unless otherwise specified. In Europe, Sector Specialists (Sales and Trading) may be shown on this report as contacts but are not authors of the report or part of the Research Department.

## Important Disclosures

Company-Specific Disclosures: Important disclosures, including price charts and credit opinion history tables, are available for compendium reports and all J.P. Morgan–covered companies, and certain non-covered companies, by visitinghttps://www.jpmm.com/research/disclosures, calling 1-800-477-0406, or e-mailing research.disclosure.inquiries@jpmorgan.com with your request.

A history of J.P. Morgan investment recommendations disseminated during the preceding 12 months can be accessed on the Research & Commentary page of http://www.jpmorganmarkets.com where you can also search by analyst name, sector or financial instrument.

Analysts' Compensation:The research analysts responsible for the preparation of this report receive compensation based upon various factors, including the quality and accuracy of research, client feedback, competitive factors, and overall firm revenues.

## Other Disclosures

J.P. Morgan is a marketing name for investment banking businesses of JPMorgan Chase & Co. and its subsidiaries and affiliates worldwide.

UK MIFID FICC research unbundling exemption: UK clients should refer to UK MIFID Research Unbundling exemption for details of J.P Morgan<sup>’</sup>s implementation of the FICC research exemption and guidance on relevant FICC research categorisation.

Any long form nomenclature for references to China; Hong Kong; Taiwan; and Macau within this research material are Mainland China; Hong Kong SAR (China); Taiwan (China); and Macau SAR (China).

J.P. Morgan Research may, from time to time, write on issuers or securities targeted by economic or financial sanctions imposed or administered by the governmental authorities of the U.S., EU, UK or other relevant jurisdictions (Sanctioned Securities). Nothing in this report is intended to be read or construed as encouraging, facilitating, promoting or otherwise approving investment or dealing in such Sanctioned Securities. Clients should be aware of their own legal and compliance obligations when making investment decisions.

Any digital or crypto assets discussed in this research report are subject to a rapidly changing regulatory landscape. For relevant regulatory advisories on crypto assets, including bitcoin and ether, please see https://www.jpmorgan.com/disclosures/cryptoasset-disclosure.

The author(s) of this research report may not be licensed to carry on regulated activities in your jurisdiction and, if not licensed, do not hold themselves out as being able to do so.

Exchange-Traded Funds (ETFs): J.P. Morgan Securities LLC (“JPMS<sup>”</sup>) acts as authorized participant for substantially all U.S.-listed ETFs. To the extent that any ETFs are mentioned in this report, JPMS may earn commissions and transaction-based compensation in connection with the distribution of those ETF shares and may earn fees for performing other trade-related services, such as securities lending to short sellers of the ETF shares. JPMS may also perform services for the ETFs themselves, including acting as a broker or dealer to the ETFs. In addition, affiliates of JPMS may perform services for the ETFs, including trust, custodial, administration, lending, index calculation and/or maintenance and other services.

Options and Futures related research: If the information contained herein regards options- or futures-related research, such information is available only to persons who have received the proper options or futures risk disclosure documents. Please contact your J.P. Morgan Representative or visit https://www.theocc.com/components/docs/riskstoc.pdf for a copy of the Option Clearing Corporation's Characteristics and Risks of Standardized Options or http://www.finra.org/sites/default/files/Security\_Futures\_Risk\_Disclosure\_Statement\_2018.pdf for a copy of the Security Futures Risk Disclosure Statement.

Changes to Interbank Offered Rates (IBORs) and other benchmark rates: Certain interest rate benchmarks are, or may in the future become, subject to ongoing international, national and other regulatory guidance, reform and proposals for reform. For more information, please consult: https://www.jpmorgan.com/global/disclosures/interbank\_offered\_rates

Private Bank Clients: Where you are receiving research as a client of the private banking businesses offered by JPMorgan Chase & Co. and its subsidiaries (“J.P. Morgan Private Bank<sup>”</sup>), research is provided to you by J.P. Morgan Private Bank and not by any other division of J.P. Morgan, including, but not limited to, the J.P. Morgan Corporate and Investment Bank and its Global Research division.

Legal entity responsible for the production and distribution of research: The legal entity identified below the name of the Reg AC Research Analyst who authored this material is the legal entity responsible for the production of this research. Where multiple Reg AC Research Analysts authored this material with different legal entities identified below their names, these legal entities are jointly responsible for the production of this research. Research Analysts from various J.P. Morgan affiliates may have contributed to the production of this material but may not be licensed to carry out regulated activities in your jurisdiction (and do not hold themselves out as being able to do so). Unless otherwise stated below, this material has been distributed by the legal entity responsible for production. If you have any queries, please contact the relevant Research Analyst in your jurisdiction or the entity in your jurisdiction that has distributed this research material.

## Legal Entities Disclosures and Country-/Region-Specific Disclosures:

Argentina: JPMorgan Chase Bank N.A Sucursal Buenos Aires is regulated by Banco Central de la República Argentina (“BCRA<sup>”</sup>- Central Bank of Argentina) and Comisión Nacional de Valores (“CNV<sup>”</sup>- Argentinian Securities Commission - ALYC y AN Integral N°51). Australia: J.P. Morgan Securities Australia Limited (“JPMSAL<sup>”</sup>) (ABN 61 003 245 234/AFS Licence No: 238066) is regulated by the Australian Securities and Investments Commission and is a Market Participant of ASX Limited, a Clearing and Settlement Participant of ASX Clear Pty Limited and a Clearing Participant of ASX Clear (Futures) Pty Limited. This material is issued and distributed in Australia by or on behalf of JPMSAL only to "wholesale clients" (as defined in section 761G of the Corporations Act 2001). A list of all financial products covered can be found by visiting https://www.jpmm.com/research/disclosures. J.P. Morgan seeks to cover companies of relevance to the domestic and international investor base across all Global Industry Classification Standard (GICS) sectors, as well as across a range of market capitalisation sizes. If applicable, in the course of conducting public side due diligence on the subject company(ies), the Research Analyst team may at times perform such diligence through corporate engagements such as site visits, discussions with company representatives, management presentations, etc. Research issued by JPMSAL has been prepared in accordance with J.P. Morgan Australia<sup>’</sup>s Research Independence Policy which can be found at the following link: J.P. Morgan Australia - Research Independence Policy. Brazil: Banco J.P. Morgan S.A. is regulated by the Comissao de Valores Mobiliarios (CVM) and by the Central Bank of Brazil. Ombudsman J.P. Morgan: 0800-7700847 / 0800-7700810 (For Hearing Impaired) / ouvidoria.jp.morgan@jpmorgan.com. Canada: J.P. Morgan Securities Canada Inc. is a registered investment dealer, regulated by the Canadian Investment Regulatory Organization and the Ontario Securities Commission and is the participating member on Canadian exchanges. This material is distributed in Canada by or on behalf of J.P.Morgan Securities Canada Inc. Chile: Inversiones J.P. Morgan Limitada is an unregulated entity incorporated in Chile. China: J.P. Morgan Securities (China) Company Limited has been approved by CSRC to conduct the securities investment consultancy business. Dubai International Financial Centre (DIFC): JPMorgan Chase Bank, N.A., Dubai Branch is regulated by the Dubai Financial Services Authority (DFSA) and its registered address is Dubai International Financial Centre - The Gate, West Wing, Level 3 and 9 PO Box 506551, Dubai, UAE. This material has been distributed by JP Morgan Chase Bank, N.A., Duba Branch to persons regarded as professional clients or market counterparties as defined under the DFSA rules. European Economic Area (EEA): Unless specified to the contrary, research is distributed in the EEA by J.P. Morgan SE (“JPM SE<sup>”</sup>), which is authorised as a credit institution by the Federal Financial Supervisory Authority (Bundesanstalt für Finanzdienstleistungsaufsicht, BaFin) and jointly supervised by the BaFin, the German Central Bank (Deutsche Bundesbank) and the European Central Bank (ECB). JPM SE is a company headquartered in Frankfurt with registered address at TaunusTurm, Taunustor 1, Frankfurt am Main, 60310, Germany. The material has been distributed in the EEA to persons regarded as professional investors (or equivalent) pursuant to Art. 4 para. 1 no. 10 and Annex II of MiFID II and its respective implementation in their home jurisdictions (“EEA professional investors<sup>”</sup>). This material must not be acted on or relied on by persons who are not EEA professional investors. Any investment or investment activity to which this material relates is only available to EEA relevant persons and will be engaged in only with EEA relevant persons. Hong Kong: J.P. Morgan Securities (Asia Pacific) Limited (CE number AAJ321) is regulated by the Hong Kong Monetary Authority and the Securities and Futures Commission in Hong Kong, and J.P. Morgan Broking (Hong Kong) Limited (CE number AAB027) is regulated by the Securities and Futures Commission in Hong Kong. JP Morgan Chase Bank, N.A., Hong Kong Branch (CE Number AAL996) is regulated by the Hong Kong Monetary Authority and the Securities and Futures Commission, is organized under the laws of the United States with limited liability. Where the distribution of this material is a regulated activity in Hong Kong, the material is distributed in Hong Kong by or through J.P. Morgan Securities (Asia Pacific) Limited and/or J.P. Morgan Broking (Hong Kong) Limited. India: J.P. Morgan India Private Limited (Corporate Identity Number - U67120MH1992FTC068724), having its registered office at J.P. Morgan Tower, Off. C.S.T. Road, Kalina, Santacruz - East, Mumbai – 400098, is registered with the Securities and Exchange Board of India (SEBI) as a <sup>‘</sup>Research Analyst<sup>’</sup> having registration number INH000001873. J.P. Morgan India Private Limited is also registered with SEBI as a member of the National Stock Exchange of India Limited and the Bombay Stock Exchange Limited (SEBI Registration Number – INZ000239730) and as a Merchant Banker (SEBI Registration Number - MB/INM000002970). Telephone: 91-22-6157 3000, Facsimile: 91-22- 6157 3990 and Website: http://www.jpmipl.com . JPMorgan Chase Bank, N.A. - Mumbai Branch is licensed by the Reserve Bank of India (RBI) (Licence No. 53/ Licence No. BY.4/94; SEBI - IN/CUS/014/ CDSL : IN-DP-CDSL-444-2008/ IN-DP-NSDL-285-2008/ INBI00000984/ INE231311239) as a Scheduled Commercial Bank in India, which is its primary license allowing it to carry on Banking business in India and other activities, which a Bank branch in India are permitted to undertake. For non-local research material, this material is not distributed in India by J.P. Morgan India Private Limited. Compliance Officer: Spurthi Gadamsetty; spurthi.gadamsetty@jpmchase.com; +912261573225 Grievance Officer: Ramprasadh K, jpmipl.research.feedback@jpmorgan.com; +912261573000.

Investment in securities market are subject to market risks. Read all the related documents carefully before investing. Registration granted by SEBI and certification from NISM in no way guarantee performance of the intermediary or provide any assurance of returns to investors.

Indonesia: PT J.P. Morgan Sekuritas Indonesia is a member of the Indonesia Stock Exchange and is registered and supervised by the Otoritas Jasa Keuangan (OJK). Korea: J.P. Morgan Securities (Far East) Limited, Seoul Branch, is a member of the Korea Exchange (KRX). JPMorgan

Srini Ramaswamy <sup>AC</sup> (1-415) 315-8117 srini.ramaswamy@jpmorgan.com J.P. Morgan Securities LLC Ipek Ozil (1-212) 834-2305 ipek.ozil@jpmorgan.com J.P. Morgan Securities LLC

Philip Michaelides (1-212) 834-2096philip.michaelides@jpmchase.comJ.P. Morgan Securities LLCArjun Parikh (1-212) 834-4436arjun.parikh@jpmchase.comJ.P. Morgan Securities LLC

Chase Bank, N.A., Seoul Branch, is licensed as a branch office of foreign bank (JPMorgan Chase Bank, N.A.) in Korea. Both entities are regulated by the Financial Services Commission (FSC) and the Financial Supervisory Service (FSS). For non-macro research material, the material is distributed in Korea by or through J.P. Morgan Securities (Far East) Limited, Seoul Branch. Japan: JPMorgan Securities Japan Co., Ltd. and JPMorgan Chase Bank, N.A., Tokyo Branch are regulated by the Financial Services Agency in Japan. Malaysia: This material is issued and distributed in Malaysia by JPMorgan Securities (Malaysia) Sdn Bhd (18146-X), which is a Participating Organization of Bursa Malaysia Berhad and holds a Capital Markets Services License issued by the Securities Commission in Malaysia. Mexico: J.P. Morgan Casa de Bolsa, S.A. de C.V. and J.P. Morgan Grupo Financiero are members of the Mexican Stock Exchange and are authorized to act as a broker dealer by the National Banking and Securities Exchange Commission. New Zealand: This material is issued and distributed by JPMSAL in New Zealand only to "wholesale clients" (as defined in the Financial Markets Conduct Act 2013). JPMSAL is registered as a Financial Service Provider under the Financial Service providers (Registration and Dispute Resolution) Act of 2008. Philippines: J.P. Morgan Securities Philippines Inc. is a Trading Participant of the Philippine Stock Exchange and a member of the Securities Clearing Corporation of the Philippines and the Securities Investor Protection Fund. It is regulated by the Securities and Exchange Commission. Singapore: This material is issued and distributed in Singapore by or through J.P. Morgan Securities Singapore Private Limited (JPMSS) [MCI (P) 030/08/2023 and Co. Reg. No.: 199405335R], which is a member of the Singapore Exchange Securities Trading Limited, and/or JPMorgan Chase Bank, N.A., Singapore branch (JPMCB Singapore), both of which are regulated by the Monetary Authority of Singapore. This material is issued and distributed in Singapore only to accredited investors, expert investors and institutional investors, as defined in Section 4A of the Securities and Futures Act, Cap. 289 (SFA). This material is not intended to be issued or distributed to any retail investors or any other investors that do not fall into the classes of “accredited investors,<sup>”</sup> “expert investors<sup>”</sup> or “institutional investors,<sup>”</sup> as defined under Section 4A of the SFA. Recipients of this material in Singapore are to contact JPMSS or JPMCB Singapore in respect of any matters arising from, or in connection with, the material. South Africa: J.P. Morgan Equities South Africa Proprietary Limited and JPMorgan Chase Bank, N.A., Johannesburg Branch are members of the Johannesburg Securities Exchange and are regulated by the Financial Services Conduct Authority (FSCA). Taiwan: J.P. Morgan Securities (Taiwan) Limited is a participant of the Taiwan Stock Exchange (company-type) and regulated by the Taiwan Securities and Futures Bureau. Material relating to equity securities is issued and distributed in Taiwan by J.P. Morgan Securities (Taiwan) Limited, subject to the license scope and the applicable laws and the regulations in Taiwan. According to Paragraph 2, Article 7-1 of Operational Regulations Governing Securities Firms Recommending Trades in Securities to Customers (as amended or supplemented) and/or other applicable laws or regulations, please note that the recipient of this material is not permitted to engage in any activities in connection with the material that may give rise to conflicts of interests, unless otherwise disclosed in the “Important Disclosures<sup>”</sup> in this material. Thailand: This material is issued and distributed in Thailand by JPMorgan Securities (Thailand) Ltd., which is a member of the Stock Exchange of Thailand and is regulated by the Ministry of Finance and the Securities and Exchange Commission, and its registered address is 3rd Floor, 20 North Sathorn Road, Silom, Bangrak, Bangkok 10500. UK: Unless specified to the contrary, research is distributed in the UK by J.P. Morgan Securities plc (“JPMS plc<sup>”</sup>) which is a member of the London Stock Exchange and is authorised by the Prudential Regulation Authority and regulated by the Financial Conduct Authority and the Prudential Regulation Authority. JPMS plc is registered in England & Wales No. 2711006, Registered Office 25 Bank Street, London, E14 5JP. This material is directed in the UK only to: (a) persons having professional experience in matters relating to investments falling within article 19(5) of the Financial Services and Markets Act 2000 (Financial Promotion) (Order) 2005 (“the FPO<sup>”</sup>); (b) persons outlined in article 49 of the FPO (high net worth companies, unincorporated associations or partnerships, the trustees of high value trusts, etc.); or (c) any persons to whom this communication may otherwise lawfully be made; all such persons being referred to as "UK relevant persons". This material must not be acted on or relied on by persons who are not UK relevant persons. Any investment or investment activity to which this material relates is only available to UK relevant persons and will be engaged in only with UK relevant persons. Research issued by JPMS plc has been prepared in accordance with JPMS plc's policy for prevention and avoidance of conflicts of interest related to the production of Research which can be found at the following link: J.P. Morgan EMEA - Research Independence Policy. U.S.: J.P. Morgan Securities LLC (“JPMS<sup>”</sup>) is a member of the NYSE, FINRA, SIPC, and the NFA. JPMorgan Chase Bank, N.A. is a member of the FDIC. Material published by non-U.S. affiliates is distributed in the U.S. by JPMS who accepts responsibility for its content.

General: Additional information is available upon request. The information in this material has been obtained from sources believed to be reliable. While all reasonable care has been taken to ensure that the facts stated in this material are accurate and that the forecasts, opinions and expectations contained herein are fair and reasonable, JPMorgan Chase & Co. or its affiliates and/or subsidiaries (collectively J.P. Morgan) make no representations or warranties whatsoever to the completeness or accuracy of the material provided, except with respect to any disclosures relative to J.P. Morgan and the Research Analyst's involvement with the issuer that is the subject of the material. Accordingly, no reliance should be placed on the accuracy, fairness or completeness of the information contained in this material. There may be certain discrepancies with data and/or limited content in this material as a result of calculations, adjustments, translations to different languages, and/or local regulatory restrictions, as applicable. These discrepancies should not impact the overall investment analysis, views and/or recommendations of the subject company(ies) that may be discussed in the material. J.P. Morgan accepts no liability whatsoever for any loss arising from any use of this material or its contents, and neither J.P. Morgan nor any of its respective directors, officers or employees, shall be in any way responsible for the contents hereof, apart from the liabilities and responsibilities that may be imposed on them by the relevant regulatory authority in the jurisdiction in question, or the regulatory regime thereunder. Opinions, forecasts or projections contained in this material represent J.P. Morgan's current opinions or judgment as of the date of the material only and are therefore subject to change without notice. Periodic updates may be provided on companies/industries based on company-specific developments or announcements, market conditions or any other publicly available information. There can be no assurance that future results or events will be consistent with any such opinions, forecasts or projections, which represent only one possible outcome. Furthermore, such opinions, forecasts or projections are subject to certain risks, uncertainties and assumptions that have not been verified, and future actual results or events could differ materially. The value of, or income from, any investments referred to in this material may fluctuate and/or be affected by changes in exchange rates. All pricing is indicative as of the close of market for the securities discussed, unless otherwise stated. Past performance is not indicative of future results. Accordingly, investors may

Srini Ramaswamy <sup>AC</sup> (1-415) 315-8117 srini.ramaswamy@jpmorgan.com J.P. Morgan Securities LLC Ipek Ozil (1-212) 834-2305 ipek.ozil@jpmorgan.com J.P. Morgan Securities LLC

Philip Michaelides (1-212) 834-2096philip.michaelides@jpmchase.comJ.P. Morgan Securities LLCArjun Parikh (1-212) 834-4436arjun.parikh@jpmchase.comJ.P. Morgan Securities LLC

North America Fixed Income Strategy

29 April 2024

receive back less than originally invested. This material is not intended as an offer or solicitation for the purchase or sale of any financial instrument. The opinions and recommendations herein do not take into account individual client circumstances, objectives, or needs and are not intended as recommendations of particular securities, financial instruments or strategies to particular clients. This material may include views on structured securities, options, futures and other derivatives. These are complex instruments, may involve a high degree of risk and may be appropriate investments only for sophisticated investors who are capable of understanding and assuming the risks involved. The recipients of this material must make their own independent decisions regarding any securities or financial instruments mentioned herein and should seek advice from such independent financial, legal, tax or other adviser as they deem necessary. J.P. Morgan may trade as a principal on the basis of the Research Analysts<sup>’</sup> views and research, and it may also engage in transactions for its own account or for its clients<sup>’</sup> accounts in a manner inconsistent with the views taken in this material, and J.P. Morgan is under no obligation to ensure that such other communication is brought to the attention of any recipient of this material. Others within J.P. Morgan, including Strategists, Sales staff and other Research Analysts, may take views that are inconsistent with those taken in this material. Employees of J.P. Morgan not involved in the preparation of this material may have investments in the securities (or derivatives of such securities) mentioned in this material and may trade them in ways different from those discussed in this material. This material is not an advertisement for or marketing of any issuer, its products or services, or its securities in any jurisdiction.

Confidentiality and Security Notice: This transmission may contain information that is privileged, confidential, legally privileged, and/or exempt from disclosure under applicable law. If you are not the intended recipient, you are hereby notified that any disclosure, copying, distribution, or use of the information contained herein (including any reliance thereon) is STRICTLY PROHIBITED. Although this transmission and any attachments are believed to be free of any virus or other defect that might affect any computer system into which it is received and opened, it is the responsibility of the recipient to ensure that it is virus free and no responsibility is accepted by JPMorgan Chase & Co., its subsidiaries and affiliates, as applicable, for any loss or damage arising in any way from its use. If you received this transmission in error, please immediately contact the sender and destroy the material in its entirety, whether in electronic or hard copy format. This message is subject to electronic monitoring: https://www.jpmorgan.com/disclosures/email

MSCI: Certain information herein (“Information<sup>”</sup>) is reproduced by permission of MSCI Inc., its affiliates and information providers (“MSCI<sup>”</sup>) ©2024. No reproduction or dissemination of the Information is permitted without an appropriate license. MSCI MAKES NO EXPRESS OR IMPLIED WARRANTIES (INCLUDING MERCHANTABILITY OR FITNESS) AS TO THE INFORMATION AND DISCLAIMS ALL LIABILITY TO THE EXTENT PERMITTED BY LAW. No Information constitutes investment advice, except for any applicable Information from MSCI ESG Research. Subject also to msci.com/disclaimer

Sustainalytics: Certain information, data, analyses and opinions contained herein are reproduced by permission of Sustainalytics and: (1) includes the proprietary information of Sustainalytics; (2) may not be copied or redistributed except as specifically authorized; (3) do not constitute investment advice nor an endorsement of any product or project; (4) are provided solely for informational purposes; and (5) are not warranted to be complete, accurate or timely. Sustainalytics is not responsible for any trading decisions, damages or other losses related to it or its use. The use of the data is subject to conditions available at https://www.sustainalytics.com/legal-disclaimers . ©2024 Sustainalytics. All Rights Reserved.

"Other Disclosures" last revised April 06, 2024.

Copyright 2024 JPMorgan Chase & Co. All rights reserved. This material or any portion hereof may not be reprinted, sold or redistributed without the written consent of J.P. Morgan. It is strictly prohibited to use or share without prior written consent from J.P. Morgan any research material received from J.P. Morgan or an authorized third-party (“J.P. Morgan Data”) in any third-party artificial intelligence (“AI”) systems or models when such J.P. Morgan Data is accessible by a third-party. It is permissible to use J.P. Morgan Data for internal business purposes only in an AI system or model that protects the confidentiality of J.P. Morgan Data so as to prevent any and all access to or use of such J.P. Morgan Data by any third-party.