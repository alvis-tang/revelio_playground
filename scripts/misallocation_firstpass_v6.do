use "$DATA/Egger et al (2022) replication_materials/rawdata/VillageBuffers_TreatmentVars_PUBLIC.dta", replace

/*

* 1) List stubs that carry the YYYYmMM suffix
local stubs ///
    amount_total_KES_ ///
    amount_total_KES_ov_ ///
    amount_total_KES_ownvill_ ///
    n_token_ ///
    n_token_ov_ ///
    n_token_ownvill_

* 2) Wide -> Long on month suffix (e.g., 2014m09)
reshape long `stubs', i(village_code distance) j(survey_mth) string

* 3) Turn "2014m09" into a proper monthly date
gen survey_mth_tm = monthly(survey_mth, "YM")
format survey_mth_tm %tm
drop survey_mth
rename survey_mth_tm survey_mth

* 3b) Remember which distance bins exist (for renaming later)
levelsof distance, local(dlist)

* 4) Long -> Wide on distance (keep panel by village_code × survey_mth)
reshape wide `stubs', i(village_code survey_mth) j(distance)

* 5) Optional: prettier names (add "_d#" to distance-suffixed vars)
foreach s of local stubs {
  foreach d of local dlist {
    capture confirm var `s'`d'
    if !_rc rename `s'`d' `s'_d`d'
  }
}

order village_code survey_mth
isid village_code survey_mth

save "C:\Users\Alvis\Dropbox\replication_materials\replication_materials\rawdata\VillageBuffers_TreatmentVars_villagesurveymth_panel.dta", replace

********************************************************
********************************************************
********************************************************

use GE_ENT_BL_EL_AllCombined.dta, replace

scalar S = 10000
gen fw_BL = round(entweight_BL * S)
gen fw_EL = round(entweight_EL * S)

** histograms

gen log_ENT_SUR_BL_rev_mon = log(ENT_SUR_BL_rev_mon+1) if ENT_SUR_BL_revprof_incons == 0

gen log_ENT_SUR_EL_rev_mon = log(ENT_SUR_EL_rev_mon+1) if ENT_SUR_EL_revprof_incons == 0

gen log_ENT_SUR_EL_rev_year = log(ENT_SUR_EL_rev_year+1) if ENT_SUR_EL_revprof_incons == 0

/*

twoway (histogram log_ENT_SUR_BL_rev_mon [fw=fw_BL], width(0.5) color(black%50)) ///
(histogram log_ENT_SUR_EL_rev_mon [fw=fw_EL], width(0.5) color(green%50)), legend(order(1 "Log Last month's nominal revenues BL" 2 "Log Last month's nominal revenues EL") pos(6) row(2)) scheme(lean2)

graph export revenues_beforeafter.png, replace

twoway (histogram log_ENT_SUR_BL_rev_mon [fw=fw_BL], width(0.5) color(black%50)) ///
(histogram log_ENT_SUR_EL_rev_mon [fw=fw_EL], width(0.5) color(green%50)), by(ownerm_treat, title("By whether owner's village was treated")) legend(order(1 "Log Last month's revenues BL" 2 "Log Last month's revenues EL") pos(6) row(2))  scheme(lean2)

graph export revenues_beforeafter_byownertreat.png, replace

*/

gen size_BL = ENT_SUR_BL_emp_n_tot
replace size_BL = HH_ENT_SUR_BL_emp_n_tot   if missing(size_BL)

gen log_ENT_SUR_BL_prof_mon = log(ENT_SUR_BL_prof_mon+1) if ENT_SUR_BL_revprof_incons == 0

gen log_ENT_SUR_EL_prof_mon = log(ENT_SUR_EL_prof_mon+1) if ENT_SUR_EL_revprof_incons == 0
gen log_ENT_SUR_EL_prof_year = log(ENT_SUR_EL_prof_year+1) if ENT_SUR_EL_revprof_incons == 0

/*

twoway (histogram log_ENT_SUR_BL_prof_mon [fw=fw_BL], width(0.25) color(black%50)) ///
(histogram log_ENT_SUR_EL_prof_mon [fw=fw_EL], width(0.25) color(green%50)), legend(order(1 "Log Last month's profits BL" 2 "Log Last month's profits EL") pos(6) row(2)) scheme(lean2)

graph export profits_beforeafter.png, replace

twoway (histogram log_ENT_SUR_BL_prof_mon [fw=fw_BL], width(0.25) color(black%50)) ///
(histogram log_ENT_SUR_EL_prof_mon [fw=fw_EL], width(0.25) color(green%50)), by(ownerm_treat, title("By whether owner's village was treated")) legend(order(1 "Log Last month's profits BL" 2 "Log Last month's profits EL") pos(6) row(2))  scheme(lean2)

graph export profits_beforeafter_byownertreat.png, replace

*/

gen owner_ITT = (ownerm_eligible==1 & ownerm_treat==1)

reg log_ENT_SUR_EL_prof_year c.size_BL##owner_ITT [aw=entweight_EL]
reg log_ENT_SUR_EL_rev_year c.size_BL##owner_ITT [aw=entweight_EL]

reg log_ENT_SUR_EL_prof_year c.ENT_SUR_BL_emp_n_tot##ownerm_treat if ownerm_eligible == 1 [aw=entweight_EL]
reg log_ENT_SUR_EL_rev_year c.ENT_SUR_BL_emp_n_tot##ownerm_treat if ownerm_eligible == 1 [aw=entweight_EL]

**** Imputed numbers ****

** ent_type = 1: non-ag outside household
** ent_type = 2: non-ag within household
** ent_type = 3: farm

use GE_ENT-Analysis_AllENTs.dta, replace

local lbl : value label bizcat
label define `lbl' 61 "New farm enterprise", add
label values bizcat `lbl'

gen log_ent_profit2 = log(ent_profit2+1)
gen log_ent_profit2_wins_PPP = log(ent_profit2_wins_PPP+1)

gen log_ent_revenue2_wins_s_PPP = log(ent_revenue2_wins_s_PPP+1)
gen log_ent_revenue2_wins_s_PPP_BL = log(ent_revenue2_wins_s_PPP_BL+1) 

decode bizcat, gen(bizcat_str)       // turn value-labeled numeric -> string
encode bizcat_str, gen(group_bizcat)

tab group_bizcat bizcat

scalar S = 10000
gen fw_BL = round(entweight_BL * S)
gen fw_EL = round(entweight_EL * S)

twoway (histogram log_ent_revenue2_wins_s_PPP_BL [fw=fw_BL] if Ment_revenue2_BL == 0 & ent_type_BL == 2, width(0.5) color(black%50)) ///
(histogram log_ent_revenue2_wins_s_PPP [fw=fw_EL] if ent_type == 2, width(0.5) color(green%50)), legend(order(1 "Log Last month's revenues BL (PPP, winsorized)" 2 "Log Last month's revenues EL (PPP, winsorized)") title("Non-farm, home-based") pos(6) row(2)) scheme(lean2)

graph export revenues_beforeafter_PPP_nonag_home.png, replace

twoway (histogram log_ent_revenue2_wins_s_PPP_BL [fw=fw_BL] if Ment_revenue2_BL == 0 & ent_type_BL == 1, width(0.5) color(black%50)) ///
(histogram log_ent_revenue2_wins_s_PPP [fw=fw_EL] if ent_type == 1, width(0.5) color(green%50)), legend(order(1 "Log Last month's revenues BL (PPP, winsorized)" 2 "Log Last month's revenues EL (PPP, winsorized)") title("Non-farm, outside home") pos(6) row(2)) scheme(lean2)

graph export revenues_beforeafter_PPP_nonag_outside.png, replace

twoway (histogram log_ent_revenue2_wins_s_PPP_BL [fw=fw_BL] if Ment_revenue2_BL == 0 & ent_type_BL == 3, width(0.5) color(black%50)) /// 
(histogram log_ent_revenue2_wins_s_PPP [fw=fw_EL] if ent_type == 3, width(0.5) color(green%50)), legend(order(1 "Log Last month's revenues BL (PPP, winsorized)" 2 "Log Last month's revenues EL (PPP, winsorized)") title("Farms") pos(6) row(2)) scheme(lean2)

graph export revenues_beforeafter_PPP_farms.png, replace

* non-ag operating from outside home
sum log_ent_revenue2_wins_s_PPP_BL [fw=fw_BL] if Ment_revenue2_BL == 0 & ent_type_BL == 1, d

* non-ag operating from homestead
sum log_ent_revenue2_wins_s_PPP [fw=fw_EL] if ent_type == 2, d

* control non-ag operating from homestead
sum log_ent_revenue2_wins_s_PPP [fw=fw_EL] if ent_type == 2 & treat == 0, d
* treated non-ag operating from homestead
sum log_ent_revenue2_wins_s_PPP [fw=fw_EL] if ent_type == 2 & treat == 1, d

