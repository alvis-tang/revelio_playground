clear all
set more off
version 17.0

********************************************************************
* Pressure test harness for 06_enterprise_reclassify.do
********************************************************************

* Resolve the repository root from this harness location.
local this_do "`c(filename)'"
if "`this_do'" == "" {
    local this_do "/Users/kstang/work/github/steg_call/scripts/test_06_pressure.do"
}
local repo_root = substr("`this_do'", 1, strrpos("`this_do'", "/scripts/") - 1)
local target_do "`repo_root'/scripts/06_enterprise_reclassify.do"

* Write fixture data and outputs under a temp project root so production files stay untouched.
local tmp_root "`c(tmpdir)'/steg_call_pressure_06"
capture mkdir "`tmp_root'"
capture mkdir "`tmp_root'/data"
capture mkdir "`tmp_root'/data/Phase 1 enterprise (market) baseline"
capture mkdir "`tmp_root'/proc"
capture mkdir "`tmp_root'/results"
capture mkdir "`tmp_root'/tables"
capture mkdir "`tmp_root'/logs"
capture mkdir "`tmp_root'/scripts"

global PROJ "`tmp_root'"
global DATA "`tmp_root'/data"
global PROC "`tmp_root'/proc"
global RESULTS "`tmp_root'/results"
global TABLES "`tmp_root'/tables"
global LOGS "`tmp_root'/logs"
global SCRIPTS "`tmp_root'/scripts"

********************************************************************
* 1. Build a minimal fixture that covers harmonization edge cases
********************************************************************

set obs 47

gen str8 survey_entid = "f" + string(_n, "%03.0f")
gen str8 survey_key = "key" + string(_n, "%03.0f")
gen str4 survey_source = "src"
gen str6 sample_strata = "st1"
gen double weight_raw = 10
gen double weight_adj = 10
gen str6 s1_market = "mkt1"
gen str20 s1_ent_cat = ""
gen byte s1_ent_cat_1 = .
gen byte s1_ent_cat_2 = .
label variable s1_ent_cat_1 "Primary enterprise category: Raw food stalls"
label variable s1_ent_cat_2 "Primary enterprise category: Processed food stalls"

gen str20 s7_prod1_productname = ""
gen str120 s7_commonproduct1 = ""
gen str120 s7_prod1_productname_oth = ""
gen str20 s7_prod2_productname = ""
gen str120 s7_commonproduct2 = ""
gen str120 s7_prod2_productname_oth = ""
gen str20 s7_prod3_productname = ""
gen str120 s7_commonproduct3 = ""
gen str120 s7_prod3_productname_oth = ""

gen double s8_bus_practice_price_obs = 1
gen double s8_bus_practice_sales = 1
gen double s8_bus_practice_suppliers = 0
gen double s8_bus_practice_records = 1
gen double s8_bus_practice_costs = 0
gen double s8_bus_practice_profits = 1
gen double s8_bus_practice_performance = 1
gen double s8_bus_practice_targets = 0
gen double s9_price_avg_market = 100
gen double s9_price_exp_next_month = 125
gen byte land_own_ind = 1
gen byte land_rent_ind = 0
gen double land_own_monthly = 10
gen double land_rent_monthly = 0
gen byte building_own_ind = 0
gen byte building_rent_ind = 1
gen double build_own_monthly = 0
gen double build_rent_monthly = 20
gen byte furniture_own_ind = 1
gen byte furniture_rent_ind = 0
gen double furniture_value_mwk = 30
gen double furniture_rent_mwk = 0
gen byte vehicle_own_ind = 0
gen byte vehicle_rent_ind = 1
gen double vehicle_count = 1
gen double vehicle_value_mwk = 0
gen double vehicle_rent_mwk = 40
gen byte machine_own_ind = 1
gen byte machine_rent_ind = 0
gen double machine_count = 2
gen double machine_value_mwk = 50
gen double machine_rent_mwk = 0

