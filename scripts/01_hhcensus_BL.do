clear all
set more off

******************* Baseline Household Census data of Phase 1 *******************

use "$DATA/HH_BL_Census_Phase_1/hhcensus_data.dta"
describe

/// Basic summary statistics

// 90.28% of surveys were answered by household head/spouse, 4.71% were answered by neighbors
tab survey_respondent

// 24.02% of households have grass thatch roof, 72.07% have iron/tin roof
tab s4_roof_quality

// 21.30% of households own a bicycle
tab s4_asset_bicycle
// 23.25% of households own a mattress
tab s4_asset_mattress
// 50.45% of households own a phone
tab s4_asset_phone
// 16.89% of households own a radio
tab s4_asset_radio
// 21.48% of households own a solar panel
tab s4_asset_solar_panel
// 35.58% of households own none of the above
tab s4_asset_none

gen assetidx_5 = s4_asset_bicycle + s4_asset_mattress + s4_asset_phone + s4_asset_radio + s4_asset_solar_panel

// 89.68% of househld cultivated land in the last planting season
tab s5_cult_land

// mean cultivated land area in the last planting season: 0.7144795 acres = 0.289 hectares
// median cultivated land area in the last planting season: 0.5 acres = 0.2023 hectares
// 95% percentile: 2 acres = 0.809 hectares, 99% perceentile: 3.4 acres = 1.38 hectares
sum s5_cult_land_acre_eqv

// net search lean2

// distribution of cultivated land (acres equivalent among those who did cultivate), cut off at 99% percentile
hist s5_cult_land_acre_eqv if s5_cult_land_acre_eqv < 3.4, scheme(lean2) note("Sample truncated at 99% percentile (3.4 acres)")

// 31.99% of households own livestock
tab s5_livestock_any

// generate dummy indicator for whether owns livestock

foreach x in chickens goats cows pigs {
	gen `x'_any = (s5_`x' > 0)
	replace `x'_any = . if s5_`x' <0
}

// household on average owns 2.23 chickens, 0.88 goats, 0.47 cows, 0.14 pigs
foreach x in chickens goats cows pigs {
	sum s5_`x' if s5_`x' >= 0 
}

// 72.08% of households had some member working for pay for someone else (including casual labor)
tab s5_employment

// 21.88% of the most important source of employment fell under food vendors (allowing multiple selection)
tab s5_ocptn_primary_sec_cat_1 

// mostly this is raw food stalls/processed food stalls
forvalues i=1/7{
	tab s5_ocptn_primary_ent_cat_`i'
}

forvalues i=10/12{
	tab s5_ocptn_primary_ent_cat_`i'
}

// 1.52% of the most important source of employment fell under agriculture
tab s5_ocptn_primary_sec_cat_2 

forvalues i=8/9{
	tab s5_ocptn_primary_ent_cat_`i'
}


// 34.62% of the most important source of employment fell under non-food vendors
tab s5_ocptn_primary_sec_cat_3 

// mostly this is clothing and footwear seller
forvalues i=13/22{
	tab s5_ocptn_primary_ent_cat_`i'
}

// 10.02% of the most important source of employment fell under manufacturing
tab s5_ocptn_primary_sec_cat_4 

// largest occupation is bicycle mechanic
forvalues i=23/27{
	tab s5_ocptn_primary_ent_cat_`i'
}

// 32.61% of the most important source of employment fell under services
tab s5_ocptn_primary_sec_cat_5

// largest occupation is photo studio/cyber cafe/CD burning, beauty salon/barber
forvalues i=28/34{
	tab s5_ocptn_primary_ent_cat_`i'
}

// 30.44% of households ran at least one non-agricultural business selling more than 10k in a typical month
tab s6_non_ag_ent

// Conditional on having having ran, average household has 1.05 non-ag businesses
sum s6_num_ent

//preserve

keep if s6_num_ent > 0


egen census_id = group(survey_key)

rename s6_primary_ent_cat__other_* s6_primary_ent_cat__78_*
rename s6_primary_ent_cat__78_text_* s6_primary_ent_cat__78_tx_*

forvalues i=1/44 {
	local ent_cat_`i': variable label s6_primary_ent_cat__`i'_1
}

forvalues i=77/78 {
	local ent_cat_`i': variable label s6_primary_ent_cat__`i'_1
}

forvalues i=1/5 {
	local sec_cat_`i': variable label s6_primary_sec_cat__`i'_1
}

local location_market      : variable label s6_business_location_market_1
local location_vill_ta     : variable label s6_business_location_vill_ta_1
local location_vill_gvh    : variable label s6_business_location_vill_gvh_1
local location_vill_vil    : variable label s6_business_location_vill_vil_1
local business_info        : variable label s6_business_info_1
local business_sector      : variable label s6_business_sector_concat_1		  
			 

