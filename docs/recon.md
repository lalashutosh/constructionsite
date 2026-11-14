# Dataset reconnaissance

Root: `/tmp/mockds`  ·  rows: 7990

## Questions by source x type

| source | type | n |
|---|---|---|
| cubicasa5k | count | 4270 |
| ifc_bench | text | 249 |
| ifc_models | area | 846 |
| ifc_models | count | 153 |
| ifc_models | length | 16 |
| ifc_models | volume | 34 |
| opening_design | area | 9 |
| opening_design | count | 39 |
| opening_design | text | 16 |
| swiss_dwellings | area | 744 |
| swiss_dwellings | count | 1614 |

## File extensions of question paths

.png: 4270, .pdf: 2644, .ifc: 1076

## Question templates (digits -> #), most frequent first, per source

### cubicasa5k

| n | type | template | answers min / median / max | share 0 |
|---|---|---|---|---|
| 241 | count | How many windows are shown on this floor plan? | 0 / 6 / 44 | 0% |
| 241 | count | Kuinka monta ikkunaa pohjapiirustuksessa on? | 0 / 6 / 44 | 0% |
| 241 | count | How many floors (storeys) does this floor plan show? | 1 / 1 / 4 | 0% |
| 241 | count | Kuinka monta kerrosta pohjapiirustuksessa on esitetty? | 1 / 1 / 4 | 0% |
| 240 | count | How many toilet bowls (WC seats) are drawn on this floor plan? | 0 / 1.0 / 4 | 5% |
| 240 | count | Kuinka monta WC-istuinta pohjapiirustukseen on piirretty? | 0 / 1.0 / 4 | 5% |
| 239 | count | How many sinks and wash basins (kitchen and bathroom combined; a double-bowl sink counts as one) are drawn on this floor plan? | 0 / 2 / 6 | 3% |
| 239 | count | Kuinka monta pesu- ja tiskiallasta (keittiö ja kylpytilat yhteensä; kaksoisallas lasketaan yhdeksi) pohjapiirustukseen on piirretty? | 0 / 2 / 6 | 3% |
| 227 | count | How many showers and bathtubs are drawn on this floor plan in total? | 0 / 1 / 6 | 6% |
| 227 | count | Kuinka monta suihkua ja kylpyammetta pohjapiirustukseen on piirretty yhteensä? | 0 / 1 / 6 | 6% |
| 176 | count | How many doors are shown on this floor plan? Count doorways fitted with a door; open doorways without a door leaf do not count. | 2 / 7.0 / 26 | 0% |
| 176 | count | Kuinka monta ovea pohjapiirustuksessa on? Laske oviaukot, joissa on ovi; pelkkiä oviaukkoja ilman ovilehteä ei lasketa. | 2 / 7.0 / 26 | 0% |
| 165 | count | How many saunas are on this floor plan? | 0 / 1 / 2 | 44% |
| 165 | count | Kuinka monta saunaa pohjapiirustuksessa on? | 0 / 1 / 2 | 44% |
| 161 | count | How many kitchens (including kitchenettes, open kitchens and utility kitchens) are on this floor plan? | 0 / 1 / 2 | 2% |
| 161 | count | Kuinka monta keittiötä (myös keittokomerot, avo- ja tupakeittiöt sekä apukeittiöt) pohjapiirustuksessa on? | 0 / 1 / 2 | 2% |
| 154 | count | How many bedrooms (makuuhuone, usually marked MH) are on this floor plan? | 0 / 2.0 / 8 | 17% |
| 154 | count | Kuinka monta makuuhuonetta (MH) pohjapiirustuksessa on? | 0 / 2.0 / 8 | 17% |
| 112 | count | How many separate WC rooms (toilet rooms marked WC) are on this floor plan? | 0 / 0.0 / 2 | 61% |
| 112 | count | Kuinka monta erillistä WC-tilaa pohjapiirustuksessa on? | 0 / 0.0 / 2 | 61% |
| 111 | count | How many bathrooms or washrooms (e.g. KH, KPH, PH, PESUH, SH) are on this floor plan, not counting separate WC rooms? | 0 / 1 / 4 | 7% |
| 111 | count | Kuinka monta kylpy- tai pesuhuonetta (esim. KH, KPH, PH, PESUH, SH) pohjapiirustuksessa on, erillisiä WC-tiloja lukuun ottamatta? | 0 / 1 / 4 | 7% |
| 68 | count | How many balconies (parveke, including glazed balconies) are on this floor plan? | 0 / 0.0 / 2 | 57% |
| 68 | count | Kuinka monta parveketta (myös lasitetut parvekkeet) pohjapiirustuksessa on? | 0 / 0.0 / 2 | 57% |

