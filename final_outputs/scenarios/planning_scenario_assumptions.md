# Planning Scenario Assumptions

These outputs are illustrative planning scenarios, not evaluated interventions.
They use the same public-data constructs as the baseline analysis: REPS-enabled sites
as a municipal supply proxy, DANE population demand, the 2024 need score and
the centroid-based travel-time matrix. OSRM-routed times are not used.

## Baseline

- Year: 2024
- Baseline high-gap threshold: p90 of current gap = 1.275
- Baseline top-decile municipalities: 113
- E2SFCA catchment: 120 minutes
- Demand denominator: DANE municipal population
- Standardisation: scenario E2SFCA values are placed on the baseline 2024 E2SFCA z-scale.

## Scenario definitions

- Distributed outreach: adds 5 REPS-site-equivalent service-opportunity units to each baseline top-decile municipality.
- Regional service hubs: adds 30 REPS-site-equivalent service-opportunity units to 12 high-gap hub municipalities selected as the highest-gap municipality in high-gap departments.
- Effective impedance relief: multiplies effective centroid travel time by 0.90 for baseline top-decile origins, with the 10-minute intra-municipal floor retained.
- Combined scenario: combines distributed outreach, regional hubs and effective impedance relief.

The added units are not claims about real facilities, staffing, funding or
implementation feasibility. They are service-opportunity equivalents used to
show how the framework can recompute accessibility surfaces under explicit
planning assumptions.

## Selected regional hubs

| cod_mpio | departamento | municipio | baseline_gap_recomputed |
| --- | --- | --- | --- |
| 27099 | Chocó | Bojayá | 4.732 |
| 99524 | Vichada | La Primavera | 4.609 |
| 97001 | Vaupés | Mitú | 3.169 |
| 91407 | Amazonas | La Pedrera (ANM) | 2.688 |
| 95200 | Guaviare | Miraflores | 2.517 |
| 54800 | Norte de Santander | Teorama | 2.473 |
| 25871 | Cundinamarca | Villagómez | 2.423 |
| 73873 | Tolima | Villarrica | 2.421 |
| 94001 | Guainía | Inírida | 2.299 |
| 44430 | La Guajira | Maicao | 2.292 |
| 19517 | Cauca | Páez | 1.987 |
| 85136 | Casanare | La Salina | 1.963 |

## Scenario summary

| scenario_id | label | supply_units_added_total | municipalities_with_added_supply | effective_time_multiplier_for_baseline_top_decile | mean_access_gain_top_decile_z | median_access_gain_top_decile_z | mean_gap_reduction_top_decile_z | median_gap_reduction_top_decile_z | baseline_top_decile_moved_below_baseline_p90 | baseline_top_decile_n | mean_gap_all_z | mean_gap_top_decile_z | max_gap_z | p90_gap_z |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| distributed_outreach | Distributed outreach | 565.000 | 113 |  | 0.778 | 0.228 | 0.778 | 0.228 | 45 | 113 | -0.099 | 1.073 | 4.269 | 1.124 |
| regional_hubs | Regional service hubs | 360.000 | 12 |  | 0.329 | 0.000 | 0.329 | 0.000 | 10 | 113 | -0.054 | 1.522 | 4.356 | 1.233 |
| connectivity_relief | Effective impedance relief | 0.000 | 0 | 0.900 | 0.139 | 0.058 | 0.139 | 0.058 | 18 | 113 | -0.009 | 1.712 | 4.812 | 1.236 |
| combined | Combined scenario | 925.000 | 113 | 0.900 | 1.250 | 0.552 | 1.250 | 0.552 | 72 | 113 | -0.158 | 0.601 | 4.269 | 1.062 |
