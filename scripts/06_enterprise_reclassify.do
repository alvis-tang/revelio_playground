clear all
set more off
version 17.0

********************************************************************
* Baseline enterprise product harmonization and sector preparation
********************************************************************

********************************************************************
* 1. Define project paths and helper program
********************************************************************

if "$PROJ" == "" {
    local this_do "`c(filename)'"
    if "`this_do'" == "" {
        local this_do "/Users/kstang/work/github/steg_call/scripts/06_enterprise_reclassify.do"
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

local INPUT  "$DATA/Phase 1 enterprise (market) baseline/enterprise_baseline_data_13_03_2026.dta"
local HET_INPUT "$PROC/enterprise_heterogeneity_BL.dta"
local OUTPUT "$PROC/enterprise_product_sector_BL.dta"

* Confirm the baseline enterprise file exists before opening it.
capture confirm file "`INPUT'"
if _rc {
    di as error "Input file not found: `INPUT'"
    exit 601
}

capture confirm file "`HET_INPUT'"
if _rc {
    di as error "Input file not found: `HET_INPUT'"
    exit 601
}

capture mkdir "$PROC"

use "`INPUT'", clear
replace survey_key = strtrim(survey_key)

* Pull forward firm-level asset fields so 07 can summarize from one processed file.
tempfile legacy_assets
preserve
    use "`HET_INPUT'", clear
    keep if survey_source == "baseline_survey"
    replace survey_key = strtrim(survey_key)
    require_vars survey_key ///
        land_own_ind land_rent_ind land_own_monthly land_rent_monthly ///
        building_own_ind building_rent_ind build_own_monthly build_rent_monthly ///
        furniture_own_ind furniture_rent_ind furniture_value_mwk furniture_rent_mwk ///
        vehicle_own_ind vehicle_rent_ind vehicle_count vehicle_value_mwk vehicle_rent_mwk ///
        machine_own_ind machine_rent_ind machine_count machine_value_mwk machine_rent_mwk
    keep survey_key ///
        land_own_ind land_rent_ind land_own_monthly land_rent_monthly ///
        building_own_ind building_rent_ind build_own_monthly build_rent_monthly ///
        furniture_own_ind furniture_rent_ind furniture_value_mwk furniture_rent_mwk ///
        vehicle_own_ind vehicle_rent_ind vehicle_count vehicle_value_mwk vehicle_rent_mwk ///
        machine_own_ind machine_rent_ind machine_count machine_value_mwk machine_rent_mwk
    duplicates drop
    isid survey_key
    save `legacy_assets'
restore

merge m:1 survey_key using `legacy_assets', nogen assert(master match)

* Build a code-to-name lookup for anchor labels from the raw data dictionary.
tempfile anchor_lookup
tempname anchor_post
postfile `anchor_post' str20 anchor_code str120 anchor_name using `anchor_lookup', replace
ds s1_ent_cat_*
foreach v of varlist `r(varlist)' {
    if substr("`v'", 1, 11) == "s1_ent_cat_" & substr("`v'", 12, 1) != "_" {
        local anchor_code = substr("`v'", 12, .)
        local anchor_label : variable label `v'
        if "`anchor_label'" != "" {
            local anchor_label = subinstr("`anchor_label'", "Primary enterprise category: ", "", 1)
            local anchor_label = itrim(strtrim("`anchor_label'"))
            post `anchor_post' ("`anchor_code'") ("`anchor_label'")
        }
    }
}
postclose `anchor_post'

********************************************************************
* 2. Confirm required inputs and declare survey design
********************************************************************

require_vars survey_entid survey_key survey_source sample_strata weight_raw weight_adj ///
    s1_market s1_ent_cat ///
    s7_prod1_productname s7_commonproduct1 s7_prod1_productname_oth ///
    s7_prod2_productname s7_commonproduct2 s7_prod2_productname_oth ///
    s7_prod3_productname s7_commonproduct3 s7_prod3_productname_oth ///
    s8_bus_practice_price_obs s8_bus_practice_sales s8_bus_practice_suppliers ///
    s8_bus_practice_records s8_bus_practice_costs s8_bus_practice_profits ///
    s8_bus_practice_performance s8_bus_practice_targets ///
    s9_price_avg_market s9_price_exp_next_month ///
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

* Recreate the market-strata survey design used in downstream summaries.
egen strata_ms = group(s1_market sample_strata), label
gen psu = _n
svyset psu [pweight=weight_adj], strata(strata_ms) singleunit(centered)

********************************************************************
* 3. Clean identifiers and preserve the firm-level baseline snapshot
********************************************************************

* Keep a stable row id before reshaping so each firm can be merged back exactly once.
gen long original_firm_id = _n

// clean up product-related string variables formatting
replace survey_entid = strtrim(survey_entid)
replace survey_key = strtrim(survey_key)
replace survey_source = strtrim(survey_source)
replace s1_ent_cat = itrim(strtrim(s1_ent_cat))

* Carry 04.do expectation and shock measures into the processed enterprise file.
gen double demel_rough = s8_bus_practice_price_obs + s8_bus_practice_sales + ///
    s8_bus_practice_suppliers + s8_bus_practice_records + s8_bus_practice_costs + ///
    s8_bus_practice_profits + 3 * s8_bus_practice_performance + s8_bus_practice_targets
label variable demel_rough "De Mel rough business-practice score"

gen double inflation_expect_pct = ///
    (s9_price_exp_next_month - s9_price_avg_market) / s9_price_avg_market
replace inflation_expect_pct = . if missing(s9_price_exp_next_month) | ///
    missing(s9_price_avg_market) | s9_price_avg_market <= 0
label variable inflation_expect_pct "Expected inflation over next month for main product"

foreach v in s7_prod1_productname s7_commonproduct1 s7_prod1_productname_oth ///
             s7_prod2_productname s7_commonproduct2 s7_prod2_productname_oth ///
             s7_prod3_productname s7_commonproduct3 s7_prod3_productname_oth {
    replace `v' = itrim(strtrim(`v'))
}

