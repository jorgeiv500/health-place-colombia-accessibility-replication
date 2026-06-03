#!/usr/bin/env python3
"""Build illustrative planning-scenario maps for the accessibility analysis.

The scenarios are not evaluated interventions. They recompute the existing
centroid-based E2SFCA surface under transparent service-opportunity and
effective-impedance assumptions to show how the framework can support
planning once local validation is available.
"""

from __future__ import annotations

import math
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from generate_final_outputs import (
    BASE,
    CMAPS,
    FIGURES,
    ROOT,
    SPATIAL,
    set_map_bounds,
    set_publication_style,
    to_metric,
)


WORK = ROOT / "data_work"
SCENARIOS = ROOT / "final_outputs" / "scenarios"

YEAR = 2024
TOP_DECILE_Q = 0.90
HUB_COUNT = 12
DISTRIBUTED_UNITS = 5.0
HUB_UNITS = 30.0
CONNECTIVITY_MULTIPLIER = 0.90
THRESHOLD_MIN = 120.0


def safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def e2sfca_decay(time_min: pd.Series, threshold: float = THRESHOLD_MIN) -> pd.Series:
    time = safe_num(time_min)
    weights = pd.Series(0.0, index=time.index)
    weights[time <= 30] = 1.0
    weights[(time > 30) & (time <= 60)] = 0.68
    weights[(time > 60) & (time <= 120)] = 0.22
    if threshold > 120:
        weights[(time > 120) & (time <= threshold)] = 0.10
    weights[time > threshold] = 0.0
    return weights


