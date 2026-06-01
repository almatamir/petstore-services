FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads

ENV PORT=8000
ENV STORE_ID=1
ENV MONGO_URI="mongodb://mongodb:27017"
ENV DB_NAME="petstore"

EXPOSE 8000

CMD ["python", "pets.py"]
