#!/usr/bin/env python3
"""Download public data sources for the Colombia accessibility analysis.

The source list includes REPS, RIPS, SIVIGILA, DANE population and poverty
files, DANE/MGN geography, OSM/OSRM support files, Bogota SaluData, and
Aerocivil connectivity layers.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data_raw"
META_DIR = RAW_DIR / "_metadata"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 Chrome/123 Safari/537.36",
    "Accept": "*/*",
}


@dataclass
class Source:
    source_id: str
    group: str
    title: str
    url: str
    local_path: str
    required_for_minimum: bool
    method: str = "direct"
    notes: str = ""


def socrata_url(resource_id: str, params: dict[str, str | int] | None = None, fmt: str = "csv") -> str:
    query = urllib.parse.urlencode(params or {})
    return f"https://www.datos.gov.co/resource/{resource_id}.{fmt}?{query}"


def ensure_dirs() -> None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    for group in [
        "minsalud_reps",
        "minsalud_rips",
        "ins_sivigila",
        "dane",
        "saludata_bogota",
        "aerocivil",
        "osm",
    ]:
        (RAW_DIR / group).mkdir(parents=True, exist_ok=True)


def stream_download(url: str, dest: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    sha = hashlib.sha256()
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as response, tmp.open("wb") as f:
        final_url = response.geturl()
        content_type = response.headers.get("content-type", "")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            sha.update(chunk)
    tmp.replace(dest)
    return {
        "final_url": final_url,
        "content_type": content_type,
        "bytes": dest.stat().st_size,
        "sha256": sha.hexdigest(),
    }


def arcgis_municipios_geojson(url: str, dest: Path) -> dict:
    """ArcGIS FeatureServer sometimes fails on HEAD but works on query GET."""
    return stream_download(url, dest)


def download_sources(sources: list[Source]) -> list[dict]:
    log: list[dict] = []
    for source in sources:
        dest = RAW_DIR / source.local_path
        row = asdict(source)
        row["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        try:
            if dest.exists() and dest.stat().st_size > 0:
                data = dest.read_bytes()
                row.update(
                    status="skipped_exists",
                    final_url=source.url,
                    content_type="",
                    bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    error="",
                )
            else:
                downloader: Callable[[str, Path], dict] = stream_download
                if source.method == "arcgis_geojson":
                    downloader = arcgis_municipios_geojson
                result = downloader(source.url, dest)
                row.update(status="ok", error="", **result)
            print(f"{row['status']:>14}  {source.source_id}  {row.get('bytes', '')}")
        except Exception as exc:
            row.update(
                status="failed",
                final_url="",
                content_type="",
                bytes="",
                sha256="",
                error=str(exc),
            )
            print(f"{'failed':>14}  {source.source_id}  {exc}", file=sys.stderr)
        row["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        log.append(row)
        time.sleep(0.2)
    return log


def write_manifest(sources: list[Source], log: list[dict]) -> None:
    fields = [
        "source_id",
        "group",
        "title",
        "required_for_minimum",
        "method",
        "url",
        "local_path",
        "status",
        "bytes",
        "sha256",
        "content_type",
        "final_url",
        "notes",
        "error",
        "started_at",
        "finished_at",
    ]
    with (META_DIR / "sources_inventory.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in log:
            writer.writerow({key: row.get(key, "") for key in fields})
    (META_DIR / "download_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    ok = [row for row in log if row["status"] in {"ok", "skipped_exists"}]
    failed = [row for row in log if row["status"] == "failed"]
    lines = [
        "# Source Download Notes",
        "",
        "Specification: monthly municipal panel for Colombia, 2021-2025, with local support sources when available.",
        "",
        f"- Sources with local files: {len(ok)}",
        f"- Failed sources: {len(failed)}",
        "- Base directory: `data_raw/`",
        "",
        "## Local Files",
        "",
    ]
    for row in ok:
        required = "core" if row["required_for_minimum"] else "optional/support"
        lines.extend(
            [
                f"### {row['source_id']} - {row['title']}",
                f"- Role: {required}",
                f"- Group: `{row['group']}`",
                f"- File: `{row['local_path']}`",
                f"- URL: {row['url']}",
                f"- Bytes: {row['bytes']}",
                f"- SHA256: `{row['sha256']}`",
                f"- Notes: {row.get('notes', '') or 'No notes.'}",
                "",
            ]
        )
    if failed:
        lines.extend(["## Failed or Blocked Sources", ""])
        for row in failed:
            lines.append(f"- `{row['source_id']}`: {row['error']} | URL: {row['url']}")
    (META_DIR / "README_sources.md").write_text("\n".join(lines), encoding="utf-8")


def build_sources() -> list[Source]:
    dane_base = "https://www.dane.gov.co"
    mgn_query = (
        "https://geoportal.dane.gov.co/mparcgis/rest/services/"
        "MGN2025/Serv_CapasMGN_2025/FeatureServer/317/query?"
        + urllib.parse.urlencode(
            {
                "where": "1=1",
                "outFields": "*",
                "outSR": "4326",
                "returnGeometry": "true",
                "f": "geojson",
                "resultRecordCount": "2000",
            }
        )
    )
    return [
        Source(
            "reps_sedes_c36g_9fc2",
            "minsalud_reps",
            "Registro Especial de Prestadores y Sedes de Servicios de Salud",
            socrata_url("c36g-9fc2", {"$limit": 100000}),
            "minsalud_reps/reps_sedes_c36g_9fc2.csv",
            True,
            notes="No contiene coordenadas; se usa como padrón nacional de sedes/prestadores.",
        ),
        Source(
            "reps_prestadores_kjjp_kasm",
            "minsalud_reps",
            "Número de prestadores por departamento, clase, año y naturaleza jurídica",
            socrata_url("kjjp-kasm", {"$limit": 5000}),
            "minsalud_reps/reps_prestadores_departamento_clase_naturaleza_kjjp_kasm.csv",
            True,
            notes="Agregado oficial complementario para oferta territorial.",
        ),
        Source(
            "reps_capacidad_instalada_minsalud",
            "minsalud_reps",
            "Servicios y capacidad instalada de IPS por departamento/distrito y naturaleza jurídica",
            "https://www.minsalud.gov.co/sites/rid/Lists/BibliotecaDigital/RIDE/VS/PSA/reporte-consolidado-departamento-naturaleza-ano-capacidad.zip",
            "minsalud_reps/reporte_consolidado_departamento_naturaleza_ano_capacidad.zip",
            True,
            notes="ZIP enlazado desde SISPRO/Minsalud.",
        ),
        Source(
            "rips_salud_mental_f_2019_2021",
            "minsalud_rips",
            "RIPS 2019-2021 filtrado a diagnósticos CIE-10 F*",
            socrata_url("5e6c-5p2c", {"$limit": 600000, "$where": "diagnostico like 'F%'"}),
            "minsalud_rips/rips_salud_mental_f_2019_2021_5e6c_5p2c.csv",
            True,
            notes="Dataset agregado en datos.gov.co; cubre 2019-2021, no 2022-2025.",
        ),
        *[
            Source(
                f"sivigila_intento_suicidio_{year}",
                "ins_sivigila",
                f"SIVIGILA microdato intento de suicidio evento 356, {year}",
                f"https://portalsivigila.ins.gov.co/Microdatos/Datos_{year}_356.{ext}",
                f"ins_sivigila/Datos_{year}_356.{ext}",
                True,
                notes="Descarga directa encontrada en el buscador oficial del INS/SIVIGILA.",
            )
            for year, ext in [
                (2021, "xls"),
                (2022, "xls"),
                (2023, "xlsx"),
                (2024, "xlsx"),
            ]
        ],
        Source(
            "dane_poblacion_municipal_area_2018_2042",
            "dane",
            "DANE proyecciones municipales por área 2018-2042",
            dane_base + "/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaMun-2018-2042_VP.xlsx",
            "dane/PPED_AreaMun_2018_2042_VP.xlsx",
            True,
        ),
        Source(
            "dane_poblacion_municipal_area_sexo_edad_2018_2042",
            "dane",
            "DANE proyecciones municipales por área, sexo y edad 2018-2042",
            dane_base + "/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaSexoEdadMun-2018-2042_VP.xlsx",
            "dane/PPED_AreaSexoEdadMun_2018_2042_VP.xlsx",
            True,
        ),
        Source(
            "dane_ipm_nacional_2025",
            "dane",
            "DANE pobreza multidimensional anexo nacional 2025",
            dane_base + "/files/operaciones/PM/anex-PMultidimensional-2025.xlsx",
            "dane/anex_PMultidimensional_2025.xlsx",
            True,
        ),
        Source(
            "dane_ipm_departamental_2025",
            "dane",
            "DANE pobreza multidimensional anexo departamental 2025",
            dane_base + "/files/operaciones/PM/anex-PMultidimensional-Departamental-2025.xlsx",
            "dane/anex_PMultidimensional_Departamental_2025.xlsx",
            True,
        ),
        Source(
            "dane_mgn_municipio_2025_geojson",
            "dane",
            "DANE MGN 2025 capa municipio, GeoJSON desde FeatureServer",
            mgn_query,
            "dane/MGN2025_municipio_317.geojson",
            True,
            method="arcgis_geojson",
            notes="Capa Municipio (317) del servicio oficial MGN2025; evita descargar el ZIP completo de 1.5 GB.",
        ),
        Source(
            "saludata_conducta_suicida_bogota",
            "saludata_bogota",
            "SaluData Bogotá conducta suicida",
            "https://datosabiertos.bogota.gov.co/dataset/2b8464e3-3aca-4dcd-91a1-93dd06ddabbb/resource/555a3bea-e358-4e77-be49-7b448774324b/download/osb_salud_mental_ideacion_e_intento.csv",
            "saludata_bogota/osb_salud_mental_ideacion_e_intento.csv",
            False,
            notes="Capa para piloto Bogotá localidad/UPZ.",
        ),
        Source(
            "saludata_morbilidad_salud_mental_ficha",
            "saludata_bogota",
            "Ficha técnica SaluData morbilidad atendida salud mental",
            "https://saludata.saludcapital.gov.co/osb/wp-content/uploads/2024/09/2023_12_14_Ficha_Tec_Morbilidad_atendida_Salud-Mental_Tablero-v1-1.pdf",
            "saludata_bogota/ficha_tecnica_morbilidad_atendida_salud_mental.pdf",
            False,
            notes="Documenta variables del tablero de morbilidad atendida.",
        ),
        Source(
            "aerocivil_trafico_origen_destino_gb6w_ynu4",
            "aerocivil",
            "Transporte aéreo comercial tráfico origen-destino Colombia",
            socrata_url("gb6w-ynu4", {"$limit": 500000}),
            "aerocivil/trafico_origen_destino_gb6w_ynu4.csv",
            False,
            notes="Capa opcional para conectividad aérea en territorios remotos.",
        ),
        Source(
            "aerocivil_operaciones_jh8x_n6h6",
            "aerocivil",
            "Operaciones aéreas acumuladas en Colombia",
            socrata_url("jh8x-n6h6", {"$limit": 600000}),
            "aerocivil/operaciones_aereas_jh8x_n6h6.csv",
            False,
            notes="Capa opcional para sensibilidad de conectividad aérea.",
        ),
        Source(
            "osm_colombia_latest_pbf",
            "osm",
            "OpenStreetMap Colombia extract Geofabrik latest",
            "https://download.geofabrik.de/south-america/colombia-latest.osm.pbf",
            "osm/colombia-latest.osm.pbf",
            True,
            notes="Base para tiempos de viaje OSRM/OSMnx. Tamaño aproximado el 2026-05-29: 315 MB.",
        ),
        Source(
            "osm_colombia_poly",
            "osm",
            "OpenStreetMap Colombia polygon Geofabrik",
            "https://download.geofabrik.de/south-america/colombia.poly",
            "osm/colombia.poly",
            False,
            notes="Límite auxiliar del extracto Geofabrik.",
        ),
    ]


def main() -> None:
    ensure_dirs()
    sources = build_sources()
    log = download_sources(sources)
    write_manifest(sources, log)


if __name__ == "__main__":
    main()
