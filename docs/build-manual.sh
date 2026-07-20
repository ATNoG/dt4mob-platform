#!/usr/bin/env bash

cd "$(dirname "$0")"

pandoc -o "$1".docx \
  --reference-doc=./template/manual.dotx \
  --template=./template/template.ooxml \
  --metadata-file="$1"/metadata.yaml \
  -t docx+native_numbering \
  --figure-caption-position=below \
  --table-caption-position=below \
  --lua-filter ./template/diagram.lua \
  --filter pandoc-crossref \
  "$1"/*.md
