#!/usr/bin/env bash
# Este script prepara a aplicação Django para o ambiente de produção no Render.

# O comando abaixo garante que o script pare imediatamente se algum comando falhar.
set -o errexit

# Passo 1: Instala todas as dependências do Python a partir do ficheiro requirements.txt.
pip install -r requirements.txt

# Passo 2: Coleta todos os ficheiros estáticos (CSS, JS, imagens) para uma única pasta.
# O Whitenoise usará esta pasta para servir os ficheiros de forma eficiente.
python manage.py collectstatic --no-input

# Passo 3: Aplica as migrações do banco de dados para criar ou atualizar as tabelas.
python manage.py migrate

python manage.py createsuperuser --noinput