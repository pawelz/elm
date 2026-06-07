#!/bin/bash
set -e

# Find the workspace root directory
if [ -n "$BUILD_WORKSPACE_DIRECTORY" ]; then
  WORKSPACE_ROOT="$BUILD_WORKSPACE_DIRECTORY"
else
  # Fallback: search upwards for MODULE.bazel
  DIR="$(pwd)"
  while [ "$DIR" != "/" ]; do
    if [ -f "$DIR/MODULE.bazel" ]; then
      WORKSPACE_ROOT="$DIR"
      break
    fi
    DIR="$(dirname "$DIR")"
  done
  if [ -z "$WORKSPACE_ROOT" ]; then
    WORKSPACE_ROOT="$(pwd)"
  fi
fi

VENV_PATH="$WORKSPACE_ROOT/.venv"

if [ ! -d "$VENV_PATH" ]; then
  echo "========================================================================"
  echo "Virtual environment not found at $VENV_PATH."
  echo "Creating virtual environment and installing python ML dependencies..."
  echo "========================================================================"
  python3 -m venv "$VENV_PATH"
  source "$VENV_PATH/bin/activate"
  # Upgrade pip first
  pip install --upgrade pip --quiet
else
  source "$VENV_PATH/bin/activate"
fi

# Fast dependency verification: we run pip install. It's very fast if all packages are already satisfied.
pip install -r "$WORKSPACE_ROOT/training/requirements.txt" --quiet

# Determine the python script to run based on the executable name (basename of $0)
BIN_NAME=$(basename "$0")

if [ "$BIN_NAME" = "train" ]; then
  SCRIPT_REL_PATH="training/train.py"
elif [ "$BIN_NAME" = "export" ]; then
  SCRIPT_REL_PATH="training/export_onnx.py"
elif [ "$BIN_NAME" = "predict" ]; then
  SCRIPT_REL_PATH="training/predict.py"
else
  # Fallback if run directly as run_python.sh
  SCRIPT_REL_PATH="$1"
  shift
fi

cd "$WORKSPACE_ROOT"
python3 "$SCRIPT_REL_PATH" "$@"
