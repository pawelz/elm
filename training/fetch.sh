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

# Exit immediately if a command exits with a non-zero status
set -e

# Find the script's directory and workspace root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load the config file
CONFIG_FILE="${SCRIPT_DIR}/fetch.cfg"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    echo "Error: Config file not found at $CONFIG_FILE" >&2
    echo "Please copy training/fetch.cfg.example to training/fetch.cfg and configure it." >&2
    exit 1
fi

# Validate inputs
if [ -z "$REMOTE_HOST" ]; then
    echo "Error: REMOTE_HOST is not specified in training/fetch.cfg" >&2
    exit 1
fi

if [ -z "$GOOD_MAILDIRS" ] && [ -z "$BAD_MAILDIRS" ]; then
    echo "Error: At least one of GOOD_MAILDIRS or BAD_MAILDIRS must be specified in training/fetch.cfg" >&2
    exit 1
fi

if [ -z "$OUTPUT_DIR" ]; then
    OUTPUT_DIR="data"
fi

# Resolve TARGET_DIR relative to workspace root if it's not absolute
if [[ "$OUTPUT_DIR" = /* ]]; then
    TARGET_DIR="$OUTPUT_DIR"
else
    TARGET_DIR="${WORKSPACE_ROOT}/${OUTPUT_DIR}"
fi

echo "Syncing emails to destination: ${TARGET_DIR}"

# Create target subdirectories, clearing them first to ensure a clean sync
rm -rf "$TARGET_DIR/good" "$TARGET_DIR/bad"
mkdir -p "$TARGET_DIR/good"
mkdir -p "$TARGET_DIR/bad"

# Create inputs.txt debug file
cat <<EOF > "$TARGET_DIR/inputs.txt"
good: $GOOD_MAILDIRS
bad: $BAD_MAILDIRS
EOF

# Create a temporary directory for flattening structures
TEMP_DIR=$(mktemp -d "${TARGET_DIR}/.tmp.XXXXXX")

# Copy good Maildirs (only cur and new subdirectories)
IFS=',' read -ra GOOD_DIRS <<< "$GOOD_MAILDIRS"
for dir in "${GOOD_DIRS[@]}"; do
    if [ -n "$dir" ]; then
        echo "good:$dir"
        rsync -rt --quiet --include="*/" --include="cur/**" --include="new/**" --exclude="*" "${REMOTE_HOST}/${dir}/" "$TEMP_DIR/"
    fi
done

# Flatten good emails directly to the flat good/ directory
if [ -d "$TEMP_DIR" ] && [ "$(ls -A "$TEMP_DIR")" ]; then
    find "$TEMP_DIR" -type f -exec mv {} "$TARGET_DIR/good/" \;
    rm -rf "$TEMP_DIR"/*
fi

# Copy bad Maildirs (only cur and new subdirectories)
IFS=',' read -ra BAD_DIRS <<< "$BAD_MAILDIRS"
for dir in "${BAD_DIRS[@]}"; do
    if [ -n "$dir" ]; then
        echo "bad:$dir"
        rsync -rt --quiet --include="*/" --include="cur/**" --include="new/**" --exclude="*" "${REMOTE_HOST}/${dir}/" "$TEMP_DIR/"
    fi
done

# Flatten bad emails directly to the flat bad/ directory
if [ -d "$TEMP_DIR" ] && [ "$(ls -A "$TEMP_DIR")" ]; then
    find "$TEMP_DIR" -type f -exec mv {} "$TARGET_DIR/bad/" \;
fi

# Clean up temp directory
rm -rf "$TEMP_DIR"

echo "Sync completed successfully!"
exit 0
