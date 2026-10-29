"""Fluxo de Orquestração com Prefect (Tasks, Retries, Observabilidade e Linhagem)."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

os.environ.setdefault("PREFECT_SERVER_ANALYTICS_ENABLED", "false")
os.environ.setdefault("DO_NOT_TRACK", "1")

try:
    from prefect import flow, task
except ImportError:  # Fallback leve caso executado sem Prefect instalado localmente

    def task(*_args: Any, **_kwargs: Any):  # type: ignore[misc]
        def decorator(func: Any) -> Any:
            return func

        return decorator

    def flow(*_args: Any, **_kwargs: Any):  # type: ignore[misc]
        def decorator(func: Any) -> Any:
            return func

        return decorator


from src.config import configure_logging
from src.extract.open_meteo_extractor import OpenMeteoExtractor
from src.load.postgres_loader import PostgresLoader
from src.metrics.metrics_generator import GoldMetrics, MetricsGenerator
from src.transform.dimensional_transformer import DimensionalTransformer, StarSchemaTables

logger = configure_logging("orchestrator")


@task(
    name="1. Extract Open-Meteo API (Bronze)",
    retries=2,
    retry_delay_seconds=10,
    description="Extrai dados meteorológicos diários das 27 capitais brasileiras via API Open-Meteo.",
)
def extract_weather_task(offline: bool = False) -> pd.DataFrame:
    extractor = OpenMeteoExtractor()
    return extractor.extract(offline=offline, save_raw=True)


@task(
    name="2. Transform & Star Schema (Silver)",
    description="Realiza limpeza, padronização e construção das tabelas Fato e Dimensões.",
)
def transform_star_schema_task(df_bronze: pd.DataFrame) -> StarSchemaTables:
    transformer = DimensionalTransformer()
    return transformer.transform(df_bronze=df_bronze, save_processed=True)


@task(
    name="3. Compute Aggregated Metrics (Gold)",
    description="Gera métricas agregadas por macrorregião e ranking das capitais brasileiras.",
)
def generate_metrics_task(star_schema: StarSchemaTables) -> GoldMetrics:
    generator = MetricsGenerator()
    return generator.generate_all(star=star_schema, save_gold=True)


@task(
    name="4. Load PostgreSQL Data Warehouse",
    retries=2,
    retry_delay_seconds=5,
    description="Carrega Dimensões, Fato e Tabelas Gold no PostgreSQL usando UPSERT idempotente.",
)
def load_postgres_dw_task(
    star_schema: StarSchemaTables,
    gold_metrics: GoldMetrics,
    skip_db: bool = False,
) -> dict[str, int]:
    if skip_db:
        logger.info("Flag skip_db=True ativa: carga no PostgreSQL ignorada.")
        return {}

    loader = PostgresLoader()
    if not loader.check_connection():
        logger.warning(
            "PostgreSQL não está acessível no momento. Os artefatos Parquet/CSV e relatórios "
            "foram gerados em data/processed e data/gold. Suba o container Docker para persistir no banco."
        )
        return {}

    return loader.load_all(star=star_schema, gold=gold_metrics)


@flow(
    name="pipeline-clima-capitais-brasileiras-dw",
    description="Pipeline ETL/ELT completo: Open-Meteo API -> Pandas Star Schema -> PostgreSQL DW -> Gold Metrics",
    log_prints=True,
)
def clima_dw_etl_flow(offline: bool = False, skip_db: bool = False) -> dict[str, Any]:
    """Orquestra a execução ponta a ponta do pipeline de engenharia de dados."""
    logger.info("=== INICIANDO PIPELINE DE DADOS CLIMÁTICOS (STAR SCHEMA DW) ===")

    df_bronze = extract_weather_task(offline=offline)
    star_schema = transform_star_schema_task(df_bronze=df_bronze)
    gold_metrics = generate_metrics_task(star_schema=star_schema)
    db_counts = load_postgres_dw_task(
        star_schema=star_schema,
        gold_metrics=gold_metrics,
        skip_db=skip_db,
    )

    result = {
        "bronze_rows": len(df_bronze),
        "dim_localidade_rows": len(star_schema.dim_localidade),
        "dim_calendario_rows": len(star_schema.dim_calendario),
        "dim_condicao_rows": len(star_schema.dim_condicao_climatica),
        "fato_clima_diario_rows": len(star_schema.fato_clima_diario),
        "agg_regioes_rows": len(gold_metrics.agg_metricas_regionais),
        "agg_capitais_rows": len(gold_metrics.agg_resumo_capitais),
        "postgres_upserted": db_counts,
        "gold_metrics": gold_metrics,
    }
    logger.info("=== PIPELINE FINALIZADO COM SUCESSO ===")
    return result


if __name__ == "__main__":
    clima_dw_etl_flow()
