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

# Usage helper
usage() {
    echo "Usage: $0 --host <user@hostname>"
    echo "Options:"
    echo "  --host, -h    Remote host (e.g. pi@raspberrypi.local or simply raspberrypi)"
    exit 1
}

# Parse arguments
HOST=""
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --host|-h) HOST="$2"; shift ;;
        *) echo "Unknown parameter: $1"; usage ;;
    esac
    shift
done

if [ -z "$HOST" ]; then
    echo "Error: --host is required."
    usage
fi

# Define local model dir and files
LOCAL_MODEL_DIR="model"
MODEL_FILES=(
    "metadata_config.json"
    "model_quantized.onnx"
    "spam_classifier.joblib"
    "tokenizer.json"
    "tokenizer_config.json"
)

# 1. Verify local files exist
echo "Checking local model files..."
for file in "${MODEL_FILES[@]}"; do
    local_path="${LOCAL_MODEL_DIR}/${file}"
    if [ ! -f "$local_path" ]; then
        echo "Error: Local model file not found: $local_path"
        echo "Please make sure to run the training/export pipeline first."
        exit 1
    fi
done

# 2. Create remote temporary directory
TEMP_DIR="/tmp/elm-model-upload"
echo "Creating temporary upload directory on remote host ($HOST)..."
ssh "$HOST" "mkdir -p $TEMP_DIR"

# 3. SCP files to remote temp directory
echo "Uploading model files to remote temporary directory..."
for file in "${MODEL_FILES[@]}"; do
    echo "  Uploading $file..."
    scp "${LOCAL_MODEL_DIR}/${file}" "${HOST}:${TEMP_DIR}/${file}"
done

# 4. Move files to production location under sudo, set permissions
echo "Moving model files to /usr/share/elm/model/ and setting correct permissions..."
ssh -t "$HOST" "sudo mkdir -p /usr/share/elm/model && \
                sudo mv ${TEMP_DIR}/* /usr/share/elm/model/ && \
                sudo rmdir ${TEMP_DIR} && \
                sudo chown -R mail:mail /usr/share/elm/model && \
                echo 'Model files successfully deployed!'"

# 5. Optionally restart the service
read -p "Would you like to restart the elm-server service on the remote host? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Restarting elm-server service..."
    ssh -t "$HOST" "sudo systemctl restart elm-server && sudo systemctl status elm-server --no-pager"
fi

echo "Deployment complete!"
