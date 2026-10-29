"""Ponto de entrada CLI do Pipeline ETL/ELT de Dados Climáticos das Capitais Brasileiras."""

from __future__ import annotations

import argparse
from typing import Sequence

from src.orchestration.prefect_flow import clima_dw_etl_flow


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline ETL/ELT: Open-Meteo API -> Pandas Star Schema -> PostgreSQL DW"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Executa com gerador determinístico offline (sem necessidade de rede externa).",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Executa Extração, Transformação e Métricas Gold sem exigir conexão ativa com PostgreSQL.",
    )
    return parser.parse_args(argv)


def print_executive_summary(result: dict) -> None:
    """Exibe no terminal um resumo executivo das tabelas e métricas agregadas."""
    gold = result["gold_metrics"]
    print("\n" + "=" * 88)
    print(" RESUMO EXECUTIVO DO PIPELINE DE DADOS (MEDALLION + STAR SCHEMA DW)")
    print("=" * 88)
    print(f" • Registros extraídos (Camada Bronze)     : {result['bronze_rows']}")
    print(f" • Dimensão Localidade (dim_localidade)    : {result['dim_localidade_rows']} capitais")
    print(f" • Dimensão Calendário (dim_calendario)    : {result['dim_calendario_rows']} dias")
    print(f" • Dimensão Condição WMO (dim_condicao)    : {result['dim_condicao_rows']} categorias")
    print(f" • Tabela Fato (fato_clima_diario)         : {result['fato_clima_diario_rows']} medições")

    if result["postgres_upserted"]:
        print(f" • Carga PostgreSQL DW (UPSERT idempotente): {result['postgres_upserted']}")
    else:
        print(" • Carga PostgreSQL DW                     : Artefatos salvos em disco (data/processed & data/gold)")

    print("\n--- MÉTRICAS AGREGADAS POR MACRORREGIÃO (CAMADA GOLD) ---")
    cols_reg = [
        "regiao",
        "qtd_capitais",
        "temp_media_regional_c",
        "temp_max_absoluta_c",
        "temp_min_absoluta_c",
        "precipitacao_acumulada_mm",
        "dias_com_alerta_chuva",
    ]
    print(gold.agg_metricas_regionais[cols_reg].to_string(index=False))

    print("\n--- TOP 5 CAPITAIS MAIS QUENTES NO PERÍODO ---")
    cols_cap = [
        "ranking_temperatura",
        "nome_capital",
        "sigla_uf",
        "regiao",
        "temp_media_periodo_c",
        "temp_max_periodo_c",
        "chuva_acumulada_mm",
    ]
    print(gold.agg_resumo_capitais[cols_cap].head(5).to_string(index=False))
    print("=" * 88 + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = clima_dw_etl_flow(offline=args.offline, skip_db=args.skip_db)
    print_executive_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
