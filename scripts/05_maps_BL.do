*****************************************

/********************************************************************
  simple_map.do  (Stata translation of simple_map.py)

  Folder structure (relative to this .do file):
    Data/
      village_info.csv
      market_info.csv
    Shape files/
      mwi_admbnda_adm2_nso_hotosm_20230405.shp
      mwi_admbnda_adm3_nso_hotosm_20230405.shp
    Map outputs/
      (created if missing)

  Requires Stata 17/18+ for geoplot/geoframe.
********************************************************************/

clear all
set more off

local BASE_DIR   "$DATA/Village and Market Info"
local DATA_DIR   "`BASE_DIR'/Data"
local SHAPE_DIR  "`BASE_DIR'/Shape files"
local OUT_DIR    "`BASE_DIR'/Map outputs"

cap mkdir "`OUT_DIR'"

local ADM2_SHP "`SHAPE_DIR'/mwi_admbnda_adm2_nso_hotosm_20230405.shp"
local ADM3_SHP "`SHAPE_DIR'/mwi_admbnda_adm3_nso_hotosm_20230405.shp"

local VILL_CSV "`DATA_DIR'/village_info.csv"
local MKT_CSV  "`DATA_DIR'/market_info.csv"

local DISTRICT "chiradzulu"
local geo "`DATA_DIR'/villagemarkets_clean.dta"
local edges "$DATA/Phase 1 household baseline/consumption_links.dta"

/********************************************************************
  1) Convert shapefiles to Stata datasets (one-time, cached)
********************************************************************/
cap confirm file "`SHAPE_DIR'/adm2_db.dta"
if _rc {
    shp2dta using "`ADM2_SHP'", database("`SHAPE_DIR'/adm2_db") coordinates("`SHAPE_DIR'/adm2_coor") replace
}

cap confirm file "`SHAPE_DIR'/adm3_db.dta"
if _rc {
    shp2dta using "`ADM3_SHP'", replace ///
        database("`SHAPE_DIR'/adm3_db") coordinates("`SHAPE_DIR'/adm3_coor")
}

/********************************************************************
  2) Filter ADM2 and ADM3 to Chiradzulu
********************************************************************/
use "`SHAPE_DIR'/adm2_db.dta", clear
gen adm2_lc = lower(strtrim(ADM2_EN))
keep if adm2_lc == "`DISTRICT'"
save "`SHAPE_DIR'/adm2_db_chiradzulu.dta", replace

use "`SHAPE_DIR'/adm3_db.dta", clear
gen adm2_lc = lower(strtrim(ADM2_EN))
keep if adm2_lc == "`DISTRICT'"
save "`SHAPE_DIR'/adm3_db_chiradzulu.dta", replace

use "`SHAPE_DIR'/adm2_db.dta", clear
gen adm2_lc = lower(strtrim(ADM2_EN))
keep if inlist(adm2_lc, "chiradzulu", "blantyre city")
save "`SHAPE_DIR'/adm2_db_chira_btyre.dta", replace

/********************************************************************
  3) Load points: villages + markets
********************************************************************/
import delimited "`VILL_CSV'", clear varnames(1)
destring longitude_medoid latitude_medoid, replace force
gen byte is_village = 1
drop if missing(longitude_medoid) | missing(latitude_medoid)
save "`DATA_DIR'/villages_clean.dta", replace

import delimited "`MKT_CSV'", clear varnames(1)
destring longitude_medoid latitude_medoid, replace force
gen byte is_market = 1
drop if missing(longitude_medoid) | missing(latitude_medoid)
save "`DATA_DIR'/markets_clean.dta", replace

use "`DATA_DIR'/villages_clean.dta", clear
append using "`DATA_DIR'/markets_clean.dta"
gen point_type = 1 if is_village == 1
replace point_type = 2 if is_market == 1
label define point_type 1 "Village" 2 "Market"
label values point_type point_type
save "`DATA_DIR'/villagemarkets_clean.dta", replace

/********************************************************************
  4) Create geoframes
********************************************************************/
geoframe create chiradzulu "`SHAPE_DIR'/adm2_db_chiradzulu.dta", ///
    shp("`SHAPE_DIR'/adm2_coor.dta") replace

geoframe create ta_bounds "`SHAPE_DIR'/adm3_db_chiradzulu.dta", ///
    shp("`SHAPE_DIR'/adm3_coor.dta") replace

geoframe create points "`DATA_DIR'/villagemarkets_clean.dta", ///
    coord(longitude_medoid latitude_medoid) replace
	