forvalues i = 1/9 {
    gen byte s9_comp_up_response_`i' = 0
    gen byte s9_comp_down_response_`i' = 0
    gen byte s9_twice_cust_shock_response_`i' = 0
    gen byte s9_twice_cust_other_resp_`i' = 0
    gen byte s9_half_cust_shock_response_`i' = 0
    gen byte s9_half_cust_other_resp_`i' = 0
}

gen byte s9_twice_cust_new_price = 0
gen byte s9_twice_cust_share_info = 1
gen byte s9_half_cust_new_price = 1
gen byte s9_half_cust_share_info = 0

* Exact-bundle support at the threshold, with one firm carrying a duplicate slot.
replace s1_ent_cat = "1" in 1/20
replace s7_prod1_productname = "100" in 1/20
replace s7_commonproduct1 = "Apple" in 1/20
replace s7_prod2_productname = "200" in 2/20
replace s7_commonproduct2 = "Banana" in 2/20
replace s7_prod2_productname = "100" in 1
replace s7_commonproduct2 = "Apple" in 1
replace s7_prod3_productname = "200" in 1/20
replace s7_commonproduct3 = "Banana" in 1/20

* A -77 slot should map when its normalized name uniquely identifies a valid code.
replace s1_ent_cat = "1" in 21
replace s7_prod1_productname = "-77" in 21
replace s7_prod1_productname_oth = "Apple" in 21

* A -77 slot should remain unresolved when the readable name maps to multiple codes.
replace s1_ent_cat = "C" in 22/24
replace s7_prod1_productname = "300" in 22
replace s7_commonproduct1 = "Soap" in 22
replace s7_prod1_productname = "301" in 23
replace s7_commonproduct1 = "Soap" in 23
replace s7_prod1_productname = "-77" in 24
replace s7_commonproduct1 = "Soap" in 24

* Special missing codes should be carried through with a fabricated label when blank.
replace s7_prod1_productname = "-88" in 25
replace s7_prod1_productname = "-99" in 26
replace s1_ent_cat = "D" in 26

* Primary-good-by-anchor support at 20, while exact bundles stay below the threshold.
replace s1_ent_cat = "2" in 27/45
replace s7_prod1_productname = "500" in 27/46
replace s7_commonproduct1 = "Rice" in 27/46
replace s7_prod2_productname = "600" in 27/45
replace s7_commonproduct2 = "Oil" in 27/45
replace s1_ent_cat = "2   C" in 46
replace s7_prod2_productname = "601" in 46
replace s7_commonproduct2 = "Salt" in 46

* A no-good firm should fall all the way back to anchor-only.
replace s1_ent_cat = "Z" in 47

replace s8_bus_practice_performance = 2 in 1
replace s8_bus_practice_targets = 1 in 1
replace s9_comp_up_response_1 = 1 in 1
replace s9_comp_down_response_7 = 1 in 1
replace s9_twice_cust_shock_response_3 = 1 in 1
replace s9_twice_cust_other_resp_6 = 1 in 1
replace s9_half_cust_shock_response_2 = 1 in 1
replace s9_half_cust_other_resp_8 = 1 in 1

replace s9_price_avg_market = 0 in 2
replace s9_price_exp_next_month = 180 in 2
replace s9_twice_cust_new_price = 1 in 2
replace s9_half_cust_share_info = 1 in 2

save "$DATA/Phase 1 enterprise (market) baseline/enterprise_baseline_data_13_03_2026.dta", replace

preserve
    keep survey_key survey_source ///
        land_own_ind land_rent_ind land_own_monthly land_rent_monthly ///
        building_own_ind building_rent_ind build_own_monthly build_rent_monthly ///
        furniture_own_ind furniture_rent_ind furniture_value_mwk furniture_rent_mwk ///
        vehicle_own_ind vehicle_rent_ind vehicle_count vehicle_value_mwk vehicle_rent_mwk ///
        machine_own_ind machine_rent_ind machine_count machine_value_mwk machine_rent_mwk
    save "$PROC/enterprise_heterogeneity_BL.dta", replace
restore

********************************************************************
* 2. Run the target script against the synthetic fixture
********************************************************************

do "`target_do'"

********************************************************************
* 3. Assert exact outputs and key invariants on the generated dataset
********************************************************************

