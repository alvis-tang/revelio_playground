* Count rows in the bounded sample; these are not population headcounts.
clear all
set more off
version 17.0
local root : environment KLC_ROOT
if "`root'" == "" {
    display as error "KLC_ROOT is required; run through ./klc run stata"
    exit 198
}
confirm file "`root'/proc/revelio_sample.dta"
use "`root'/proc/revelio_sample.dta", clear
confirm variable rcid country
assert _N > 0
describe
contract rcid country, freq(sample_position_rows)
list, noobs
save "`root'/proc/revelio_sample_counts.dta", replace