reshape long s6_business_location_ ///
              s6_business_location_market_ ///
              s6_business_location_vill_ta_ ///
              s6_business_location_vill_gvh_ ///
              s6_business_location_vill_vil_ ///
              s6_bus_location_market_oth__ ///
              s6_business_info_ ///
              s6_business_sector_concat_ ///
              s6_primary_ent_cat__1_  s6_primary_ent_cat__2_  s6_primary_ent_cat__3_  s6_primary_ent_cat__4_  s6_primary_ent_cat__5_ ///
s6_primary_ent_cat__6_  s6_primary_ent_cat__7_  s6_primary_ent_cat__8_  s6_primary_ent_cat__9_  s6_primary_ent_cat__10_ ///
s6_primary_ent_cat__11_ s6_primary_ent_cat__12_ s6_primary_ent_cat__13_ s6_primary_ent_cat__14_ s6_primary_ent_cat__15_ ///
s6_primary_ent_cat__16_ s6_primary_ent_cat__17_ s6_primary_ent_cat__18_ s6_primary_ent_cat__19_ s6_primary_ent_cat__20_ ///
s6_primary_ent_cat__21_ s6_primary_ent_cat__22_ s6_primary_ent_cat__23_ s6_primary_ent_cat__24_ s6_primary_ent_cat__25_ ///
s6_primary_ent_cat__26_ s6_primary_ent_cat__27_ s6_primary_ent_cat__28_ s6_primary_ent_cat__29_ s6_primary_ent_cat__30_ ///
s6_primary_ent_cat__31_ s6_primary_ent_cat__32_ s6_primary_ent_cat__33_ s6_primary_ent_cat__34_ s6_primary_ent_cat__35_ ///
s6_primary_ent_cat__36_ s6_primary_ent_cat__37_ s6_primary_ent_cat__38_ s6_primary_ent_cat__39_ s6_primary_ent_cat__40_ ///
s6_primary_ent_cat__41_ s6_primary_ent_cat__42_ s6_primary_ent_cat__43_ s6_primary_ent_cat__44_ ///
s6_primary_ent_cat__77_ s6_primary_ent_cat__78_ ///
              s6_primary_sec_cat__1_ s6_primary_sec_cat__2_ s6_primary_sec_cat__3_ s6_primary_sec_cat__4_ s6_primary_sec_cat__5_, ///
              i(census_id) j(business_id) 
			  
forvalues i=1/44 {
	label variable s6_primary_ent_cat__`i'_ "`ent_cat_`i''"	  
}

forvalues i=77/78 {
	label variable s6_primary_ent_cat__`i'_ "`ent_cat_`i''"	  
}

forvalues i=1/5 {
	label variable s6_primary_ent_cat__`i'_  "`sec_cat_`i''"
}

label variable s6_business_location_market_      "`location_market'"
label variable s6_business_location_vill_ta_      "`location_vill_ta'"
label variable s6_business_location_vill_gvh_     "`location_vill_gvh'"
label variable s6_business_location_vill_vil_     "`location_vill_vil'"
label variable s6_business_info_                  "`business_info'"
label variable s6_business_sector_concat_         "`business_sector'"

// 65.96% of the enterprises ran by the household were food vendors
sum s6_primary_sec_cat__1_ 

// mostly this is raw food stalls/processed food stalls, followed by processed food stalls, sale/brewing alcohol
forvalues i=1/7{
	tab s6_primary_ent_cat__`i'_
}

forvalues i=10/12{
	tab s6_primary_ent_cat__`i'_
}

// 7.79% of the enterprises ran by the household were agriculture
sum s6_primary_sec_cat__2_ 

// mostly this is agricultural/vet supplies
forvalues i=8/9{
	tab s6_primary_ent_cat__`i'_
}

// 14.22% of the enterprises ran by the household were non-food vendors
sum s6_primary_sec_cat__3_ 

// mostly this is charcoal vendors, clothing/shoes, household items and supplies, arts and crafts
forvalues i=13/22{
	tab s6_primary_ent_cat__`i'_
}

// 5.24% of the enterprises ran by the household were manufacturing
sum s6_primary_sec_cat__4_ 

// mostly this is tailor, carpenter/woodwork
forvalues i=23/27{
	tab s6_primary_ent_cat__`i'_
}

// 8.44% of the enterprises ran by the household were services
sum s6_primary_sec_cat__5_	

// motorcycle transport, beauty salon/barber
forvalues i=28/38{
	tab s6_primary_ent_cat__`i'_
}
			  
// these need categorizing into sectors
sum s6_primary_ent_cat__39_ s6_primary_ent_cat__40_ s6_primary_ent_cat__41_ s6_primary_ent_cat__42_ s6_primary_ent_cat__43_ s6_primary_ent_cat__44_			  