use "$PROC/enterprise_product_sector_BL.dta", clear

* The final file should be unique on firm-by-anchor after anchor expansion.
isid original_firm_id anchor_index
assert enterprise_category_key != ""

* Exact bundles at support 20 should stay native even with duplicate raw slots.
count if survey_entid == "f001" & anchor_code == "1"
assert r(N) == 1
assert harmonization_status_slot1 == "kept_original" if survey_entid == "f001" & anchor_code == "1"
assert harmonized_product_code_slot1 == "100" if survey_entid == "f001" & anchor_code == "1"
assert harmonized_product_code_slot2 == "100" if survey_entid == "f001" & anchor_code == "1"
assert harmonized_product_code_slot3 == "200" if survey_entid == "f001" & anchor_code == "1"
assert harmonized_repeat_in_raw == 1 if survey_entid == "f001" & anchor_code == "1"
assert n_unique_goods == 2 if survey_entid == "f001" & anchor_code == "1"
assert unique_good_code1 == "100" if survey_entid == "f001" & anchor_code == "1"
assert unique_good_code2 == "200" if survey_entid == "f001" & anchor_code == "1"
assert unique_good_code3 == "" if survey_entid == "f001" & anchor_code == "1"
assert bundle_firm_n == 20 if survey_entid == "f001" & anchor_code == "1"
assert category_assignment_tier == "exact_bundle" if survey_entid == "f001" & anchor_code == "1"
assert demel_rough == 11 if survey_entid == "f001" & anchor_code == "1"
assert inflation_expect_pct == .25 if survey_entid == "f001" & anchor_code == "1"
assert s9_comp_up_response_1 == 1 if survey_entid == "f001" & anchor_code == "1"
assert s9_comp_down_response_7 == 1 if survey_entid == "f001" & anchor_code == "1"
assert s9_twice_cust_shock_response_3 == 1 if survey_entid == "f001" & anchor_code == "1"
assert s9_twice_cust_other_resp_6 == 1 if survey_entid == "f001" & anchor_code == "1"
assert s9_half_cust_shock_response_2 == 1 if survey_entid == "f001" & anchor_code == "1"
assert s9_half_cust_other_resp_8 == 1 if survey_entid == "f001" & anchor_code == "1"

* A unique -77 name should map onto the observed canonical code and name.
assert harmonization_status_slot1 == "mapped_from_-77" if survey_entid == "f021" & anchor_code == "1"
assert harmonized_product_code_slot1 == "100" if survey_entid == "f021" & anchor_code == "1"
assert harmonized_product_name_slot1 == "Apple" if survey_entid == "f021" & anchor_code == "1"
assert primary_harmonized_good_code == "100" if survey_entid == "f021" & anchor_code == "1"
assert category_assignment_tier == "primary_good_anchor" if survey_entid == "f021" & anchor_code == "1"
assert enterprise_category_key == "good:100|anchor:1" if survey_entid == "f021" & anchor_code == "1"
assert enterprise_category_label == "Apple x anchor Raw food stalls" if survey_entid == "f021" & anchor_code == "1"

* Ambiguous -77 names should remain unresolved and fall back to anchor-only.
assert harmonization_status_slot1 == "unresolved_-77" if survey_entid == "f024" & anchor_code == "C"
assert harmonized_product_code_slot1 == "-77" if survey_entid == "f024" & anchor_code == "C"
assert harmonized_product_name_slot1 == "Soap" if survey_entid == "f024" & anchor_code == "C"
assert category_assignment_tier == "anchor_only" if survey_entid == "f024" & anchor_code == "C"
assert enterprise_category_key == "anchor:C" if survey_entid == "f024" & anchor_code == "C"
assert enterprise_category_label == "anchor C" if survey_entid == "f024" & anchor_code == "C"

* Special missing codes should survive unchanged with the fabricated placeholder label.
assert harmonization_status_slot1 == "special_missing_code" if survey_entid == "f025" & anchor_code == "missing_anchor"
assert harmonized_product_code_slot1 == "-88" if survey_entid == "f025" & anchor_code == "missing_anchor"
assert harmonized_product_name_slot1 == "[missing label]" if survey_entid == "f025" & anchor_code == "missing_anchor"
assert n_unique_goods == 0 if survey_entid == "f025" & anchor_code == "missing_anchor"
assert enterprise_category_key == "anchor:missing_anchor" if survey_entid == "f025" & anchor_code == "missing_anchor"

