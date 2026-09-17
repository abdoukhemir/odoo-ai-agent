FROM python:3.12-slim

WORKDIR /app
COPY . /app

# Install dependencies including email-validator
RUN pip install fastapi uvicorn "pydantic[email]"

EXPOSE 8001

CMD ["uvicorn", "mcp:app", "--host", "0.0.0.0", "--port", "8001"]
