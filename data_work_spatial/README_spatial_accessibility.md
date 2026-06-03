# Spatial accessibility layer

This directory contains the spatial accessibility layer used in the replication package.

## Routing mode

- `osrm-extract`: True
- `osrm-contract`: True
- `osrm-routed`: False
- Python `osmnx`: False
- Applied mode: `great_circle_detour_proxy_osrm_installed_not_prepared`

The national matrix is a transparent proxy: haversine distance multiplied by a road-detour factor of 1.45, divided by 45 km/h, with a 10-minute intra-municipal floor. OSRM is installed if reported above, but this script uses the proxy unless a prepared `.osrm` dataset exists. In this workspace, full Colombia OSRM extraction was attempted and stopped because the disk had insufficient free space. The proxy is useful for workflow validation and preliminary comparative screening; it should be replaced by a routed OSRM/OSMnx matrix before making road-network travel-time claims.

## Outputs

- `municipality_centroids_mgn2025.csv` and `.geojson`: DANE/MGN municipal centroids.
- `municipality_spatial_catalog.csv`: DANE panel municipalities joined to centroids and REPS supply.
- `travel_time_matrix_municipio_municipio_proxy.csv`: selected origin-destination pairs by 240-minute threshold plus 35 nearest supply municipalities.
- `accessibility_indices_municipio_year.csv`: Hansen and E2SFCA indices.
- `municipal_panel_spatial_access_2021_2025.csv`: panel with `access_spatial_z` and `brecha_spatial_z`.
- `reps_geocoded_mental_services_7r2w_27jm.csv`: support download from the georeferenced REPS view found in datos.gov.co.
- `fig_brecha_spatial_proxy_2024.png`: choropleth for QA only.

## Coverage

- Panel municipalities: 1,123
- Municipalities with MGN centroid: 1,122
- Municipalities with REPS supply: 1,122
- OD pairs in proxy matrix: 129,544
- Geocoded mental-health support rows: 42
- Geocoded mental-health support municipalities: 6

## Main formula

`brecha_spatial_z = need_proxy_z - z(e2sfca_sedes_all_120min)`

The need side is inherited from the seed panel: SIVIGILA attempted-suicide rate plus departmental IPM. The access side is now spatially lagged through E2SFCA rather than using only local per-capita REPS supply.

## Highest 2024 spatial gaps

|   year |   cod_mpio | departamento       | municipio             |   e2sfca_sedes_all_120min |   brecha_spatial_z |
|-------:|-----------:|:-------------------|:----------------------|--------------------------:|-------------------:|
|   2024 |      27099 | Chocó              | Bojayá                |               0.000360732 |            4.73152 |
|   2024 |      99524 | Vichada            | La Primavera          |               0.000471565 |            4.609   |
|   2024 |      99773 | Vichada            | Cumaribo              |               3.83197e-05 |            4.35554 |
|   2024 |      99624 | Vichada            | Santa Rosalía         |               0.000479616 |            4.03984 |
|   2024 |      97001 | Vaupés             | Mitú                  |               0.00116316  |            3.16921 |
|   2024 |      99001 | Vichada            | Puerto Carreño        |               0.00100171  |            3.07136 |
|   2024 |      91407 | Amazonas           | La Pedrera (ANM)      |               0.000245519 |            2.68751 |
|   2024 |      91460 | Amazonas           | Miriti - Paraná (ANM) |               0.000489476 |            2.53273 |
|   2024 |      95200 | Guaviare           | Miraflores            |               0.000141864 |            2.51662 |
|   2024 |      54800 | Norte de Santander | Teorama               |               0.000261743 |            2.47312 |
|   2024 |      25871 | Cundinamarca       | Villagómez            |               0.000592959 |            2.42312 |
|   2024 |      91263 | Amazonas           | El Encanto (ANM)      |               0.000452284 |            2.42197 |

## Required next replacement

Build an OSRM/OSMnx routed matrix from `data_raw/osm/colombia-latest.osm.pbf` and rerun E2SFCA with road-network times. This script already isolates the matrix input so that replacement is straightforward.
