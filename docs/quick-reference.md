# Elm Quick Reference Guide

This reference guide provides a concise, step-by-step walkthrough of how to ingest data, train the machine learning models, build the Debian package, and deploy the entire Elm spam classification stack.

---

## Architecture Overview
* **Client (`elm-client`)**: A native C executable that reads an email from standard input, streams it to a local UNIX domain socket, receives a score, prints the classification headers (`X-Spam-Status`, `X-Spam-Score`), and dumps the original email back to standard output. Perfect for MTA integration (e.g., Exim4, postfix, or maildrop).
* **Server Daemon (`elm-server`)**: A persistent Python background service running in a local virtual environment. It listens on a UNIX domain socket, processes incoming emails concurrently, tokenizes text, generates high-quality multilingual sentence embeddings using a quantized ONNX model, evaluates the spam probability using a trained classifier head, and returns the result.

---

## Step 1: Fetch Raw Email Data
Use the `ingest/fetch.sh` utility to copy, filter (grabbing only `new` and `cur` mail files), and flatten email datasets from a remote mail server via `rsync`.

```bash
./ingest/fetch.sh \
  --remote user@your-mail-server.com:/home/user/Maildir \
  --good .Archive,.Inbox \
  --bad .Spam,.Junk
```

This creates a flattened dataset folder at `data/YYYYMMDD-X/` (where `X` is a disambiguation character), creating two subdirectories:
* `data/YYYYMMDD-X/good/` (non-spam emails)
* `data/YYYYMMDD-X/bad/` (spam emails)

---

## Step 2: Ingest and Parse Emails
Convert the raw Maildir files into a single, standardized, JSONL training dataset. This step decodes alternative text encodings, strips HTML markup while preserving layout, extracts URLs, and extracts core metadata:

```bash
# 1. Build the ingestion target
bazel build //training:ingest

# 2. Parse the emails
./bazel-bin/training/ingest \
  --good data/YYYYMMDD-X/good \
  --bad data/YYYYMMDD-X/bad \
  --output training.jsonl
```

---

## Step 3: Train the Classifier
Extract multilingual text embeddings using a sentence-transformer backbone and train a Scikit-Learn Logistic Regression classification head on the combined text embeddings and tabular email metadata:

```bash
# 1. Build the training target
bazel build //training:train

# 2. Execute training
./bazel-bin/training/train \
  --data-path training.jsonl \
  --model-dir model
```

This generates `spam_classifier.joblib` (the trained head) and `metadata_config.json` (pipeline dimension details) in your local `model/` folder.

---

## Step 4: Export & Quantize the ONNX Model
Trace the SentenceTransformer backbone model, compile it to an ONNX graph, apply Post-Training INT8 Dynamic Quantization (reducing the model size by over 70% to ~119MB), copy the tokenizer configurations, and automatically apply runtime compatibility patches:

```bash
# 1. Build the export target
bazel build //training:export

# 2. Export and Quantize
./bazel-bin/training/export \
  --output-dir model
```

This generates `model_quantized.onnx`, `tokenizer.json`, and `tokenizer_config.json` (specifically patched for cross-platform unpickling safety) in your local `model/` folder.

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
