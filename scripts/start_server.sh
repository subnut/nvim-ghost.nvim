#!/bin/sh
ROOT_DIR=$(cd "$(dirname "$0")/..";pwd -P)
nohup "$ROOT_DIR/binary" --start-server > /dev/null &
disown