* Build a (group_bizcat -> label) map from the current estimation sample
preserve
    keep group_bizcat
    duplicates drop
    decode group_bizcat, gen(lbl)   // readable names
    keep group_bizcat lbl
    tempfile lblmap
    save `lblmap'
restore

/*

foreach y in log_ent_profit2_wins_PPP log_ent_revenue2_wins_s_PPP {

    // ----- outcome-specific labels -----
    local noun = cond("`y'"=="log_ent_profit2_wins_PPP","profits","revenues")
    local base_title "Predicted log `noun' at endline (PPP, winsorized)"
    local xt "log(`noun') (PPP, wins., +1)"

    // ---------- Treat vs Control ----------
    reg `y' ib(first).group_bizcat##i.treat [pw=entweight_EL], vce(cluster village_code)

    margins group_bizcat#treat
    marginsplot, horizontal recast(scatter) recastci(rcap) ///
        plot1opts(msymbol(D) msize(small) mcolor(red))    /// control points
        plot2opts(msymbol(D) msize(small) mcolor(blue))   /// treated points
        ci1opts(lwidth(thick) lcolor(red))                /// control CI
        ci2opts(lwidth(thick) lcolor(blue))               /// treated CI
        ylabel(1(1)35, angle(0) labsize(small) valuelabel) ///
        xtitle("") ///
        legend(order(3 "Control village" 4 "Treated village") pos(6) row(1)) ///
        title("`base_title'") scheme(lean2)

    graph export `y'_treat.png, replace

    // ---------- High- vs Low-saturation (hi_sat) ----------
    reg `y' ib(first).group_bizcat##i.hi_sat [pw=entweight_EL], vce(cluster village_code)

    margins group_bizcat#hi_sat
    marginsplot, horizontal recast(scatter) recastci(rcap) ///
        plot1opts(msymbol(Oh) msize(small) mcolor(black))   /// Low-sat
        plot2opts(msymbol(Sh) msize(small) mcolor(black))   /// High-sat
        ci1opts(lwidth(thick) lcolor(gs8))                  ///
        ci2opts(lwidth(thick) lcolor(gs8) lpattern(dash))   ///
        ylabel(1(1)35, angle(0) labsize(small) valuelabel) ///
        xtitle("") ///
        legend(order(3 "Low-saturation sublocation" 4 "High-saturation sublocation") pos(6) row(2)) ///
        title("`base_title'") scheme(lean2)

    graph export `y'_hisat.png, replace

    // ---------- Triple interaction: Saturation × Treatment ----------
    reg `y' i.group_bizcat##i.hi_sat##i.treat [pw=entweight_EL], vce(cluster village_code)

    margins group_bizcat#hi_sat#treat
    marginsplot, horizontal recast(scatter) recastci(rcap) ///
        plot1opts(msymbol(Oh) msize(small) mcolor(red))    /// low-sat, control
        plot2opts(msymbol(Oh) msize(small) mcolor(blue))   /// low-sat, treated
        plot3opts(msymbol(Sh) msize(small) mcolor(red))    /// high-sat, control
        plot4opts(msymbol(Sh) msize(small) mcolor(blue))   /// high-sat, treated
        ci1opts(lwidth(thick)  lcolor(red)  )              ///
        ci2opts(lwidth(thick)  lcolor(blue) )              ///
        ci3opts(lwidth(thick)  lcolor(red)  lpattern(dash)) ///
        ci4opts(lwidth(thick)  lcolor(blue) lpattern(dash)) ///
        ylabel(1(1)35, angle(0) labsize(small) valuelabel) ///
        xtitle("") ///
        legend( order(5 6 7 8) ///
                label(5 "Low-sat, Control") ///
                label(6 "Low-sat, Treated") ///
                label(7 "High-sat, Control") ///
                label(8 "High-sat, Treated") ///
                pos(6) row(2) ) ///
        title("`base_title'") scheme(lean2)

    graph export `y'_hisat_treat.png, replace
}

**** Imputed numbers ****
use GE_ENT-Analysis_AllENTs.dta, clear

local lbl : value label bizcat
capture label define `lbl' 61 "New farm enterprise", add
label values bizcat `lbl'

gen log_ent_profit2_wins_PPP     = log(ent_profit2_wins_PPP + 1)
gen log_ent_revenue2_wins_s_PPP  = log(ent_revenue2_wins_s_PPP + 1)


* stable categorical with readable labels
decode bizcat, gen(bizcat_str)
encode bizcat_str, gen(group_bizcat)    // carries value labels

foreach y in log_ent_profit2_wins_PPP log_ent_revenue2_wins_s_PPP {

    * outcome-specific text
    local noun = cond("`y'"=="log_ent_profit2_wins_PPP","profits","revenues")
    local xt   "Δ log(`noun') vs control"    // centered at control
    local ttlA "Treatment effect "
    local ttlB "Treatment effect"

    *********** CENTERED: Treat – Control within each industry ***********
    reg `y' i.group_bizcat##i.treat [pw=entweight_EL], vce(cluster village_code)

    * TE_k = dydx(treat) within each group_bizcat (control is 0 by construction)
    margins group_bizcat, dydx(treat)

    marginsplot, horizontal recast(scatter) recastci(rcap) ///
        plotopts(msymbol(D) msize(small) mcolor(blue)) ///
        ciopts(lwidth(thick) lcolor(blue)) ///
        ylabel(1(1)35, valuelabel angle(0) labsize(small)) ///
        xline(0, lpattern(dash) lcolor(gs12)) ///
        xtitle("`xt'") ///
        title("") legend(order(2 "Treated − control")) scheme(lean2)

    graph export `y'_TE_by_industry.png, replace

    *********** CENTERED: Treat – Control within each industry × hi_sat ***********
    reg `y' i.group_bizcat##i.hi_sat##i.treat [pw=entweight_EL], vce(cluster village_code)

    * Two series: low-sat TE and high-sat TE (each is treated − control within that saturation)
    margins group_bizcat, over(hi_sat) dydx(treat)

    * Style: red = low-sat TE, blue = high-sat TE
    marginsplot, horizontal recast(scatter) recastci(rcap) ///
        plot1opts(msymbol(Oh) msize(small) mcolor(red))    /// low-sat TE
        plot2opts(msymbol(Sh) msize(small) mcolor(blue))   /// high-sat TE
        ci1opts(lwidth(thick) lcolor(red)) ///
        ci2opts(lwidth(thick) lcolor(blue)) ///
        ylabel(1(1)35, valuelabel angle(0) labsize(small)) ///
        xline(0, lpattern(dash) lcolor(gs12)) ///
        xtitle("`xt'") ///
        legend(order(3 "Low-saturation TE" 4 "High-saturation TE") pos(6) row(1)) ///
        title("") scheme(lean2)

    graph export `y'_TE_by_industry_hisat.png, replace
}



**** Imputed numbers ****
use GE_ENT-Analysis_AllENTs.dta, clear

replace bizcat_cons = 8 if bizcat_cons == 9

local lbl : value label bizcat_cons
capture label define `lbl' 8 "New farm enterprise", modify
label values bizcat_cons `lbl'

gen log_ent_profit2_wins_PPP     = log(ent_profit2_wins_PPP + 1)
gen log_ent_revenue2_wins_s_PPP  = log(ent_revenue2_wins_s_PPP + 1)

foreach y in log_ent_profit2_wins_PPP log_ent_revenue2_wins_s_PPP {

    * outcome-specific text
    local noun = cond("`y'"=="log_ent_profit2_wins_PPP","profits","revenues")
    local xt   "Δ log(`noun') vs control"    // centered at control
    local ttlA "Treatment effect "
    local ttlB "Treatment effect"

    *********** CENTERED: Treat – Control within each industry ***********
    reg `y' i.bizcat_cons##i.treat [pw=entweight_EL], vce(cluster village_code)

    * TE_k = dydx(treat) within each group_bizcat (control is 0 by construction)
    margins bizcat_cons, dydx(treat)

    marginsplot, horizontal recast(scatter) recastci(rcap) ///
        plotopts(msymbol(D) msize(small) mcolor(blue)) ///
        ciopts(lwidth(thick) lcolor(blue)) ///
        ylabel(1(1)8, valuelabel angle(0) labsize(small)) ///
        xline(0, lpattern(dash) lcolor(gs12)) ///
        xtitle("`xt'") ///
        title("") legend(order(2 "Treated − control")) scheme(lean2)

    graph export `y'_TE_by_sector.png, replace

    *********** CENTERED: Treat – Control within each industry × hi_sat ***********
    reg `y' i.bizcat_cons##i.hi_sat##i.treat [pw=entweight_EL], vce(cluster village_code)

    * Two series: low-sat TE and high-sat TE (each is treated − control within that saturation)
    margins bizcat_cons, over(hi_sat) dydx(treat)

    * Style: red = low-sat TE, blue = high-sat TE
    marginsplot, horizontal recast(scatter) recastci(rcap) ///
        plot1opts(msymbol(Oh) msize(small) mcolor(red))    /// low-sat TE
        plot2opts(msymbol(Sh) msize(small) mcolor(blue))   /// high-sat TE
        ci1opts(lwidth(thick) lcolor(red)) ///
        ci2opts(lwidth(thick) lcolor(blue)) ///
        ylabel(1(1)8, valuelabel angle(0) labsize(small)) ///
        xline(0, lpattern(dash) lcolor(gs12)) ///
        xtitle("`xt'") ///
        legend(order(3 "Low-saturation TE" 4 "High-saturation TE") pos(6) row(1)) ///
        title("") scheme(lean2)

    graph export `y'_TE_by_sector_hisat.png, replace
}

**** Imputed numbers ****
use GE_ENT-Analysis_AllENTs.dta, clear

local lbl : value label bizcat
capture label define `lbl' 61 "New farm enterprise", add
label values bizcat `lbl'

gen log_ent_profit2_wins_PPP     = log(ent_profit2_wins_PPP + 1)
gen log_ent_revenue2_wins_s_PPP  = log(ent_revenue2_wins_s_PPP + 1)

* stable categorical with readable labels
decode bizcat, gen(bizcat_str)
encode bizcat_str, gen(group_bizcat)    // carries value labels

foreach y in log_ent_profit2_wins_PPP log_ent_revenue2_wins_s_PPP {

    * outcome-specific text
    local noun = cond("`y'"=="log_ent_profit2_wins_PPP","profits","revenues")
    local xt   "Δ log(`noun') vs control"    // centered at control
    local ttlA "Treatment effect "
    local ttlB "Treatment effect"

    *********** CENTERED: Treat – Control within each industry × hi_sat ***********
    reg `y' i.group_bizcat##i.ownerm_eligible##i.ownerm_treat [pw=entweight_EL], vce(cluster village_code)
	
	* Two series: low-sat TE and high-sat TE (each is treated − control within that saturation
    margins group_bizcat, over(ownerm_eligible) dydx(ownerm_treat)

    * Style: red = low-sat TE, blue = high-sat TE
    marginsplot, horizontal recast(scatter) recastci(rcap) ///
        plot1opts(msymbol(Oh) msize(small) mcolor(red))    /// low-sat TE
        plot2opts(msymbol(Sh) msize(small) mcolor(blue))   /// high-sat TE
        ci1opts(lwidth(thick) lcolor(red)) ///
        ci2opts(lwidth(thick) lcolor(blue)) ///
        ylabel(1(1)35, valuelabel angle(0) labsize(small)) ///
        xline(0, lpattern(dash) lcolor(gs12)) ///
        xtitle("`xt'") ///
        legend(order(3 "Not eligible" 4 "Eligible") pos(6) row(1)) ///
        title("") scheme(lean2)

    graph export `y'_TE_by_industry_eligible.png, replace
}
	
**** Imputed numbers ****
use GE_ENT-Analysis_AllENTs.dta, clear

replace bizcat_cons = 8 if bizcat_cons == 9

local lbl : value label bizcat_cons
capture label define `lbl' 8 "New farm enterprise", modify
label values bizcat_cons `lbl'

gen log_ent_profit2_wins_PPP     = log(ent_profit2_wins_PPP + 1)
gen log_ent_revenue2_wins_s_PPP  = log(ent_revenue2_wins_s_PPP + 1)

foreach y in log_ent_profit2_wins_PPP log_ent_revenue2_wins_s_PPP {

    * outcome-specific text
    local noun = cond("`y'"=="log_ent_profit2_wins_PPP","profits","revenues")
    local xt   "Δ log(`noun') vs control"    // centered at control
    local ttlA "Treatment effect "
    local ttlB "Treatment effect"

    *********** CENTERED: Treat – Control within each industry × hi_sat ***********
    reg `y' i.bizcat_cons##i.ownerm_eligible##i.ownerm_treat [pw=entweight_EL], vce(cluster village_code)

    * Two series: low-sat TE and high-sat TE (each is treated − control within that saturation
    margins bizcat_cons, over(ownerm_eligible) dydx(ownerm_treat)

    * Style: red = low-sat TE, blue = high-sat TE
    marginsplot, horizontal recast(scatter) recastci(rcap) ///
        plot1opts(msymbol(Oh) msize(small) mcolor(red))    /// low-sat TE
        plot2opts(msymbol(Sh) msize(small) mcolor(blue))   /// high-sat TE
        ci1opts(lwidth(thick) lcolor(red)) ///
        ci2opts(lwidth(thick) lcolor(blue)) ///
        ylabel(1(1)8, valuelabel angle(0) labsize(small)) ///
        xline(0, lpattern(dash) lcolor(gs12)) ///
        xtitle("`xt'") ///
        legend(order(3 "Not eligible" 4 "Eligible") pos(6) row(1)) ///
        title("") scheme(lean2)

    graph export `y'_TE_by_sector_eligible.png, replace
}

******* What about a point estimate

foreach y in log_ent_profit2_wins_PPP log_ent_revenue2_wins_s_PPP {
	reg `y' i.ownerm_eligible##i.ownerm_treat i.bizcat [pw=entweight_EL], vce(cluster village_code)
}


