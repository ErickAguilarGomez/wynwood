# Wynwood House

Aplicación de reservas con Django 5.2, Python 3.14, Bootstrap, PostgreSQL y Redis/Celery. La interfaz está disponible en español e inglés y los pagos son simulados.

- [Aplicación desplegada](https://wynwood-production-e22b.up.railway.app/)
- [Repositorio](https://github.com/ErickAguilarGomez/wynwood)

## Inicio local con Docker y PostgreSQL

Necesitas Docker Desktop con Docker Compose y OpenSSL. Desde la carpeta del proyecto:

```bash
cp .env.example .env
openssl rand -hex 32
openssl rand -hex 32
```

Copia el primer resultado en `DJANGO_SECRET_KEY` y el segundo en `POSTGRES_PASSWORD` dentro de `.env`. Conserva los demás valores locales de la plantilla y ejecuta:

```bash
docker compose up --build -d
docker compose logs -f web worker
```

Abre [localhost:8000](http://localhost:8000) cuando web termine de iniciar. El arranque instala las migraciones, recopila los estáticos y, con `DJANGO_DEBUG=True`, carga datos de ejemplo si aún no hay alojamientos. El worker procesa los correos; por defecto se muestran en sus logs, sin necesitar cuentas externas. Las imágenes se guardan en el volumen local `media`.

Comprueba que la aplicación y la base de datos responden:

```bash
curl --fail http://localhost:8000/health/ready/
```

Debe devolver `{"status": "ok"}`. PostgreSQL y Redis se ejecutan dentro de Docker y no necesitan instalarse ni publicar puertos en tu máquina.

## Administración y datos de ejemplo

```bash
docker compose exec web python manage.py createsuperuser
```

Entra en [localhost:8000/admin/](http://localhost:8000/admin/) para administrar países, destinos, aeropuertos, alojamientos, imágenes, comodidades y servicios con sus precios y textos bilingües.

Para cargar los datos de ejemplo manualmente:

```bash
docker compose exec web python manage.py seed_demo
```

El comando carga países e impuestos, destinos, aeropuertos, comodidades, alojamientos, imágenes y servicios con sus tarifas. Se puede repetir sin duplicar datos; conserva los cambios administrativos de países y servicios y completa los registros faltantes. Con `DJANGO_DEBUG=False`, ejecútalo después de migrar una base vacía.

`make seed` también renueva las imágenes de ejemplo. Con Cloudinary actualiza sus referencias sin borrar los originales remotos. Cada imagen subida se valida, convierte a WebP y reduce a un máximo de 1200 × 1200 px conservando sus proporciones. El seeder carga datos; Resend y Cloudinary requieren las variables de sus respectivas cuentas.

### Reiniciar una base PostgreSQL existente

Las migraciones iniciales consolidadas requieren una base nueva. Si ya instalaste una versión anterior y puedes descartar sus datos, despliega primero el código actualizado y detén temporalmente el worker. En la consola del servicio web ejecuta:

```bash
celery -A config purge -f
python manage.py reset_database --yes
python manage.py createsuperuser
```

El comando elimina todos los datos del esquema `public` de la base configurada, aplica las migraciones y carga los datos de ejemplo. Si una migración o el seeder falla, PostgreSQL revierte el cambio completo. Los archivos de imágenes no se borran. Reactiva el worker al terminar. Ejecuta este reinicio una sola vez; en los siguientes despliegues usa el arranque normal.

## Alternativa local con SQLite

También puedes usar SQLite para desarrollo local. Necesitas Python 3.14 y las dependencias del proyecto:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=sqlite:///db.sqlite3
export DJANGO_SECRET_KEY=$(openssl rand -hex 32)
export DJANGO_DEBUG=True
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
export DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000
export DJANGO_SECURE_SSL_REDIRECT=False
export EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

La base `db.sqlite3` se crea en el proyecto. Las variables se leen del entorno del proceso; Django no carga `.env` automáticamente fuera de Docker. Si cambias traducciones, instala GNU gettext y ejecuta `python manage.py compilemessages`.

Para procesar correos usando SQLite, instala Redis e inícialo con `redis-server`. En otra terminal con el mismo entorno virtual y las mismas variables, ejecuta:

```bash
export REDIS_URL=redis://localhost:6379/0
celery -A config worker --loglevel=INFO
```

PostgreSQL impide reservas solapadas mediante una restricción de exclusión; SQLite utiliza triggers. SQLite serializa las escrituras y se limita al desarrollo local de una sola instancia. Usa PostgreSQL para producción y para la suite principal de pruebas.

## Probar una reserva

Busca un alojamiento, selecciona fechas futuras y huéspedes, completa el registro y configura los servicios que agregues. En el pago usa vencimiento futuro y CVV `123`:

| Tarjeta | Resultado |
| --- | --- |
| `4242 4242 4242 4242` | Aprueba y confirma la reserva |
| `4000 0000 0000 0002` | Rechaza y permite reintentar durante la retención |

Las retenciones duran 20 minutos. Solo un pago aprobado confirma la reserva y encola su correo. No se realizan cargos reales ni se almacenan los datos de tarjeta.

## Verificaciones

Con Docker en marcha:

```bash
make test
make check
```

Para ejecutar Ruff en tu máquina:

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
make lint
```

`make test` usa una base PostgreSQL de pruebas separada; `make check` revisa la configuración de despliegue.

## Producción y servicios opcionales

En Railway despliega el mismo repositorio como servicio web (`APP_ROLE=web`) y worker (`APP_ROLE=worker`), compartiendo PostgreSQL, Redis y las variables de correo y Cloudinary. Configura `DJANGO_DEBUG=False`, una clave propia en `DJANGO_SECRET_KEY`, `APP_ENV=production`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_SSL_REDIRECT=True` y `PUBLIC_BASE_URL` con el origen público HTTPS. Usa `/health/ready/` como health check. Railway proporciona `PORT`.

- **PostgreSQL y Redis:** asigna `DATABASE_URL` y `REDIS_URL` a las referencias de esos servicios. Fuera de Railway, PostgreSQL también acepta las variables `POSTGRES_*` de la plantilla.
- **Resend:** en web y worker, configura `EMAIL_BACKEND=bookings.email_backends.ResendEmailBackend`, `RESEND_API_KEY`, `EMAIL_FROM_EMAIL` con una dirección de tu dominio verificado y `EMAIL_FROM_NAME`.
- **Cloudinary:** para medios persistentes en Railway, configura `USE_CLOUDINARY=True`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY` y `CLOUDINARY_API_SECRET` en ambos servicios. Las URLs entregan WebP de hasta 1200 px. Con almacenamiento local y `DEBUG=False`, el servidor de despliegue debe servir `/media/` desde un volumen persistente.
- **GlitchTip:** es opcional; asigna `GLITCHTIP_DSN` para reportar excepciones. Para el stack local configura sus secretos en `.env` y ejecuta `make observability`.

Las claves de `.env.example` son marcadores. Reemplázalas por credenciales propias cuando actives un proveedor; el inicio local no requiere Resend ni Cloudinary. Los cambios de traducciones se compilan al construir la imagen Docker.

## Detener el proyecto

```bash
docker compose down
```

Este comando conserva las bases de datos y los archivos subidos en sus volúmenes.
