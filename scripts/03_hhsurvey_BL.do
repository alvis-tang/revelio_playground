clear all
set more off

******************* Baseline household survey Phase 1 *******************

clear all 

// household survey has 7822 variables
set maxvar 32767
	  
use "$DATA/Phase 1 household baseline/hh_baseline_data.dta", replace

label define yesno 0 "No" 1 "Yes"

foreach v of varlist s3_hh_head s4_land_rented_out s4_owns_bed_frame s4_owns_mattress s4_owns_blankets s4_owns_wardrobe s4_owns_table s4_owns_chair s4_owns_sofa s4_owns_cabinet s4_owns_stove s4_owns_grain_mill s4_owns_kitchen_equip s4_owns_utensils s4_owns_iron s4_owns_refrigerator s4_owns_lantern s4_owns_lamp_torch s4_owns_clock_watch s4_owns_television s4_owns_radio s4_owns_smartphone s4_owns_mobile_phone s4_owns_computer_tablet s4_owns_generator s4_owns_car_battery s4_owns_solar s4_owns_bicycle s4_owns_motor_vehicle s4_owns_gold s4_owns_silver s4_owns_water_tank s4_owns_mortar_pestle s4_owns_hand_tools s4_owns_plows s4_owns_livestock_tools s4_owns_water_pump s4_owns_wheelbarrow s4_owns_cart s4_owns_sewing_machine s4_own_other_assets_yn s4_bank_account s4_mobile_account s4_group_savings s4_loan_bank s4_loan_mlend s4_trans_sent_received s4_trans_rec_oth  s4_trans_sent s4_trans_sent_oth s5_nonfe_other s5_goods_availab s5_livestock_past s6_livestock_own_1 s6_livestock_own_2 s6_livestock_own_3 s6_livestock_own_4 s6_livestock_own_5 s6_livestock_own_6 s6_livestock_own_7 s6_livestock_own_8 s6_livestock_own_9 s6_livestock_own_10 s6_livestock_own_11 s6_livestock_own_12 s6_livestock_own_13 s6_livestock_own_14 s6_livestock_own__77 s6_livestock_hm_1 s6_livestock_hm_2 s6_livestock_hm_3 s6_livestock_hm_4 s6_past_agriculture s6_crops_own_1 s6_crops_own_2 s6_crops_own_3 s6_crops_own_4 s6_crops_own_5 s6_crops_own_6 s6_crops_own_7 s6_crops_own_8 s6_crops_own_9 s6_crops_own_10 s6_crops_own_11 s6_crops_own_12 s6_crops_own_13 s6_crops_own_14 s6_crops_own_15 s6_crops_own_16 s6_crops_own_17 s6_crops_own_18 s6_crops_own_19 s6_crops_own_20 s6_crops_own_21 s6_crops_own_22 s6_crops_own_23 s6_crops_own_24 s6_crops_own_25 s6_crops_own_26 s6_crops_own_27 s6_crops_own_28 s6_crops_own_29 s6_crops_own_30 s6_crops_own_31 s6_crops_own_32 s6_crops_own_33 s6_crops_own_34 s6_crops_own_35 s6_crops_own_36 s6_crops_own_37 s6_crops_own_38 s6_crops_own_39 s6_crops_own_40 s6_crops_own_41 s6_crops_own_42 s6_crops_own_43 s6_crops_own_44 s6_crops_own_45 s6_crops_own_46 s6_crops_own_47 s6_crops_own_48 s6_crops_own_49 s6_crops_own_50 s6_crops_own_51 s6_crops_own_52 s6_crops_own_t5_1 s6_crops_own_t5_2 s6_crops_own_t5_3 s6_crops_own_t5_4 s6_crops_own_t5_5 s6_crops_own_t5_6 s6_crops_own_t5_7 s6_crops_own_t5_8 s6_crops_own_t5_9 s6_crops_own_t5_10 s6_crops_own_t5_11 s6_crops_own_t5_12 s6_crops_own_t5_13 s6_crops_own_t5_14 s6_crops_own_t5_15 s6_crops_own_t5_16 s6_crops_own_t5_17 s6_crops_own_t5_18 s6_crops_own_t5_19 s6_crops_own_t5_20 s6_crops_own_t5_21 s6_crops_own_t5_22 s6_crops_own_t5_23 s6_crops_own_t5_24 s6_crops_own_t5_25 s6_crops_own_t5_26 s6_crops_own_t5_27 s6_crops_own_t5_28 s6_crops_own_t5_29 s6_crops_own_t5_30 s6_crops_own_t5_31 s6_crops_own_t5_32 s6_crops_own_t5_33 s6_crops_own_t5_34 s6_crops_own_t5_35 s6_crops_own_t5_36 s6_crops_own_t5_37 s6_crops_own_t5_38 s6_crops_own_t5_39 s6_crops_own_t5_40 s6_crops_own_t5_41 s6_crops_own_t5_42 s6_crops_own_t5_43 s6_crops_own_t5_44 s6_crops_own_t5_45 s6_crops_own_t5_46 s6_crops_own_t5_47 s6_crops_own_t5_48 s6_crops_own_t5_49 s6_crops_own_t5_50 s6_crops_own_t5_51 s6_crops_own_t5_52 s6_crops_sell_1 s6_crops_sell_2 s6_crops_sell_3 s6_crops_sell_4 s6_crops_sell_5 s7_self_emp s7_stock_inv_own_1 s7_stock_inv_own_2 s7_stock_inv_own_3 s7_stock_inv_own_4 s7_mat_supp_own_1 s7_mat_supp_own_2 s7_mat_supp_own_3 s7_mat_supp_own_4 s7_invest_vhcl_1 s7_invest_vhcl_2 s7_invest_vhcl_3 s7_invest_vhcl_4 s7_invest_tool_1 s7_invest_tool_2 s7_invest_tool_3 s7_invest_tool_4 s8_hh_emp s8a_hh_volunt s8_emp_status_1_1 s8_emp_status_1_2 s8_emp_status_1_3 s8_emp_status_2_1 s8_emp_status_2_2 s8_emp_status_2_3 s8_emp_status_3_1 s8_emp_status_3_2 s8_emp_status_3_3 s8_emp_status_4_1 s8_emp_status_4_2 s8_emp_status_4_3 s8_emp_status_5_1 s8_emp_status_5_2 s8_emp_status_5_3 s8_emp_status_6_1 s8_emp_status_6_2 s8_emp_status_6_3 s11_nonfood_aid_type s11_sctp s11_afford_input s11_cash_aid s12_sym_fever s12_sym_cough s12_sym_tired s12_sym_stomach s12_sym_worms s12_sym_blood_stool s12_sym_weight_loss s12_sym_diarrhea s12_sym_skin_rash s12_sym_sores s12_sym_swalling s12_sym_wound s12_sym_malaria s12_sym_typhoid s12_sym_tuberculosis s12_sym_genitals s12_sym_cholera s12_sym_yellow_fever s12_sym_asthma s12_sym_urination s12_sym_thirst s12_sym_diabetes s12_sym_sti s12_sym_blood_pressure s12_sym_oth s12_major_health_issue_1 s12_major_health_issue_2 s12_major_health_issue_3 s12_major_health_issue_4 s12_major_health_issue_5 s12_major_health_issue_6 s12_major_health_issue_7 s12_major_health_issue_8 s12_major_health_issue_9 s12_major_health_issue_10 s12_major_health_issue_11 s12_major_health_issue_12 s12_major_health_issue_13 s12_major_health_issue_14 s12_major_health_issue_15 s12_major_health_issue_16 s12_major_health_issue_17 s12_major_health_issue_18 s12_major_health_issue_19 s12_major_health_issue_20 s12_major_health_issue_21 s12_major_health_issue_22 s12_major_health_issue_23 s12_major_health_issue_24 s12_major_health_issue_25 s12_major_health_issue_26 s12_major_health_issue_27 s12_major_health_issue_28 s12_major_health_issue__77 s12_major_health_issue__99 s14_personal_bank_acct s14_personal_mob_phone s14_mob_money_acct s14_privacy survey_others_present { 
	recode `v' (2=0)
	label values `v' yesno	
}

