"""Camada de Carga (Load) - Persistência idempotente (Upsert) no PostgreSQL Data Warehouse."""

from src.load.postgres_loader import PostgresLoader

__all__ = ["PostgresLoader"]
