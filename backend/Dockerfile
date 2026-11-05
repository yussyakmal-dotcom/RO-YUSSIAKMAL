# Build the React client; final image runs only Django on existing port 900.
FROM node:22-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-builder /frontend/dist/assets /app/ro_core/static/frontend/assets
COPY --from=frontend-builder /frontend/dist/index.html /app/ro_core/templates/store_app.html
EXPOSE 8000
