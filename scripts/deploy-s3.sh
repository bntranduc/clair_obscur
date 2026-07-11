#!/usr/bin/env bash
# Alias — préférer deploy-infra.sh
exec "$(dirname "$0")/deploy-infra.sh" "$@"