def z_from_baseline(values: pd.Series, baseline_values: pd.Series) -> pd.Series:
    baseline = safe_num(baseline_values)
    mean = baseline.mean()
    sd = baseline.std(ddof=0)
    if pd.isna(sd) or sd == 0:
        return pd.Series(0.0, index=values.index)
    return (safe_num(values) - mean) / sd


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, gpd.GeoDataFrame]:
    panel = pd.read_csv(
        SPATIAL / "municipal_panel_spatial_access_2021_2025.csv",
        dtype={"cod_dpto": str, "cod_mpio": str},
    )
    matrix = pd.read_csv(
        SPATIAL / "travel_time_matrix_municipio_municipio_proxy.csv",
        dtype={"origin_cod_mpio": str, "dest_cod_mpio": str},
    )
    gdf = gpd.read_file(ROOT / "data_raw/dane/MGN2025_municipio_317.geojson")
    gdf["cod_mpio"] = gdf["MPIO_CDPMP"].astype(str).str.zfill(5)
    for df in [panel, matrix]:
        for col in ["cod_mpio", "origin_cod_mpio", "dest_cod_mpio"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.zfill(5)
    return panel, matrix, gdf


def select_planning_targets(current: pd.DataFrame) -> tuple[pd.Index, list[str]]:
    cutoff = current["brecha_spatial_z"].quantile(TOP_DECILE_Q)
    top = current[current["brecha_spatial_z"] >= cutoff].copy()
    top = top.sort_values("brecha_spatial_z", ascending=False)

    first_by_dept = (
        top.sort_values("brecha_spatial_z", ascending=False)
        .groupby("cod_dpto", as_index=False)
        .head(1)
        .sort_values("brecha_spatial_z", ascending=False)
    )
    hubs = first_by_dept["cod_mpio"].head(HUB_COUNT).tolist()
    return top.index, hubs


def compute_e2sfca(
    matrix: pd.DataFrame,
    current: pd.DataFrame,
    supply: pd.Series,
    time_multiplier_origins: set[str] | None = None,
    multiplier: float = 1.0,
) -> pd.Series:
    pairs = matrix[
        [
            "origin_cod_mpio",
            "dest_cod_mpio",
            "travel_time_proxy_min",
        ]
    ].copy()
    pairs["time_effective_min"] = safe_num(pairs["travel_time_proxy_min"])
    if time_multiplier_origins:
        origin_mask = pairs["origin_cod_mpio"].isin(time_multiplier_origins)
        pairs.loc[origin_mask, "time_effective_min"] = np.maximum(
            10.0, pairs.loc[origin_mask, "time_effective_min"] * multiplier
        )
    pairs = pairs[pairs["time_effective_min"] <= THRESHOLD_MIN].copy()
    pairs["decay"] = e2sfca_decay(pairs["time_effective_min"], THRESHOLD_MIN)

    population = current.set_index("cod_mpio")["population_total"].pipe(safe_num).fillna(0.0)
    pairs["origin_population"] = pairs["origin_cod_mpio"].map(population).fillna(0.0)
    pairs["supply"] = pairs["dest_cod_mpio"].map(supply).fillna(0.0)

    denom = (
        pairs.assign(weighted_population=pairs["origin_population"] * pairs["decay"])
        .groupby("dest_cod_mpio", as_index=True)["weighted_population"]
        .sum()
        .replace(0, np.nan)
    )
    pairs["provider_to_population_ratio"] = pairs["supply"] / pairs["dest_cod_mpio"].map(denom)
    access = (
        pairs.assign(access=pairs["provider_to_population_ratio"] * pairs["decay"])
        .groupby("origin_cod_mpio", as_index=True)["access"]
        .sum()
    )
    return current["cod_mpio"].map(access).fillna(0.0)


def build_scenarios(panel: pd.DataFrame, matrix: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str], float]:
    current = panel[(panel["year"] == YEAR) & panel["brecha_spatial_z"].notna()].copy()
    current = current.sort_values("cod_mpio").reset_index(drop=True)
    top_idx, hubs = select_planning_targets(current)
    top_codes = set(current.loc[top_idx, "cod_mpio"])

    supply_base = (
        matrix[["dest_cod_mpio", "dest_sedes_reps"]]
        .drop_duplicates("dest_cod_mpio")
        .assign(dest_sedes_reps=lambda d: safe_num(d["dest_sedes_reps"]).fillna(0.0))
        .set_index("dest_cod_mpio")["dest_sedes_reps"]
    )
    current["baseline_e2sfca_recomputed"] = compute_e2sfca(matrix, current, supply_base)
    current["baseline_access_z_recomputed"] = z_from_baseline(
        current["baseline_e2sfca_recomputed"], current["baseline_e2sfca_recomputed"]
    )
    current["baseline_gap_recomputed"] = current["need_proxy_z"] - current["baseline_access_z_recomputed"]
    current["baseline_top_decile"] = current["cod_mpio"].isin(top_codes)
    current["regional_hub"] = current["cod_mpio"].isin(hubs)

    baseline_p90 = current["baseline_gap_recomputed"].quantile(TOP_DECILE_Q)

    scenarios = {
        "distributed_outreach": {
            "label": "Distributed outreach",
            "supply_add": {code: DISTRIBUTED_UNITS for code in top_codes},
            "time_origins": set(),
            "time_multiplier": 1.0,
        },
        "regional_hubs": {
            "label": "Regional service hubs",
            "supply_add": {code: HUB_UNITS for code in hubs},
            "time_origins": set(),
            "time_multiplier": 1.0,
        },
        "connectivity_relief": {
            "label": "Effective impedance relief",
            "supply_add": {},
            "time_origins": top_codes,
            "time_multiplier": CONNECTIVITY_MULTIPLIER,
        },
        "combined": {
            "label": "Combined scenario",
            "supply_add": {
                **{code: DISTRIBUTED_UNITS for code in top_codes},
                **{code: HUB_UNITS + (DISTRIBUTED_UNITS if code in top_codes else 0.0) for code in hubs},
            },
            "time_origins": top_codes,
            "time_multiplier": CONNECTIVITY_MULTIPLIER,
        },
    }

    out = current[
        [
            "cod_dpto",
            "departamento",
            "cod_mpio",
            "municipio",
            "population_total",
            "need_proxy_z",
            "access_spatial_z",
            "brecha_spatial_z",
            "baseline_e2sfca_recomputed",
            "baseline_access_z_recomputed",
            "baseline_gap_recomputed",
            "baseline_top_decile",
            "regional_hub",
        ]
    ].copy()

    summary_rows = []
    for scenario_id, spec in scenarios.items():
        supply = supply_base.copy()
        for code, add in spec["supply_add"].items():
            supply.loc[code] = supply.get(code, 0.0) + add
        scenario_e2 = compute_e2sfca(
            matrix,
            current,
            supply,
            time_multiplier_origins=spec["time_origins"],
            multiplier=spec["time_multiplier"],
        )
        access_z = z_from_baseline(scenario_e2, current["baseline_e2sfca_recomputed"])
        gap_z = current["need_proxy_z"] - access_z
        out[f"{scenario_id}_e2sfca"] = scenario_e2
        out[f"{scenario_id}_access_z"] = access_z
        out[f"{scenario_id}_gap_z"] = gap_z
        out[f"{scenario_id}_access_gain_z"] = access_z - current["baseline_access_z_recomputed"]
        out[f"{scenario_id}_gap_reduction_z"] = current["baseline_gap_recomputed"] - gap_z

        top = out["baseline_top_decile"]
        summary_rows.append(
            {
                "scenario_id": scenario_id,
                "label": spec["label"],
                "supply_units_added_total": sum(spec["supply_add"].values()),
                "municipalities_with_added_supply": len(spec["supply_add"]),
                "effective_time_multiplier_for_baseline_top_decile": spec["time_multiplier"]
                if spec["time_origins"]
                else np.nan,
                "mean_access_gain_top_decile_z": out.loc[top, f"{scenario_id}_access_gain_z"].mean(),
                "median_access_gain_top_decile_z": out.loc[top, f"{scenario_id}_access_gain_z"].median(),
                "mean_gap_reduction_top_decile_z": out.loc[top, f"{scenario_id}_gap_reduction_z"].mean(),
                "median_gap_reduction_top_decile_z": out.loc[top, f"{scenario_id}_gap_reduction_z"].median(),
                "baseline_top_decile_moved_below_baseline_p90": int(
                    (out.loc[top, f"{scenario_id}_gap_z"] < baseline_p90).sum()
                ),
                "baseline_top_decile_n": int(top.sum()),
                "mean_gap_all_z": gap_z.mean(),
                "mean_gap_top_decile_z": gap_z[top].mean(),
                "max_gap_z": gap_z.max(),
                "p90_gap_z": gap_z.quantile(TOP_DECILE_Q),
            }
        )
    summary = pd.DataFrame(summary_rows)

    current_match = current["access_spatial_z"].corr(current["baseline_access_z_recomputed"])
    summary.attrs["baseline_access_correlation"] = current_match
    return out, summary, hubs, baseline_p90