### ifc_bench

| n | type | template | answers min / median / max | share 0 |
|---|---|---|---|---|
| 4 | text | What are all the spaces on level #, with their areas? | (text) |  |
| 3 | text | What are all the spaces on level #, grouped by function with their areas? | (text) |  |
| 2 | text | Which room in the building is the largest? | (text) |  |
| 2 | text | What spaces are on Level E#_OKRD, with their room names and areas? | (text) |  |
| 2 | text | How many MEP components are there by system type? | (text) |  |
| 2 | text | What is the total length of exterior walls? | (text) |  |
| 2 | text | What is the total volume of all floor slabs combined? | (text) |  |
| 1 | text | What is the building's type and its function? | (text) |  |
| 1 | text | What software and ifc standards were used to create this model? | (text) |  |
| 1 | text | What are the number of levels, building footprint area, total floor area, and total number of rooms/spaces? | (text) |  |
| 1 | text | What is the space distribution by level with areas and primary space functions with percentages? | (text) |  |
| 1 | text | What is the space breakdown of the basement floor grouped by function with areas? | (text) |  |
| 1 | text | What is the space breakdown of the ground level grouped by function with areas? | (text) |  |
| 1 | text | What is the space breakdown of the first floor grouped by function with areas? | (text) |  |
| 1 | text | What is the space breakdown of the second level grouped by function with areas? | (text) |  |
| 1 | text | What is the space breakdown of the attic floor with areas? | (text) |  |
| 1 | text | What are the heights of each level? | (text) |  |
| 1 | text | Which door types are installed in this building with quantities? | (text) |  |
| 1 | text | Which two doors have the greatest widths in the building? | (text) |  |
| 1 | text | What is the narrowest door width used here? | (text) |  |
| 1 | text | Which window types are present in the building and how many of each? | (text) |  |
| 1 | text | What is the widest window in the building? | (text) |  |
| 1 | text | What is the narrowest window width used in this building? | (text) |  |
| 1 | text | What wall types are present in the building and how many of each? | (text) |  |
| 1 | text | Which wall types are used on the exterior side of the building and how many of each? | (text) |  |
| 1 | text | Could you provide me with a list of all the different types of interior wall in the building and how many of each type there are? | (text) |  |
| 1 | text | Which materials are used to construct the walls and their usage across wall types? | (text) |  |
| 1 | text | What materials are applied in the outer walls and their distribution across wall types? | (text) |  |
| 1 | text | What materials are found in the internal walls and their distribution across wall types? | (text) |  |
| 1 | text | What are the thicknesses of the various wall types? | (text) |  |
| 1 | text | How many of the walls are load-bearing compared with non-load-bearing? | (text) |  |
| 1 | text | What is the total combined length of inside walls? | (text) |  |
| 1 | text | What is the total length of outside walls? | (text) |  |
| 1 | text | What is the building's total net usable floor area with the breakdown by level? | (text) |  |
| 1 | text | Which coverings are applied throughout the building? | (text) |  |
| 1 | text | Which ceiling materials are used in the building? | (text) |  |
| 1 | text | What furniture items are present inside the building including quantities for each type? | (text) |  |
| 1 | text | Which sanitary fixtures are available in this building? | (text) |  |
| 1 | text | How many toilets exist on the ground floor? | (text) |  |
| 1 | text | Which stair types are used here with quantities? | (text) |  |
| 1 | text | What is the total volume of the slabs with the breakdown by slab type? | (text) |  |
| 1 | text | Which railing types are installed in the building? | (text) |  |
| 1 | text | Which rooms have the tallest ceilings? | (text) |  |
| 1 | text | Which types of doors include fire rating details? | (text) |  |
| 1 | text | Which windows have fire rating information? | (text) |  |
| 1 | text | Which structural components exist in this building? | (text) |  |
| 1 | text | Which beams are used in the building? | (text) |  |
| 1 | text | Which column types are present here and how many of each? | (text) |  |
| 1 | text | What are the sizes of the columns? | (text) |  |
| 1 | text | Which slab types are present with quantities and thicknesses? | (text) |  |
| 1 | text | Which roof structure elements are used? | (text) |  |
| 1 | text | Which MEP systems are installed in this building? | (text) |  |
| 1 | text | What types of pipes are used in the building? | (text) |  |
| 1 | text | Which heating systems are included in this building? | (text) |  |
| 1 | text | What type of building is this and where is it situated? | (text) |  |
| 1 | text | What is the building's total floor area, number of levels, total spaces, and program breakdown by floor? | (text) |  |
| 1 | text | Which software tools and modeling standards were applied? | (text) |  |
| 1 | text | What is the complete space breakdown for all building levels, listing room names and areas? | (text) |  |
| 1 | text | What spaces are on Level B#_OKRD, with their room names and areas? | (text) |  |
| 1 | text | What are the dimensions and parking capacity of the lot? | (text) |  |

