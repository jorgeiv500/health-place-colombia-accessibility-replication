# Source Download Notes

Specification: Colombia municipal and monthly source layers for 2021-2025, with REPS, RIPS, SIVIGILA, DANE, MGN, OSM/OSRM and selected support sources.

- Sources with local files: 19
- Failed sources: 0
- Base directory: `data_raw/`

## Local Files

### reps_sedes_c36g_9fc2 - Registro Especial de Prestadores y Sedes de Servicios de Salud
- Role: core
- Group: `minsalud_reps`
- File: `minsalud_reps/reps_sedes_c36g_9fc2.csv`
- URL: https://www.datos.gov.co/resource/c36g-9fc2.csv?%24limit=100000
- Bytes: 32191578
- SHA256: `249668c179092d6b15590f84cc00f3d41851749d67929e892e26f4603739af52`
- Notes: No contiene coordenadas; se usa como padrón nacional de sedes/prestadores.

### reps_prestadores_kjjp_kasm - Número de prestadores por departamento, clase, año y naturaleza jurídica
- Role: core
- Group: `minsalud_reps`
- File: `minsalud_reps/reps_prestadores_departamento_clase_naturaleza_kjjp_kasm.csv`
- URL: https://www.datos.gov.co/resource/kjjp-kasm.csv?%24limit=5000
- Bytes: 84069
- SHA256: `2491aecf6c7cdbea398aa613e16040d4d4a14f6cd8e3b2ef4692b0abba88df2f`
- Notes: Agregado oficial complementario para oferta territorial.

### reps_capacidad_instalada_minsalud - Servicios y capacidad instalada de IPS por departamento/distrito y naturaleza jurídica
- Role: core
- Group: `minsalud_reps`
- File: `minsalud_reps/reporte_consolidado_departamento_naturaleza_ano_capacidad.zip`
- URL: https://www.minsalud.gov.co/sites/rid/Lists/BibliotecaDigital/RIDE/VS/PSA/reporte-consolidado-departamento-naturaleza-ano-capacidad.zip
- Bytes: 44763
- SHA256: `550d12766d047ea85344a73e5c18e8b6faba94117d704c008db077158f912a11`
- Notes: ZIP enlazado desde SISPRO/Minsalud.

### rips_salud_mental_f_2019_2021 - RIPS 2019-2021 filtrado a diagnósticos CIE-10 F*
- Role: core
- Group: `minsalud_rips`
- File: `minsalud_rips/rips_salud_mental_f_2019_2021_5e6c_5p2c.csv`
- URL: https://www.datos.gov.co/resource/5e6c-5p2c.csv?%24limit=600000&%24where=diagnostico+like+%27F%25%27
- Bytes: 68576998
- SHA256: `fa9a0cf48e20b226f4d978e60bdba8adc4b7f421a019b6c321014e8506b147a7`
- Notes: Dataset agregado en datos.gov.co; cubre 2019-2021, no 2022-2025.

### sivigila_intento_suicidio_2021 - SIVIGILA microdato intento de suicidio evento 356, 2021
- Role: core
- Group: `ins_sivigila`
- File: `ins_sivigila/Datos_2021_356.xls`
- URL: https://portalsivigila.ins.gov.co/Microdatos/Datos_2021_356.xls
- Bytes: 32646144
- SHA256: `d9f6f5130fbbc8331c4bb83b8474c055f73e82be6228fc26d1eea88f4870427c`
- Notes: Descarga directa encontrada en el buscador oficial del INS/SIVIGILA.

### sivigila_intento_suicidio_2022 - SIVIGILA microdato intento de suicidio evento 356, 2022
- Role: core
- Group: `ins_sivigila`
- File: `ins_sivigila/Datos_2022_356.xls`
- URL: https://portalsivigila.ins.gov.co/Microdatos/Datos_2022_356.xls
- Bytes: 40869888
- SHA256: `98cd17a913f578a7e2ad9ab6059fc07d5e53d2f1d3da05d03be783ef3dd2d632`
- Notes: Descarga directa encontrada en el buscador oficial del INS/SIVIGILA.

### sivigila_intento_suicidio_2023 - SIVIGILA microdato intento de suicidio evento 356, 2023
- Role: core
- Group: `ins_sivigila`
- File: `ins_sivigila/Datos_2023_356.xlsx`
- URL: https://portalsivigila.ins.gov.co/Microdatos/Datos_2023_356.xlsx
- Bytes: 13957727
- SHA256: `8f20d9397d756e0143653c4138f535be2f52b233cabba242948f729832caee6e`
- Notes: Descarga directa encontrada en el buscador oficial del INS/SIVIGILA.

### sivigila_intento_suicidio_2024 - SIVIGILA microdato intento de suicidio evento 356, 2024
- Role: core
- Group: `ins_sivigila`
- File: `ins_sivigila/Datos_2024_356.xlsx`
- URL: https://portalsivigila.ins.gov.co/Microdatos/Datos_2024_356.xlsx
- Bytes: 12921920
- SHA256: `8f2567475da33f573c6652c561ad3fa4fdcb24ffaad015d8fe808f3d3918d198`
- Notes: Descarga directa encontrada en el buscador oficial del INS/SIVIGILA.

### dane_poblacion_municipal_area_2018_2042 - DANE proyecciones municipales por área 2018-2042
- Role: core
- Group: `dane`
- File: `dane/PPED_AreaMun_2018_2042_VP.xlsx`
- URL: https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaMun-2018-2042_VP.xlsx
- Bytes: 3948350
- SHA256: `1ea83594ad308becff39934a3977c102919c25740f60439be95d797396d11283`
- Notes: No notes.

