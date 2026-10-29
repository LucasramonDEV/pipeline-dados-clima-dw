"""Extrator resiliente da API Pública Open-Meteo para as 27 capitais brasileiras."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import (
    BRAZILIAN_CAPITALS,
    DATA_RAW_DIR,
    APIConfig,
    configure_logging,
)

logger = configure_logging("extractor")

DAILY_VARIABLES = [
    "weather_code",
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


class OpenMeteoExtractor:
    """Realiza extração de séries temporais meteorológicas da API pública Open-Meteo."""

    def __init__(
        self,
        api_config: APIConfig | None = None,
        capitals: list[dict[str, Any]] | None = None,
    ) -> None:
        self.api_config = api_config or APIConfig()
        self.capitals = capitals or BRAZILIAN_CAPITALS
        self.session = self._build_http_session()

    def _build_http_session(self) -> requests.Session:
        """Cria sessão HTTP com política de Retry e Exponential Backoff."""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.api_config.max_retries,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(
            {
                "User-Agent": "DataEngineeringPortfolio-ClimaDW/1.0",
                "Accept": "application/json",
            }
        )
        return session

    def fetch_city_weather(self, capital: dict[str, Any]) -> dict[str, Any]:
        """Consulta a API Open-Meteo para uma única capital brasileira."""
        params = {
            "latitude": capital["latitude"],
            "longitude": capital["longitude"],
            "daily": ",".join(DAILY_VARIABLES),
            "timezone": self.api_config.timezone,
            "past_days": self.api_config.past_days,
            "forecast_days": self.api_config.forecast_days,
        }
        response = self.session.get(
            self.api_config.base_url,
            params=params,
            timeout=self.api_config.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return {
            "capital_metadata": capital,
            "daily": payload.get("daily", {}),
            "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "open-meteo-api",
        }

    def fetch_batch_weather(self) -> list[dict[str, Any]]:
        """Consulta a API Open-Meteo em lote (batch) para todas as capitais."""
        latitudes = ",".join(str(c["latitude"]) for c in self.capitals)
        longitudes = ",".join(str(c["longitude"]) for c in self.capitals)
        params = {
            "latitude": latitudes,
            "longitude": longitudes,
            "daily": ",".join(DAILY_VARIABLES),
            "timezone": self.api_config.timezone,
            "past_days": self.api_config.past_days,
            "forecast_days": self.api_config.forecast_days,
        }

        logger.info(
            "Iniciando requisição HTTP em lote na API Open-Meteo para %d capitais...",
            len(self.capitals),
        )
        response = self.session.get(
            self.api_config.base_url,
            params=params,
            timeout=self.api_config.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        # Quando há apenas 1 coordenada a API retorna dict; para múltiplas retorna list
        items = payload if isinstance(payload, list) else [payload]
        extracted_at = datetime.now(timezone.utc).isoformat()

        raw_records: list[dict[str, Any]] = []
        for capital, item in zip(self.capitals, items):
            raw_records.append(
                {
                    "capital_metadata": capital,
                    "daily": item.get("daily", {}),
                    "extracted_at_utc": extracted_at,
                    "source": "open-meteo-api",
                }
            )
        logger.info("Extração via API concluída com sucesso (%d capitais).", len(raw_records))
        return raw_records

    def generate_fallback_records(self, days: int = 17) -> list[dict[str, Any]]:
        """Gera dados meteorológicos realistas caso o ambiente esteja sem acesso à internet (CI/Offline)."""
        logger.warning(
            "Modo de contingência (offline/fallback) ativado: gerando série climática para %d capitais.",
            len(self.capitals),
        )
        rng = np.random.default_rng(seed=42)
        base_date = datetime.now(timezone.utc).date() - timedelta(days=days - 3)
        dates = [(base_date + timedelta(days=i)).isoformat() for i in range(days)]
        extracted_at = datetime.now(timezone.utc).isoformat()

        regional_baselines = {
            "Norte": {"t_max": 33.5, "t_min": 24.0, "rain_prob": 0.65, "uv": 11.2},
            "Nordeste": {"t_max": 31.8, "t_min": 23.5, "rain_prob": 0.40, "uv": 11.5},
            "Centro-Oeste": {"t_max": 32.5, "t_min": 20.0, "rain_prob": 0.45, "uv": 10.8},
            "Sudeste": {"t_max": 28.0, "t_min": 18.0, "rain_prob": 0.45, "uv": 9.5},
            "Sul": {"t_max": 24.5, "t_min": 14.2, "rain_prob": 0.50, "uv": 8.2},
        }
        wmo_dry_codes = [0, 1, 2, 3]
        wmo_rain_codes = [51, 61, 63, 65, 80, 81, 95]

        records: list[dict[str, Any]] = []
        for capital in self.capitals:
            base = regional_baselines.get(
                capital["regiao"],
                {"t_max": 29.0, "t_min": 19.0, "rain_prob": 0.45, "uv": 9.5},
            )
            t_max = np.round(rng.normal(base["t_max"], 2.4, size=days), 1)
            t_min = np.round(
                np.minimum(t_max - 3.5, rng.normal(base["t_min"], 2.0, size=days)), 1
            )
            t_mean = np.round((t_max + t_min) / 2.0, 1)
            app_max = np.round(t_max + rng.normal(1.8, 0.8, size=days), 1)
            app_min = np.round(t_min + rng.normal(0.5, 0.6, size=days), 1)

            is_rainy = rng.random(size=days) < base["rain_prob"]
            precip_sum = np.where(
                is_rainy, np.round(rng.gamma(shape=2.0, scale=8.5, size=days), 1), 0.0
            )
            precip_hours = np.where(
                is_rainy, np.round(np.clip(precip_sum / 3.5, 1.0, 18.0), 1), 0.0
            )
            weather_codes = [
                int(rng.choice(wmo_rain_codes)) if rainy else int(rng.choice(wmo_dry_codes))
                for rainy in is_rainy
            ]
            wind_max = np.round(rng.uniform(10.0, 42.0, size=days), 1)
            wind_gusts = np.round(wind_max * rng.uniform(1.25, 1.65, size=days), 1)
            uv_max = np.round(np.clip(rng.normal(base["uv"], 1.4, size=days), 3.0, 14.0), 1)
            radiation = np.round(np.clip(uv_max * rng.uniform(1.8, 2.4, size=days), 8.0, 32.0), 2)

            records.append(
                {
                    "capital_metadata": capital,
                    "daily": {
                        "time": dates,
                        "weather_code": weather_codes,
                        "temperature_2m_max": t_max.tolist(),
                        "temperature_2m_min": t_min.tolist(),
                        "temperature_2m_mean": t_mean.tolist(),
                        "apparent_temperature_max": app_max.tolist(),
                        "apparent_temperature_min": app_min.tolist(),
                        "precipitation_sum": precip_sum.tolist(),
                        "precipitation_hours": precip_hours.tolist(),
                        "wind_speed_10m_max": wind_max.tolist(),
                        "wind_gusts_10m_max": wind_gusts.tolist(),
                        "uv_index_max": uv_max.tolist(),
                        "shortwave_radiation_sum": radiation.tolist(),
                    },
                    "extracted_at_utc": extracted_at,
                    "source": "synthetic-fallback",
                }
            )
        return records

    @staticmethod
    def flatten_to_dataframe(raw_records: list[dict[str, Any]]) -> pd.DataFrame:
        """Converte a lista de payloads JSON aninhados em um DataFrame tabular (Camada Bronze)."""
        rows: list[dict[str, Any]] = []
        for entry in raw_records:
            meta = entry["capital_metadata"]
            daily = entry.get("daily", {})
            dates = daily.get("time", [])
            num_days = len(dates)

            for idx in range(num_days):
                row: dict[str, Any] = {
                    "sk_localidade": meta["sk_localidade"],
                    "codigo_ibge": meta["codigo_ibge"],
                    "nome_capital": meta["nome_capital"],
                    "sigla_uf": meta["sigla_uf"],
                    "nome_estado": meta["nome_estado"],
                    "regiao": meta["regiao"],
                    "latitude": meta["latitude"],
                    "longitude": meta["longitude"],
                    "altitude_metros": meta["altitude_metros"],
                    "fuso_horario": meta["fuso_horario"],
                    "data_medicao": dates[idx],
                    "extracted_at_utc": entry["extracted_at_utc"],
                    "data_source": entry.get("source", "open-meteo-api"),
                }
                for var in DAILY_VARIABLES:
                    values = daily.get(var, [])
                    row[var] = values[idx] if idx < len(values) else None
                rows.append(row)

        df_bronze = pd.DataFrame(rows)
        logger.info(
            "DataFrame Bronze gerado com %d registros e %d colunas.",
            len(df_bronze),
            len(df_bronze.columns),
        )
        return df_bronze

    def extract(self, offline: bool = False, save_raw: bool = True) -> pd.DataFrame:
        """Executa o fluxo completo de extração (API com fallback seguro) e salva na camada Bronze."""
        if offline:
            raw_records = self.generate_fallback_records(
                days=self.api_config.past_days + self.api_config.forecast_days
            )
        else:
            try:
                raw_records = self.fetch_batch_weather()
            except requests.RequestException as exc:
                logger.warning(
                    "Falha na conexão com a API Open-Meteo (%s). Acionando fallback seguro.",
                    exc,
                )
                raw_records = self.generate_fallback_records(
                    days=self.api_config.past_days + self.api_config.forecast_days
                )

        df_bronze = self.flatten_to_dataframe(raw_records)

        if save_raw:
            self.save_bronze_artifacts(raw_records, df_bronze)

        return df_bronze

    @staticmethod
    def save_bronze_artifacts(
        raw_records: list[dict[str, Any]],
        df_bronze: pd.DataFrame,
        output_dir: Path = DATA_RAW_DIR,
    ) -> dict[str, Path]:
        """Persiste o JSON bruto e o CSV/Parquet da camada Bronze."""
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "weather_raw_latest.json"
        csv_path = output_dir / "weather_bronze_latest.csv"

        with open(json_path, "w", encoding="utf-8") as fp:
            json.dump(raw_records, fp, ensure_ascii=False, indent=2)

        df_bronze.to_csv(csv_path, index=False, encoding="utf-8")
        logger.info("Artefatos Bronze salvos em: %s e %s", json_path, csv_path)
        return {"json": json_path, "csv": csv_path}