egen village_id = group(s1_ta s1_gvh s1_village)

svyset village_id [pweight=survey_hh_weight]

svy: tab s12_exp_healthpbm

gen s4_owns_phone = (s4_owns_smartphone == 1 | s4_owns_mobile_phone == 1)
replace s4_owns_phone = . if missing(s4_owns_smartphone) 

// created a 5-asset index with loosely the same definition as the household census
gen assetidx_5 = s4_owns_bicycle + s4_owns_mattress + s4_owns_phone + s4_owns_radio + s4_owns_solar

// what do households think they'll spend the lottery on?

egen hyplott_sum = rowtotal(s13_share_food s13_share_nonfood s13_share_ag_assets s13_share_oth_assets s13_share_edu s13_share_medical s13_share_bus_start s13_share_bus_invest s13_share_save s13_share_debt s13_share_share s13_share_migrate s13_share_oth)

replace s13_share_oth = 0 if s13_share_oth == .

local oldvars  s13_share_food  s13_share_nonfood  s13_share_ag_assets ///
               s13_share_oth_assets  s13_share_edu  s13_share_medical ///
               s13_share_bus_start  s13_share_bus_invest  s13_share_save ///
               s13_share_debt  s13_share_share  s13_share_migrate  s13_share_oth

local newvars  food nonfood ag_assets ///
               oth_assets edu medical ///
               bus_start bus_invest save ///
               debt share migrate oth

local n : word count `oldvars'

forvalues i = 1/`n' {
    local old : word `i' of `oldvars'
    local new : word `i' of `newvars'
    
    gen hyplott_share_`new' = `old' / hyplott_sum if hyplott_sum > 0
}

svy: mean hyplott_share_*

save "$PROC/p1_hhsur_b1.dta", replace

preserve
// the exchange rate adopted was 1 USD = 1724.138 MWK
gen xchange_rate = s5_tot_consumption/s5_tot_consumption_usd
sum xchange_rate

// the conversion from monthly to annual was 12 months = 1 year

gen month_annual = s5_total_nonfood_annual/s5_total_nonfood_monthly
sum month_annual

// conversion from last 7 days to annual was 52 weeks = 1 year
gen week_annual = s5_food_from_production_annual/s5_food_from_production_7d 
sum week_annual

restore

* Get stubs
ds *_loc
local locvars `r(varlist)'
local stubs
foreach v of local locvars {
    local s = subinstr("`v'","_loc","",.)
    capture confirm variable `s'_spent
    if !_rc local stubs `stubs' `s'
}

* First pass on full data: fill origin village, compute nummkts
foreach s of local stubs {
    replace `s'_ta      = s1_ta      if `s'_loc == 11
    replace `s'_gvh     = s1_gvh     if `s'_loc == 11
    replace `s'_village = s1_village if `s'_loc == 11

    ds `s'_m_*
    local mvars `r(varlist)'
    local mnum
    foreach mv of local mvars {
        if regexm("`mv'","_m_[0-9]+$") local mnum `mnum' `mv'
    }
    egen `s'_nummkts = rowtotal(`mnum')
}

tempfile wide
save `wide'

tempfile long_stubs
local first 1
foreach s of local stubs {
    use `wide', clear
    
    * get numeric market vars only
    ds `s'_m_*
    local mvars `r(varlist)'
    local mnum
    foreach mv of local mvars {
        if regexm("`mv'","_m_[0-9]+$") local mnum `mnum' `mv'
    }
    keep survey_hhid s1_village s1_gvh s1_ta ///
         `s'_spent `s'_loc `s'_nummkts ///
         `s'_village `s'_ta `s'_gvh ///
         `mnum' survey_hh_weight
    
    drop if missing(`s'_spent) | `s'_spent == 0
    drop if missing(`s'_loc)
    
    rename `s'_spent   spent
    rename `s'_loc     loc
    rename `s'_nummkts nummkts
    rename `s'_village dest_village
    rename `s'_ta      dest_ta
    rename `s'_gvh     dest_gvh

    * annualization factor
    local annfactor = 52
    if regexm("`s'", "^s5_nonfe_") local annfactor = 12

    foreach mv of local mnum {
        if regexm("`mv'","_m_([0-9]+)$") {
            local num = regexs(1)
            rename `mv' mkt`num'
        }
    }
    
    gen stub = "`s'"

    * --- Non-market rows ---
    preserve
    keep if loc != 13
    gen dest_id     = dest_village
    replace dest_id = 8888 if loc == 14
    replace dest_id = 9999 if loc == 15
    gen spent_amt   = spent * `annfactor'
    gen spent_amt_w = spent_amt * survey_hh_weight
    drop mkt*
    
    if `first' {
        save `long_stubs', replace
        local first 0
    }
    else {
        append using `long_stubs'
        save `long_stubs', replace
    }
    restore

    * --- Market rows ---
    keep if loc == 13
    quietly count
    if r(N) == 0 continue
    
    reshape long mkt, i(survey_hhid stub) j(mktnum)
    keep if mkt == 1
    
    gen dest_id     = mktnum
    gen spent_amt   = (spent / nummkts) * `annfactor'
    gen spent_amt_w = spent_amt * survey_hh_weight
    drop mkt mktnum dest_village dest_ta dest_gvh
    
    append using `long_stubs'
    save `long_stubs', replace
}

