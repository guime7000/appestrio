#! /usr/bin/env bash

set -e
set -x

# SQLite needs no server to wait for. Create the tables if they don't exist yet.
python -c "from app.core.db import init_db; init_db()"
