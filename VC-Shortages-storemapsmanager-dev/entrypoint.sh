#!/bin/bash

set -ex

exec gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:5000 --timeout 1800
