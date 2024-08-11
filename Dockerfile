FROM python:3.12

WORKDIR /app

COPY pyproject.toml poetry.lock* /app/

RUN pip install poetry && poetry install --no-dev

COPY . /app/

# 安裝 PostgreSQL 客戶端，此段透過command看結果可以改為直接連進 postgresql的contianer 下 psql達到一樣的效果
#RUN apt-get update && apt-get install -y postgresql-client

CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]