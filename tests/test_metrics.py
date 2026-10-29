"""Testes unitários para a camada Gold (Métricas Agregadas)."""

from __future__ import annotations

from pathlib import Path

from src.extract.open_meteo_extractor import OpenMeteoExtractor
from src.metrics.metrics_generator import MetricsGenerator
from src.transform.dimensional_transformer import DimensionalTransformer


def test_metrics_generator_produces_regional_and_capital_marts(tmp_path: Path) -> None:
    extractor = OpenMeteoExtractor()
    df_bronze = extractor.flatten_to_dataframe(extractor.generate_fallback_records(days=10))
    star = DimensionalTransformer().transform(df_bronze, save_processed=False)

    generator = MetricsGenerator()
    gold = generator.generate_all(star, save_gold=True, output_dir=tmp_path)

    # 5 macrorregiões brasileiras (Norte, Nordeste, Centro-Oeste, Sudeste, Sul)
    assert len(gold.agg_metricas_regionais) == 5
    assert set(gold.agg_metricas_regionais["regiao"]) == {
        "Norte",
        "Nordeste",
        "Centro-Oeste",
        "Sudeste",
        "Sul",
    }
    assert gold.agg_metricas_regionais["qtd_capitais"].sum() == 27

    # 27 capitais no resumo analítico
    assert len(gold.agg_resumo_capitais) == 27
    assert gold.agg_resumo_capitais["ranking_temperatura"].min() == 1
    assert gold.agg_resumo_capitais["ranking_temperatura"].max() <= 27

    # Verifica artefatos gerados
    assert (tmp_path / "agg_metricas_regionais.parquet").exists()
    assert (tmp_path / "agg_resumo_capitais.parquet").exists()
    assert (tmp_path / "relatorio_executivo_metricas.md").exists()
