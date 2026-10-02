clear all
set more off
version 17.0

********************************************************************
* Summary statistics by reclassified enterprise type
********************************************************************

if "$PROJ" == "" {
    local this_do "`c(filename)'"
    if "`this_do'" == "" {
        local this_do "/Users/kstang/work/github/steg_call/scripts/07_enterprise_type_summary.do"
    }
    global PROJ = substr("`this_do'", 1, strrpos("`this_do'", "/scripts/") - 1)
    global DATA    "$PROJ/data"
    global PROC    "$PROJ/proc"
    global RESULTS "$PROJ/results"
    global TABLES  "$PROJ/tables"
    global LOGS    "$PROJ/logs"
    global SCRIPTS "$PROJ/scripts"
}

capture program drop require_vars
program define require_vars
    syntax varlist
    foreach v of varlist `varlist' {
        capture confirm variable `v'
        if _rc {
            di as error "Required variable missing: `v'"
            exit 111
        }
    }
end

capture program drop yesno_to_byte
program define yesno_to_byte
    syntax newvarname =/exp

    local newvar `varlist'
    local src `exp'

    capture confirm string variable `src'
    if !_rc {
        gen byte `newvar' = .
        replace `newvar' = 1 if inlist(lower(strtrim(`src')), "yes", "y", "1", "true")
        replace `newvar' = 0 if inlist(lower(strtrim(`src')), "no", "n", "0", "false")
        exit
    }

    capture confirm numeric variable `src'
    if _rc {
        di as error "Variable `src' is neither string nor numeric."
        exit 198
    }

    gen double `newvar' = `src'

    tempvar decoded
    local vallab : value label `src'
    if "`vallab'" != "" {
        capture decode `src', gen(`decoded')
        if !_rc {
            replace `newvar' = 1 if inlist(lower(strtrim(`decoded')), "yes", "y", "1", "true")
            replace `newvar' = 0 if inlist(lower(strtrim(`decoded')), "no", "n", "0", "false")
        }
    }

    replace `newvar' = . if !inlist(`newvar', 0, 1) & !missing(`newvar')
    recast byte `newvar'
end

capture program drop append_stat
program define append_stat
    syntax, VARname(name) CODE(string)

    use "$SUM_MERGED_BASE", clear
    local statlab : variable label `varname'
    if `"`statlab'"' == "" {
        local statlab "`code'"
    }

    keep $SUM_GROUPVARS survey_weight_anchor `varname'
    keep if !missing(`varname')

    if _N == 0 {
        use "$SUM_CATEGORY_MASTER", clear
        gen long raw_n = 0
        gen double weighted_n = 0
        gen double mean = .
        gen double sd = .
        gen str64 statistic_code = "`code'"
        gen str120 statistic_label = `"`statlab'"'

        capture confirm file "$SUM_ALL_STATS"
        if _rc {
            save "$SUM_ALL_STATS", replace
        }
        else {
            append using "$SUM_ALL_STATS"
            save "$SUM_ALL_STATS", replace
        }
        exit
    }

    collapse (count) raw_n=`varname' ///
        (sum) weighted_n=survey_weight_anchor ///
        (mean) mean=`varname' ///
        (sd) sd=`varname' [aw=survey_weight_anchor], by($SUM_GROUPVARS)

    tempfile stat_result
    save `stat_result'

    use "$SUM_CATEGORY_MASTER", clear
    merge 1:1 $SUM_GROUPVARS using `stat_result', nogen
    replace raw_n = 0 if missing(raw_n)
    replace weighted_n = 0 if missing(weighted_n)

    gen str64 statistic_code = "`code'"
    gen str120 statistic_label = `"`statlab'"'

    capture confirm file "$SUM_ALL_STATS"
    if _rc {
        save "$SUM_ALL_STATS", replace
    }
    else {
        append using "$SUM_ALL_STATS"
        save "$SUM_ALL_STATS", replace
    }
end

