#!/bin/bash

(cd docs && python3 gen.py)

(cd blog && python3 _site/create.py)

npx prettier --end-of-line lf --write .
