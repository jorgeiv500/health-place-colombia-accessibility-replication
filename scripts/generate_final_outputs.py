#!/usr/bin/env python3
"""Generate empirical tables and figures for the replication package.

The outputs intentionally keep the current claim boundary visible: the national
accessibility surface uses a centroid-based travel-time proxy because OSRM
could not be prepared on the local disk. The generated assets reproduce the
reported tables, figures and summary diagnostics without making routed
travel-time claims.
"""

from __future__ import annotations

import json
import math
from textwrap import fill
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mpl_toolkits.axes_grid1.inset_locator import inset_axes


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data_work"
SPATIAL = ROOT / "data_work_spatial"
OUT = ROOT / "final_outputs"
TABLES = OUT / "tables"
FIGURES = OUT / "figures"
METRIC_CRS = "EPSG:3116"


BASE = {
    "page": "#ffffff",
    "basemap": "#f8f9fa",
    "polygon": "#f3f4f5",
    "boundary": "#d5d9de",
    "boundary_dark": "#4b5563",
    "blue": "#527ea9",
    "line_red": "#a93f37",
    "reference_red": "#a83b35",
    "green": "#8aa892",
    "peach": "#d8b08f",
    "neutral": "#d9dde2",
    "grid": "#e6e9ed",
    "text": "#1f2937",
    "muted": "#697381",
}

CMAPS = {
    "gap_diverging": mcolors.LinearSegmentedColormap.from_list(
        "gap_diverging",
        ["#405f91", "#8fb8cc", "#f7f3d0", "#d99a5b", "#9f2f2f"],
    ),
    "access_inverse": mcolors.LinearSegmentedColormap.from_list(
        "access_inverse",
        ["#9f2f2f", "#f7f3d0", "#2f648d"],
    ),
    "access_blue": mcolors.LinearSegmentedColormap.from_list(
        "access_blue",
        ["#f4f8f8", "#b7d5db", "#6899b8", "#2f648d"],
    ),
    "need_pink": mcolors.LinearSegmentedColormap.from_list(
        "need_pink",
        ["#fbf5f3", "#e9b9ad", "#c86f69", "#8f2f45"],
    ),
}