local CLASS_INPUT  "$PROC/enterprise_product_sector_BL.dta"
local OUTPUT_DTA   "$PROC/enterprise_type_summary_BL.dta"
local OUTPUT_CSV   "$TABLES/enterprise_type_summary_BL.csv"

capture confirm file "`CLASS_INPUT'"
if _rc {
    di as error "Input file not found: `CLASS_INPUT'"
    exit 601
}

capture mkdir "$PROC"
capture mkdir "$TABLES"

********************************************************************
* 1. Build a firm-level baseline slice from the processed enterprise file
********************************************************************

use "`CLASS_INPUT'", clear
keep if survey_source == "baseline_survey"

require_vars survey_key survey_entid survey_date survey_weight_anchor ///
    enterprise_category_id enterprise_category_key enterprise_category_label ///
    category_assignment_tier anchor_index ///
    s2_open_month ///
    s2_months_open s2_months_open__13 ///
    s2_months_open__1 s2_months_open__2 s2_months_open__3 s2_months_open__4 ///
    s2_months_open__5 s2_months_open__6 s2_months_open__7 s2_months_open__8 ///
    s2_months_open__9 s2_months_open__10 s2_months_open__11 s2_months_open__12 ///
    s2_op_loc_oth_loc s2_revenue_7day s2_revenue_1m s2_profit_7day s2_profit_1m ///
    s2_current_biz_opr_cap s2_earning_best s2_earning_worst s2_mob_money ///
    s2_customers_7d s2_final_customers_prop s2_oth_ent_prop ///
    s2_paid_employees_30days s3_volunteer_num ///
    s4_stock_value s4_stock_spend_30d s4_matsupp_value s4_matsupp_spend_30d ///
    s5_invest_30d s5_invest_12m ///
    land_own_ind land_rent_ind land_own_monthly land_rent_monthly ///
    building_own_ind building_rent_ind build_own_monthly build_rent_monthly ///
    furniture_own_ind furniture_rent_ind furniture_value_mwk furniture_rent_mwk ///
    vehicle_own_ind vehicle_rent_ind vehicle_count vehicle_value_mwk vehicle_rent_mwk ///
    machine_own_ind machine_rent_ind machine_count machine_value_mwk machine_rent_mwk ///
    s8_bus_practice_price_obs s8_bus_practice_price_coord s8_bus_practice_demand ///
    s8_bus_practice_sales s8_bus_practice_suppliers s8_bus_practice_records ///
    s8_bus_practice_costs s8_bus_practice_profits s8_bus_practice_performance ///
    s8_bus_practice_targets ///
    s7_newprod_any s7_dropprod_any ///
    demel_rough inflation_expect_pct ///
    s9_comp_up_response_1 s9_comp_up_response_2 s9_comp_up_response_3 ///
    s9_comp_up_response_4 s9_comp_up_response_5 s9_comp_up_response_6 ///
    s9_comp_up_response_7 s9_comp_up_response_8 s9_comp_up_response_9 ///
    s9_comp_down_response_1 s9_comp_down_response_2 s9_comp_down_response_3 ///
    s9_comp_down_response_4 s9_comp_down_response_5 s9_comp_down_response_6 ///
    s9_comp_down_response_7 s9_comp_down_response_8 s9_comp_down_response_9 ///
    s9_twice_cust_shock_response_1 s9_twice_cust_shock_response_2 ///
    s9_twice_cust_shock_response_3 s9_twice_cust_shock_response_4 ///
    s9_twice_cust_shock_response_5 s9_twice_cust_shock_response_6 ///
    s9_twice_cust_shock_response_7 s9_twice_cust_shock_response_8 ///
    s9_twice_cust_shock_response_9 s9_twice_cust_new_price s9_twice_cust_share_info ///
    s9_twice_cust_other_resp_1 s9_twice_cust_other_resp_2 s9_twice_cust_other_resp_3 ///
    s9_twice_cust_other_resp_4 s9_twice_cust_other_resp_5 s9_twice_cust_other_resp_6 ///
    s9_twice_cust_other_resp_7 s9_twice_cust_other_resp_8 s9_twice_cust_other_resp_9 ///
    s9_half_cust_shock_response_1 s9_half_cust_shock_response_2 ///
    s9_half_cust_shock_response_3 s9_half_cust_shock_response_4 ///
    s9_half_cust_shock_response_5 s9_half_cust_shock_response_6 ///
    s9_half_cust_shock_response_7 s9_half_cust_shock_response_8 ///
    s9_half_cust_shock_response_9 s9_half_cust_new_price s9_half_cust_share_info ///
    s9_half_cust_other_resp_1 s9_half_cust_other_resp_2 s9_half_cust_other_resp_3 ///
    s9_half_cust_other_resp_4 s9_half_cust_other_resp_5 s9_half_cust_other_resp_6 ///
    s9_half_cust_other_resp_7 s9_half_cust_other_resp_8 s9_half_cust_other_resp_9

