#!/bin/sh
ROOT_DIR=$(cd "$(dirname "$0")/..";pwd -P)
nohup "$ROOT_DIR/binary" --session-closed > /dev/null &
disown
