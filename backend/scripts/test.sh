#!/usr/bin/env bash

set -e
set -x

coverage run -m pytest app/tests/
coverage report
coverage html --title "${@-coverage}"
