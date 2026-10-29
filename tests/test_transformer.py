"""Testes unitários para a camada de Transformação e Modelagem Dimensional (Star Schema)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.extract.open_meteo_extractor import OpenMeteoExtractor
from src.transform.dimensional_transformer import DimensionalTransformer


def test_clean_bronze_handles_duplicates_and_inverted_temperatures() -> None:
    extractor = OpenMeteoExtractor()
    raw = extractor.generate_fallback_records(days=5)
    df_bronze = extractor.flatten_to_dataframe(raw)

    # Injeta uma linha duplicada e temperaturas invertidas (t_max < t_min) e chuva negativa
    dirty_row = df_bronze.iloc[[0]].copy()
    dirty_row["temperature_2m_max"] = 15.0
    dirty_row["temperature_2m_min"] = 28.0
    dirty_row["precipitation_sum"] = -12.5
    df_dirty = pd.concat([df_bronze, dirty_row], ignore_index=True)

    transformer = DimensionalTransformer()
    df_clean = transformer.clean_bronze_dataframe(df_dirty)

    # Duplicata deve ter sido removida
    assert len(df_clean) == len(df_bronze)
    # Nenhuma temperatura máxima pode ser menor que a mínima
    assert (df_clean["temperature_2m_max"] >= df_clean["temperature_2m_min"]).all()
    # Nenhuma precipitação pode ser negativa
    assert (df_clean["precipitation_sum"] >= 0.0).all()
    # Amplitude térmica deve ser sempre >= 0
    assert (df_clean["amplitude_termica_c"] >= 0.0).all()


def test_star_schema_referential_integrity(tmp_path: Path) -> None:
    extractor = OpenMeteoExtractor()
    df_bronze = extractor.flatten_to_dataframe(extractor.generate_fallback_records(days=7))

    transformer = DimensionalTransformer()
    star = transformer.transform(df_bronze, save_processed=True, output_dir=tmp_path)

    assert len(star.dim_localidade) == 27
    assert len(star.dim_calendario) == 7
    assert len(star.fato_clima_diario) == 27 * 7

    # Integridade referencial (FK -> PK) entre Fato e todas as Dimensões
    assert set(star.fato_clima_diario["sk_localidade"]).issubset(
        set(star.dim_localidade["sk_localidade"])
    )
    assert set(star.fato_clima_diario["sk_tempo"]).issubset(
        set(star.dim_calendario["sk_tempo"])
    )
    assert set(star.fato_clima_diario["sk_condicao"]).issubset(
        set(star.dim_condicao_climatica["sk_condicao"])
    )


def test_southern_hemisphere_seasons_and_uv_classification() -> None:
    t = DimensionalTransformer()
    assert t.get_southern_hemisphere_season(date(2026, 1, 15)) == "Verão"
    assert t.get_southern_hemisphere_season(date(2026, 4, 15)) == "Outono"
    assert t.get_southern_hemisphere_season(date(2026, 7, 15)) == "Inverno"
    assert t.get_southern_hemisphere_season(date(2026, 10, 29)) == "Primavera"

    assert t.classify_uv_index(2.1) == "Baixo"
    assert t.classify_uv_index(4.5) == "Moderado"
    assert t.classify_uv_index(7.0) == "Alto"
    assert t.classify_uv_index(9.5) == "Muito Alto"
    assert t.classify_uv_index(12.0) == "Extremo"


def test_empty_dataframe_raises_value_error() -> None:
    transformer = DimensionalTransformer()
    with pytest.raises(ValueError, match="vazio"):
        transformer.clean_bronze_dataframe(pd.DataFrame())
