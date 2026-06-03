#!/usr/bin/env python3
"""Build reproducible municipal panels for the Colombia accessibility analysis.

The script harmonises REPS, RIPS, SIVIGILA, DANE population and poverty
indicators, MGN municipal geography checks, OSM metadata, and selected support
sources into municipality-year and municipality-month tables.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw"
META = RAW / "_metadata"
WORK = ROOT / "data_work"

YEARS = list(range(2019, 2026))
STUDY_YEARS = list(range(2021, 2026))
SIVIGILA_MICRO_YEARS = {2021, 2022, 2023, 2024}
RIPS_YEARS = {2019, 2020, 2021}


def norm_col(value: object) -> str:
    text = "" if value is None else str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def norm_key(value: object) -> str:
    text = "" if value is None else str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^0-9a-z]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def code5(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    if " - " in text:
        text = text.split(" - ", 1)[0]
    match = re.search(r"\d+", text)
    if not match:
        return None
    number = match.group(0)
    if len(number) > 5:
        number = number[:5]
    return f"{int(number):05d}"


def dpto_mun_code(dpto: object, mun: object) -> str | None:
    if pd.isna(dpto) or pd.isna(mun):
        return None
    try:
        return f"{int(float(dpto)):02d}{int(float(mun)):03d}"
    except (TypeError, ValueError):
        return None


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(df: pd.DataFrame, relative: str) -> Path:
    path = WORK / relative
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


def rate_per_100k(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denom = pd.to_numeric(denominator, errors="coerce").replace(0, pd.NA)
    num = pd.to_numeric(numerator, errors="coerce")
    return num / denom * 100_000


def read_population() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    path = RAW / "dane/PPED_AreaMun_2018_2042_VP.xlsx"
    df = pd.read_excel(path, sheet_name="PobMunicipalxÁrea", header=7)
    df.columns = [norm_col(c) for c in df.columns]
    df = df.dropna(subset=["mpio", "ano", "area_geografica"])
    df = df.rename(
        columns={
            "dp": "cod_dpto_num",
            "dpnom": "departamento",
            "mpio": "cod_mpio_num",
            "dpmp": "municipio",
            "ano": "year",
            "total": "population",
        }
    )
    df["year"] = numeric(df["year"]).astype("Int64")
    df = df[df["year"].isin(YEARS)]
    df["cod_mpio"] = df["cod_mpio_num"].map(code5)
    df["cod_dpto"] = df["cod_mpio"].str[:2]
    df["population"] = numeric(df["population"]).astype("Int64")
    df = df[
        [
            "cod_dpto",
            "departamento",
            "cod_mpio",
            "municipio",
            "year",
            "area_geografica",
            "population",
        ]
    ].dropna(subset=["cod_mpio"])
    df = df.sort_values(["cod_mpio", "year", "area_geografica"])
    write_csv(df, "dane_population_municipality_year_area.csv")

    total = (
        df[df["area_geografica"].astype(str).str.lower().eq("total")]
        .drop(columns=["area_geografica"])
        .rename(columns={"population": "population_total"})
        .copy()
    )
    catalog = (
        total.sort_values(["cod_mpio", "year"])
        .drop_duplicates("cod_mpio", keep="last")[
            ["cod_dpto", "departamento", "cod_mpio", "municipio"]
        ]
        .reset_index(drop=True)
    )
    dept_pop = (
        total.groupby(["cod_dpto", "departamento", "year"], as_index=False)[
            "population_total"
        ].sum()
        .rename(columns={"population_total": "department_population_total"})
    )
    return total, catalog, dept_pop


def read_reps_sedes(valid_codes: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = RAW / "minsalud_reps/reps_sedes_c36g_9fc2.csv"
    df = pd.read_csv(path, dtype=str, low_memory=False)
    df["cod_mpio"] = df["municipiosede"].map(code5)
    df = df.dropna(subset=["cod_mpio"])
    invalid = df[~df["cod_mpio"].isin(valid_codes)].copy()
    qa_invalid = (
        invalid.groupby(["cod_mpio", "departamentodededesc", "municipiosededesc"], as_index=False)
        .agg(reps_rows=("codigohabilitacionsede", "size"))
        .sort_values(["cod_mpio"])
        if len(invalid)
        else pd.DataFrame(
            columns=["cod_mpio", "departamentodededesc", "municipiosededesc", "reps_rows"]
        )
    )
    write_csv(qa_invalid, "qa_reps_invalid_municipality_codes.csv")
    df = df[df["cod_mpio"].isin(valid_codes)].copy()
    df["is_ips"] = df["claseprestador"].str.contains(
        "Instituciones Prestadoras", case=False, na=False
    )
    df["is_public"] = df["naturalezajuridica"].str.contains(
        "Publica|Pública", case=False, na=False
    )
    df["is_private"] = df["naturalezajuridica"].str.contains(
        "Privada", case=False, na=False
    )
    base = (
        df.groupby("cod_mpio", as_index=False)
        .agg(
            sedes_reps=("codigohabilitacionsede", "nunique"),
            prestadores_reps=("codigoprestador", "nunique"),
            reps_rows=("codigohabilitacionsede", "size"),
        )
        .set_index("cod_mpio")
    )
    for name, mask in {
        "sedes_ips_reps": df["is_ips"],
        "sedes_publicas_reps": df["is_public"],
        "sedes_privadas_reps": df["is_private"],
    }.items():
        base[name] = df[mask].groupby("cod_mpio")["codigohabilitacionsede"].nunique()
    base = base.fillna(0).astype(int).reset_index()
    if "fecha_corte_reps" in df.columns and df["fecha_corte_reps"].notna().any():
        base["fecha_corte_reps"] = df["fecha_corte_reps"].dropna().mode().iloc[0]
    write_csv(base.sort_values("cod_mpio"), "reps_sedes_by_municipio.csv")
    return base, qa_invalid


def read_reps_capacity(dept_catalog: pd.DataFrame) -> pd.DataFrame:
    path = RAW / "minsalud_reps/reporte_consolidado_departamento_naturaleza_ano_capacidad.zip"
    with zipfile.ZipFile(path) as archive:
        xlsx_names = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".xlsx") and "__macosx" not in name.lower()
        ]
        if not xlsx_names:
            raise FileNotFoundError("No .xlsx workbook inside capacity ZIP")
        with archive.open(xlsx_names[0]) as fh:
            df = pd.read_excel(fh, sheet_name="Hoja1", header=10)
    df.columns = [norm_col(c) for c in df.columns]
    df = df.rename(columns={"ano": "year"})
    df["year"] = numeric(df["year"]).astype("Int64")
    mental_cols = [
        col
        for col in df.columns
        if any(term in col for term in ["mental", "psiquiatria", "farmacodependencia"])
    ]
    for col in mental_cols:
        df[col] = numeric(df[col]).fillna(0)
    df["capacidad_salud_mental_reps"] = df[mental_cols].sum(axis=1)
    agg = (
        df.groupby(["departamento", "year"], as_index=False)
        .agg(
            capacidad_salud_mental_reps=("capacidad_salud_mental_reps", "sum"),
            capacidad_rows_reps=("departamento", "size"),
            **{col: (col, "sum") for col in mental_cols},
        )
        .dropna(subset=["departamento", "year"])
    )

    dept_map = dept_catalog.copy()
    dept_map["dept_key"] = dept_map["departamento"].map(norm_key)
    agg["dept_key"] = agg["departamento"].map(norm_key)
    agg = agg.merge(dept_map[["cod_dpto", "dept_key"]].drop_duplicates(), on="dept_key", how="left")
    manual_dpto = {
        "bogota dc": "11",
        "san andres y providencia": "88",
        "archipielago de san andres providencia y santa catalina": "88",
    }
    agg["cod_dpto"] = agg["cod_dpto"].fillna(agg["dept_key"].map(manual_dpto))
    agg["cod_dpto"] = agg["cod_dpto"].map(lambda x: f"{int(float(x)):02d}" if pd.notna(x) else pd.NA)
    agg = agg.drop(columns=["dept_key"])
    cols = ["cod_dpto", "departamento", "year"] + [
        c for c in agg.columns if c not in {"cod_dpto", "departamento", "year"}
    ]
    agg = agg[cols].sort_values(["cod_dpto", "year"], na_position="last")
    write_csv(agg, "reps_capacidad_departamento_year.csv")
    return agg


def read_rips(valid_codes: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = RAW / "minsalud_rips/rips_salud_mental_f_2019_2021_5e6c_5p2c.csv"
    groups: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, dtype=str, chunksize=150_000):
        chunk["cod_mpio"] = chunk["municipio"].map(code5)
        chunk["year"] = numeric(chunk["a_o"]).astype("Int64")
        chunk["numeroatenciones"] = numeric(chunk["numeroatenciones"]).fillna(0)
        chunk = chunk.dropna(subset=["cod_mpio", "year"])
        grouped = chunk.groupby(["cod_mpio", "year"], as_index=False).agg(
            rips_f_atenciones=("numeroatenciones", "sum"),
            rips_f_rows=("diagnostico", "size"),
            rips_f_diagnosticos_distinct=("diagnostico", "nunique"),
            rips_f_tipos_atencion_distinct=("tipoatencion", "nunique"),
        )
        groups.append(grouped)
    out_all = (
        pd.concat(groups, ignore_index=True)
        .groupby(["cod_mpio", "year"], as_index=False)
        .agg(
            rips_f_atenciones=("rips_f_atenciones", "sum"),
            rips_f_rows=("rips_f_rows", "sum"),
            rips_f_diagnosticos_distinct=("rips_f_diagnosticos_distinct", "max"),
            rips_f_tipos_atencion_distinct=("rips_f_tipos_atencion_distinct", "max"),
        )
        .sort_values(["cod_mpio", "year"])
    )
    invalid = out_all[~out_all["cod_mpio"].isin(valid_codes)].copy()
    out = out_all[out_all["cod_mpio"].isin(valid_codes)].copy()
    write_csv(invalid, "qa_rips_invalid_municipality_codes.csv")
    write_csv(out, "rips_salud_mental_by_municipio_year.csv")
    return out, invalid


def read_sivigila(valid_codes: set[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    annual_parts: list[pd.DataFrame] = []
    monthly_parts: list[pd.DataFrame] = []
    source_dir = RAW / "ins_sivigila"
    for path in sorted(source_dir.glob("Datos_*_356.*")):
        match = re.search(r"Datos_(\d{4})_356", path.name)
        file_year = int(match.group(1)) if match else None
        header = pd.read_excel(path, nrows=0)
        usecols = [
            col
            for col in header.columns
            if norm_col(col)
            in {
                "cod_eve",
                "fec_not",
                "semana",
                "ano",
                "cod_dpto_r",
                "cod_mun_r",
                "cod_dpto_o",
                "cod_mun_o",
                "sexo",
                "edad",
                "confirmados",
                "ajuste",
            }
        ]
        df = pd.read_excel(path, usecols=usecols)
        df.columns = [norm_col(c) for c in df.columns]
        if "ano" in df.columns:
            df["year"] = numeric(df["ano"]).astype("Int64")
        else:
            df["year"] = file_year
        df["cod_mpio"] = [
            dpto_mun_code(dpto, mun)
            for dpto, mun in zip(df.get("cod_dpto_r"), df.get("cod_mun_r"))
        ]
        if "cod_dpto_o" in df.columns and "cod_mun_o" in df.columns:
            df["cod_mpio_ocurrencia"] = [
                dpto_mun_code(dpto, mun)
                for dpto, mun in zip(df["cod_dpto_o"], df["cod_mun_o"])
            ]
        else:
            df["cod_mpio_ocurrencia"] = None
        df["confirmed_case"] = 1
        if "confirmados" in df.columns:
            df["confirmed_case"] = (numeric(df["confirmados"]).fillna(0) == 1).astype(int)
        df["date_notified"] = pd.to_datetime(df.get("fec_not"), errors="coerce")
        df["month"] = df["date_notified"].dt.month.astype("Int64")
        df = df.dropna(subset=["cod_mpio", "year"])

        annual_parts.append(
            df.groupby(["cod_mpio", "year"], as_index=False).agg(
                sivigila_intento_suicidio=("cod_mpio", "size"),
                sivigila_intento_suicidio_confirmados=("confirmed_case", "sum"),
                sivigila_intento_suicidio_occurrence_mpio_distinct=(
                    "cod_mpio_ocurrencia",
                    "nunique",
                ),
            )
        )
        monthly_parts.append(
            df.dropna(subset=["month"])
            .groupby(["cod_mpio", "year", "month"], as_index=False)
            .agg(
                sivigila_intento_suicidio=("cod_mpio", "size"),
                sivigila_intento_suicidio_confirmados=("confirmed_case", "sum"),
            )
        )

    annual_all = (
        pd.concat(annual_parts, ignore_index=True)
        .groupby(["cod_mpio", "year"], as_index=False)
        .sum(numeric_only=True)
        .sort_values(["cod_mpio", "year"])
    )
    monthly_all = (
        pd.concat(monthly_parts, ignore_index=True)
        .groupby(["cod_mpio", "year", "month"], as_index=False)
        .sum(numeric_only=True)
        .sort_values(["cod_mpio", "year", "month"])
    )
    invalid = annual_all[~annual_all["cod_mpio"].isin(valid_codes)].copy()
    annual = annual_all[annual_all["cod_mpio"].isin(valid_codes)].copy()
    monthly = monthly_all[monthly_all["cod_mpio"].isin(valid_codes)].copy()
    write_csv(invalid, "qa_sivigila_invalid_municipality_codes_by_year.csv")
    write_csv(annual, "sivigila_intento_suicidio_by_municipio_year.csv")
    write_csv(monthly, "sivigila_intento_suicidio_by_municipio_month.csv")
    return annual, monthly, invalid


def read_ipm_departamental(dept_catalog: pd.DataFrame) -> pd.DataFrame:
    path = RAW / "dane/anex_PMultidimensional_Departamental_2025.xlsx"
    raw = pd.read_excel(path, sheet_name="IPM_Departamentos", header=None)
    year_row = raw.iloc[11]
    domain_row = raw.iloc[12]
    year_cols: list[tuple[int, int, str]] = []
    current_year = None
    for idx, value in year_row.items():
        if pd.notna(value):
            match = re.search(r"\d{4}", str(value))
            if match:
                current_year = int(match.group(0))
        if idx == 0:
            continue
        domain = domain_row.get(idx)
        if current_year and pd.notna(domain):
            year_cols.append((idx, current_year, str(domain).replace("\n", " ").strip()))

    dept_map = dept_catalog.copy()
    dept_map["dept_key"] = dept_map["departamento"].map(norm_key)
    records = []
    for row_idx in range(13, len(raw)):
        dept = raw.iat[row_idx, 0]
        if pd.isna(dept):
            continue
        dept_text = str(dept).strip()
        if dept_text.lower().startswith(("fuente", "nota", "actualizado")):
            continue
        for col_idx, year, domain in year_cols:
            value = raw.iat[row_idx, col_idx]
            if pd.isna(value):
                continue
            records.append(
                {
                    "departamento": dept_text,
                    "year": year,
                    "ipm_domain": domain,
                    "ipm_pct": float(value),
                    "dept_key": norm_key(dept_text),
                }
            )
    out = pd.DataFrame(records)
    out = out.merge(dept_map[["cod_dpto", "dept_key"]].drop_duplicates(), on="dept_key", how="left")
    out = out.drop(columns=["dept_key"]).sort_values(["cod_dpto", "year", "ipm_domain"])
    write_csv(out, "dane_ipm_departamento_year_domain.csv")
    total = out[out["ipm_domain"].map(norm_key).eq("total")].rename(
        columns={"ipm_pct": "ipm_total_pct"}
    )
    return total[["cod_dpto", "departamento", "year", "ipm_total_pct"]]


def read_saludata() -> pd.DataFrame:
    path = RAW / "saludata_bogota/osb_salud_mental_ideacion_e_intento.csv"
    df = pd.read_csv(path, sep=";", encoding="latin1", dtype=str)
    df.columns = [norm_col(c) for c in df.columns]
    df["year"] = numeric(df["ano_notificacion"]).astype("Int64")
    df["codigo_localidad"] = numeric(df["codigo_localidadresidencia"]).astype("Int64")
    df["conducta_key"] = df["clasificaciondelaconducta"].map(norm_key)
    df["is_intento"] = df["conducta_key"].str.contains("intento", na=False)
    df["is_ideacion"] = df["conducta_key"].str.contains("ideacion", na=False)
    out = df.groupby(["year", "codigo_localidad", "localidad_residencia"], as_index=False).agg(
        saludata_conducta_total=("conducta_key", "size"),
        saludata_intento_suicidio=("is_intento", "sum"),
        saludata_ideacion_suicida=("is_ideacion", "sum"),
    )
    out = out.sort_values(["year", "codigo_localidad"])
    write_csv(out, "bogota_saludata_conducta_suicida_by_locality_year.csv")
    return out


def read_aerocivil() -> pd.DataFrame:
    path = RAW / "aerocivil/trafico_origen_destino_gb6w_ynu4.csv"
    groups: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, dtype=str, chunksize=150_000):
        chunk["year"] = numeric(chunk["a_o"]).astype("Int64")
        chunk["month"] = numeric(chunk["n_mero_de_mes"]).astype("Int64")
        chunk["pasajeros"] = numeric(chunk["pasajeros"]).fillna(0)
        chunk["carga_correo_kg"] = numeric(chunk["carga_correo_kg"]).fillna(0)
        grouped = chunk.groupby(
            ["year", "month", "origen", "ciudad_origen", "destino", "ciudad_destino"],
            as_index=False,
        ).agg(
            pasajeros=("pasajeros", "sum"),
            carga_correo_kg=("carga_correo_kg", "sum"),
            rutas_rows=("origen", "size"),
        )
        groups.append(grouped)
    out = (
        pd.concat(groups, ignore_index=True)
        .groupby(
            ["year", "month", "origen", "ciudad_origen", "destino", "ciudad_destino"],
            as_index=False,
        )
        .sum(numeric_only=True)
        .sort_values(["year", "month", "origen", "destino"])
    )
    write_csv(out, "aerocivil_trafico_origen_destino_by_city_month.csv")
    return out


def build_panels(
    population: pd.DataFrame,
    catalog: pd.DataFrame,
    dept_pop: pd.DataFrame,
    reps: pd.DataFrame,
    capacity: pd.DataFrame,
    rips: pd.DataFrame,
    sivigila_annual: pd.DataFrame,
    sivigila_monthly: pd.DataFrame,
    ipm: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = population.merge(reps, on="cod_mpio", how="left")
    panel = panel.merge(rips, on=["cod_mpio", "year"], how="left")
    panel = panel.merge(sivigila_annual, on=["cod_mpio", "year"], how="left")
    panel = panel.merge(ipm, on=["cod_dpto", "year"], how="left", suffixes=("", "_ipm"))

    cap = capacity.merge(dept_pop, on=["cod_dpto", "year"], how="left")
    cap["capacidad_salud_mental_reps_per_100k_dept"] = (
        cap["capacidad_salud_mental_reps"] / cap["department_population_total"] * 100_000
    )
    latest_cap = (
        capacity.dropna(subset=["cod_dpto"])
        .sort_values(["cod_dpto", "year"])
        .drop_duplicates("cod_dpto", keep="last")[
            ["cod_dpto", "year", "capacidad_salud_mental_reps"]
        ]
        .rename(
            columns={
                "year": "capacity_baseline_source_year",
                "capacidad_salud_mental_reps": "capacidad_salud_mental_reps_baseline",
            }
        )
    )
    panel = panel.merge(
        cap[
            [
                "cod_dpto",
                "year",
                "capacidad_salud_mental_reps",
                "capacidad_salud_mental_reps_per_100k_dept",
            ]
        ],
        on=["cod_dpto", "year"],
        how="left",
    )
    panel = panel.merge(latest_cap, on="cod_dpto", how="left")
    panel = panel.merge(
        dept_pop[["cod_dpto", "year", "department_population_total"]],
        on=["cod_dpto", "year"],
        how="left",
    )
    panel["capacidad_salud_mental_reps_baseline_per_100k_dept"] = (
        panel["capacidad_salud_mental_reps_baseline"]
        / panel["department_population_total"]
        * 100_000
    )
    panel["capacity_access_per_100k_dept_for_proxy"] = panel[
        "capacidad_salud_mental_reps_per_100k_dept"
    ].combine_first(panel["capacidad_salud_mental_reps_baseline_per_100k_dept"])
    panel["reps_source_static_cut_2026"] = True
    for col in [
        "sedes_reps",
        "prestadores_reps",
        "sedes_ips_reps",
        "sedes_publicas_reps",
        "sedes_privadas_reps",
    ]:
        panel[col] = panel[col].fillna(0)
    panel["rips_source_available"] = panel["year"].isin(RIPS_YEARS)
    for col in [
        "rips_f_atenciones",
        "rips_f_rows",
        "rips_f_diagnosticos_distinct",
        "rips_f_tipos_atencion_distinct",
    ]:
        panel.loc[panel["rips_source_available"], col] = panel.loc[
            panel["rips_source_available"], col
        ].fillna(0)
    panel["sivigila_microdata_available"] = panel["year"].isin(SIVIGILA_MICRO_YEARS)
    for col in [
        "sivigila_intento_suicidio",
        "sivigila_intento_suicidio_confirmados",
        "sivigila_intento_suicidio_occurrence_mpio_distinct",
    ]:
        panel.loc[panel["sivigila_microdata_available"], col] = panel.loc[
            panel["sivigila_microdata_available"], col
        ].fillna(0)

    panel["sedes_reps_per_100k"] = rate_per_100k(panel["sedes_reps"], panel["population_total"])
    panel["prestadores_reps_per_100k"] = rate_per_100k(
        panel["prestadores_reps"], panel["population_total"]
    )
    panel["rips_f_atenciones_per_100k"] = rate_per_100k(
        panel["rips_f_atenciones"], panel["population_total"]
    )
    panel["sivigila_intento_confirmados_per_100k"] = rate_per_100k(
        panel["sivigila_intento_suicidio_confirmados"], panel["population_total"]
    )

    proxy_mask = panel["sivigila_microdata_available"]
    panel["z_need_sivigila"] = pd.NA
    panel["z_need_ipm"] = pd.NA
    panel["z_access_reps"] = pd.NA
    panel["z_access_capacity"] = pd.NA
    panel.loc[proxy_mask, "z_need_sivigila"] = zscore_by_year(
        panel.loc[proxy_mask].copy(), "sivigila_intento_confirmados_per_100k"
    )
    panel.loc[proxy_mask, "z_need_ipm"] = zscore_by_year(
        panel.loc[proxy_mask].copy(), "ipm_total_pct"
    )
    panel.loc[proxy_mask, "z_access_reps"] = zscore_by_year(
        panel.loc[proxy_mask].copy(), "sedes_reps_per_100k"
    )
    panel.loc[proxy_mask, "z_access_capacity"] = zscore_by_year(
        panel.loc[proxy_mask].copy(), "capacity_access_per_100k_dept_for_proxy"
    )
    panel["need_proxy_z"] = panel[["z_need_sivigila", "z_need_ipm"]].mean(axis=1, skipna=True)
    panel["access_proxy_z"] = panel[["z_access_reps", "z_access_capacity"]].mean(
        axis=1, skipna=True
    )
    panel["brecha_proxy_z"] = panel["need_proxy_z"] - panel["access_proxy_z"]
    panel["analysis_eligible_population"] = pd.to_numeric(
        panel["population_total"], errors="coerce"
    ) > 0
    noneligible = ~panel["analysis_eligible_population"]
    analysis_cols = [
        "sedes_reps_per_100k",
        "prestadores_reps_per_100k",
        "rips_f_atenciones_per_100k",
        "sivigila_intento_confirmados_per_100k",
        "z_need_sivigila",
        "z_need_ipm",
        "z_access_reps",
        "z_access_capacity",
        "need_proxy_z",
        "access_proxy_z",
        "brecha_proxy_z",
    ]
    panel.loc[noneligible, analysis_cols] = pd.NA

    panel = panel.sort_values(["cod_mpio", "year"])
    write_csv(panel, "municipal_panel_seed_2019_2025.csv")
    write_csv(panel[panel["year"].isin(STUDY_YEARS)], "municipal_panel_seed_2021_2025.csv")

    months = pd.DataFrame(
        [
            {"cod_mpio": row.cod_mpio, "year": year, "month": month}
            for row in catalog.itertuples(index=False)
            for year in STUDY_YEARS
            for month in range(1, 13)
        ]
    )
    monthly = months.merge(catalog, on="cod_mpio", how="left")
    monthly = monthly.merge(
        population[["cod_mpio", "year", "population_total"]], on=["cod_mpio", "year"], how="left"
    )
    monthly = monthly.merge(reps, on="cod_mpio", how="left")
    monthly = monthly.merge(sivigila_monthly, on=["cod_mpio", "year", "month"], how="left")
    monthly["sivigila_microdata_available"] = monthly["year"].isin(SIVIGILA_MICRO_YEARS)
    for col in ["sivigila_intento_suicidio", "sivigila_intento_suicidio_confirmados"]:
        monthly.loc[monthly["sivigila_microdata_available"], col] = monthly.loc[
            monthly["sivigila_microdata_available"], col
        ].fillna(0)
    monthly = monthly.sort_values(["cod_mpio", "year", "month"])
    write_csv(monthly, "municipal_month_seed_2021_2025.csv")
    return panel, monthly


def count_csv_rows(path: Path, sep: str = ",", encoding: str = "utf-8") -> int:
    return sum(len(chunk) for chunk in pd.read_csv(path, sep=sep, encoding=encoding, chunksize=100_000))


def mgn_feature_count(path: Path) -> int:
    return path.read_bytes().count(b'"type": "Feature"')


def build_validation_summary(outputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    raw_specs = [
        ("reps_sedes_c36g_9fc2", RAW / "minsalud_reps/reps_sedes_c36g_9fc2.csv", "csv"),
        ("rips_salud_mental_f_2019_2021", RAW / "minsalud_rips/rips_salud_mental_f_2019_2021_5e6c_5p2c.csv", "csv"),
        ("sivigila_2021_xls", RAW / "ins_sivigila/Datos_2021_356.xls", "excel"),
        ("sivigila_2022_xls", RAW / "ins_sivigila/Datos_2022_356.xls", "excel"),
        ("sivigila_2023_xlsx", RAW / "ins_sivigila/Datos_2023_356.xlsx", "excel"),
        ("sivigila_2024_xlsx", RAW / "ins_sivigila/Datos_2024_356.xlsx", "excel"),
        ("dane_population_area", RAW / "dane/PPED_AreaMun_2018_2042_VP.xlsx", "excel"),
        ("dane_ipm_departamental", RAW / "dane/anex_PMultidimensional_Departamental_2025.xlsx", "excel"),
        ("dane_mgn_municipio_2025", RAW / "dane/MGN2025_municipio_317.geojson", "geojson"),
        ("osm_colombia_latest_pbf", RAW / "osm/colombia-latest.osm.pbf", "pbf"),
        ("saludata_conducta_suicida", RAW / "saludata_bogota/osb_salud_mental_ideacion_e_intento.csv", "csv_semicolon_latin1"),
        ("aerocivil_origen_destino", RAW / "aerocivil/trafico_origen_destino_gb6w_ynu4.csv", "csv"),
    ]
    rows = []
    for source_id, path, kind in raw_specs:
        row = {
            "kind": "raw",
            "id": source_id,
            "path": str(path.relative_to(ROOT)),
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
            "sha256": sha256_file(path) if path.exists() and path.stat().st_size < 150_000_000 else "",
            "rows_or_features": "",
            "notes": "",
        }
        if path.exists():
            if kind == "csv":
                row["rows_or_features"] = count_csv_rows(path)
            elif kind == "csv_semicolon_latin1":
                row["rows_or_features"] = count_csv_rows(path, sep=";", encoding="latin1")
            elif kind == "geojson":
                row["rows_or_features"] = mgn_feature_count(path)
                row["notes"] = "MGN municipality features counted without loading geometry"
            elif kind == "pbf":
                row["notes"] = "OSM/OSRM extract; routing graph not built in this step"
        rows.append(row)

    for name, df in outputs.items():
        path = WORK / name
        rows.append(
            {
                "kind": "derived",
                "id": name,
                "path": str(path.relative_to(ROOT)),
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
                "sha256": sha256_file(path) if path.exists() else "",
                "rows_or_features": len(df),
                "notes": "",
            }
        )
    summary = pd.DataFrame(rows)
    write_csv(summary, "source_validation_summary.csv")
    return summary


def refresh_sources_readme() -> None:
    inventory_path = META / "sources_inventory.csv"
    if not inventory_path.exists():
        return
    inv = pd.read_csv(inventory_path)
    ok = inv[inv["status"].isin(["ok", "skipped_exists"])]
    failed = inv[~inv["status"].isin(["ok", "skipped_exists"])]
    lines = [
        "# Source Download Notes",
        "",
        "Specification: Colombia municipal and monthly source layers for 2021-2025, with REPS, RIPS, SIVIGILA, DANE, MGN, OSM/OSRM and selected support sources.",
        "",
        f"- Sources with local files: {len(ok)}",
        f"- Failed sources: {len(failed)}",
        "- Base directory: `data_raw/`",
        "",
        "## Local Files",
        "",
    ]
    for row in ok.itertuples(index=False):
        layer = "core" if bool(getattr(row, "required_for_minimum")) else "optional/support"
        lines.extend(
            [
                f"### {row.source_id} - {row.title}",
                f"- Role: {layer}",
                f"- Group: `{row.group}`",
                f"- File: `{row.local_path}`",
                f"- URL: {row.url}",
                f"- Bytes: {int(row.bytes)}",
                f"- SHA256: `{row.sha256}`",
                f"- Notes: {getattr(row, 'notes', '') if pd.notna(getattr(row, 'notes', '')) else 'No notes.'}",
                "",
            ]
        )
    if len(failed):
        lines.extend(["## Failed or Blocked Sources", ""])
        for row in failed.itertuples(index=False):
            lines.append(f"- `{row.source_id}`: {row.error} | URL: {row.url}")
    (META / "README_sources.md").write_text("\n".join(lines), encoding="utf-8")


def write_readme(summary: pd.DataFrame, panel: pd.DataFrame, monthly: pd.DataFrame) -> None:
    top_gap = (
        panel[panel["year"].isin(SIVIGILA_MICRO_YEARS)]
        .dropna(subset=["brecha_proxy_z"])
        .sort_values("brecha_proxy_z", ascending=False)
        .head(10)[["year", "cod_mpio", "departamento", "municipio", "brecha_proxy_z"]]
    )
    lines = [
        "# Data Work Notes",
        "",
        "This folder contains the derived aggregate tables used to build the municipal accessibility analysis.",
        "",
        "## Main Outputs",
        "",
        "- `source_validation_summary.csv`: source existence, size, row/entity counts and hashes when available.",
        "- `municipal_panel_seed_2021_2025.csv`: municipality-year panel for the study period.",
        "- `municipal_month_seed_2021_2025.csv`: municipality-month panel for spatial-accessibility processing.",
        "- `reps_sedes_by_municipio.csv`: REPS-enabled sites by municipality.",
        "- `rips_salud_mental_by_municipio_year.csv`: recorded RIPS mental-health service-use records by municipality-year, 2019-2021.",
        "- `sivigila_intento_suicidio_by_municipio_month.csv`: attempted-suicide notifications by municipality-month, 2021-2024.",
        "- `dane_population_municipality_year_area.csv`: DANE population by municipality, area and year.",
        "- `dane_ipm_departamento_year_domain.csv`: departmental multidimensional poverty indicators, 2018-2025.",
        "- `qa_*_invalid_municipality_codes*.csv`: source codes that do not match the municipal catalog used for the panel.",
        "",
        "## Effective Coverage",
        "",
        f"- Municipality-year panel, 2021-2025: {len(panel[panel['year'].isin(STUDY_YEARS)]):,} rows.",
        f"- Municipality-month panel, 2021-2025: {len(monthly):,} rows.",
        "- Direct SIVIGILA microdata available locally: 2021-2024. The tested direct endpoint did not provide `Datos_2025_356`.",
        "- Open national RIPS data available locally: 2019-2021.",
        "- REPS installed-capacity data downloaded: 2017-2020. For 2021-2025, the 2020 departmental baseline is retained in `*_baseline` columns and is not treated as a contemporaneous observation.",
        "- REPS site records used here do not provide a complete national geocoded mental-health provider layer.",
        "- The OSM PBF was downloaded, but the OSRM extraction was not completed because local disk space was insufficient.",
        "",
        "## Integration Check",
        "",
        "`brecha_proxy_z = z(necesidad) - z(acceso)` is retained as an integration check. Need combines confirmed SIVIGILA notification rates and departmental multidimensional poverty; the access component combines REPS sites per 100,000 inhabitants and the latest available REPS departmental mental-health capacity baseline when annual data are unavailable. This check does not replace the Hansen or E2SFCA potential-accessibility measures.",
        "",
        "Highest municipality-year rows by `brecha_proxy_z`:",
        "",
        top_gap.to_markdown(index=False),
        "",
        "## Technical Priorities",
        "",
        "1. Replace the centroid travel-time proxy with a routed travel-time matrix when the OSRM extraction can be completed.",
        "2. Obtain or build a complete national geocoded mental-health service layer if available.",
        "3. Recompute Hansen and E2SFCA accessibility with routed times and service-specific supply.",
        "",
    ]
    (WORK / "README_data_work.md").write_text("\n".join(lines), encoding="utf-8")


def remove_partial_downloads() -> None:
    for path in RAW.rglob("*.part"):
        if path.name == "trafico_origen_destino_gb6w_ynu4.csv.part":
            path.unlink()


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    refresh_sources_readme()
    remove_partial_downloads()

    population, catalog, dept_pop = read_population()
    valid_codes = set(catalog["cod_mpio"])
    dept_catalog = catalog[["cod_dpto", "departamento"]].drop_duplicates()
    reps, reps_invalid = read_reps_sedes(valid_codes)
    capacity = read_reps_capacity(dept_catalog)
    rips, rips_invalid = read_rips(valid_codes)
    sivigila_annual, sivigila_monthly, sivigila_invalid = read_sivigila(valid_codes)
    ipm = read_ipm_departamental(dept_catalog)
    saludata = read_saludata()
    aerocivil = read_aerocivil()
    panel, monthly = build_panels(
        population,
        catalog,
        dept_pop,
        reps,
        capacity,
        rips,
        sivigila_annual,
        sivigila_monthly,
        ipm,
    )

    outputs = {
        "dane_population_municipality_year_area.csv": population,
        "reps_sedes_by_municipio.csv": reps,
        "qa_reps_invalid_municipality_codes.csv": reps_invalid,
        "reps_capacidad_departamento_year.csv": capacity,
        "rips_salud_mental_by_municipio_year.csv": rips,
        "qa_rips_invalid_municipality_codes.csv": rips_invalid,
        "sivigila_intento_suicidio_by_municipio_year.csv": sivigila_annual,
        "sivigila_intento_suicidio_by_municipio_month.csv": sivigila_monthly,
        "qa_sivigila_invalid_municipality_codes_by_year.csv": sivigila_invalid,
        "dane_ipm_departamento_year_domain.csv": pd.read_csv(
            WORK / "dane_ipm_departamento_year_domain.csv"
        ),
        "bogota_saludata_conducta_suicida_by_locality_year.csv": saludata,
        "aerocivil_trafico_origen_destino_by_city_month.csv": aerocivil,
        "municipal_panel_seed_2019_2025.csv": panel,
        "municipal_panel_seed_2021_2025.csv": panel[panel["year"].isin(STUDY_YEARS)],
        "municipal_month_seed_2021_2025.csv": monthly,
    }
    summary = build_validation_summary(outputs)
    write_readme(summary, panel, monthly)
    print(f"Wrote {len(outputs)} derived tables to {WORK}")
    print(summary[["kind", "id", "rows_or_features"]].to_string(index=False))


if __name__ == "__main__":
    main()