* Store the untouched wide firm record and later bundle counts as tempfiles.
tempfile base_wide slot_harmonized bundle_counts
// current untouched wide firm-level version
save `base_wide'

preserve
    * Keep only the three product slots so they can be harmonized consistently.
    keep original_firm_id survey_entid survey_key ///
        s7_prod1_productname s7_commonproduct1 s7_prod1_productname_oth ///
        s7_prod2_productname s7_commonproduct2 s7_prod2_productname_oth ///
        s7_prod3_productname s7_commonproduct3 s7_prod3_productname_oth

    rename (s7_prod1_productname s7_prod2_productname s7_prod3_productname) ///
           (raw_product_code1 raw_product_code2 raw_product_code3)
    rename (s7_commonproduct1 s7_commonproduct2 s7_commonproduct3) ///
        (raw_readable_name1 raw_readable_name2 raw_readable_name3)
    rename (s7_prod1_productname_oth s7_prod2_productname_oth s7_prod3_productname_oth) ///
        (raw_other_text1 raw_other_text2 raw_other_text3)

    * Reshape to one row per product slot so code-name mappings can be learned across firms.
    reshape long raw_product_code raw_readable_name raw_other_text, i(original_firm_id) j(product_slot)

    replace raw_product_code = itrim(strtrim(raw_product_code))
    replace raw_readable_name = itrim(strtrim(raw_readable_name))
    replace raw_other_text = itrim(strtrim(raw_other_text))

    * Prefer the readable label, then "other" text, and only fabricate a label for special missing codes.
    gen str120 slot_display_name = raw_readable_name
    replace slot_display_name = raw_other_text if slot_display_name == "" & raw_other_text != ""
    replace slot_display_name = "[missing label]" if slot_display_name == "" & inlist(raw_product_code, "-88", "-99")

	// reformat slot label
    gen str120 normalized_slot_name = lower(itrim(strtrim(slot_display_name)))

    ********************************************************************
    * 4. Build canonical product mappings from valid observed code-name pairs
    ********************************************************************

    tempfile long_slots canonical_by_code canonical_by_name
    save `long_slots'

	// generate canonical names, using the most common names
    * Use only non-missing, non-special product codes when defining canonical names.
    keep if raw_product_code != ""
    keep if !inlist(raw_product_code, "-77", "-88", "-99")
    collapse (count) code_name_obs = original_firm_id, ///
        by(raw_product_code normalized_slot_name slot_display_name)
    bysort raw_product_code: egen max_code_name_obs = max(code_name_obs)
    keep if code_name_obs == max_code_name_obs
	// break ties by alphabetical order
    bysort raw_product_code (normalized_slot_name slot_display_name): keep if _n == 1
    rename slot_display_name canonical_name
    rename normalized_slot_name canonical_name_norm
    gen str20 canonical_code = raw_product_code
    keep raw_product_code canonical_code canonical_name canonical_name_norm
    save `canonical_by_code'

	// check if each canonical name matches to one code
    use `canonical_by_code', clear
    bysort canonical_name_norm: gen canonical_name_count = _N
    keep if canonical_name_count == 1
    rename canonical_name_norm normalized_slot_name
    rename canonical_code matched_code
    rename canonical_name matched_name
    keep normalized_slot_name matched_code matched_name
    save `canonical_by_name'

    ********************************************************************
    * 5. Apply slot-level harmonization and return to wide firm form
    ********************************************************************

    use `long_slots', clear
    merge m:1 raw_product_code using `canonical_by_code', nogen keep(master match)
    merge m:1 normalized_slot_name using `canonical_by_name', nogen keep(master match)

    * Track whether each slot keeps its own code, maps a -77 entry, or remains unresolved.
    gen str24 harmonization_status = "missing_code"
    replace harmonization_status = "kept_original" if raw_product_code != "" & ///
        !inlist(raw_product_code, "-77", "-88", "-99")
    replace harmonization_status = "mapped_from_-77" if raw_product_code == "-77" & matched_code != ""
    replace harmonization_status = "unresolved_-77" if raw_product_code == "-77" & matched_code == ""
    replace harmonization_status = "special_missing_code" if inlist(raw_product_code, "-88", "-99")

    gen str20 harmonized_product_code = ""
    gen str120 harmonized_product_name = ""

    * Keep valid codes as-is, infer replacements for -77 when names uniquely identify a code,
    * and carry special missing codes through unchanged.
    replace harmonized_product_code = raw_product_code if harmonization_status == "kept_original"
    replace harmonized_product_name = canonical_name if harmonization_status == "kept_original" & ///
        canonical_name != ""
    replace harmonized_product_name = slot_display_name if harmonization_status == "kept_original" & ///
        harmonized_product_name == ""

    replace harmonized_product_code = matched_code if harmonization_status == "mapped_from_-77"
    replace harmonized_product_name = matched_name if harmonization_status == "mapped_from_-77"

    replace harmonized_product_code = raw_product_code if harmonization_status == "unresolved_-77"
    replace harmonized_product_name = slot_display_name if harmonization_status == "unresolved_-77"

    replace harmonized_product_code = raw_product_code if harmonization_status == "special_missing_code"
    replace harmonized_product_name = slot_display_name if harmonization_status == "special_missing_code"

    keep original_firm_id product_slot raw_product_code raw_readable_name raw_other_text ///
        slot_display_name normalized_slot_name harmonized_product_code harmonized_product_name ///
        harmonization_status

    reshape wide raw_product_code raw_readable_name raw_other_text ///
        slot_display_name normalized_slot_name harmonized_product_code harmonized_product_name ///
        harmonization_status, i(original_firm_id) j(product_slot)

    * Rename reshaped fields so the final dataset keeps explicit slot suffixes.
    rename (raw_product_code1 raw_product_code2 raw_product_code3) ///
        (raw_product_code_slot1 raw_product_code_slot2 raw_product_code_slot3)
    rename (raw_readable_name1 raw_readable_name2 raw_readable_name3) ///
        (raw_readable_name_slot1 raw_readable_name_slot2 raw_readable_name_slot3)
    rename (raw_other_text1 raw_other_text2 raw_other_text3) ///
        (raw_other_text_slot1 raw_other_text_slot2 raw_other_text_slot3)
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

