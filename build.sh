#!/bin/bash
pip install -r requirements.txt
alembic upgrade head 2>/dev/null || true
