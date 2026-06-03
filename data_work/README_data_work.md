# Data Work Notes

This folder contains the derived aggregate tables used to build the municipal accessibility analysis.

## Main Outputs

- `source_validation_summary.csv`: source existence, size, row/entity counts and hashes when available.
- `municipal_panel_seed_2021_2025.csv`: municipality-year panel for the study period.
- `municipal_month_seed_2021_2025.csv`: municipality-month panel for spatial-accessibility processing.
- `reps_sedes_by_municipio.csv`: REPS-enabled sites by municipality.
- `rips_salud_mental_by_municipio_year.csv`: recorded RIPS mental-health service-use records by municipality-year, 2019-2021.
- `sivigila_intento_suicidio_by_municipio_month.csv`: attempted-suicide notifications by municipality-month, 2021-2024.
- `dane_population_municipality_year_area.csv`: DANE population by municipality, area and year.
- `dane_ipm_departamento_year_domain.csv`: departmental multidimensional poverty indicators, 2018-2025.
- `qa_*_invalid_municipality_codes*.csv`: source codes that do not match the municipal catalog used for the panel.

## Effective Coverage

- Municipality-year panel, 2021-2025: 5,615 rows.
- Municipality-month panel, 2021-2025: 67,380 rows.
- Direct SIVIGILA microdata available locally: 2021-2024. The tested direct endpoint did not provide `Datos_2025_356`.
- Open national RIPS data available locally: 2019-2021.
- REPS installed-capacity data downloaded: 2017-2020. For 2021-2025, the 2020 departmental baseline is retained in `*_baseline` columns and is not treated as a contemporaneous observation.
- REPS site records used here do not provide a complete national geocoded mental-health provider layer.
- The OSM PBF was downloaded, but the OSRM extraction was not completed because local disk space was insufficient.

## Integration Check

`brecha_proxy_z = z(necesidad) - z(acceso)` is retained as an integration check. Need combines confirmed SIVIGILA notification rates and departmental multidimensional poverty; the access component combines REPS sites per 100,000 inhabitants and the latest available REPS departmental mental-health capacity baseline when annual data are unavailable. This check does not replace the Hansen or E2SFCA potential-accessibility measures.

Highest municipality-year rows by `brecha_proxy_z`:

|   year |   cod_mpio | departamento   | municipio     |   brecha_proxy_z |
|-------:|-----------:|:---------------|:--------------|-----------------:|
|   2023 |      97666 | Vaupés         | Taraira       |          5.54047 |
|   2022 |      97666 | Vaupés         | Taraira       |          5.40822 |
|   2023 |      97001 | Vaupés         | Mitú          |          4.81972 |
|   2024 |      27099 | Chocó          | Bojayá        |          4.68579 |
|   2023 |      97161 | Vaupés         | Carurú        |          4.66833 |
|   2024 |      99524 | Vichada        | La Primavera  |          4.62601 |
|   2022 |      99624 | Vichada        | Santa Rosalía |          4.57139 |
|   2023 |      99624 | Vichada        | Santa Rosalía |          4.50907 |
|   2023 |      27099 | Chocó          | Bojayá        |          4.47006 |
|   2024 |      99624 | Vichada        | Santa Rosalía |          4.06466 |

## Technical Priorities

1. Replace the centroid travel-time proxy with a routed travel-time matrix when the OSRM extraction can be completed.
2. Obtain or build a complete national geocoded mental-health service layer if available.
3. Recompute Hansen and E2SFCA accessibility with routed times and service-specific supply.