isid survey_key anchor_index

* Standardize binary yes/no fields before constructing summary outcomes.
yesno_to_byte mob_money_accepts = s2_mob_money
yesno_to_byte new_product_30d = s7_newprod_any
yesno_to_byte dropped_product_30d = s7_dropprod_any

forvalues m = 1/12 {
    yesno_to_byte month_open_`m' = s2_months_open__`m'
}
yesno_to_byte month_open_all = s2_months_open__13

* Build seasonality and asset summary measures once at the firm level.
gen double months_worked_12m = .
replace months_worked_12m = 12 if month_open_all == 1
replace months_worked_12m = 0 if missing(months_worked_12m)
forvalues m = 1/12 {
    replace months_worked_12m = months_worked_12m + month_open_`m' if !missing(month_open_`m')
}
replace months_worked_12m = . if trim(s2_months_open) == "" & missing(s2_months_open__13)
replace months_worked_12m = 12 if months_worked_12m > 12 & !missing(months_worked_12m)

gen byte started_over_12m = .
replace started_over_12m = (s2_open_month < dofm(mofd(survey_date) - 12)) ///
    if !missing(s2_open_month) & !missing(survey_date)

gen double seasonality_months_worked = months_worked_12m if started_over_12m == 1
label variable seasonality_months_worked "Months worked in past 12 months (>12 months since start)"

gen double any_worker_ex_owner = .
replace any_worker_ex_owner = 0 if !missing(s2_paid_employees_30days) | !missing(s3_volunteer_num)
replace any_worker_ex_owner = any_worker_ex_owner + s2_paid_employees_30days if !missing(s2_paid_employees_30days)
replace any_worker_ex_owner = any_worker_ex_owner + s3_volunteer_num if !missing(s3_volunteer_num)
label variable any_worker_ex_owner "Any worker excluding owner"

gen double land_monthly_value = .
replace land_monthly_value = 0 if !missing(land_own_monthly) | !missing(land_rent_monthly)
replace land_monthly_value = land_monthly_value + land_own_monthly if !missing(land_own_monthly)
replace land_monthly_value = land_monthly_value + land_rent_monthly if !missing(land_rent_monthly)
label variable land_monthly_value "Monthly-equivalent land rental value (MWK)"

gen double building_monthly_value = .
replace building_monthly_value = 0 if !missing(build_own_monthly) | !missing(build_rent_monthly)
replace building_monthly_value = building_monthly_value + build_own_monthly if !missing(build_own_monthly)
replace building_monthly_value = building_monthly_value + build_rent_monthly if !missing(build_rent_monthly)
label variable building_monthly_value "Monthly-equivalent building rental value (MWK)"

label variable mob_money_accepts "Accepts mobile money"
label variable new_product_30d "Introduced new product in last 30 days"
label variable dropped_product_30d "Dropped/discontinued product in last 30 days"

tempfile merged_base category_master all_stats
local groupvars enterprise_category_id enterprise_category_key ///
    enterprise_category_label category_assignment_tier
global SUM_GROUPVARS `groupvars'

save `merged_base'
global SUM_MERGED_BASE `merged_base'

preserve
    keep enterprise_category_id enterprise_category_key enterprise_category_label ///
        category_assignment_tier
    duplicates drop
    bysort `groupvars': assert _N == 1
    save `category_master'
    global SUM_CATEGORY_MASTER `category_master'
