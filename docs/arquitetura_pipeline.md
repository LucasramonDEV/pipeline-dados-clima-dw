# Arquitetura do Pipeline de Engenharia de Dados

## Visão Geral (Arquitetura Medalhão + Data Warehouse)

O projeto combina o padrão **Medallion Architecture (Bronze → Silver → Gold)** em armazenamento colunar local (`Parquet`) com um **Data Warehouse Relacional (Star Schema)** no **PostgreSQL 16**, orquestrado via **Prefect 3** (e com DAG equivalente para **Apache Airflow 2.x**).

```mermaid
flowchart LR
    subgraph Fonte["1. Fonte Externa"]
        API["API Pública Open-Meteo<br/>(27 Capitais Brasileiras)"]
    end

    subgraph Orquestracao["2. Orquestrador (Docker)"]
        PREF["Prefect 3 Flow<br/>& Airflow DAG"]
    end

    subgraph Medallion["3. Processamento Python (Pandas)"]
        B["Camada Bronze<br/>JSON + CSV Bruto<br/>(data/raw)"]
        S["Camada Silver<br/>Limpeza, Tipagem e<br/>Star Schema Parquet<br/>(data/processed)"]
        G["Camada Gold<br/>Métricas Agregadas &<br/>Relatório Executivo<br/>(data/gold)"]
    end

    subgraph DW["4. Data Warehouse (Docker)"]
        PG[("PostgreSQL 16<br/>Schema: dw<br/>Fato + Dimensões + Views")]
    end

    API -->|"HTTP GET + Retry/Backoff"| B
    B -->|"Deduplicação & Regras"| S
    S -->|"Agregações Regionais"| G
    S -->|"UPSERT Idempotente"| PG
    G -->|"UPSERT Data Marts"| PG
    PREF -.->|"Orquestra Tasks"| B
    PREF -.->|"Orquestra Tasks"| S
    PREF -.->|"Orquestra Tasks"| G
    PREF -.->|"Orquestra Tasks"| PG
```

## Boas Práticas de Engenharia de Dados Implementadas

- **Resiliência na Extração:** Sessão HTTP com `Retry` e *Exponential Backoff* para lidar com instabilidades de rede e *rate limits* (`HTTP 429/5xx`), além de modo de contingência determinístico (`--offline`) para testes reproduzíveis em CI/CD.
- **Qualidade de Dados (Data Quality):** Validação física de temperaturas (`temp_max >= temp_min`), remoção de duplicidades na chave natural `(codigo_ibge, data_medicao)`, imputação de valores ausentes e bloqueio de valores negativos para grandezas absolutas (precipitação, vento, radiação UV).
- **Idempotência no Banco de Dados:** Uso de `INSERT ... ON CONFLICT DO UPDATE` (Upsert nativo do PostgreSQL via SQLAlchemy 2.0) em todas as tabelas de dimensão, fato e agregações. O pipeline pode ser executado $N$ vezes no mesmo dia sem gerar registros duplicados.
- **Armazenamento Colunar:** Persistência intermediária em formato **Apache Parquet** (`pyarrow`), garantindo compressão eficiente e preservação estrita de tipos de dados.
- **Testes Automatizados e CI/CD:** Suíte `pytest` cobrindo extração, transformação, integridade referencial do Star Schema (`FK -> PK`) e agregações Gold, integrada ao GitHub Actions com container de serviço PostgreSQL 16.
