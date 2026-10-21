FROM postgres:17.11-alpine

# Container clock + Postgres default timezone (initdb picks this up).
ENV TZ=Australia/Brisbane

# Scripts here run once, in filename order, only when the data volume is empty.
COPY init/ /docker-entrypoint-initdb.d/
