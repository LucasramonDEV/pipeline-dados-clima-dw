"""Transformação, limpeza via Pandas e construção do Star Schema (Fato e Dimensões)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    DATA_PROCESSED_DIR,
    WMO_WEATHER_CODES,
    configure_logging,
)

logger = configure_logging("transformer")

MESES_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

DIAS_SEMANA_PT = {
    0: "Segunda-feira",
    1: "Terça-feira",
    2: "Quarta-feira",
    3: "Quinta-feira",
    4: "Sexta-feira",
    5: "Sábado",
    6: "Domingo",
}


@dataclass
class StarSchemaTables:
    """Contêiner tipado com as tabelas Fato e Dimensões prontas para carga no Data Warehouse."""

    dim_localidade: pd.DataFrame
    dim_calendario: pd.DataFrame
    dim_condicao_climatica: pd.DataFrame
    fato_clima_diario: pd.DataFrame


class DimensionalTransformer:
    """Responsável pela limpeza de dados e modelagem dimensional (Star Schema)."""

    @staticmethod
    def get_southern_hemisphere_season(dt: date) -> str:
        """Retorna a estação do ano no Hemisfério Sul a partir de uma data."""
        month_day = (dt.month, dt.day)
        if month_day >= (12, 21) or month_day < (3, 20):
            return "Verão"
        if (3, 20) <= month_day < (6, 21):
            return "Outono"
        if (6, 21) <= month_day < (9, 23):
            return "Inverno"
        return "Primavera"

    @staticmethod
    def classify_uv_index(uv: float) -> str:
        """Classifica o Índice UV segundo o padrão da Organização Mundial da Saúde (OMS)."""
        if pd.isna(uv) or uv < 3.0:
            return "Baixo"
        if uv < 6.0:
            return "Moderado"
        if uv < 8.0:
            return "Alto"
        if uv < 11.0:
            return "Muito Alto"
        return "Extremo"

    def clean_bronze_dataframe(self, df_bronze: pd.DataFrame) -> pd.DataFrame:
        """Limpa, valida e enriquece o DataFrame bruto da camada Bronze."""
        if df_bronze.empty:
            raise ValueError("O DataFrame de entrada (Bronze) está vazio.")

        df = df_bronze.copy()

        # 1. Conversão numérica explícita antes da filtragem de nulos críticos
        numeric_cols = [
            "temperature_2m_max",
            "temperature_2m_min",
            "temperature_2m_mean",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "precipitation_sum",
            "precipitation_hours",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "uv_index_max",
            "shortwave_radiation_sum",
        ]
        for col in numeric_cols:
            if col not in df.columns:
                df[col] = np.nan
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # 2. Padronização de datas e remoção de duplicatas por (codigo_ibge, data_medicao)
        df["data_medicao"] = pd.to_datetime(df["data_medicao"], errors="coerce").dt.date
        df = df.dropna(
            subset=["codigo_ibge", "data_medicao", "temperature_2m_max", "temperature_2m_min"]
        )
        df = df.drop_duplicates(subset=["codigo_ibge", "data_medicao"], keep="last").reset_index(
            drop=True
        )

        # 3. Garantia de consistência física: temp_max >= temp_min
        swapped_mask = df["temperature_2m_max"] < df["temperature_2m_min"]
        if swapped_mask.any():
            df.loc[swapped_mask, ["temperature_2m_max", "temperature_2m_min"]] = df.loc[
                swapped_mask, ["temperature_2m_min", "temperature_2m_max"]
            ].to_numpy()

        # Imputação da temperatura média caso ausente na resposta da API
        df["temperature_2m_mean"] = df["temperature_2m_mean"].fillna(
            ((df["temperature_2m_max"] + df["temperature_2m_min"]) / 2.0).round(2)
        )
        df["apparent_temperature_max"] = df["apparent_temperature_max"].fillna(df["temperature_2m_max"])
        df["apparent_temperature_min"] = df["apparent_temperature_min"].fillna(df["temperature_2m_min"])

        # Valores não-negativos para chuva, vento, UV e radiação
        for non_neg_col in [
            "precipitation_sum",
            "precipitation_hours",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "uv_index_max",
            "shortwave_radiation_sum",
        ]:
            df[non_neg_col] = df[non_neg_col].fillna(0.0).clip(lower=0.0)

        # 4. Código meteorológico WMO padronizado
        df["weather_code"] = (
            pd.to_numeric(df["weather_code"], errors="coerce").fillna(999).astype(int)
        )
        df["weather_code"] = df["weather_code"].apply(
            lambda code: code if code in WMO_WEATHER_CODES else 999
        )

        # 5. Colunas derivadas e regras de negócio (Engenharia de Atributos)
        df["amplitude_termica_c"] = (df["temperature_2m_max"] - df["temperature_2m_min"]).round(2)
        df["classificacao_uv"] = df["uv_index_max"].apply(self.classify_uv_index)

        high_severity_codes = {
            code for code, info in WMO_WEATHER_CODES.items() if info["requer_alerta"]
        }
        df["alerta_chuva_intensa"] = (df["precipitation_sum"] >= 30.0) | (
            df["weather_code"].isin(high_severity_codes)
        )
        df["alerta_calor_extremo"] = df["temperature_2m_max"] >= 35.0

        logger.info("Limpeza Silver concluída: %d registros válidos processados.", len(df))
        return df

    def build_dim_localidade(self, df_clean: pd.DataFrame) -> pd.DataFrame:
        """Constrói a tabela de dimensão geográfica `dim_localidade`."""
        cols = [
            "sk_localidade",
            "codigo_ibge",
            "nome_capital",
            "sigla_uf",
            "nome_estado",
            "regiao",
            "latitude",
            "longitude",
            "altitude_metros",
            "fuso_horario",
        ]
        dim_loc = (
            df_clean[cols]
            .drop_duplicates(subset=["sk_localidade"])
            .sort_values("sk_localidade")
            .reset_index(drop=True)
        )
        return dim_loc

    def build_dim_calendario(self, df_clean: pd.DataFrame) -> pd.DataFrame:
        """Constrói a tabela de dimensão temporal `dim_calendario`."""
        unique_dates = sorted(df_clean["data_medicao"].unique())
        rows = []
        for dt in unique_dates:
            sk_tempo = int(dt.strftime("%Y%m%d"))
            weekday = dt.weekday()
            iso_week = int(dt.isocalendar()[1])
            quarter = ((dt.month - 1) // 3) + 1
            rows.append(
                {
                    "sk_tempo": sk_tempo,
                    "data_completa": dt,
                    "ano": dt.year,
                    "trimestre": quarter,
                    "mes": dt.month,
                    "nome_mes": MESES_PT[dt.month],
                    "dia": dt.day,
                    "dia_da_semana": weekday,
                    "nome_dia_semana": DIAS_SEMANA_PT[weekday],
                    "semana_do_ano": iso_week,
                    "eh_fim_de_semana": weekday >= 5,
                    "estacao_hemisferio_sul": self.get_southern_hemisphere_season(dt),
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def build_dim_condicao_climatica() -> pd.DataFrame:
        """Constrói a tabela de dimensão meteorológica `dim_condicao_climatica` (padrão WMO)."""
        rows = []
        for code, attrs in sorted(WMO_WEATHER_CODES.items(), key=lambda item: item[1]["sk_condicao"]):
            rows.append(
                {
                    "sk_condicao": attrs["sk_condicao"],
                    "codigo_wmo": code,
                    "descricao_clima": attrs["descricao_clima"],
                    "grupo_climatico": attrs["grupo_climatico"],
                    "nivel_severidade": attrs["nivel_severidade"],
                    "requer_alerta": attrs["requer_alerta"],
                }
            )
        return pd.DataFrame(rows)

    def build_fato_clima_diario(self, df_clean: pd.DataFrame) -> pd.DataFrame:
        """Constrói a tabela fato `fato_clima_diario` relacionando as chaves substitutas (SKs)."""
        wmo_to_sk = {code: info["sk_condicao"] for code, info in WMO_WEATHER_CODES.items()}

        fato = pd.DataFrame(
            {
                "sk_localidade": df_clean["sk_localidade"].astype(int),
                "sk_tempo": df_clean["data_medicao"].apply(lambda d: int(d.strftime("%Y%m%d"))),
                "sk_condicao": df_clean["weather_code"].map(wmo_to_sk).astype(int),
                "temp_max_c": df_clean["temperature_2m_max"].round(2),
                "temp_min_c": df_clean["temperature_2m_min"].round(2),
                "temp_media_c": df_clean["temperature_2m_mean"].round(2),
                "amplitude_termica_c": df_clean["amplitude_termica_c"].round(2),
                "sensacao_termica_max_c": df_clean["apparent_temperature_max"].round(2),
                "sensacao_termica_min_c": df_clean["apparent_temperature_min"].round(2),
                "precipitacao_total_mm": df_clean["precipitation_sum"].round(2),
                "horas_precipitacao": df_clean["precipitation_hours"].round(1),
                "velocidade_vento_max_kmh": df_clean["wind_speed_10m_max"].round(2),
                "rajada_vento_max_kmh": df_clean["wind_gusts_10m_max"].round(2),
                "indice_uv_max": df_clean["uv_index_max"].round(2),
                "radiacao_solar_mj_m2": df_clean["shortwave_radiation_sum"].round(2),
                "classificacao_uv": df_clean["classificacao_uv"],
                "alerta_chuva_intensa": df_clean["alerta_chuva_intensa"].astype(bool),
                "alerta_calor_extremo": df_clean["alerta_calor_extremo"].astype(bool),
                "data_extracao_utc": pd.to_datetime(df_clean["extracted_at_utc"], utc=True),
            }
        )
        return fato.sort_values(["sk_tempo", "sk_localidade"]).reset_index(drop=True)

    def transform(
        self,
        df_bronze: pd.DataFrame,
        save_processed: bool = True,
        output_dir: Path = DATA_PROCESSED_DIR,
    ) -> StarSchemaTables:
        """Executa todo o pipeline de transformação e retorna as tabelas do Star Schema."""
        df_clean = self.clean_bronze_dataframe(df_bronze)

        dim_localidade = self.build_dim_localidade(df_clean)
        dim_calendario = self.build_dim_calendario(df_clean)
        dim_condicao = self.build_dim_condicao_climatica()
        fato_clima = self.build_fato_clima_diario(df_clean)

        star_schema = StarSchemaTables(
            dim_localidade=dim_localidade,
            dim_calendario=dim_calendario,
            dim_condicao_climatica=dim_condicao,
            fato_clima_diario=fato_clima,
        )

        if save_processed:
            self.save_star_schema_files(star_schema, output_dir=output_dir)

        return star_schema

    @staticmethod
    def save_star_schema_files(
        star_schema: StarSchemaTables,
        output_dir: Path = DATA_PROCESSED_DIR,
    ) -> dict[str, Path]:
        """Persiste as tabelas Fato e Dimensões na camada Silver/Processed em CSV e Parquet."""
        output_dir.mkdir(parents=True, exist_ok=True)
        tables = {
            "dim_localidade": star_schema.dim_localidade,
            "dim_calendario": star_schema.dim_calendario,
            "dim_condicao_climatica": star_schema.dim_condicao_climatica,
            "fato_clima_diario": star_schema.fato_clima_diario,
        }
        saved_paths: dict[str, Path] = {}
        for name, df in tables.items():
            csv_path = output_dir / f"{name}.csv"
            parquet_path = output_dir / f"{name}.parquet"
            df.to_csv(csv_path, index=False, encoding="utf-8")
            df.to_parquet(parquet_path, index=False)
            saved_paths[name] = parquet_path

        logger.info("Tabelas dimensionais salvas em CSV e Parquet em: %s", output_dir)
        return saved_paths