use `long_stubs', clear

order survey_hhid stub loc spent s1_ta s1_gvh s1_village dest_ta dest_gvh dest_village nummkts
sort survey_hhid loc spent s1_ta s1_gvh s1_village dest_ta dest_gvh dest_village nummkts

* destination point type
gen dest_point_type = .
replace dest_point_type = 1 if inlist(loc, 11, 12)  // village
replace dest_point_type = 2 if loc == 13             // market center
replace dest_point_type = 3 if loc == 14             // Blantyre
replace dest_point_type = 4 if loc == 15             // outside Chiradzulu

* destination node id
gen dest_node = dest_village  if dest_point_type == 1
replace dest_node = dest_id   if dest_point_type == 2
replace dest_node = 8888 if dest_point_type == 3
replace dest_node = 9999 if dest_point_type == 4

* origin is always a village
gen origin_node = s1_village
gen origin_point_type = 1

* collapse to village-level network
collapse ///
    (sum) spent_amt          ///  unweighted total spending
    (sum) spent_amt_w        ///  weighted total spending  
    (count) n_hh = spent_amt ///  raw hh count
    , by(s1_ta s1_gvh s1_village dest_ta dest_gvh dest_village ///
         origin_node origin_point_type dest_node dest_point_type stub)

local DATA_DIR   "$DATA/Phase 1 household baseline"
save "`DATA_DIR'/consumption_links.dta", replace 

*-----------------------------
* 0) Household id
*-----------------------------
use "$PROC/p1_hhsur_b1.dta", replace

isid survey_hhid

preserve

