# Potential Accessibility to Mental-Health Services in Colombia

Replication package for:

**Potential accessibility to mental-health services in Colombia: territorial screening with public data**

This repository contains the code, derived aggregate data, spatial outputs, tables and figures used to reproduce a municipal screening analysis of potential accessibility to mental-health services in Colombia.

The workflow harmonises public-data derivatives from REPS, RIPS, SIVIGILA attempted-suicide notifications, DANE population projections, multidimensional poverty data and DANE/MGN municipal boundaries. The current accessibility surface uses a centroid-based travel-time approximation. OSRM-routed travel times were not used.

## Scope

The package includes:

- source inventories and download metadata,
- derived municipal and municipality-year panels,
- spatial accessibility outputs,
- final empirical tables and figures,
- scripts used to rebuild the analytical outputs,
- documentation of the OSRM routing attempt.

The package does not include the full raw-data cache. Raw files are large and should be obtained from their official public sources. The inventory in `data_raw/_metadata/sources_inventory.csv` documents the sources used.

## Claim Boundary

The accessibility surface is based on a centroid travel-time approximation. It should be interpreted as a reproducible potential-accessibility screening surface, not as a routed road-network travel-time analysis.

REPS-enabled sites are used as a municipal supply proxy. They should not be interpreted as a complete geocoded universe of mental-health providers.

The planning-scenario outputs are illustrative recalculations under transparent assumptions. They are not evaluated interventions and should not be read as resource-allocation recommendations without local validation.

## Repository Structure

- `scripts/`: reproducible workflow scripts.
- `data_raw/_metadata/`: source inventory and download metadata.
- `data_work/`: derived tabular panels and data-quality outputs.
- `data_work_spatial/`: municipal centroids, proxy travel-time matrix and spatial accessibility outputs.
- `data_work_osrm/`: notes from the attempted OSRM preparation.
- `final_outputs/`: empirical tables, figures and planning-scenario outputs.

## Reproduction

Install Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run the main workflow:

```bash
make data
make spatial
make outputs
make scenarios
```

Run a lightweight validation check:

```bash
make validate
```

The commands can also be run directly:

```bash
python3 scripts/download_public_sources.py
python3 scripts/build_municipal_panel.py
python3 scripts/build_spatial_accessibility.py
python3 scripts/generate_final_outputs.py
python3 scripts/build_planning_scenarios.py
```

## Data Availability

Raw public sources should be obtained from the official providers listed in `data_raw/_metadata/sources_inventory.csv`.

Derived aggregate tables and spatial outputs needed to verify the analysis are included in this package. These files are public-data derivatives and do not contain individual-level health records.

## Citation and Archiving

The replication package is archived on Zenodo:

```text
https://doi.org/10.5281/zenodo.20519724
```

GitHub repository:

```text
https://github.com/jorgeiv500/health-place-colombia-accessibility-replication
```

Current release tag:

```text
v0.1.1
```

## Authors

- Jorge Iván Romero-Gelvez, Universidad de Bogotá Jorge Tadeo Lozano
- Mariana Angélica Contreras Gamboa, Universidad de Bogotá Jorge Tadeo Lozano

## License

See `LICENSE`.