foreach y in log_ent_profit2_wins_PPP log_ent_revenue2_wins_s_PPP {
	reg `y' i.ownerm_eligible##i.ownerm_treat i.bizcat_cons [pw=entweight_EL], vce(cluster village_code)
}

*/

use GE_ENT-Analysis_AllENTs.dta, clear

* make sure it's tagged as a daily date (optional but good hygiene)
gen EL_date = survey_EL_date 
replace EL_date = census_EL_date if census_EL_date != .

* convert to monthly date and show as 2014m2, 2017m3, etc.
gen survey_mth = mofd(EL_date )
format survey_mth %tm
label var survey_mth "Endline Survey month (YYYYm#)"

merge m:1 survey_mth village_code using   "C:\Users\Alvis\Dropbox\replication_materials\replication_materials\analysisdata\intermediate\pricedeflator.dta"

keep if _merge == 3

scalar S = 10000
gen fw_BL = round(entweight_BL * S)
gen fw_EL = round(entweight_EL * S)


* deflate prices
foreach var in wage_h ent_totcost ent_wagebill ent_profit2 ent_rent ent_revenue2 {
	gen `var'_deflate = `var' / deflator
}

/*

* investment (annualized) only asked for non-ag firms, 61.97% of firms have 0 investment last year
tab ent_inv_wins_PPP

tab ent_type if ent_inv_wins_PPP != .

* non-ag operating from homestead
sum inv_year if ent_type == 2
** non-ag operating from outside 
sum inv_year if ent_type == 1

* inventory (annualized) only asked for non-ag firms, 26.91% of firms have <=0 inventory
tab ent_inventory_wins_PPP

tab ent_type if ent_inventory_wins_PPP != .

* wage bill (annualized) asked across all three types of firms. 11.95% of non-ag firms have 0 wage bill

tab ent_wagebill_wins_PPP if ent_type == 1 | ent_type == 2

* rent only asked for non-ag firms. 84.62% of firms have 0 rent bill.

tab ent_rent_wins_PPP ent_type, column

* security fee only asked for non-ag firms. 94.39% of firms have 0 security bill.

tab ent_rent_wins_PPP ent_type, column

* total costs asked for all three types of firms. 9.91% of firms have 0 costs

tab ent_rent_wins_PPP ent_type, column

*gen log_ent_profit2_wins_PPP = log(ent_profit2_wins_PPP+1)
*gen log_ent_revenue2_wins_s_PPP = log(ent_revenue2_wins_s_PPP+1)
*/

tab bizcat_cons

*** Hsieh and Klenow approach for only the non-ag enterprises, outside home (1) or outside of home (2)
** we'll have two factors, labor and non-labor

* 0) set parameters
* capital share of output = 0.33
local alpha = 0.33
* elasticity of substitution between plant value-added
local sigma = 3

egen wage_h_deflate_med = median(wage_h_deflate), by(bizcat_cons ent_type)

* 1) need to value household labor - ent_wagebill doesn't include free labor
** this is still buggy
gen HK_wage_bill = emp_h_tot * wage_h_deflate * (365/7)
replace HK_wage_bill = emp_h_tot * wage_h_deflate_med * (365/7) if HK_wage_bill == .

* 2) we don't have capital bill, so maybe let's use non-labor costs
*gen HK_nonwage_bill = ent_totcost_deflate - ent_wagebill_deflate 
gen HK_nonwage_bill = ent_revenue2_deflate - ent_totcost_deflate - ent_profit2_deflate
replace HK_nonwage_bill = 0 if HK_nonwage_bill < 0

* 3) we need to approximate value-added: profits + wage bill + rent
gen va_ysi = ent_profit2_deflate + HK_wage_bill + ent_rent_deflate

* 4) tau_{Ysi}
gen tau_ysi = 1-(`sigma'/(`sigma'-1)*HK_wage_bill/((1-`alpha')*va_ysi))

