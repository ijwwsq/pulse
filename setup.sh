#!/bin/bash

# Создаем структуру папок
mkdir -p database app/templates app/static

# 1. Создаем файлы для Базы Данных
touch database/schema.sql      # Структура таблиц (Инженер БД)
touch database/seeds.sql       # Тестовые данные (Инженер БД)
touch database/views_procs.sql # Процедуры и вьюхи (Инженер БД)

# 2. Создаем файлы для Python-части
touch app/main.py             # Сервер FastAPI (Python Инженер)
touch app/database.py         # Подключение к БД (Общее)
touch app/templates/index.html # Главная страница (Python Инженер)

# 3. Создаем конфигурационные файлы
touch requirements.txt
touch .env
touch .gitignore
touch README.md

# Заполняем .gitignore, чтобы не пушить лишнее
cat <<EOT >> .gitignore
__pycache__/
*.py[cod]
*$py.class
.env
.venv
env/
venv/
.vscode/
.idea/
EOT

# Заполняем requirements.txt базовыми библиотеками
cat <<EOT >> requirements.txt
fastapi
uvicorn[standard]
psycopg[binary]
jinja2
sqladmin
python-dotenv
EOT

# Заполняем README.md базовой инфой
echo "# PULSE: Gym Management System 🍗" >> README.md
echo "Проект по дисциплине БД. Стек: FastAPI + PostgreSQL." >> README.md

echo "✅ Структура проекта Pulse успешно создана!"
