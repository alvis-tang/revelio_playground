clear all
set more off
version 17.0
local root : environment KLC_ROOT
if "`root'" == "" {
    display as error "KLC_ROOT is required; run through ./klc run stata"
    exit 198
}
set obs 3
generate value = _n
assert value == _n
save "`root'/proc/stata_smoke.dta", replace
display "Stata smoke test completed."