* 5) tau_{Ksi}
gen tau_ksi = (`alpha'/(1-`alpha'))*HK_wage_bill/HK_nonwage_bill-1
replace tau_ksi = 0 if tau_ksi == .

* 6) something proportional to TFPR_si
gen shareL_si = HK_wage_bill/va_ysi
gen shareK_si = HK_nonwage_bill/va_ysi
gen TFPR_si = ((1-`alpha')/shareL_si)*(((`alpha'*shareL_si)/((1-`alpha')*shareK_si))^(`alpha'))

quietly summarize TFPR_si if !missing(TFPR_si), detail
local p1  = r(p1)
local p99 = r(p99)

* keep a trimmed copy (set outliers to missing), OR drop them:
gen TFPR_si_trim = TFPR_si
replace TFPR_si_trim = . if TFPR_si_trim < `p1' | TFPR_si_trim > `p99'

* Revenue shares within industry (bizcat_cons)
bys bizcat_cons ent_type : egen Rtot = total(va_ysi) if TFPR_si_trim != .
bys bizcat_cons ent_type: egen wagebilltot = total(HK_wage_bill) if TFPR_si_trim != .
bys bizcat_cons ent_type: egen nonwagebilltot = total(HK_nonwage_bill) if TFPR_si_trim != .

gen TFPR_s_geom = ((Rtot/nonwagebilltot)^(`alpha'))*((Rtot/wagebilltot)^(1-`alpha'))

gen recalib_const = (`alpha'^(`alpha'))*((1-`alpha')^(1-`alpha'))

* Normalized log ratio for Figure-2 style plots: log(TFPR_i / TFPR_s)
gen ln_TFPR_ratio = -ln(recalib_const) + ln(TFPR_si_trim) - ln(TFPR_s_geom)

sum TFPR_si_trim TFPR_s_geom

hist ln_TFPR_ratio, fraction

twoway (kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 1 & treat == 0, width(0.1) color(red%50) lpattern(solid)) /// 
(kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 1 & treat == 1, width(0.1) color(green%50) lpattern(solid)), legend(order(1 "log(TFPR_si/TFPR_s) control" 2 "log(TFPR_si/TFPR_s) treated") title("Non-ag outside") pos(6) row(1)) scheme(lean2) text(0.7 2.2 "Kolmogorov-Smirnov test p-value: 0.006", place(ne) size(small)) ytitle("Density") xscale(range(-1(1)5))

graph export ln_TFPR_ratio_EL_treatcontrol.png, replace

twoway (kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 1 & hi_sat == 0, width(0.1) color(red%50) lpattern(solid)) /// 
(kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 1 & hi_sat == 1, width(0.1) color(green%50) lpattern(solid)), legend(order(1 "log(TFPR_si/TFPR_s) low-saturation" 2 "log(TFPR_si/TFPR_s) high-saturation") title("Non-ag outside") pos(6) row(2)) scheme(lean2)

graph export ln_TFPR_ratio_EL_hilosat.png, replace

/*

twoway (kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 2 & treat == 0, width(0.1) color(black%50)) /// 
(kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 2 & treat == 1, width(0.1) color(green%50)), legend(order(1 "log(TFPR_si/TFPR_s) control" 2 "log(TFPR_si/TFPR_s) treated") title("Non-ag homestead") pos(6) row(2)) scheme(lean2)

twoway (kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 2 & hi_sat == 0, width(0.1) color(black%50)) /// 
(kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 2 & hi_sat == 1, width(0.1) color(green%50)), legend(order(1 "log(TFPR_si/TFPR_s) low-saturation" 2 "log(TFPR_si/TFPR_s) high-saturation") title("Non-ag homestead") pos(6) row(2)) scheme(lean2)

twoway (kdensity ln_TFPR_ratio [fw=fw_EL] if (ent_type == 1 | ent_type == 2) & treat == 0, width(0.1) color(black%50)) /// 
(kdensity ln_TFPR_ratio [fw=fw_EL] if (ent_type == 1 | ent_type == 2) & treat == 1, width(0.1) color(green%50)), legend(order(1 "log(TFPR_si/TFPR_s) control" 2 "log(TFPR_si/TFPR_s) treated") title("Non-ag") pos(6) row(2)) scheme(lean2)

twoway (kdensity ln_TFPR_ratio [fw=fw_EL] if (ent_type == 1 | ent_type == 2) & hi_sat == 0, width(0.1) color(black%50)) /// 
(kdensity ln_TFPR_ratio [fw=fw_EL] if (ent_type == 1 | ent_type == 2) & hi_sat == 1, width(0.1) color(green%50)), legend(order(1 "log(TFPR_si/TFPR_s) low-saturation" 2 "log(TFPR_si/TFPR_s) high-saturation") title("Non-ag") pos(6) row(2)) scheme(lean2)
*/

bys treat: sum ln_TFPR_ratio if ent_type == 1 [aw=entweight_EL]
bys hi_sat: sum ln_TFPR_ratio [aw=entweight_EL]

save TFPR_EL.dta, replace

drop _merge

corr ln_TFPR_ratio ent_revenue2 [aw=entweight_EL]

collapse (sd) ln_TFPR_ratio (mean) treat (sum) fw_EL if ent_type == 1, by(village_code)

gen var_ln_TFPR_ratio_EL = ln_TFPR_ratio^2

twoway (histogram var_ln_TFPR_ratio_EL [fw=fw_EL] if treat == 0, width(0.1) color(red%50)) ///
(histogram var_ln_TFPR_ratio_EL [fw=fw_EL] if treat == 1, width(0.1) color(green%50)), legend(order(1 "Endline var(ln_TFPR_ratio) control" 2 "Endline var(ln_TFPR_ratio) treated") pos(6) row(2)) scheme(lean2) ytitle("Density")

graph export var_ln_TFPR_ratio_EL_treatcontrol.png, replace

save TFPR_var_EL.dta, replace

/*

merge m:1 survey_mth village_code using   "C:\Users\Alvis\Dropbox\replication_materials\replication_materials\rawdata\VillageBuffers_TreatmentVars_villagesurveymth_panel.dta"

reg TFPR_si_trim c.amount_total_KES__d2#ownerm_eligible c.amount_total_KES__d4#ownerm_eligible c.amount_total_KES__d6#ownerm_eligible c.amount_total_KES__d8#ownerm_eligible c.amount_total_KES__d10#ownerm_eligible c.amount_total_KES__d12#ownerm_eligible c.amount_total_KES__d14#ownerm_eligible c.amount_total_KES__d16#ownerm_eligible c.amount_total_KES__d18#ownerm_eligible c.amount_total_KES__d20#ownerm_eligible [aw=entweight_EL], vce(cluster village_code)

*/

********************************************************
********************************************************
********************************************************

use GE_ENT_BL_EL_AllCombined.dta, replace

** Use only endline enterprise survey and endline hh survey for agricultural enterprises **
*keep if ENT_SUR_EL == 1 | HH_AGENT_SUR_EL == 1
ren ENT_SUR_EL_* *

foreach v of var HH_AGENT_SUR_EL_* {
	local name = substr("`v'",17,.)
	disp "`name'"
	capture: replace `name' = `v' if `name' == . & HH_AGENT_EL == 1
	if _rc != 0 {
		gen `name' = `v' if HH_AGENT_EL == 1
	}
}

foreach v of var HH_AGENT_EL_* {
	local name = substr("`v'",13,.)
	disp "`name'"
	capture: replace `name' = `v' if `name' == . & HH_AGENT_EL == 1
	if _rc != 0 {
		gen `name' = `v' if HH_AGENT_EL == 1
	}
}

/*

project, original( "$dr/GE_Treat_Status_Master.dta") preserve
merge m:1 village_code using "$dr/GE_Treat_Status_Master.dta", keepusing(location_code sublocation_code treat hi_sat)
drop if _merge == 2 // those are villages where no enterprises were surveyed
drop _merge
*/

format village_code %15.0f

** Generate primary endline outcomes **
gen operates_from_hh = (operate_from == 1) if operate_from != .
gen operates_outside_hh = 1 if operates_from_hh != 1 & operate_from != .
replace operates_outside_hh = 0 if operates_outside_hh == . & operate_from != .

** generate indicator for farm enterprise **
gen ent_ownfarm = (HH_AGENT_EL == 1)
replace operates_from_hh = 0 if ent_ownfarm == 1
replace operates_outside_hh = 0 if ent_ownfarm == 1

egen ent_type = group(ent_ownfarm operates_from_hh)

** Generate primary endline outcomes **
gen ent_profit1 = prof_mon * 12
replace ent_profit1 = prof_year if ent_profit1 == .
la var ent_profit1 "Profits, annualized"
gen ent_profit2 = prof_mon * 12 if revprof_incons != 1
replace ent_profit2 = prof_year if ent_profit2 == . & revprof_incons != 1
la var ent_profit2 "Profits (drop incons.), annualized"

gen ent_revenue1 = rev_mon * 12
replace ent_revenue1 = rev_year if ent_revenue1 == .
la var ent_revenue1 "Revenue, annualized"
gen ent_revenue2 = rev_mon * 12 if revprof_incons != 1
replace ent_revenue2 = rev_year if ent_revenue2 == . & revprof_incons != 1
la var ent_revenue2 "Revenue (drop incons.), annualized"

gen ent_profitmargin1 = ent_profit1/ent_revenue1
la var ent_profitmargin1 "Profit margin"
gen ent_profitmargin2 = ent_profit2/ent_revenue2
la var ent_profitmargin2 "Profit margin (drop incons.)"

gen ent_totaltaxes = t_county + t_national + t_chiefs + t_other
la var ent_totaltaxes "Total taxes paid last year"

gen ent_wagebill = wage_total * 12
la var ent_wagebill "Total wage bill, annualized"
gen ent_inv = inv_mon * 12
la var ent_inv "Investment, annualized"
gen ent_inventory = inventory
la var ent_inventory "Inventory"
gen ent_rent = c_rent * 12
la var ent_rent "Rent paid, annualized"
gen ent_security = c_security * 12
la var ent_security "Security costs, annualized"

gen ent_totcost = ent_wagebill + ent_rent + ent_security
replace ent_totcost = ent_wagebill + c_total if HH_AGENT_EL == 1
la var ent_totcost "Total costs, annualized"

** Slack variables **
gen ent_cust_perhour = cust_perweek/op_hoursperweek
la var ent_cust_perhour "Customers per hour business is open"

gen ent_rev_perhour = rev_mon/(op_hoursperweek*4)
la var ent_rev_perhour "Revenue per hour business is open"

** Labor market variables **
gen ent_hrs_tot = emp_h_tot
la var ent_hrs_tot "Total labor hours last week"

la var wage_h "Average hourly wage paid by enterprise"

**Generating enterprise sector**
/*
 * Sector 1: Retail
1 "Tea buying centre" 2 "Small retail" 3 "M-Pesa"
6 "Large retail" 9 "Hardware store" 16 "Bookshop"
22 "Food stall / Raw food and fruits vendor" 23 "Chemist"
27 "Petrol station"
31 "Livestock / Animal (Products) / Poultry Sale"
34 "Fish Sale / Mongering" 35 "Cereals" 36 "Agrovet"
39 "Non-Food Vendor"
*/

gen sector = 1 if inlist(bizcat, 1, 2, 3, 6, 9, 16, 22, 23, 27, 31, 34, 35, 36, 39)
replace sector = 1 if inlist(bizcat_nonfood, 2, 9, 12) // mtumba, kerosene and water all most similar to retail

/*
Sector 2: Manufacturing

 17 "Posho mill" 18 "Welding / metalwork" 19 "Carpenter"
 30 "Sale or brewing of homemade alcohol / liquor"
 38 "Jaggery"
 40 "Non-Food Producer"
*/
replace sector = 2 if inlist(bizcat, 17, 18, 19, 30, 38, 40)

/*
Sector 3: Services
4 "Mobile charging" 5 "Bank agent"
7 "Restaurant" 8 "Bar"
10 "Barber shop" 11 "Beauty shop / Salon" 12 "Butcher"
13 "Video Room/Football hall" 14 "Cyber café" 15 "Tailor"
20 "Guesthouse/ Hotel" 21 "Food stand / Prepared food vendor"
24 "Motor Vehicles Mechanic" 25 "Motorcycle Repair / Shop" 26 "Bicycle repair / mechanic shop"  28 "Piki driver" 29 "Boda driver"
32 "Oxen / donkey / tractor plouging" 37 "Photo studio"
 */
replace sector = 3 if inlist(bizcat, 4, 5, 7, 8, 10, 11, 12, 13, 14, 15, 20, 21, 24, 25, 26, 28, 29, 32, 37)
replace sector = 3 if inlist(bizcat_nonfood, 6) & sector == 3 // cobblers to services

/* agriculture -
61 (new farm enterprises), 33 (fishing) (note that there are no fishing enterprises)
*/

replace sector = 4 if inlist(bizcat, 61, 33)

la define sectors 1 "Retail" 2 "Manufacturing" 3 "Services" 4 "Agriculture"
la val sector sectors

gen all = 1
gen ent = 1 if sector == 1
gen manuf = 1 if sector == 2
gen service = 1 if sector == 3
gen agri = 1 if sector == 4


** Generate baseline controls for primary endline outcomes **
*************************************************************

/** NOTE -- THIS IS FOR ENTERPRISES FOR WHICH WE HAVE PANEL INFORMATION.
   VILLAGE-LEVEL AVERAGES ARE MERGED IN BELOW **/

** fix baseline village code **
ren HH_ENT_BL_village_code village_code_BL
replace village_code_BL = HH_AGENT_BL_village_code if HH_AGENT_BL == 1

** Here, we give the baseline survey priority over the baseline census (where we have information for both) **
gen operates_from_hh_BL = (ENT_SUR_BL_operate_from == 1) if ENT_SUR_BL_operate_from != .
replace operates_from_hh_BL = (ENT_CEN_BL_operate_from == 1) if operates_from_hh_BL == . & ENT_CEN_BL_operate_from != .
replace operates_from_hh_BL = (HH_ENT_CEN_BL_operate_from == 1) if operates_from_hh_BL == . & HH_ENT_CEN_BL_operate_from != .
corr operates_from_hh_BL operates_from_hh // there is a positive correlation, but it's not that close to 1.

gen operates_outside_hh_BL = 1 if operates_from_hh_BL != 1 & operates_from_hh_BL != .
replace operates_outside_hh_BL = 0 if operates_outside_hh_BL == . & operates_from_hh_BL != .

** generate indicator for farm enterprise **
gen ent_ownfarm_BL = (HH_AGENT_BL == 1)
replace operates_from_hh_BL = 0 if ent_ownfarm_BL == 1
replace operates_outside_hh_BL = 0 if ent_ownfarm_BL == 1

egen ent_type_BL = group(ent_ownfarm_BL operates_from_hh_BL)

** Baseline sector **
********************
gen bizcat_BL = ENT_SUR_BL_bizcat
replace bizcat_BL = HH_ENT_SUR_BL_bizcat if bizcat_BL == .
replace bizcat_BL = HH_ENT_CEN_BL_bizcat  if bizcat_BL == .
replace bizcat_BL = HH_AGENT_SUR_BL_bizcat if bizcat_BL == .

** Services
gen sector_BL = 1 if inlist(bizcat_BL, 1, 2, 3, 6, 9, 12, 16, 22, 23, 27, 34, 35, 36, 39, 31)

** Manufacturing
replace sector_BL = 2 if inlist(bizcat_BL, 15, 17, 18, 19, 30, 40, 33, 32, 38)

** Services
replace sector_BL = 3 if inlist(bizcat_BL, 4, 5, 7, 8, 10, 11, 13, 14, 20, 21, 24, 25, 26, 28, 29, 37)

** Agriculture **
replace sector_BL = 4 if inlist(bizcat_BL, 61)

** Baseline profits / revenues **
*********************************
gen prof_mon1_BL = ENT_SUR_BL_prof_mon
replace prof_mon1_BL = HH_ENT_SUR_BL_prof_mon if prof_mon1_BL == .
replace prof_mon1_BL = HH_ENT_CEN_BL_prof_mon if prof_mon1_BL == .
gen ent_profit1_BL = prof_mon1_BL * 12
la var ent_profit1_BL "Baseline profits, annualized"

gen prof_mon2_BL = ENT_SUR_BL_prof_mon if ENT_SUR_BL_revprof_incons != 1
replace prof_mon2_BL = HH_ENT_SUR_BL_prof_mon if prof_mon2_BL == . & HH_ENT_SUR_BL_revprof_incons != 1
replace prof_mon2_BL = HH_ENT_CEN_BL_prof_mon if prof_mon2_BL == . & HH_ENT_CEN_BL_revprof_incons != 1
gen ent_profit2_BL = prof_mon2_BL * 12
la var ent_profit2_BL "Baseline profits (drop incons.), annualized"

gen rev_mon1_BL = ENT_SUR_BL_rev_mon
replace rev_mon1_BL = HH_ENT_SUR_BL_rev_mon if rev_mon1_BL == .
replace rev_mon1_BL = HH_ENT_CEN_BL_rev_mon if rev_mon1_BL == .
gen ent_revenue1_BL = rev_mon1_BL * 12
la var ent_revenue1_BL "Baseline revenue, annualized"

gen rev_mon2_BL = ENT_SUR_BL_rev_mon if ENT_SUR_BL_revprof_incons != 1
replace rev_mon2_BL = HH_ENT_SUR_BL_rev_mon if rev_mon2_BL == . & HH_ENT_SUR_BL_revprof_incons != 1
replace rev_mon2_BL = HH_ENT_CEN_BL_rev_mon if rev_mon2_BL == . & HH_ENT_CEN_BL_revprof_incons != 1
gen ent_revenue2_BL = rev_mon2_BL * 12
la var ent_revenue2_BL "Baseline revenue (drop incons.), annualized"

gen ent_profitmargin1_BL = ent_profit1_BL/ent_revenue1_BL
la var ent_profitmargin1_BL "Baseline profit margin"
gen ent_profitmargin2_BL = ent_profit2_BL/ent_revenue2_BL
la var ent_profitmargin2_BL "Baseline profit margin (drop incons.)"

gen ent_totaltaxes_BL = ENT_SUR_BL_t_county + ENT_SUR_BL_t_national + ENT_SUR_BL_t_chiefs + ENT_SUR_BL_t_other
replace ent_totaltaxes_BL = HH_ENT_SUR_BL_t_county + HH_ENT_SUR_BL_t_national + HH_ENT_SUR_BL_t_chiefs + HH_ENT_SUR_BL_t_other if ent_totaltaxes_BL == .
la var ent_totaltaxes_BL "Baseline total taxes paid last year"

gen wage_total_BL = ENT_SUR_BL_wage_total
replace wage_total_BL = HH_ENT_SUR_BL_wage_total if wage_total_BL == .
replace wage_total_BL = HH_AGENT_SUR_BL_wage_total if wage_total_BL == .
gen ent_wagebill_BL = wage_total_BL * 12
la var ent_wagebill_BL "Baseline total wage bill, annualized"

gen c_rent_BL = ENT_SUR_BL_c_rent
replace c_rent_BL = HH_ENT_SUR_BL_c_rent if c_rent_BL == .
gen ent_rent_BL = c_rent_BL * 12
la var ent_rent_BL "Baseline rent paid, annualized"

gen ent_totcost_BL = ent_wagebill_BL + ENT_SUR_BL_c_rent + ENT_SUR_BL_c_security
replace ent_totcost_BL = ent_wagebill_BL + HH_ENT_SUR_BL_c_rent + HH_ENT_SUR_BL_c_utilities + HH_ENT_SUR_BL_c_repairs + HH_ENT_SUR_BL_c_healthinsurance + HH_ENT_SUR_BL_c_vandalism if ent_totcost_BL == .
replace ent_totcost_BL = ent_wagebill_BL + HH_AGENT_SUR_BL_c_total if ent_totcost_BL == .
la var ent_totcost_BL "Baseline total costs, annualized"

*drop ENT_* HH_ENT_* HH_AGENT_*

/*

** Winsorize and PPP **
foreach v of var ent_profit? ent_profitmargin? ent_revenue? ent_totaltaxes ent_wagebill ent_inv ent_inventory ent_rent ent_security ent_totcost wage_h {
	wins_top1 `v', by(ent_type)
	gen `v'_wins_PPP = `v'_wins * $ppprate

	loc vl : var label `v'
	la var `v'_wins "`vl' (wins. top 1%)"
	la var `v'_wins_PPP "`vl' (wins. top 1%, PPP)"
}

** non-PPP outcomes **
foreach v of var ent_cust_perhour op_hoursperday op_hoursperweek {
	wins_top1 `v', by(ent_type)
}

** winsorize for some outcomes by sector **
foreach v of var ent_profit? ent_profitmargin? ent_revenue? ent_totaltaxes ent_wagebill ent_inv ent_inventory ent_rent ent_security ent_totcost wage_h ent_rev_perhour {
	gen `v'_wins_s_PPP = `v' * $ppprate

** looping through sectors **
	forval i = 1 / 4 {
		summ `v'_wins_s_PPP if sector == `i', d
		replace `v'_wins_s_PPP = r(p99) if sector == `i' & `v'_wins_s_PPP > r(p99) & ~mi(`v'_wins_s_PPP)
		local vl : var label `v'
		la var `v'_wins_s_PPP "`vl' (wins by sector)"
	}
}

** non-PPP outcomes **
foreach v of var ent_cust_perhour op_hoursperday op_hoursperweek {
	gen `v'_wins_s = `v'
	forval i = 1 / 4 {
		summ `v' if sector == `i', d
		replace `v'_wins_s = r(p99) if sector == `i' & `v' > r(p99) & ~mi(`v')
		local vl : var label `v'
		la var `v'_wins_s "`vl' (wins by sector)"
	}
}


** take logs for some skewed outcomes **
foreach v of var ent_cust_perhour ent_rev_perhour {
	gen ln_`v' = ln(`v')
	local vl : variable label `v'
	la var ln_`v' "Log `vl'"
}


foreach v of var ent_profit?_BL ent_profitmargin?_BL ent_revenue?_BL ent_totaltaxes_BL ent_wagebill_BL ent_rent_BL ent_totcost_BL {
	wins_top1 `v', by(ent_type)
	gen `v'_wins_PPP = `v'_wins * $ppprate

	loc vl : var label `v'
	la var `v'_wins "`vl' (wins. top 1%)"
	la var `v'_wins_PPP "`vl' (wins. top 1%, PPP)"
}


* also generating versions by sector *
foreach v of var ent_profit?_BL ent_profitmargin?_BL ent_revenue?_BL ent_totaltaxes_BL ent_wagebill_BL ent_rent_BL ent_totcost_BL {
	gen `v'_wins_s_PPP = `v' * $ppprate

	forval i = 1 / 4 {

	summ `v'_wins_s_PPP if sector == `i' , d

	replace `v'_wins_s_PPP = r(p99) if `v'_wins_s_PPP > r(p99) & ~mi(`v'_wins_s_PPP) & sector == `i'
	loc vl : var label `v'
	la var `v'_wins_s_PPP "`vl' (wins. top 1% by sector, PPP)"
}
}


** rename **
foreach v of var *BL_wins* {
	local name = substr("`v'",1,strpos("`v'","_BL")) + substr("`v'",strpos("`v'","_BL") + 4,.) + "_BL"
	disp "`name'"
	rename `v' `name'
}

** Set baseline control to average and add indicator for missing values **
foreach v of var ent_profit?_*BL ent_profitmargin*_BL ent_revenue*_BL ent_totaltaxes_*BL ent_wagebill_*BL ent_rent_*BL ent_totcost_*BL{
	gen M`v' = (`v' == .)
	label var M`v' "`v' missing at BL"

	foreach typ in 1 2 3 {
		sum `v' [weight=entweight_EL] if ent_type == `typ'
		if `r(N)' == 0 {
			** set to overall mean when there is no baseline for any in this category
			summ M`v' if ent_type == `typ'
			assert r(min) == 1 & r(max) == 1
			summ `v' [weight=entweight_EL]
			replace `v' = r(mean) if `v' == . & ent_type == `typ'
		}
		else {
			sum `v' [weight=entweight_EL] if ent_type == `typ'
			replace `v' = r(mean) if `v' == . & ent_type == `typ'
		}
	}
}


**********************************************
** Merge in village-level baseline controls **
**********************************************
project, uses("$da/intermediate/GE_ENT_BL_VillageAvg.dta") preserve

merge m:1 village_code ent_type using "$da/intermediate/GE_ENT_BL_VillageAvg.dta"
list village_code ent_type operates_from_hh if _merge == 1 // those have operates_from_hh missing or are from strange villages
drop if _merge == 1
drop if _merge == 2 // we don't have enteprises of that type from those villages in the survey
drop _merge
** note: there are only 649 villages in the endline census

**************************
*** Add in Census Data ***
**************************
preserve
project, uses("$da/GE_ENT_BL_EL_AllCombined.dta")
use "$da/GE_ENT_BL_EL_AllCombined.dta", clear
*/

** where survey and census disagree, set location equal to survey **
count if ENT_CEN_EL_operate_from != operate_from & operate_from != .
replace ENT_CEN_EL_operate_from = operate_from if ENT_CEN_EL_operate_from != operate_from & operate_from != .

gen n_operates_from_hh = (ENT_CEN_EL_operate_from == 1) if ENT_CEN_EL_operate_from != .
gen n_operates_outside_hh = (ENT_CEN_EL_operate_from != 1) if ENT_CEN_EL_operate_from != .
gen n_ent_ownfarm = (HH_AGENT_EL == 1) * 0.964 // not quite all households have an own-farm enterprise
egen n_allents = rowtotal(n_operates_from_hh n_operates_outside_hh n_ent_ownfarm)

gen n_ent_elig = (ownerm_eligible == 1)
gen n_ent_inelig = (ownerm_eligible == 0)
gen n_ent_treat = (ownerm_eligible == 1 & ownerm_treat == 1)
gen n_ent_eligcontrol = (ownerm_eligible == 1 & ownerm_treat == 0)
gen n_ent_untreat = (ownerm_eligible == 0 | ownerm_treat == 0)

drop operates_from_hh_BL

** baseline numbers **
gen operates_from_hh_BL = (ENT_SUR_BL_operate_from == 1) if ENT_SUR_BL_operate_from != .
replace operates_from_hh_BL = (ENT_CEN_BL_operate_from == 1) if operates_from_hh_BL == . & ENT_CEN_BL_operate_from != .
replace operates_from_hh_BL = (HH_ENT_CEN_BL_operate_from == 1) if operates_from_hh_BL == . & HH_ENT_CEN_BL_operate_from != .
corr operates_from_hh_BL n_operates_from_hh // there is a positive correlation, but it's not that close to 1.

drop operates_outside_hh_BL

gen operates_outside_hh_BL = 1 if operates_from_hh_BL != 1 & operates_from_hh_BL != .
replace operates_outside_hh_BL = 0 if operates_outside_hh_BL == . & operates_from_hh_BL != .

drop ent_ownfarm_BL

** generate indicator for farm enterprise **
gen ent_ownfarm_BL = (HH_AGENT_BL == 1)
replace operates_from_hh_BL = 0 if ent_ownfarm_BL == 1
replace operates_outside_hh_BL = 0 if ent_ownfarm_BL == 1

tab operates_from_hh_BL HH_ENT_BL // WORKS

gen n_operates_from_hh_BL = (operates_from_hh_BL == 1) if operates_from_hh_BL != .
gen n_operates_outside_hh_BL = (operates_from_hh_BL == 0) if HH_ENT_BL == 1 & operates_from_hh_BL != .
gen n_ent_ownfarm_BL = (ent_ownfarm_BL == 1) * 0.964 if ent_ownfarm_BL != . // not quite all households have an own-farm enterprise
egen n_allents_BL = rowtotal(n_operates_from_hh_BL n_operates_outside_hh_BL n_ent_ownfarm_BL)

** fix village code **
list village_code ENT_CEN_EL_village_code if village_code != ENT_CEN_EL_village_code & village_code != . // some enterprises changed villages, adjust
replace ENT_CEN_EL_village_code = village_code if village_code != ENT_CEN_EL_village_code & village_code != .

*** Hsieh and Klenow approach for only the non-ag enterprises, outside home (1) or outside of home (2)
** we'll have two factors, labor and non-labor

* make sure it's tagged as a daily date (optional but good hygiene)
gen BL_date  = ENT_CEN_BL_date
replace BL_date = HH_ENT_CEN_BL_date if HH_ENT_CEN_BL_date != .
replace BL_date = HH_ENT_SUR_BL_date if HH_ENT_SUR_BL_date != .
replace BL_date  = ENT_SUR_BL_date if ENT_SUR_BL_date != .
replace BL_date = HH_AGENT_SUR_BL_date if HH_AGENT_SUR_BL_date != .

* convert to monthly date and show as 2014m2, 2017m3, etc.
gen survey_mth = mofd(BL_date)
format survey_mth %tm
label var survey_mth "Baseline Survey month (YYYYm#)"

rename village_code village_code_EL
rename village_code_BL village_code

merge m:1 survey_mth village_code using   "C:\Users\Alvis\Dropbox\replication_materials\replication_materials\analysisdata\intermediate\pricedeflator.dta"

*keep if _merge == 3
drop _merge

* deflate prices
foreach var in ENT_SUR_BL_wage_h ent_totcost_BL ent_wagebill_BL ent_profit2_BL ent_revenue2_BL ent_rent_BL {
	gen `var'_deflate = `var' / deflator
}

* 0) set parameters
* capital share of output = 0.33
local alpha = 0.33
* elasticity of substitution between plant value-added
local sigma = 3

gen bizcat_cons_BL = . 
replace bizcat_cons_BL = ENT_SUR_BL_bizcat_cons if !missing(ENT_SUR_BL_bizcat_cons) 
replace bizcat_cons_BL = ENT_CEN_BL_bizcat_cons if !missing(ENT_CEN_BL_bizcat_cons) 
replace bizcat_cons_BL = HH_ENT_SUR_BL_bizcat_cons if !missing(HH_ENT_SUR_BL_bizcat_cons) 
replace bizcat_cons_BL = HH_AGENT_SUR_BL_bizcat_cons if !missing(HH_AGENT_SUR_BL_bizcat_cons)
replace bizcat_cons_BL = HH_ENT_CEN_BL_bizcat_cons if !missing(HH_ENT_CEN_BL_bizcat_cons)

*** stylized fact 1: dispersion in firm profits
quietly summarize ent_profit2_BL_deflate if ent_type_BL == 1 & !missing(ent_profit2_BL_deflate), detail
local p1  = r(p1)
local p99 = r(p99)

gen ent_profit2_trim_BL = ent_profit2_BL_deflate
replace ent_profit2_trim_BL = . if ent_profit2_BL_deflate < `p1' | ent_profit2_BL_deflate > `p99'

kdensity ent_profit2_trim_BL if ent_type_BL == 1 [aw=entweight_BL], title("Profits of non-ag enterprises at markets") note("Trimmed at 1% and 99% percentile") scheme(lean2) xtitle("Baseline profits (Kenyan Shillings)")
graph export styfact_profitdispersion_BL.png, replace

local color1 "225 128 126"
local color2 "237 210 131"
local color3 "165 211 149"
local color4 "ebg"
local color5 "0 116 179"
local color6 "97 193 191"
local color7 "191 149 193"
local color8 "108 163 212"

twoway (kdensity ent_profit2_trim_BL if ent_type_BL == 1 & bizcat_cons_BL == 1 [aw=entweight_BL], color("`color1'") lpattern(solid)) /// 
(kdensity ent_profit2_trim_BL if ent_type_BL == 1 & bizcat_cons_BL == 2 [aw=entweight_BL], color("`color2'") lpattern(solid)) ///
(kdensity ent_profit2_trim_BL if ent_type_BL == 1 & bizcat_cons_BL == 3 [aw=entweight_BL], color("`color3'") lpattern(solid)) /// 
(kdensity ent_profit2_trim_BL if ent_type_BL == 1 & bizcat_cons_BL == 4 [aw=entweight_BL], color("`color4'") lpattern(solid)) /// 
(kdensity ent_profit2_trim_BL if ent_type_BL == 1 & bizcat_cons_BL == 5 [aw=entweight_BL], color("`color5'") lpattern(solid)) ///
(kdensity ent_profit2_trim_BL if ent_type_BL == 1 & bizcat_cons_BL == 6 [aw=entweight_BL], color("`color6'") lpattern(solid)) ///
(kdensity ent_profit2_trim_BL if ent_type_BL == 1 & bizcat_cons_BL == 7 [aw=entweight_BL], color("`color7'") lpattern(solid)) /// 
(kdensity ent_profit2_trim_BL if ent_type_BL == 1 & bizcat_cons_BL == 8 [aw=entweight_BL], color("`color8'") lpattern(solid)) ///
, ytitle("Profits of non-ag enterprises at markets") note("Trimmed at 1% and 99% percentile") scheme(lean2) xtitle("Baseline profits (Kenyan Shillings)") legend(order(1 "Food" 2 "Transport" 3 "Food Processing" 4 "Retail" 5 "Personal Services" 6 "Manufacturing" 7 "Hospitality" 8 "Other"))
graph export styfact_profitdispersion_bybroadsector_BL.png, replace

egen wage_h_deflate_med = median(ENT_SUR_BL_wage_h_deflate), by(bizcat_cons_BL ent_type_BL)

* 1) need to value household labor - ent_wagebill doesn't include free labor
gen HK_wage_bill_BL = ENT_SUR_BL_emp_h_tot * ENT_SUR_BL_wage_h_deflate * (365/7)
replace HK_wage_bill_BL = ENT_SUR_BL_emp_h_tot * wage_h_deflate_med * (365/7) if HK_wage_bill_BL == .

* 2) we don't have capital bill, so maybe let's use non-labor costs
*gen HK_nonwage_bill_BL = ent_totcost_BL_deflate - ent_wagebill_BL_deflate 
gen HK_nonwage_bill_BL = ent_revenue2_BL_deflate - ent_totcost_BL_deflate - ent_profit2_BL_deflate 
replace HK_nonwage_bill_BL = 0 if HK_nonwage_bill_BL < 0

