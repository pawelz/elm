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

Because the dataset files in `data/` are exposed to Bazel via a `BUILD.bazel` file, Bazel tracks their contents and will automatically avoid rebuilding if neither your training scripts nor your raw emails have changed.

---

## Step 5: Build the Debian Package
Compile the native C client, package the Python server script, systemd configuration, and post-installation setup scripts into a ready-to-deploy `.deb` package. The build system is fully hermetic and does not bundle the heavy, non-hermetic machine learning models:

```bash
bazel build //pkg:elm_deb
```
This outputs the cross-compiled package at:
`bazel-bin/pkg/elm-server_1.0.0_arm64.deb`

---

## Step 6: Deploy to Production

Deploying is a two-step process: installing the lightweight daemon/client package and deploying the heavy, separately-supplied model files.

### 1. Install/Upgrade the Server Package
Copy the `.deb` package to your production host and install it:
```bash
scp bazel-bin/pkg/elm-server_1.0.0_arm64.deb user@production-host:/tmp/
ssh user@production-host "sudo dpkg -i /tmp/elm-server_1.0.0_arm64.deb"
```
The package automatically:
* Registers a dedicated local Python virtual environment under `/usr/share/elm/.venv`.
* Installs all production serving dependencies (ONNX Runtime, Transformers, joblib, Scikit-Learn, bs4) securely.
* Creates the systemd service file (`elm-server.service`).
* Sets ownership permissions to `mail:mail`.

### 2. Deploy Model Files
Upload the 5 model assets from your local `model/` folder to the `/usr/share/elm/model/` directory on the target host using the automated `deploy.sh` script:

```bash
./deploy.sh --host user@production-host
```
Select `y` when prompted to restart the `elm-server` systemd service so that the daemon starts up and begins serving.

---

## Verifying the Production Server

To verify that the server is successfully listening on the socket:
```bash
ssh user@production-host "sudo systemctl status elm-server"
```

To test the client-server pipeline manually on the target machine:
```bash
ssh user@production-host "elm-client --socket /run/elm/elm.sock --threshold 0.50 --filter < /path/to/test/email.eml"
```
The client will output the classification headers followed by the unmodified email content.
