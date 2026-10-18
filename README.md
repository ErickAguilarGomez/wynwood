# Wynwood House

Aplicación Django para buscar alojamientos, crear reservas y completar pagos de demostración. Usa PostgreSQL, Redis y Celery.

## Iniciar el proyecto

Requisitos: Docker Desktop y Docker Compose.

```bash
cp .env.example .env
```

En `.env`, reemplaza `DJANGO_SECRET_KEY` y `POSTGRES_PASSWORD` por valores propios. Puedes generar secretos con `openssl rand -hex 32`.

```bash
docker compose up --build
```

La aplicación migra la base de datos y queda disponible en <http://localhost:8000>. Con `DJANGO_DEBUG=True`, el primer inicio carga alojamientos e imágenes demo automáticamente si el catálogo está vacío. Con `DJANGO_DEBUG=False` no se crean datos demo.

`seed_demo` se puede volver a ejecutar sin duplicar alojamientos. `make seed` actualiza las imágenes demo existentes.

## Pagos de demostración

El checkout es un simulador local y no realiza cargos. Usa una fecha futura y CVV `123`:

| Número | Resultado |
| --- | --- |
| `4242 4242 4242 4242` | Pago aprobado |
| `4000 0000 0000 0002` | Pago rechazado; permite reintentar mientras la reserva esté vigente |

No se guardan el número de tarjeta, vencimiento, CVV ni datos de facturación.

## Pruebas y calidad

```bash
make test
make lint
make check
```

Las pruebas usan PostgreSQL y se ejecutan en la imagen Docker del proyecto.

Para instalar Ruff en el entorno local y usar `make lint`:

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Opciones

- Los medios se guardan localmente por defecto. Cloudinary y Cloudflare R2 son opciones para almacenamiento remoto.
- Configura `SMTP_*` en `.env` para enviar correo real. Sin SMTP configurado, el resto de la aplicación funciona y el envío de confirmaciones no completa.
- GlitchTip es opcional. Configura sus variables en `.env` y ejecuta `make observability` para iniciar su stack separado.

## Administración

```bash
docker compose exec web python manage.py createsuperuser
```

Luego entra a <http://localhost:8000/admin/>. `docker compose down` detiene el entorno y conserva los datos; `docker compose down -v` también elimina las bases de datos y los volúmenes.