* 3) we need to approximate value-added: profits + wage bill + rent
gen va_ysi_BL = ent_profit2_BL_deflate + HK_wage_bill_BL + ent_rent_BL_deflate 

* 4) tau_{Ysi}
gen tau_ysi_BL = 1-(`sigma'/(`sigma'-1)*HK_wage_bill_BL/((1-`alpha')*va_ysi_BL))

* 5) tau_{Ksi}
gen tau_ksi_BL = (`alpha'/(1-`alpha'))*HK_wage_bill_BL/HK_nonwage_bill_BL-1
replace tau_ksi_BL = 0 if tau_ksi_BL == .

* 6) something proportional to TFPR_si
gen shareL_si_BL = HK_wage_bill_BL/va_ysi_BL
gen shareK_si_BL = HK_nonwage_bill_BL/va_ysi_BL
gen TFPR_si_BL = ((1-`alpha')/shareL_si_BL)*(((`alpha'*shareL_si_BL)/((1-`alpha')*shareK_si_BL))^(`alpha'))

quietly summarize TFPR_si_BL if !missing(TFPR_si_BL), detail
local p1  = r(p1)
local p99 = r(p99)

* keep a trimmed copy (set outliers to missing), OR drop them:
gen TFPR_si_trim_BL = TFPR_si_BL
replace TFPR_si_trim_BL = . if TFPR_si_trim_BL < `p1' | TFPR_si_trim_BL > `p99'

* Revenue shares within industry (bizcat_cons)
bys bizcat_cons_BL ent_type_BL : egen Rtot_BL = total(va_ysi_BL) if TFPR_si_trim_BL != .
bys bizcat_cons_BL ent_type_BL : egen wagebilltot_BL = total(HK_wage_bill_BL) if TFPR_si_trim_BL != .
bys bizcat_cons_BL ent_type_BL : egen nonwagebilltot_BL = total(HK_nonwage_bill_BL) if TFPR_si_trim_BL != .

gen TFPR_s_geom = ((Rtot_BL/nonwagebilltot_BL)^(`alpha'))*((Rtot_BL/wagebilltot_BL)^(1-`alpha'))

gen recalib_const = (`alpha'^(`alpha'))*((1-`alpha')^(1-`alpha'))

* Normalized log ratio for Figure-2 style plots: log(TFPR_i / TFPR_s)
gen ln_TFPR_ratio_BL = -ln(recalib_const) + ln(TFPR_si_trim_BL) - ln(TFPR_s_geom)

hist ln_TFPR_ratio_BL, fraction

sum TFPR_si_trim_BL TFPR_s_geom

merge m:1 village_code using "C:\Users\Alvis\Dropbox\replication_materials\replication_materials\rawdata\GE_Treat_Status_Master.dta", keepusing(location_code sublocation_code treat hi_sat)

keep if _merge== 3

scalar S = 10000
gen fw_BL = round(entweight_BL * S)
gen fw_EL = round(entweight_EL * S)

twoway (kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 1 & treat == 0, width(0.1) color(gs8%50) lpattern(-)) /// 
(kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 1 & treat == 1, width(0.1) color(gs8%50) lpattern(longdash)), legend(order(1 "log(TFPR_si/TFPR_s) control" 2 "log(TFPR_si/TFPR_s) treated") pos(6) row(2)) scheme(lean2) ytitle("Density") text(0.7 2.2 "Kolmogorov-Smirnov test p-value: 0.343", place(ne) size(small)) xscale(range(-1(1)5))

graph export ln_TFPR_ratio_BL_treatcontrol.png, replace

twoway (kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 1 & hi_sat == 0, width(0.1) color(gs8%50) lpattern(-)) /// 
(kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 1 & hi_sat == 1, width(0.1) color(gs8%50) lpattern(longdash)), legend(order(1 "log(TFPR_si/TFPR_s) low-saturation" 2 "log(TFPR_si/TFPR_s) high-saturation") title("") pos(6) row(2)) scheme(lean2) ytitle("Density")

graph export ln_TFPR_ratio_BL_hilosat.png, replace

bys treat: sum ln_TFPR_ratio_BL if ent_type_BL == 1 [aw=entweight_BL]
bys hi_sat: sum ln_TFPR_ratio_BL if ent_type_BL == 1 [aw=entweight_BL]

save TFPR_BL.dta, replace

collapse (sd) ln_TFPR_ratio_BL (mean) treat (sum) fw_BL if ent_type_BL == 1, by(village_code)

gen var_ln_TFPR_ratio_BL = ln_TFPR_ratio_BL^2

twoway (histogram var_ln_TFPR_ratio_BL [fw=fw_BL] if treat == 0, width(0.1) color(black%50)) ///
(histogram var_ln_TFPR_ratio_BL [fw=fw_BL] if treat == 1, width(0.1) color(green%50)), legend(order(1 "Baseline SD in ln_TFPR_ratio control" 2 "Baseline SD in ln_TFPR_ratio treated") pos(6) row(2)) scheme(lean2)

graph export var_ln_TFPR_ratio_BL_treatcontrol.png, replace

save TFPR_var_BL.dta, replace

/*

twoway (kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 2 & treat == 0, width(0.1) color(black%50)) /// 
(kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 2 & treat == 1, width(0.1) color(green%50)), legend(order(1 "log(TFPR_si/TFPR_s) control" 2 "log(TFPR_si/TFPR_s) treated") title("Non-ag homestead at baseline") pos(6) row(2)) scheme(lean2)

twoway (kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 2 & hi_sat == 0, width(0.1) color(black%50)) /// 
(kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 2 & hi_sat == 1, width(0.1) color(green%50)), legend(order(1 "log(TFPR_si/TFPR_s) low-saturation" 2 "log(TFPR_si/TFPR_s) high-saturation") title("Non-ag homestead at baseline") pos(6) row(2)) scheme(lean2)

twoway (kdensity ln_TFPR_ratio_BL [fw=fw_BL] if (ent_type_BL == 1 | ent_type_BL == 2) & treat == 0, width(0.1) color(black%50)) /// 
(kdensity ln_TFPR_ratio_BL [fw=fw_BL] if (ent_type_BL == 1 | ent_type_BL == 2) & treat == 1, width(0.1) color(green%50)), legend(order(1 "log(TFPR_si/TFPR_s) control" 2 "log(TFPR_si/TFPR_s) treated") title("Non-ag at baseline") pos(6) row(2)) scheme(lean2)

twoway (kdensity ln_TFPR_ratio_BL [fw=fw_BL] if (ent_type_BL == 1 | ent_type_BL == 2) & hi_sat == 0, width(0.1) color(black%50)) /// 
(kdensity ln_TFPR_ratio [fw=fw_EL] if (ent_type == 1 | ent_type == 2) & hi_sat == 1, width(0.1) color(green%50)), legend(order(1 "log(TFPR_si/TFPR_s) low-saturation" 2 "log(TFPR_si/TFPR_s) high-saturation") title("Non-ag at baseline") pos(6) row(2)) scheme(lean2)
*/

use TFPR_var_BL.dta, replace
merge 1:1 village_code using TFPR_var_EL.dta

gen diff_TFPR_var = var_ln_TFPR_ratio_EL - var_ln_TFPR_ratio_BL

twoway (histogram var_ln_TFPR_ratio_BL [fw=fw_BL], width(0.1) color(black%20)) ///
(histogram var_ln_TFPR_ratio_EL if treat == 0 [fw=fw_EL], width(0.1) color(red%20)) /// 
(histogram var_ln_TFPR_ratio_EL if treat == 1 [fw=fw_EL], width(0.1) color(green%20)), legend(order(1 "Baseline Variance in ln_TFPR_ratio" 2 "Endline Variance in ln_TFPR_ratio control" 3 "Endline Variance in ln_TFPR_ratio treated") pos(6) row(3)) scheme(lean2) ytitle("Density")

twoway (kdensity var_ln_TFPR_ratio_BL [fw=fw_BL], width(0.1) color(black)) ///
(kdensity var_ln_TFPR_ratio_EL if treat == 0 [fw=fw_EL], width(0.1) color(red)) /// 
(kdensity var_ln_TFPR_ratio_EL if treat == 1 [fw=fw_EL], width(0.1) color(green)), legend(order(1 "Baseline Variance in ln_TFPR_ratio" 2 "Endline Variance in ln_TFPR_ratio control" 3 "Endline Variance in ln_TFPR_ratio treated") pos(6) row(3)) scheme(lean2) ytitle("Density")

twoway (kdensity var_ln_TFPR_ratio_BL if treat == 0 [fw=fw_BL], width(0.1) color(black)) ///
(kdensity var_ln_TFPR_ratio_BL if treat == 1 [fw=fw_BL], width(0.1) color(gs8)) ///
(kdensity var_ln_TFPR_ratio_EL if treat == 0 [fw=fw_EL], width(0.1) color(red)) /// 
(kdensity var_ln_TFPR_ratio_EL if treat == 1 [fw=fw_EL], width(0.1) color(green)), legend(order(1 "Baseline Variance in ln_TFPR_ratio control" 2 "Baseline Variance in ln_TFPR_ratio treat" 3 "Endline Variance in ln_TFPR_ratio control" 4 "Endline Variance in ln_TFPR_ratio treated") pos(6) row(2)) scheme(lean2) ytitle("Density")

use TFPR_BL.dta, replace
append using TFPR_EL.dta

twoway (kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 1 & treat == 0, width(0.1) color(gs8%50) lpattern(-)) /// 
(kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 1 & treat == 1, width(0.1) color(gs8%50) lpattern(longdash)) ///
(kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 1 & treat == 0, width(0.1) color(red%50) lpattern(solid)) /// 
(kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 1 & treat == 1, width(0.1) color(green%50) lpattern(solid)) ///
, legend(order(1 "log(TFPR_si/TFPR_s) control baseline" 2 "log(TFPR_si/TFPR_s) treated baseline" 3 "log(TFPR_si/TFPR_s) control endline" 4 "log(TFPR_si/TFPR_s) treated endline") title("") pos(6) row(4)) scheme(lean2) ytitle("Density")

graph export ln_TFPR_ratio_preposttreatcontrol.png, replace

twoway (kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 1 & hi_sat == 0, width(0.1) color(gs8%50) lpattern(-)) /// 
(kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 1 & hi_sat == 1, width(0.1) color(gs8%50) lpattern(longdash)) ///
(kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 1 & hi_sat == 0, width(0.1) color(red%50) lpattern(solid)) /// 
(kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 1 & hi_sat == 1, width(0.1) color(green%50) lpattern(solid)) ///
, legend(order(1 "log(TFPR_si/TFPR_s) low-saturation baseline" 2 "log(TFPR_si/TFPR_s) high-saturation baseline" 3 "log(TFPR_si/TFPR_s) low-saturation endline" 4 "log(TFPR_si/TFPR_s) high-saturation endline") title("") pos(6) row(2)) scheme(lean2) ytitle("Density")

graph export ln_TFPR_ratio_preposthilosat.png, replace

twoway (kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 1 & treat == 0, width(0.1) color(gs8%50) lpattern(-)) /// 
(kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 1 & treat == 0, width(0.1) color(red%50) lpattern(solid)) /// 
, legend(order(1 "log(TFPR_si/TFPR_s) control baseline" 2 "log(TFPR_si/TFPR_s) control endline") title("") pos(6) row(4)) scheme(lean2) ytitle("Density")
graph export ln_TFPR_ratio_prepostcontrol.png, replace

twoway (kdensity ln_TFPR_ratio_BL [fw=fw_BL] if ent_type_BL == 1 & treat == 1, width(0.1) color(gs8%50) lpattern(longdash)) ///
(kdensity ln_TFPR_ratio [fw=fw_EL] if ent_type == 1 & treat == 1, width(0.1) color(green%50) lpattern(solid)) ///
, legend(order(1 "log(TFPR_si/TFPR_s) treated baseline" 2 "log(TFPR_si/TFPR_s) treated endline") title("") pos(6) row(4)) scheme(lean2) ytitle("Density")
graph export ln_TFPR_ratio_preposttreated.png, replace

******* Concentration ******* 

use TFPR_BL.dta, replace
gen BL = 1
*expand entweight_BL
append using TFPR_EL.dta
*expand entweight_EL if BL == .

gen ln_TFPR_ratio_any = ln_TFPR_ratio_BL
replace ln_TFPR_ratio_any = ln_TFPR_ratio if ln_TFPR_ratio_any == .
replace BL = 0 if BL == .

keep if ln_TFPR_ratio_any !=.

gen ent_type_any = ent_type_BL if BL == 1
replace ent_type_any = ent_type if BL == 0

*****************************************************
* ONE BLOCK: robvar + weighted Brown–Forsythe (no stray quotes)
* Fixes your error by storing IF-conditions in separate indexed macros
*****************************************************

* 0) Weight to use when BL/EL are mixed in the same sample
capture drop pw_bywave 
gen double pw_bywave = .
replace pw_bywave = entweight_BL if BL==1
replace pw_bywave = entweight_EL if BL==0

* 1) Program: weighted Brown–Forsythe via regression on |y - median_g|
capture program drop bf_weighted
program define bf_weighted, rclass
    version 16.0
    syntax varname [if], BY(varname) [WTYPE(string) WVAR(name)]
    marksample touse, novarlist
    if ("`wtype'"=="") local wtype "pw"

    tempvar med z
    tempfile meds

    * compute weighted group medians on the analysis sample
    preserve
        keep if `touse'
        quietly collapse (p50) `med' = `varlist' [`wtype'=`wvar'], by(`by')
        quietly save `meds', replace
    restore

    * run the BF regression on abs deviations within the same sample
    preserve
        keep if `touse'
        quietly merge m:1 `by' using `meds', nogen keep(match)
        gen double `z' = abs(`varlist' - `med')
        quietly regress `z' i.`by' [`wtype'=`wvar']
        testparm i.`by'
        di as txt "Brown–Forsythe (weighted):  F = " %9.2f r(F) "   p = " %6.4f r(p)
        return scalar F = r(F)
        return scalar p = r(p)
    restore
end

* 2) Define scenarios WITHOUT embedding quotes inside list elements
*    (each IF condition gets its own macro to avoid parsing issues)
local y1  ln_TFPR_ratio_BL
local by1 treat
local if1 (ent_type_any==1)
local w1  entweight_BL
local lb1 "Control/Treatment @ baseline"

local y2  ln_TFPR_ratio
local by2 treat
local if2 (ent_type_any==1)
local w2  entweight_EL
local lb2 "Control/Treatment @ endline"

local y3  ln_TFPR_ratio_any
local by3 BL
local if3 (ent_type_any==1)
local w3  pw_bywave
local lb3 "Pre/Post (all)"

local y4  ln_TFPR_ratio_any
local by4 BL
local if4 (ent_type_any==1 & treat==0)
local w4  pw_bywave
local lb4 "Control Pre/Post"

local y5  ln_TFPR_ratio_any
local by5 BL
local if5 (ent_type_any==1 & treat==1)
local w5  pw_bywave
local lb5 "Treatment Pre/Post"

* 3) Loop over the 5 scenarios
forvalues i = 1/5 {
    local y  = "`y`i''"
    local by = "`by`i''"
    local ifc = "`if`i''"
    local wv = "`w`i''"
    local lb = "`lb`i''"

    di as res _newline "===================================================="
    di as res "Scenario `i': `lb'"
    robvar `y' if `ifc', by(`by')
    bf_weighted `y' if `ifc', by(`by') wtype(pw) wvar(`wv')
}

* F-value: 0.06, p-value: 0.8098 - control/treatment @ baseline
* F-value: 0.10, p-value: 0.7561 - control/treatment @ endline
* F-value: 2.31, p-value: 0.1285 - pre/post
* F-value: 0.95, p-value: 0.3484 - control pre/post
* F-value: 1.46, p-value: 0.2271 - treatment pre/post

** Kolmogorov-Smirnov test of equality of distribution

use TFPR_BL.dta, replace
gen BL = 1
expand entweight_BL 
append using TFPR_EL.dta
expand entweight_EL  if BL == .

gen ln_TFPR_ratio_any = ln_TFPR_ratio_BL
replace ln_TFPR_ratio_any = ln_TFPR_ratio if ln_TFPR_ratio_any == .
replace BL = 0 if BL == .

keep if ln_TFPR_ratio_any !=.

gen ent_type_any = ent_type_BL if BL == 1
replace ent_type_any = ent_type if BL == 0

* p-value: 0.343
ksmirnov ln_TFPR_ratio_BL if ent_type_any == 1, by(treat) exact

* p-value: 0.006
ksmirnov ln_TFPR_ratio if ent_type_any == 1, by(treat) exact

* p-value: 0.001
ksmirnov ln_TFPR_ratio_any if ent_type_any == 1, by(BL) exact

* p-value: 0.001
ksmirnov ln_TFPR_ratio_any if ent_type_any == 1 & treat == 0, by(BL) exact

* p-value: 0.029
ksmirnov ln_TFPR_ratio_any if ent_type_any == 1 & treat == 1, by(BL) exact

* Sectoral shares

use TFPR_BL.dta, replace

* deflate prices
/*
foreach var in ent_revenue2_BL {
	gen `var'_deflate = `var' / deflator
}
*/