*-----------------------------
* 1) Rename s3_mem#m_*  ->  *_m
*    Example: s3_mem3_gender -> gender_3
*-----------------------------
forvalues m = 1/13 {

    * core
    capture confirm variable s3_mem`m'_gender
    if !_rc rename s3_mem`m'_gender gender_`m'

    capture confirm variable s3_mem`m'_age
    if !_rc rename s3_mem`m'_age age_`m'

    capture confirm variable s3_mem`m'_rel_respondent
    if !_rc rename s3_mem`m'_rel_respondent rel_respondent_`m'

    capture confirm variable s3_mem`m'_rel_respondent_oth
    if !_rc rename s3_mem`m'_rel_respondent_oth rel_respondent_oth_`m'

    * education status
    capture confirm variable s3_mem`m'_edu_comp
    if !_rc rename s3_mem`m'_edu_comp edu_comp_`m'

    capture confirm variable s3_mem`m'_edu_enrol
    if !_rc rename s3_mem`m'_edu_enrol edu_enrol_`m'

    capture confirm variable s3_mem`m'_edu_not_enrol
    if !_rc rename s3_mem`m'_edu_not_enrol edu_not_enrol_`m'

    * edu_not_enrol multi-select + special codes
    foreach k in 1 2 3 4 5 6 7 8 9 10 11 12 _77 _88 _99 oth {
        capture confirm variable s3_mem`m'_edu_not_enrol_`k'
        if !_rc rename s3_mem`m'_edu_not_enrol_`k' edu_not_enrol_`k'_`m'
    }

    capture confirm variable s3_mem`m'_edu_type
    if !_rc rename s3_mem`m'_edu_type edu_type_`m'

    capture confirm variable s3_mem`m'_edu_type_oth
    if !_rc rename s3_mem`m'_edu_type_oth edu_type_oth_`m'

    * enrolled course (single + multi-select + special codes)
    capture confirm variable s3_mem`m'_enrolled_course
    if !_rc rename s3_mem`m'_enrolled_course enrolled_course_`m'

    foreach k in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 _77 _88 _99 oth {
        capture confirm variable s3_mem`m'_enrolled_course_`k'
        if !_rc rename s3_mem`m'_enrolled_course_`k' enrolled_course_`k'_`m'
    }

    * schooling + skills
    capture confirm variable s3_mem`m'_schl_days_attend
    if !_rc rename s3_mem`m'_schl_days_attend schl_days_attend_`m'

    capture confirm variable s3_mem`m'_schl_days_miss
    if !_rc rename s3_mem`m'_schl_days_miss schl_days_miss_`m'

    capture confirm variable s3_mem`m'_can_read
    if !_rc rename s3_mem`m'_can_read can_read_`m'

    capture confirm variable s3_mem`m'_can_math
    if !_rc rename s3_mem`m'_can_math can_math_`m'

    * work + health
    capture confirm variable s3_mem`m'_occupation
    if !_rc rename s3_mem`m'_occupation occupation_`m'

    capture confirm variable s3_mem`m'_occupatio_oth
    if !_rc rename s3_mem`m'_occupatio_oth occupation_oth_`m'

    capture confirm variable s3_mem`m'_days_missed_hlth
    if !_rc rename s3_mem`m'_days_missed_hlth days_missed_hlth_`m'
}


local stubs ///
    gender_ age_ rel_respondent_ rel_respondent_oth_ ///
    edu_comp_ edu_enrol_ edu_not_enrol_ ///
    edu_not_enrol_1_ edu_not_enrol_2_ edu_not_enrol_3_ edu_not_enrol_4_ edu_not_enrol_5_ edu_not_enrol_6_ ///
    edu_not_enrol_7_ edu_not_enrol_8_ edu_not_enrol_9_ edu_not_enrol_10_ edu_not_enrol_11_ edu_not_enrol_12_ ///
    edu_not_enrol__77_ edu_not_enrol__88_ edu_not_enrol__99_ edu_not_enrol_oth_ ///
    edu_type_ edu_type_oth_ ///
    enrolled_course_ ///
    enrolled_course_1_ enrolled_course_2_ enrolled_course_3_ enrolled_course_4_ enrolled_course_5_ enrolled_course_6_ ///
    enrolled_course_7_ enrolled_course_8_ enrolled_course_9_ enrolled_course_10_ enrolled_course_11_ enrolled_course_12_ ///
    enrolled_course_13_ enrolled_course_14_ enrolled_course_15_ enrolled_course_16_ enrolled_course_17_ enrolled_course_18_ ///
    enrolled_course_19_ enrolled_course_20_ enrolled_course_21_ enrolled_course_22_ ///
    enrolled_course__77_ enrolled_course__88_ enrolled_course__99_ enrolled_course_oth_ ///
    schl_days_attend_ schl_days_miss_ can_read_ can_math_ ///
    occupation_ occupation_oth_ days_missed_hlth_ 

*------------------------------------------------------------
* 1) STORE VARIABLE LABELS FROM ENTERPRISE 1 (suffix _1)
*    Store in dataset characteristics so they survive reshape
*------------------------------------------------------------
local K = 0
foreach s of local stubs {
    local ++K
    char _dta[stub`K'] "`s'"
    capture confirm variable `s'1
    if !_rc {
        local lbl : variable label `s'1
        char _dta[lbl`K'] "`lbl'"
    }
    else {
        char _dta[lbl`K'] ""
    }
}

*-----------------------------
* 2) Reshape long
*-----------------------------
reshape long `stubs', i(survey_hhid) j(member)

label var member "Household member number (roster)"

*------------------------------------------------------------
* 3) RE-APPLY MEMBER 1 LABELS TO RESHAPED (LONG) VARIABLES
*------------------------------------------------------------
forvalues i = 1/`K' {
    local s   : char _dta[stub`i']
    local lbl : char _dta[lbl`i']
    if "`lbl'" != "" {
        capture label var `s' "`lbl'"
    }
}

restore

*------------------------------------------------------------
* Rename non-ag enterprise variables such that they end with enterprise id
*------------------------------------------------------------
preserve

keep survey_hhid survey_hh_weight s7_*

local enterprises 1 2 3 4
local tools 1 2 3 4 5
local prods 1 2 3

*-----------------------------
* TOOLS: move enterprise to end; keep tool slot as "tool#"
*-----------------------------
foreach e of local enterprises {
    foreach t of local tools {

        * basic tool vars
        capture confirm variable s7_tools_type_`e'_`t'
        if !_rc rename s7_tools_type_`e'_`t' s7_tools_type_tool`t'_`e'

        capture confirm variable s7_tools_rent_`e'_`t'
        if !_rc rename s7_tools_rent_`e'_`t' s7_tools_rent_tool`t'_`e'

        * tool rent categories: 1 2 3 __88 __99
        foreach k in 1 2 3 __88 __99 {
            capture confirm variable s7_tools_rent_`k'_`e'_`t'
            if !_rc rename s7_tools_rent_`k'_`e'_`t' s7_tools_rent_`k'_tool`t'_`e'
        }

        * time-use and in/out
        foreach v in inuse_h inuse_m rentout_h rentout_m rentin_h rentin_m {
            capture confirm variable s7_tools_`v'_`e'_`t'
            if !_rc rename s7_tools_`v'_`e'_`t' s7_tools_`v'_tool`t'_`e'
        }
    }
}

*-----------------------------
* PRODUCTS: move enterprise to end; keep product slot as "prod#"
*-----------------------------
foreach e of local enterprises {
    foreach p of local prods {

        capture confirm variable s7_prod_name_`e'_`p'
        if !_rc rename s7_prod_name_`e'_`p' s7_prod_name_prod`p'_`e'

        foreach v in quant_sold_q quant_sold_u quant_sold_u_oth usold_l7d psold_l7d {
            capture confirm variable s7_`v'_`e'_`p'
            if !_rc rename s7_`v'_`e'_`p' s7_`v'_prod`p'_`e'
        }

        * extra units and round-2 price/cost/profit have trailing _1/_2
        foreach k in 1 2 {
            capture confirm variable s7_extra_units_`e'_`p'_`k'
            if !_rc rename s7_extra_units_`e'_`p'_`k' s7_extra_units_prod`p'_`k'_`e'

            foreach r2 in price cost profit {
                capture confirm variable s7_prod_r2_`r2'_`e'_`p'_`k'
                if !_rc rename s7_prod_r2_`r2'_`e'_`p'_`k' s7_prod_r2_`r2'_prod`p'_`k'_`e'
            }
        }
    }
}

*------------------------------------------------------------
* SAFE swap of positions: _index_e_s -> _index_s_e
*                         _value_e_s -> _value_s_e
* using temp names to avoid collisions
*------------------------------------------------------------

local ents 1 2 3 4
local slots 1 2 3

* PASS 1: move old vars to temporary names
foreach e in `ents' {
    foreach s in `slots' {

        local old "s7_primary_ent_cat_index_`e'_`s'"
        capture confirm variable `old'
        if !_rc {
            local tmp "TMP__index__`e'__`s'"
            capture drop `tmp'
            rename `old' `tmp'
        }

        local old "s7_primary_ent_cat_value_`e'_`s'"
        capture confirm variable `old'
        if !_rc {
            local tmp "TMP__value__`e'__`s'"
            capture drop `tmp'
            rename `old' `tmp'
        }
    }
}

* PASS 2: rename temporary vars to final names
foreach e in `ents' {
    foreach s in `slots' {

        local tmp "TMP__index__`e'__`s'"
        capture confirm variable `tmp'
        if !_rc {
            local new "s7_primary_ent_cat_index_`s'_`e'"
            capture confirm variable `new'
            if _rc rename `tmp' `new'
            else di as error "`new' already exists; not overwriting (tmp=`tmp')"
        }

        local tmp "TMP__value__`e'__`s'"
        capture confirm variable `tmp'
        if !_rc {
            local new "s7_primary_ent_cat_value_`s'_`e'"
            capture confirm variable `new'
            if _rc rename `tmp' `new'
            else di as error "`new' already exists; not overwriting (tmp=`tmp')"
        }
    }
}

