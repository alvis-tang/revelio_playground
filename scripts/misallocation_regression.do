cd "C:\Users\Alvis\Dropbox\replication_materials\replication_materials\analysisdata"

/*

use TFPR_EL.dta, replace

****************************************************
* 1. Enterprise-level data + spatial instruments   *
****************************************************

* Change this to where your Egger data live
global data "/path/to/egger/data"

* (a) Start from Egger's enterprise file with spatial stuff
use "$data/Ent_SpatialData_Temporal.dta", clear

* Keep only actual firms (endline enterprises)
keep if !missing(entcode_EL)

* (b) If your own firm outcomes are in a separate file, merge them here
*     (Assumes your file has entcode_EL as key)
* merge 1:1 entcode_EL using "/path/to/my_firm_outcomes.dta", nogen

* (c) Bring in village-level treatment amounts and IVs
merge m:1 village_code using "$data/GE_VillageLevel_ECMA.dta", ///
      keepusing( ///
        pp_actamt_ownvill ///
        pp_actamt_ov_0to2km pp_actamt_ov_2to4km pp_actamt_ov_4to6km ///
        pp_actamt_ov_6to8km pp_actamt_ov_8to10km ///
        share_ge_elig_treat_ov_0to2km share_ge_elig_treat_ov_2to4km ///
        share_ge_elig_treat_ov_4to6km share_ge_elig_treat_ov_6to8km ///
        share_ge_elig_treat_ov_8to10km ///
      ), nogen

* Endogenous regressors = actual per-capita transfer amounts
local endregs pp_actamt_ownvill ///
              pp_actamt_ov_0to2km pp_actamt_ov_2to4km pp_actamt_ov_4to6km ///
              pp_actamt_ov_6to8km pp_actamt_ov_8to10km

* Instruments = assignment / treated share in those rings
local exregs  treat ///
              share_ge_elig_treat_ov_0to2km share_ge_elig_treat_ov_2to4km ///
              share_ge_elig_treat_ov_4to6km share_ge_elig_treat_ov_6to8km ///
              share_ge_elig_treat_ov_8to10km

tempfile ent_anal
save `ent_anal', replace

use `ent_anal', clear

****************************************************
* 2. Firm-level regressions (Table 3-type)         *
****************************************************

* List the firm outcomes you care about
* (Example: the original Table 3 outcomes)
local firm_outcomes ent_profit2_wins_PPP ent_revenue2_wins_PPP ///
                    ent_profitmargin2_wins ent_inventory_wins_PPP ///
                    ent_inv_wins_PPP

foreach y of local firm_outcomes {

    di "----- Outcome: `y' -----"

    * Baseline control: assume baseline version is called `y'_BL
    * If you don't have a baseline for some outcome, this just drops controls.
    local y_bl `y'_BL
    capture confirm variable `y_bl'
    if _rc==0 {
        quietly egen M_`y_bl' = mean(`y_bl'), by(village_code)
        local blvars "c.`y_bl' c.M_`y_bl'"
    }
    else {
        local blvars ""
    }

    *---------------------------
    * Column 1: OLS (treat vs control)
    *---------------------------
    reg `y' treat hi_sat `blvars' [aweight = entweight_EL], ///
        cluster(sublocation_code)

    * Store or outreg2 here if you want to build a table

    *---------------------------
    * Columns 2–3: Spatial IV
    *---------------------------

    ivreg2 `y' `blvars' ///
        (`endregs' = `exregs') ///
        [aweight = entweight_EL], cluster(sublocation_code)

    * ---- Total effect on treated villages (col 2 analogue) ----
    quietly summarize pp_actamt_ownvill if treat==1 [aweight = entweight_EL]
    local m_own = r(mean)

    foreach v in pp_actamt_ov_0to2km pp_actamt_ov_2to4km ///
                 pp_actamt_ov_4to6km pp_actamt_ov_6to8km ///
                 pp_actamt_ov_8to10km {
        quietly summarize `v' if treat==1 [aweight = entweight_EL]
        local m_`v' = r(mean)
    }

    lincom ///
        `m_own'                     * pp_actamt_ownvill      + ///
        `m_pp_actamt_ov_0to2km'     * pp_actamt_ov_0to2km    + ///
        `m_pp_actamt_ov_2to4km'     * pp_actamt_ov_2to4km    + ///
        `m_pp_actamt_ov_4to6km'     * pp_actamt_ov_4to6km    + ///
        `m_pp_actamt_ov_6to8km'     * pp_actamt_ov_6to8km    + ///
        `m_pp_actamt_ov_8to10km'    * pp_actamt_ov_8to10km

    * That lincom is your "total effect" estimate, evaluated at
    * average transfer amounts in treated villages.

    * ---- Spillover effect on control villages (col 3 analogue) ----
    quietly summarize pp_actamt_ownvill if treat==0 [aweight = entweight_EL]
    local m0_own = r(mean)

    foreach v in pp_actamt_ov_0to2km pp_actamt_ov_2to4km ///
                 pp_actamt_ov_4to6km pp_actamt_ov_6to8km ///
                 pp_actamt_ov_8to10km {
        quietly summarize `v' if treat==0 [aweight = entweight_EL]
        local m0_`v' = r(mean)
    }

    lincom ///
        `m0_own'                    * pp_actamt_ownvill      + ///
        `m0_pp_actamt_ov_0to2km'    * pp_actamt_ov_0to2km    + ///
        `m0_pp_actamt_ov_2to4km'    * pp_actamt_ov_2to4km    + ///
        `m0_pp_actamt_ov_4to6km'    * pp_actamt_ov_4to6km    + ///
        `m0_pp_actamt_ov_6to8km'    * pp_actamt_ov_6to8km    + ///
        `m0_pp_actamt_ov_8to10km'   * pp_actamt_ov_8to10km

    * That lincom is the "spillover effect" on control villages,
    * evaluating the IV coefficients at the average spatial transfers
    * around control villages.

}

*/

