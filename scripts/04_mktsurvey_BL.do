clear all
set more off

******************* Baseline Enterprise survey *******************

use "$DATA/Phase 1 enterprise (market) baseline/enterprise_baseline_data_13_03_2026.dta", replace

egen strata_ms = group(s1_market sample_strata), label
gen psu = _n
svyset psu [pweight=weight_adj], strata(strata_ms) singleunit(centered)

svy: mean s1_owner_gender
svy: tab s1_owner_gender

// business practices in the last 30 days
// 60.8% of enterprises visited >=1 competitor to see what prices they are pricing
// 63.6% of enterprises coordinated with other businesses in the market
// 54.5% of enterprises talked to other  businesses about demand for product
// 60.3% of enterprises attracted customers with a special offer or sale
// 68.9% of enterprises compared prices or quality offered by alternative suppleirs
// 29.2% of enterprises kept written business records
// 74.4% of enterprises worked out hte cost to the business of each main product
// 86.7% of enterprises know the product he/she makes the most profits per item sold
// 64.0% of enterprises review financial performance of busines and analyse where there are areas for improvement at least monthly
// 45.8% of enterprises have a target set for sales over the next month
svy: mean s8_bus_practice_price_obs s8_bus_practice_price_coord s8_bus_practice_demand s8_bus_practice_sales s8_bus_practice_suppliers s8_bus_practice_records s8_bus_practice_costs s8_bus_practice_profits s8_bus_practice_performance s8_bus_practice_targets

// some of these questions are from de mel et al, 2014 (JDE)
// adds up to 10 points
gen demel_rough = s8_bus_practice_price_obs + s8_bus_practice_sales + s8_bus_practice_suppliers + s8_bus_practice_records + s8_bus_practice_costs + s8_bus_practice_profits + 3* s8_bus_practice_performance + s8_bus_practice_targets

// mean of the sample: 6.25 points
svy: mean demel_rough

// expected inflation for the main product over the next month
gen inflation_expect_pct = (s9_price_exp_next_month - s9_price_avg_market) / s9_price_avg_market
replace inflation_expect_pct = . if missing(s9_price_exp_next_month) | missing(s9_price_avg_market) | s9_price_avg_market <= 0

// mean expected price increase over the next month is 25.7%
svy: mean inflation_expect_pct

// hypothetical responses to a doubling in the number of competitors
// 37.6% of enterprises would increase their opening hours
// 13.5% of enterprises would reduce their stock of existing products
// 18.4% of enterprises would increase their stock of existing products
// 26.4% of enterprises would source new products of higher quality
// 1.3% of enterprises would source new products of lower quality
// 1.2% of enterprises would hire additional workers
// 17.4% of enterprises would change their average prices
// 26.6% of enterprises would bargain more with individual customers
// 0.7% of enterprises would bargain less with individual customers
svy: mean s9_comp_up_response_1 s9_comp_up_response_2 s9_comp_up_response_3 s9_comp_up_response_4 s9_comp_up_response_5 s9_comp_up_response_6 s9_comp_up_response_7 s9_comp_up_response_8 s9_comp_up_response_9

// hypothetical responses to a halving in the number of competitors
// 38.5% of enterprises would increase their opening hours
// 2.7% of enterprises would reduce their stock of existing products
// 53.0% of enterprises would increase their stock of existing products
// 28.6% of enterprises would source new products of higher quality
// 1.6% of enterprises would source new products of lower quality
// 5.3% of enterprises would hire additional workers
// 12.2% of enterprises would change their average prices
// 14.2% of enterprises would bargain more with individual customers
// 1.6% of enterprises would bargain less with individual customers
svy: mean s9_comp_down_response_1 s9_comp_down_response_2 s9_comp_down_response_3 s9_comp_down_response_4 s9_comp_down_response_5 s9_comp_down_response_6 s9_comp_down_response_7 s9_comp_down_response_8 s9_comp_down_response_9

// hypothetical responses to twice as many customers
// 42.7% of enterprises would increase their opening hours
// 1.3% of enterprises would reduce their stock of existing products
// 57.3% of enterprises would increase their stock of existing products
// 26.8% of enterprises would source new products of higher quality
// 2.4% of enterprises would source new products of lower quality
// 7.6% of enterprises would hire additional workers
// 10.9% of enterprises would change their average prices
// 13.8% of enterprises would bargain more with individual customers
// 1.2% of enterprises would bargain less with individual customers
svy: mean s9_twice_cust_shock_response_1 s9_twice_cust_shock_response_2 s9_twice_cust_shock_response_3 s9_twice_cust_shock_response_4 s9_twice_cust_shock_response_5 s9_twice_cust_shock_response_6 s9_twice_cust_shock_response_7 s9_twice_cust_shock_response_8 s9_twice_cust_shock_response_9

