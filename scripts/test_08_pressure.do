clear all
set more off
version 17.0

********************************************************************
* Pressure test harness for 08_hh_business_reclassify.do
********************************************************************

local this_do "`c(filename)'"
if "`this_do'" == "" {
    local this_do "/Users/kstang/work/github/steg_call/scripts/test_08_pressure.do"
}
local repo_root = substr("`this_do'", 1, strrpos("`this_do'", "/scripts/") - 1)
local target_do "`repo_root'/scripts/08_hh_business_reclassify.do"

local tmp_root "`c(tmpdir)'/steg_call_pressure_08"
capture mkdir "`tmp_root'"
capture mkdir "`tmp_root'/proc"
capture mkdir "`tmp_root'/scripts"
capture mkdir "`tmp_root'/data"
capture mkdir "`tmp_root'/results"
capture mkdir "`tmp_root'/tables"
capture mkdir "`tmp_root'/logs"

global PROJ "`tmp_root'"
global DATA "`tmp_root'/data"
global PROC "`tmp_root'/proc"
global RESULTS "`tmp_root'/results"
global TABLES "`tmp_root'/tables"
global LOGS "`tmp_root'/logs"
global SCRIPTS "`tmp_root'/scripts"

********************************************************************
* 1. Build a business-level fixture matching the 03.do output contract
********************************************************************

set obs 24

gen str8 survey_hhid = "hh" + string(_n, "%03.0f")
gen byte business_id = 1
gen double survey_hh_weight = 10

gen byte s7_main_decision = 1
gen byte s7_primary_sec_cat = 1
gen str40 s7_primary_sec_cat_oth = ""
gen str40 s7_primary_ent_cat = ""
gen byte s7_primary_ent_cat_r_count = 1

gen str20 s7_primary_ent_cat_index_1 = ""
gen str120 s7_primary_ent_cat_value_1 = ""
gen str20 s7_primary_ent_cat_index_2 = ""
gen str120 s7_primary_ent_cat_value_2 = ""
gen str20 s7_primary_ent_cat_index_3 = ""
gen str120 s7_primary_ent_cat_value_3 = ""

gen str120 s7_prod_name_prod1 = ""
gen str120 s7_prod_name_prod2 = ""
gen str120 s7_prod_name_prod3 = ""
gen str120 s7_prod_type_oth1 = ""
gen str120 s7_prod_type_oth2 = ""
gen str120 s7_prod_type_oth3 = ""

