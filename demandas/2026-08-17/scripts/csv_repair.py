import csv
import re
import pandas as pd
import duckdb
from pathlib import Path
from collections import defaultdict

def extrair_data_da_linha(colunas):
    if len(colunas) > 8:
        campo_data = colunas[8]
        match = re.search(r'\d{4}-\d{2}-\d{2}', campo_data)
        if match:
            return match.group(0)
    return "data_desconhecida"


def dividir_arquivos_individuais_por_data(pasta_corrigidos, pasta_saida, tem_cabecalho=False):
    caminho_in = Path(pasta_corrigidos)
    caminho_out = Path(pasta_saida)
    caminho_out.mkdir(parents=True, exist_ok=True)

    arquivos_csv = list(caminho_in.glob("*.csv"))
    if not arquivos_csv:
        print(f"Nenhum arquivo CSV encontrado em '{pasta_corrigidos}'.")
        return

    print(f"Processando {len(arquivos_csv)} arquivo(s) individualmente...\n")

    for arquivo in arquivos_csv:
        dados_por_data = defaultdict(list)
        cabecalho = None

        with open(arquivo, 'r', encoding='utf-8') as f:
            leitor = csv.reader(f)

            for idx, linha in enumerate(leitor):
                if not linha:
                    continue

                if tem_cabecalho and idx == 0:
                    cabecalho = linha
                    continue

                data_encontrada = extrair_data_da_linha(linha)
                dados_por_data[data_encontrada].append(linha)

        nome_base = arquivo.stem

        for data, linhas in dados_por_data.items():
            nome_novo_arquivo = f"{nome_base}_{data}.csv"
            caminho_novo = caminho_out / nome_novo_arquivo

            with open(caminho_novo, 'w', encoding='utf-8', newline='') as f_out:
                escritor = csv.writer(f_out)

                if tem_cabecalho and cabecalho:
                    escritor.writerow(cabecalho)

                escritor.writerows(linhas)

            print(f"✔ Gerado: {nome_novo_arquivo} ({len(linhas)} linhas)")


def proteger_arrays(linha):

    def envolver(match):
        conteudo = match.group(0)
        conteudo_escapado = conteudo.replace('"', '""')
        return f'"{conteudo_escapado}"'

    return re.sub(r'\[.*?\]', envolver, linha)


def processar_pasta_csv(pasta_entrada, pasta_saida):
    caminho_in = Path(pasta_entrada)
    caminho_out = Path(pasta_saida)

    caminho_out.mkdir(parents=True, exist_ok=True)

    arquivos_csv = list(caminho_in.glob("*.csv"))

    if not arquivos_csv:
        print(f"Nenhum arquivo .csv_originais encontrado na pasta '{pasta_entrada}'.")
        return

    print(f"Localizados {len(arquivos_csv)} arquivo(s). Iniciando processamento...\n")

    for arquivo in arquivos_csv:
        arquivo_saida = caminho_out / f"corrigido_{arquivo.name}"

        with open(arquivo, 'r', encoding='utf-8') as f_in, \
                open(arquivo_saida, 'w', encoding='utf-8', newline='') as f_out:

            for linha in f_in:
                linha_limpa = linha.strip()
                if linha_limpa:
                    f_out.write(proteger_arrays(linha_limpa) + '\n')

        print(f"✔ Concluído: {arquivo.name} -> {arquivo_saida.name}")


def pivotar_frequencias(caminho_entrada, caminho_saida):
    df = pd.read_csv(caminho_entrada)

    colunas_frequencia = ['trait', 'value', 'label']
    colunas_identificadoras = [c for c in df.columns if c not in colunas_frequencia]

    df['pair'] = list(zip(df['value'], df['label']))

    df_grouped = df.groupby(colunas_identificadoras + ['trait'])['pair'].apply(list)

    df_pivoted = df_grouped.unstack('trait').reset_index()

    df_pivoted.columns.name = None

    df_pivoted.to_csv(caminho_saida, index=False)
    print(f"✔ Arquivo processado mantendo {len(colunas_identificadoras)} colunas identificadoras.")


def contar_linhas_pandas(caminho_csv, chunksize=500_000):
    total_linhas = 0

    for chunk in pd.read_csv(caminho_csv, chunksize=chunksize, usecols=[0]):
        total_linhas += len(chunk)

    print(f"Total de linhas (sem contar cabeçalho): {total_linhas:,}")
    return total_linhas


