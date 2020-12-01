ROOT_DIR=$(
  cd "$(dirname "$0")/.."
  pwd -P
)
echo $ROOT_DIR
cd "$ROOT_DIR"
cp "$ROOT_DIR"/scripts/hooks "$ROOT_DIR"/.git/ -r
