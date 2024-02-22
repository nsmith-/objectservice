#!/usr/bin/env bash
set -e

alembic upgrade head
python -m app.init