local stubs ///
    s7_main_decision_ ///
    s7_primary_sec_cat_ ///
    s7_primary_sec_cat_oth_ ///
    s7_primary_ent_cat_ ///
    s7_primary_ent_cat_1_  s7_primary_ent_cat_2_  s7_primary_ent_cat_3_  s7_primary_ent_cat_4_  s7_primary_ent_cat_5_ ///
    s7_primary_ent_cat_6_  s7_primary_ent_cat_7_  s7_primary_ent_cat_8_  s7_primary_ent_cat_9_  s7_primary_ent_cat_10_ ///
    s7_primary_ent_cat_11_ s7_primary_ent_cat_12_ s7_primary_ent_cat_13_ s7_primary_ent_cat_14_ s7_primary_ent_cat_15_ ///
    s7_primary_ent_cat_16_ s7_primary_ent_cat_17_ s7_primary_ent_cat_18_ s7_primary_ent_cat_19_ s7_primary_ent_cat_20_ ///
    s7_primary_ent_cat_21_ s7_primary_ent_cat_22_ s7_primary_ent_cat_23_ s7_primary_ent_cat_24_ s7_primary_ent_cat_25_ ///
    s7_primary_ent_cat_26_ s7_primary_ent_cat_27_ s7_primary_ent_cat_28_ s7_primary_ent_cat_29_ s7_primary_ent_cat_30_ ///
    s7_primary_ent_cat_31_ s7_primary_ent_cat_32_ s7_primary_ent_cat_33_ s7_primary_ent_cat_34_ ///
    s7_primary_ent_cat__77_ s7_primary_ent_cat__88_ s7_primary_ent_cat__99_ s7_primary_ent_cat_oth_ ///
    s7_ent_location_ ///
    s7_ent_location_1_ s7_ent_location_2_ s7_ent_location_3_ s7_ent_location_4_ s7_ent_location_5_ ///
    s7_ent_location__88_ s7_ent_location__99_ ///
    s7_ent_ta_ ///
    s7_market_ ///
    s7_market__77_ ///
    s7_market_20_ s7_market_21_ s7_market_23_ s7_market_24_ s7_market_25_ s7_market_27_ s7_market_28_ ///
    s7_market_32_ s7_market_33_ s7_market_36_ s7_market_37_ s7_market_38_ s7_market_40_ s7_market_41_ ///
    s7_market_42_ s7_market_49_ s7_market_51_ s7_market_52_ s7_market_55_ s7_market_56_ s7_market_58_ ///
    s7_market_60_ s7_market_61_ s7_market_63_ s7_market_65_ s7_market_66_ s7_market_67_ s7_market_68_ ///
    s7_market_69_ s7_market_70_ s7_market_71_ s7_market_83_ s7_market_84_ ///
    s7_market_oth_ ///
    s7_entrprs_active_ ///
    s7_primary_ent_cat_r_count_ ///
    s7_primary_ent_cat_index_1_ s7_primary_ent_cat_value_1_ ///
    s7_primary_ent_cat_index_2_ s7_primary_ent_cat_value_2_ ///
    s7_primary_ent_cat_index_3_ s7_primary_ent_cat_value_3_ ///
    s7_tools_type_tool1_ s7_tools_type_tool2_ s7_tools_type_tool3_ s7_tools_type_tool4_ s7_tools_type_tool5_ ///
	s7b_providing_info_ ///
    s7_primary_loc_ ///
    s7_primary_loc_oth_ ///
    s7_own_stru_ ///
    s7_vill_hmstd_ ///
    s7_month_oprtnl_ ///
    s7_month_oprtnl_1_  s7_month_oprtnl_2_  s7_month_oprtnl_3_  s7_month_oprtnl_4_  s7_month_oprtnl_5_  s7_month_oprtnl_6_ ///
    s7_month_oprtnl_7_  s7_month_oprtnl_8_  s7_month_oprtnl_9_  s7_month_oprtnl_10_ s7_month_oprtnl_11_ s7_month_oprtnl_12_ ///
    s7_month_oprtnl__88_ s7_month_oprtnl__99_ ///
    s7_days_oprtnl_ ///
    s7_hours_oprtnl_ ///
    s7_hours_oprtnl_cust_ ///
    s7_profits_7d_ ///
    s7_profits_1m_ ///
    s7_shincome_7d_ ///
    s7_shincome_1m_ ///
    s7_earnings_7d_ ///
    s7_earnings_1m_ ///
    s7_best7_rev_ ///
    s7_worst7_rev_ ///
    s7_cust_yd_ ///
    s7_cust_7d_ ///
    s7_max_cap_30d_ ///
    s7_percentage_capacity_ ///
    s7_confirm_pct_capacity_ ///
    s7_th_work_hh_ ///
    s7_th_work_oo_ ///
    s7_emp_num_ ///
    s7_emptotal_hour_ ///
    s7_emptotal_comp_ ///
    s7_empvolun_num_ ///
    s7_empvolun_hour_ ///
    s7_stock_inv_own_ ///
    s7_stock_inv_worth_ ///
    s7_stock_inv_exp_ ///
    s7_mat_supp_own_ ///
    s7_mat_supp_worth_ ///
    s7_mat_supp_exp_ ///
    s7_source_goods_ ///
    s7_source_goods_1_ s7_source_goods_2_ s7_source_goods_3_ ///
    s7_source_goods__88_ s7_source_goods__99_ ///
    s7_invest_spd_30d_ ///
    s7_invest_spd_12m_ ///
    s7_invest_vhcl_ ///
    s7_invest_tool_ ///
    s7_prod_count_ ///
    s7_prod_count_max3_ ///
    s7_prod_count_max3_wr_ ///
    s7_prod_type_ ///
    s7_prod_type_1_  s7_prod_type_2_  s7_prod_type_3_  s7_prod_type_4_  s7_prod_type_5_  s7_prod_type_6_  s7_prod_type_7_ ///
    s7_prod_type_8_  s7_prod_type_9_  s7_prod_type_10_ s7_prod_type_11_ s7_prod_type_12_ s7_prod_type_13_ s7_prod_type_14_ ///
    s7_prod_type__771_ s7_prod_type__772_ s7_prod_type__773_ ///
    s7_prod_type__88_ s7_prod_type__99_ ///
    s7_prod_type_oth1_ s7_prod_type_oth2_ s7_prod_type_oth3_ /// 
    s7_prod_name_prod1_ s7_prod_name_prod2_ s7_prod_name_prod3_

