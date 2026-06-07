# Implementation Plan: Python Training & Export Pipeline with Bazel

This plan details the steps to implement a machine learning training, ONNX export, and prediction pipeline in the `training/` directory of the workspace, wrapped in Bazel build targets for a seamless integration with the existing Bazel build system.

---

## Proposed Changes

We will introduce a Python-based pipeline inside the `training/` directory. Due to the heavy nature of Python machine learning dependencies (like PyTorch and SentenceTransformers) and potential compatibility issues compiling them hermetically in Bazel on macOS ARM64 with newer Python versions (such as 3.14), we will wrap the Python scripts in robust shell-script runners. These runners will automatically manage a local virtual environment (`.venv`) and resolve dependencies. Bazel will expose these runners via `sh_binary` targets, so they can be run simply with `bazel run //training:<target>`.

### Components & File Structure

#### [NEW] [BUILD.bazel (training)](file:///Users/pawelz/git/elm/training/BUILD.bazel)
Defines the Bazel targets:
* `//training:train`: Runs the model training phase.
* `//training:export`: Converts the trained sentence-transformer to ONNX and quantizes it to INT8.

#### [NEW] [BUILD.bazel (serving)](file:///Users/pawelz/git/elm/serving/BUILD.bazel)
Defines the Bazel targets:
* `//serving:predict`: Runs a standalone inference prediction on a sample email.

#### [NEW] [requirements.txt](file:///Users/pawelz/git/elm/training/requirements.txt)
Lists all python dependencies needed for the project:
* `sentence-transformers`
* `transformers`
* `scikit-learn`
* `joblib`
* `onnx`
* `onnxruntime`
* `numpy`

#### [NEW] [train.py](file:///Users/pawelz/git/elm/training/train.py)
Python script to:
1. Load a training dataset from a parameterized `--data-path` flag (rather than a hardcoded file).
2. Extract the text (Subject + Body) and generate embeddings using `paraphrase-multilingual-MiniLM-L12-v2`.
3. Concatenate the text embedding vectors with the numerical features found in `metadata_features` (supporting parsing of `metadata_features` so it is forward-compatible).
4. Train a `scikit-learn` Logistic Regression classifier.
5. Save the trained classifier `.joblib` file and feature schema definitions to a parameterized `--model-dir` flag (avoiding hardcoding).

#### [NEW] [export_onnx.py](file:///Users/pawelz/git/elm/training/export_onnx.py)
Python script to:
1. Export the SentenceTransformer embedding model to ONNX format.
2. Apply INT8 Dynamic Quantization to the model to reduce its footprint to ~34MB and optimize it for the Raspberry Pi ARM CPU.
3. Save the quantized model output to a parameterized `--output-dir` flag.

#### [NEW] [predict.py](file:///Users/pawelz/git/elm/serving/predict.py)
A standalone, ultra-lightweight inference script that does not require PyTorch or Hugging Face. It:
1. Uses `onnxruntime` to generate text embeddings from a parameterized `--onnx-path` file.
2. Formats incoming input text and `metadata_features` (e.g., using `--subject`, `--body`, and `--metadata` flags).
3. Passes the concatenated features into the loaded classifier using a parameterized `--classifier-path` file to produce a spam probability.

#### [NEW] [run_python.sh](file:///Users/pawelz/git/elm/training/run_python.sh)
A helper shell script used by Bazel to:
1. Create and manage a local Python virtual environment `.venv/` if not already present.
2. Install dependencies from `requirements.txt` if they have changed or are missing.
3. Execute the corresponding Python script (`train.py`, `export_onnx.py`, or `predict.py`), forwarding all command-line arguments.

---

## Verification Plan

### Automated Tests
- We will verify that each Bazel command executes successfully with parameterized flags:
  - `bazel run //training:train -- --data-path data/20260606-0/training.jsonl --model-dir training` to train the PoC v1 model.
  - `bazel run //training:export -- --output-dir training` to generate the optimized ONNX model.
  - `bazel run //serving:predict -- --subject "Test" --body "Hello there!" --metadata "[0, 0, 0]" --onnx-path training/model_quantized.onnx --classifier-path training/spam_classifier.joblib` to run verification.

### Manual Verification
- Confirm that the final model size of `model_quantized.onnx` is ~34MB and that the runtime takes less than 100ms per prediction on CPU.