quietly summarize ent_revenue2_BL if !missing(ent_revenue2_BL), detail
local p1  = r(p1)
local p99 = r(p99)

* winsorize
gen ent_revenue2_BL_winsor = ent_revenue2_BL 
replace ent_revenue2_BL_winsor = `p1' if ent_revenue2_BL  < `p1' & !missing(ent_revenue2_BL)
replace ent_revenue2_BL_winsor = `p99' if ent_revenue2_BL > `p99' & !missing(ent_revenue2_BL)

replace emp_n_tot = . if emp_n_tot == -99

gen emp_n_tot_group = .
replace emp_n_tot_group = 0 if emp_n_tot == 0
replace emp_n_tot_group = 1 if emp_n_tot == 1
replace emp_n_tot_group = 2 if emp_n_tot == 2
replace emp_n_tot_group = 3 if emp_n_tot == 3
replace emp_n_tot_group = 4 if emp_n_tot == 4
replace emp_n_tot_group = 5 if emp_n_tot == 5
replace emp_n_tot_group = 6 if emp_n_tot >= 6 & emp_n_tot <= 9
replace emp_n_tot_group = 7 if emp_n_tot >= 10 & !missing(emp_n_tot)

label define emp_n_tot_group 0 "0" 1 "1" 2 "2" 3 "3" 4 "4" 5 "5" 6 "6-9" 7 "10+"
label values emp_n_tot_group emp_n_tot_group 

