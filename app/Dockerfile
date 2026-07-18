FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py db.py eduhelp.py eduhelp.json olimpiadas.py ./
COPY conteudo ./conteudo
COPY conteudo_olimpiadas ./conteudo_olimpiadas
COPY static ./static
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
