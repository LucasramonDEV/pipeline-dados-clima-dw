"""Configurações centralizadas, catálogo geográfico das capitais brasileiras e códigos WMO."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
DATA_GOLD_DIR = BASE_DIR / "data" / "gold"
LOGS_DIR = BASE_DIR / "logs"
SQL_INIT_FILE = BASE_DIR / "sql" / "01_init_dw_schema.sql"

for directory in (DATA_RAW_DIR, DATA_PROCESSED_DIR, DATA_GOLD_DIR, LOGS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class DatabaseConfig:
    """Configurações de conexão com o Data Warehouse PostgreSQL."""

    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database: str = os.getenv("POSTGRES_DB", "clima_dw")
    user: str = os.getenv("POSTGRES_USER", "dw_user")
    password: str = os.getenv("POSTGRES_PASSWORD", "dw_password_2026")
    schema: str = os.getenv("POSTGRES_SCHEMA", "dw")

    @property
    def sqlalchemy_url(self) -> str:
        """Retorna a connection string compatível com SQLAlchemy 2.0 + psycopg2."""
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass(frozen=True)
class APIConfig:
    """Configurações de extração na API pública Open-Meteo."""

    base_url: str = os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast")
    past_days: int = int(os.getenv("PAST_DAYS", "14"))
    forecast_days: int = int(os.getenv("FORECAST_DAYS", "3"))
    timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    timezone: str = "America/Sao_Paulo"


def configure_logging(name: str = "pipeline_clima_dw") -> logging.Logger:
    """Configura logging estruturado em console e arquivo."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(getattr(logging, log_level, logging.INFO))
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        file_handler = logging.FileHandler(LOGS_DIR / "pipeline.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Catálogo oficial das 27 Capitais Brasileiras (com código IBGE, UF, Região e Coordenadas)
BRAZILIAN_CAPITALS: list[dict[str, Any]] = [
    {"sk_localidade": 1, "codigo_ibge": 1200401, "nome_capital": "Rio Branco", "sigla_uf": "AC", "nome_estado": "Acre", "regiao": "Norte", "latitude": -9.97499, "longitude": -67.8243, "altitude_metros": 153.0, "fuso_horario": "America/Rio_Branco"},
    {"sk_localidade": 2, "codigo_ibge": 2704302, "nome_capital": "Maceió", "sigla_uf": "AL", "nome_estado": "Alagoas", "regiao": "Nordeste", "latitude": -9.66599, "longitude": -35.7350, "altitude_metros": 16.0, "fuso_horario": "America/Maceio"},
    {"sk_localidade": 3, "codigo_ibge": 1600303, "nome_capital": "Macapá", "sigla_uf": "AP", "nome_estado": "Amapá", "regiao": "Norte", "latitude": 0.03493, "longitude": -51.0694, "altitude_metros": 14.0, "fuso_horario": "America/Belem"},
    {"sk_localidade": 4, "codigo_ibge": 1302603, "nome_capital": "Manaus", "sigla_uf": "AM", "nome_estado": "Amazonas", "regiao": "Norte", "latitude": -3.10194, "longitude": -60.0250, "altitude_metros": 92.0, "fuso_horario": "America/Manaus"},
    {"sk_localidade": 5, "codigo_ibge": 2927408, "nome_capital": "Salvador", "sigla_uf": "BA", "nome_estado": "Bahia", "regiao": "Nordeste", "latitude": -12.97111, "longitude": -38.5108, "altitude_metros": 8.0, "fuso_horario": "America/Bahia"},
    {"sk_localidade": 6, "codigo_ibge": 2304400, "nome_capital": "Fortaleza", "sigla_uf": "CE", "nome_estado": "Ceará", "regiao": "Nordeste", "latitude": -3.71722, "longitude": -38.5431, "altitude_metros": 21.0, "fuso_horario": "America/Fortaleza"},
    {"sk_localidade": 7, "codigo_ibge": 5300108, "nome_capital": "Brasília", "sigla_uf": "DF", "nome_estado": "Distrito Federal", "regiao": "Centro-Oeste", "latitude": -15.77972, "longitude": -47.9297, "altitude_metros": 1172.0, "fuso_horario": "America/Sao_Paulo"},
    {"sk_localidade": 8, "codigo_ibge": 3205309, "nome_capital": "Vitória", "sigla_uf": "ES", "nome_estado": "Espírito Santo", "regiao": "Sudeste", "latitude": -20.31944, "longitude": -40.3378, "altitude_metros": 12.0, "fuso_horario": "America/Sao_Paulo"},
    {"sk_localidade": 9, "codigo_ibge": 5208707, "nome_capital": "Goiânia", "sigla_uf": "GO", "nome_estado": "Goiás", "regiao": "Centro-Oeste", "latitude": -16.67861, "longitude": -49.2539, "altitude_metros": 749.0, "fuso_horario": "America/Sao_Paulo"},
    {"sk_localidade": 10, "codigo_ibge": 2111300, "nome_capital": "São Luís", "sigla_uf": "MA", "nome_estado": "Maranhão", "regiao": "Nordeste", "latitude": -2.52972, "longitude": -44.3028, "altitude_metros": 24.0, "fuso_horario": "America/Fortaleza"},
    {"sk_localidade": 11, "codigo_ibge": 5103403, "nome_capital": "Cuiabá", "sigla_uf": "MT", "nome_estado": "Mato Grosso", "regiao": "Centro-Oeste", "latitude": -15.59611, "longitude": -56.0967, "altitude_metros": 165.0, "fuso_horario": "America/Cuiaba"},
    {"sk_localidade": 12, "codigo_ibge": 5002704, "nome_capital": "Campo Grande", "sigla_uf": "MS", "nome_estado": "Mato Grosso do Sul", "regiao": "Centro-Oeste", "latitude": -20.44278, "longitude": -54.6464, "altitude_metros": 592.0, "fuso_horario": "America/Campo_Grande"},
    {"sk_localidade": 13, "codigo_ibge": 3106200, "nome_capital": "Belo Horizonte", "sigla_uf": "MG", "nome_estado": "Minas Gerais", "regiao": "Sudeste", "latitude": -19.92083, "longitude": -43.9378, "altitude_metros": 852.0, "fuso_horario": "America/Sao_Paulo"},
    {"sk_localidade": 14, "codigo_ibge": 1501402, "nome_capital": "Belém", "sigla_uf": "PA", "nome_estado": "Pará", "regiao": "Norte", "latitude": -1.45583, "longitude": -48.5044, "altitude_metros": 10.0, "fuso_horario": "America/Belem"},
    {"sk_localidade": 15, "codigo_ibge": 2507507, "nome_capital": "João Pessoa", "sigla_uf": "PB", "nome_estado": "Paraíba", "regiao": "Nordeste", "latitude": -7.11500, "longitude": -34.8631, "altitude_metros": 47.0, "fuso_horario": "America/Fortaleza"},
    {"sk_localidade": 16, "codigo_ibge": 4106902, "nome_capital": "Curitiba", "sigla_uf": "PR", "nome_estado": "Paraná", "regiao": "Sul", "latitude": -25.42778, "longitude": -49.2731, "altitude_metros": 934.0, "fuso_horario": "America/Sao_Paulo"},
    {"sk_localidade": 17, "codigo_ibge": 2611606, "nome_capital": "Recife", "sigla_uf": "PE", "nome_estado": "Pernambuco", "regiao": "Nordeste", "latitude": -8.05389, "longitude": -34.8811, "altitude_metros": 4.0, "fuso_horario": "America/Recife"},
    {"sk_localidade": 18, "codigo_ibge": 2211001, "nome_capital": "Teresina", "sigla_uf": "PI", "nome_estado": "Piauí", "regiao": "Nordeste", "latitude": -5.08917, "longitude": -42.8019, "altitude_metros": 72.0, "fuso_horario": "America/Fortaleza"},
    {"sk_localidade": 19, "codigo_ibge": 3304557, "nome_capital": "Rio de Janeiro", "sigla_uf": "RJ", "nome_estado": "Rio de Janeiro", "regiao": "Sudeste", "latitude": -22.90642, "longitude": -43.1822, "altitude_metros": 11.0, "fuso_horario": "America/Sao_Paulo"},
    {"sk_localidade": 20, "codigo_ibge": 2408102, "nome_capital": "Natal", "sigla_uf": "RN", "nome_estado": "Rio Grande do Norte", "regiao": "Nordeste", "latitude": -5.79500, "longitude": -35.2094, "altitude_metros": 30.0, "fuso_horario": "America/Fortaleza"},
    {"sk_localidade": 21, "codigo_ibge": 4314902, "nome_capital": "Porto Alegre", "sigla_uf": "RS", "nome_estado": "Rio Grande do Sul", "regiao": "Sul", "latitude": -30.03306, "longitude": -51.2300, "altitude_metros": 10.0, "fuso_horario": "America/Sao_Paulo"},
    {"sk_localidade": 22, "codigo_ibge": 1100205, "nome_capital": "Porto Velho", "sigla_uf": "RO", "nome_estado": "Rondônia", "regiao": "Norte", "latitude": -8.76194, "longitude": -63.9039, "altitude_metros": 85.0, "fuso_horario": "America/Porto_Velho"},
    {"sk_localidade": 23, "codigo_ibge": 1400100, "nome_capital": "Boa Vista", "sigla_uf": "RR", "nome_estado": "Roraima", "regiao": "Norte", "latitude": 2.81972, "longitude": -60.6733, "altitude_metros": 85.0, "fuso_horario": "America/Boa_Vista"},
    {"sk_localidade": 24, "codigo_ibge": 4205407, "nome_capital": "Florianópolis", "sigla_uf": "SC", "nome_estado": "Santa Catarina", "regiao": "Sul", "latitude": -27.59667, "longitude": -48.5492, "altitude_metros": 3.0, "fuso_horario": "America/Sao_Paulo"},
    {"sk_localidade": 25, "codigo_ibge": 3550308, "nome_capital": "São Paulo", "sigla_uf": "SP", "nome_estado": "São Paulo", "regiao": "Sudeste", "latitude": -23.54750, "longitude": -46.6361, "altitude_metros": 760.0, "fuso_horario": "America/Sao_Paulo"},
    {"sk_localidade": 26, "codigo_ibge": 2800308, "nome_capital": "Aracaju", "sigla_uf": "SE", "nome_estado": "Sergipe", "regiao": "Nordeste", "latitude": -10.91111, "longitude": -37.0717, "altitude_metros": 4.0, "fuso_horario": "America/Maceio"},
    {"sk_localidade": 27, "codigo_ibge": 1721000, "nome_capital": "Palmas", "sigla_uf": "TO", "nome_estado": "Tocantins", "regiao": "Norte", "latitude": -10.18444, "longitude": -48.3336, "altitude_metros": 260.0, "fuso_horario": "America/Araguaina"},
]

# Tabela oficial de interpretação de códigos meteorológicos WMO (World Meteorological Organization)
WMO_WEATHER_CODES: dict[int, dict[str, Any]] = {
    0: {"sk_condicao": 1, "descricao_clima": "Céu limpo", "grupo_climatico": "Céu Limpo", "nivel_severidade": "Baixo", "requer_alerta": False},
    1: {"sk_condicao": 2, "descricao_clima": "Predominantemente limpo", "grupo_climatico": "Céu Limpo", "nivel_severidade": "Baixo", "requer_alerta": False},
    2: {"sk_condicao": 3, "descricao_clima": "Parcialmente nublado", "grupo_climatico": "Nublado", "nivel_severidade": "Baixo", "requer_alerta": False},
    3: {"sk_condicao": 4, "descricao_clima": "Encoberto", "grupo_climatico": "Nublado", "nivel_severidade": "Baixo", "requer_alerta": False},
    45: {"sk_condicao": 5, "descricao_clima": "Nevoeiro", "grupo_climatico": "Nevoeiro", "nivel_severidade": "Moderado", "requer_alerta": False},
    48: {"sk_condicao": 6, "descricao_clima": "Nevoeiro com geada", "grupo_climatico": "Nevoeiro", "nivel_severidade": "Moderado", "requer_alerta": False},
    51: {"sk_condicao": 7, "descricao_clima": "Garoa leve", "grupo_climatico": "Garoa", "nivel_severidade": "Baixo", "requer_alerta": False},
    53: {"sk_condicao": 8, "descricao_clima": "Garoa moderada", "grupo_climatico": "Garoa", "nivel_severidade": "Baixo", "requer_alerta": False},
    55: {"sk_condicao": 9, "descricao_clima": "Garoa intensa", "grupo_climatico": "Garoa", "nivel_severidade": "Moderado", "requer_alerta": False},
    61: {"sk_condicao": 10, "descricao_clima": "Chuva fraca", "grupo_climatico": "Chuva", "nivel_severidade": "Baixo", "requer_alerta": False},
    63: {"sk_condicao": 11, "descricao_clima": "Chuva moderada", "grupo_climatico": "Chuva", "nivel_severidade": "Moderado", "requer_alerta": False},
    65: {"sk_condicao": 12, "descricao_clima": "Chuva forte", "grupo_climatico": "Chuva", "nivel_severidade": "Alto", "requer_alerta": True},
    71: {"sk_condicao": 13, "descricao_clima": "Queda de neve fraca", "grupo_climatico": "Neve/Frio", "nivel_severidade": "Moderado", "requer_alerta": True},
    80: {"sk_condicao": 14, "descricao_clima": "Pancadas de chuva leves", "grupo_climatico": "Pancadas de Chuva", "nivel_severidade": "Baixo", "requer_alerta": False},
    81: {"sk_condicao": 15, "descricao_clima": "Pancadas de chuva moderadas", "grupo_climatico": "Pancadas de Chuva", "nivel_severidade": "Moderado", "requer_alerta": False},
    82: {"sk_condicao": 16, "descricao_clima": "Pancadas de chuva violentas", "grupo_climatico": "Pancadas de Chuva", "nivel_severidade": "Alto", "requer_alerta": True},
    95: {"sk_condicao": 17, "descricao_clima": "Tempestade com trovoadas", "grupo_climatico": "Tempestade", "nivel_severidade": "Alto", "requer_alerta": True},
    96: {"sk_condicao": 18, "descricao_clima": "Tempestade com granizo leve", "grupo_climatico": "Tempestade", "nivel_severidade": "Extremo", "requer_alerta": True},
    99: {"sk_condicao": 19, "descricao_clima": "Tempestade severa com granizo", "grupo_climatico": "Tempestade", "nivel_severidade": "Extremo", "requer_alerta": True},
    999: {"sk_condicao": 20, "descricao_clima": "Condição não classificada", "grupo_climatico": "Outros", "nivel_severidade": "Baixo", "requer_alerta": False},
}
