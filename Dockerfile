FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
EXPOSE 8080
# Set GEMINI_API_KEY and ADMIN_PASSWORD as environment variables on the host (not baked into the image).
CMD ["sh", "-c", "waitress-serve --host=0.0.0.0 --port=${PORT} app:app"]