tab bizcat_cons_BL

* ensure nice labels for the by-panel headers
label define bizcat 1 "Food" 2 "Transport" 3 "Food Processing" 4 "Retail" ///
                    5 "Personal Services" 6 "Manufacturing" 7 "Hospitality" 8 "Other", replace
label values bizcat_cons_BL bizcat
decode bizcat_cons_BL, gen(bizcat_lbl)

local color1 "225 128 126"
local color2 "237 210 131"
local color3 "165 211 149"
local color4 "ebg"
local color5 "0 116 179"
local color6 "97 193 191"
local color7 "191 149 193"
local color8 "108 163 212"

graph pie ent_revenue2_BL_winsor if inrange(bizcat_cons_BL,1,8) & ent_type_BL==1 [fw=fw_BL], ///
    over(emp_n_tot_group) ///
    pie(1,  color("`color1'"))  pie(2,  color("`color2'"))  pie(3,  color("`color3'")) ///
    pie(4,  color("`color4'"))  pie(5,  color("`color5'"))  pie(6,  color("`color6'")) ///
    pie(7,  color("`color7'")) ///
    legend(rows(2)) ///
    by(bizcat_lbl, cols(4) compact title("")) scheme(lean2)
graph export revenueshare_BL.png, replace

use TFPR_EL.dta, replace