def ordenar_colunas_csv(caminho_entrada, caminho_saida):
    df = pd.read_csv(caminho_entrada)

    ordem_desejada = ['camera',
     'imgtype',
     'zoom',
     'exposure',
     'gain',
     'frame',
     'rotation',
     'lifter',
     'timestamp',
     'id',
     'barcode',
     'treatment',
     'velocity',
     'cartag',
     'measurementlabel',
     'other',
     'image',
     'sample',
     'blue_frequencies',
     'green_frequencies',
     'red_frequencies',
     'lightness_frequencies',
     'green-magenta_frequencies',
     'blue-yellow_frequencies',
     'hue_frequencies',
     'saturation_frequencies',
     'value_frequencies',
     'nir_frequencies']

    df = df[ordem_desejada]

    df.to_csv(caminho_saida, index=False)


def ordenar_linhas_csv(pasta_entrada, pasta_saida):
    caminho_in = Path(pasta_entrada)
    caminho_out = Path(pasta_saida)
    caminho_out.mkdir(parents=True, exist_ok=True)

    for arquivo in caminho_in.glob("*.csv"):
        query = f"""
            SELECT * 
            FROM read_csv_auto('{arquivo}')
            ORDER BY barcode ASC, timestamp ASC
            """

        duckdb.sql(f"COPY ({query}) TO '{caminho_out / f"ordenado_{arquivo.name}"}' (HEADER, DELIMITER ',');")
        print(f"✔ Ordenação de {arquivo} concluída via DuckDB!")