### ifc_models

| n | type | template | answers min / median / max | share 0 |
|---|---|---|---|---|
| 80 | area | What is the net floor area of the room 'ELUTUBA+KÖÖK (#-#)' on '#.korrus', in m²? | 20.3 / 25.25 / 28.3 | 0% |
| 80 | area | Kui suur on ruumi „ELUTUBA+KÖÖK (#-#)“ netopõrandapind korrusel „#.korrus“ (m²)? | 20.3 / 25.25 / 28.3 | 0% |
| 80 | area | What is the net floor area of the room 'TUALETTRUUM (#-#)' on '#.korrus', in m²? | 4.2 / 5.58 / 6.24 | 0% |
| 80 | area | Kui suur on ruumi „TUALETTRUUM (#-#)“ netopõrandapind korrusel „#.korrus“ (m²)? | 4.2 / 5.58 / 6.24 | 0% |
| 80 | area | What is the net floor area of the room 'ESIK (#-#)' on '#.korrus', in m²? | 3.01 / 5.1 / 7.73 | 0% |
| 80 | area | Kui suur on ruumi „ESIK (#-#)“ netopõrandapind korrusel „#.korrus“ (m²)? | 3.01 / 5.1 / 7.73 | 0% |
| 30 | area | What is the net floor area of the room 'Kontor (Rum nr. #)' on '#. Sal', in m²? | 10.43 / 19.439999999999998 / 70.19 | 0% |
| 30 | area | Hvad er nettoarealet af rummet 'Kontor (Rum nr. #)' på '#. Sal' i m²? | 10.43 / 19.439999999999998 / 70.19 | 0% |
| 15 | area | What is the net floor area of the room 'Toilet (Rum nr. #)' on '#. Sal', in m²? | 3.96 / 4.07 / 5.83 | 0% |
| 15 | area | Hvad er nettoarealet af rummet 'Toilet (Rum nr. #)' på '#. Sal' i m²? | 3.96 / 4.07 / 5.83 | 0% |
| 10 | area | What is the net floor area of the room 'KORIDOR (#)' on '#.korrus', in m²? | 63.84 / 71.12 / 78.4 | 0% |
| 10 | area | Kui suur on ruumi „KORIDOR (#)“ netopõrandapind korrusel „#.korrus“ (m²)? | 63.84 / 71.12 / 78.4 | 0% |
| 5 | count | How many doors are shown on the floor plan of '#.korrus'? | 39 / 42 / 46 | 0% |
| 5 | count | Mitu ust on näidatud korruse „#.korrus“ plaanil? | 39 / 42 / 46 | 0% |
| 5 | count | How many rooms (spaces) are shown on the floor plan of '#.korrus'? | 50 / 60 / 60 | 0% |
| 5 | count | Mitu ruumi on näidatud korruse „#.korrus“ plaanil? | 50 / 60 / 60 | 0% |
| 5 | area | What is the total net floor area of all rooms (spaces) on '#.korrus', in m²? | 857.18 / 859.31 / 870.29 | 0% |
| 5 | area | Kui suur on kõigi ruumide netopõrandapind kokku korrusel „#.korrus“ (m²)? | 857.18 / 859.31 / 870.29 | 0% |
| 5 | area | What is the net floor area of the room 'ABIRUUM (#)' on '#.korrus', in m²? | 3.98 / 3.98 / 22.4 | 0% |
| 5 | area | Kui suur on ruumi „ABIRUUM (#)“ netopõrandapind korrusel „#.korrus“ (m²)? | 3.98 / 3.98 / 22.4 | 0% |
| 5 | count | How many doors are shown on the floor plan of '#. Sal'? | 15 / 18 / 18 | 0% |
| 5 | count | Hvor mange døre er vist på plantegningen for '#. Sal'? | 15 / 18 / 18 | 0% |
| 5 | count | How many walls are shown on the floor plan of '#. Sal'? | 26 / 26 / 26 | 0% |
| 5 | count | Hvor mange vægge er vist på plantegningen for '#. Sal'? | 26 / 26 / 26 | 0% |
| 5 | count | How many columns are shown on the floor plan of '#. Sal'? | 2 / 2 / 2 | 0% |
| 5 | count | Hvor mange søjler er vist på plantegningen for '#. Sal'? | 2 / 2 / 2 | 0% |
| 5 | area | What is the net floor area of the room 'Skakt (Rum nr. #)' on '#. Sal', in m²? | 2.21 / 2.21 / 2.21 | 0% |
| 5 | area | Hvad er nettoarealet af rummet 'Skakt (Rum nr. #)' på '#. Sal' i m²? | 2.21 / 2.21 / 2.21 | 0% |
| 5 | area | What is the net floor area of the room 'Teknikrum (Rum nr. #)' on '#. Sal', in m²? | 10.38 / 10.38 / 10.38 | 0% |
| 5 | area | Hvad er nettoarealet af rummet 'Teknikrum (Rum nr. #)' på '#. Sal' i m²? | 10.38 / 10.38 / 10.38 | 0% |
| 5 | area | What is the net floor area of the room 'Gang (Rum nr. #)' on '#. Sal', in m²? | 179.23 / 179.23 / 179.23 | 0% |
| 5 | area | Hvad er nettoarealet af rummet 'Gang (Rum nr. #)' på '#. Sal' i m²? | 179.23 / 179.23 / 179.23 | 0% |
| 5 | area | What is the net floor area of the room 'Tekøkken (Rum nr. #)' on '#. Sal', in m²? | 4.48 / 4.48 / 4.48 | 0% |
| 5 | area | Hvad er nettoarealet af rummet 'Tekøkken (Rum nr. #)' på '#. Sal' i m²? | 4.48 / 4.48 / 4.48 | 0% |
| 5 | area | What is the net floor area of the room 'Lounge (Rum nr. #)' on '#. Sal', in m²? | 26.65 / 26.65 / 31.67 | 0% |
| 5 | area | Hvad er nettoarealet af rummet 'Lounge (Rum nr. #)' på '#. Sal' i m²? | 26.65 / 26.65 / 31.67 | 0% |
| 5 | area | What is the total net floor area of all rooms (spaces) on '#. Sal', in m²? | 416.62 / 523.09 / 530.03 | 0% |
| 5 | area | Hvad er det samlede nettoareal af alle rum på '#. Sal' i m²? | 416.62 / 523.09 / 530.03 | 0% |
| 5 | length | What is the total length of all walls on '#. Sal', in metres? | 222.79 / 229.413 / 229.513 | 0% |
| 5 | length | Hvad er den samlede længde af alle vægge på '#. Sal' i meter? | 222.79 / 229.413 / 229.513 | 0% |
| 5 | area | What is the total net side area of all walls on '#. Sal', in m²? | 643.917 / 665.07 / 726.8 | 0% |
| 5 | area | Hvad er det samlede nettosideareal af alle vægge på '#. Sal' i m²? | 643.917 / 665.07 / 726.8 | 0% |
| 5 | volume | What is the total net volume of all walls on '#. Sal', in m³? | 207.502 / 211.462 / 245.702 | 0% |
| 5 | volume | Hvad er det samlede nettovolumen af alle vægge på '#. Sal' i m³? | 207.502 / 211.462 / 245.702 | 0% |
| 5 | volume | What is the total net volume of all slabs on '#. Sal', in m³? | 146.572 / 188.989 / 189.023 | 0% |
| 5 | volume | Hvad er det samlede nettovolumen af alle dæk og plader på '#. Sal' i m³? | 146.572 / 188.989 / 189.023 | 0% |
| 4 | count | How many stairs are shown on the floor plan of '#.korrus'? | 1 / 1.0 / 1 | 0% |
| 4 | count | Mitu treppi on näidatud korruse „#.korrus“ plaanil? | 1 / 1.0 / 1 | 0% |
| 4 | area | What is the net floor area of the room 'TREPIKODA (#)' on '#.korrus', in m²? | 45.5 / 45.5 / 45.5 | 0% |
| 4 | area | Kui suur on ruumi „TREPIKODA (#)“ netopõrandapind korrusel „#.korrus“ (m²)? | 45.5 / 45.5 / 45.5 | 0% |
| 4 | area | What is the net floor area of the room 'MAGAMISTUBA (#-#)' on '#.korrus', in m²? | 18.5 / 18.5 / 18.5 | 0% |
| 4 | area | Kui suur on ruumi „MAGAMISTUBA (#-#)“ netopõrandapind korrusel „#.korrus“ (m²)? | 18.5 / 18.5 / 18.5 | 0% |
| 4 | count | How many windows are shown on the floor plan of '#. Sal'? | 20 / 20.0 / 20 | 0% |
| 4 | count | Hvor mange vinduer er vist på plantegningen for '#. Sal'? | 20 / 20.0 / 20 | 0% |
| 4 | count | How many rooms (spaces) are shown on the floor plan of '#. Sal'? | 17 / 17.0 / 18 | 0% |
| 4 | count | Hvor mange rum er vist på plantegningen for '#. Sal'? | 17 / 17.0 / 18 | 0% |
| 4 | area | What is the net floor area of the room 'Møderum (Rum nr. #)' on '#. Sal', in m²? | 67.51 / 67.51 / 67.51 | 0% |
| 4 | area | Hvad er nettoarealet af rummet 'Møderum (Rum nr. #)' på '#. Sal' i m²? | 67.51 / 67.51 / 67.51 | 0% |
| 4 | area | What is the net floor area of the room 'Depot (Rum nr. #)' on '#. Sal', in m²? | 9.85 / 9.85 / 9.85 | 0% |
| 4 | area | Hvad er nettoarealet af rummet 'Depot (Rum nr. #)' på '#. Sal' i m²? | 9.85 / 9.85 / 9.85 | 0% |

### opening_design

| n | type | template | answers min / median / max | share 0 |
|---|---|---|---|---|
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors (door numbers) are listed in the door schedule? | 38 / 38 / 38 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule are door type A# (swing door)? | 14 / 14 / 14 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule are door type A# (double swing door)? | 1 / 1 / 1 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule are door type B# (aluminium door with glazing)? | 9 / 9 / 9 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule are door type B# (double aluminium door with glazing)? | 10 / 10 / 10 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule are door type B# (aluminium sliding door)? | 1 / 1 / 1 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule are door type C# (roll-up insulated door)? | 1 / 1 / 1 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule have a wood solid core door (material WD-#)? | 13 / 13 / 13 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule have an interior-grade hollow metal frame (STL-#)? | 13 / 13 / 13 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule have aluminium storefront frames (AL-# or AL-#)? | 17 / 17 / 17 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule carry note A (wide stile)? | 10 / 10 / 10 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule carry note B (opens #°)? | 4 / 4 / 4 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule carry note C (card reader)? | 5 / 5 / 5 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule are #'-#" wide? | 8 / 8 / 8 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors in the door schedule are #'-#" high? | 13 / 13 / 13 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors does the door schedule list for room # (Fitness Center)? | 5 / 5 / 5 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many doors does the door schedule list for room # (Fieldhouse)? | 5 / 5 / 5 | 0% |
| 1 | text | On sheet A-# of the Xcel Sports Complex drawings, what is the width of door #.A? | (text) |  |
| 1 | text | On sheet A-# of the Xcel Sports Complex drawings, what door type is door #.A, and what kind of door is that? | (text) |  |
| 1 | text | On sheet A-# of the Xcel Sports Complex drawings, what are the width and height of door #.B? | (text) |  |
| 1 | text | On sheet A-# of the Xcel Sports Complex drawings, which hardware group is specified for door #.A? | (text) |  |
| 1 | text | On sheet A-# of the Xcel Sports Complex drawings, what door material is specified for door #.A? | (text) |  |
| 1 | text | On sheet A-# of the Xcel Sports Complex drawings, what is the height of the four doors of type B# that serve the Fitness Center (#.A#-#.B#)? | (text) |  |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many rooms are listed in the finish room schedule? | 29 / 29 / 29 | 0% |
| 1 | area | On sheet A-# of the Xcel Sports Complex drawings, what is the area of room # (Fieldhouse) in the finish room schedule? | 29690 / 29690 / 29690 | 0% |
| 1 | area | On sheet A-# of the Xcel Sports Complex drawings, what is the area of room # (Fitness Center) in the finish room schedule? | 5183 / 5183 / 5183 | 0% |
| 1 | area | On sheet A-# of the Xcel Sports Complex drawings, what is the area of room # (Wrestling) in the finish room schedule? | 3814 / 3814 / 3814 | 0% |
| 1 | area | On sheet A-# of the Xcel Sports Complex drawings, what is the area of room # (Clinic) in the finish room schedule? | 2470 / 2470 / 2470 | 0% |
| 1 | area | On sheet A-# of the Xcel Sports Complex drawings, what is the total area of all rooms that have an area listed in the finish room schedule? | 49560 / 49560 / 49560 | 0% |
| 1 | area | On sheet A-# of the Xcel Sports Complex drawings, what is the total area of the rooms named OFFICE in the finish room schedule? | 816 / 816 / 816 | 0% |
| 1 | area | On sheet A-# of the Xcel Sports Complex drawings, what is the total area of the rooms named RESTROOM in the finish room schedule? | 193 / 193 / 193 | 0% |
| 1 | area | On sheet A-# of the Xcel Sports Complex drawings, what is the combined area of the women's and men's locker rooms? | 1181 / 1181 / 1181 | 0% |
| 1 | text | On sheet A-# of the Xcel Sports Complex drawings, how many rooms have floor finish F# (unfinished concrete slab), and what is their total ar | (text) |  |
| 1 | area | On sheet A-# of the Xcel Sports Complex drawings, what is the total area of rooms with floor finish F# (resilient flooring)? | 4769 / 4769 / 4769 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many rooms have a ceramic tile base (B#)? | 5 / 5 / 5 | 0% |
| 1 | count | On sheet A-# of the Xcel Sports Complex drawings, how many rooms have all four walls finished with W# (painted gypsum board)? | 6 / 6 / 6 | 0% |
| 1 | text | On sheet A-# of the Xcel Sports Complex drawings, what is the floor finish of room # (Aerobics & Yoga), and what does it mean? | (text) |  |
| 1 | text | On sheet A-# of the Xcel Sports Complex drawings, what floor finishes are scheduled for the Fieldhouse (room #)? | (text) |  |
| 1 | text | On sheet A-# of the Xcel Sports Complex drawings, what is the ceiling finish of the Fieldhouse (room #)? | (text) |  |
| 1 | text | On sheet A-# of the Xcel Sports Complex drawings, what is the north wall finish of the Fitness Center (room #)? | (text) |  |
| 1 | text | On sheet A-# of the Xcel Sports Complex drawings, which room in the finish room schedule has the largest area? | (text) |  |
| 1 | count | On sheet A-# (Restrooms) of the Xcel Sports Complex drawings, how many water closets are drawn in enlarged plan #A 'Restrooms'? | 2 / 2 / 2 | 0% |
| 1 | count | On sheet A-# (Restrooms) of the Xcel Sports Complex drawings, how many lavatories are drawn inside the two restrooms of enlarged plan #A? | 2 / 2 / 2 | 0% |
| 1 | text | On sheet A-# (Restrooms) of the Xcel Sports Complex drawings, how many water closets, lavatories and showers are drawn in enlarged plan #B ' | (text) |  |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many unit entry doors (type U#) are scheduled? | 71 / 71 / 71 | 0% |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many #'-#" x #'-#" privacy swing doors (type U#)  | 256 / 256 / 256 | 0% |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many Marvin Essential sliding patio doors are sch | 27 / 27 / 27 | 0% |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many Marvin Essential sliding patio doors are sch | 15 / 15 / 15 | 0% |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many Vistagrande fiberglass entry doors are sched | 19 / 19 / 19 | 0% |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many doors with an acoustical seal (type U#) are  | 52 / 52 / 52 | 0% |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many items in total are counted in the door type  | 657 / 657 / 657 | 0% |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many door leaves of the types whose description s | 418 / 418 / 418 | 0% |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many sliding flush wood doors (types U# and U#) a | 65 / 65 / 65 | 0% |
| 1 | text | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), what fire rating is scheduled for the unit doors (typ | (text) |  |
| 1 | text | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), what frame material is scheduled for the unit doors ( | (text) |  |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many chain-link gates (type U#) are scheduled? | 15 / 15 / 15 | 0% |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many windows (window assemblies) are listed in th | 235 / 235 / 235 | 0% |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many windows of type SS (#-WIDE (TEMP ALL LOW) ES | 118 / 118 / 118 | 0% |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many windows of type RR (#-WIDE (TEMP LOWER) ESDH | 84 / 84 / 84 | 0% |
| 1 | count | On sheet A# of the Cannery Trail Residences drawings (# N Oxford Ave, Eau Claire, WI), how many windows of type QQ (#-WIDE (TEMP ALL) ESDH#) | 16 / 16 / 16 | 0% |

### swiss_dwellings

| n | type | template | answers min / median / max | share 0 |
|---|---|---|---|---|
| 65 | count | How many apartments (residential units) are shown on this floor plan? | 1 / 2 / 15 | 0% |
| 65 | count | How many doors (interior doors and entrance doors together) are drawn on this floor plan? | 5 / 23 / 114 | 0% |
| 65 | count | How many windows are drawn on this floor plan? | 0 / 13 / 69 | 2% |
| 65 | count | How many toilets (WC) are drawn on this floor plan? | 0 / 3 / 15 | 5% |
| 65 | count | How many washbasins are drawn on this floor plan? | 0 / 3 / 33 | 9% |
| 65 | area | What is the total net floor area in m² of all numbered indoor rooms on this floor (excluding balconies, loggias, terraces and other outdoor  | 34.08 / 219.86 / 1275.14 | 0% |
| 56 | count | How many bathtubs are drawn on this floor plan? | 1 / 2.0 / 15 | 0% |
| 48 | area | What is the net floor area of apartment A in m², summing all its rooms except balconies, loggias, terraces and other outdoor spaces? | 25.54 / 76.10499999999999 / 163.78 | 0% |
| 41 | area | What is the net floor area of apartment B in m², summing all its rooms except balconies, loggias, terraces and other outdoor spaces? | 27.17 / 69.84 / 135.38 | 0% |
| 22 | count | Wie viele Wohnungen sind auf diesem Grundriss dargestellt? | 1 / 2.0 / 4 | 0% |
| 22 | count | Wie viele Türen (Innentüren und Eingangstüren zusammen) sind auf diesem Grundriss eingezeichnet? | 5 / 22.5 / 43 | 0% |
| 22 | count | Wie viele Fenster sind auf diesem Grundriss eingezeichnet? | 3 / 10.5 / 28 | 0% |
| 22 | count | Wie viele WCs sind auf diesem Grundriss eingezeichnet? | 1 / 3.0 / 6 | 0% |
| 22 | count | Wie viele Lavabos sind auf diesem Grundriss eingezeichnet? | 1 / 3.0 / 7 | 0% |
| 22 | area | Wie gross ist die gesamte Nettogeschossfläche in m² aller nummerierten Innenräume dieses Geschosses (ohne Balkone, Loggien, Terrassen und an | 49.1 / 199.64 / 341.45 | 0% |
| 22 | count | Combien d'appartements (logements) figurent sur ce plan d'étage ? | 1 / 3.0 / 15 | 0% |
| 22 | count | Combien de portes (portes intérieures et portes d'entrée confondues) sont dessinées sur ce plan ? | 5 / 26.0 / 114 | 0% |
| 22 | count | Combien de fenêtres sont dessinées sur ce plan ? | 0 / 17.0 / 63 | 5% |
| 22 | count | Combien de WC sont dessinés sur ce plan ? | 0 / 3.0 / 15 | 9% |
| 22 | count | Combien de lavabos sont dessinés sur ce plan ? | 0 / 3.5 / 33 | 18% |
| 22 | area | Quelle est la surface nette totale en m² de toutes les pièces intérieures numérotées de cet étage (hors balcons, loggias, terrasses et autre | 34.08 / 257.18 / 925.01 | 0% |
| 21 | count | Quanti appartamenti (unità abitative) sono rappresentati in questa pianta? | 1 / 2 / 10 | 0% |
| 21 | count | How many rooms labelled 'Cucina' are there on this floor? | 1 / 2 / 10 | 0% |
| 21 | count | Quanti locali con la denominazione «Cucina» ci sono in questo piano? | 1 / 2 / 10 | 0% |
| 21 | count | Quante porte (porte interne e porte d'ingresso insieme) sono disegnate in questa pianta? | 6 / 20 / 112 | 0% |
| 21 | count | Quante finestre sono disegnate in questa pianta? | 3 / 13 / 69 | 0% |
| 21 | count | Quanti WC sono disegnati in questa pianta? | 0 / 2 / 13 | 5% |
| 21 | count | Quanti lavabi sono disegnati in questa pianta? | 0 / 3 / 17 | 10% |
| 21 | area | Qual è la superficie netta totale in m² di tutti i locali interni numerati di questo piano (esclusi balconi, logge, terrazze e altri spazi e | 86.11 / 182.97 / 1275.14 | 0% |
| 21 | count | How many rooms labelled 'Küche' are there on this floor? | 1 / 2 / 4 | 0% |
| 21 | count | Wie viele Räume mit der Bezeichnung «Küche» gibt es in diesem Geschoss? | 1 / 2 / 4 | 0% |
| 21 | count | How many rooms labelled 'Bad' are there on this floor? | 1 / 3 / 7 | 0% |
| 21 | count | Wie viele Räume mit der Bezeichnung «Bad» gibt es in diesem Geschoss? | 1 / 3 / 7 | 0% |
| 21 | count | How many rooms labelled 'Korridor' are there on this floor? | 1 / 3 / 7 | 0% |
| 21 | count | Wie viele Räume mit der Bezeichnung «Korridor» gibt es in diesem Geschoss? | 1 / 3 / 7 | 0% |
| 21 | count | How many showers are drawn on this floor plan? | 1 / 2 / 7 | 0% |
| 21 | count | How many rooms labelled 'Couloir' are there on this floor? | 1 / 3 / 19 | 0% |
| 21 | count | Combien de pièces portant la désignation « Couloir » y a-t-il à cet étage ? | 1 / 3 / 19 | 0% |
| 20 | count | How many rooms labelled 'Cuisine' are there on this floor? | 1 / 3.0 / 7 | 0% |
| 20 | count | Combien de pièces portant la désignation « Cuisine » y a-t-il à cet étage ? | 1 / 3.0 / 7 | 0% |
| 19 | count | How many rooms labelled 'Corridoio' are there on this floor? | 1 / 3 / 5 | 0% |
| 19 | count | Quanti locali con la denominazione «Corridoio» ci sono in questo piano? | 1 / 3 / 5 | 0% |
| 19 | count | Quante vasche da bagno sono disegnate in questa pianta? | 1 / 2 / 6 | 0% |
| 19 | count | Wie viele Badewannen sind auf diesem Grundriss eingezeichnet? | 1 / 2 / 5 | 0% |
| 19 | count | How many rooms labelled 'Pièce' are there on this floor? | 1 / 8 / 22 | 0% |
| 19 | count | Combien de pièces portant la désignation « Pièce » y a-t-il à cet étage ? | 1 / 8 / 22 | 0% |
| 18 | count | How many rooms labelled 'Bain' are there on this floor? | 1 / 4.0 / 24 | 0% |
| 18 | count | Combien de pièces portant la désignation « Bain » y a-t-il à cet étage ? | 1 / 4.0 / 24 | 0% |
| 18 | count | Combien de baignoires sont dessinées sur ce plan ? | 1 / 3.0 / 15 | 0% |
| 18 | area | What is the total net area in m² of all rooms labelled 'Pièce' on this floor? | 20.9 / 132.31 / 338.99 | 0% |
| 18 | area | Quelle est la surface nette totale en m² de toutes les pièces désignées « Pièce » à cet étage ? | 20.9 / 132.31 / 338.99 | 0% |
| 17 | area | Wie gross ist die Nettowohnfläche von Wohnung A in m² (Summe aller Räume ohne Balkone, Loggien, Terrassen und andere Aussenräume)? | 40.9 / 72.17 / 132.97 | 0% |
| 16 | count | How many rooms labelled 'Stanza' are there on this floor? | 1 / 6.0 / 22 | 0% |
| 16 | count | Quanti locali con la denominazione «Stanza» ci sono in questo piano? | 1 / 6.0 / 22 | 0% |
| 16 | area | Qual è la superficie netta dell'appartamento A in m² (somma di tutti i locali, esclusi balconi, logge, terrazze e altri spazi esterni)? | 61.49 / 81.75999999999999 / 163.78 | 0% |
| 16 | area | What is the total net area in m² of all rooms labelled 'Stanza' on this floor? | 17.55 / 105.025 / 482.19 | 0% |
| 16 | area | Qual è la superficie netta totale in m² di tutti i locali denominati «Stanza» in questo piano? | 17.55 / 105.025 / 482.19 | 0% |
| 16 | count | How many rooms labelled 'Zimmer' are there on this floor? | 1 / 5.0 / 12 | 0% |
| 16 | count | Wie viele Räume mit der Bezeichnung «Zimmer» gibt es in diesem Geschoss? | 1 / 5.0 / 12 | 0% |
| 16 | area | Wie gross ist die Nettowohnfläche von Wohnung B in m² (Summe aller Räume ohne Balkone, Loggien, Terrassen und andere Aussenräume)? | 27.17 / 61.78 / 104.12 | 0% |

## Files

distinct question paths: 320 · present on disk: 0

