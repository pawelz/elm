#!/bin/bash
# Copyright 2026 Paweł Zuzelski
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

# Resolve symbolic links recursively to locate the physical source file
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
DIR="$SCRIPT_DIR"
WORKSPACE_ROOT=""
while [ "$DIR" != "/" ]; do
  if [ -f "$DIR/MODULE.bazel" ]; then
    WORKSPACE_ROOT="$DIR"
    break
  fi
  DIR="$(dirname "$DIR")"
done

if [ -z "$WORKSPACE_ROOT" ]; then
  echo "Error: Could not locate workspace root (MODULE.bazel)" >&2
  exit 1
fi

VENV_PATH="$WORKSPACE_ROOT/.venv"

if [ ! -d "$VENV_PATH" ]; then
  echo "Error: Python virtual environment not found at $VENV_PATH." >&2
  echo "Please set up the virtual environment by running training or serving first." >&2
  exit 1
fi

source "$VENV_PATH/bin/activate"
export PYTHONPATH="$WORKSPACE_ROOT:$PYTHONPATH"

# Run unittest
python3 "$WORKSPACE_ROOT/core/email_parser_test.py"
