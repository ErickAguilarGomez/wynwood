# Wynwood House

## Entrega

- Repositorio: [github.com/ErickAguilarGomez/wynwood](https://github.com/ErickAguilarGomez/wynwood)
- Aplicación: [wynwood-production-e22b.up.railway.app](https://wynwood-production-e22b.up.railway.app/)

## Requisitos

- Docker Desktop con Docker Compose
- OpenSSL para generar los secretos
- Git (solo para clonar el proyecto)

El proyecto usa PostgreSQL porque la base de datos aplica una restricción de exclusión para impedir reservas solapadas incluso ante solicitudes simultáneas. SQLite no soporta esa restricción; no se debe usar para ejecutar ni validar el flujo de reservas.

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

Para trabajar sin Docker, instala Python 3.14, crea un entorno virtual, instala `requirements.txt` y configura una instancia de PostgreSQL 17. Define `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` y `POSTGRES_PORT` (o `DATABASE_URL`), además de `DJANGO_SECRET_KEY`. Luego ejecuta `python manage.py migrate`, `python manage.py seed_demo` y `python manage.py runserver`. Redis y Celery son necesarios para procesar los correos de confirmación en segundo plano; el servidor puede iniciar sin ellos, pero el envío de tareas no funcionará.

Para actualizar las imágenes de demostración:

```bash
make seed
```

## Verificar el proyecto

`make test` usa PostgreSQL real y no SQLite. `make lint` revisa estilo y errores estáticos; `make check` ejecuta las comprobaciones de despliegue con `DEBUG=False` y redirección HTTPS activa.

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

### Envío de correos con Resend

Configura Resend en los servicios web y worker con una clave de API de envío y una dirección de un dominio verificado:

```dotenv
EMAIL_BACKEND=bookings.email_backends.ResendEmailBackend
RESEND_API_KEY=
EMAIL_FROM_EMAIL=reservas@erickaguilargomez.me
EMAIL_FROM_NAME=Wynwood House
```

El backend envía mediante HTTPS. `EMAIL_FROM_EMAIL` debe pertenecer a un dominio verificado en Resend.


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