/*

* deflate prices
foreach var in ent_revenue2 {
	gen `var'_deflate = `var' / deflator
}
*/

quietly summarize ent_revenue2_deflate if !missing(ent_revenue2_deflate), detail
local p1  = r(p1)
local p99 = r(p99)

* winsorize
gen ent_revenue2_winsor = ent_revenue2_deflate 
replace ent_revenue2_winsor = `p1' if ent_revenue2_deflate < `p1' & !missing(ent_revenue2_deflate)
replace ent_revenue2_winsor = `p99' if ent_revenue2_deflate > `p99' & !missing(ent_revenue2_deflate)

replace emp_n_tot = . if emp_n_tot == -99

gen emp_n_tot_group = .
replace emp_n_tot_group = 0 if emp_n_tot == 0
replace emp_n_tot_group = 1 if emp_n_tot == 1
replace emp_n_tot_group = 2 if emp_n_tot == 2
replace emp_n_tot_group = 3 if emp_n_tot == 3
replace emp_n_tot_group = 4 if emp_n_tot == 4
replace emp_n_tot_group = 5 if emp_n_tot == 5
replace emp_n_tot_group = 6 if emp_n_tot >= 6 & emp_n_tot <= 9
replace emp_n_tot_group = 7 if emp_n_tot >= 10 & !missing(emp_n_tot)

label define emp_n_tot_group 0 "0" 1 "1" 2 "2" 3 "3" 4 "4" 5 "5" 6 "6-9" 7 "10+"
label values emp_n_tot_group emp_n_tot_group 

tab bizcat_cons

local color1 "225 128 126"
local color2 "237 210 131"
local color3 "165 211 149"
local color4 "ebg"
local color5 "0 116 179"
local color6 "97 193 191"
local color7 "191 149 193"
local color8 "108 163 212"

graph pie ent_revenue2_winsor if inrange(bizcat_cons,1,8) & ent_type ==1 [fw=fw_BL], ///
    over(emp_n_tot_group) ///
    pie(1,  color("`color1'"))  pie(2,  color("`color2'"))  pie(3,  color("`color3'")) ///
    pie(4,  color("`color4'"))  pie(5,  color("`color5'"))  pie(6,  color("`color6'")) ///
    pie(7,  color("`color7'")) ///
    legend(rows(2)) ///
    by(bizcat_cons, cols(4) compact title("")) scheme(lean2)
graph export revenueshare_EL.png, replace

****** Changes in concentration ****** 

use TFPR_EL.dta, replace

/*

* deflate prices
foreach var in ent_revenue2 {
	gen `var'_deflate = `var' / deflator
}

*/

quietly summarize ent_revenue2_deflate if !missing(ent_revenue2_deflate), detail
local p1  = r(p1)
local p99 = r(p99)

* winsorize
gen ent_revenue2_winsor = ent_revenue2_deflate 
replace ent_revenue2_winsor = `p1' if ent_revenue2_deflate < `p1' & !missing(ent_revenue2_deflate)
replace ent_revenue2_winsor = `p99' if ent_revenue2_deflate > `p99' & !missing(ent_revenue2_deflate)

****** Changes in firm size and average labor productivity ****** 

use TFPR_BL.dta, replace

gen revenue_lastmth_BL = HH_ENT_CEN_BL_rev_mon 
replace revenue_lastmth_BL = ENT_SUR_BL_rev_mon if !missing(ENT_SUR_BL_rev_mon) & revenue_lastmth_BL == . 
replace revenue_lastmth_BL = HH_ENT_SUR_BL_rev_mon if !missing(HH_ENT_SUR_BL_rev_mon) & revenue_lastmth_BL == . 
 
* deflate prices
foreach var in revenue_lastmth_BL {
	gen `var'_deflate = `var' / deflator
}

gen arpl_BL = revenue_lastmth_BL_deflate/(ENT_SUR_BL_emp_h_tot*(31/7))

* deflate prices
foreach var in arpl_BL {
	quietly summarize `var' if !missing(`var'), detail
	local p10  = r(p10)
	local p90 = r(p90)

	* winsorize
	gen `var'_winsor = `var' if !missing(`var')
	replace `var'_winsor = . if `var' < `p10' & !missing(`var')
	replace `var'_winsor = . if `var' > `p90' & !missing(`var')
}

* sector total repeated on every row in that sector
bysort bizcat_cons_BL: ///
    egen double emp_h_tot_sector = total(ENT_SUR_BL_emp_h_tot * fw_BL) ///
    if inrange(bizcat_cons_BL,1,8) & ent_type_BL==1
	
gen emp_share = ENT_SUR_BL_emp_h_tot * fw_BL/emp_h_tot_sector 

binscatter arpl_BL emp_share [fw=fw_BL] if arpl_BL <= 9000, scheme(lean2) ytitle("ARPL") xtitle("Employment share in sector") by(treat) nquantiles(30)
graph export ARPL_employshare_BL_treatcontrol.png, replace

binscatter arpl_BL emp_share [fw=fw_BL] if arpl_BL <= 9000, scheme(lean2) ytitle("ARPL") xtitle("Employment share in sector") nquantiles(30)
graph export ARPL_employshare_BL.png, replace

*** need to fix this - how come revenue went down - rev_mon is off?

use TFPR_EL.dta, replace

* deflate prices
foreach var in rev_mon {
	gen `var'_deflate = `var' / deflator
}

gen arpl_EL = rev_mon_deflate/(emp_h_tot*(31/7))

* deflate prices
foreach var in arpl_EL {
	quietly summarize `var' if !missing(`var'), detail
	local p10  = r(p10)
	local p90 = r(p90)

	* winsorize
	gen `var'_winsor = `var' if !missing(`var')
	replace `var'_winsor = . if `var' < `p10' & !missing(`var')
	replace `var'_winsor = . if `var' > `p90' & !missing(`var')
}

* sector total repeated on every row in that sector
bysort bizcat_cons: ///
    egen double emp_h_tot_sector = total(emp_h_tot * fw_EL) ///
    if inrange(bizcat_cons,1,8) & ent_type==1
	
gen emp_share = emp_h_tot * fw_EL/emp_h_tot_sector 

binscatter arpl_EL emp_share [fw=fw_EL] if arpl_EL <= 9000, scheme(lean2) ytitle("ARPL") xtitle("Employment share in sector") by(treat) nquantiles(30)
graph export ARPL_employshare_EL.png, replace
