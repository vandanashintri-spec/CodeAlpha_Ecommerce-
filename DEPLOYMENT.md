# Deployment

ByteCart is prepared for a Python WSGI host with PostgreSQL and HTTPS. It has not been deployed; choose a hosting provider and supply its database, domain, and email settings first.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

## Hosting setup

1. Push the project to a private or public Git repository and connect it to a host that supports Python, Gunicorn, PostgreSQL, and HTTPS.
2. Set these environment variables in the host's secret/settings panel:

   - `DJANGO_DEBUG=false`
   - `DJANGO_SECRET_KEY`: generate a unique value with `python -c "import secrets; print(secrets.token_urlsafe(64))"`
   - `DJANGO_ALLOWED_HOSTS`: your domain, without the scheme, for example `shop.example.com`
   - `DJANGO_CSRF_TRUSTED_ORIGINS`: your HTTPS origin, for example `https://shop.example.com`
   - `DATABASE_URL`: the PostgreSQL connection URL supplied by the host
   - `DJANGO_TRUST_PROXY_SSL_HEADER=true` only when the host terminates HTTPS at a trusted reverse proxy and strips client-supplied forwarded-protocol headers
3. Use `pip install -r requirements.txt` as the build command, then run `python manage.py collectstatic --noinput` and `python manage.py migrate` as the release/deploy commands.
4. Use the included `Procfile` (`gunicorn config.wsgi:application --workers 3 --access-logfile -`) as the web process.
5. Create the production administrator using the host's one-off command/console: `python manage.py createsuperuser`.
6. On a newly provisioned production database, load the included product catalog once with `python manage.py loaddata products.json`. Do not run this repeatedly on a populated database.
7. Configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `DEFAULT_FROM_EMAIL` if order-confirmation emails should be delivered. Without SMTP settings, local development writes email to the console.

## Current payment support

Checkout supports cash on delivery and records payment status. There is no online payment provider integration; that requires a provider account, keys, and webhook configuration before deployment.

The local SQLite database, local admin password, and local order records are deliberately not included in the product fixture. A production database starts with the catalog only; customers and orders created on the deployed site are stored there.