geoframe create chira_btyre "`SHAPE_DIR'/adm2_db_chira_btyre.dta", ///
    shp("`SHAPE_DIR'/adm2_coor.dta") replace
	
clear
input str12 name double longitude_medoid latitude_medoid
"Blantyre" 35.0058 -15.7861
end

gen byte is_blantyre = 1
save "`DATA_DIR'/blantyre_point.dta", replace

geoframe create blantyre_pt "`DATA_DIR'/blantyre_point.dta", coord(longitude_medoid latitude_medoid) replace

/********************************************************************
  5) Plot base map: villages and markets
********************************************************************/

geoplot ///
    (area chira_btyre, fcolor(white) lcolor(black) lwidth(medthick)) ///
    (area ta_bounds,  fcolor(none)  lcolor(gs10)  lwidth(vthin)) ///
    (point points if is_village==1, mcolor(gs6) msize(0.6)) ///
    (point points if is_market==1,  mcolor(red)  msize(0.6)) ///
    (point blantyre_pt, mcolor(black) msymbol(D) msize(1)) ///
    , graphregion(color(white)) ///
      legend(off) ///
      glegend(layout(3 "Village" . 4 "Market" . 5 "Blantyre") ///
              position(ne) rowgap(2))

geoplot ///
    (area chiradzulu, fcolor(white) lcolor(black) lwidth(medthick)) ///
    (area ta_bounds,  fcolor(none)  lcolor(gs10)  lwidth(vthin)) ///
    (point points if is_village==1, mcolor(gs6) msize(0.6)) ///
    (point points if is_market==1,  mcolor(red)  msize(0.6)) ///
    , graphregion(color(white)) ///
    legend(off) ///
    glegend(layout(3 "Village" . 4 "Market") position(ne) rowgap(2))
	
 graph export "`OUT_DIR'/basemap.png", replace width(2000)

/********************************************************************
  6) Build consumption links with geography
********************************************************************/
use "`geo'", clear
keep if point_type == 1
tempfile geo_villages
save `geo_villages'

use "`geo'", clear
keep if point_type == 2
tempfile geo_markets
save `geo_markets'

tempfile pt1 pt2 pt3 pt4

foreach pt in 1 2 3 4 {
    use "`edges'", clear
    keep if dest_point_type == `pt'
    
    if `pt' == 1 {
        rename dest_node    village_id
        rename dest_ta      ta_id
        rename dest_gvh     gvh_id
        merge m:1 ta_id gvh_id village_id using `geo_villages', ///
            keepusing(latitude_medoid longitude_medoid ta gvh village) ///
            keep(master match) nogen
        rename village_id   dest_node
        rename ta_id        dest_ta
        rename gvh_id       dest_gvh
    }
    if `pt' == 2 {
        rename dest_node market_id
        merge m:1 market_id using `geo_markets', ///
            keepusing(latitude_medoid longitude_medoid market) ///
            keep(master match) nogen
        rename market_id  dest_node
        rename market     village
    }
    if `pt' == 3 {
        gen latitude_medoid  = -15.7861
        gen longitude_medoid = 35.0058 
        gen village = cond(`pt'==3, "Blantyre", "Outside")
    }
    if `pt' == 4 {
        gen latitude_medoid  = .
        gen longitude_medoid = .
        gen village = "Outside"
    }
    rename latitude_medoid  dest_lat
    rename longitude_medoid dest_lon
    rename village          dest_name
    save `pt`pt'', replace
}