use `slot_harmonized', clear

********************************************************************
* 6. Collapse harmonized slots to unique goods bundle counts
********************************************************************

use `base_wide', clear
merge 1:1 original_firm_id using `slot_harmonized', nogen assert(match)

gen str20 unique_good_code1 = ""
gen str20 unique_good_code2 = ""
gen str20 unique_good_code3 = ""
gen str120 unique_good_name1 = ""
gen str120 unique_good_name2 = ""
gen str120 unique_good_name3 = ""

* Remove repeated raw slots so each firm contributes at most three distinct harmonized goods.
forvalues s = 1/3 {
    local code harmonized_product_code_slot`s'
    local name harmonized_product_name_slot`s'
    replace unique_good_code1 = `code' if unique_good_code1 == "" & ///
        !inlist(`code', "", "-88", "-99")
    replace unique_good_name1 = `name' if unique_good_name1 == "" & ///
        !inlist(`code', "", "-88", "-99")

    replace unique_good_code2 = `code' if unique_good_code1 != "" & unique_good_code2 == "" ///
        & !inlist(`code', "", "-88", "-99") & `code' != unique_good_code1
    replace unique_good_name2 = `name' if unique_good_code1 != "" & unique_good_code2 == `code' ///
        & unique_good_name2 == ""

    replace unique_good_code3 = `code' if unique_good_code2 != "" & unique_good_code3 == "" ///
        & !inlist(`code', "", "-88", "-99") & `code' != unique_good_code1 & `code' != unique_good_code2
    replace unique_good_name3 = `name' if unique_good_code2 != "" & unique_good_code3 == `code' ///
        & unique_good_name3 == ""
}

gen byte n_unique_goods = (unique_good_code1 != "") + ///
    (unique_good_code2 != "") + ///
    (unique_good_code3 != "")

* Concatenate only populated distinct goods so bundle strings do not carry trailing separators.
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

* Count how many firms share each exact harmonized bundle before anchor-based pooling.
// note that the same product bundle but with different ordering are considered as different bundles. 
preserve
    keep original_firm_id harmonized_bundle_code
    keep if harmonized_bundle_code != ""
    duplicates drop
    bysort harmonized_bundle_code: gen long bundle_firm_n = _N
    keep harmonized_bundle_code bundle_firm_n
    duplicates drop
    save `bundle_counts'
restore

********************************************************************
* 7. Expand firms across anchor codes and assign pooled categories
********************************************************************

* Split multi-code enterprise categories so one firm can contribute weight across anchors.
// Anchors are obtained by splitting the original enterprise-category field (s1_ent_cat)
split s1_ent_cat, parse(" ") gen(anchor_raw_)
gen int n_anchor_codes = wordcount(s1_ent_cat)
replace n_anchor_codes = 1 if missing(n_anchor_codes) | n_anchor_codes == 0

reshape long anchor_raw_, i(original_firm_id) j(anchor_index)
rename anchor_raw_ anchor_code

* Keep exactly the intended number of anchor rows so single-anchor firms do not gain spurious missing rows.
drop if anchor_index > n_anchor_codes

replace anchor_code = "missing_anchor" if anchor_code == "" | missing(anchor_code)

* Divide the firm survey weight equally across its reported anchor codes.
gen double survey_weight_anchor = weight_adj / n_anchor_codes
gen double survey_weight_raw_firm = weight_adj

merge m:1 anchor_code using `anchor_lookup', nogen keep(master match)
gen str120 anchor_display = anchor_name
replace anchor_display = anchor_code if anchor_display == ""

merge m:1 harmonized_bundle_code using `bundle_counts', nogen
replace bundle_firm_n = 0 if missing(bundle_firm_n)

* Track support for the fallback grouping based on primary good crossed with anchor.
bysort primary_harmonized_good_code anchor_code: egen long primary_good_anchor_n = ///
    count(original_firm_id) if primary_harmonized_good_code != ""

gen str24 category_assignment_tier = ""
gen str120 enterprise_category_key = ""

* Prefer exact bundles when common enough (20 enterprises), then pool to primary-good-by-anchor, and finally anchor only.
replace category_assignment_tier = "exact_bundle" if harmonized_bundle_code != "" & bundle_firm_n >= 20
replace enterprise_category_key = "bundle:" + harmonized_bundle_code if category_assignment_tier == "exact_bundle"

// if the bundle doesn't make it, but the primary good does have more than 20 enterprises
replace category_assignment_tier = "primary_good_anchor" if category_assignment_tier == "" ///
    & primary_harmonized_good_code != "" & primary_good_anchor_n >= 20
replace enterprise_category_key = "good:" + primary_harmonized_good_code + "|anchor:" + anchor_code ///
    if category_assignment_tier == "primary_good_anchor"

replace category_assignment_tier = "anchor_only" if category_assignment_tier == ""
replace enterprise_category_key = "anchor:" + anchor_code if category_assignment_tier == "anchor_only"

egen long enterprise_category_id = group(enterprise_category_key)
gen str244 enterprise_category_label = harmonized_bundle_name if category_assignment_tier == "exact_bundle"
replace enterprise_category_label = primary_harmonized_good_name + " x anchor " + anchor_display ///
    if category_assignment_tier == "primary_good_anchor"
replace enterprise_category_label = "anchor " + anchor_display if category_assignment_tier == "anchor_only"
drop anchor_name anchor_display

gen byte category_is_native = category_assignment_tier == "exact_bundle"
gen byte category_is_pooled = category_is_native == 0
gen byte harmonized_repeat_in_raw = ///
    (harmonized_product_code_slot1 != "" & harmonized_product_code_slot1 == harmonized_product_code_slot2) | ///
    (harmonized_product_code_slot1 != "" & harmonized_product_code_slot1 == harmonized_product_code_slot3) | ///
    (harmonized_product_code_slot2 != "" & harmonized_product_code_slot2 == harmonized_product_code_slot3)

********************************************************************
* 8. Order final variables and write the cleaned output
********************************************************************

order original_firm_id survey_entid survey_key survey_source ///
    weight_raw weight_adj survey_weight_raw_firm survey_weight_anchor ///
    sample_strata strata_ms psu s1_market s1_ent_cat n_anchor_codes anchor_index anchor_code ///
    s7_prod1_productname s7_commonproduct1 s7_prod1_productname_oth ///
    s7_prod2_productname s7_commonproduct2 s7_prod2_productname_oth ///
    s7_prod3_productname s7_commonproduct3 s7_prod3_productname_oth ///
    raw_product_code_slot1 raw_readable_name_slot1 raw_other_text_slot1 slot_display_name1 normalized_slot_name1 ///
    harmonized_product_code_slot1 harmonized_product_name_slot1 harmonization_status_slot1 ///
    raw_product_code_slot2 raw_readable_name_slot2 raw_other_text_slot2 slot_display_name2 normalized_slot_name2 ///
    harmonized_product_code_slot2 harmonized_product_name_slot2 harmonization_status_slot2 ///
    raw_product_code_slot3 raw_readable_name_slot3 raw_other_text_slot3 slot_display_name3 normalized_slot_name3 ///
    harmonized_product_code_slot3 harmonized_product_name_slot3 harmonization_status_slot3 ///
    harmonized_repeat_in_raw ///
    unique_good_code1 unique_good_name1 unique_good_code2 unique_good_name2 unique_good_code3 unique_good_name3 ///
    n_unique_goods primary_harmonized_good_code primary_harmonized_good_name ///
    harmonized_bundle_code harmonized_bundle_name bundle_firm_n primary_good_anchor_n ///
    category_assignment_tier enterprise_category_id enterprise_category_key enterprise_category_label ///
    category_is_native category_is_pooled

compress
save "`OUTPUT'", replace

di as text "06_enterprise_reclassify.do completed successfully."
di as text "Wrote cleaned product-sector dataset: `OUTPUT'"
