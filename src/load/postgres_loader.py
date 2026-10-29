"""Carregador idempotente (UPSERT) para o Data Warehouse PostgreSQL via SQLAlchemy 2.0."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from src.config import SQL_INIT_FILE, DatabaseConfig, configure_logging
from src.metrics.metrics_generator import GoldMetrics
from src.transform.dimensional_transformer import StarSchemaTables

logger = configure_logging("loader")


class PostgresLoader:
    """Gerencia a inicialização do schema DW e carga idempotente no PostgreSQL."""

    def __init__(
        self,
        db_config: DatabaseConfig | None = None,
        engine: Engine | None = None,
    ) -> None:
        self.db_config = db_config or DatabaseConfig()
        self.engine = engine or create_engine(
            self.db_config.sqlalchemy_url,
            pool_pre_ping=True,
        )

    def check_connection(self) -> bool:
        """Testa se o banco PostgreSQL está acessível."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.warning("Banco PostgreSQL indisponível em %s:%s (%s)", self.db_config.host, self.db_config.port, exc)
            return False

    def initialize_schema(self, sql_file: Path = SQL_INIT_FILE) -> None:
        """Executa o script DDL para garantir que o schema `dw`, tabelas e views existam."""
        ddl_script = sql_file.read_text(encoding="utf-8")
        with self.engine.begin() as conn:
            conn.execute(text(ddl_script))
        logger.info("Schema '%s' e objetos DDL verificados/inicializados com sucesso.", self.db_config.schema)

    def upsert_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        conflict_columns: list[str],
    ) -> int:
        """Realiza UPSERT (INSERT ... ON CONFLICT DO UPDATE) em lote no PostgreSQL."""
        if df.empty:
            return 0

        metadata = MetaData(schema=self.db_config.schema)
        table = Table(table_name, metadata, autoload_with=self.engine)
        clean_df = df.where(pd.notnull(df), None)
        records: list[dict[str, Any]] = clean_df.to_dict(orient="records")

        with self.engine.begin() as conn:
            stmt = pg_insert(table).values(records)
            update_cols = {
                col.name: stmt.excluded[col.name]
                for col in table.columns
                if col.name not in conflict_columns and col.name != "id_fato"
            }
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns,
                set_=update_cols,
            )
            conn.execute(upsert_stmt)

        logger.info(
            "UPSERT concluído em %s.%s: %d registros processados.",
            self.db_config.schema,
            table_name,
            len(records),
        )
        return len(records)

    def load_all(self, star: StarSchemaTables, gold: GoldMetrics) -> dict[str, int]:
        """Inicializa o schema e carrega todas as tabelas Dimensão, Fato e Gold de forma idempotente."""
        self.initialize_schema()

        counts: dict[str, int] = {}
        counts["dim_localidade"] = self.upsert_dataframe(
            star.dim_localidade,
            table_name="dim_localidade",
            conflict_columns=["sk_localidade"],
        )
        counts["dim_calendario"] = self.upsert_dataframe(
            star.dim_calendario,
            table_name="dim_calendario",
            conflict_columns=["sk_tempo"],
        )
        counts["dim_condicao_climatica"] = self.upsert_dataframe(
            star.dim_condicao_climatica,
            table_name="dim_condicao_climatica",
            conflict_columns=["sk_condicao"],
        )
        counts["fato_clima_diario"] = self.upsert_dataframe(
            star.fato_clima_diario,
            table_name="fato_clima_diario",
            conflict_columns=["sk_localidade", "sk_tempo"],
        )
        counts["agg_metricas_regionais"] = self.upsert_dataframe(
            gold.agg_metricas_regionais,
            table_name="agg_metricas_regionais",
            conflict_columns=["regiao"],
        )
        counts["agg_resumo_capitais"] = self.upsert_dataframe(
            gold.agg_resumo_capitais,
            table_name="agg_resumo_capitais",
            conflict_columns=["codigo_ibge"],
        )

        logger.info("Carga completa no PostgreSQL Data Warehouse finalizada: %s", counts)
        return counts

    def fetch_dw_summary(self) -> dict[str, int]:
        """Retorna a contagem atual de registros em cada tabela do Data Warehouse."""
        tables = [
            "dim_localidade",
            "dim_calendario",
            "dim_condicao_climatica",
            "fato_clima_diario",
            "agg_metricas_regionais",
            "agg_resumo_capitais",
        ]
        summary: dict[str, int] = {}
        with self.engine.connect() as conn:
            for tbl in tables:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {self.db_config.schema}.{tbl}")
                )
                summary[tbl] = int(result.scalar_one())
        return summary
