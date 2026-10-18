# Wynwood House

## Requisitos

- Docker Desktop con Docker Compose
- OpenSSL para generar los secretos

## Configuración

Desde la carpeta del proyecto, copia la plantilla de variables:

```bash
cp .env.example .env
```

En `.env`, configura estos valores para el entorno local:

```dotenv
DJANGO_SECRET_KEY=pega-aqui-un-secreto-aleatorio
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000
DJANGO_SECURE_SSL_REDIRECT=False

POSTGRES_DB=wynwood
POSTGRES_USER=wynwood
POSTGRES_PASSWORD=pega-aqui-una-contrasena-segura
POSTGRES_HOST=db
POSTGRES_PORT=5432
DATABASE_SSLMODE=prefer

REDIS_URL=redis://redis:6379/0
```

Genera un valor distinto para `DJANGO_SECRET_KEY` y `POSTGRES_PASSWORD` ejecutando dos veces:

```bash
openssl rand -hex 32
```

`POSTGRES_PASSWORD` es obligatorio.

## Iniciar la aplicación

Construye la imagen e inicia los servicios:

```bash
docker compose up --build
```

Espera a que termine el inicio y abre [http://localhost:8000](http://localhost:8000). Para iniciar en segundo plano, usa `make up`. La aplicación migra la base de datos y recopila los archivos estáticos al arrancar. Con `DJANGO_DEBUG=True`, carga alojamientos e imágenes de demostración si la base de datos todavía no tiene alojamientos.

Para actualizar las imágenes de demostración:

```bash
make seed
```

## Verificar el proyecto
```bash
make test
make lint
make check
```

Para preparar Ruff:

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Pagos de demostración

El checkout simula el resultado del pago y no realiza cargos reales. Usa una fecha de vencimiento futura y el CVV `123`.

| Número de tarjeta | Resultado |
| --- | --- |
| `4242 4242 4242 4242` | Pago aprobado |
| `4000 0000 0000 0002` | Pago rechazado; se puede reintentar mientras la reserva siga vigente |

## Configuración opcional de `.env`
### Moneda, impuestos, puntos y enlaces de correo

```dotenv
BOOKING_CURRENCY=USD
BOOKING_TAX_RATE=0
WYNWOOD_POINTS_RATE=0.41
PUBLIC_BASE_URL=http://localhost:8000
```

`BOOKING_TAX_RATE` es la tasa de respaldo para países que no tienen una tasa específica configurada. `PUBLIC_BASE_URL` se usa para los enlaces incluidos en los correos.

### Envío de correos por SMTP

Reemplaza los valores vacíos por los datos de tu proveedor de correo:

```dotenv
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_TLS=True
SMTP_FROM_EMAIL=bookings@example.com
SMTP_FROM_NAME=Wynwood House
```


### Imágenes con Cloudinary

Completa las credenciales desde el panel de Cloudinary:

```dotenv
USE_CLOUDINARY=True
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

Si Cloudinary no está habilitado, los medios se guardan en el volumen local `media`.

### GlitchTip

Genera valores nuevos para `GLITCHTIP_SECRET_KEY` y `GLITCHTIP_DB_PASSWORD` con `openssl rand -hex 32`. Para recibir errores de la aplicación en GlitchTip, copia el DSN del proyecto en `GLITCHTIP_DSN`.

```dotenv
GLITCHTIP_DSN=
GLITCHTIP_TRACES_SAMPLE_RATE=1.0
GLITCHTIP_SECRET_KEY=
GLITCHTIP_DB_PASSWORD=
GLITCHTIP_DOMAIN=http://localhost:8080
GLITCHTIP_ALLOWED_HOSTS=localhost,127.0.0.1
GLITCHTIP_CSRF_TRUSTED_ORIGINS=http://localhost:8080
GLITCHTIP_ENABLE_REGISTRATION=True
GLITCHTIP_RETENTION_DAYS=30
APP_ENV=development
APP_RELEASE=local
```

Después ejecuta `make observability`. El panel queda disponible en [http://localhost:8080](http://localhost:8080).

### Nivel de registro

Para cambiar el detalle de los logs del sitio y del worker:

```dotenv
LOG_LEVEL=INFO
```

## Administración

Crea un usuario administrador:

```bash
docker compose exec web python manage.py createsuperuser
```

Abre el panel en [http://localhost:8000/admin/](http://localhost:8000/admin/).

## Detener el entorno

Detén los servicios y conserva los datos:

```bash
docker compose down
```

Para borrar también las bases de datos y los demás volúmenes:

```bash
docker compose down -v
```
