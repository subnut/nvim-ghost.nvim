#!/usr/bin/env sh

# For more info about the 'set' command, see
# https://www.gnu.org/software/bash/manual/bash.html#The-Set-Builtin
set -e
set -u

if which curl 2>&1 >/dev/null; then
  continue
else
  echo "curl: command not found" >&2
  echo 'Please ensure that curl is installed and available in your $PATH' >&2
  exit 127
fi

ROOT_DIR=$(
  cd "$(dirname "$0")/.."
  pwd -P
)
cd "$ROOT_DIR"

OS="$(uname)"
OUTFILE="$ROOT_DIR/nvim-ghost-binary"
PKG_VERSION=$(cat "$ROOT_DIR/.binary_version")
RELEASE_URL="https://github.com/subnut/nvim-ghost.nvim/releases/download/$PKG_VERSION"

if [ -e $OUTFILE ]; then
  rm -f $OUTFILE
fi

if [ "$OS" = 'Darwin' ]; then
  TARGET="nvim-ghost-macos"
elif [ "$OS" = 'Linux' ]; then
  TARGET="nvim-ghost-linux"
else
  echo "nvim-ghost does not support your system"
  exit 1
fi

FILENAME="$TARGET.tar.gz"
DOWNLOAD_URL="$RELEASE_URL/$FILENAME"
echo "Downloading $DOWNLOAD_URL"
curl -L --progress-bar \
  --fail \
  --output "$FILENAME" \
  "$DOWNLOAD_URL"
tar xzf "$FILENAME"
rm -f "$FILENAME"
chmod +x "$OUTFILE"
