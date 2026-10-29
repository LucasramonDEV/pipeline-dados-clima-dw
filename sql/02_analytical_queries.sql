-- =============================================================================
-- CONSULTAS ANALÍTICAS (OLAP) SOBRE O STAR SCHEMA - PORTFÓLIO DE ENGENHARIA DE DADOS
-- =============================================================================

-- 1. Agregação Regional: Temperatura média, precipitação acumulada e total de alertas por Região
SELECT
    l.regiao,
    COUNT(DISTINCT l.sk_localidade) AS qtd_capitais,
    ROUND(AVG(f.temp_media_c), 2) AS temp_media_c,
    ROUND(MAX(f.temp_max_c), 2) AS maior_temp_registrada_c,
    ROUND(MIN(f.temp_min_c), 2) AS menor_temp_registrada_c,
    ROUND(SUM(f.precipitacao_total_mm), 2) AS chuva_acumulada_mm,
    SUM(CASE WHEN f.alerta_chuva_intensa THEN 1 ELSE 0 END) AS eventos_chuva_intensa,
    SUM(CASE WHEN f.alerta_calor_extremo THEN 1 ELSE 0 END) AS eventos_calor_extremo
FROM dw.fato_clima_diario f
JOIN dw.dim_localidade l ON f.sk_localidade = l.sk_localidade
GROUP BY l.regiao
ORDER BY temp_media_c DESC;

-- 2. Top 10 Capitais com Maior Amplitude Térmica Média e Ranking Regional (Window Function)
SELECT
    l.nome_capital,
    l.sigla_uf,
    l.regiao,
    ROUND(AVG(f.amplitude_termica_c), 2) AS amplitude_media_c,
    ROUND(MAX(f.amplitude_termica_c), 2) AS amplitude_maxima_c,
    DENSE_RANK() OVER (
        PARTITION BY l.regiao
        ORDER BY AVG(f.amplitude_termica_c) DESC
    ) AS rank_amplitude_na_regiao
FROM dw.fato_clima_diario f
JOIN dw.dim_localidade l ON f.sk_localidade = l.sk_localidade
GROUP BY l.nome_capital, l.sigla_uf, l.regiao
ORDER BY amplitude_media_c DESC
LIMIT 10;

-- 3. Média Móvel de 7 dias de Temperatura e Precipitação por Capital (Série Temporal)
SELECT
    l.nome_capital,
    l.sigla_uf,
    c.data_completa,
    f.temp_media_c,
    ROUND(
        AVG(f.temp_media_c) OVER (
            PARTITION BY l.sk_localidade
            ORDER BY c.data_completa
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ), 2
    ) AS media_movel_7d_temp_c,
    f.precipitacao_total_mm,
    ROUND(
        SUM(f.precipitacao_total_mm) OVER (
            PARTITION BY l.sk_localidade
            ORDER BY c.data_completa
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ), 2
    ) AS acumulado_movel_7d_chuva_mm
FROM dw.fato_clima_diario f
JOIN dw.dim_localidade l ON f.sk_localidade = l.sk_localidade
JOIN dw.dim_calendario c ON f.sk_tempo = c.sk_tempo
ORDER BY l.nome_capital, c.data_completa;

-- 4. Distribuição de Condições Meteorológicas (WMO) e Nível de Severidade
SELECT
    w.grupo_climatico,
    w.nivel_severidade,
    COUNT(*) AS total_ocorrencias_capital_dia,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentual_total,
    ROUND(AVG(f.precipitacao_total_mm), 2) AS precipitacao_media_mm,
    ROUND(AVG(f.velocidade_vento_max_kmh), 2) AS vento_medio_kmh
FROM dw.fato_clima_diario f
JOIN dw.dim_condicao_climatica w ON f.sk_condicao = w.sk_condicao
GROUP BY w.grupo_climatico, w.nivel_severidade
ORDER BY total_ocorrencias_capital_dia DESC;
