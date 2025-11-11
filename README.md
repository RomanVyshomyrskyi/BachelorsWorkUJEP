# Development Docker setup — simulate two networks

This repository contains `docker-compose.dev.yml`, a Compose configuration that simulates two isolated networks:

- prod_net — "production" simulation with MSSQL, MariaDB, MongoDB, a SQLite file, and a Superset instance built from the local `./Superset` repo.
- dev_net — a separate network with the same DB types and another Superset instance built from the same local repo (useful for comparing local/dev vs production-like environments).

Files added

- `docker-compose.dev.yml` — Compose file that builds Superset from `./Superset` and creates the DB services for both networks.

How it works (quick)

- Each network has services named with `_prod` or `_dev` suffixes. The Superset services are built from the local `./Superset` folder (they use the repository's `Dockerfile`).
- SQLite is represented by a tiny container that creates the DB file in a named volume; the superset containers mount the same named volume so they can use that file as the metadata DB.
- Ports are mapped on the host so both Superset instances can run simultaneously:
  - Production-like Superset: http://localhost:8088
  - Development Superset: http://localhost:8089

Default credentials and connection notes

- MSSQL (both): SA password set to `Your_strong_P@ssw0rd!` — change this before using in any real environment.
- MariaDB prod: root password `rootpass`; MariaDB dev: root password `devroot`.
- MongoDB no authentication in this compose (for dev/test only).

Connection examples (from Superset UI when adding new database connections):

- MariaDB (prod): mysql+pymysql://root:rootpass@mariadb_prod:3306/demo
- MariaDB (dev): mysql+pymysql://root:devroot@mariadb_dev:3306/demo
- MSSQL: mssql+pyodbc://sa:Your_strong_P@ssw0rd!@mssql_prod:1433/<YOUR_DB>?driver=ODBC+Driver+17+for+SQL+Server
  - Note: ODBC drivers may need to be available in the Superset image or use pymssql connector.
- MongoDB: mongodb://mongo_prod:27017
- SQLite metadata DB (already pointed to by the Superset containers): sqlite:////var/lib/superset/prod_superset.db or sqlite:////var/lib/superset/dev_superset.db

How to run

1. From the repository root (where `docker-compose.dev.yml` lives), build and start everything:

```powershell
docker-compose -f .\docker-compose.dev.yml up --build
```

2. Wait for images to build and services to warm up. Open the Dev Superset at http://localhost:8089 and the Prod-like Superset at http://localhost:8088.

Notes, assumptions, and limitations

- This is intended for local development only. The images and passwords are not production-secure.
- The Superset image is built from the `./Superset` directory in this workspace and uses the repo's `Dockerfile`. The repo's Dockerfile may expect additional build args or setup steps; if you run into build errors, consult the repo's `Dockerfile` and `INSTALL.md` in `./Superset` for prerequisites.
- MSSQL official images are large and may require platform compatibility and sufficient resources. If you do not need MSSQL locally, consider removing or replacing it with a lightweight substitute.
- Superset often requires initialization steps (e.g., `superset db upgrade`, `superset init`). If the image's entrypoint does not run these automatically, you can exec into the container and run them, or extend the Dockerfile to run them at startup.

Next steps (optional suggestions)

- Add an entrypoint script for `superset_dev` that runs `superset db upgrade` and `superset init` on first start.
- Add seeded sample data and example connections (SQLAlchemy URIs) as environment variables so Superset registers the example datasources automatically.
- If you want to use Postgres instead of SQLite for Superset metadata, add a Postgres service and point `SUPERSET_SQLALCHEMY_CONN` to it.

If you'd like, I can:

- Add an init script for Superset to auto-run migrations and create an admin user.
- Add example SQLAlchemy URIs and a small seed script that registers the DBs in Superset automatically.


