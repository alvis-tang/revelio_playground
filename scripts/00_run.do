*******************************************************
* 00_run.do
* Master entry point for steg_call project
*******************************************************

clear all
set more off
version 17.0

capture log close

*******************************************************
* 1. Define project root
*******************************************************

cd "/Users/kstang/work/github/steg_call/scripts"

local cur "`c(pwd)'"
global PROJ = substr("`cur'", 1, strrpos("`cur'", "/") - 1)

display "$PROJ"

*******************************************************
* 2. Define standard folders
*******************************************************

global DATA    "$PROJ/data"
global PROC    "$PROJ/proc"
global RESULTS "$PROJ/results"
global TABLES  "$PROJ/tables"
global LOGS    "$PROJ/logs"
global SCRIPTS "$PROJ/scripts"

display "$LOGS"

*******************************************************
* 4. Start log
*******************************************************
log using "$LOGS/run.log", replace text

*******************************************************
* 5. Call project pipeline
*******************************************************

do "$SCRIPTS/01_hhcensus_BL.do"
do "$SCRIPTS/02_mktcensus_BL.do"
do "$SCRIPTS/03_hhsurvey_BL.do"
do "$SCRIPTS/04_mktsurvey_BL.do"
do "$SCRIPTS/05_maps_BL.do"
do "$SCRIPTS/06_enterprise_reclassify.do"
do "$SCRIPTS/08_hh_business_reclassify.do"
do "$SCRIPTS/07_enterprise_type_summary.do"


*******************************************************
* 6. Close log
*******************************************************

display "00_run.do completed successfully."
