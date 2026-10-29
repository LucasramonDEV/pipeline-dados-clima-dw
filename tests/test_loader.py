"""Testes de integração da camada de Carga (Load) no PostgreSQL Data Warehouse."""

from __future__ import annotations

import pytest

from src.extract.open_meteo_extractor import OpenMeteoExtractor
from src.load.postgres_loader import PostgresLoader
from src.metrics.metrics_generator import MetricsGenerator
from src.transform.dimensional_transformer import DimensionalTransformer


def test_postgres_loader_idempotent_upsert() -> None:
    loader = PostgresLoader()
    if not loader.check_connection():
        pytest.skip("Container PostgreSQL não está ativo no momento do teste.")

    extractor = OpenMeteoExtractor()
    df_bronze = extractor.flatten_to_dataframe(extractor.generate_fallback_records(days=5))
    star = DimensionalTransformer().transform(df_bronze, save_processed=False)
    gold = MetricsGenerator().generate_all(star, save_gold=False)

    # Primeira execução (INSERT/UPSERT)
    first_counts = loader.load_all(star=star, gold=gold)
    # Segunda execução consecutiva (deve fazer UPSERT idempotente sem duplicar registros)
    second_counts = loader.load_all(star=star, gold=gold)

    assert first_counts["dim_localidade"] == 27
    assert second_counts["dim_localidade"] == 27
    assert first_counts["agg_metricas_regionais"] == 5

    summary = loader.fetch_dw_summary()
    assert summary["dim_localidade"] == 27
    assert summary["agg_metricas_regionais"] == 5
    assert summary["agg_resumo_capitais"] == 27
    assert summary["fato_clima_diario"] >= 27 * 5