### dane_poblacion_municipal_area_sexo_edad_2018_2042 - DANE proyecciones municipales por área, sexo y edad 2018-2042
- Role: core
- Group: `dane`
- File: `dane/PPED_AreaSexoEdadMun_2018_2042_VP.xlsx`
- URL: https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaSexoEdadMun-2018-2042_VP.xlsx
- Bytes: 131609579
- SHA256: `7e461635315664d44ba52cc7f951947085a0ea6f2dda72fe2efed11a76880516`
- Notes: No notes.

### dane_ipm_nacional_2025 - DANE pobreza multidimensional anexo nacional 2025
- Role: core
- Group: `dane`
- File: `dane/anex_PMultidimensional_2025.xlsx`
- URL: https://www.dane.gov.co/files/operaciones/PM/anex-PMultidimensional-2025.xlsx
- Bytes: 449869
- SHA256: `ae59a747adab22bb06fdd724262c0bcded0a9b256d477a1f0c366fbab00d09c0`
- Notes: No notes.

### dane_ipm_departamental_2025 - DANE pobreza multidimensional anexo departamental 2025
- Role: core
- Group: `dane`
- File: `dane/anex_PMultidimensional_Departamental_2025.xlsx`
- URL: https://www.dane.gov.co/files/operaciones/PM/anex-PMultidimensional-Departamental-2025.xlsx
- Bytes: 482244
- SHA256: `73caab08046d6b35f80326b1b6f2e9b1cb8ad75a2ac4946515fda320ffaaf447`
- Notes: No notes.

### dane_mgn_municipio_2025_geojson - DANE MGN 2025 capa municipio, GeoJSON desde FeatureServer
- Role: core
- Group: `dane`
- File: `dane/MGN2025_municipio_317.geojson`
- URL: https://geoportal.dane.gov.co/mparcgis/rest/services/MGN2025/Serv_CapasMGN_2025/FeatureServer/317/query?where=1%3D1&outFields=%2A&outSR=4326&returnGeometry=true&f=geojson&resultRecordCount=2000
- Bytes: 256093934
- SHA256: `3f262f024000fb8a4d9f091aca29136f4beb14beb9cf9d980c4e882926caa558`
- Notes: Capa Municipio (317) del servicio oficial MGN2025; evita descargar el ZIP completo de 1.5 GB.

### saludata_conducta_suicida_bogota - SaluData Bogotá conducta suicida
- Role: optional/support
- Group: `saludata_bogota`
- File: `saludata_bogota/osb_salud_mental_ideacion_e_intento.csv`
- URL: https://datosabiertos.bogota.gov.co/dataset/2b8464e3-3aca-4dcd-91a1-93dd06ddabbb/resource/555a3bea-e358-4e77-be49-7b448774324b/download/osb_salud_mental_ideacion_e_intento.csv
- Bytes: 31841499
- SHA256: `98a11c890db3bcd078faf08d4f7dd341d2f1c02b4d2b869309607405d562ac27`
- Notes: Capa para piloto Bogotá localidad/UPZ.

### saludata_morbilidad_salud_mental_ficha - Ficha técnica SaluData morbilidad atendida salud mental
- Role: optional/support
- Group: `saludata_bogota`
- File: `saludata_bogota/ficha_tecnica_morbilidad_atendida_salud_mental.pdf`
- URL: https://saludata.saludcapital.gov.co/osb/wp-content/uploads/2024/09/2023_12_14_Ficha_Tec_Morbilidad_atendida_Salud-Mental_Tablero-v1-1.pdf
- Bytes: 278020
- SHA256: `42d62efcb3c360e9661fa74e8818355916bc156ffc3cffbccefc528b503970d2`
- Notes: Documenta variables del tablero de morbilidad atendida.

### aerocivil_trafico_origen_destino_gb6w_ynu4 - Transporte aéreo comercial tráfico origen-destino Colombia
- Role: optional/support
- Group: `aerocivil`
- File: `aerocivil/trafico_origen_destino_gb6w_ynu4.csv`
- URL: https://www.datos.gov.co/resource/gb6w-ynu4.csv?%24limit=500000
- Bytes: 72696425
- SHA256: `24f96ac935e52810c19e058105218de247f8f872cb259e4f79c81046573b7560`
- Notes: Capa opcional para conectividad aérea en territorios remotos.

### aerocivil_operaciones_jh8x_n6h6 - Operaciones aéreas acumuladas en Colombia
- Role: optional/support
- Group: `aerocivil`
- File: `aerocivil/operaciones_aereas_jh8x_n6h6.csv`
- URL: https://www.datos.gov.co/resource/jh8x-n6h6.csv?%24limit=600000
- Bytes: 37688594
- SHA256: `485142ec650514456ee212e730d23153c40afd72d06ea902993383181216ba7b`
- Notes: Capa opcional para sensibilidad de conectividad aérea.

### osm_colombia_latest_pbf - OpenStreetMap Colombia extract Geofabrik latest
- Role: core
- Group: `osm`
- File: `osm/colombia-latest.osm.pbf`
- URL: https://download.geofabrik.de/south-america/colombia-latest.osm.pbf
- Bytes: 315272834
- SHA256: `a3c9595c2bf79f918106d6245b5699749925f358c2972a56008467252339b4a3`
- Notes: Base para tiempos de viaje OSRM/OSMnx. Tamaño aproximado el 2026-05-29: 315 MB.

### osm_colombia_poly - OpenStreetMap Colombia polygon Geofabrik
- Role: optional/support
- Group: `osm`
- File: `osm/colombia.poly`
- URL: https://download.geofabrik.de/south-america/colombia.poly
- Bytes: 7115
- SHA256: `9e6a3cff560d39efc59fb07f4f8b71a8ea95a73638b2b5ca743fe88cfa8cfebf`
- Notes: Límite auxiliar del extracto Geofabrik.
