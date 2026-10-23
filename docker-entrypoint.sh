#!/bin/sh
set -e
case "$1" in
  demo)
    [ -f data/demo.db ] || python seed_demo_data.py
    exec python start_demo.py
    ;;
  stellwerk)
    exec python app.py
    ;;
  *)
    exec "$@"
    ;;
esac
