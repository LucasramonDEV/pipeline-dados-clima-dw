#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="${1:-pipeline-dados-clima-dw}"
DESCRIPTION="Pipeline ETL/ELT de Engenharia de Dados: API Pública Open-Meteo -> Python (Pandas) -> Modelagem Dimensional (Star Schema) -> PostgreSQL & Prefect/Airflow em Docker"

echo "======================================================================"
echo " 1. Preparando Ambiente Virtual Python (.venv) e Dependências"
echo "======================================================================"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

echo "======================================================================"
echo " 2. Executando Suíte de Testes Automatizados (Pytest)"
echo "======================================================================"
.venv/bin/pytest -v

echo "======================================================================"
echo " 3. Testando Execução do Pipeline ETL/ELT (Extração -> Silver -> Gold)"
echo "======================================================================"
.venv/bin/python -m src.main --skip-db

echo "======================================================================"
echo " 4. Inicializando Git e Realizando Commit"
echo "======================================================================"
if [ ! -d ".git" ]; then
    git init -b main
else
    git branch -M main
fi

git add .

if git diff --cached --quiet; then
    echo "Nenhuma alteração pendente para commit."
else
    git commit -m "$(cat <<'EOF'
feat: pipeline ETL/ELT climático com Star Schema, PostgreSQL e Prefect/Airflow

- Extração resiliente da API pública Open-Meteo para as 27 capitais brasileiras
- Limpeza, enriquecimento e modelagem dimensional (Star Schema) com Pandas
- Carga idempotente (UPSERT) no PostgreSQL 16 via SQLAlchemy 2.0
- Camada Gold com métricas agregadas por macrorregião e ranking de capitais
- Orquestração em Docker com Prefect 3 e DAG equivalente para Apache Airflow
- Suíte de testes automatizados (Pytest) e pipeline CI no GitHub Actions
EOF
)"
fi

echo "======================================================================"
echo " 5. Criando Repositório Público '${REPO_NAME}' no GitHub e Subindo"
echo "======================================================================"
if ! gh auth status >/dev/null 2>&1; then
    echo "Atenção: Você ainda não está autenticado no GitHub CLI (gh)."
    echo "Execute primeiro: gh auth login"
    exit 1
fi

if git remote get-url origin >/dev/null 2>&1; then
    git push -u origin main
else
    gh repo create "${REPO_NAME}" --public --description "${DESCRIPTION}" --source=. --remote=origin --push
fi

echo "======================================================================"
echo " SUCESSO! Projeto testado, validado e publicado no seu GitHub!"
echo "======================================================================"