restore

capture erase `all_stats'
global SUM_ALL_STATS `all_stats'

********************************************************************
* 3. Loop over requested statistics and save a long summary table
********************************************************************
append_stat, varname(seasonality_months_worked) code(seasonality_months_worked)
append_stat, varname(s2_op_loc_oth_loc) code(also_other_location)
append_stat, varname(s2_revenue_7day) code(revenue_7d)
append_stat, varname(s2_revenue_1m) code(revenue_30d)
append_stat, varname(s2_profit_7day) code(profit_7d)
append_stat, varname(s2_profit_1m) code(profit_30d)
append_stat, varname(s2_current_biz_opr_cap) code(capacity_utilization)
append_stat, varname(s2_earning_best) code(best_week_revenue)
append_stat, varname(s2_earning_worst) code(worst_week_revenue)
append_stat, varname(mob_money_accepts) code(accepts_mobile_money)
append_stat, varname(s2_customers_7d) code(customers_7d)
append_stat, varname(s2_final_customers_prop) code(final_consumer_share)
append_stat, varname(s2_oth_ent_prop) code(other_enterprise_share)
append_stat, varname(s2_paid_employees_30days) code(paid_employees)
append_stat, varname(any_worker_ex_owner) code(any_worker_ex_owner)
append_stat, varname(s4_stock_value) code(inventory_current)
append_stat, varname(s4_stock_spend_30d) code(inventory_purchases_30d)
append_stat, varname(s4_matsupp_value) code(materials_current)
append_stat, varname(s4_matsupp_spend_30d) code(materials_purchases_30d)
append_stat, varname(s5_invest_30d) code(investment_30d)
append_stat, varname(s5_invest_12m) code(investment_12m)
append_stat, varname(land_own_ind) code(owns_land)
append_stat, varname(land_rent_ind) code(rents_land)
append_stat, varname(land_monthly_value) code(land_monthly_rental_value)
append_stat, varname(building_own_ind) code(owns_building)
append_stat, varname(building_rent_ind) code(rents_building)
append_stat, varname(building_monthly_value) code(building_monthly_rental_value)
append_stat, varname(furniture_own_ind) code(owns_furniture)
append_stat, varname(furniture_rent_ind) code(rents_furniture)
append_stat, varname(furniture_value_mwk) code(furniture_value_owned)
append_stat, varname(furniture_rent_mwk) code(furniture_rent_30d)
append_stat, varname(vehicle_own_ind) code(owns_vehicle)
append_stat, varname(vehicle_rent_ind) code(rents_vehicle)
append_stat, varname(vehicle_count) code(vehicle_count)
append_stat, varname(vehicle_value_mwk) code(vehicle_value_owned)
append_stat, varname(vehicle_rent_mwk) code(vehicle_rent_30d)
append_stat, varname(machine_own_ind) code(owns_machine)
append_stat, varname(machine_rent_ind) code(rents_machine)
append_stat, varname(machine_count) code(machine_count)
append_stat, varname(machine_value_mwk) code(machine_value_owned)
append_stat, varname(machine_rent_mwk) code(machine_rent_30d)
append_stat, varname(s8_bus_practice_price_obs) code(practice_price_obs)
append_stat, varname(s8_bus_practice_price_coord) code(practice_price_coord)
append_stat, varname(s8_bus_practice_demand) code(practice_demand)
append_stat, varname(s8_bus_practice_sales) code(practice_sales)
append_stat, varname(s8_bus_practice_suppliers) code(practice_suppliers)
append_stat, varname(s8_bus_practice_records) code(practice_records)
append_stat, varname(s8_bus_practice_costs) code(practice_costs)
append_stat, varname(s8_bus_practice_profits) code(practice_profits)
append_stat, varname(s8_bus_practice_performance) code(practice_performance)
append_stat, varname(s8_bus_practice_targets) code(practice_targets)
append_stat, varname(new_product_30d) code(new_product_30d)
append_stat, varname(dropped_product_30d) code(dropped_product_30d)
append_stat, varname(demel_rough) code(demel_rough)
append_stat, varname(inflation_expect_pct) code(inflation_expect_pct)

