# OSRM attempt log

OSRM backend was installed with Homebrew on 2026-05-29 local workspace time.

Commands attempted:

```bash
brew install osrm-backend
ln -sf ../data_raw/osm/colombia-latest.osm.pbf data_work_osrm/colombia-latest.osm.pbf
osrm-extract -p /opt/homebrew/opt/osrm-backend/share/osrm/profiles/car.lua data_work_osrm/colombia-latest.osm.pbf
```

Observed extraction status:

- Input PBF: `data_raw/osm/colombia-latest.osm.pbf`
- OSM timestamp reported by OSRM: `2026-05-29T20:21:10Z`
- Raw input parsed by OSRM: 45,508,606 nodes; 4,819,851 ways; 2,167 relations; 6,845 restrictions.
- Peak RAM reported by OSRM before failure: 4,307,599,360 bytes.
- Failure reason: `No space left on device` while writing `data_work_osrm/colombia-latest.osrm.geometry`.

The partial `.osrm*` files were removed after failure to avoid leaving the disk full. The current reproducible national accessibility layer therefore uses `great_circle_detour_proxy` travel times. To produce final road-network travel times, rerun OSRM on a volume with substantially more free space, then replace `data_work_spatial/travel_time_matrix_municipio_municipio_proxy.csv` with an OSRM table-derived matrix.
