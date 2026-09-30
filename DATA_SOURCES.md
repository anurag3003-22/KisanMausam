# Data sources and honesty notes

## Panchayat directory (`public/data/`)
Built by `scripts/build_data.py` from two open datasets packaged by
[ramSeraph/indian_admin_boundaries](https://github.com/ramSeraph/indian_admin_boundaries) (licence: CC0 1.0, please attribute DataMeet and the original government source):

| Layer | Original source | Used for |
|---|---|---|
| `LGD_panchayats` | LGD / Bharatmaps Gram Panchayat boundaries | 25 states/UTs, real **LGD codes** |
| `bhuvan_panchayats` | Bhuvan Panchayat, NRSC/ISRO (SIS-DP) | Only states missing from the LGD layer: Himachal Pradesh, Jammu & Kashmir, Sikkim, Meghalaya, Mizoram, Manipur, Nagaland, Arunachal Pradesh (codes shown as `B<code>`, they are **not** LGD codes) |

Result: **236,308 named Panchayats in 33 states/UTs**.

### Known gaps (nothing was invented to fill them)
* About 53,000 polygons in the LGD layer have **no name or LGD code** in the source and are skipped. Because of that some states have fewer Panchayats than official counts (for example Delhi, Chandigarh and Ladakh have none; Kerala, West Bengal and Rajasthan are a little short).
* Bhuvan-sourced states may not match LGD names or counts, and Meghalaya's layer reflects village councils rather than Gram Panchayats.
* A Panchayat's map position is a point inside its boundary (`point_on_surface` of its largest polygon), not the official centroid. `area_km2` is approximate.
* Urban local bodies are not Panchayats and are not included.

To close the gaps, export the official list from https://lgdirectory.gov.in and run
`python scripts/build_data.py --csv your.csv` (columns: state,district,block,panchayat,code,lat,lng).

## Weather
[Open-Meteo](https://open-meteo.com) (free for non-commercial use, no API key). The ECMWF IFS model is requested as a second opinion for the confidence range.
Re-check Open-Meteo's terms before any commercial deployment.

## Advice rules
`server/advisory_rules.json` (thresholds and messages) and `server/crop_advice.json` (crop tips). Rain bands follow IMD categories. **Have a KVK / agriculture expert review these before real-world use.**
