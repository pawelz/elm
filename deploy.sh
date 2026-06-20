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
LOCAL_MODEL_DIR="bazel-bin/model"
MODEL_FILES=(
    "metadata_config.json"
    "model_quantized.onnx"
    "spam_classifier.joblib"
    "tokenizer.json"
    "tokenizer_config.json"
)

# 1. Verify local files exist before doing anything on the remote host
echo "Checking local model files..."
for file in "${MODEL_FILES[@]}"; do
    local_path="${LOCAL_MODEL_DIR}/${file}"
    if [ ! -f "$local_path" ]; then
        echo "Error: Local model file not found: $local_path"
        echo "Please make sure to run the training/export pipeline first."
        exit 1
    fi
done

# 2. Ensure the remote repository directory exists and is initialized as a git repository
echo ""
echo "------------------------------------------------------------"
echo ">>> STEP 2/11: Initializing remote repository on target..."
echo "------------------------------------------------------------"
ssh "$HOST" "echo 'Creating/verifying remote directory ~/elm...' && mkdir -p elm && cd elm && if [ ! -d .git ]; then echo 'Initializing git repository...'; git init; else echo 'Git repository already initialized.'; fi"

# 3. Use Git to force-push the local HEAD to the remote deployment branch 'deploy'
echo ""
echo "------------------------------------------------------------"
echo ">>> STEP 3/11: Syncing local repository to remote host..."
echo "------------------------------------------------------------"
git push -f "${HOST}:elm" HEAD:refs/heads/deploy

# 4. SSH to remote host, checkout/instantiate the files, and build the Debian package
echo ""
echo "------------------------------------------------------------"
echo ">>> STEP 4/11: Updating working tree & building Debian package on remote..."
echo "------------------------------------------------------------"
ssh -t "$HOST" "bash -l -c 'source ~/.bashrc 2>/dev/null || true; \
                 echo \"[Remote] Entering ~/elm directory...\" && cd elm && \
                 echo \"[Remote] Checking out deploy branch...\" && git checkout -f deploy && \
                 echo \"[Remote] Resetting working tree to match pushed commit...\" && git reset --hard deploy && \
                 echo \"[Remote] Launching Bazel compilation of pkg:elm_deb... (this can take a moment on low-end devices)\" && \
                 bazel build --local_ram_resources=1024 --local_cpu_resources=2 --jobs=2 --color=yes --curses=yes pkg:elm_deb && \
                 echo \"[Remote] Bazel compilation completed successfully!\"'"

# 5. Create remote temporary directory for model files
TEMP_DIR="/tmp/elm-model-upload"
echo ""
echo "------------------------------------------------------------"
echo ">>> STEP 5/11: Creating model upload folder on remote..."
echo "------------------------------------------------------------"
ssh "$HOST" "echo 'Creating temporary directory $TEMP_DIR...' && mkdir -p $TEMP_DIR"

# 6. SCP files to remote temp directory
echo ""
echo "------------------------------------------------------------"
echo ">>> STEP 6/11: Uploading ML model files via SCP..."
echo "------------------------------------------------------------"
for file in "${MODEL_FILES[@]}"; do
    echo "  -> Copying ${file}..."
    scp "${LOCAL_MODEL_DIR}/${file}" "${HOST}:${TEMP_DIR}/${file}"
done

# 7. Stop exim4 service on remote host to prevent incoming email issues during installation
echo ""
echo "------------------------------------------------------------"
echo ">>> STEP 7/11: Stopping Exim4 service on remote..."
echo "------------------------------------------------------------"
ssh -t "$HOST" "sudo service exim4 stop"

# 8. Install the built Debian package on the remote host
echo ""
echo "------------------------------------------------------------"
echo ">>> STEP 8/11: Installing built Debian package via dpkg..."
echo "------------------------------------------------------------"
ssh -t "$HOST" "echo 'Running dpkg installer...' && sudo dpkg -i ~/elm/bazel-bin/pkg/elm-server_*.deb"

# 9. Move files to production location under sudo, set permissions
echo ""
echo "------------------------------------------------------------"
echo ">>> STEP 9/11: Deploying ML model files to system directory..."
echo "------------------------------------------------------------"
ssh -t "$HOST" "echo 'Creating production directory /usr/share/elm/model/...' && sudo mkdir -p /usr/share/elm/model && \
                echo 'Moving files from temporary location...' && sudo mv ${TEMP_DIR}/* /usr/share/elm/model/ && \
                echo 'Cleaning up temporary folder...' && sudo rmdir ${TEMP_DIR} && \
                echo 'Setting directory ownership to mail:mail...' && sudo chown -R mail:mail /usr/share/elm/model && \
                echo 'Model files successfully deployed!'"

# 10. Restart elm-server service on the remote host
echo ""
echo "------------------------------------------------------------"
echo ">>> STEP 10/11: Restarting elm-server service..."
echo "------------------------------------------------------------"
ssh -t "$HOST" "sudo systemctl restart elm-server && echo 'elm-server service successfully restarted!'"

# 11. Start exim4 service on remote host
echo ""
echo "------------------------------------------------------------"
echo ">>> STEP 11/11: Starting Exim4 service back up..."
echo "------------------------------------------------------------"
ssh -t "$HOST" "sudo service exim4 start && echo 'Exim4 service successfully started!'"

echo ""
echo "============================================================"
echo " Deployment Complete & Services Re-activated Successfully!"
echo "============================================================"
