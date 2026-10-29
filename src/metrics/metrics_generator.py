"""Cálculo de métricas agregadas (Camada Gold / Data Marts) via Pandas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import DATA_GOLD_DIR, configure_logging
from src.transform.dimensional_transformer import StarSchemaTables

logger = configure_logging("metrics")


@dataclass
class GoldMetrics:
    """Contêiner com os DataFrames agregados da camada Gold."""

    agg_metricas_regionais: pd.DataFrame
    agg_resumo_capitais: pd.DataFrame


class MetricsGenerator:
    """Gera agregações analíticas regionais e por capital a partir do Star Schema."""

    @staticmethod
    def compute_regional_metrics(star: StarSchemaTables) -> pd.DataFrame:
        """Agrega indicadores climáticos pelas 5 macrorregiões do Brasil."""
        merged = star.fato_clima_diario.merge(
            star.dim_localidade[["sk_localidade", "regiao"]],
            on="sk_localidade",
            how="inner",
        )

        grouped = (
            merged.groupby("regiao", as_index=False)
            .agg(
                qtd_capitais=("sk_localidade", "nunique"),
                total_observacoes=("sk_tempo", "count"),
                temp_media_regional_c=("temp_media_c", "mean"),
                temp_max_absoluta_c=("temp_max_c", "max"),
                temp_min_absoluta_c=("temp_min_c", "min"),
                amplitude_termica_media_c=("amplitude_termica_c", "mean"),
                precipitacao_acumulada_mm=("precipitacao_total_mm", "sum"),
                precipitacao_media_diaria_mm=("precipitacao_total_mm", "mean"),
                vento_max_registrado_kmh=("velocidade_vento_max_kmh", "max"),
                indice_uv_medio=("indice_uv_max", "mean"),
                dias_com_alerta_chuva=("alerta_chuva_intensa", "sum"),
                dias_com_alerta_calor=("alerta_calor_extremo", "sum"),
            )
            .sort_values("temp_media_regional_c", ascending=False)
            .reset_index(drop=True)
        )

        round_cols = [
            "temp_media_regional_c",
            "temp_max_absoluta_c",
            "temp_min_absoluta_c",
            "amplitude_termica_media_c",
            "precipitacao_acumulada_mm",
            "precipitacao_media_diaria_mm",
            "vento_max_registrado_kmh",
            "indice_uv_medio",
        ]
        grouped[round_cols] = grouped[round_cols].round(2)
        grouped["dias_com_alerta_chuva"] = grouped["dias_com_alerta_chuva"].astype(int)
        grouped["dias_com_alerta_calor"] = grouped["dias_com_alerta_calor"].astype(int)
        grouped["atualizado_em"] = datetime.now(timezone.utc)

        return grouped

    @staticmethod
    def compute_capitals_summary(star: StarSchemaTables) -> pd.DataFrame:
        """Agrega indicadores climáticos e rankings por capital brasileira."""
        merged = star.fato_clima_diario.merge(
            star.dim_localidade[
                ["sk_localidade", "codigo_ibge", "nome_capital", "sigla_uf", "regiao"]
            ],
            on="sk_localidade",
            how="inner",
        )
        merged["teve_chuva"] = merged["precipitacao_total_mm"] >= 1.0

        capitals = (
            merged.groupby(
                ["codigo_ibge", "nome_capital", "sigla_uf", "regiao"], as_index=False
            )
            .agg(
                dias_analisados=("sk_tempo", "count"),
                temp_media_periodo_c=("temp_media_c", "mean"),
                temp_max_periodo_c=("temp_max_c", "max"),
                temp_min_periodo_c=("temp_min_c", "min"),
                amplitude_max_c=("amplitude_termica_c", "max"),
                chuva_acumulada_mm=("precipitacao_total_mm", "sum"),
                dias_chuvosos=("teve_chuva", "sum"),
                vento_max_kmh=("velocidade_vento_max_kmh", "max"),
                uv_max_registrado=("indice_uv_max", "max"),
            )
            .reset_index(drop=True)
        )

        capitals["pct_dias_chuvosos"] = (
            100.0 * capitals["dias_chuvosos"] / capitals["dias_analisados"]
        ).round(2)

        round_cols = [
            "temp_media_periodo_c",
            "temp_max_periodo_c",
            "temp_min_periodo_c",
            "amplitude_max_c",
            "chuva_acumulada_mm",
            "vento_max_kmh",
            "uv_max_registrado",
        ]
        capitals[round_cols] = capitals[round_cols].round(2)
        capitals["dias_chuvosos"] = capitals["dias_chuvosos"].astype(int)

        # Rankings analíticos (1 = capital mais quente / mais chuvosa)
        capitals["ranking_temperatura"] = (
            capitals["temp_media_periodo_c"]
            .rank(method="min", ascending=False)
            .astype(int)
        )
        capitals["ranking_precipitacao"] = (
            capitals["chuva_acumulada_mm"]
            .rank(method="min", ascending=False)
            .astype(int)
        )
        capitals["atualizado_em"] = datetime.now(timezone.utc)

        return capitals.sort_values("ranking_temperatura").reset_index(drop=True)

    def generate_all(
        self,
        star: StarSchemaTables,
        save_gold: bool = True,
        output_dir: Path = DATA_GOLD_DIR,
    ) -> GoldMetrics:
        """Calcula todas as tabelas agregadas Gold e gera relatório executivo."""
        agg_regiao = self.compute_regional_metrics(star)
        agg_capitais = self.compute_capitals_summary(star)
        gold = GoldMetrics(
            agg_metricas_regionais=agg_regiao,
            agg_resumo_capitais=agg_capitais,
        )

        if save_gold:
            self.save_gold_artifacts(gold, output_dir=output_dir)

        return gold

    @staticmethod
    def save_gold_artifacts(
        gold: GoldMetrics,
        output_dir: Path = DATA_GOLD_DIR,
    ) -> dict[str, Path]:
        """Salva tabelas Gold em CSV, Parquet e gera resumo executivo em Markdown."""
        output_dir.mkdir(parents=True, exist_ok=True)
        reg_csv = output_dir / "agg_metricas_regionais.csv"
        reg_parquet = output_dir / "agg_metricas_regionais.parquet"
        cap_csv = output_dir / "agg_resumo_capitais.csv"
        cap_parquet = output_dir / "agg_resumo_capitais.parquet"
        report_md = output_dir / "relatorio_executivo_metricas.md"

        gold.agg_metricas_regionais.to_csv(reg_csv, index=False, encoding="utf-8")
        gold.agg_metricas_regionais.to_parquet(reg_parquet, index=False)
        gold.agg_resumo_capitais.to_csv(cap_csv, index=False, encoding="utf-8")
        gold.agg_resumo_capitais.to_parquet(cap_parquet, index=False)

        hottest = gold.agg_resumo_capitais.iloc[0]
        rainiest = gold.agg_resumo_capitais.sort_values(
            "chuva_acumulada_mm", ascending=False
        ).iloc[0]

        reg_df_display = gold.agg_metricas_regionais.drop(columns=["atualizado_em"])
        cap_df_display = gold.agg_resumo_capitais.head(10).drop(columns=["atualizado_em"])
        try:
            reg_table_str = reg_df_display.to_markdown(index=False)
            cap_table_str = cap_df_display.to_markdown(index=False)
        except ImportError:
            reg_table_str = reg_df_display.to_string(index=False)
            cap_table_str = cap_df_display.to_string(index=False)

        md_lines = [
            "# Relatório Executivo - Inteligência Climática das Capitais Brasileiras",
            "",
            f"- **Gerado em (UTC):** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}`",
            f"- **Capital mais quente (média):** {hottest['nome_capital']}/{hottest['sigla_uf']} ({hottest['temp_media_periodo_c']} °C)",
            f"- **Capital com maior precipitação acumulada:** {rainiest['nome_capital']}/{rainiest['sigla_uf']} ({rainiest['chuva_acumulada_mm']} mm)",
            "",
            "## 1. Métricas Agregadas por Região",
            "",
            reg_table_str,
            "",
            "## 2. Top 10 Capitais por Temperatura Média",
            "",
            cap_table_str,
            "",
        ]
        report_md.write_text("\n".join(md_lines), encoding="utf-8")
        logger.info("Métricas agregadas (Camada Gold) salvas em: %s", output_dir)

        return {
            "agg_metricas_regionais": reg_parquet,
            "agg_resumo_capitais": cap_parquet,
            "report_md": report_md,
        }
