PYTHON ?= python3

.PHONY: all data spatial outputs scenarios validate clean

all: data spatial outputs scenarios

data:
	$(PYTHON) scripts/build_municipal_panel.py

spatial:
	$(PYTHON) scripts/build_spatial_accessibility.py

outputs:
	$(PYTHON) scripts/generate_final_outputs.py

scenarios:
	$(PYTHON) scripts/build_planning_scenarios.py

validate:
	$(PYTHON) -m py_compile scripts/*.py
	test -f data_raw/_metadata/sources_inventory.csv
	test -f data_work/municipal_panel_seed_2021_2025.csv
	test -f data_work_spatial/municipal_panel_spatial_access_2021_2025.csv
	test -f final_outputs/tables/table_7_moran_i_2024.csv

clean:
	rm -rf scripts/__pycache__
