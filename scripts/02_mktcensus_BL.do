clear all
set more off

// cd "/Users/kstang/work/github/steg_call"

******************* Baseline Market Census Phase 1,2 *******************
	  
use "$DATA/ENT_MKT_BL_Census_Phase_1&2/entcensus_data.dta", replace	  

// 51.58% of the enterprises are food vendors
sum s1_primary_sec_cat__1 

// mostly this is raw food stalls/processed food stalls, followed by processed food stalls. A lot less selling/brewing alcohol
forvalues i=1/7{
	tab s1_primary_ent_cat__`i'
}

// 1.54% of the enterprises are agriculture/livestock
sum s1_primary_sec_cat__2 

// mostly this is agricultural/vet supplies
forvalues i=8/9{
	tab s1_primary_ent_cat__`i'
}

// unlike household census, livestock vendors are here now
forvalues i=10/12{
	tab s1_primary_ent_cat__`i'
}

// 17.90% of the enterprises are non-food vendors
sum s1_primary_sec_cat__3 

// clothing sellers, household items and supplies, hardware stores
forvalues i=13/22{
	tab s1_primary_ent_cat__`i'
}

forvalues i=39/41{
	tab s1_primary_ent_cat__`i'
}

// 6.24% of the enterprises are manufacturing
sum s1_primary_sec_cat__4 

// mostly this is tailors
forvalues i=23/27{
	tab s1_primary_ent_cat__`i'
}

// there are 70 maize mills at markets
tab s1_primary_ent_cat__42


// 25.93% of the enterprises are services 
sum s1_primary_sec_cat__5 

