#!/bin/bash
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu
exec /usr/local/bin/libcamera-vid "$@"