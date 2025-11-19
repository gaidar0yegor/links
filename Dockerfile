# Dockerfile

# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта в контейнер
COPY . .

# Команда для запуска бота
# Мы будем использовать Gunicorn/Supervisor для продакшена позже, но пока это просто команда запуска
# Используем команду, которая будет выполнена при запуске контейнера
CMD ["python", "main.py"]
