-- =============================================================================
-- DATA WAREHOUSE: MONITORAMENTO CLIMÁTICO DAS CAPITAIS BRASILEIRAS
-- Modelagem Dimensional (Star Schema) - PostgreSQL 16
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS dw;

-- -----------------------------------------------------------------------------
-- 1. DIMENSÃO LOCALIDADE (dw.dim_localidade)
-- Granularidade: 1 registro por capital estadual brasileira (SCD Tipo 1)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.dim_localidade (
    sk_localidade       INTEGER PRIMARY KEY,
    codigo_ibge         INTEGER NOT NULL UNIQUE,
    nome_capital        VARCHAR(100) NOT NULL,
    sigla_uf            CHAR(2) NOT NULL,
    nome_estado         VARCHAR(60) NOT NULL,
    regiao              VARCHAR(30) NOT NULL,
    latitude            NUMERIC(9, 6) NOT NULL,
    longitude           NUMERIC(9, 6) NOT NULL,
    altitude_metros     NUMERIC(7, 2) NOT NULL,
    fuso_horario        VARCHAR(50) NOT NULL DEFAULT 'America/Sao_Paulo',
    atualizado_em       TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_localidade_regiao ON dw.dim_localidade (regiao);
CREATE INDEX IF NOT EXISTS idx_dim_localidade_uf ON dw.dim_localidade (sigla_uf);

-- -----------------------------------------------------------------------------
-- 2. DIMENSÃO CALENDÁRIO / TEMPO (dw.dim_calendario)
-- Granularidade: 1 registro por dia civil
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.dim_calendario (
    sk_tempo            INTEGER PRIMARY KEY,           -- Formato YYYYMMDD (ex: 20261029)
    data_completa       DATE NOT NULL UNIQUE,
    ano                 SMALLINT NOT NULL,
    trimestre           SMALLINT NOT NULL,
    mes                 SMALLINT NOT NULL,
    nome_mes            VARCHAR(20) NOT NULL,
    dia                 SMALLINT NOT NULL,
    dia_da_semana       SMALLINT NOT NULL,             -- 0=Segunda .. 6=Domingo
    nome_dia_semana     VARCHAR(20) NOT NULL,
    semana_do_ano       SMALLINT NOT NULL,
    eh_fim_de_semana    BOOLEAN NOT NULL,
    estacao_hemisferio_sul VARCHAR(20) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dim_calendario_data ON dw.dim_calendario (data_completa);
CREATE INDEX IF NOT EXISTS idx_dim_calendario_ano_mes ON dw.dim_calendario (ano, mes);

-- -----------------------------------------------------------------------------
-- 3. DIMENSÃO CONDIÇÃO CLIMÁTICA (dw.dim_condicao_climatica)
-- Granularidade: 1 registro por código meteorológico WMO (World Meteorological Org)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.dim_condicao_climatica (
    sk_condicao         INTEGER PRIMARY KEY,
    codigo_wmo          INTEGER NOT NULL UNIQUE,
    descricao_clima     VARCHAR(100) NOT NULL,
    grupo_climatico     VARCHAR(50) NOT NULL,          -- Céu Limpo, Nublado, Chuva, Tempestade, etc.
    nivel_severidade    VARCHAR(20) NOT NULL,          -- Baixo, Moderado, Alto, Extremo
    requer_alerta       BOOLEAN NOT NULL DEFAULT FALSE
);

-- -----------------------------------------------------------------------------
-- 4. TABELA FATO: CLIMA DIÁRIO (dw.fato_clima_diario)
-- Granularidade: 1 registro por capital por dia (sk_localidade + sk_tempo)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.fato_clima_diario (
    id_fato                     BIGSERIAL PRIMARY KEY,
    sk_localidade               INTEGER NOT NULL REFERENCES dw.dim_localidade (sk_localidade),
    sk_tempo                    INTEGER NOT NULL REFERENCES dw.dim_calendario (sk_tempo),
    sk_condicao                 INTEGER NOT NULL REFERENCES dw.dim_condicao_climatica (sk_condicao),
    temp_max_c                  NUMERIC(5, 2) NOT NULL,
    temp_min_c                  NUMERIC(5, 2) NOT NULL,
    temp_media_c                NUMERIC(5, 2) NOT NULL,
    amplitude_termica_c         NUMERIC(5, 2) NOT NULL,
    sensacao_termica_max_c      NUMERIC(5, 2),
    sensacao_termica_min_c      NUMERIC(5, 2),
    precipitacao_total_mm       NUMERIC(7, 2) NOT NULL DEFAULT 0.0,
    horas_precipitacao          NUMERIC(4, 1) NOT NULL DEFAULT 0.0,
    velocidade_vento_max_kmh    NUMERIC(6, 2) NOT NULL DEFAULT 0.0,
    rajada_vento_max_kmh        NUMERIC(6, 2),
    indice_uv_max               NUMERIC(4, 2),
    radiacao_solar_mj_m2        NUMERIC(6, 2),
    classificacao_uv            VARCHAR(25) NOT NULL,
    alerta_chuva_intensa        BOOLEAN NOT NULL DEFAULT FALSE,
    alerta_calor_extremo        BOOLEAN NOT NULL DEFAULT FALSE,
    data_extracao_utc           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fato_localidade_tempo UNIQUE (sk_localidade, sk_tempo)
);

CREATE INDEX IF NOT EXISTS idx_fato_sk_tempo ON dw.fato_clima_diario (sk_tempo);
CREATE INDEX IF NOT EXISTS idx_fato_sk_localidade ON dw.fato_clima_diario (sk_localidade);
CREATE INDEX IF NOT EXISTS idx_fato_sk_condicao ON dw.fato_clima_diario (sk_condicao);

-- -----------------------------------------------------------------------------
-- 5. CAMADA GOLD: TABELAS DE MÉTRICAS AGREGADAS (Data Marts)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.agg_metricas_regionais (
    regiao                      VARCHAR(30) PRIMARY KEY,
    qtd_capitais                INTEGER NOT NULL,
    total_observacoes           INTEGER NOT NULL,
    temp_media_regional_c       NUMERIC(5, 2) NOT NULL,
    temp_max_absoluta_c         NUMERIC(5, 2) NOT NULL,
    temp_min_absoluta_c         NUMERIC(5, 2) NOT NULL,
    amplitude_termica_media_c   NUMERIC(5, 2) NOT NULL,
    precipitacao_acumulada_mm   NUMERIC(9, 2) NOT NULL,
    precipitacao_media_diaria_mm NUMERIC(7, 2) NOT NULL,
    vento_max_registrado_kmh    NUMERIC(6, 2) NOT NULL,
    indice_uv_medio             NUMERIC(4, 2) NOT NULL,
    dias_com_alerta_chuva       INTEGER NOT NULL,
    dias_com_alerta_calor       INTEGER NOT NULL,
    atualizado_em               TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dw.agg_resumo_capitais (
    codigo_ibge                 INTEGER PRIMARY KEY,
    nome_capital                VARCHAR(100) NOT NULL,
    sigla_uf                    CHAR(2) NOT NULL,
    regiao                      VARCHAR(30) NOT NULL,
    dias_analisados             INTEGER NOT NULL,
    temp_media_periodo_c        NUMERIC(5, 2) NOT NULL,
    temp_max_periodo_c          NUMERIC(5, 2) NOT NULL,
    temp_min_periodo_c          NUMERIC(5, 2) NOT NULL,
    amplitude_max_c             NUMERIC(5, 2) NOT NULL,
    chuva_acumulada_mm          NUMERIC(8, 2) NOT NULL,
    dias_chuvosos               INTEGER NOT NULL,
    pct_dias_chuvosos           NUMERIC(5, 2) NOT NULL,
    vento_max_kmh               NUMERIC(6, 2) NOT NULL,
    uv_max_registrado           NUMERIC(4, 2) NOT NULL,
    ranking_temperatura         INTEGER NOT NULL,
    ranking_precipitacao        INTEGER NOT NULL,
    atualizado_em               TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 6. VIEWS ANALÍTICAS PARA CONSUMO BI / ANALYTICS
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW dw.vw_analise_climatica_completa AS
SELECT
    c.data_completa,
    c.ano,
    c.mes,
    c.nome_mes,
    c.nome_dia_semana,
    c.eh_fim_de_semana,
    c.estacao_hemisferio_sul,
    l.codigo_ibge,
    l.nome_capital,
    l.sigla_uf,
    l.regiao,
    l.latitude,
    l.longitude,
    w.codigo_wmo,
    w.descricao_clima,
    w.grupo_climatico,
    w.nivel_severidade,
    f.temp_max_c,
    f.temp_min_c,
    f.temp_media_c,
    f.amplitude_termica_c,
    f.precipitacao_total_mm,
    f.horas_precipitacao,
    f.velocidade_vento_max_kmh,
    f.indice_uv_max,
    f.radiacao_solar_mj_m2,
    f.classificacao_uv,
    f.alerta_chuva_intensa,
    f.alerta_calor_extremo
FROM dw.fato_clima_diario f
INNER JOIN dw.dim_calendario c ON f.sk_tempo = c.sk_tempo
INNER JOIN dw.dim_localidade l ON f.sk_localidade = l.sk_localidade
INNER JOIN dw.dim_condicao_climatica w ON f.sk_condicao = w.sk_condicao;
