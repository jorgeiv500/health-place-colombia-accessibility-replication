#!/usr/bin/env python3
"""Build the spatial accessibility layer for the Colombia analysis.

This script creates municipality centroids, a municipality-to-supply
travel-friction matrix, Hansen and E2SFCA accessibility indices, and a spatial
gap panel. It uses OSRM/OSMnx only if those tools are already available; in the
current project environment they are not, so the implemented national layer is
a transparent great-circle/road-detour proxy. The proxy supports reproducible
screening and should be replaced by a routed matrix before making
road-network travel-time claims.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw"
WORK = ROOT / "data_work"
SPATIAL = ROOT / "data_work_spatial"

RID_REPS_GEO = "7r2w-27jm"
REPS_GEO_URL = f"https://www.datos.gov.co/resource/{RID_REPS_GEO}.csv"

YEARS = list(range(2021, 2026))
EARTH_RADIUS_KM = 6371.0088

# Conservative defaults for a national QA layer. These are not substitutes for
# OSRM routed travel times.
ROAD_DETOUR_FACTOR = 1.45
ROAD_SPEED_KMH = 45.0
INTRA_MUNICIPAL_TIME_MIN = 10.0
MAX_PROXY_TIME_MIN = 240.0
TOP_K_SUPPLY_DESTINATIONS = 35


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(df: pd.DataFrame, relative: str) -> Path:
    path = SPATIAL / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def zscore_by_year(df: pd.DataFrame, column: str) -> pd.Series:
    def z(group: pd.Series) -> pd.Series:
        sd = group.std(ddof=0)
        if pd.isna(sd) or sd == 0:
            return pd.Series(0.0, index=group.index)
        return (group - group.mean()) / sd

    return df.groupby("year", group_keys=False)[column].transform(z)


def code5(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) < 5:
        return None
    return digits[:5]


def tool_status() -> dict[str, str | bool]:
    status = {
        "osrm-extract": bool(shutil.which("osrm-extract")),
        "osrm-contract": bool(shutil.which("osrm-contract")),
        "osrm-routed": bool(shutil.which("osrm-routed")),
        "osmnx_python": False,
        "routing_mode": "great_circle_detour_proxy",
    }
    try:
        import osmnx  # noqa: F401

        status["osmnx_python"] = True
    except Exception:
        status["osmnx_python"] = False
    if status["osrm-extract"] and status["osrm-contract"] and status["osrm-routed"]:
        status["routing_mode"] = "great_circle_detour_proxy_osrm_installed_not_prepared"
    return status


def download_reps_geocoded_mental() -> pd.DataFrame:
    """Download the small georeferenced REPS support view found in datos.gov.co."""
    out = RAW / "minsalud_reps/reps_georreferenciado_salud_mental_7r2w_27jm.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    where = (
        "upper(serv_nombre) like '%PSI%' OR upper(serv_nombre) like '%MENTAL%' "
        "OR upper(serv_nombre) like '%FARMACODEPENDENCIA%' "
        "OR upper(serv_nombre) like '%SUSTANCIAS%' "
        "OR especificidad_salud_mental='SI' OR especificidad_spa='SI' "
        "OR especificidad_sustancias='SI'"
    )
    select = ",".join(
        [
            "codigo_habilitacion",
            "sede_nombre",
            "direccion",
            "latitud",
            "longitud",
            "serv_codigo",
            "serv_nombre",
            "especificidad_salud_mental",
            "especificidad_spa",
            "especificidad_sustancias",
            "modalidad_telemedicina",
            "clpr_nombre",
            "naju_nombre",
            "grse_nombre",
            "complejidades",
            "razon_social",
        ]
    )
    params = {
        "$select": select,
        "$where": where,
        "$limit": 50000,
        "$order": "codigo_habilitacion,serv_codigo",
    }
    url = REPS_GEO_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/csv,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        out.write_bytes(response.read())

    df = pd.read_csv(out, dtype=str)
    if df.empty:
        df["cod_mpio"] = pd.Series(dtype=str)
        write_csv(df, "reps_geocoded_mental_services_7r2w_27jm.csv")
        return df
    df["cod_mpio"] = df["codigo_habilitacion"].map(code5)
    df["latitud"] = pd.to_numeric(df["latitud"], errors="coerce")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")
    df["has_valid_coordinate"] = (
        df["latitud"].between(-5, 15) & df["longitud"].between(-82, -66)
    )
    write_csv(df, "reps_geocoded_mental_services_7r2w_27jm.csv")
    return df


def build_centroids() -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    gdf = gpd.read_file(RAW / "dane/MGN2025_municipio_317.geojson")
    gdf = gdf[
        [
            "DPTO_CCDGO",
            "MPIO_CDPMP",
            "DPTO_CNMBRE",
            "MPIO_CNMBRE",
            "MPIO_TIPO",
            "MPIO_NAREA",
            "geometry",
        ]
    ].copy()
    gdf["cod_dpto"] = gdf["DPTO_CCDGO"].astype(str).str.zfill(2)
    gdf["cod_mpio"] = gdf["MPIO_CDPMP"].astype(str).str.zfill(5)
    projected = gdf.to_crs(9377)
    centroids_4326 = gpd.GeoSeries(projected.geometry.centroid, crs=9377).to_crs(4326)
    gdf["centroid_lon"] = centroids_4326.x
    gdf["centroid_lat"] = centroids_4326.y
    gdf["area_km2_calc"] = projected.geometry.area / 1_000_000

    out = gdf[
        [
            "cod_dpto",
            "cod_mpio",
            "DPTO_CNMBRE",
            "MPIO_CNMBRE",
            "MPIO_TIPO",
            "MPIO_NAREA",
            "area_km2_calc",
            "centroid_lat",
            "centroid_lon",
        ]
    ].rename(
        columns={
            "DPTO_CNMBRE": "departamento_mgn",
            "MPIO_CNMBRE": "municipio_mgn",
            "MPIO_TIPO": "municipio_tipo_mgn",
            "MPIO_NAREA": "area_km2_mgn_attribute",
        }
    )
    write_csv(out.sort_values("cod_mpio"), "municipality_centroids_mgn2025.csv")

    point_gdf = gpd.GeoDataFrame(
        out,
        geometry=gpd.points_from_xy(out["centroid_lon"], out["centroid_lat"]),
        crs="EPSG:4326",
    )
    point_gdf.to_file(SPATIAL / "municipality_centroids_mgn2025.geojson", driver="GeoJSON")
    return out, gdf


def attach_catalog(
    centroids: pd.DataFrame, reps: pd.DataFrame, panel: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    catalog = panel[["cod_dpto", "departamento", "cod_mpio", "municipio"]].drop_duplicates()
    catalog["cod_dpto"] = catalog["cod_dpto"].astype(str).str.zfill(2)
    catalog["cod_mpio"] = catalog["cod_mpio"].astype(str).str.zfill(5)
    reps = reps.copy()
    reps["cod_mpio"] = reps["cod_mpio"].astype(str).str.zfill(5)
    merged = catalog.merge(centroids, on=["cod_dpto", "cod_mpio"], how="left")
    merged = merged.merge(reps, on="cod_mpio", how="left")
    supply_cols = [
        "sedes_reps",
        "prestadores_reps",
        "sedes_ips_reps",
        "sedes_publicas_reps",
        "sedes_privadas_reps",
    ]
    for col in supply_cols:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)
    merged["has_mgn_centroid"] = merged["centroid_lat"].notna() & merged["centroid_lon"].notna()
    merged["has_reps_supply"] = merged["sedes_reps"] > 0
    qa_missing = merged[~merged["has_mgn_centroid"]].copy()
    write_csv(qa_missing, "qa_panel_municipalities_missing_mgn_centroid.csv")
    write_csv(merged.sort_values("cod_mpio"), "municipality_spatial_catalog.csv")
    return merged, qa_missing


def haversine_matrix_km(
    lat_origin: np.ndarray, lon_origin: np.ndarray, lat_dest: np.ndarray, lon_dest: np.ndarray
) -> np.ndarray:
    lat1 = np.radians(lat_origin)[:, None]
    lon1 = np.radians(lon_origin)[:, None]
    lat2 = np.radians(lat_dest)[None, :]
    lon2 = np.radians(lon_dest)[None, :]
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return EARTH_RADIUS_KM * 2 * np.arcsin(np.sqrt(a))


def build_travel_matrix(catalog: pd.DataFrame) -> pd.DataFrame:
    origins = catalog[catalog["has_mgn_centroid"]].copy().reset_index(drop=True)
    destinations = origins[origins["has_reps_supply"]].copy().reset_index(drop=True)
    dist = haversine_matrix_km(
        origins["centroid_lat"].to_numpy(float),
        origins["centroid_lon"].to_numpy(float),
        destinations["centroid_lat"].to_numpy(float),
        destinations["centroid_lon"].to_numpy(float),
    )
    time_min = dist * ROAD_DETOUR_FACTOR / ROAD_SPEED_KMH * 60.0
    same = origins["cod_mpio"].to_numpy()[:, None] == destinations["cod_mpio"].to_numpy()[None, :]
    time_min = np.where(same, INTRA_MUNICIPAL_TIME_MIN, time_min)

    threshold_mask = (time_min <= MAX_PROXY_TIME_MIN) | same
    top_k = min(TOP_K_SUPPLY_DESTINATIONS, destinations.shape[0])
    nearest_idx = np.argpartition(time_min, kth=top_k - 1, axis=1)[:, :top_k]
    topk_mask = np.zeros_like(threshold_mask, dtype=bool)
    rows = np.arange(time_min.shape[0])[:, None]
    topk_mask[rows, nearest_idx] = True
    selected = threshold_mask | topk_mask

    oi, dj = np.where(selected)
    matrix = pd.DataFrame(
        {
            "origin_cod_mpio": origins.loc[oi, "cod_mpio"].to_numpy(),
            "origin_departamento": origins.loc[oi, "departamento"].to_numpy(),
            "origin_municipio": origins.loc[oi, "municipio"].to_numpy(),
            "dest_cod_mpio": destinations.loc[dj, "cod_mpio"].to_numpy(),
            "dest_departamento": destinations.loc[dj, "departamento"].to_numpy(),
            "dest_municipio": destinations.loc[dj, "municipio"].to_numpy(),
            "haversine_km": dist[oi, dj],
            "travel_time_proxy_min": time_min[oi, dj],
            "selected_within_240min": threshold_mask[oi, dj],
            "selected_topk": topk_mask[oi, dj],
            "same_municipality": same[oi, dj],
            "dest_sedes_reps": destinations.loc[dj, "sedes_reps"].to_numpy(float),
            "dest_sedes_ips_reps": destinations.loc[dj, "sedes_ips_reps"].to_numpy(float),
            "dest_prestadores_reps": destinations.loc[dj, "prestadores_reps"].to_numpy(float),
        }
    )
    matrix["within_60min"] = matrix["travel_time_proxy_min"] <= 60
    matrix["within_120min"] = matrix["travel_time_proxy_min"] <= 120
    matrix["within_180min"] = matrix["travel_time_proxy_min"] <= 180
    matrix["within_240min"] = matrix["travel_time_proxy_min"] <= 240
    matrix = matrix.sort_values(["origin_cod_mpio", "travel_time_proxy_min", "dest_cod_mpio"])
    write_csv(matrix, "travel_time_matrix_municipio_municipio_proxy.csv")
    return matrix


def e2sfca_decay(time_min: pd.Series, threshold: float) -> pd.Series:
    time = pd.to_numeric(time_min, errors="coerce")
    weights = pd.Series(0.0, index=time.index)
    weights[time <= 30] = 1.0
    weights[(time > 30) & (time <= 60)] = 0.68
    weights[(time > 60) & (time <= 120)] = 0.22
    if threshold > 120:
        weights[(time > 120) & (time <= threshold)] = 0.10
    weights[time > threshold] = 0.0
    return weights


def compute_accessibility(matrix: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    base = panel[
        [
            "cod_dpto",
            "departamento",
            "cod_mpio",
            "municipio",
            "year",
            "population_total",
            "sivigila_intento_confirmados_per_100k",
            "ipm_total_pct",
            "need_proxy_z",
            "brecha_proxy_z",
        ]
    ].copy()
    base["cod_mpio"] = base["cod_mpio"].astype(str).str.zfill(5)

    static_supply = (
        panel.sort_values("year")
        .drop_duplicates("cod_mpio", keep="last")[
            ["cod_mpio", "sedes_reps", "sedes_ips_reps", "prestadores_reps"]
        ]
        .copy()
    )
    static_supply["cod_mpio"] = static_supply["cod_mpio"].astype(str).str.zfill(5)
    static_supply = static_supply.rename(
        columns={
            "cod_mpio": "dest_cod_mpio",
            "sedes_reps": "supply_sedes_reps",
            "sedes_ips_reps": "supply_sedes_ips_reps",
            "prestadores_reps": "supply_prestadores_reps",
        }
    )
    pairs = matrix.merge(static_supply, on="dest_cod_mpio", how="left")
    for col in ["supply_sedes_reps", "supply_sedes_ips_reps", "supply_prestadores_reps"]:
        pairs[col] = pd.to_numeric(pairs[col], errors="coerce").fillna(0)
    pairs["hansen_decay_hl60"] = np.exp(-math.log(2) * pairs["travel_time_proxy_min"] / 60.0)
    pairs["hansen_decay_hl120"] = np.exp(-math.log(2) * pairs["travel_time_proxy_min"] / 120.0)

    outputs = []
    for year in YEARS:
        year_panel = base[base["year"] == year][["cod_mpio", "population_total"]].rename(
            columns={"cod_mpio": "origin_cod_mpio", "population_total": "origin_population"}
        )
        year_pairs = pairs.merge(year_panel, on="origin_cod_mpio", how="left")
        year_pairs["origin_population"] = pd.to_numeric(
            year_pairs["origin_population"], errors="coerce"
        ).fillna(0)

        record = pd.DataFrame({"cod_mpio": sorted(base.loc[base["year"] == year, "cod_mpio"].unique())})
        record["year"] = year

        for supply_col, suffix in [
            ("supply_sedes_reps", "sedes_all"),
            ("supply_sedes_ips_reps", "sedes_ips"),
        ]:
            hansen60 = (
                year_pairs.assign(value=year_pairs[supply_col] * year_pairs["hansen_decay_hl60"])
                .groupby("origin_cod_mpio", as_index=False)["value"]
                .sum()
                .rename(columns={"origin_cod_mpio": "cod_mpio", "value": f"hansen_{suffix}_hl60"})
            )
            hansen120 = (
                year_pairs.assign(value=year_pairs[supply_col] * year_pairs["hansen_decay_hl120"])
                .groupby("origin_cod_mpio", as_index=False)["value"]
                .sum()
                .rename(columns={"origin_cod_mpio": "cod_mpio", "value": f"hansen_{suffix}_hl120"})
            )
            record = record.merge(hansen60, on="cod_mpio", how="left")
            record = record.merge(hansen120, on="cod_mpio", how="left")

            for threshold in [120.0, 180.0]:
                col_name = f"e2sfca_{suffix}_{int(threshold)}min"
                sub = year_pairs[year_pairs["travel_time_proxy_min"] <= threshold].copy()
                sub["decay"] = e2sfca_decay(sub["travel_time_proxy_min"], threshold)
                denom = (
                    sub.assign(weighted_population=sub["origin_population"] * sub["decay"])
                    .groupby("dest_cod_mpio", as_index=False)["weighted_population"]
                    .sum()
                )
                dest_ratio = static_supply[["dest_cod_mpio", supply_col]].merge(
                    denom, on="dest_cod_mpio", how="left"
                )
                dest_ratio["weighted_population"] = dest_ratio["weighted_population"].replace(0, np.nan)
                dest_ratio["provider_to_population_ratio"] = (
                    dest_ratio[supply_col] / dest_ratio["weighted_population"]
                )
                sub = sub.merge(
                    dest_ratio[["dest_cod_mpio", "provider_to_population_ratio"]],
                    on="dest_cod_mpio",
                    how="left",
                )
                access = (
                    sub.assign(access=sub["provider_to_population_ratio"] * sub["decay"])
                    .groupby("origin_cod_mpio", as_index=False)["access"]
                    .sum()
                    .rename(columns={"origin_cod_mpio": "cod_mpio", "access": col_name})
                )
                record = record.merge(access, on="cod_mpio", how="left")
        outputs.append(record)

    access = pd.concat(outputs, ignore_index=True)
    panel_access = base.merge(access, on=["cod_mpio", "year"], how="left")
    for col in [
        "hansen_sedes_all_hl60",
        "hansen_sedes_ips_hl60",
        "e2sfca_sedes_all_120min",
        "e2sfca_sedes_ips_120min",
        "e2sfca_sedes_all_180min",
        "e2sfca_sedes_ips_180min",
    ]:
        if col in panel_access.columns:
            panel_access[f"z_{col}"] = zscore_by_year(panel_access, col)

    panel_access["access_spatial_z"] = panel_access["z_e2sfca_sedes_all_120min"]
    panel_access["brecha_spatial_z"] = panel_access["need_proxy_z"] - panel_access["access_spatial_z"]
    panel_access["routing_mode"] = "great_circle_detour_proxy"
    panel_access["supply_definition_main"] = "REPS all enabled sites assigned to DANE/MGN municipal centroids"
    panel_access = panel_access.sort_values(["cod_mpio", "year"])
    write_csv(access.sort_values(["cod_mpio", "year"]), "accessibility_indices_municipio_year.csv")
    write_csv(panel_access, "municipal_panel_spatial_access_2021_2025.csv")
    return panel_access


def summarize_mental_geo_support(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        out = pd.DataFrame(
            columns=[
                "cod_mpio",
                "geocoded_mental_service_rows",
                "geocoded_mental_sites",
                "psychology_rows",
                "psychiatry_rows",
            ]
        )
        write_csv(out, "reps_geocoded_mental_services_by_municipio_support.csv")
        return out
    valid = df[df["has_valid_coordinate"]].copy()
    valid["serv_upper"] = valid["serv_nombre"].astype(str).str.upper()
    valid["is_psychology"] = valid["serv_upper"].str.contains("PSICOLOG", na=False)
    valid["is_psychiatry"] = valid["serv_upper"].str.contains("PSIQUIATR", na=False)
    out = valid.groupby("cod_mpio", as_index=False).agg(
        geocoded_mental_service_rows=("serv_nombre", "size"),
        geocoded_mental_sites=("codigo_habilitacion", "nunique"),
        psychology_rows=("is_psychology", "sum"),
        psychiatry_rows=("is_psychiatry", "sum"),
    )
    write_csv(out.sort_values("cod_mpio"), "reps_geocoded_mental_services_by_municipio_support.csv")
    return out


def write_method_readme(
    status: dict[str, str | bool],
    catalog: pd.DataFrame,
    matrix: pd.DataFrame,
    panel_access: pd.DataFrame,
    geocoded_raw: pd.DataFrame,
    geocoded_support: pd.DataFrame,
) -> None:
    top_gap = (
        panel_access[panel_access["year"].eq(2024)]
        .dropna(subset=["brecha_spatial_z"])
        .sort_values("brecha_spatial_z", ascending=False)
        .head(12)[
            [
                "year",
                "cod_mpio",
                "departamento",
                "municipio",
                "e2sfca_sedes_all_120min",
                "brecha_spatial_z",
            ]
        ]
    )
    lines = [
        "# Spatial accessibility layer",
        "",
        "This directory contains the spatial accessibility layer used in the replication package.",
        "",
        "## Routing mode",
        "",
        f"- `osrm-extract`: {status['osrm-extract']}",
        f"- `osrm-contract`: {status['osrm-contract']}",
        f"- `osrm-routed`: {status['osrm-routed']}",
        f"- Python `osmnx`: {status['osmnx_python']}",
        f"- Applied mode: `{status['routing_mode']}`",
        "",
        "The national matrix is a transparent proxy: haversine distance multiplied by a road-detour factor of 1.45, divided by 45 km/h, with a 10-minute intra-municipal floor. OSRM is installed if reported above, but this script uses the proxy unless a prepared `.osrm` dataset exists. In this workspace, full Colombia OSRM extraction was attempted and stopped because the disk had insufficient free space. The proxy supports reproducible screening and should be replaced by a routed OSRM/OSMnx matrix before making road-network travel-time claims.",
        "",
        "## Outputs",
        "",
        "- `municipality_centroids_mgn2025.csv` and `.geojson`: DANE/MGN municipal centroids.",
        "- `municipality_spatial_catalog.csv`: DANE panel municipalities joined to centroids and REPS supply.",
        "- `travel_time_matrix_municipio_municipio_proxy.csv`: selected origin-destination pairs by 240-minute threshold plus 35 nearest supply municipalities.",
        "- `accessibility_indices_municipio_year.csv`: Hansen and E2SFCA indices.",
        "- `municipal_panel_spatial_access_2021_2025.csv`: panel with `access_spatial_z` and `brecha_spatial_z`.",
        "- `reps_geocoded_mental_services_7r2w_27jm.csv`: support download from the georeferenced REPS view found in datos.gov.co.",
        "- `fig_brecha_spatial_proxy_2024.png`: choropleth for QA only.",
        "",
        "## Coverage",
        "",
        f"- Panel municipalities: {catalog['cod_mpio'].nunique():,}",
        f"- Municipalities with MGN centroid: {catalog['has_mgn_centroid'].sum():,}",
        f"- Municipalities with REPS supply: {catalog['has_reps_supply'].sum():,}",
        f"- OD pairs in proxy matrix: {len(matrix):,}",
        f"- Geocoded mental-health support rows: {len(geocoded_raw):,}",
        f"- Geocoded mental-health support municipalities: {geocoded_support['cod_mpio'].nunique() if 'cod_mpio' in geocoded_support.columns else 0:,}",
        "",
        "## Main formula",
        "",
        "`brecha_spatial_z = need_proxy_z - z(e2sfca_sedes_all_120min)`",
        "",
        "The need side is inherited from the seed panel: SIVIGILA attempted-suicide rate plus departmental IPM. The access side is now spatially lagged through E2SFCA rather than using only local per-capita REPS supply.",
        "",
        "## Highest 2024 spatial gaps",
        "",
        top_gap.to_markdown(index=False),
        "",
        "## Required next replacement",
        "",
        "Build an OSRM/OSMnx routed matrix from `data_raw/osm/colombia-latest.osm.pbf` and rerun E2SFCA with road-network times. This script already isolates the matrix input so that replacement is straightforward.",
        "",
    ]
    (SPATIAL / "README_spatial_accessibility.md").write_text("\n".join(lines), encoding="utf-8")


def make_map(mgn: gpd.GeoDataFrame, panel_access: pd.DataFrame) -> None:
    plot_df = panel_access[panel_access["year"].eq(2024)][
        ["cod_mpio", "brecha_spatial_z", "e2sfca_sedes_all_120min"]
    ].copy()
    gdf = mgn.merge(plot_df, left_on="cod_mpio", right_on="cod_mpio", how="left")
    fig, ax = plt.subplots(figsize=(9, 11))
    gdf.plot(
        column="brecha_spatial_z",
        ax=ax,
        cmap="RdYlBu_r",
        linewidth=0.08,
        edgecolor="#555555",
        legend=True,
        missing_kwds={"color": "#eeeeee", "label": "Missing"},
    )
    ax.set_axis_off()
    ax.set_title(
        "Spatial mental-health access gap proxy, Colombia 2024",
        fontsize=13,
        pad=12,
    )
    ax.text(
        0.01,
        0.01,
        "Proxy: DANE/MGN centroids + REPS municipal supply + haversine-detour travel time",
        transform=ax.transAxes,
        fontsize=7,
        color="#333333",
    )
    fig.tight_layout()
    fig.savefig(SPATIAL / "fig_brecha_spatial_proxy_2024.png", dpi=220)
    plt.close(fig)


def build_validation_summary(files: Iterable[Path]) -> pd.DataFrame:
    rows = []
    for path in files:
        if path.exists():
            rows.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path) if path.stat().st_size < 200_000_000 else "",
                }
            )
    summary = pd.DataFrame(rows)
    write_csv(summary, "spatial_output_manifest.csv")
    return summary


def write_spatial_sources() -> None:
    rows = [
        {
            "source_id": "dane_mgn_municipio_2025_geojson",
            "role": "municipal geometry and centroids",
            "local_path": "data_raw/dane/MGN2025_municipio_317.geojson",
            "url": "https://geoportal.dane.gov.co/mparcgis/rest/services/MGN2025/Serv_CapasMGN_2025/FeatureServer/317",
        },
        {
            "source_id": "reps_sedes_c36g_9fc2",
            "role": "national municipal supply counts",
            "local_path": "data_raw/minsalud_reps/reps_sedes_c36g_9fc2.csv",
            "url": "https://www.datos.gov.co/resource/c36g-9fc2",
        },
        {
            "source_id": "reps_georreferenciado_7r2w_27jm",
            "role": "small geocoded mental-health service support view",
            "local_path": "data_raw/minsalud_reps/reps_georreferenciado_salud_mental_7r2w_27jm.csv",
            "url": "https://www.datos.gov.co/resource/7r2w-27jm",
        },
        {
            "source_id": "osm_colombia_latest_pbf",
            "role": "downloaded routing source; not yet used because OSRM/OSMnx unavailable",
            "local_path": "data_raw/osm/colombia-latest.osm.pbf",
            "url": "https://download.geofabrik.de/south-america/colombia-latest.osm.pbf",
        },
    ]
    write_csv(pd.DataFrame(rows), "spatial_sources_used.csv")


def main() -> None:
    SPATIAL.mkdir(parents=True, exist_ok=True)
    status = tool_status()
    (SPATIAL / "routing_environment.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    panel = pd.read_csv(
        WORK / "municipal_panel_seed_2021_2025.csv",
        dtype={"cod_dpto": str, "cod_mpio": str},
    )
    reps = pd.read_csv(WORK / "reps_sedes_by_municipio.csv", dtype={"cod_mpio": str})

    geocoded = download_reps_geocoded_mental()
    geocoded_support = summarize_mental_geo_support(geocoded)
    centroids, mgn = build_centroids()
    catalog, _ = attach_catalog(centroids, reps, panel)
    matrix = build_travel_matrix(catalog)
    panel_access = compute_accessibility(matrix, panel)
    make_map(mgn, panel_access)
    write_spatial_sources()
    write_method_readme(status, catalog, matrix, panel_access, geocoded, geocoded_support)

    files = sorted(SPATIAL.glob("*"))
    manifest = build_validation_summary([p for p in files if p.is_file()])
    print(f"Wrote spatial outputs to {SPATIAL}")
    print(manifest[["path", "bytes"]].to_string(index=False))
    print(status)


if __name__ == "__main__":
    main()
