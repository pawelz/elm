# Elm Quick Reference Guide

This reference guide provides a concise, step-by-step walkthrough of how to ingest data, train the machine learning models, build the Debian package, and deploy the entire Elm spam classification stack.

---

## Architecture Overview
* **Client (`elm-client`)**: A native C executable that reads an email from standard input, streams it to a local UNIX domain socket, receives a score, prints the classification headers (`X-Spam-Status`, `X-Spam-Score`), and dumps the original email back to standard output. Perfect for MTA integration (e.g., Exim4, postfix, or maildrop).
* **Server Daemon (`elm-server`)**: A persistent Python background service running in a local virtual environment. It listens on a UNIX domain socket, processes incoming emails concurrently, tokenizes text, generates high-quality multilingual sentence embeddings using a quantized ONNX model, evaluates the spam probability using a trained classifier head, and returns the result.

---

## Step 1: Configure & Fetch Raw Email Data
The email ingestion process is configured via a gitignored configuration file `training/fetch.cfg`. 

1. Copy the example configuration template:
   ```bash
   cp training/fetch.cfg.example training/fetch.cfg
   ```
2. Open `training/fetch.cfg` in your editor and configure your remote server details and the target good/bad Maildir directories.
3. Run the fetch script:
   ```bash
   ./training/fetch.sh
   ```

This will connect to your remote mail server via `rsync` and synchronize your emails directly to:
* `data/good/` (clean non-spam emails)
* `data/bad/` (spam emails)

The script automatically flattens, filters, and clears out old datasets to guarantee clean, up-to-date inputs.

---

## Step 2: Build & Train the Model (Automated with Bazel)
The entire training pipeline (ingesting raw emails, extracting multilingual sentence embeddings, training a Scikit-Learn Logistic Regression classification head, tracing/exporting the PyTorch model to ONNX, and compiling/quantizing to INT8) is fully automated with a single Bazel command:

```bash
bazel build model:elm
```

This runs the end-to-end ML orchestration using your local Python virtual environment (`.venv`). It automatically produces all 5 required model and tokenizer artifacts in the Bazel output bin directory:
* `bazel-bin/model/model_quantized.onnx`
* `bazel-bin/model/tokenizer.json`
* `bazel-bin/model/tokenizer_config.json`
* `bazel-bin/model/spam_classifier.joblib`
* `bazel-bin/model/metadata_config.json`

> [!NOTE]
> **Email Dataset Tracking Disclaimer**: Because Maildir format filenames contain colons (`:`) and commas (`,`), which are incompatible with Bazel's target/label character restrictions, the raw emails in `data/good/` and `data/bad/` are accessed directly by the local genrule during the build phase instead of being explicitly listed in `srcs`.
>
> Consequently, Bazel **does not track individual raw email file changes**. It considers the build fresh if your training source files and configurations (e.g. `training/train.py`, etc.) are unchanged.
>
> To **force-rebuild/retrain** the model after fetching fresh raw emails, you can either:
> 1. Run `touch training/train.py` locally before running the build.
> 2. Pass a dynamic environment variable to Bazel to bypass the action cache:
>    ```bash
>    bazel build model:elm --action_env=FORCE_REBUILD=$(date +%s)
>    ```

---

## Step 3: Deploy to Production (Fully Automated)

The entire deployment process—pushing your latest code, natively building the lightweight Debian package on the target machine, copying the heavy machine learning model files, and performing a zero-downtime service restart—is fully automated via the `deploy.sh` script.

To deploy the entire stack to your production server:

```bash
./deploy.sh --host user@production-host
```

### What `deploy.sh` does automatically:
1. **Pre-Flight Checks**: Verifies that your local Bazel-compiled ML model files exist under `bazel-bin/model/`.
2. **Git Auto-Initialization**: Ensures the remote directory exists, is initialized as a Git repository on-the-fly (`git init`) if needed, and is configured (`receive.denyCurrentBranch = ignore`) to safely accept pushes to its currently checked-out branch.
3. **Smart Git Sync**: Force-pushes the local `HEAD` commit directly to a dedicated remote `deploy` branch (`${HOST}:elm`).
4. **Native Remote Compilation**: Connects via SSH to perform a hard reset to the `deploy` branch and compile the Debian package (`pkg:elm_deb`) natively on the target host. It automatically restricts CPU and RAM resources (`--local_ram_resources=1024 --jobs=2`) to run smoothly even on low-end target hardware (like a Raspberry Pi 4) without causing disk swap thrashing.
5. **Model Staging**: Securely uploads your local model and tokenizer files via SCP to a temporary directory on the host.
6. **Just-In-Time Exim4 Stopping**: Stops the remote `exim4` service right before installing any files to avoid incoming email classification race conditions.
7. **Package Installation**: Installs the freshly built native Debian package securely (`sudo dpkg -i bazel-bin/pkg/elm-server_*.deb`).
8. **Model Deployment**: Moves the staging model files directly into `/usr/share/elm/model/` with correct permissions and ownership.
9. **Zero-Downtime Restarts**: Restarts the `elm-server` daemon and starts `exim4` back up immediately, reducing the mail delivery downtime window to **just 2–3 seconds**.

---

## Step 4: Verifying the Production Server

To verify that the server is successfully listening on the socket:
```bash
ssh user@production-host "sudo systemctl status elm-server"
```

To test the client-server pipeline manually on the target machine, pipe any raw `.eml` file into the client:
```bash
ssh user@production-host "elm-client --socket /run/elm/elm.sock --threshold 0.50 --filter < /path/to/test/email.eml"
```

The client will process the message and output the updated classification headers (`X-Spam-Status`, `X-Spam-Score`) followed by the unmodified email content.


