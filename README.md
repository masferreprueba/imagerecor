# Mas Ferre — Procesador automático de imágenes

Aplicación web completa para recibir un ZIP de fotografías de producto, eliminar sus fondos mediante IA y generar automáticamente salidas de **500 × 500 px** y **4000 × 4000 px**. Los PNG de 4000 × 4000 también se guardan en Google Drive.

## Qué incluye

- Interfaz responsive en Next.js con drag & drop, estados, progreso, vistas previas y descarga.
- API en FastAPI con validación segura de ZIP, límites de carga y protección frente a *ZIP Slip* y bombas de compresión.
- Proveedores externos intercambiables: PhotoRoom, Remove.bg, Poof.bg y Claid.
- Recorte por canal alfa, escala proporcional, centrado y margen uniforme con Pillow.
- En cada ZIP, salida adicional en PNG transparente de 4000 × 4000 px con guardado automático en Google Drive.
- Acabado de estudio gratuito en JPEG 1500 × 1500, con fondo neutro, sombra natural y ajustes conservadores de luz, color y nitidez.
- Procesamiento concurrente y cola distribuida Celery + Redis para producción.
- PostgreSQL opcional para historial y SQLite como modo sencillo de desarrollo.
- Limpieza automática de archivos temporales.
- Contenedores para frontend, API, worker, Redis y PostgreSQL.

## Inicio rápido con Docker

1. Copia las variables de ejemplo:

   ```bash
   cp .env.example .env
   ```

2. Abre `.env`, pega la llave del proveedor elegido en `IMAGE_API_KEY` y cambia la contraseña de PostgreSQL tanto en `DATABASE_URL` como en `docker-compose.yml`.

3. Inicia la aplicación:

   ```bash
   docker compose up --build
   ```

4. Abre `http://localhost:3000`. La documentación interactiva de la API queda en `http://localhost:8000/docs`.

## Desarrollo sin Docker

Instalación automatizada:

```bash
chmod +x scripts/bootstrap-local.sh
./scripts/bootstrap-local.sh
```

Frontend:

```bash
npm ci
cp .env.example .env.local
npm run dev
```

Backend, usando SQLite y la cola interna:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
export PYTHONPATH=backend
export TASK_QUEUE=inline
export DATABASE_URL=sqlite:///./data/app.db
export STORAGE_ROOT=./data/jobs
uvicorn app.main:app --reload --app-dir backend
```

## Variables principales

| Variable | Uso |
| --- | --- |
| `IMAGE_API_PROVIDER` | `claid`, `photoroom` o `removebg` |
| `IMAGE_API_KEY` | Llave privada del proveedor |
| `NEXT_PUBLIC_API_URL` | URL pública de FastAPI |
| `OUTPUT_SIZE` | Lado del PNG final; por defecto 500 |
| `OBJECT_MARGIN_PERCENT` | Margen por lado; por defecto 10 |
| `PROCESSING_CONCURRENCY` | Imágenes simultáneas por worker |
| `TEMP_TTL_HOURS` | Tiempo de conservación del ZIP final |
| `TASK_QUEUE` | `inline` para desarrollo o `celery` para producción |
| `DATABASE_URL` | Conexión SQLite o PostgreSQL |
| `GOOGLE_DRIVE_ENABLED` | Activa la carga de los PNG 4000 × 4000 |
| `GOOGLE_DRIVE_FOLDER_ID` | Carpeta principal donde se crea una subcarpeta por ZIP |
| `GOOGLE_DRIVE_OAUTH_CLIENT_ID` | ID del cliente OAuth de la cuenta propietaria |
| `GOOGLE_DRIVE_OAUTH_CLIENT_SECRET` | Secreto del cliente OAuth; sólo debe guardarse en Render |
| `GOOGLE_DRIVE_OAUTH_REFRESH_TOKEN` | Token de actualización de la cuenta propietaria; sólo debe guardarse en Render |

## API

- `POST /api/jobs`: recibe `multipart/form-data` con `file`; el modo estándar genera automáticamente ambos tamaños. `output_mode=png_4000` se conserva por compatibilidad.
- `GET /api/jobs/{id}`: devuelve estado, progreso, conteos y vistas previas.
- `GET /api/jobs/{id}/download`: descarga el ZIP terminado.
- `GET /api/jobs/{id}/download/png-4000`: descarga el ZIP de PNG transparentes de 4000 × 4000.
- `GET /api/jobs/{id}/download/studio`: descarga el ZIP de fotografías con acabado de estudio.
- `GET /health`: verificación de disponibilidad.

## Proveedores

La integración está desacoplada en `backend/app/services/`. PhotoRoom, Remove.bg, Poof.bg y Claid se prueban con las llaves activas configuradas, sin cargar modelos de IA en el servidor. Para agregar otro proveedor, implementa `BackgroundRemovalProvider` y regístralo en `factory.py`.

## Despliegue

### Frontend en Vercel

1. Importa el repositorio.
2. Configura `NEXT_PUBLIC_API_URL=https://api.tudominio.com`.
3. Despliega con el preset Next.js.

> `NEXT_PUBLIC_API_URL` es una variable pública de compilación. Debe apuntar a una URL HTTPS accesible desde el navegador; no uses `localhost` en una versión publicada.

### Backend en Railway, Render o DigitalOcean

1. Construye con `backend/Dockerfile`.
2. Añade PostgreSQL, Redis y un almacenamiento persistente montado en `/app/data`.
3. Ejecuta la API con el comando incluido en el Dockerfile.
4. Ejecuta un segundo servicio worker con:

   ```bash
   celery -A app.workers.celery_app.celery_app worker --loglevel=INFO --concurrency=4
   ```

5. Define todas las variables de `.env.example`, agrega el dominio del frontend a `CORS_ORIGINS` y nunca publiques `IMAGE_API_KEY`.

### AWS o Cloudflare R2

Para grandes volúmenes, sustituye el volumen local por S3/R2: guarda el ZIP de entrada y salida en almacenamiento de objetos, conserva solo las claves en PostgreSQL y genera enlaces firmados con vencimiento. La capa de trabajo ya concentra las rutas de archivos, por lo que el cambio no afecta al frontend ni a los proveedores de IA.

## Escalamiento previsto

La tabla de trabajos ya admite `user_id`; esto permite sumar autenticación e historial. La separación entre API, cola, worker, base de datos y proveedor facilita añadir créditos, cobros, una API pública e integraciones con Shopify, WooCommerce o Mercado Libre sin reescribir el procesador de imágenes.

## Seguridad operativa

- No cargues `.env` al repositorio.
- Usa un bucket privado y enlaces firmados en producción.
- Reduce `MAX_UPLOAD_MB` si el servidor tiene poca memoria o disco.
- Coloca la API detrás de HTTPS, un proxy con límite de petición y rate limiting.
- Rota la llave del proveedor si se expone.
- No publiques las credenciales OAuth de Google Drive ni las incluyas en GitHub.
