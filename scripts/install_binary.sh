#!/bin/sh

# For more info about the 'set' command, see
# https://www.gnu.org/software/bash/manual/bash.html#The-Set-Builtin
set -e
set -u

# Ensure curl is installed
if which curl 2>&1 >/dev/null; then
  continue
else
  echo "curl: command not found" >&2
  echo 'Please ensure that curl is installed and available in your $PATH' >&2
  exit 127
fi

# chdir to the plugin dir
ROOT_DIR=$(
  cd "$(dirname "$0")/.."
  pwd -P
)
cd "$ROOT_DIR"

# set variables
OS="$(uname)"
OUTFILE="$ROOT_DIR/nvim-ghost-binary"
PKG_VERSION=$(cat "$ROOT_DIR/binary_version")
RELEASE_URL="https://github.com/subnut/nvim-ghost.nvim/releases/download/$PKG_VERSION"

# delete any previous partial downloads
if [ -e $OUTFILE ]; then
  rm -f $OUTFILE
fi

# set download name
if   [ "$OS" = Darwin ]; then TARGET=nvim-ghost-macos
elif [ "$OS" = Linux  ]; then TARGET=nvim-ghost-linux
else
  echo "nvim-ghost does not have pre-built binaries for your system"
  exit 1
fi

# download
FILENAME="$TARGET.tar.gz"
DOWNLOAD_URL="$RELEASE_URL/$FILENAME"
echo "Downloading $DOWNLOAD_URL"
curl -L \
  --fail \
  --progress-bar \
  --output "$FILENAME" \
  "$DOWNLOAD_URL"

# extract
tar xzf "$FILENAME"
rm -f "$FILENAME"
chmod +x "$OUTFILE"

# vim: et sw=2 ts=2 sts=2