// restaurant, barber, mobile charging, photo studio, video room
forvalues i=28/38{
	tab s1_primary_ent_cat__`i'
}

tab s1_primary_ent_cat__43

// 93.57% of enterprises are owned by single owner. Only 6.31% joint ownership, which includes owner and spouse having claim to enterprise's assets.
tab s1_ownership

// 94.7% of enterprises sell at the current market every week on market day(s)
tab s2_market_day_often	

// 88.25% of enterprises operated in this market in the past 30 days.
// 22.38% of enterprises operated in another market place in Chiradzulu
// 10.69% of enterprises worked in another location..
sum s3_op_location__0 s3_op_location__1 s3_op_location__2 s3_op_location__3 s3_op_location__4 s3_op_location__5

// some ppl work in Limbe... mulanje and zomba districts
br s3_op_loc_oth if s3_op_location__5 == 1 

// # of months opened in the past 12 months
egen months_open_total = rowtotal(s3_months_open__1 s3_months_open__2 s3_months_open__3 s3_months_open__4 s3_months_open__5 s3_months_open__6 s3_months_open__7 s3_months_open__8 s3_months_open__9 s3_months_open__10 s3_months_open__11 s3_months_open__12) if s3_months_open != ""
replace months_open_total = 12 if s3_months_open__13 == 1

// hungry season dummy 
egen hungry_months_open_total = rowtotal(s3_months_open__1 s3_months_open__2 s3_months_open__3 s3_months_open__10 s3_months_open__11 s3_months_open__12) if s3_months_open != ""
replace hungry_months_open_total = 6 if s3_months_open__13 == 1

// average enterprise opens for 9.62 months in the past 12 months
sum months_open_total

// does this depend on sector? minute differences
sum months_open_total if s1_primary_sec_cat__1 == 1 
sum months_open_total if s1_primary_sec_cat__2 == 1
sum months_open_total if s1_primary_sec_cat__3 == 1
sum months_open_total if s1_primary_sec_cat__4 == 1
sum months_open_total if s1_primary_sec_cat__5 == 1

// seasonal sellers open on average 6.35 months in the past 12 months - seems quite seasonal
sum months_open_total if months_open_total < 12

// does this depend on sector? not really
sum months_open_total if s1_primary_sec_cat__1 == 1 & months_open_total < 12
sum months_open_total if s1_primary_sec_cat__2 == 1 & months_open_total < 12
sum months_open_total if s1_primary_sec_cat__3 == 1 & months_open_total < 12
sum months_open_total if s1_primary_sec_cat__4 == 1 & months_open_total < 12
sum months_open_total if s1_primary_sec_cat__5 == 1 & months_open_total < 12

// average seasonal enterprise opens for 2.92 months during hungry season (6 months long)
sum hungry_months_open_total if months_open_total < 12

// does this depend on sector? seems not
sum hungry_months_open_total if s1_primary_sec_cat__1 == 1
sum hungry_months_open_total if s1_primary_sec_cat__2 == 1
sum hungry_months_open_total if s1_primary_sec_cat__3 == 1
sum hungry_months_open_total if s1_primary_sec_cat__4 == 1
sum hungry_months_open_total if s1_primary_sec_cat__5 == 1

// # of employees

// 87.43% of enterprises had 0 paid employees in the last 30 days. 8.47% had 1 paid employee
tab s2_paid_employees_30days

// 71.52% of enterprises had 0 unpaid workers and volunteers currently working
tab s2_unpaid_workers

gen workers_total_30days = s2_paid_employees_30days + s2_unpaid_workers

// 61.81% of enterprises had 0 workers, 23.49% of enterprises had 1 worker
tab workers_total_30days

// stock/inventory or materials/supplies

// 68.32% of enterprises has ever owned any stock/inventory or materials/supplies in the last 30 days
tab s2_has_inventory

// 92.15% of enterprises with stock/inventory/materials/supplies in the last 30 days knows the inventory amount
tab s2_inventory_amount_y

_pctile s2_inventory_value_today, p(99)
local p99 = r(r1)
display "99th percentile of current stock/inventory/material/supplies: `p99'"
hist s2_inventory_value_today if s2_inventory_value_today <= `p99', ///
    percent scheme(lean2) title("Current stock/inventory/material/supplies") note("Sample restricted to enterprises who have owned stock/inventory/material/supplies in the past 30 days." "Truncated at 99th percentile: `p99' MWK.")

// 78.38% of enterprises with stock/inventory/materials/supplies in the last 30 days has purchased stock/inventory/materials/supplies in the past 30 days
tab s2_inventory_value_y

_pctile s2_inventory_exp_30days, p(99)
local p99 = r(r1)
display "99th percentile of purchases in stock/inventory/material/supplies in the past 30 days: `p99'"
hist s2_inventory_exp_30days ///
    if s2_inventory_exp_30days <= `p99', ///
    percent scheme(lean2) ///
    title("Purchases in stock/inventory/material/supplies in the past 30 days", size(medium)) ///
	note("Sample restricted to enterprises who have owned stock/inventory/material/supplies in the past 30 days." "Truncated at 99th percentile (`p99' MWK).")
	
// revenue measures

_pctile s2_revenue_7day, p(99)
local p99 = r(r1)
display "99th percentile of revenues over the past 7 days: `p99'"
hist s2_revenue_7day ///
    if s2_revenue_7day <= `p99', ///
    percent scheme(lean2) ///
    title("Revenues over the past 7 days", size(medium)) ///
	note("Truncated at 99th percentile (`p99' MWK).")
	
_pctile s2_revenue_1m, p(99)
local p99 = r(r1)
display "99th percentile of revenues over the past 30 days: `p99'"
hist s2_revenue_1m ///
    if s2_revenue_1m <= `p99', ///
    percent scheme(lean2) ///
    title("Revenues over the past 30 days", size(medium)) ///
	note("Truncated at 99th percentile (`p99' MWK).")

// profit measures

_pctile s2_profit_7day, p(1 99)

local p1  = r(r1)
local p99 = r(r2)

display "1st percentile of profits over the past 7 days: `p1'"
display "99th percentile of profits over the past 7 days: `p99'"

hist s2_profit_7day ///
    if inrange(s2_profit_7day, `p1', `p99'), ///
    percent scheme(lean2) ///
    title("Profits over the past 7 days", size(medium)) ///
    note("Truncated at 1st percentile (`p1' MWK) and 99th percentile (`p99' MWK).")
	
_pctile s2_profit_1m, p(1 99)

local p1  = r(r1)
local p99 = r(r2)

display "1st percentile of profits over the past 30 days: `p1'"
display "99th percentile of profits over the past 30 days: `p99'"

hist s2_profit_1m ///
    if inrange(s2_profit_1m, `p1', `p99'), ///
    percent scheme(lean2) ///
    title("Profits over the past 30 days", size(medium)) ///
    note("Truncated at 1st percentile (`p1' MWK) and 99th percentile (`p99' MWK).")

// slack measures

// slack measure was done on opened businesses only - which was like half of the firms
tab survey_business_open

forvalues i=2/17 {
	local slack_`i': variable label obs_slack_actions_1__`i'
	egen slack_3mins_`i' = rowtotal(obs_slack_actions_1__`i' obs_slack_actions_2__`i' obs_slack_actions_3__`i') if !missing(obs_slack_actions_1__2) & !missing(obs_slack_actions_2__2) & !missing(obs_slack_actions_3__2)
	replace slack_3mins_`i' = . if slack_3mins_`i' < 0
	label variable slack_3mins_`i' "`slack_`i''"
	gen slack_3mins_yn_`i' = (slack_3mins_`i'>0)
	replace slack_3mins_yn_`i' = . if slack_3mins_`i' < 0
	replace slack_3mins_yn_`i' = . if slack_3mins_`i' == .
	label variable slack_3mins_yn_`i' "`slack_`i''"
}		 

sum slack_3mins_yn_*

// for firms that we can observe 3 minutes
// 64.9% of firms waited for customers (16)
// 36.2% of firms interacted with consumers (5)
// 18.4% of firms ate (4) - probably an artifact of the time of survey
sum slack_3mins_yn_*

// similar among those who open year round and those who don't 
sum slack_3mins_yn_* if months_open_total < 12
sum slack_3mins_yn_* if months_open_total == 12

// 72.3% of firms waited for customers, 33.4% interacted with consumers for food vendors
sum slack_3mins_yn_* if s1_primary_sec_cat__1 == 1
// 37.8% of firms waited for customers, 37.8% interacted with consumers for agriculture/livestock
sum slack_3mins_yn_* if s1_primary_sec_cat__2 == 1
// 70.8% of firms waited for customers, 35.9% interacted with consumers for non-food vendors
sum slack_3mins_yn_* if s1_primary_sec_cat__3 == 1
// 43.5% of firms waited for customers, 35.1% interacted with consumers for manufacturing
sum slack_3mins_yn_* if s1_primary_sec_cat__4 == 1
// 55.2% of firms waited for customers, 43.1% interacted with consumers for services
sum slack_3mins_yn_* if s1_primary_sec_cat__5 == 1


forvalues i=2/17 {
	local slack_`i': variable label obs_slack_actions_1__`i'
	egen slack_anymins_`i' = rowmax(obs_slack_actions_1__`i' obs_slack_actions_2__`i' obs_slack_actions_3__`i')
	label variable slack_anymins_`i' "`slack_`i''"
}

sum slack_anymins_*

// for firms that we can see any minute 
// 64.3% of firms waited for customers, 33.4% interacted with consumers for services
sum slack_anymins_*

// 56.5% of firms waited for customers, 40.1% interacted with consumers for food vendors
sum slack_anymins_* if s1_primary_sec_cat__1 == 1
// 56.5% of firms waited for customers, 40.1% interacted with consumers for agriculture/livestock
sum slack_anymins_* if s1_primary_sec_cat__2 == 1
// 56.5% of firms waited for customers, 40.1% interacted with consumers for non-food vendors
sum slack_anymins_* if s1_primary_sec_cat__3 == 1
// 56.5% of firms waited for customers, 40.1% interacted with consumers for manufacturing
sum slack_anymins_* if s1_primary_sec_cat__4 == 1
// 56.5% of firms waited for customers, 40.1% interacted with consumers for services
sum slack_anymins_* if s1_primary_sec_cat__5 == 1

