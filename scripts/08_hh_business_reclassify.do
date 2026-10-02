clear all
set more off
version 17.0

********************************************************************
* Household business product harmonization and sector preparation
********************************************************************

********************************************************************
* 1. Define project paths and helper program
********************************************************************

if "$PROJ" == "" {
    local this_do "`c(filename)'"
    if "`this_do'" == "" {
        local this_do "/Users/kstang/work/github/steg_call/scripts/08_hh_business_reclassify.do"
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

local INPUT  "$PROC/p1_hhsur_businesses_b1.dta"
local OUTPUT "$PROC/hh_business_product_sector_BL.dta"
local SUPPORT_CUTOFF = 10

capture confirm file "`INPUT'"
if _rc {
    di as error "Input file not found: `INPUT'"
    exit 601
}

use "`INPUT'", clear

require_vars survey_hhid business_id survey_hh_weight ///
    s7_primary_ent_cat_index_1 s7_primary_ent_cat_value_1 ///
    s7_primary_ent_cat_index_2 s7_primary_ent_cat_value_2 ///
    s7_primary_ent_cat_index_3 s7_primary_ent_cat_value_3 ///
    s7_prod_name_prod1 s7_prod_name_prod2 s7_prod_name_prod3 ///
    s7_prod_type_oth1 s7_prod_type_oth2 s7_prod_type_oth3

ds s7_prod_type_*
local product_type_vars `r(varlist)'
local product_type_indicators
foreach v of local product_type_vars {
    if !inlist("`v'", "s7_prod_type_oth1", "s7_prod_type_oth2", "s7_prod_type_oth3") {
        local product_type_indicators `product_type_indicators' `v'
    }
}
if "`product_type_indicators'" == "" {
    di as error "No section-7 product-type indicator variables found."
    exit 111
}

********************************************************************
* 2. Clean strings and derive product-type lookup labels
********************************************************************

gen long original_business_id = _n

foreach v in s7_prod_name_prod1 s7_prod_name_prod2 s7_prod_name_prod3 ///
             s7_prod_type_oth1 s7_prod_type_oth2 s7_prod_type_oth3 {
    replace `v' = itrim(strtrim(`v'))
}

