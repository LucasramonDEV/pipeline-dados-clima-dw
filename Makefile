.PHONY: help install up down run run-offline test lint clean logs-db query-metrics

PYTHON ?= python3

help:
	@echo "Comandos disponíveis no Pipeline de Engenharia de Dados:"
	@echo "  make install        - Instala dependências Python no ambiente virtual"
	@echo "  make up             - Sobe PostgreSQL DW + Prefect Server + Executa Pipeline em Docker"
	@echo "  make down           - Para e remove os containers Docker"
	@echo "  make run            - Executa o pipeline localmente (API -> Pandas -> Postgres/Arquivos)"
	@echo "  make run-offline    - Executa o pipeline em modo offline determinístico"
	@echo "  make test           - Executa a suíte de testes unitários com Pytest"
	@echo "  make query-metrics  - Consulta as métricas agregadas diretamente no PostgreSQL via Docker"

install:
	$(PYTHON) -m pip install -r requirements.txt

up:
	docker compose up --build -d

down:
	docker compose down

run:
	$(PYTHON) -m src.main

run-offline:
	$(PYTHON) -m src.main --offline --skip-db

test:
	$(PYTHON) -m pytest -v

query-metrics:
	docker exec -it clima_postgres_dw psql -U dw_user -d clima_dw -c "SELECT regiao, qtd_capitais, temp_media_regional_c, precipitacao_acumulada_mm, dias_com_alerta_chuva FROM dw.agg_metricas_regionais ORDER BY temp_media_regional_c DESC;"
