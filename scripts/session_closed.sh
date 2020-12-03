#!/bin/sh
ROOT_DIR=$(cd "$(dirname "$0")/..";pwd -P)
nohup "$ROOT_DIR/binary" --session-closed "$NVIM_LISTEN_ADDRESS" > /dev/null &
disown