*******************************************************
*******************************************************
*******************************************************
*******************************************************
*******************************************************

***********************************************
* 3. Village-level data + your outcomes       *
***********************************************

use TFPR_EL.dta, replace
keep if ln_TFPR_ratio != .

gen ln_TFPR_si_trim = ln(TFPR_si_trim)

collapse (sd) ln_TFPR_ratio ln_TFPR_si_trim (mean) treat (sum) entweight_EL if ent_type == 1, by(village_code)

gen var_ln_TFPR_ratio = ln_TFPR_ratio^2
gen var_ln_TFPR_si_trim  = ln_TFPR_si_trim ^2

save TFPR_EL_var.dta, replace

use TFPR_BL.dta, replace
keep if ln_TFPR_ratio_BL != .

gen ln_TFPR_si_trim_BL = ln(TFPR_si_trim_BL)

collapse (sd) ln_TFPR_ratio_BL ln_TFPR_si_trim_BL (mean) treat (sum) entweight_BL if ent_type == 1, by(village_code)

gen var_ln_TFPR_ratio_BL = ln_TFPR_ratio_BL^2
gen var_ln_TFPR_si_trim_BL = ln_TFPR_si_trim_BL ^2

save TFPR_BL_var.dta, replace

use "C:\Users\Alvis\Dropbox\replication_materials\replication_materials\analysisdata\GE_VillageLevel_ECMA.dta", clear

merge 1:1 village_code using TFPR_EL_var.dta, nogen
merge 1:1 village_code using TFPR_BL_var.dta, nogen

gen diff_var_ln_TFPR_ratio = var_ln_TFPR_ratio - var_ln_TFPR_ratio_BL
gen diff_var_ln_TFPR_si_trim = var_ln_TFPR_si_trim - var_ln_TFPR_si_trim_BL

* only 10 observations?!
sum diff_var_ln_TFPR_ratio diff_var_ln_TFPR_si_trim 

* Adjust the path to wherever calculate_optimal_radii.ado lives on your machine
do "C:\Users\Alvis\Dropbox\replication_materials\replication_materials\code\ado\calculate_optimal_radii.ado"

****************************************************
* 4. Village-level regressions (Table 3 Panel C)   *
****************************************************

* Outcome: endline variance of log TFPR
local y var_ln_TFPR_ratio

* Baseline variance as a control (optional but recommended)
*local blvars "var_ln_TFPR_ratio_BL"

*---------------------------------------------------
* 4.1 Choose optimal radius by Egger's BIC routine *
*---------------------------------------------------

* This uses the actual calculate_optimal_radii.ado
* with the , vill option (village-level spec)
calculate_optimal_radii `y' [aweight = entweight_EL], ///
    vill blvars("`blvars'") quietly

local r = r(r_max)
di "BIC-chosen outer radius r_max = `r' km"

*---------------------------------------------------
* 4.2 Build endogenous regressors & instruments    *
*     exactly like ge_tables_ent.do (Panel C)      *
*---------------------------------------------------

cap gen cons = 1   // harmless, used in GPS version

local endregs "pp_actamt_ownvill"
local exregs  "treat"
local amount_list ""

forvalues rad = 2(2)`r' {
    local r2 = `rad' - 2
    local endregs     "`endregs' pp_actamt_ov_`r2'to`rad'km"
    local exregs      "`exregs' share_ge_elig_treat_ov_`r2'to`rad'km"
    local amount_list "`amount_list' pp_actamt_ov_`r2'to`rad'km"
}

*---------------------------------------------------
* 4.3 Column 1 analogue: OLS, clustered at subloc  *
*---------------------------------------------------