def merge_geometry(results: pd.DataFrame, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    plot = gdf[["cod_mpio", "geometry"]].merge(results, on="cod_mpio", how="left")
    plot = to_metric(plot)
    plot["geometry"] = plot.geometry.simplify(2800, preserve_topology=True)
    return plot


def draw_map(ax: plt.Axes, plot: gpd.GeoDataFrame, column: str, title: str, cmap: str, norm: mcolors.Normalize) -> None:
    cmap_obj = CMAPS[cmap] if cmap in CMAPS else plt.get_cmap(cmap)
    ax.set_facecolor(BASE["basemap"])
    plot.plot(ax=ax, color=BASE["polygon"], edgecolor=BASE["boundary"], linewidth=0.04, zorder=1)
    plot.plot(column=column, ax=ax, cmap=cmap_obj, norm=norm, edgecolor="#c6ccd3", linewidth=0.03, zorder=2)
    mainland = plot.loc[~plot["cod_mpio"].astype(str).str.startswith("88")]
    set_map_bounds(ax, mainland if not mainland.empty else plot, pad=0.035)
    ax.set_title(title, loc="left", fontsize=7.2, fontweight="semibold", color=BASE["text"], pad=2.5)


def draw_proposal_map(ax: plt.Axes, plot: gpd.GeoDataFrame) -> None:
    ax.set_facecolor(BASE["basemap"])
    plot.plot(ax=ax, color="#f5f5f5", edgecolor=BASE["boundary"], linewidth=0.04, zorder=1)
    plot.loc[plot["baseline_top_decile"].fillna(False)].plot(
        ax=ax, color="#d8a39c", edgecolor="#ffffff", linewidth=0.04, zorder=2
    )
    hubs = plot.loc[plot["regional_hub"].fillna(False)].copy()
    if not hubs.empty:
        pts = hubs.representative_point()
        ax.scatter(pts.x, pts.y, s=13, color="#111827", edgecolor="white", linewidth=0.35, zorder=4)
    mainland = plot.loc[~plot["cod_mpio"].astype(str).str.startswith("88")]
    set_map_bounds(ax, mainland if not mainland.empty else plot, pad=0.035)
    ax.set_title("C. Scenario geography", loc="left", fontsize=7.2, fontweight="semibold", color=BASE["text"], pad=2.5)
    ax.text(
        0.02,
        0.04,
        "Shaded: baseline top decile\nDots: regional hubs",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=5.5,
        color=BASE["boundary_dark"],
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.76, pad=1.1),
    )


