# Stress test: Plumb API folder (project) mode

Endpoint: POST http://localhost:8000/api/building (timeout 900 s). Dataset root: ~/Downloads/junction-dataset-preview.
Health before: 200 `{"status":"ok","engine":"pipeline"}`. Health after every request: 200.
Raw responses and analysis: scratchpad `resp/*.body`, `analysis.txt`. Method per folder is "reasoning model (strong)" for all.
Files skipped: LICENSE.md, .DS_Store. Sizes are `find -L` file counts.

## Per-folder results

| # | Folder | HTTP | Sec | Files req / classified | Floors (display_label, level) | doc_type counts | Notes |
|---|---|---|---|---|---|---|---|
| 1 | od/3_Offices | 200 | 7.2 | 1 / 1 | Pre-permit demolition and lighting layout, None | floor_plan 1 | 1 plan without storey, shown one at a time |
| 1 | od/Aalseth_Residence | 200 | 14.8 | 7 / 7 | none | bim_model 1, specification 1, other 2, schedule 1, cad_drawing 2 | none |
| 1 | od/Asbuilts_for_Small_Apartment | 200 | 8.6 | 2 / 2 | none | other 1, cad_drawing 1 | none |
| 1 | od/CTR | 200 | 28.2 | 11 / 11 | 1st FLOOR, 0 | floor_plan 1, specification 1, enlarged_plan 2, schedule 2, site_plan 1, render_3d 1, cad_drawing 2, elevation 1 | none |
| 1 | od/Crema_Cafe | 200 | 11.2 | 4 / 4 | none | elevation 3, other 1 | none |
| 1 | od/Facilities_Building | 200 | 28.1 | 7 / 7 | none | bim_model 1, site_plan 2, cad_drawing 4 | none |
| 1 | od/Lake_Kegonsa_Home | 200 | 14.2 | 3 / 3 | none | cad_drawing 1, elevation 1, other 1 | none |
| 1 | od/Lake_Mills_Basement_Renovation | 200 | 8.7 | 1 / 1 | Basement, -1 | floor_plan 1 | none |
| 1 | od/LaundryMat | 200 | 13.8 | 2 / 2 | Demolition and Equipment Plan, None | floor_plan 1, cad_drawing 1 | 1 plan without storey, shown one at a time |
| 1 | od/Oakfire_2.0 | 200 | 4.1 | 1 / 1 | none | cad_drawing 1 | none |
| 1 | od/Open_Source_Metal_Building | 200 | 4.6 | 1 / 1 | Warehouse Floor Plan, None | floor_plan 1 | 1 plan without storey |
| 1 | od/Schultz_Residence | 200 | 17.3 | 1 / 1 | none | detail 1 | none |
| 1 | od/Screened_in_Porch | 200 | 7.6 | 1 / 1 | none | cad_drawing 1 | none |
| 1 | od/Sports_Complex | 200 | 27.3 | 27 / 27 | Floor Plan and Door Schedule (2015-07-20), None | floor_plan 1, bim_model 2, render_3d 1, section 1, detail 5, enlarged_plan 1, schedule 2, site_plan 4, foundation_plan 2, cad_drawing 7, elevation 1 | 1 plan without storey |
| 1 | od/ULI-44_E_Mifflin-Suite_802 | 200 | 5.2 | 1 / 1 | none | bim_model 1 | none |
| 1 | od/Vacation_Rental | 200 | 30.5 | 11 / 11 | none | foundation_plan 1, detail 6, schedule 2, enlarged_plan 1, other 1 | none |
| 2 | data/ifc_models | 200 | 135.8 | 10 / 10 | Kælder, -1 ; 4.korrus, 3 | floor_plan 6, bim_model 4 | 2 same-storey duplicates; 2 plans without storey kept out of stack (Dachgeschoss PDF and SVG) |
| 3 | swiss site1138_bldg2292 (3 files, 1.59 MB) | 200 | 22.2 | 3 / 3 | Level 3, 3 | floor_plan 2, cad_drawing 1 | 2 same-storey duplicates |
| 3 | swiss site1015_bldg2113 (3 files, 1.23 MB) | 200 | 21.1 | 3 / 3 | Apartment floor plan – raster export, None | floor_plan 2, cad_drawing 1 | 2 plans without storey kept out of stack |
| 4 | junk (3 cubicasa png, 2 wikimedia jpg, 1 swiss pdf, 1 ifc) | 200 | 24.1 | 7 / 7 | 1. UG, -1 | floor_plan 4, photo 2, bim_model 1 | 3 plans without storey kept out of stack |
| 5 | empty (files: []) | 200 | 0.03 | 0 / 0 | none | none | method "reasoning model (strong): 0/0 files" |
| 5 | missing path (data/does_not_exist_folder/x.pdf) | 200 | 2.2 | 1 / 1 | none | other 1 | building "Unknown building project; no identifying information provided"; file labelled "Unidentified PDF" |

## Sanity findings

- No render, section, schedule, elevation, or detail was ever stacked as a floor. Every floor entry across all runs is `floor_plan`.
- Floor levels look plausible: Kælder -1, Lake Mills Basement -1, swiss "1. UG" -1, "Level 3" 3, "4.korrus" 3, CTR "1st FLOOR" 0.
- No file went missing from output. Every requested name appears in floors, alternatives, or other.
- No 5xx and no crashes. The server stayed healthy throughout.

## Problems

1. Missing path returns 200, not an error. The API invented a building and a classification (`Unknown building project`, `Unidentified PDF`, doc_type other) for a file that does not exist. Medium to high severity: the API should reject or report unreadable paths.
2. Empty folder returns 200 and calls the reasoning model with 0 files. Harmless but wasteful, and it does not return a clear "no files" note.
3. Aalseth "2019-022- Aalseth Residence - Revised Framing.pdf" is labelled "Revised Framing Invoice". The word "Invoice" is not in the filename. Possibly an invented label; not verified against the PDF content.
4. IFC folder: kit-fzk-haus "Dachgeschoss" (attic) plans have no storey and are kept out of the stack. Intentional per the notes, but the attic plan is not shown as a floor.
5. Duplicates: the same storey appears twice in ifc_models (level -1 and level 3) and in swiss site1138 (level 3). Handled by the "newest is used" rule with the rest as alternatives.
6. Opening_design: 16 project folders were tested rather than ~10, because the directory has 16 project subfolders.
7. Swiss group choice: the 2 largest groups were picked by total bytes. All groups had 3 files, so this was an assumption.

Server status: stayed up. Health was 200 after every request.
