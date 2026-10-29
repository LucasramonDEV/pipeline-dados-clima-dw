"""Testes unitários para a camada de Extração (Bronze)."""

from __future__ import annotations

from pathlib import Path

from src.config import BRAZILIAN_CAPITALS
from src.extract.open_meteo_extractor import DAILY_VARIABLES, OpenMeteoExtractor


def test_generate_fallback_records_cover_all_27_capitals() -> None:
    extractor = OpenMeteoExtractor()
    records = extractor.generate_fallback_records(days=10)

    assert len(records) == len(BRAZILIAN_CAPITALS) == 27
    first = records[0]
    assert "capital_metadata" in first
    assert "daily" in first
    assert len(first["daily"]["time"]) == 10


def test_flatten_to_dataframe_schema_and_row_count(tmp_path: Path) -> None:
    extractor = OpenMeteoExtractor()
    records = extractor.generate_fallback_records(days=7)
    df_bronze = extractor.flatten_to_dataframe(records)

    assert len(df_bronze) == 27 * 7
    for var in DAILY_VARIABLES:
        assert var in df_bronze.columns

    saved = extractor.save_bronze_artifacts(records, df_bronze, output_dir=tmp_path)
    assert saved["json"].exists()
    assert saved["csv"].exists()