foreach pt in 1 2 3 4 {
    use `pt`pt'', clear
    rename origin_node  village_id
    rename s1_ta        ta_id
    rename s1_gvh       gvh_id
    merge m:1 ta_id gvh_id village_id using `geo_villages', ///
        keepusing(latitude_medoid longitude_medoid village) ///
        keep(master match) nogen
    rename latitude_medoid  origin_lat
    rename longitude_medoid origin_lon
    rename village          origin_name
    rename village_id       origin_node
    rename ta_id            s1_ta
    rename gvh_id           s1_gvh
    save `pt`pt'', replace
}

use `pt1', clear
forvalues pt = 2/4 {
    append using `pt`pt''
}

* Haversine distance in km
gen double pi = c(pi)
gen double lat1 = origin_lat*pi/180
gen double lon1 = origin_lon*pi/180
gen double lat2 = dest_lat*pi/180
gen double lon2 = dest_lon*pi/180

gen double dlat = lat2 - lat1
gen double dlon = lon2 - lon1

gen double a = (sin(dlat/2))^2 + cos(lat1)*cos(lat2)*(sin(dlon/2))^2
gen double cang = 2*asin(min(1, sqrt(a)))     // guard for rounding
gen double dist_km = 6371.0088 * cang         // mean Earth radius (km)

label var dist_km "Great-circle distance (km) origin->dest"

save "$DATA/Phase 1 household baseline/consumption_links_geo.dta", replace

/********************************************************************
  7) Prepare flow frames
********************************************************************/
use "$DATA/Phase 1 household baseline/consumption_links_geo.dta", clear

* helper program to avoid repetition
cap program drop make_flow_frame
program make_flow_frame
    args framename threshold
    * filter is already applied before calling - just collapse and scale
    
    keep if inlist(dest_point_type, 1, 2, 3)
    
    collapse (sum) spent_amt_w n_hh, ///
        by(origin_node origin_name origin_lat origin_lon ///
           dest_node dest_name dest_lat dest_lon dest_point_type)
    
    // drop if spent_amt_w < `threshold'
    
    /*
	gen log_w = log(spent_amt_w)
    sum log_w
    //gen line_w = (log_w - r(min)) / (r(max) - r(min)) * 1 + 0.1
    */
	
	gen line_w = 0.1 + log10(spent_amt_w/1724.138)
	
    rename origin_lat y1
    rename origin_lon x1
    rename dest_lat   y2
    rename dest_lon   x2
    
    cap frame drop `framename'
    frame put y1 x1 y2 x2 line_w, into(`framename')
end

local dur_stubs "s5_nonfe_vehic s5_nonfe_furnit s5_nonfe_carpets s5_nonfe_hhequip s5_nonfe_elecequip"

* food
use "$DATA/Phase 1 household baseline/consumption_links_geo.dta", clear
keep if regexm(stub, "^s5_fe_")
make_flow_frame flows_food 13625

* non-food non-durable
use "$DATA/Phase 1 household baseline/consumption_links_geo.dta", clear
keep if regexm(stub, "^s5_nonfe_")
foreach s of local dur_stubs {
    drop if stub == "`s'"
}
make_flow_frame flows_nonfood 13625

* durables
use "$DATA/Phase 1 household baseline/consumption_links_geo.dta", clear
keep if inlist(stub, "s5_nonfe_vehic", "s5_nonfe_furnit", "s5_nonfe_carpets", ///
                     "s5_nonfe_hhequip", "s5_nonfe_elecequip")
make_flow_frame flows_dur 13625

* food - no blantyre
use "$DATA/Phase 1 household baseline/consumption_links_geo.dta", clear
keep if regexm(stub, "^s5_fe_")
keep if dest_point_type == 1 | dest_point_type == 2 
make_flow_frame flows_food_noblant 13625

* non-food non-durable
use "$DATA/Phase 1 household baseline/consumption_links_geo.dta", clear
keep if regexm(stub, "^s5_nonfe_")
keep if dest_point_type == 1 | dest_point_type == 2
foreach s of local dur_stubs {
    drop if stub == "`s'"
}
make_flow_frame flows_nonfood_noblant 13625

* durables
use "$DATA/Phase 1 household baseline/consumption_links_geo.dta", clear
keep if inlist(stub, "s5_nonfe_vehic", "s5_nonfe_furnit", "s5_nonfe_carpets", ///
                     "s5_nonfe_hhequip", "s5_nonfe_elecequip")
keep if dest_point_type == 1 | dest_point_type == 2
make_flow_frame flows_dur_noblant 13625

/********************************************************************
  8) Map A: Food, Non-food non-durable, Durable
********************************************************************/
geoplot ///
    (area chiradzulu, fcolor(white) lcolor(black) lwidth(medthick)) ///
    (area ta_bounds,  fcolor(none)  lcolor(gs10)  lwidth(vthin)) ///
    (pcspike flows_food_noblant line_w, coordinates(x1 y1 x2 y2) lcolor(navy%10)   ///
        cuts(0 1 2 3 4 5 6 7 ) lwidth(0.05 3) label(,drop(0 1 2 3 4 5 6))) ///
    (point points if is_village==1, mcolor(gs6)  msize(0.5)) ///
    (point points if is_market==1,  mcolor(red)  msize(0.5)) ///
    , title("Food flows") graphregion(color(white)) ///
      glegend(layout(3 "Food flows" . 4 "Village" . 5 "Market")) ///
      name(map_food_noblant, replace)

geoplot ///
    (area chiradzulu, fcolor(white) lcolor(black) lwidth(medthick)) ///
    (area ta_bounds,  fcolor(none)  lcolor(gs10)  lwidth(vthin)) ///
    (pcspike flows_nonfood_noblant line_w, coordinates(x1 y1 x2 y2) lcolor(navy%10) ///
        cuts(0 1 2 3 4 5 6 7) lwidth(0.05 1) label(,drop(0 1 2 3 4 5 6))) ///
    (point points if is_village==1, mcolor(gs6)  msize(0.5)) ///
    (point points if is_market==1,  mcolor(red)  msize(0.5)) ///
    , title("Non-food non-durable flows") graphregion(color(white)) ///
      glegend(layout(3 "Non-food non-durable flows" . 4 "Village" . 5 "Market")) ///
      name(map_nonfood_noblant, replace)

geoplot ///
    (area chiradzulu, fcolor(white) lcolor(black) lwidth(medthick)) ///
    (area ta_bounds,  fcolor(none)  lcolor(gs10)  lwidth(vthin)) ///
    (pcspike flows_dur_noblant line_w, coordinates(x1 y1 x2 y2) lcolor(navy%10) ///
        cuts(0 1 2 3 4 5 6 7) lwidth(0.05 1) label(,drop(0 1 2 3 4 5 6))) ///
    (point points if is_village==1, mcolor(gs6)  msize(0.5)) ///
    (point points if is_market==1,  mcolor(red)  msize(0.5)) ///
    , title("Durables flows") graphregion(color(white)) ///
      glegend(layout(3 "Durable flow" . 4 "Village" . 5 "Market")) ///
      name(map_dur_noblant, replace)  
	  
/********************************************************************
  8) Map A: Food vs Non-food non-durable
********************************************************************/
geoplot ///
    (area chiradzulu, fcolor(white) lcolor(black) lwidth(medthick)) ///
    (area ta_bounds,  fcolor(none)  lcolor(gs10)  lwidth(vthin)) ///
    (pcspike flows_food_noblant line_w, coordinates(x1 y1 x2 y2) lcolor(navy%10)   ///
        cuts(0 1 2 3 4 5 6 7 ) lwidth(0.05 3) label(,drop(0 1 2 3 4 5 6))) ///
    (pcspike flows_nonfood_noblant line_w, coordinates(x1 y1 x2 y2) lcolor(orange%10) ///
        cuts(0 1 2 3 4 5 6 7) lwidth(0.05 3) label(,drop(0 1 2 3 4 5 6))) ///
    (point points if is_village==1, mcolor(gs6)  msize(0.5)) ///
    (point points if is_market==1,  mcolor(red)  msize(0.5)) ///
    , title("Food vs Non-food flows") graphregion(color(white)) ///
      glegend(layout(3 "Food" . 4 "Non-food" . 5 "Village" . 6 "Market")) ///
      name(map_food_nonfood_noblant, replace)

geoplot ///
    (area chira_btyre, fcolor(white) lcolor(black) lwidth(medthick)) ///
    (area ta_bounds,  fcolor(none)  lcolor(gs10)  lwidth(vthin)) ///
    (pcspike flows_food line_w, coordinates(x1 y1 x2 y2) lcolor(navy%10)   ///
        cuts(0 1 2 3 4 5 6 7 ) lwidth(0.05 1) label(,drop(0 1 2 3 4 5 6))) ///
    (pcspike flows_nonfood line_w, coordinates(x1 y1 x2 y2) lcolor(orange%10) ///
        cuts(0 1 2 3 4 5 6 7) lwidth(0.05 1) label(,drop(0 1 2 3 4 5 6))) ///
    (point points if is_village==1, mcolor(gs6)  msize(0.5)) ///
    (point points if is_market==1,  mcolor(red)  msize(0.5)) ///
    (point blantyre_pt, mcolor(black) msymbol(D) msize(1)) ///
    , title("Food vs Non-food flows") graphregion(color(white)) ///
      glegend(layout(3 "Food" . 4 "Non-food" . 5 "Village" . 6 "Market" . 7 "Blantyre")) ///
      name(map_food_nonfood, replace)

	 
/********************************************************************
  9) Map B: Food vs Durables
********************************************************************/
geoplot ///
    (area chiradzulu, fcolor(white) lcolor(black) lwidth(medthick)) ///
    (area ta_bounds,  fcolor(none)  lcolor(gs10)  lwidth(vthin)) ///
    (pcspike flows_food_noblant line_w, coordinates(x1 y1 x2 y2) lcolor(navy%10) cuts(0 1 2 3 4 5 6 7) lwidth(0.05 1) label(,drop(0 1 2 3 4 5 6))) ///
    (pcspike flows_dur_noblant line_w,  coordinates(x1 y1 x2 y2) lcolor(cranberry%10) cuts(0 1 2 3 4 5 6 7) lwidth(0.05 1) label(,drop(0 1 2 3 4 5 6))) ///
    (point points if is_village==1, mcolor(gs6) msize(0.5)) ///
    (point points if is_market==1,  mcolor(red) msize(0.5)) ///
    , title("Food vs Durables flows") graphregion(color(white)) ///
    glegend(layout(3 "Food" . 4 "Durables" . 5 "Village" . 6 "Market" )) ///
    name(map_food_dur_noblant, replace)

geoplot ///
    (area chira_btyre, fcolor(white) lcolor(black) lwidth(medthick)) ///
    (area ta_bounds,  fcolor(none)  lcolor(gs10)  lwidth(vthin)) ///
    (pcspike flows_food line_w, coordinates(x1 y1 x2 y2) lcolor(navy%10) cuts(0 1 2 3 4 5 6 7) lwidth(0.05 1) label(,drop(0 1 2 3 4 5 6))) ///
    (pcspike flows_dur line_w,  coordinates(x1 y1 x2 y2) lcolor(cranberry%10) cuts(0 1 2 3 4 5 6 7) lwidth(0.05 1) label(,drop(0 1 2 3 4 5 6))) ///
    (point points if is_village==1, mcolor(gs6) msize(0.5)) ///
    (point points if is_market==1,  mcolor(red) msize(0.5)) ///
	(point blantyre_pt, mcolor(black) msymbol(D) msize(1)) ///
    , title("Food vs Durables flows") graphregion(color(white)) ///
    glegend(layout(3 "Food" . 4 "Durables" . 5 "Village" . 6 "Market" . 7 "Blantyre")) ///
    name(map_food_dur, replace)

/********************************************************************
  10) Export individual + combined
********************************************************************/
graph export "`OUT_DIR'/map_food_nonfood.png", name(map_food_nonfood_noblant) width(2000) replace
graph export "`OUT_DIR'/map_food_dur.png", name(map_food_dur_noblant) width(2000) replace

graph combine map_food_nonfood_noblant map_food_dur_noblant, ///
    rows(1) xsize(16) ysize(8) ///
    graphregion(color(white))
	
// graph export "`OUT_DIR'/combined_flows.png", replace width(3000)

/// How correlated are these flows_dur

* ── Rebuild collapsed frames with a shared key ──────────────────────
foreach cat in food nonfood dur {
    use "$DATA/Phase 1 household baseline/consumption_links_geo.dta", clear

    if "`cat'" == "food"    keep if regexm(stub, "^s5_fe_")
    if "`cat'" == "nonfood" {
        keep if regexm(stub, "^s5_nonfe_")
        foreach s of local dur_stubs { 
			drop if stub == "`s'" 
		}
    }
    if "`cat'" == "dur" keep if inlist(stub, "s5_nonfe_vehic","s5_nonfe_furnit", ///
        "s5_nonfe_carpets","s5_nonfe_hhequip","s5_nonfe_elecequip")

    keep if inlist(dest_point_type, 1, 2)
    collapse (sum) spent_`cat' = spent_amt_w n_`cat' = n_hh (mean) dist_km, ///
        by(origin_node dest_node)
    tempfile `cat'_flows
    save ``cat'_flows'
}

* ── Merge on OD pair ────────────────────────────────────────────────
use `food_flows', clear
merge 1:1 origin_node dest_node using `nonfood_flows', nogen
merge 1:1 origin_node dest_node using `dur_flows',    nogen

* ── Fill in missing OD pairs with zeros ─────────────────────────────
fillin origin_node dest_node
foreach v of varlist spent_food spent_nonfood spent_dur n_food n_nonfood n_dur {
    replace `v' = 0 if missing(`v')
}
drop _fillin

* ── Correlations ────────────────────────────────────────────────────
pwcorr spent_food spent_nonfood spent_dur dist_km, obs sig star(0.05)
spearman spent_food spent_nonfood spent_dur dist_km

keep if spent_food>0 | spent_nonfood>0 | spent_dur>0
pwcorr spent_food spent_nonfood spent_dur dist_km

