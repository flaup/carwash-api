# Используем Alpine-based образ Python
FROM python:3.9-alpine

# Устанавливаем рабочий каталог
WORKDIR /app

# Устанавливаем зависимости для psycopg2 и компиляторы
RUN apk add --no-cache gcc python3-dev musl-dev postgresql-dev

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Удаляем ненужные компиляторы после установки
RUN apk del gcc python3-dev musl-dev

# Копируем остальные файлы проекта
COPY . .

# Команда для запуска приложения
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]