*------------------------------------------------------------
* 1) STORE VARIABLE LABELS FROM ENTERPRISE 1 (suffix _1)
*    Store in dataset characteristics so they survive reshape
*------------------------------------------------------------
local K = 0
foreach s of local stubs {
    local ++K
    char _dta[stub`K'] "`s'"
    capture confirm variable `s'1
    if !_rc {
        local lbl : variable label `s'1
        char _dta[lbl`K'] "`lbl'"
    }
    else {
        char _dta[lbl`K'] ""
    }
}

*------------------------------------------------------------
* 2) RESHAPE
*------------------------------------------------------------
reshape long `stubs', i(survey_hhid) j(business_id)

*------------------------------------------------------------
* 3) RE-APPLY ENTERPRISE 1 LABELS TO RESHAPED (LONG) VARIABLES
*------------------------------------------------------------
forvalues i = 1/`K' {
    local s   : char _dta[stub`i']
    local lbl : char _dta[lbl`i']
    if "`lbl'" != "" {
        capture label var `s' "`lbl'"
    }
}

* Drop the trailing reshape underscore so downstream scripts can use stable business-level names.
foreach s of local stubs {
    local vlong = substr("`s'", 1, length("`s'") - 1)
    capture confirm variable `s'
    if !_rc {
        capture rename `s' `vlong'
    }
}

* Keep only populated household-business rows and save the long-form input for 08_hh_business_reclassify.do.
gen byte hh_business_has_any = 0
foreach v in s7_main_decision s7_primary_sec_cat s7_primary_sec_cat_oth ///
             s7_primary_ent_cat s7_primary_ent_cat_r_count s7_entrprs_active ///
             s7_primary_loc s7_primary_loc_oth s7_prod_count s7_prod_count_max3 ///
             s7_prod_count_max3_wr s7_prod_name_prod1 s7_prod_name_prod2 s7_prod_name_prod3 ///
             s7_primary_ent_cat_index_1 s7_primary_ent_cat_index_2 s7_primary_ent_cat_index_3 ///
             s7_primary_ent_cat_value_1 s7_primary_ent_cat_value_2 s7_primary_ent_cat_value_3 {
    capture confirm string variable `v'
    if !_rc {
        replace hh_business_has_any = 1 if itrim(strtrim(`v')) != ""
    }
    else {
        replace hh_business_has_any = 1 if !missing(`v')
    }
}

ds s7_prod_type_*
foreach v of varlist `r(varlist)' {
    capture confirm numeric variable `v'
    if !_rc {
        replace hh_business_has_any = 1 if !missing(`v') & `v' != 0
    }
}

keep if hh_business_has_any
drop hh_business_has_any

isid survey_hhid business_id
compress
save "$PROC/p1_hhsur_businesses_b1.dta", replace

restore

****************************************************
* SECTION 8: Reshape to MEMBER-long, keep 3 POSITIONS wide
*   Input vars look like:  s8_..._<member>_<pos>
*   Output after reshape:  s8_..._p1  s8_..._p2  s8_..._p3   (per member row)
****************************************************

*------------------------------------------------------------
* A) Rename *_<m>_<j> -> *_p<j>_<m>  (same logic as before)
*------------------------------------------------------------
local members 1 2 3 4 5 6
local pos     1 2 3

foreach m of local members {
    foreach j of local pos {
        capture ds *_`m'_`j'
        if _rc==0 {
            foreach v of varlist `r(varlist)' {
                if regexm("`v'", "_`m'_`j'$") {
                    local base = regexr("`v'", "_`m'_`j'$", "")
                    local newname = "`base'_p`j'_`m'"
                    capture rename `v' `newname'
                }
            }
        }
    }
}

ds s8_empl_location_*
foreach v of varlist `r(varlist)' {

    * new name: replace "_location_" with "_loc_"
    local newname = subinstr("`v'", "_location_", "_loc_", .)

    capture rename `v' `newname'
}