def set_publication_style() -> None:
    """Apply a compact publication-style figure theme."""
    plt.rcParams.update(
        {
            "figure.facecolor": BASE["page"],
            "savefig.facecolor": BASE["page"],
            "font.family": "DejaVu Sans",
            "font.size": 7.8,
            "axes.titlesize": 8.6,
            "axes.labelsize": 7.6,
            "axes.edgecolor": BASE["boundary_dark"],
            "axes.linewidth": 0.65,
            "xtick.labelsize": 6.9,
            "ytick.labelsize": 6.9,
            "legend.fontsize": 6.8,
            "grid.color": BASE["grid"],
            "grid.linewidth": 0.48,
            "grid.linestyle": "-",
            "savefig.dpi": 300,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def ensure_dirs() -> None:
    for path in [OUT, TABLES, FIGURES]:
        path.mkdir(parents=True, exist_ok=True)


def write_table(df: pd.DataFrame, stem: str) -> None:
    csv_path = TABLES / f"{stem}.csv"
    md_path = TABLES / f"{stem}.md"
    df.to_csv(csv_path, index=False)
    try:
        markdown = df.to_markdown(index=False)
    except ImportError:
        cols = list(df.columns)
        lines = [
            "| " + " | ".join(cols) + " |",
            "| " + " | ".join(["---"] * len(cols)) + " |",
        ]
        for _, row in df.iterrows():
            values = [str(row[col]) for col in cols]
            lines.append("| " + " | ".join(values) + " |")
        markdown = "\n".join(lines)
    md_path.write_text(markdown, encoding="utf-8")


def safe_num(series: pd.Series) -> pd.Series:
    out = pd.to_numeric(series, errors="coerce")
    return out.replace([np.inf, -np.inf], np.nan)


def to_metric(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Project geography to a Colombian metric CRS for publication map plates."""
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs(METRIC_CRS)


def set_map_bounds(ax: plt.Axes, gdf: gpd.GeoDataFrame, pad: float = 0.025) -> None:
    minx, miny, maxx, maxy = gdf.total_bounds
    dx = maxx - minx
    dy = maxy - miny
    ax.set_xlim(minx - dx * pad, maxx + dx * pad)
    ax.set_ylim(miny - dy * pad, maxy + dy * pad)
    ax.set_aspect("equal")
    ax.set_axis_off()


def add_panel_label(ax: plt.Axes, label: str, x: float = 0.02, y: float = 0.96) -> None:
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=7.2,
        fontweight="semibold",
        color=BASE["text"],
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.68, pad=1.1),
        zorder=90,
    )


def add_north_arrow(ax: plt.Axes, x: float = 0.93, y: float = 0.82) -> None:
    ax.annotate(
        "N",
        xy=(x, y + 0.042),
        xytext=(x, y),
        xycoords="axes fraction",
        ha="center",
        va="center",
        fontsize=5.8,
        fontweight="semibold",
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.54, pad=0.10),
        arrowprops=dict(arrowstyle="-|>", color="#111827", lw=0.65),
        zorder=90,
    )


def add_scale_bar(ax: plt.Axes, length_km: int = 200, x: float = 0.06, y: float = 0.055) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    length_m = length_km * 1000
    sx = x0 + (x1 - x0) * x
    sy = y0 + (y1 - y0) * y
    ax.plot([sx, sx + length_m], [sy, sy], color="#111827", lw=1.0, solid_capstyle="butt", zorder=90)
    ax.plot([sx, sx], [sy - (y1 - y0) * 0.005, sy + (y1 - y0) * 0.005], color="#111827", lw=0.65, zorder=90)
    ax.plot(
        [sx + length_m, sx + length_m],
        [sy - (y1 - y0) * 0.005, sy + (y1 - y0) * 0.005],
        color="#111827",
        lw=0.65,
        zorder=90,
    )
    ax.text(
        sx + length_m / 2,
        sy + (y1 - y0) * 0.013,
        f"{length_km} km",
        ha="center",
        va="bottom",
        fontsize=5.2,
        color="#111827",
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.62, pad=0.45),
        zorder=91,
    )


def save_publication_figure(fig: plt.Figure, filename: str, **kwargs) -> None:
    """Write raster and vector copies so LaTeX can use publication-grade art."""
    png = FIGURES / filename
    pdf = png.with_suffix(".pdf")
    fig.savefig(png, dpi=300, bbox_inches="tight", **kwargs)
    fig.savefig(pdf, bbox_inches="tight", **kwargs)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, gpd.GeoDataFrame]:
    panel = pd.read_csv(
        SPATIAL / "municipal_panel_spatial_access_2021_2025.csv",
        dtype={"cod_dpto": str, "cod_mpio": str},
    )
    seed = pd.read_csv(
        WORK / "municipal_panel_seed_2021_2025.csv",
        dtype={"cod_dpto": str, "cod_mpio": str},
    )
    for df in [panel, seed]:
        df["cod_dpto"] = df["cod_dpto"].astype(str).str.zfill(2)
        df["cod_mpio"] = df["cod_mpio"].astype(str).str.zfill(5)
    gdf = gpd.read_file(ROOT / "data_raw/dane/MGN2025_municipio_317.geojson")
    gdf["cod_mpio"] = gdf["MPIO_CDPMP"].astype(str).str.zfill(5)
    return panel, seed, gdf


def table_data_coverage(panel: pd.DataFrame, seed: pd.DataFrame) -> pd.DataFrame:
    validation = pd.read_csv(WORK / "source_validation_summary.csv")
    spatial_matrix = pd.read_csv(
        SPATIAL / "travel_time_matrix_municipio_municipio_proxy.csv",
        usecols=["origin_cod_mpio", "dest_cod_mpio"],
        dtype=str,
    )
    routing = json.loads((SPATIAL / "routing_environment.json").read_text())
    rows = [
        ["Municipality-year panel rows", len(panel), "Derived"],
        ["Municipalities in panel", panel["cod_mpio"].nunique(), "Derived"],
        [
            "Municipalities with non-missing spatial gap in 2024",
            panel.query("year == 2024")["brecha_spatial_z"].notna().sum(),
            "Derived",
        ],
        ["Municipality-month seed rows", len(pd.read_csv(WORK / "municipal_month_seed_2021_2025.csv")), "Derived"],
        [
            "REPS source rows",
            int(validation.loc[validation["id"].eq("reps_sedes_c36g_9fc2"), "rows_or_features"].iloc[0]),
            "Raw public extract",
        ],
        [
            "RIPS mental-health source rows",
            int(validation.loc[validation["id"].eq("rips_salud_mental_f_2019_2021"), "rows_or_features"].iloc[0]),
            "Raw public extract",
        ],
        [
            "SIVIGILA municipality-year rows",
            len(pd.read_csv(WORK / "sivigila_intento_suicidio_by_municipio_year.csv")),
            "Derived",
        ],
        [
            "SaluData Bogota rows",
            int(validation.loc[validation["id"].eq("saludata_conducta_suicida"), "rows_or_features"].iloc[0]),
            "Raw public extract",
        ],
        [
            "MGN municipality features",
            int(validation.loc[validation["id"].eq("dane_mgn_municipio_2025"), "rows_or_features"].iloc[0]),
            "Raw public geometry",
        ],
        [
            "Proxy OD pairs",
            len(spatial_matrix),
            "Derived; 240-min threshold plus nearest supply nodes",
        ],
        ["Routing mode", routing.get("routing_mode", ""), "Environment"],
    ]
    out = pd.DataFrame(rows, columns=["item", "value", "source_or_note"])
    write_table(out, "table_1_data_coverage")
    return out


def table_yearly_summary(panel: pd.DataFrame, seed: pd.DataFrame) -> pd.DataFrame:
    joined = panel.merge(
        seed[
            [
                "cod_mpio",
                "year",
                "sedes_reps",
                "sivigila_intento_suicidio_confirmados",
                "analysis_eligible_population",
            ]
        ],
        on=["cod_mpio", "year"],
        how="left",
    )
    rows = []
    for year, group in joined.groupby("year"):
        eligible = group[group["brecha_spatial_z"].notna()].copy()
        rows.append(
            {
                "year": int(year),
                "municipalities_with_gap": int(len(eligible)),
                "population_total": int(safe_num(eligible["population_total"]).sum()),
                "sivigila_confirmed_attempts": int(
                    safe_num(eligible["sivigila_intento_suicidio_confirmados"]).sum()
                )
                if year <= 2024
                else np.nan,
                "mean_ipm_pct": safe_num(eligible["ipm_total_pct"]).mean(),
                "median_e2sfca_120": safe_num(eligible["e2sfca_sedes_all_120min"]).median(),
                "mean_need_z": safe_num(eligible["need_proxy_z"]).mean(),
                "mean_access_z": safe_num(eligible["access_spatial_z"]).mean(),
                "gap_mean": safe_num(eligible["brecha_spatial_z"]).mean(),
                "gap_p90": safe_num(eligible["brecha_spatial_z"]).quantile(0.90),
            }
        )
    out = pd.DataFrame(rows)
    write_table(out.round(6), "table_2_yearly_summary")
    return out


def table_departments_2024(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel[(panel["year"] == 2024) & panel["brecha_spatial_z"].notna()].copy()
    out = (
        df.groupby(["cod_dpto", "departamento"], as_index=False)
        .agg(
            municipalities=("cod_mpio", "nunique"),
            population=("population_total", "sum"),
            mean_gap_z=("brecha_spatial_z", "mean"),
            median_gap_z=("brecha_spatial_z", "median"),
            mean_need_z=("need_proxy_z", "mean"),
            mean_access_z=("access_spatial_z", "mean"),
            mean_ipm_pct=("ipm_total_pct", "mean"),
            median_sivigila_rate=("sivigila_intento_confirmados_per_100k", "median"),
            median_e2sfca_120=("e2sfca_sedes_all_120min", "median"),
        )
        .sort_values("mean_gap_z", ascending=False)
    )
    write_table(out.round(6), "table_3_department_summary_2024")
    return out


def table_top_gap_2024(panel: pd.DataFrame, seed: pd.DataFrame) -> pd.DataFrame:
    df = panel[(panel["year"] == 2024) & panel["brecha_spatial_z"].notna()].merge(
        seed[["cod_mpio", "year", "sedes_reps", "sedes_ips_reps"]],
        on=["cod_mpio", "year"],
        how="left",
    )
    out = df.sort_values("brecha_spatial_z", ascending=False).head(30)[
        [
            "cod_mpio",
            "departamento",
            "municipio",
            "population_total",
            "ipm_total_pct",
            "sivigila_intento_confirmados_per_100k",
            "sedes_reps",
            "sedes_ips_reps",
            "e2sfca_sedes_all_120min",
            "need_proxy_z",
            "access_spatial_z",
            "brecha_spatial_z",
        ]
    ]
    write_table(out.round(6), "table_4_top_gap_municipalities_2024")
    return out


def table_high_gap_decomposition(panel: pd.DataFrame, seed: pd.DataFrame) -> pd.DataFrame:
    df = panel[(panel["year"] == 2024) & panel["brecha_spatial_z"].notna()].merge(
        seed[["cod_mpio", "year", "sedes_reps", "sedes_ips_reps"]],
        on=["cod_mpio", "year"],
        how="left",
    )
    cutoff = df["brecha_spatial_z"].quantile(0.90)
    df["group"] = np.where(df["brecha_spatial_z"] >= cutoff, "Top decile gap", "Other municipalities")
    rows = []
    variables = [
        ("population_total", "Population", "median"),
        ("ipm_total_pct", "IPM pct", "mean"),
        ("sivigila_intento_confirmados_per_100k", "Attempted-suicide notifications per 100k", "median"),
        ("sedes_reps", "REPS sites", "median"),
        ("sedes_ips_reps", "REPS IPS sites", "median"),
        ("e2sfca_sedes_all_120min", "E2SFCA 120-min accessibility", "median"),
        ("need_proxy_z", "Need score z", "mean"),
        ("access_spatial_z", "Access score z", "mean"),
        ("brecha_spatial_z", "Spatial gap z", "mean"),
    ]
    for col, label, stat in variables:
        for group, gdf in df.groupby("group"):
            values = safe_num(gdf[col])
            value = values.median() if stat == "median" else values.mean()
            rows.append({"variable": label, "statistic": stat, "group": group, "value": value})
    out = pd.DataFrame(rows)
    write_table(out.round(6), "table_5_high_gap_decomposition_2024")
    return out


def table_correlations_2024(panel: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "brecha_spatial_z",
        "need_proxy_z",
        "access_spatial_z",
        "ipm_total_pct",
        "sivigila_intento_confirmados_per_100k",
        "e2sfca_sedes_all_120min",
        "hansen_sedes_all_hl60",
    ]
    df = panel[(panel["year"] == 2024) & panel["brecha_spatial_z"].notna()][cols].copy()
    corr = df.apply(safe_num).corr(method="spearman")
    out = corr.reset_index().rename(columns={"index": "variable"})
    write_table(out.round(4), "table_6_spearman_correlations_2024")
    return out


def moran_i_2024(panel: pd.DataFrame, gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    df = panel[(panel["year"] == 2024) & panel["brecha_spatial_z"].notna()][
        ["cod_mpio", "brecha_spatial_z"]
    ].copy()
    mg = gdf[["cod_mpio", "geometry"]].merge(df, on="cod_mpio", how="inner").reset_index(drop=True)
    x = safe_num(mg["brecha_spatial_z"]).to_numpy(float)
    xbar = np.nanmean(x)
    z = x - xbar
    idx = mg.sindex
    pairs = []
    for i, geom in enumerate(mg.geometry):
        try:
            candidates = idx.query(geom, predicate="touches")
        except TypeError:
            candidates = idx.query(geom)
        for j in candidates:
            if i != j and i < j and geom.touches(mg.geometry.iloc[j]):
                pairs.append((i, int(j)))
    if not pairs:
        out = pd.DataFrame([{"moran_i": np.nan, "n": len(mg), "edge_pairs": 0, "p_permutation_greater": np.nan}])
        write_table(out, "table_7_moran_i_2024")
        return out
    zi = np.array([z[i] for i, _ in pairs])
    zj = np.array([z[j] for _, j in pairs])
    w_sum = len(pairs) * 2
    numerator = 2 * np.sum(zi * zj)
    denominator = np.sum(z**2)
    observed = len(mg) / w_sum * numerator / denominator

    rng = np.random.default_rng(20260529)
    perms = []
    for _ in range(499):
        zp = rng.permutation(z)
        zpi = np.array([zp[i] for i, _ in pairs])
        zpj = np.array([zp[j] for _, j in pairs])
        perms.append(len(mg) / w_sum * (2 * np.sum(zpi * zpj)) / denominator)
    p_greater = (1 + np.sum(np.array(perms) >= observed)) / (len(perms) + 1)
    out = pd.DataFrame(
        [
            {
                "moran_i": observed,
                "n": len(mg),
                "edge_pairs": len(pairs),
                "permutations": len(perms),
                "p_permutation_greater": p_greater,
            }
        ]
    )
    write_table(out.round(6), "table_7_moran_i_2024")
    return out


def map_variable(
    gdf: gpd.GeoDataFrame,
    panel: pd.DataFrame,
    variable: str,
    title: str,
    filename: str,
    cmap: str = "RdYlBu_r",
    legend_label: str = "",
    centered: bool = False,
    note: str = "",
) -> None:
    data = panel[panel["year"] == 2024][["cod_mpio", variable]].copy()
    plot = gdf[["cod_mpio", "geometry"]].merge(data, on="cod_mpio", how="left")
    plot = to_metric(plot)
    plot["geometry"] = plot.geometry.simplify(2800, preserve_topology=True)
    values = safe_num(plot[variable])
    valid = plot.loc[values.notna()].copy()
    cmap_obj = CMAPS[cmap] if cmap in CMAPS else plt.get_cmap(cmap)
    if centered and values.notna().any():
        limit = float(np.nanpercentile(np.abs(values.dropna()), 98))
        if not np.isfinite(limit) or limit == 0:
            limit = float(np.nanmax(np.abs(values)))
        norm = mcolors.TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)
    else:
        vmin = float(np.nanpercentile(values.dropna(), 2)) if values.notna().any() else 0.0
        vmax = float(np.nanpercentile(values.dropna(), 98)) if values.notna().any() else 1.0
        if vmin == vmax:
            vmin, vmax = float(values.min()), float(values.max())
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    fig, ax = plt.subplots(figsize=(5.9, 7.9))
    fig.patch.set_facecolor(BASE["page"])
    ax.set_facecolor(BASE["basemap"])
    plot.plot(
        ax=ax,
        color=BASE["polygon"],
        edgecolor=BASE["boundary"],
        linewidth=0.08,
        zorder=1,
    )
    plot.plot(
        column=variable,
        ax=ax,
        cmap=cmap_obj,
        norm=norm,
        linewidth=0.06,
        edgecolor="#c6ccd3",
        legend=False,
        zorder=2,
    )
    if variable == "brecha_spatial_z" and values.notna().any():
        cutoff = float(values.quantile(0.90))
        plot.loc[values >= cutoff].boundary.plot(ax=ax, color="#8f2428", linewidth=0.28, zorder=4)
    mainland = plot.loc[~plot["cod_mpio"].astype(str).str.startswith("88")].copy()
    set_map_bounds(ax, mainland if not mainland.empty else plot)
    add_panel_label(ax, title)
    add_north_arrow(ax)
    add_scale_bar(ax)
    islands = plot.loc[plot["cod_mpio"].astype(str).str.startswith("88")].copy()
    if not islands.empty:
        iax = inset_axes(ax, width="16%", height="16%", loc="upper left", borderpad=0.55)
        iax.set_facecolor("white")
        islands.plot(ax=iax, color=BASE["polygon"], edgecolor=BASE["boundary"], linewidth=0.12, zorder=1)
        islands.plot(column=variable, ax=iax, cmap=cmap_obj, norm=norm, linewidth=0.10, edgecolor="#aab3bd", zorder=2)
        iax.set_axis_off()
        iax.set_aspect("equal")
        iax.text(
            0.02,
            0.02,
            "Island frame",
            transform=iax.transAxes,
            ha="left",
            va="bottom",
            fontsize=4.3,
            color=BASE["boundary_dark"],
        )
    sm = cm.ScalarMappable(norm=norm, cmap=cmap_obj)
    sm.set_array([])
    cbar = fig.colorbar(
        sm,
        ax=ax,
        orientation="horizontal",
        shrink=0.54,
        pad=0.012,
        fraction=0.030,
        aspect=26,
    )
    cbar.set_label(legend_label, fontsize=5.8, labelpad=2.2)
    cbar.outline.set_linewidth(0.4)
    cbar.ax.tick_params(labelsize=5.4, width=0.35, length=1.7)
    if note:
        ax.text(
            0.01,
            0.015,
            note,
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=5.4,
            color=BASE["boundary_dark"],
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.72, pad=1.3),
            zorder=90,
        )
    fig.tight_layout(pad=0.18)
    save_publication_figure(fig, filename)
    plt.close(fig)


def draw_map_panel(
    ax: plt.Axes,
    plot: gpd.GeoDataFrame,
    variable: str,
    title: str,
    cmap_name: str,
    norm: mcolors.Normalize,
    legend_label: str,
    outline_top_decile: bool = False,
) -> None:
    """Draw a compact map panel using the same geography as the main maps."""
    cmap_obj = CMAPS[cmap_name] if cmap_name in CMAPS else plt.get_cmap(cmap_name)
    ax.set_facecolor(BASE["basemap"])
    plot.plot(ax=ax, color=BASE["polygon"], edgecolor=BASE["boundary"], linewidth=0.045, zorder=1)
    plot.plot(
        column=variable,
        ax=ax,
        cmap=cmap_obj,
        norm=norm,
        linewidth=0.035,
        edgecolor="#c6ccd3",
        legend=False,
        zorder=2,
    )
    if outline_top_decile and plot[variable].notna().any():
        cutoff = float(safe_num(plot["brecha_spatial_z"]).quantile(0.90))
        plot.loc[safe_num(plot["brecha_spatial_z"]) >= cutoff].boundary.plot(
            ax=ax,
            color="#8f2428",
            linewidth=0.22,
            zorder=4,
        )
    mainland = plot.loc[~plot["cod_mpio"].astype(str).str.startswith("88")].copy()
    set_map_bounds(ax, mainland if not mainland.empty else plot, pad=0.035)
    ax.set_title(title, loc="left", pad=2.5, fontsize=7.2, fontweight="semibold", color=BASE["text"])
    ax.text(
        0.02,
        0.025,
        legend_label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=5.2,
        color=BASE["boundary_dark"],
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.72, pad=1.0),
        zorder=90,
    )


def build_spatial_decomposition_figure(panel: pd.DataFrame, gdf: gpd.GeoDataFrame) -> None:
    """Create the main visual plate linking gap, components and scatter."""
    df = panel[(panel["year"] == 2024) & panel["brecha_spatial_z"].notna()].copy()
    map_data = df[["cod_mpio", "brecha_spatial_z", "access_spatial_z", "need_proxy_z"]].copy()
    plot = gdf[["cod_mpio", "geometry"]].merge(map_data, on="cod_mpio", how="left")
    plot = to_metric(plot)
    plot["geometry"] = plot.geometry.simplify(2800, preserve_topology=True)

    z_values = pd.concat(
        [
            safe_num(plot["brecha_spatial_z"]),
            safe_num(plot["access_spatial_z"]),
            safe_num(plot["need_proxy_z"]),
        ],
        ignore_index=True,
    ).dropna()
    z_limit = float(np.nanpercentile(np.abs(z_values), 98)) if not z_values.empty else 3.0
    if not np.isfinite(z_limit) or z_limit <= 0:
        z_limit = 3.0
    z_norm = mcolors.TwoSlopeNorm(vmin=-z_limit, vcenter=0, vmax=z_limit)

    fig = plt.figure(figsize=(7.4, 7.25))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.0], hspace=0.28, wspace=0.06)
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]
    fig.patch.set_facecolor(BASE["page"])

    draw_map_panel(
        axes[0],
        plot,
        "brecha_spatial_z",
        "A. Gap score",
        "gap_diverging",
        z_norm,
        "need - accessibility (z)",
        outline_top_decile=True,
    )
    draw_map_panel(
        axes[1],
        plot,
        "access_spatial_z",
        "B. Accessibility score",
        "access_inverse",
        z_norm,
        "access score (z)",
    )
    draw_map_panel(
        axes[2],
        plot,
        "need_proxy_z",
        "C. Need score",
        "gap_diverging",
        z_norm,
        "need score (z)",
    )

    ax = axes[3]
    mask = df["brecha_spatial_z"] >= df["brecha_spatial_z"].quantile(0.90)
    ax.scatter(
        df.loc[~mask, "access_spatial_z"],
        df.loc[~mask, "need_proxy_z"],
        c=BASE["blue"],
        s=8,
        alpha=0.30,
        linewidth=0,
        label="Other municipalities",
    )
    ax.scatter(
        df.loc[mask, "access_spatial_z"],
        df.loc[mask, "need_proxy_z"],
        c=BASE["reference_red"],
        s=13,
        alpha=0.82,
        linewidth=0.20,
        edgecolor="white",
        label="Top-decile gap",
    )
    x = safe_num(df["access_spatial_z"])
    y = safe_num(df["need_proxy_z"])
    ok = x.notna() & y.notna()
    if ok.sum() > 2:
        lo = float(min(x[ok].min(), y[ok].min()))
        hi = float(max(x[ok].max(), y[ok].max()))
        ax.plot([lo, hi], [lo, hi], color=BASE["boundary_dark"], linewidth=0.75, linestyle=(0, (3, 2)), label="Need = accessibility")
    ax.axhline(0, color=BASE["boundary_dark"], linewidth=0.50)
    ax.axvline(0, color=BASE["boundary_dark"], linewidth=0.50)
    ax.text(
        0.035,
        0.955,
        "D. Need-accessibility space",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=7.2,
        fontweight="semibold",
        color=BASE["text"],
    )
    ax.set_xlabel("Spatial accessibility score (z)")
    ax.set_ylabel("Need score (z)")
    ax.grid(True)
    ax.legend(frameon=False, loc="upper right", handlelength=1.6, borderpad=0.2, labelspacing=0.35)
    ax.spines[["top", "right"]].set_visible(False)

    fig.text(
        0.015,
        0.010,
        "Municipal 2024 values. Accessibility uses REPS-enabled sites, centroid travel times and no OSRM-routed matrix.",
        ha="left",
        va="bottom",
        fontsize=5.8,
        color=BASE["muted"],
    )
    save_publication_figure(fig, "fig_1_spatial_decomposition_2024.png")
    plt.close(fig)


def build_workflow_figure() -> None:
    """Create a restrained methods figure in the style of a journal table."""
    fig, ax = plt.subplots(figsize=(7.2, 3.15))
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    text_color = "#111111"
    muted = "#555555"
    rule = "#2f2f2f"
    light_rule = "#b8b8b8"
    row_fill = "#f7f7f7"

    ax.text(
        0.025,
        0.935,
        "Municipal screening construct",
        ha="left",
        va="top",
        fontsize=9.0,
        fontweight="semibold",
        color=text_color,
    )
    ax.text(
        0.025,
        0.885,
        "Analytical roles, transformations and outputs used to estimate the 2024 potential-accessibility gap.",
        ha="left",
        va="top",
        fontsize=6.4,
        color=muted,
    )

    left, right = 0.025, 0.975
    top = 0.790
    header_bottom = 0.705
    bottom = 0.215
    col_edges = [left, 0.205, 0.465, 0.680, 0.820, right]
    col_text = [0.035, 0.220, 0.480, 0.695, 0.835]
    headers = ["Analytical role", "Observed source", "Transformation", "Output", "Interpretation"]

    ax.hlines([top, header_bottom, bottom], left, right, colors=rule, linewidths=[0.85, 0.55, 0.85])
    for x in col_edges[1:-1]:
        ax.vlines(x, bottom, top, colors=light_rule, linewidth=0.35)

    for x, header in zip(col_text, headers):
        ax.text(x, 0.748, header, ha="left", va="center", fontsize=6.15, fontweight="semibold", color=text_color)

    rows = [
        (
            "Need signal",
            "SIVIGILA attempted-suicide\nnotifications; DANE IPM",
            "Within-year standardisation\nand component averaging",
            r"$Need_{it}$",
            "Severe surveillance and\nsocial vulnerability signal",
        ),
        (
            "Service\nopportunity",
            "REPS-enabled sites; DANE\npopulation; centroid matrix",
            "Hansen and E2SFCA\naccessibility metrics",
            r"$Access_{it}$",
            "Potential accessibility,\nnot realised care",
        ),
        (
            "Territorial\nmismatch",
            "Need and accessibility\non the municipal scale",
            "Standardised difference:\n" + r"$Need_{it}-Access_{it}$",
            r"$Gap_{it}$",
            "Maps, ranked excerpts\nand Moran's I",
        ),
    ]
    row_tops = [header_bottom, 0.545, 0.385]
    row_bottoms = [0.545, 0.385, bottom]
    row_centers = [(a + b) / 2 for a, b in zip(row_tops, row_bottoms)]

    for idx, (y0, y1) in enumerate(zip(row_tops, row_bottoms)):
        if idx % 2 == 1:
            ax.add_patch(mpatches.Rectangle((left, y1), right - left, y0 - y1, facecolor=row_fill, edgecolor="none"))
        ax.hlines(y1, left, right, colors=light_rule, linewidth=0.35)

    for y, cells in zip(row_centers, rows):
        for cidx, (x, cell) in enumerate(zip(col_text, cells)):
            ax.text(
                x,
                y,
                cell,
                ha="left",
                va="center",
                fontsize=5.9 if cidx != 3 else 7.0,
                fontweight="semibold" if cidx in (0, 3) else "normal",
                color=text_color if cidx in (0, 3) else muted,
                linespacing=1.10,
            )

    ax.hlines(0.145, left, right, colors=rule, linewidth=0.55)
    ax.text(0.025, 0.108, "Claim boundary", ha="left", va="center", fontsize=6.2, fontweight="semibold", color=text_color)
    ax.text(
        0.185,
        0.108,
        "Ecological municipal screening; broad REPS supply measure; centroid travel-time approximation; OSRM routing and provider geocoding remain pending.",
        ha="left",
        va="center",
        fontsize=5.85,
        color=muted,
    )

    fig.tight_layout(pad=0.12)
    save_publication_figure(fig, "fig_0_workflow.png")
    plt.close(fig)


def make_figures(panel: pd.DataFrame, departments: pd.DataFrame, gdf: gpd.GeoDataFrame) -> None:
    set_publication_style()
    build_spatial_decomposition_figure(panel, gdf)
    map_variable(
        gdf,
        panel,
        "brecha_spatial_z",
        "Potential-accessibility gap, 2024",
        "fig_1_gap_map_2024.png",
        "gap_diverging",
        "gap (z)",
        centered=True,
        note="Centroid proxy travel-time surface",
    )
    map_variable(
        gdf,
        panel,
        "e2sfca_sedes_all_120min",
        "E2SFCA potential accessibility, 2024",
        "fig_2_e2sfca_accessibility_map_2024.png",
        "access_blue",
        "E2SFCA",
        note="REPS-enabled sites; proxy travel time",
    )
    map_variable(
        gdf,
        panel,
        "need_proxy_z",
        "Need score proxy, 2024",
        "fig_3_need_proxy_map_2024.png",
        "need_pink",
        "need (z)",
        centered=False,
        note="Attempted-suicide notifications + IPM",
    )

    df = panel[(panel["year"] == 2024) & panel["brecha_spatial_z"].notna()].copy()
    cutoff = df["brecha_spatial_z"].quantile(0.90)
    fig, ax = plt.subplots(figsize=(5.6, 3.9))
    fig.patch.set_facecolor(BASE["page"])
    mask = df["brecha_spatial_z"] >= cutoff
    ax.scatter(
        df.loc[~mask, "access_spatial_z"],
        df.loc[~mask, "need_proxy_z"],
        c=BASE["blue"],
        s=9,
        alpha=0.34,
        linewidth=0,
        label="Other municipalities",
    )
    ax.scatter(
        df.loc[mask, "access_spatial_z"],
        df.loc[mask, "need_proxy_z"],
        c=BASE["reference_red"],
        s=14,
        alpha=0.82,
        linewidth=0.22,
        edgecolor="white",
        label="Top-decile gap",
    )
    x = safe_num(df["access_spatial_z"])
    y = safe_num(df["need_proxy_z"])
    ok = x.notna() & y.notna()
    if ok.sum() > 2:
        lo = float(min(x[ok].min(), y[ok].min()))
        hi = float(max(x[ok].max(), y[ok].max()))
        ax.plot([lo, hi], [lo, hi], color=BASE["boundary_dark"], linewidth=0.75, linestyle=(0, (3, 2)), label="Need = accessibility")
    ax.axhline(0, color=BASE["boundary_dark"], linewidth=0.55)
    ax.axvline(0, color=BASE["boundary_dark"], linewidth=0.55)
    ax.set_xlabel("Spatial accessibility score (z)")
    ax.set_ylabel("Need score (z)")
    ax.set_title("Need and potential accessibility, 2024", loc="left", pad=6)
    ax.grid(True)
    ax.legend(frameon=False, loc="upper right", handlelength=1.6, borderpad=0.2, labelspacing=0.35)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.45)
    save_publication_figure(fig, "fig_4_need_access_scatter_2024.png")
    plt.close(fig)

    dep = departments.sort_values("mean_gap_z", ascending=False)
    show = pd.concat([dep.head(10), dep.tail(10)]).drop_duplicates("departamento")
    label_map = {
        "Archipiélago de San Andrés, Providencia y Santa Catalina": "San Andrés and Providencia",
    }
    labels = [fill(label_map.get(name, name), width=22) for name in show["departamento"]]
    fig, ax = plt.subplots(figsize=(6.2, 5.1))
    fig.patch.set_facecolor(BASE["page"])
    colors = [BASE["reference_red"] if v > 0 else BASE["blue"] for v in show["mean_gap_z"]]
    ax.barh(labels, show["mean_gap_z"], color=colors, edgecolor=BASE["boundary_dark"], linewidth=0.30)
    ax.axvline(0, color=BASE["boundary_dark"], linewidth=0.65)
    ax.invert_yaxis()
    ax.set_xlabel("Mean potential-accessibility gap (z)")
    ax.set_title("Department mean municipal gap, 2024", loc="left", pad=5)
    ax.tick_params(axis="y", labelsize=6.2)
    ax.grid(axis="x")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.45)
    save_publication_figure(fig, "fig_5_department_gap_bar_2024.png")
    plt.close(fig)

    years = [2021, 2022, 2023, 2024]
    rows = []
    for year in years:
        values = (
            panel[(panel["year"] == year) & panel["brecha_spatial_z"].notna()]["brecha_spatial_z"]
            .astype(float)
            .dropna()
            .to_numpy()
        )
        pct = np.nanpercentile(values, [5, 10, 25, 50, 75, 90, 95])
        rows.append({"year": year, "n": len(values), "p5": pct[0], "p10": pct[1], "p25": pct[2], "p50": pct[3], "p75": pct[4], "p90": pct[5], "p95": pct[6]})

    fig, ax = plt.subplots(figsize=(5.7, 3.35))
    fig.patch.set_facecolor(BASE["page"])
    y_positions = np.arange(len(rows))[::-1]
    for y_pos, row in zip(y_positions, rows):
        ax.hlines(y_pos, row["p5"], row["p95"], color="#c7ccd3", lw=2.0, zorder=1)
        ax.hlines(y_pos, row["p10"], row["p90"], color=BASE["blue"], lw=4.0, alpha=0.55, zorder=2)
        ax.hlines(y_pos, row["p25"], row["p75"], color=BASE["blue"], lw=7.5, alpha=0.80, zorder=3)
        ax.scatter(row["p50"], y_pos, s=22, color="white", edgecolor=BASE["boundary_dark"], linewidth=0.65, zorder=5, label="median" if y_pos == y_positions[0] else None)
        ax.scatter(row["p90"], y_pos, marker="D", s=25, color=BASE["reference_red"], edgecolor="white", linewidth=0.45, zorder=6, label="90th percentile" if y_pos == y_positions[0] else None)
        ax.text(row["p90"] + 0.055, y_pos, f"p90={row['p90']:.2f}", va="center", ha="left", fontsize=5.7, color=BASE["reference_red"])
        ax.text(-2.45, y_pos - 0.18, f"n={row['n']:,}", va="center", ha="left", fontsize=5.2, color=BASE["muted"])
    ax.axvline(0, color=BASE["boundary_dark"], linewidth=0.65)
    ax.set_yticks(y_positions)
    ax.set_yticklabels([str(row["year"]) for row in rows])
    ax.set_xlim(-2.55, 2.65)
    ax.set_xlabel("Potential-accessibility gap (z)")
    ax.set_title("Gap percentile profile by year", loc="left", pad=5)
    ax.grid(axis="x")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout(pad=0.45)
    save_publication_figure(fig, "fig_6_gap_distribution_by_year.png")
    plt.close(fig)

    build_workflow_figure()


def write_results_narrative(
    coverage: pd.DataFrame,
    yearly: pd.DataFrame,
    departments: pd.DataFrame,
    top_gap: pd.DataFrame,
    moran: pd.DataFrame,
) -> None:
    top = top_gap.iloc[0]
    dep_top = departments.iloc[0]
    dep_low = departments.sort_values("mean_gap_z").iloc[0]
    text = f"""# Empirical Results Summary

Claim boundary: these results are based on a centroid travel-time proxy. They
support a reproducible potential-accessibility screening analysis. OSRM-routed
travel times should replace the proxy before making routed road-network claims.

## Coverage

The analytic panel contains {int(coverage.loc[coverage['item'].eq('Municipalities in panel'), 'value'].iloc[0]):,}
municipalities and {int(coverage.loc[coverage['item'].eq('Municipality-year panel rows'), 'value'].iloc[0]):,}
municipality-year rows. In 2024, the spatial gap is non-missing for
{int(coverage.loc[coverage['item'].eq('Municipalities with non-missing spatial gap in 2024'), 'value'].iloc[0]):,}
municipalities.

## Main 2024 pattern

The highest 2024 spatial gap in the current proxy is {top['municipio']},
{top['departamento']} (`{top['cod_mpio']}`), with `brecha_spatial_z =
{top['brecha_spatial_z']:.2f}`. The department with the highest mean municipal
gap is {dep_top['departamento']} (`mean_gap_z = {dep_top['mean_gap_z']:.2f}`),
while the lowest mean gap is in {dep_low['departamento']} (`mean_gap_z =
{dep_low['mean_gap_z']:.2f}`).

## Spatial clustering

The queen-contiguity Moran's I for the 2024 gap is {moran['moran_i'].iloc[0]:.3f}
using {int(moran['edge_pairs'].iloc[0]):,} undirected neighbour pairs
(`p_greater = {moran['p_permutation_greater'].iloc[0]:.3f}`, 499 permutations).
This supports reporting spatial clustering descriptively, not causally.

## Output use

Use Table 1 for data coverage, Table 2 for yearly summary, Table 3 for
departmental comparison, Table 4 for high-gap municipalities, Table 5 for
top-decile decomposition, Table 6 for correlation structure, and Table 7 for
spatial autocorrelation. Figures 0-6 provide workflow, maps, scatter and
distribution evidence.
"""
    (OUT / "empirical_results_summary.md").write_text(text, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    panel, seed, gdf = load_data()
    coverage = table_data_coverage(panel, seed)
    yearly = table_yearly_summary(panel, seed)
    departments = table_departments_2024(panel)
    top_gap = table_top_gap_2024(panel, seed)
    table_high_gap_decomposition(panel, seed)
    table_correlations_2024(panel)
    moran = moran_i_2024(panel, gdf)
    make_figures(panel, departments, gdf)
    write_results_narrative(coverage, yearly, departments, top_gap, moran)
    print(f"Wrote final outputs to {OUT}")
    print((OUT / "empirical_results_summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