def draw_scatter(ax: plt.Axes, results: pd.DataFrame) -> None:
    top = results["baseline_top_decile"]
    ax.scatter(
        results.loc[~top, "baseline_gap_recomputed"],
        results.loc[~top, "combined_gap_z"],
        s=7,
        color=BASE["blue"],
        alpha=0.25,
        linewidth=0,
        label="Other municipalities",
    )
    ax.scatter(
        results.loc[top, "baseline_gap_recomputed"],
        results.loc[top, "combined_gap_z"],
        s=13,
        color=BASE["reference_red"],
        alpha=0.82,
        linewidth=0.2,
        edgecolor="white",
        label="Baseline top decile",
    )
    lo = min(results["baseline_gap_recomputed"].min(), results["combined_gap_z"].min())
    hi = max(results["baseline_gap_recomputed"].max(), results["combined_gap_z"].max())
    ax.plot([lo, hi], [lo, hi], color=BASE["boundary_dark"], linewidth=0.75, linestyle=(0, (3, 2)))
    ax.set_xlabel("Current gap (z)", fontsize=6.8, labelpad=2.0)
    ax.set_ylabel("Residual gap (z)", fontsize=6.8, labelpad=1.5)
    ax.set_title("F. Current vs residual gap", loc="left", fontsize=7.2, fontweight="semibold", color=BASE["text"], pad=2.5)
    ax.grid(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left", fontsize=5.8, handlelength=1.3, labelspacing=0.25)


def save_figure(fig: plt.Figure, stem: str) -> None:
    png = FIGURES / f"{stem}.png"
    pdf = FIGURES / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")


def markdown_table(df: pd.DataFrame) -> str:
    """Return a simple GitHub-flavoured Markdown table without dependencies."""
    if df.empty:
        return "_No rows._"
    display = df.copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda x: "" if pd.isna(x) else f"{x:.3f}")
        else:
            display[col] = display[col].map(lambda x: "" if pd.isna(x) else str(x))
    cols = list(display.columns)
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in cols) + " |")
    return "\n".join(lines)