def agrupando_linhas_csv(pasta_entrada, pasta_saida):
    caminho_in = Path(pasta_entrada)
    caminho_out = Path(pasta_saida)
    caminho_out.mkdir(parents=True, exist_ok=True)

    for arquivo in caminho_in.glob("ordenado_corrigido_*.csv"):
        query = f"""
        SELECT 
            camera, imgtype, zoom, exposure, gain, frame, rotation, lifter,
            timestamp, id, barcode, treatment, velocity, cartag, measurementlabel,
            other, image,
            FIRST(color_chip_size) FILTER (WHERE color_chip_size != 'NA') AS color_chip_size,
            FIRST(median_color_chip_height) FILTER (WHERE median_color_chip_height != 'NA') AS median_color_chip_height,
            FIRST(median_color_chip_width) FILTER (WHERE median_color_chip_width != 'NA') AS median_color_chip_width,
            FIRST(in_bounds) FILTER (WHERE in_bounds != 'NA') AS in_bounds,
            FIRST(area) FILTER (WHERE area != 'NA') AS area,
            FIRST(convex_hull_area) FILTER (WHERE convex_hull_area != 'NA') AS convex_hull_area,
            FIRST(solidity) FILTER (WHERE solidity != 'NA') AS solidity,
            FIRST(perimeter) FILTER (WHERE perimeter != 'NA') AS perimeter,
            FIRST(width) FILTER (WHERE width != 'NA') AS width,
            FIRST(height) FILTER (WHERE height != 'NA') AS height,
            FIRST(longest_path) FILTER (WHERE longest_path != 'NA') AS longest_path,
            FIRST(convex_hull_vertices) FILTER (WHERE convex_hull_vertices != 'NA') AS convex_hull_vertices,
            FIRST(object_in_frame) FILTER (WHERE object_in_frame != 'NA') AS object_in_frame,
            FIRST(ellipse_major_axis) FILTER (WHERE ellipse_major_axis != 'NA') AS ellipse_major_axis,
            FIRST(ellipse_minor_axis) FILTER (WHERE ellipse_minor_axis != 'NA') AS ellipse_minor_axis,
            FIRST(ellipse_angle) FILTER (WHERE ellipse_angle != 'NA') AS ellipse_angle,
            FIRST(ellipse_eccentricity) FILTER (WHERE ellipse_eccentricity != 'NA') AS ellipse_eccentricity,            
            FIRST(horizontal_reference_position) FILTER (WHERE horizontal_reference_position != 'NA') AS horizontal_reference_position,
            FIRST(height_above_reference) FILTER (WHERE height_above_reference != 'NA') AS height_above_reference,
            FIRST(height_below_reference) FILTER (WHERE height_below_reference != 'NA') AS height_below_reference,
            FIRST(area_above_reference) FILTER (WHERE area_above_reference != 'NA') AS area_above_reference,
            FIRST(percent_area_above_reference) FILTER (WHERE percent_area_above_reference != 'NA') AS percent_area_above_reference,
            FIRST(area_below_reference) FILTER (WHERE area_below_reference != 'NA') AS area_below_reference,
            FIRST(percent_area_below_reference) FILTER (WHERE percent_area_below_reference != 'NA') AS percent_area_below_reference,
            FIRST(hue_circular_mean) FILTER (WHERE hue_circular_mean != 'NA') AS hue_circular_mean,
            FIRST(hue_circular_std) FILTER (WHERE hue_circular_std != 'NA') AS hue_circular_std,
            FIRST(hue_median) FILTER (WHERE hue_median != 'NA') AS hue_median,            
            FIRST(nir_mean) FILTER (WHERE nir_mean != 'NA') AS nir_mean,
            FIRST(nir_median) FILTER (WHERE nir_median != 'NA') AS nir_median,
            FIRST(nir_stdev) FILTER (WHERE nir_stdev != 'NA') AS nir_stdev
        FROM read_csv_auto('{arquivo}')
        GROUP BY ALL
        """

        duckdb.sql(f"COPY ({query}) TO '{caminho_out / f"agrupado_{arquivo.name}"}' (HEADER, DELIMITER ',');")
        print(f"✔ Ordenação de {arquivo} concluída via DuckDB!")

    for arquivo in caminho_in.glob("ordenado_reduzido_*.csv"):
        query = f"""
        SELECT 
            camera, imgtype, zoom, exposure, gain, frame, rotation, lifter, 
            timestamp, id, barcode, treatment, velocity, cartag, measurementlabel, 
            other, image,

            -- Agrega pegando o primeiro valor válido (diferente de NULL e [(nan, nan)])
            FIRST(blue_frequencies) FILTER (
                WHERE blue_frequencies IS NOT NULL 
                  AND REPLACE(blue_frequencies, ' ', '') != '[(nan,nan)]'
            ) AS blue_frequencies,

            FIRST(green_frequencies) FILTER (
                WHERE green_frequencies IS NOT NULL 
                  AND REPLACE(green_frequencies, ' ', '') != '[(nan,nan)]'
            ) AS green_frequencies,

            FIRST(red_frequencies) FILTER (
                WHERE red_frequencies IS NOT NULL 
                  AND REPLACE(red_frequencies, ' ', '') != '[(nan,nan)]'
            ) AS red_frequencies,

            FIRST(lightness_frequencies) FILTER (
                WHERE lightness_frequencies IS NOT NULL 
                  AND REPLACE(lightness_frequencies, ' ', '') != '[(nan,nan)]'
            ) AS lightness_frequencies,

            FIRST("green-magenta_frequencies") FILTER (
                WHERE "green-magenta_frequencies" IS NOT NULL 
                  AND REPLACE("green-magenta_frequencies", ' ', '') != '[(nan,nan)]'
            ) AS "green-magenta_frequencies",

            FIRST("blue-yellow_frequencies") FILTER (
                WHERE "blue-yellow_frequencies" IS NOT NULL 
                  AND REPLACE("blue-yellow_frequencies", ' ', '') != '[(nan,nan)]'
            ) AS "blue-yellow_frequencies",

            FIRST(hue_frequencies) FILTER (
                WHERE hue_frequencies IS NOT NULL 
                  AND REPLACE(hue_frequencies, ' ', '') != '[(nan,nan)]'
            ) AS hue_frequencies,

            FIRST(saturation_frequencies) FILTER (
                WHERE saturation_frequencies IS NOT NULL 
                  AND REPLACE(saturation_frequencies, ' ', '') != '[(nan,nan)]'
            ) AS saturation_frequencies,

            FIRST(value_frequencies) FILTER (
                WHERE value_frequencies IS NOT NULL 
                  AND REPLACE(value_frequencies, ' ', '') != '[(nan,nan)]'
            ) AS value_frequencies,

            FIRST(nir_frequencies) FILTER (
                WHERE nir_frequencies IS NOT NULL 
                  AND REPLACE(nir_frequencies, ' ', '') != '[(nan,nan)]'
            ) AS nir_frequencies

        FROM read_csv_auto('{arquivo}')
        GROUP BY ALL
        """

        duckdb.sql(f"COPY ({query}) TO '{caminho_out / f"agrupado_{arquivo.name}"}' (HEADER, DELIMITER ',');")
        print(f"✔ Ordenação de {arquivo} concluída via DuckDB!")


