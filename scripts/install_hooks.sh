ROOT_DIR=$(cd "$(dirname "$0")/.."; pwd -P)
cd "$ROOT_DIR"
cp scripts/hooks .git/hooks -r