assert harmonization_status_slot1 == "special_missing_code" if survey_entid == "f026" & anchor_code == "D"
assert harmonized_product_code_slot1 == "-99" if survey_entid == "f026" & anchor_code == "D"
assert harmonized_product_name_slot1 == "[missing label]" if survey_entid == "f026" & anchor_code == "D"
assert enterprise_category_key == "anchor:D" if survey_entid == "f026" & anchor_code == "D"

* Bundles with support 19 should pool to primary-good-by-anchor once that cell reaches 20.
assert bundle_firm_n == 19 if survey_entid == "f027" & anchor_code == "2"
assert primary_good_anchor_n == 20 if survey_entid == "f027" & anchor_code == "2"
assert category_assignment_tier == "primary_good_anchor" if survey_entid == "f027" & anchor_code == "2"
assert enterprise_category_key == "good:500|anchor:2" if survey_entid == "f027" & anchor_code == "2"
assert enterprise_category_label == "Rice x anchor Processed food stalls" if survey_entid == "f027" & anchor_code == "2"

* Repeated spaces should collapse to two anchors, and the weight should split evenly across rows.
bysort survey_entid: gen anchor_rows = _N
assert anchor_rows == 2 if survey_entid == "f046"
assert n_anchor_codes == 2 if survey_entid == "f046"
assert survey_weight_anchor == 5 if survey_entid == "f046"
assert primary_harmonized_good_code == "500" if survey_entid == "f046"
assert primary_good_anchor_n == 20 if survey_entid == "f046" & anchor_code == "2"
assert primary_good_anchor_n == 1 if survey_entid == "f046" & anchor_code == "C"
assert category_assignment_tier == "primary_good_anchor" if survey_entid == "f046" & anchor_code == "2"
assert category_assignment_tier == "anchor_only" if survey_entid == "f046" & anchor_code == "C"
assert enterprise_category_label == "Rice x anchor Processed food stalls" if survey_entid == "f046" & anchor_code == "2"
assert enterprise_category_label == "anchor C" if survey_entid == "f046" & anchor_code == "C"
drop anchor_rows

* A firm with no retained goods should still receive an anchor-only category.
assert n_unique_goods == 0 if survey_entid == "f047" & anchor_code == "Z"
assert category_assignment_tier == "anchor_only" if survey_entid == "f047" & anchor_code == "Z"
assert enterprise_category_key == "anchor:Z" if survey_entid == "f047" & anchor_code == "Z"
assert enterprise_category_label == "anchor Z" if survey_entid == "f047" & anchor_code == "Z"

* Bundle strings should concatenate only retained goods without trailing delimiters.
assert harmonized_bundle_code == "100|200" if survey_entid == "f001" & anchor_code == "1"
assert harmonized_bundle_name == "Apple | Banana" if survey_entid == "f001" & anchor_code == "1"
assert enterprise_category_key == "bundle:100|200" if survey_entid == "f001" & anchor_code == "1"

* Firms with a nonblank anchor string should not pick up spurious missing-anchor rows.
count if s1_ent_cat != "" & anchor_code == "missing_anchor"
assert r(N) == 0

* The 04.do derived expectation measure should be missing when baseline price is nonpositive.
assert missing(inflation_expect_pct) if survey_entid == "f002" & anchor_code == "1"

* Newly required expectation/shock fields should survive to the final processed file.
foreach v in demel_rough inflation_expect_pct s9_twice_cust_new_price s9_twice_cust_share_info ///
             s9_half_cust_new_price s9_half_cust_share_info land_own_ind machine_value_mwk {
    capture confirm variable `v'
    assert _rc == 0
}

* One blank-anchor firm plus one two-anchor firm should yield 48 output rows in total.
count
assert r(N) == 48

di as text "test_06_pressure.do completed successfully."