def unificar_csv(tipo = None):
    query = f"""SELECT 
        CASE 
            WHEN EXTRACT(HOUR FROM CAST(CASE WHEN timestamp LIKE '[%' THEN REGEXP_EXTRACT(timestamp, '''([^'']+)''', 1) ELSE timestamp END AS TIMESTAMP)) < 5 
                THEN CAST(CAST(CASE WHEN timestamp LIKE '[%' THEN REGEXP_EXTRACT(timestamp, '''([^'']+)''', 1) ELSE timestamp END AS TIMESTAMP) - INTERVAL '1 DAY' AS DATE)
            ELSE 
                CAST(CASE WHEN timestamp LIKE '[%' THEN REGEXP_EXTRACT(timestamp, '''([^'']+)''', 1) ELSE timestamp END AS DATE)
        END AS data_operacional,
        CASE WHEN barcode LIKE '[%' THEN REGEXP_EXTRACT(barcode, '''([^'']+)''', 1) ELSE barcode END AS barcode,
        CASE WHEN timestamp LIKE '[%' THEN REGEXP_EXTRACT(timestamp, '''([^'']+)''', 1) ELSE timestamp END AS timestamp,
        camera, imgtype, zoom, exposure, gain, frame, rotation, lifter, 
        id, treatment, velocity, cartag, measurementlabel, 
        other, image, color_chip_size, median_color_chip_height, median_color_chip_width, in_bounds,
        area, convex_hull_area, solidity, perimeter,
        width, height, longest_path, convex_hull_vertices, object_in_frame,
        ellipse_major_axis, ellipse_minor_axis, ellipse_angle, ellipse_eccentricity,
        horizontal_reference_position, height_above_reference, height_below_reference,
        area_above_reference, percent_area_above_reference, area_below_reference, percent_area_below_reference,
        hue_circular_mean, hue_circular_std, hue_median,
        nir_mean, nir_median, nir_stdev
        FROM read_csv_auto('./4_csv_agrupados/*single-value*.csv')
        { f"""WHERE SUBSTRING(
            CASE WHEN barcode LIKE '[%' THEN REGEXP_EXTRACT(barcode, '''([^'']+)''', 1) ELSE barcode END, 
            7, 1
        ) = '{tipo}'""" if tipo else ""}
        ORDER BY data_operacional ASC, barcode ASC, timestamp ASC"""

    query_2 = f"""SELECT
        CASE 
            WHEN EXTRACT(HOUR FROM CAST(CASE WHEN timestamp LIKE '[%' THEN REGEXP_EXTRACT(timestamp, '''([^'']+)''', 1) ELSE timestamp END AS TIMESTAMP)) < 5 
                THEN CAST(CAST(CASE WHEN timestamp LIKE '[%' THEN REGEXP_EXTRACT(timestamp, '''([^'']+)''', 1) ELSE timestamp END AS TIMESTAMP) - INTERVAL '1 DAY' AS DATE)
            ELSE 
                CAST(CASE WHEN timestamp LIKE '[%' THEN REGEXP_EXTRACT(timestamp, '''([^'']+)''', 1) ELSE timestamp END AS DATE)
        END AS data_operacional,
        CASE WHEN barcode LIKE '[%' THEN REGEXP_EXTRACT(barcode, '''([^'']+)''', 1) ELSE barcode END AS barcode,
        CASE WHEN timestamp LIKE '[%' THEN REGEXP_EXTRACT(timestamp, '''([^'']+)''', 1) ELSE timestamp END AS timestamp,                
        camera, imgtype, zoom, exposure, gain, frame, rotation, lifter, 
        id, treatment, velocity, cartag, measurementlabel, 
        other, image, blue_frequencies, green_frequencies, red_frequencies,
        lightness_frequencies, "green-magenta_frequencies", "blue-yellow_frequencies",
        hue_frequencies, saturation_frequencies, value_frequencies, nir_frequencies  
        FROM read_csv_auto('./4_csv_agrupados/*multi-value*.csv')
        { f"""WHERE SUBSTRING(
            CASE WHEN barcode LIKE '[%' THEN REGEXP_EXTRACT(barcode, '''([^'']+)''', 1) ELSE barcode END, 
            7, 1
        ) = '{tipo}'""" if tipo else ""}
        ORDER BY data_operacional ASC, barcode ASC, timestamp ASC"""

    duckdb.sql(f"COPY ({query}) TO './5_csv_unificado/single-value-{tipo if tipo else "full"}.csv' (HEADER, DELIMITER ',');")
    duckdb.sql(f"COPY ({query_2}) TO './5_csv_unificado/multi-value-{tipo if tipo else "full"}.csv' (HEADER, DELIMITER ',');")