* village_oth: s8_empl_location_village_oth_<m>_<j> -> s8_loc_villoth_p<j>_<m>
forvalues m = 1/6 {
    forvalues j = 1/3 {
        capture confirm variable s8_empl_loc_village_oth_`m'_`j'
        if !_rc rename s8_empl_loc_village_oth_`m'_`j' s8_empl_loc_villoth_p`j'_`m'
    }
}

rename s8_empl_loc_m_mbulumbuzi_*_ s8_empl_loc_m_mbulumbuzi_*
rename s8_empl_loc_m_mbulumbuzi_* s8_empl_loc_m_mbulumbuzi_p1_*
rename s8_empl_loc_m_mbulumbudzi_* s8_empl_loc_m_mbulumbudzi_p1_*


*------------------------------------------------------------
* B) Define stubs explicitly (member suffix comes last)
*    Each stub MUST end in "_" so stub + member = varname.
*------------------------------------------------------------
local stubs ///
    s8_provide_info_ s8_emp_pos_num_ s8_empl_loc_m_mbulumbuzi_p1_ s8_empl_loc_m_mbulumbudzi_p1_ ///
	s8_emp_occup_p1_ s8_emp_occup_p2_ s8_emp_occup_p3_ ///
    s8i_other_occup_p1_ s8i_other_occup_p2_ s8i_other_occup_p3_ ///
    s8_emp_industry_p1_ s8_emp_industry_p2_ s8_emp_industry_p3_ ///
    s8_emp_industry_oth_p1_ s8_emp_industry_oth_p2_ s8_emp_industry_oth_p3_ ///
    s8_empstart_month_p1_ s8_empstart_month_p2_ s8_empstart_month_p3_ ///
    s8a_empstart_year_p1_ s8a_empstart_year_p2_ s8a_empstart_year_p3_ ///
    s8_emp_status_p1_ s8_emp_status_p2_ s8_emp_status_p3_ ///
    s8a_empend_month_p1_ s8a_empend_month_p2_ s8a_empend_month_p3_ ///
    s8b_empend_year_p1_ s8b_empend_year_p2_ s8b_empend_year_p3_ ///
    s8_emp_worpatrn_p1_ s8_emp_worpatrn_p2_ s8_emp_worpatrn_p3_ ///
    s8_emp_worpatrn_oth_p1_ s8_emp_worpatrn_oth_p2_ s8_emp_worpatrn_oth_p3_ ///
    s8_working_hours_l7d_p1_ s8_working_hours_l7d_p2_ s8_working_hours_l7d_p3_ ///
    s8_salary_amount_p1_ s8_salary_amount_p2_ s8_salary_amount_p3_ ///
    s8a_kind_food_p1_ s8a_kind_food_p2_ s8a_kind_food_p3_ ///
    s8b_health_insu_p1_ s8b_health_insu_p2_ s8b_health_insu_p3_ ///
    s8c_housing_p1_ s8c_housing_p2_ s8c_housing_p3_ ///
    s8d_clothing_p1_ s8d_clothing_p2_ s8d_clothing_p3_ ///
    s8e_training_allowance_p1_ s8e_training_allowance_p2_ s8e_training_allowance_p3_ ///
    s8f_other_allowance_p1_ s8f_other_allowance_p2_ s8f_other_allowance_p3_ ///
    ///
    s8_empl_loc_p1_ s8_empl_loc_tam_p1_ s8_empl_loc_m_p1_ s8_empl_loc_m__77_p1_ ///
    s8_empl_loc_oth_p1_ s8_empl_loc_ta_p1_ s8_empl_loc_ta_oth_p1_ ///
    s8_empl_loc_gvh_p1_ s8_empl_loc_gvh_oth_p1_ ///
    s8_empl_loc_village_p1_ s8_empl_loc_villoth_p1_ ///
    ///
    s8_empl_loc_p2_ s8_empl_loc_tam_p2_ s8_empl_loc_m_p2_ s8_empl_loc_m__77_p2_ ///
    s8_empl_loc_oth_p2_ s8_empl_loc_ta_p2_ s8_empl_loc_ta_oth_p2_ ///
    s8_empl_loc_gvh_p2_ s8_empl_loc_gvh_oth_p2_ ///
    s8_empl_loc_village_p2_ s8_empl_loc_villoth_p2_ ///
    ///
    s8_empl_loc_p3_ s8_empl_loc_tam_p3_ s8_empl_loc_m_p3_ s8_empl_loc_m__77_p3_ ///
    s8_empl_loc_oth_p3_ s8_empl_loc_ta_p3_ s8_empl_loc_ta_oth_p3_ ///
    s8_empl_loc_gvh_p3_ s8_empl_loc_gvh_oth_p3_ ///
    s8_empl_loc_village_p3_ s8_empl_loc_villoth_p3_ ///
    ///
    s8_empl_loc_m_84_p1_ s8_empl_loc_m_29_p1_ s8_empl_loc_m_37_p1_ s8_empl_loc_m_65_p1_ ///
    s8_empl_loc_m_25_p1_ s8_empl_loc_m_43_p1_ s8_empl_loc_m_83_p1_ s8_empl_loc_m_33_p1_ ///
    s8_empl_loc_m_36_p1_ s8_empl_loc_m_32_p1_ s8_empl_loc_m_63_p1_ s8_empl_loc_m_20_p1_ ///
    s8_empl_loc_m_21_p1_ s8_empl_loc_m_41_p1_ s8_empl_loc_m_66_p1_ s8_empl_loc_m_71_p1_ ///
    s8_empl_loc_m_26_p1_ s8_empl_loc_m_49_p1_ s8_empl_loc_m_58_p1_ s8_empl_loc_m_57_p1_ ///
    s8_empl_loc_m_69_p1_ s8_empl_loc_m_42_p1_ s8_empl_loc_m_23_p1_ s8_empl_loc_m_52_p1_ ///
    s8_empl_loc_m_61_p1_ s8_empl_loc_m_22_p1_ ///
    ///
    s8_empl_loc_m_84_p2_ s8_empl_loc_m_29_p2_ s8_empl_loc_m_37_p2_ s8_empl_loc_m_65_p2_ ///
    s8_empl_loc_m_25_p2_ s8_empl_loc_m_43_p2_ s8_empl_loc_m_83_p2_ s8_empl_loc_m_33_p2_ ///
    s8_empl_loc_m_36_p2_ s8_empl_loc_m_32_p2_ s8_empl_loc_m_63_p2_ s8_empl_loc_m_20_p2_ ///
    s8_empl_loc_m_21_p2_ s8_empl_loc_m_41_p2_ s8_empl_loc_m_66_p2_ s8_empl_loc_m_71_p2_ ///
    s8_empl_loc_m_26_p2_ s8_empl_loc_m_49_p2_ s8_empl_loc_m_58_p2_ s8_empl_loc_m_57_p2_ ///
    s8_empl_loc_m_69_p2_ s8_empl_loc_m_42_p2_ s8_empl_loc_m_23_p2_ s8_empl_loc_m_52_p2_ ///
    s8_empl_loc_m_61_p2_ s8_empl_loc_m_22_p2_ ///
    ///
    s8_empl_loc_m_84_p3_ s8_empl_loc_m_29_p3_ s8_empl_loc_m_37_p3_ s8_empl_loc_m_65_p3_ ///
    s8_empl_loc_m_25_p3_ s8_empl_loc_m_43_p3_ s8_empl_loc_m_83_p3_ s8_empl_loc_m_33_p3_ ///
    s8_empl_loc_m_36_p3_ s8_empl_loc_m_32_p3_ s8_empl_loc_m_63_p3_ s8_empl_loc_m_20_p3_ ///
    s8_empl_loc_m_21_p3_ s8_empl_loc_m_41_p3_ s8_empl_loc_m_66_p3_ s8_empl_loc_m_71_p3_ ///
    s8_empl_loc_m_26_p3_ s8_empl_loc_m_49_p3_ s8_empl_loc_m_58_p3_ s8_empl_loc_m_57_p3_ ///
    s8_empl_loc_m_69_p3_ s8_empl_loc_m_42_p3_ s8_empl_loc_m_23_p3_ s8_empl_loc_m_52_p3_ ///
    s8_empl_loc_m_61_p3_ s8_empl_loc_m_22_p3_ ///
    ///
    s8_work_month_p1_ ///
    s8_work_month_1_p1_ s8_work_month_2_p1_ s8_work_month_3_p1_ s8_work_month_4_p1_ s8_work_month_5_p1_ s8_work_month_6_p1_ ///
    s8_work_month_7_p1_ s8_work_month_8_p1_ s8_work_month_9_p1_ s8_work_month_10_p1_ s8_work_month_11_p1_ s8_work_month_12_p1_ ///
    s8_work_month__88_p1_ s8_work_month__99_p1_ ///
    ///
    s8_work_month_p2_ ///
    s8_work_month_1_p2_ s8_work_month_2_p2_ s8_work_month_3_p2_ s8_work_month_4_p2_ s8_work_month_5_p2_ s8_work_month_6_p2_ ///
    s8_work_month_7_p2_ s8_work_month_8_p2_ s8_work_month_9_p2_ s8_work_month_10_p2_ s8_work_month_11_p2_ s8_work_month_12_p2_ ///
    s8_work_month__88_p2_ s8_work_month__99_p2_ ///
    ///
    s8_work_month_p3_ ///
    s8_work_month_1_p3_ s8_work_month_2_p3_ s8_work_month_3_p3_ s8_work_month_4_p3_ s8_work_month_5_p3_ s8_work_month_6_p3_ ///
    s8_work_month_7_p3_ s8_work_month_8_p3_ s8_work_month_9_p3_ s8_work_month_10_p3_ s8_work_month_11_p3_ s8_work_month_12_p3_ ///
    s8_work_month__88_p3_ s8_work_month__99_p3_ ///
    ///
    s8_extra_jobs_earn_

*------------------------------------------------------------
* C) Store labels from member 1, reshape, reapply labels
*------------------------------------------------------------
local K = 0
foreach s of local stubs {
    local ++K
    char _dta[stub`K'] "`s'"
    capture confirm variable `s'1
    if !_rc {
        local lbl : variable label `s'1
        char _dta[lbl`K'] "`lbl'"
    }
    else char _dta[lbl`K'] ""
}

reshape long `stubs', i(survey_hhid) j(member)

label var member "Household member number (1-6)"

forvalues i = 1/`K' {
    local s   : char _dta[stub`i']
    local lbl : char _dta[lbl`i']
    local vlong = substr("`s'", 1, length("`s'")-1)
    if "`lbl'" != "" capture label var `vlong' "`lbl'"
}

****************************************************
* S8-only rename: *_p#_  ->  *_#_
* (run when you are already member-long: isid survey_hhid member)
****************************************************
isid survey_hhid member

foreach j in 1 2 3 {

    * only pull S8 vars that end in _p#_
    capture ds s8*_p`j'_
    if _rc==0 {
        foreach v of varlist `r(varlist)' {

            * safety: only rename if it truly ends with _p#_
            if regexm("`v'", "_p`j'_$") {
                local base    = regexr("`v'", "_p`j'_$", "")
                local newname = "`base'_`j'"
                capture rename `v' `newname'
            }
        }
    }
}

*------------------------------------------------------------
* 2) Explicit job-stint stubs (ONLY position variables)
*    Each stub ends with "_" so stub + job = varname
*------------------------------------------------------------
local stubs_job ///
    s8_emp_occup_ ///
    s8i_other_occup_ ///
    s8_emp_industry_ ///
    s8_emp_industry_oth_ ///
    s8_empstart_month_ ///
    s8a_empstart_year_ ///
    s8_emp_status_ ///
    s8a_empend_month_ ///
    s8b_empend_year_ ///
    s8_emp_worpatrn_ ///
    s8_emp_worpatrn_oth_ ///
    s8_working_hours_l7d_ ///
    s8_salary_amount_ ///
    s8a_kind_food_ ///
    s8b_health_insu_ ///
    s8c_housing_ ///
    s8d_clothing_ ///
    s8e_training_allowance_ ///
    s8f_other_allowance_ ///
    ///
    s8_empl_loc_ ///
    s8_empl_loc_tam_ ///
    s8_empl_loc_m_ ///
    s8_empl_loc_m__77_ ///
    s8_empl_loc_oth_ ///
    s8_empl_loc_ta_ ///
    s8_empl_loc_ta_oth_ ///
    s8_empl_loc_gvh_ ///
    s8_empl_loc_gvh_oth_ ///
    s8_empl_loc_village_ ///
    s8_empl_loc_villoth_ s8_empl_loc_m_84_ s8_empl_loc_m_29_ s8_empl_loc_m_37_ s8_empl_loc_m_65_ ///
    s8_empl_loc_m_25_ s8_empl_loc_m_43_ s8_empl_loc_m_83_ s8_empl_loc_m_33_ ///
    s8_empl_loc_m_36_ s8_empl_loc_m_32_ s8_empl_loc_m_63_ s8_empl_loc_m_20_ ///
    s8_empl_loc_m_21_ s8_empl_loc_m_41_ s8_empl_loc_m_66_ s8_empl_loc_m_71_ ///
    s8_empl_loc_m_26_ s8_empl_loc_m_49_ s8_empl_loc_m_58_ s8_empl_loc_m_57_ ///
    s8_empl_loc_m_69_ s8_empl_loc_m_42_ s8_empl_loc_m_23_ s8_empl_loc_m_52_ ///
    s8_empl_loc_m_61_ s8_empl_loc_m_22_ ///
    ///
    s8_work_month_ ///
    s8_work_month_1_ s8_work_month_2_ s8_work_month_3_ s8_work_month_4_ s8_work_month_5_ s8_work_month_6_ ///
    s8_work_month_7_ s8_work_month_8_ s8_work_month_9_ s8_work_month_10_ s8_work_month_11_ s8_work_month_12_ ///
    s8_work_month__88_ s8_work_month__99_

*------------------------------------------------------------
* 3) Store labels from job=1 so they survive reshape
*------------------------------------------------------------
local K = 0
foreach s of local stubs_job {
    local ++K
    char _dta[jstub`K'] "`s'"
    capture confirm variable `s'1
    if !_rc {
        local lbl : variable label `s'1
        char _dta[jlbl`K'] "`lbl'"
    }
    else char _dta[jlbl`K'] ""
}

*------------------------------------------------------------
* 4) Reshape long to job-stint level
*------------------------------------------------------------
reshape long `stubs_job', i(survey_hhid member) j(job)

label var job "Job stint (1-3)"

*------------------------------------------------------------
* 5) Re-apply labels
*------------------------------------------------------------
forvalues i = 1/`K' {
    local s   : char _dta[jstub`i']
    local lbl : char _dta[jlbl`i']
    local vlong = substr("`s'", 1, length("`s'")-1)
    if "`lbl'" != "" capture label var `vlong' "`lbl'"
}