foreach code in 1 2 3 4 5 _771 _772 _773 _88 _99 {
    gen byte s7_prod_type_`code' = 0
}

label variable s7_prod_type_1 "Apple"
label variable s7_prod_type_2 "Banana"
label variable s7_prod_type_3 "Soap"
label variable s7_prod_type_4 "Salt"
label variable s7_prod_type_5 "Tailoring"
label variable s7_prod_type__771 "Other product 1"
label variable s7_prod_type__772 "Other product 2"
label variable s7_prod_type__773 "Other product 3"
label variable s7_prod_type__88 "Don't know"
label variable s7_prod_type__99 "Missing"

* Exact-bundle support at the cutoff.
replace s7_primary_ent_cat_index_1 = "A" in 1/10
replace s7_primary_ent_cat_value_1 = "Raw food" in 1/10
replace s7_prod_type_1 = 1 in 1/10
replace s7_prod_type_2 = 1 in 1/10
replace s7_prod_name_prod1 = "Apple" in 1/10
replace s7_prod_name_prod2 = "Banana" in 1/10

* Bundle support below cutoff, but primary-good-by-anchor reaches the cutoff.
replace s7_primary_ent_cat_index_1 = "B" in 11/20
replace s7_primary_ent_cat_value_1 = "Processed food" in 11/20
replace s7_prod_type_1 = 1 in 11/21
replace s7_prod_name_prod1 = "Apple" in 11/21

replace s7_prod_type_3 = 1 in 11/19
replace s7_prod_name_prod2 = "Soap" in 11/19

replace s7_prod_type_4 = 1 in 20
replace s7_prod_name_prod2 = "Salt" in 20

* A multi-anchor business should split weight and classify separately by anchor.
replace s7_primary_ent_cat_index_1 = "B" in 21
replace s7_primary_ent_cat_value_1 = "Processed food" in 21
replace s7_primary_ent_cat_index_2 = "C" in 21
replace s7_primary_ent_cat_value_2 = "Services" in 21

* A one-off business should fall back to anchor-only.
replace s7_primary_ent_cat_index_1 = "D" in 22
replace s7_primary_ent_cat_value_1 = "Tailoring" in 22
replace s7_prod_type_5 = 1 in 22
replace s7_prod_name_prod1 = "Tailoring" in 22

* Special missing product types should not become retained goods.
replace s7_prod_type__88 = 1 in 23

* Other-specified product type should use the free-text label fallback.
replace s7_primary_ent_cat_index_1 = "E" in 24
replace s7_primary_ent_cat_value_1 = "Other goods" in 24
replace s7_prod_type__771 = 1 in 24
replace s7_prod_type_oth1 = "Custom snack" in 24

save "$PROC/p1_hhsur_businesses_b1.dta", replace

********************************************************************
* 2. Run the target script against the synthetic fixture
********************************************************************

do "`target_do'"

********************************************************************
* 3. Assert exact outputs and household-business invariants
********************************************************************

use "$PROC/hh_business_product_sector_BL.dta", clear

isid original_business_id anchor_index
assert enterprise_category_key != ""

* Exact bundles at support 10 should stay native.
assert category_assignment_tier == "exact_bundle" if survey_hhid == "hh001" & anchor_code == "A"
assert bundle_firm_n == 10 if survey_hhid == "hh001" & anchor_code == "A"
assert enterprise_category_key == "bundle:1|2" if survey_hhid == "hh001" & anchor_code == "A"
assert enterprise_category_label == "Apple | Banana" if survey_hhid == "hh001" & anchor_code == "A"

* Sub-cutoff bundles should pool to primary-good-by-anchor once the support reaches 10.
assert category_assignment_tier == "primary_good_anchor" if survey_hhid == "hh011" & anchor_code == "B"
assert bundle_firm_n == 9 if survey_hhid == "hh011" & anchor_code == "B"
assert primary_good_anchor_n == 11 if survey_hhid == "hh011" & anchor_code == "B"
assert enterprise_category_key == "good:1|anchor:B" if survey_hhid == "hh011" & anchor_code == "B"
assert enterprise_category_label == "Apple x anchor Processed food" if survey_hhid == "hh011" & anchor_code == "B"

* Multi-anchor businesses should split weight and classify independently by anchor.
bysort survey_hhid: gen anchor_rows = _N
assert anchor_rows == 2 if survey_hhid == "hh021"
assert n_anchor_codes == 2 if survey_hhid == "hh021"
assert survey_weight_anchor == 5 if survey_hhid == "hh021"
assert category_assignment_tier == "primary_good_anchor" if survey_hhid == "hh021" & anchor_code == "B"
assert category_assignment_tier == "anchor_only" if survey_hhid == "hh021" & anchor_code == "C"
drop anchor_rows

* Rare businesses should fall back to anchor-only.
assert category_assignment_tier == "anchor_only" if survey_hhid == "hh022" & anchor_code == "D"
assert enterprise_category_key == "anchor:D" if survey_hhid == "hh022" & anchor_code == "D"

* Special missing product types should survive but not count as retained goods.
assert anchor_code == "missing_anchor" if survey_hhid == "hh023"
assert harmonization_status_slot1 == "special_missing_code" if survey_hhid == "hh023"
assert harmonized_product_code_slot1 == "_88" if survey_hhid == "hh023"
assert harmonized_product_name_slot1 == "[missing label]" if survey_hhid == "hh023"
assert n_unique_goods == 0 if survey_hhid == "hh023"
assert category_assignment_tier == "anchor_only" if survey_hhid == "hh023"
assert enterprise_category_key == "anchor:missing_anchor" if survey_hhid == "hh023"

* Other-specified product types should use the free-text fallback label.
assert harmonized_product_code_slot1 == "_771" if survey_hhid == "hh024" & anchor_code == "E"
assert harmonized_product_name_slot1 == "Custom snack" if survey_hhid == "hh024" & anchor_code == "E"
assert category_assignment_tier == "anchor_only" if survey_hhid == "hh024" & anchor_code == "E"

* One multi-anchor business adds one extra output row.
count
assert r(N) == 25

di as text "test_08_pressure.do completed successfully."