local response_codes increase_opening_hours reduce_stock_existing_products ///
    increase_stock_existing_products source_higher_quality_products ///
    source_lower_quality_products hire_additional_workers ///
    change_average_prices bargain_more_individual_customers ///
    bargain_less_individual_customers

forvalues i = 1/9 {
    local response_code : word `i' of `response_codes'
    append_stat, varname(s9_comp_up_response_`i') code(comp_up_`response_code')
}

forvalues i = 1/9 {
    local response_code : word `i' of `response_codes'
    append_stat, varname(s9_comp_down_response_`i') code(comp_down_`response_code')
}

forvalues i = 1/9 {
    local response_code : word `i' of `response_codes'
    append_stat, varname(s9_twice_cust_shock_response_`i') code(twice_cust_`response_code')
}
append_stat, varname(s9_twice_cust_new_price) code(twice_cust_new_price)
append_stat, varname(s9_twice_cust_share_info) code(twice_cust_share_info)
forvalues i = 1/9 {
    local response_code : word `i' of `response_codes'
    append_stat, varname(s9_twice_cust_other_resp_`i') code(twice_cust_others_`response_code')
}

forvalues i = 1/9 {
    local response_code : word `i' of `response_codes'
    append_stat, varname(s9_half_cust_shock_response_`i') code(half_cust_`response_code')
}
append_stat, varname(s9_half_cust_new_price) code(half_cust_new_price)
append_stat, varname(s9_half_cust_share_info) code(half_cust_share_info)
forvalues i = 1/9 {
    local response_code : word `i' of `response_codes'
    append_stat, varname(s9_half_cust_other_resp_`i') code(half_cust_others_`response_code')
}

use "$SUM_ALL_STATS", clear
gen int statistic_order = .
replace statistic_order = 1 if statistic_code == "seasonality_months_worked"
replace statistic_order = 2 if statistic_code == "also_other_location"
replace statistic_order = 3 if statistic_code == "revenue_7d"
replace statistic_order = 4 if statistic_code == "revenue_30d"
replace statistic_order = 5 if statistic_code == "profit_7d"
replace statistic_order = 6 if statistic_code == "profit_30d"
replace statistic_order = 7 if statistic_code == "capacity_utilization"
replace statistic_order = 8 if statistic_code == "best_week_revenue"
replace statistic_order = 9 if statistic_code == "worst_week_revenue"
replace statistic_order = 10 if statistic_code == "accepts_mobile_money"
replace statistic_order = 11 if statistic_code == "customers_7d"
replace statistic_order = 12 if statistic_code == "final_consumer_share"
replace statistic_order = 13 if statistic_code == "other_enterprise_share"
replace statistic_order = 14 if statistic_code == "paid_employees"
replace statistic_order = 15 if statistic_code == "any_worker_ex_owner"
replace statistic_order = 16 if statistic_code == "inventory_current"
replace statistic_order = 17 if statistic_code == "inventory_purchases_30d"
replace statistic_order = 18 if statistic_code == "materials_current"
replace statistic_order = 19 if statistic_code == "materials_purchases_30d"
replace statistic_order = 20 if statistic_code == "investment_30d"
replace statistic_order = 21 if statistic_code == "investment_12m"
replace statistic_order = 22 if statistic_code == "owns_land"
replace statistic_order = 23 if statistic_code == "rents_land"
replace statistic_order = 24 if statistic_code == "land_monthly_rental_value"
replace statistic_order = 25 if statistic_code == "owns_building"
replace statistic_order = 26 if statistic_code == "rents_building"
replace statistic_order = 27 if statistic_code == "building_monthly_rental_value"
replace statistic_order = 28 if statistic_code == "owns_furniture"
replace statistic_order = 29 if statistic_code == "rents_furniture"
replace statistic_order = 30 if statistic_code == "furniture_value_owned"
replace statistic_order = 31 if statistic_code == "furniture_rent_30d"
replace statistic_order = 32 if statistic_code == "owns_vehicle"
replace statistic_order = 33 if statistic_code == "rents_vehicle"
replace statistic_order = 34 if statistic_code == "vehicle_count"
replace statistic_order = 35 if statistic_code == "vehicle_value_owned"
replace statistic_order = 36 if statistic_code == "vehicle_rent_30d"
replace statistic_order = 37 if statistic_code == "owns_machine"
replace statistic_order = 38 if statistic_code == "rents_machine"
replace statistic_order = 39 if statistic_code == "machine_count"
replace statistic_order = 40 if statistic_code == "machine_value_owned"
replace statistic_order = 41 if statistic_code == "machine_rent_30d"
replace statistic_order = 42 if statistic_code == "practice_price_obs"
replace statistic_order = 43 if statistic_code == "practice_price_coord"
replace statistic_order = 44 if statistic_code == "practice_demand"
replace statistic_order = 45 if statistic_code == "practice_sales"
replace statistic_order = 46 if statistic_code == "practice_suppliers"
replace statistic_order = 47 if statistic_code == "practice_records"
replace statistic_order = 48 if statistic_code == "practice_costs"
replace statistic_order = 49 if statistic_code == "practice_profits"
replace statistic_order = 50 if statistic_code == "practice_performance"
replace statistic_order = 51 if statistic_code == "practice_targets"
replace statistic_order = 52 if statistic_code == "new_product_30d"
replace statistic_order = 53 if statistic_code == "dropped_product_30d"
replace statistic_order = 54 if statistic_code == "demel_rough"
replace statistic_order = 55 if statistic_code == "inflation_expect_pct"

local next_order = 56
forvalues i = 1/9 {
    local response_code : word `i' of `response_codes'
    replace statistic_order = `next_order' if statistic_code == "comp_up_`response_code'"
    local next_order = `next_order' + 1
}
forvalues i = 1/9 {
    local response_code : word `i' of `response_codes'
    replace statistic_order = `next_order' if statistic_code == "comp_down_`response_code'"
    local next_order = `next_order' + 1
}
forvalues i = 1/9 {
    local response_code : word `i' of `response_codes'
    replace statistic_order = `next_order' if statistic_code == "twice_cust_`response_code'"
    local next_order = `next_order' + 1
}
replace statistic_order = `next_order' if statistic_code == "twice_cust_new_price"
local next_order = `next_order' + 1
replace statistic_order = `next_order' if statistic_code == "twice_cust_share_info"
local next_order = `next_order' + 1
forvalues i = 1/9 {
    local response_code : word `i' of `response_codes'
    replace statistic_order = `next_order' if statistic_code == "twice_cust_others_`response_code'"
    local next_order = `next_order' + 1
}
forvalues i = 1/9 {
    local response_code : word `i' of `response_codes'
    replace statistic_order = `next_order' if statistic_code == "half_cust_`response_code'"
    local next_order = `next_order' + 1
}
replace statistic_order = `next_order' if statistic_code == "half_cust_new_price"
local next_order = `next_order' + 1
replace statistic_order = `next_order' if statistic_code == "half_cust_share_info"
local next_order = `next_order' + 1
forvalues i = 1/9 {
    local response_code : word `i' of `response_codes'
    replace statistic_order = `next_order' if statistic_code == "half_cust_others_`response_code'"
    local next_order = `next_order' + 1
}

order enterprise_category_id enterprise_category_key enterprise_category_label ///
    category_assignment_tier statistic_order statistic_code statistic_label ///
    mean sd weighted_n raw_n

sort enterprise_category_id statistic_order
compress
save "`OUTPUT_DTA'", replace
export delimited using "`OUTPUT_CSV'", replace

di as text "07.do completed successfully."
di as text "Wrote long summary dataset: `OUTPUT_DTA'"
di as text "Wrote CSV mirror: `OUTPUT_CSV'"
