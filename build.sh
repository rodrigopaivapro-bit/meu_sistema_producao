#!/usr/bin/env bash
# O comando abaixo faz o script parar se algum comando falhar
set -o errexit

# 1. Instala todas as dependências do Python listadas no requirements.txt
pip install -r requirements.txt

# 2. Coleta todos os arquivos estáticos (CSS, JS, imagens) para uma única pasta
python manage.py collectstatic --no-input

# 3. Aplica as migrações do banco de dados para criar as tabelas
python manage.py migrate
```

### O porquê das coisas:

* **`pip install -r requirements.txt`**: Instala todas as bibliotecas que seu projeto precisa (Django, Gunicorn, Decouple, etc.) no ambiente do Render.
* **`python manage.py collectstatic --no-input`**: Em produção, o Django não serve os arquivos estáticos. Este comando copia todos os seus arquivos de CSS, imagens e JavaScript para a pasta `staticfiles`, de onde um serviço especializado (o Whitenoise, que já configuramos) irá servi-los de forma muito mais eficiente. `--no-input` apenas confirma "sim" para qualquer pergunta.
* **`python manage.py migrate`**: Executa as migrações para criar a estrutura de tabelas no seu novo banco de dados PostgreSQL do Render.

### Passo 2: Enviar o Novo Arquivo para o GitHub

Agora que o arquivo foi criado, precisamos adicioná-lo ao seu histórico do Git e enviá-lo para o GitHub, para que o Render possa encontrá-lo.

1.  Abra o seu terminal e navegue até a pasta raiz do seu projeto.
2.  Execute o seguinte comando para adicionar o arquivo `build.sh` à "área de preparação" do Git:
    ```bash
    git add build.sh
    ```

3.  Crie um novo *commit* (uma "fotografia" da alteração) com uma mensagem clara:
    ```bash
    git commit -m "Adiciona script de build para o Render"
    ```

4.  Envie este novo commit para o seu repositório no GitHub:
    ```bash
    git push origin main
