#!/bin/sh
set -eu

if [ "${APP_ROLE:-web}" = "worker" ]; then
    exec celery -A config worker --loglevel="${LOG_LEVEL:-INFO}" --concurrency="${CELERY_CONCURRENCY:-2}"
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput
case "${DJANGO_DEBUG:-True}" in
    [Tt][Rr][Uu][Ee]|1|[Yy][Ee][Ss]|[Oo][Nn])
        python manage.py seed_demo --if-empty
        ;;
esac
exec gunicorn config.wsgi:application --bind 0.0.0.0:"${PORT:-8000}" --workers="${WEB_CONCURRENCY:-2}" --threads="${WEB_THREADS:-2}" --timeout=45 --access-logfile=- --error-logfile=- --worker-tmp-dir=/tmp