tempfile base_wide slot_harmonized bundle_counts
save `base_wide'

gen str20 raw_product_code1 = ""
gen str20 raw_product_code2 = ""
gen str20 raw_product_code3 = ""
gen str120 raw_indicator_label1 = ""
gen str120 raw_indicator_label2 = ""
gen str120 raw_indicator_label3 = ""

local product_type_order 1 2 3 4 5 6 7 8 9 10 11 12 13 14 _771 _772 _773 _88 _99
foreach code of local product_type_order {
    local v "s7_prod_type_`code'"
    capture confirm numeric variable `v'
    if !_rc {
        local code_label : variable label `v'
        replace raw_product_code1 = "`code'" if raw_product_code1 == "" & `v' == 1
        replace raw_indicator_label1 = "`code_label'" if raw_product_code1 == "`code'" & raw_indicator_label1 == ""

        replace raw_product_code2 = "`code'" if raw_product_code1 != "" & raw_product_code2 == "" & `v' == 1 ///
            & raw_product_code1 != "`code'"
        replace raw_indicator_label2 = "`code_label'" if raw_product_code2 == "`code'" & raw_indicator_label2 == ""

        replace raw_product_code3 = "`code'" if raw_product_code2 != "" & raw_product_code3 == "" & `v' == 1 ///
            & raw_product_code1 != "`code'" & raw_product_code2 != "`code'"
        replace raw_indicator_label3 = "`code_label'" if raw_product_code3 == "`code'" & raw_indicator_label3 == ""
    }
    else {
        capture confirm string variable `v'
        if !_rc {
            local code_label : variable label `v'
            replace raw_product_code1 = "`code'" if raw_product_code1 == "" & itrim(strtrim(`v')) == "1"
            replace raw_indicator_label1 = "`code_label'" if raw_product_code1 == "`code'" & raw_indicator_label1 == ""

            replace raw_product_code2 = "`code'" if raw_product_code1 != "" & raw_product_code2 == "" ///
                & itrim(strtrim(`v')) == "1" & raw_product_code1 != "`code'"
            replace raw_indicator_label2 = "`code_label'" if raw_product_code2 == "`code'" & raw_indicator_label2 == ""

            replace raw_product_code3 = "`code'" if raw_product_code2 != "" & raw_product_code3 == "" ///
                & itrim(strtrim(`v')) == "1" & raw_product_code1 != "`code'" & raw_product_code2 != "`code'"
            replace raw_indicator_label3 = "`code_label'" if raw_product_code3 == "`code'" & raw_indicator_label3 == ""
        }
    }
}

gen str120 raw_readable_name1 = s7_prod_name_prod1
gen str120 raw_readable_name2 = s7_prod_name_prod2
gen str120 raw_readable_name3 = s7_prod_name_prod3

gen str120 raw_other_text1 = ""
gen str120 raw_other_text2 = ""
gen str120 raw_other_text3 = ""

foreach s in 1 2 3 {
    replace raw_other_text`s' = s7_prod_type_oth1 if raw_product_code`s' == "_771"
    replace raw_other_text`s' = s7_prod_type_oth2 if raw_product_code`s' == "_772"
    replace raw_other_text`s' = s7_prod_type_oth3 if raw_product_code`s' == "_773"
    replace raw_other_text`s' = itrim(strtrim(raw_other_text`s'))
}

********************************************************************
* 3. Harmonize slot-level goods using product-type codes first
********************************************************************

preserve
    keep original_business_id survey_hhid business_id ///
        raw_product_code1 raw_product_code2 raw_product_code3 ///
        raw_readable_name1 raw_readable_name2 raw_readable_name3 ///
        raw_other_text1 raw_other_text2 raw_other_text3 ///
        raw_indicator_label1 raw_indicator_label2 raw_indicator_label3

    reshape long raw_product_code raw_readable_name raw_other_text raw_indicator_label, ///
        i(original_business_id) j(product_slot)

    replace raw_product_code = itrim(strtrim(raw_product_code))
    replace raw_readable_name = itrim(strtrim(raw_readable_name))
    replace raw_other_text = itrim(strtrim(raw_other_text))
    replace raw_indicator_label = itrim(strtrim(raw_indicator_label))

    gen str120 slot_display_name = raw_readable_name
    replace slot_display_name = raw_other_text if slot_display_name == "" & raw_other_text != ""
    replace slot_display_name = raw_indicator_label if slot_display_name == "" & raw_indicator_label != ""
    replace slot_display_name = "[missing label]" if inlist(raw_product_code, "_88", "_99") ///
        & raw_readable_name == "" & raw_other_text == ""

    gen str120 normalized_slot_name = lower(itrim(strtrim(slot_display_name)))

    tempfile long_slots canonical_by_code
    save `long_slots'

    keep if raw_product_code != ""
    keep if !inlist(raw_product_code, "_88", "_99")
    collapse (count) code_name_obs = original_business_id, ///
        by(raw_product_code normalized_slot_name slot_display_name)
    bysort raw_product_code: egen max_code_name_obs = max(code_name_obs)
    keep if code_name_obs == max_code_name_obs
    bysort raw_product_code (normalized_slot_name slot_display_name): keep if _n == 1
    rename slot_display_name canonical_name
    rename normalized_slot_name canonical_name_norm
    keep raw_product_code canonical_name canonical_name_norm
    save `canonical_by_code'

    use `long_slots', clear
    merge m:1 raw_product_code using `canonical_by_code', nogen keep(master match)

    gen str24 harmonization_status = "missing_code"
    replace harmonization_status = "kept_original" if raw_product_code != "" & ///
        !inlist(raw_product_code, "_88", "_99")
    replace harmonization_status = "special_missing_code" if inlist(raw_product_code, "_88", "_99")

    gen str20 harmonized_product_code = ""
    gen str120 harmonized_product_name = ""

    replace harmonized_product_code = raw_product_code if harmonization_status == "kept_original"
    replace harmonized_product_name = canonical_name if harmonization_status == "kept_original" & canonical_name != ""
    replace harmonized_product_name = slot_display_name if harmonization_status == "kept_original" & ///
        harmonized_product_name == ""

    replace harmonized_product_code = raw_product_code if harmonization_status == "special_missing_code"
    replace harmonized_product_name = slot_display_name if harmonization_status == "special_missing_code"

    keep original_business_id product_slot raw_product_code raw_readable_name raw_other_text ///
        raw_indicator_label slot_display_name normalized_slot_name ///
        harmonized_product_code harmonized_product_name harmonization_status

    reshape wide raw_product_code raw_readable_name raw_other_text raw_indicator_label ///
        slot_display_name normalized_slot_name harmonized_product_code ///
        harmonized_product_name harmonization_status, i(original_business_id) j(product_slot)

    rename (raw_product_code1 raw_product_code2 raw_product_code3) ///
        (raw_product_code_slot1 raw_product_code_slot2 raw_product_code_slot3)
    rename (raw_readable_name1 raw_readable_name2 raw_readable_name3) ///
        (raw_readable_name_slot1 raw_readable_name_slot2 raw_readable_name_slot3)
    rename (raw_other_text1 raw_other_text2 raw_other_text3) ///
        (raw_other_text_slot1 raw_other_text_slot2 raw_other_text_slot3)
    rename (raw_indicator_label1 raw_indicator_label2 raw_indicator_label3) ///
        (raw_indicator_label_slot1 raw_indicator_label_slot2 raw_indicator_label_slot3)
    rename (slot_display_name1 slot_display_name2 slot_display_name3) ///
        (slot_display_name1 slot_display_name2 slot_display_name3)
    rename (normalized_slot_name1 normalized_slot_name2 normalized_slot_name3) ///
        (normalized_slot_name1 normalized_slot_name2 normalized_slot_name3)
    rename (harmonized_product_code1 harmonized_product_code2 harmonized_product_code3) ///
        (harmonized_product_code_slot1 harmonized_product_code_slot2 harmonized_product_code_slot3)
    rename (harmonized_product_name1 harmonized_product_name2 harmonized_product_name3) ///
        (harmonized_product_name_slot1 harmonized_product_name_slot2 harmonized_product_name_slot3)
    rename (harmonization_status1 harmonization_status2 harmonization_status3) ///
        (harmonization_status_slot1 harmonization_status_slot2 harmonization_status_slot3)

    save `slot_harmonized'
restore

use `base_wide', clear
merge 1:1 original_business_id using `slot_harmonized', nogen assert(match)

********************************************************************
* 4. Collapse harmonized slots to distinct goods bundles
********************************************************************

gen str20 unique_good_code1 = ""
gen str20 unique_good_code2 = ""
gen str20 unique_good_code3 = ""
gen str120 unique_good_name1 = ""
gen str120 unique_good_name2 = ""
gen str120 unique_good_name3 = ""

forvalues s = 1/3 {
    local code harmonized_product_code_slot`s'
    local name harmonized_product_name_slot`s'

    replace unique_good_code1 = `code' if unique_good_code1 == "" & ///
        !inlist(`code', "", "_88", "_99")
    replace unique_good_name1 = `name' if unique_good_name1 == "" & ///
        !inlist(`code', "", "_88", "_99")

    replace unique_good_code2 = `code' if unique_good_code1 != "" & unique_good_code2 == "" ///
        & !inlist(`code', "", "_88", "_99") & `code' != unique_good_code1
    replace unique_good_name2 = `name' if unique_good_code1 != "" & unique_good_code2 == `code' ///
        & unique_good_name2 == ""

    replace unique_good_code3 = `code' if unique_good_code2 != "" & unique_good_code3 == "" ///
        & !inlist(`code', "", "_88", "_99") & `code' != unique_good_code1 & `code' != unique_good_code2
    replace unique_good_name3 = `name' if unique_good_code2 != "" & unique_good_code3 == `code' ///
        & unique_good_name3 == ""
}

gen byte n_unique_goods = (unique_good_code1 != "") + ///
    (unique_good_code2 != "") + ///
    (unique_good_code3 != "")

gen str62 harmonized_bundle_code = ""
replace harmonized_bundle_code = unique_good_code1 if unique_good_code1 != ""
replace harmonized_bundle_code = harmonized_bundle_code + "|" + unique_good_code2 if unique_good_code2 != ""
replace harmonized_bundle_code = harmonized_bundle_code + "|" + unique_good_code3 if unique_good_code3 != ""

gen str366 harmonized_bundle_name = ""
replace harmonized_bundle_name = unique_good_name1 if unique_good_name1 != ""
replace harmonized_bundle_name = harmonized_bundle_name + " | " + unique_good_name2 if unique_good_name2 != ""
replace harmonized_bundle_name = harmonized_bundle_name + " | " + unique_good_name3 if unique_good_name3 != ""

gen str20 primary_harmonized_good_code = unique_good_code1
gen str120 primary_harmonized_good_name = unique_good_name1

preserve
    keep original_business_id harmonized_bundle_code
    keep if harmonized_bundle_code != ""
    duplicates drop
    bysort harmonized_bundle_code: gen long bundle_firm_n = _N
    keep harmonized_bundle_code bundle_firm_n
    duplicates drop
    save `bundle_counts'
restore

********************************************************************
* 5. Expand businesses across anchor categories and assign tiers
********************************************************************

foreach s in 1 2 3 {
    capture confirm string variable s7_primary_ent_cat_index_`s'
    if !_rc {
        gen str40 anchor_code`s' = itrim(strtrim(s7_primary_ent_cat_index_`s'))
    }
    else {
        tostring s7_primary_ent_cat_index_`s', gen(anchor_code`s') usedisplayformat force
        replace anchor_code`s' = itrim(strtrim(anchor_code`s'))
        replace anchor_code`s' = "" if anchor_code`s' == "."
    }

    capture confirm string variable s7_primary_ent_cat_value_`s'
    if !_rc {
        gen str120 anchor_value`s' = itrim(strtrim(s7_primary_ent_cat_value_`s'))
    }
    else {
        tostring s7_primary_ent_cat_value_`s', gen(anchor_value`s') usedisplayformat force
        replace anchor_value`s' = itrim(strtrim(anchor_value`s'))
        replace anchor_value`s' = "" if anchor_value`s' == "."
    }

    gen byte anchor_present`s' = anchor_code`s' != "" | anchor_value`s' != ""
}

gen int raw_n_anchor_codes = anchor_present1 + anchor_present2 + anchor_present3
gen int n_anchor_codes = raw_n_anchor_codes
replace n_anchor_codes = 1 if n_anchor_codes == 0

reshape long anchor_code anchor_value anchor_present, i(original_business_id) j(anchor_index)
drop if raw_n_anchor_codes == 0 & anchor_index > 1
drop if raw_n_anchor_codes > 0 & anchor_present == 0

replace anchor_code = anchor_value if anchor_code == "" & anchor_value != ""
replace anchor_code = "missing_anchor" if anchor_code == ""

gen str120 anchor_display = anchor_value
replace anchor_display = anchor_code if anchor_display == ""

gen double survey_weight_raw_business = survey_hh_weight
gen double survey_weight_anchor = survey_hh_weight / n_anchor_codes

merge m:1 harmonized_bundle_code using `bundle_counts', nogen
replace bundle_firm_n = 0 if missing(bundle_firm_n)

bysort primary_harmonized_good_code anchor_code: egen long primary_good_anchor_n = ///
    count(original_business_id) if primary_harmonized_good_code != ""
replace primary_good_anchor_n = 0 if missing(primary_good_anchor_n)

gen str24 category_assignment_tier = ""
gen str120 enterprise_category_key = ""

replace category_assignment_tier = "exact_bundle" if harmonized_bundle_code != "" & ///
    bundle_firm_n >= `SUPPORT_CUTOFF'
replace enterprise_category_key = "bundle:" + harmonized_bundle_code if ///
    category_assignment_tier == "exact_bundle"

replace category_assignment_tier = "primary_good_anchor" if category_assignment_tier == "" ///
    & primary_harmonized_good_code != "" & primary_good_anchor_n >= `SUPPORT_CUTOFF'
replace enterprise_category_key = "good:" + primary_harmonized_good_code + "|anchor:" + anchor_code ///
    if category_assignment_tier == "primary_good_anchor"

replace category_assignment_tier = "anchor_only" if category_assignment_tier == ""
replace enterprise_category_key = "anchor:" + anchor_code if category_assignment_tier == "anchor_only"

egen long enterprise_category_id = group(enterprise_category_key)
gen str244 enterprise_category_label = harmonized_bundle_name if category_assignment_tier == "exact_bundle"
replace enterprise_category_label = primary_harmonized_good_name + " x anchor " + anchor_display ///
    if category_assignment_tier == "primary_good_anchor"
replace enterprise_category_label = "anchor " + anchor_display if category_assignment_tier == "anchor_only"

gen byte category_is_native = category_assignment_tier == "exact_bundle"
gen byte category_is_pooled = category_is_native == 0
gen byte harmonized_repeat_in_raw = ///
    (harmonized_product_code_slot1 != "" & harmonized_product_code_slot1 == harmonized_product_code_slot2) | ///
    (harmonized_product_code_slot1 != "" & harmonized_product_code_slot1 == harmonized_product_code_slot3) | ///
    (harmonized_product_code_slot2 != "" & harmonized_product_code_slot2 == harmonized_product_code_slot3)

********************************************************************
* 6. Order final variables and write the output
********************************************************************

order original_business_id survey_hhid business_id ///
    survey_hh_weight survey_weight_raw_business survey_weight_anchor ///
    raw_n_anchor_codes n_anchor_codes anchor_index anchor_code anchor_value anchor_display ///
    s7_main_decision s7_primary_sec_cat s7_primary_sec_cat_oth ///
    s7_primary_ent_cat s7_primary_ent_cat_r_count ///
    s7_primary_ent_cat_index_1 s7_primary_ent_cat_value_1 ///
    s7_primary_ent_cat_index_2 s7_primary_ent_cat_value_2 ///
    s7_primary_ent_cat_index_3 s7_primary_ent_cat_value_3 ///
    s7_prod_name_prod1 s7_prod_name_prod2 s7_prod_name_prod3 ///
    s7_prod_type_oth1 s7_prod_type_oth2 s7_prod_type_oth3 ///
    raw_product_code_slot1 raw_readable_name_slot1 raw_other_text_slot1 raw_indicator_label_slot1 ///
    slot_display_name1 normalized_slot_name1 harmonized_product_code_slot1 ///
    harmonized_product_name_slot1 harmonization_status_slot1 ///
    raw_product_code_slot2 raw_readable_name_slot2 raw_other_text_slot2 raw_indicator_label_slot2 ///
    slot_display_name2 normalized_slot_name2 harmonized_product_code_slot2 ///
    harmonized_product_name_slot2 harmonization_status_slot2 ///
    raw_product_code_slot3 raw_readable_name_slot3 raw_other_text_slot3 raw_indicator_label_slot3 ///
    slot_display_name3 normalized_slot_name3 harmonized_product_code_slot3 ///
    harmonized_product_name_slot3 harmonization_status_slot3 ///
    harmonized_repeat_in_raw ///
    unique_good_code1 unique_good_name1 unique_good_code2 unique_good_name2 unique_good_code3 unique_good_name3 ///
    n_unique_goods primary_harmonized_good_code primary_harmonized_good_name ///
    harmonized_bundle_code harmonized_bundle_name bundle_firm_n primary_good_anchor_n ///
    category_assignment_tier enterprise_category_id enterprise_category_key enterprise_category_label ///
    category_is_native category_is_pooled

compress
save "`OUTPUT'", replace

di as text "08_hh_business_reclassify.do completed successfully."
di as text "Wrote household business product-sector dataset: `OUTPUT'"