// 24.7% of enterprises would change their price if customers doubled
svy: mean s9_twice_cust_new_price

// 69.5% of enterprises would share this information with other traders if customers doubled
svy: mean s9_twice_cust_share_info

// what enterprises think other traders would do if customers doubled
// 42.5% of enterprises think other traders would increase their opening hours
// 1.5% of enterprises think other traders would reduce their stock of existing products
// 52.0% of enterprises think other traders would increase their stock of existing products
// 24.5% of enterprises think other traders would source new products of higher quality
// 1.9% of enterprises think other traders would source new products of lower quality
// 6.9% of enterprises think other traders would hire additional workers
// 20.3% of enterprises think other traders would change their average prices
// 15.1% of enterprises think other traders would bargain more with individual customers
// 1.8% of enterprises think other traders would bargain less with individual customers
svy: mean s9_twice_cust_other_resp_1 s9_twice_cust_other_resp_2 s9_twice_cust_other_resp_3 s9_twice_cust_other_resp_4 s9_twice_cust_other_resp_5 s9_twice_cust_other_resp_6 s9_twice_cust_other_resp_7 s9_twice_cust_other_resp_8 s9_twice_cust_other_resp_9

// hypothetical responses to half as many customers
// 39.1% of enterprises would increase their opening hours
// 17.7% of enterprises would reduce their stock of existing products
// 24.2% of enterprises would increase their stock of existing products
// 22.5% of enterprises would source new products of higher quality
// 2.4% of enterprises would source new products of lower quality
// 2.2% of enterprises would hire additional workers
// 15.3% of enterprises would change their average prices
// 24.1% of enterprises would bargain more with individual customers
// 1.2% of enterprises would bargain less with individual customers
svy: mean s9_half_cust_shock_response_1 s9_half_cust_shock_response_2 s9_half_cust_shock_response_3 s9_half_cust_shock_response_4 s9_half_cust_shock_response_5 s9_half_cust_shock_response_6 s9_half_cust_shock_response_7 s9_half_cust_shock_response_8 s9_half_cust_shock_response_9

// 21.6% of enterprises would change their price if customers halved
svy: mean s9_half_cust_new_price

// 73.7% of enterprises would share this information with other traders if customers halved
svy: mean s9_half_cust_share_info

// what enterprises think other traders would do if customers halved
// 38.9% of enterprises think other traders would increase their opening hours
// 17.4% of enterprises think other traders would reduce their stock of existing products
// 20.6% of enterprises think other traders would increase their stock of existing products
// 20.9% of enterprises think other traders would source new products of higher quality
// 1.3% of enterprises think other traders would source new products of lower quality
// 2.1% of enterprises think other traders would hire additional workers
// 19.7% of enterprises think other traders would change their average prices
// 18.6% of enterprises think other traders would bargain more with individual customers
// 1.5% of enterprises think other traders would bargain less with individual customers
svy: mean s9_half_cust_other_resp_1 s9_half_cust_other_resp_2 s9_half_cust_other_resp_3 s9_half_cust_other_resp_4 s9_half_cust_other_resp_5 s9_half_cust_other_resp_6 s9_half_cust_other_resp_7 s9_half_cust_other_resp_8 s9_half_cust_other_resp_9

// phq-2: >3 has potential major depression
gen phq_2 = s10_phq_1 + s10_phq_2

// Depression screen: Mild - 5-9; Moderate - 10-14; Severe >14
// 3.18% of enterprises have mild depression
// 3.67% of enterprise owners have moderate depression
// 3.04% of enterprise owners have severe depression
gen depression_mild = (s10_phq8_score>=5 & s10_phq8_score<=9)
replace depression_mild = . if missing(phq_2)
gen depression_moderate = (s10_phq8_score>=10 & s10_phq8_score<=14)
replace depression_moderate = . if missing(phq_2)
gen depression_severe = (s10_phq8_score>14 & !missing(s10_phq8_score))
replace depression_severe = . if missing(phq_2)

svy: mean depression_*