def barcodes_faltantes():
    query = """
    WITH mestre AS (
        SELECT DISTINCT 
            CASE 
                WHEN CAST(barcode AS VARCHAR) LIKE '[%' THEN REGEXP_EXTRACT(CAST(barcode AS VARCHAR), '''([^'']+)''', 1) 
                ELSE CAST(barcode AS VARCHAR) 
            END AS barcode_clean
        FROM read_csv_auto('barcodes.csv')
    ),
    processados AS (
        SELECT DISTINCT 
            CASE 
                WHEN CAST(barcode AS VARCHAR) LIKE '[%' THEN REGEXP_EXTRACT(CAST(barcode AS VARCHAR), '''([^'']+)''', 1) 
                ELSE CAST(barcode AS VARCHAR) 
            END AS barcode_clean
        FROM read_csv_auto('./5_csv_unificado/single-value-full.csv')
    )
    SELECT 
        m.barcode_clean AS barcode_faltante
    FROM mestre m
    LEFT JOIN processados p ON m.barcode_clean = p.barcode_clean
    WHERE p.barcode_clean IS NULL
    ORDER BY barcode_faltante ASC
    """

    duckdb.sql(
        f"COPY ({query}) TO 'barcodes_faltantes.csv' (HEADER, DELIMITER ',');"
    )

    print("Verificação concluída! Confira o arquivo 'barcodes_faltantes.csv'.")


def faltantes_dednoplant():
    caminho_faltantes = 'barcodes_faltantes.csv'
    caminho_problemas = 'dead_no_plant.csv'
    caminho_saida_validacao = 'validacao_faltantes.csv'

    query = f"""
    WITH faltantes AS (
        SELECT DISTINCT 
            CASE 
                WHEN CAST(barcode_faltante AS VARCHAR) LIKE '[%' THEN REGEXP_EXTRACT(CAST(barcode_faltante AS VARCHAR), '''([^'']+)''', 1) 
                ELSE CAST(barcode_faltante AS VARCHAR) 
            END AS barcode
        FROM read_csv_auto('{caminho_faltantes}')
    ),
    problemas AS (
        SELECT DISTINCT 
            CASE 
                WHEN CAST(barcode AS VARCHAR) LIKE '[%' THEN REGEXP_EXTRACT(CAST(barcode AS VARCHAR), '''([^'']+)''', 1) 
                ELSE CAST(barcode AS VARCHAR) 
            END AS barcode
        FROM read_csv_auto('{caminho_problemas}')
    )
    SELECT 
        f.barcode AS barcode_faltante,
        CASE 
            WHEN p.barcode IS NOT NULL THEN 'OK - Está na lista de problemas'
            ELSE 'ALERTA - Faltante mas NÃO está na lista de problemas'
        END AS status_verificacao
    FROM faltantes f
    LEFT JOIN problemas p ON f.barcode = p.barcode
    ORDER BY status_verificacao DESC, f.barcode ASC
    """

    df_resumo = duckdb.sql(f"""
        WITH resultado AS ({query})
        SELECT status_verificacao, COUNT(*) AS quantidade
        FROM resultado
        GROUP BY status_verificacao
    """).df()

    print("--- RESUMO DA VERIFICAÇÃO ---")
    print(df_resumo.to_string(index=False))

    duckdb.sql(f"COPY ({query}) TO '{caminho_saida_validacao}' (HEADER, DELIMITER ',');")
    print(f"\nDetalhes salvos em: '{caminho_saida_validacao}'")


def contar_linhas_por_data():
    query = f"""
                SELECT data_operacional, COUNT(*) AS quantidade
                FROM read_csv_auto('./5_csv_unificado/single-value-full.csv')
                GROUP BY data_operacional
                ORDER BY data_operacional ASC
                """

    duckdb.sql(query).show()


def detectar_duplicacoes_por_dia():
    query = f"""
        SELECT data_operacional, barcode, COUNT(*) AS quantidade
        FROM read_csv_auto('./5_csv_unificado/single-value-full.csv')
        GROUP BY data_operacional, barcode
        HAVING COUNT(*) > 1
        ORDER BY data_operacional ASC, barcode ASC
    """

    duckdb.sql(f"COPY ({query}) TO 'duplicados_por_dia.csv' (HEADER, DELIMITER ',');")