def build_story_figures(results: pd.DataFrame, gdf: gpd.GeoDataFrame) -> None:
    set_publication_style()
    plot = merge_geometry(results, gdf)
    z_values = pd.concat(
        [
            safe_num(plot["baseline_access_z_recomputed"]),
            safe_num(plot["baseline_gap_recomputed"]),
            safe_num(plot["combined_gap_z"]),
        ]
    ).dropna()
    zlim = max(2.5, float(np.nanpercentile(np.abs(z_values), 98)))
    z_norm = mcolors.TwoSlopeNorm(vmin=-zlim, vcenter=0, vmax=zlim)
    gain_norm = mcolors.Normalize(
        vmin=0.0,
        vmax=float(np.nanpercentile(safe_num(plot["combined_access_gain_z"]).dropna(), 98)),
    )

    # Compact before/after maps.
    fig1, axes = plt.subplots(2, 2, figsize=(7.1, 6.5))
    draw_map(axes[0, 0], plot, "baseline_access_z_recomputed", "A. Current accessibility", "access_inverse", z_norm)
    draw_map(axes[0, 1], plot, "baseline_gap_recomputed", "B. Current gap", "gap_diverging", z_norm)
    draw_proposal_map(axes[1, 0], plot)
    draw_map(axes[1, 1], plot, "combined_gap_z", "D. Residual gap", "gap_diverging", z_norm)
    fig1.text(
        0.02,
        0.01,
        "Illustrative scenario; not an evaluated intervention. Accessibility uses REPS-enabled sites and centroid travel times.",
        ha="left",
        va="bottom",
        fontsize=6.0,
        color=BASE["muted"],
    )
    fig1.tight_layout(rect=[0, 0.025, 1, 1])
    save_figure(fig1, "fig_7_planning_scenario_story_2024_v1")
    plt.close(fig1)

    # Six-panel scenario sequence.
    fig2 = plt.figure(figsize=(7.4, 7.35))
    gs = fig2.add_gridspec(2, 3, hspace=0.20, wspace=0.08)
    ax = [fig2.add_subplot(gs[i, j]) for i in range(2) for j in range(3)]
    draw_map(ax[0], plot, "baseline_access_z_recomputed", "A. Current accessibility", "access_inverse", z_norm)
    draw_map(ax[1], plot, "baseline_gap_recomputed", "B. Current gap", "gap_diverging", z_norm)
    draw_proposal_map(ax[2], plot)
    draw_map(ax[3], plot, "combined_access_gain_z", "D. Simulated access gain", "access_blue", gain_norm)
    draw_map(ax[4], plot, "combined_gap_z", "E. Residual gap", "gap_diverging", z_norm)
    draw_scatter(ax[5], results)
    fig2.text(
        0.015,
        0.012,
        "Combined scenario = distributed outreach + regional hubs + effective impedance relief. Scenario outputs are planning illustrations, not causal estimates.",
        ha="left",
        va="bottom",
        fontsize=5.8,
        color=BASE["muted"],
    )
    fig2.tight_layout(rect=[0, 0.03, 1, 1])
    save_figure(fig2, "fig_7_planning_scenario_story_2024_v2")
    plt.close(fig2)

    # Final scenario sequence.
    fig3 = plt.figure(figsize=(7.4, 7.15))
    gs = fig3.add_gridspec(2, 3, hspace=0.22, wspace=0.22)
    axes = [fig3.add_subplot(gs[i, j]) for i in range(2) for j in range(3)]
    draw_map(axes[0], plot, "baseline_access_z_recomputed", "A. Current accessibility", "access_inverse", z_norm)
    draw_map(axes[1], plot, "baseline_gap_recomputed", "B. Current gap", "gap_diverging", z_norm)
    draw_proposal_map(axes[2], plot)
    draw_map(axes[3], plot, "combined_access_gain_z", "D. Simulated access gain", "access_blue", gain_norm)
    draw_map(axes[4], plot, "combined_gap_z", "E. Residual gap", "gap_diverging", z_norm)
    draw_scatter(axes[5], results)
    scale_specs = [
        ([0.08, 0.066, 0.22, 0.010], CMAPS["access_inverse"], z_norm, "accessibility z-score"),
        ([0.39, 0.066, 0.22, 0.010], CMAPS["gap_diverging"], z_norm, "gap z-score"),
        ([0.70, 0.066, 0.22, 0.010], CMAPS["access_blue"], gain_norm, "access gain (z)"),
    ]
    for box, cmap_obj, norm_obj, label in scale_specs:
        sm = cm.ScalarMappable(norm=norm_obj, cmap=cmap_obj)
        sm.set_array([])
        cax = fig3.add_axes(box)
        cb = fig3.colorbar(sm, cax=cax, orientation="horizontal")
        cb.set_label(label, fontsize=5.4, labelpad=1.2)
        cb.ax.tick_params(labelsize=5.1, width=0.30, length=1.3)
        cb.outline.set_linewidth(0.30)
    fig3.text(
        0.015,
        0.016,
        "Illustrative 2024 planning scenario using the centroid travel-time matrix; not an evaluated intervention or routed-network claim.",
        ha="left",
        va="bottom",
        fontsize=5.8,
        color=BASE["muted"],
    )
    fig3.subplots_adjust(left=0.035, right=0.985, bottom=0.135, top=0.965, wspace=0.22, hspace=0.22)
    save_figure(fig3, "fig_7_planning_scenario_story_2024_v3")
    save_figure(fig3, "fig_7_planning_scenario_story_2024")
    plt.close(fig3)


