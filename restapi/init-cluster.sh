#!/usr/bin/env bash
set -e

ls
alembic upgrade head
python -m app.init