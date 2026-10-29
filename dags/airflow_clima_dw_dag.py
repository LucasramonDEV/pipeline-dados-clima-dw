"""DAG Apache Airflow equivalente para orquestração diária do Data Warehouse Climático.

Este arquivo demonstra a portabilidade da arquitetura modular (`src/`) para ambientes
Apache Airflow 2.x utilizando a TaskFlow API (@dag / @task).
"""

from __future__ import annotations

from datetime import datetime, timedelta

try:
    from airflow.decorators import dag, task
except ImportError:
    # Permite importação/linting mesmo fora do container do Airflow
    def dag(*_args, **_kwargs):  # type: ignore[misc]
        def wrapper(func):
            return func

        return wrapper

    def task(*_args, **_kwargs):  # type: ignore[misc]
        def wrapper(func):
            return func

        return wrapper


default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="clima_capitais_brasileiras_dw",
    default_args=default_args,
    description="Pipeline ETL diário: Open-Meteo API -> Pandas Star Schema -> PostgreSQL DW",
    schedule="0 6 * * *",  # Executa diariamente às 06:00 UTC
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "star-schema", "postgresql", "open-meteo", "portfolio"],
)
def clima_capitais_dw_dag():
    """Define o grafo de execução (DAG) do pipeline dimensional no Apache Airflow."""

    @task(task_id="extract_open_meteo_bronze")
    def extract_task() -> str:
        from src.extract.open_meteo_extractor import OpenMeteoExtractor

        extractor = OpenMeteoExtractor()
        df_bronze = extractor.extract(offline=False, save_raw=True)
        return f"Extraídos {len(df_bronze)} registros na camada Bronze."

    @task(task_id="transform_star_schema_silver")
    def transform_task(_extract_status: str) -> str:
        import pandas as pd

        from src.config import DATA_RAW_DIR
        from src.transform.dimensional_transformer import DimensionalTransformer

        df_bronze = pd.read_csv(DATA_RAW_DIR / "weather_bronze_latest.csv")
        transformer = DimensionalTransformer()
        star = transformer.transform(df_bronze, save_processed=True)
        return f"Star Schema gerado com {len(star.fato_clima_diario)} registros na fato."

    @task(task_id="generate_gold_metrics_and_load_dw")
    def metrics_and_load_task(_transform_status: str) -> dict[str, int]:
        import pandas as pd

        from src.config import DATA_PROCESSED_DIR
        from src.load.postgres_loader import PostgresLoader
        from src.metrics.metrics_generator import MetricsGenerator
        from src.transform.dimensional_transformer import StarSchemaTables

        star = StarSchemaTables(
            dim_localidade=pd.read_parquet(DATA_PROCESSED_DIR / "dim_localidade.parquet"),
            dim_calendario=pd.read_parquet(DATA_PROCESSED_DIR / "dim_calendario.parquet"),
            dim_condicao_climatica=pd.read_parquet(
                DATA_PROCESSED_DIR / "dim_condicao_climatica.parquet"
            ),
            fato_clima_diario=pd.read_parquet(DATA_PROCESSED_DIR / "fato_clima_diario.parquet"),
        )
        gold = MetricsGenerator().generate_all(star, save_gold=True)
        loader = PostgresLoader()
        return loader.load_all(star=star, gold=gold)

    extracted = extract_task()
    transformed = transform_task(extracted)
    metrics_and_load_task(transformed)


dag_instance = clima_capitais_dw_dag()