def write_outputs(results: pd.DataFrame, summary: pd.DataFrame, hubs: list[str], baseline_p90: float) -> None:
    SCENARIOS.mkdir(parents=True, exist_ok=True)

    results.to_csv(SCENARIOS / "planning_scenario_municipal_2024.csv", index=False)
    summary.to_csv(SCENARIOS / "planning_scenario_summary_2024.csv", index=False)

    hub_table = results.loc[results["regional_hub"], ["cod_mpio", "departamento", "municipio", "baseline_gap_recomputed"]].sort_values(
        "baseline_gap_recomputed", ascending=False
    )
    hub_table.to_csv(SCENARIOS / "planning_scenario_hubs_2024.csv", index=False)

    assumptions = f"""# Planning Scenario Assumptions

These outputs are illustrative planning scenarios, not evaluated interventions.
They use the same public-data constructs as the baseline analysis: REPS-enabled sites
as a municipal supply proxy, DANE population demand, the 2024 need score and
the centroid-based travel-time matrix. OSRM-routed times are not used.

## Baseline

- Year: {YEAR}
- Baseline high-gap threshold: p90 of current gap = {baseline_p90:.3f}
- Baseline top-decile municipalities: {int(results['baseline_top_decile'].sum())}
- E2SFCA catchment: {int(THRESHOLD_MIN)} minutes
- Demand denominator: DANE municipal population
- Standardisation: scenario E2SFCA values are placed on the baseline 2024 E2SFCA z-scale.

## Scenario definitions

- Distributed outreach: adds {DISTRIBUTED_UNITS:.0f} REPS-site-equivalent service-opportunity units to each baseline top-decile municipality.
- Regional service hubs: adds {HUB_UNITS:.0f} REPS-site-equivalent service-opportunity units to {HUB_COUNT} high-gap hub municipalities selected as the highest-gap municipality in high-gap departments.
- Effective impedance relief: multiplies effective centroid travel time by {CONNECTIVITY_MULTIPLIER:.2f} for baseline top-decile origins, with the 10-minute intra-municipal floor retained.
- Combined scenario: combines distributed outreach, regional hubs and effective impedance relief.

The added units are not claims about real facilities, staffing, funding or
implementation feasibility. They are service-opportunity equivalents used to
show how the framework can recompute accessibility surfaces under explicit
planning assumptions.

## Selected regional hubs

{markdown_table(hub_table)}

## Scenario summary

{markdown_table(summary)}
"""
    (SCENARIOS / "planning_scenario_assumptions.md").write_text(assumptions, encoding="utf-8")

def main() -> None:
    panel, matrix, gdf = load_inputs()
    results, summary, hubs, baseline_p90 = build_scenarios(panel, matrix)
    build_story_figures(results, gdf)
    write_outputs(results, summary, hubs, baseline_p90)
    print("Wrote planning scenario outputs:")
    print(f"- {SCENARIOS / 'planning_scenario_municipal_2024.csv'}")
    print(f"- {SCENARIOS / 'planning_scenario_summary_2024.csv'}")
    print(f"- {FIGURES / 'fig_7_planning_scenario_story_2024.pdf'}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