reg `y' treat hi_sat `blvars' [aweight = entweight_EL], ///
    cluster(sublocation_code)

*---------------------------------------------------
* 4.4 Columns 2–3 analogue: spatial IV             *
*     (same structure as Table 3 Panel C)          *
*---------------------------------------------------

ivreg2 `y' `blvars' (`endregs' = `exregs') ///
    [aweight = entweight_EL], cluster(sublocation_code) first

*---------------------------------------------------
* 4.5 Total effect on treated villages             *
*     (own + neighbors at treated means)           *
*---------------------------------------------------

quietly summarize pp_actamt_ownvill if treat == 1 ///
    [aweight = entweight_EL]
local m_own = r(mean)

local ATE_tot "`m_own'*pp_actamt_ownvill"

foreach v of local amount_list {
    quietly summarize `v' if treat == 1 [aweight = entweight_EL]
    local m_`v' = r(mean)
    local ATE_tot "`ATE_tot' + `m_`v''*`v'"
}

di "Total-effect lincom: `ATE_tot'"
lincom `ATE_tot'

*---------------------------------------------------
* 4.6 Spillover effect on control villages         *
*     (neighbors only, own transfers = 0)          *
*---------------------------------------------------

local ATE_spill "0"

foreach v of local amount_list {
    quietly summarize `v' if treat == 0 [aweight = entweight_EL]
    local m0_`v' = r(mean)
    local ATE_spill "`ATE_spill' + `m0_`v''*`v'"
}

di "Spillover-effect lincom: `ATE_spill'"
lincom `ATE_spill'

/*

****************************************************
* 4. Village-level regressions (Table 3 Panel C)   *
****************************************************

* For now, I'll just use the raw count as the dependent variable.
local y var_ln_TFPR_ratio  // or your own variable

* Same endogenous regressors and instruments as above
local endregs pp_actamt_ownvill ///
              pp_actamt_ov_0to2km pp_actamt_ov_2to4km pp_actamt_ov_4to6km ///
              pp_actamt_ov_6to8km pp_actamt_ov_8to10km

local exregs  treat ///
              share_ge_elig_treat_ov_0to2km share_ge_elig_treat_ov_2to4km ///
              share_ge_elig_treat_ov_4to6km share_ge_elig_treat_ov_6to8km ///
              share_ge_elig_treat_ov_8to10km

* Column 1 analogue: OLS, clustered at sublocation
reg `y' treat hi_sat [aweight=entweight_EL], cluster(sublocation_code)

* Columns 2–3 analogue: IV with spatial treatment, clustered at sublocation
ivreg2 `y' (`endregs' = `exregs') [aweight=entweight_EL], cluster(sublocation_code) first

* You can repeat the same linear-combination logic as above
* to construct "total" and "spillover" effects at the village level.

* ---- Total effect on treated villages (col 2 analogue) ----
    quietly summarize pp_actamt_ownvill if treat==1 [aweight=entweight_EL]
    local m_own = r(mean)

    foreach v in pp_actamt_ov_0to2km pp_actamt_ov_2to4km ///
                 pp_actamt_ov_4to6km pp_actamt_ov_6to8km ///
                 pp_actamt_ov_8to10km {
        quietly summarize `v' if treat==1 [aweight=entweight_EL]
        local m_`v' = r(mean)
    }

    lincom ///
        `m_own'                     * pp_actamt_ownvill      + ///
        `m_pp_actamt_ov_0to2km'     * pp_actamt_ov_0to2km    + ///
        `m_pp_actamt_ov_2to4km'     * pp_actamt_ov_2to4km    + ///
        `m_pp_actamt_ov_4to6km'     * pp_actamt_ov_4to6km    + ///
        `m_pp_actamt_ov_6to8km'     * pp_actamt_ov_6to8km    + ///
        `m_pp_actamt_ov_8to10km'    * pp_actamt_ov_8to10km

    * That lincom is your "total effect" estimate, evaluated at
    * average transfer amounts in treated villages.

    * Spillover effect on control villages: neighbors only
foreach v in pp_actamt_ov_0to2km pp_actamt_ov_2to4km ///
             pp_actamt_ov_4to6km pp_actamt_ov_6to8km ///
             pp_actamt_ov_8to10km {
    quietly summarize `v' if treat==0 [aweight=entweight_EL]
    local m0_`v' = r(mean)
}

	lincom ///
    `m0_pp_actamt_ov_0to2km' * pp_actamt_ov_0to2km    + ///
    `m0_pp_actamt_ov_2to4km' * pp_actamt_ov_2to4km    + ///
    `m0_pp_actamt_ov_4to6km' * pp_actamt_ov_4to6km    + ///
    `m0_pp_actamt_ov_6to8km' * pp_actamt_ov_6to8km    + ///
    `m0_pp_actamt_ov_8to10km'* pp_actamt_ov_8to10km


