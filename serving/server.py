#!/usr/bin/env python3
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

import argparse
import json
import os
import signal
import socket
import sys
import threading
import traceback
import numpy as np
import joblib
import onnxruntime as ort
from transformers import AutoTokenizer

from core import email_parser

# Global variable to hold socket path so signal handler can clean it up
socket_path_to_clean = None

def signal_handler(signum, frame):
    """Gracefully cleans up the UNIX socket file on exit."""
    print(f"\nReceived signal {signum}. Shutting down...", flush=True)
    if socket_path_to_clean and os.path.exists(socket_path_to_clean):
        try:
            os.remove(socket_path_to_clean)
            print(f"Cleaned up socket file at: {socket_path_to_clean}", flush=True)
        except Exception as e:
            print(f"Error cleaning up socket file: {e}", file=sys.stderr, flush=True)
    sys.exit(0)

def load_config(classifier_path, total_features):
    """Loads metadata dimension configurations from classifier directory if present."""
    classifier_dir = os.path.dirname(classifier_path)
    config_path = os.path.join(classifier_dir, "metadata_config.json")
    
    embedding_dim = 384  # Default for paraphrase-multilingual-MiniLM-L12-v2
    metadata_dim = total_features - embedding_dim
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                embedding_dim = config.get("embedding_dim", embedding_dim)
                metadata_dim = config.get("metadata_dim", metadata_dim)
                print(f"Loaded config: Embedding Dim = {embedding_dim}, Metadata Dim = {metadata_dim}", flush=True)
        except Exception as e:
            print(f"Warning: Failed to load config file: {e}. Falling back to default dimensions.", file=sys.stderr, flush=True)
            
    if embedding_dim + metadata_dim != total_features:
        metadata_dim = total_features - embedding_dim
        print(f"Adjusted metadata dimension to match classifier: {metadata_dim}", flush=True)
        
    return embedding_dim, metadata_dim

def handle_client(client_sock, session, tokenizer, classifier, metadata_dim):
    """Processes an incoming connection from the native client."""
    try:
        # Read raw email bytes until EOF
        raw_bytes_list = []
        while True:
            data = client_sock.recv(4096)
            if not data:
                break
            raw_bytes_list.append(data)
            
        raw_email_bytes = b"".join(raw_bytes_list)
        if not raw_email_bytes:
            # Empty stream
            client_sock.sendall(b"0.5000\n")
            return
            
        # 1. Parse using shared core.email_parser
        record = email_parser.parse(raw_email_bytes)
        subject = record.get("subject", "")
        body = record.get("body", "")
        
        # 2. Tokenize text input
        combined_text = f"Subject: {subject}\n{body}"
        inputs = tokenizer(
            combined_text,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="np"
        )
        
        # 3. Format inputs for ONNX
        onnx_inputs = {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64)
        }
        
        # 4. Run ONNX embeddings inference
        outputs = session.run(["embeddings"], onnx_inputs)
        text_embedding = outputs[0]  # Shape: [1, embedding_dim]
        
        # 5. Synthesize joint feature vector (metadata elements default to 0.0)
        if metadata_dim > 0:
            metadata_features = np.zeros((1, metadata_dim))
            final_features = np.hstack((text_embedding, metadata_features))
        else:
            final_features = text_embedding
            
        # 6. Run final classification decision
        prob = classifier.predict_proba(final_features)[0]
        score = prob[1] # Probability of class 1 (SPAM)
        
        response = f"{score:.4f}\n"
        client_sock.sendall(response.encode("utf-8"))
        
    except Exception as e:
        print(f"Error serving inference request: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        # Safe Picard Fallback: on any error, return 0.5000 so the email is not lost or blackholed
        try:
            client_sock.sendall(b"0.5000\n")
        except Exception:
            pass
    finally:
        try:
            client_sock.close()
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="High-performance pure Python server daemon for Elm Spam Classification.")
    parser.add_argument("--socket", default="/run/elm/elm.sock", help="Path to the UNIX domain socket.")
    parser.add_argument("--onnx-path", default="model/model_quantized.onnx", help="Path to the quantized ONNX embedding model file.")
    parser.add_argument("--classifier-path", default="model/spam_classifier.joblib", help="Path to the trained joblib classifier file.")

    args = parser.parse_args()

    # 1. Validate assets and exit early if missing
    if not os.path.exists(args.classifier_path):
        print(f"Error: Classifier model not found at: {args.classifier_path}", file=sys.stderr, flush=True)
        sys.exit(1)
    if not os.path.exists(args.onnx_path):
        print(f"Error: ONNX model not found at: {args.onnx_path}", file=sys.stderr, flush=True)
        sys.exit(1)

    print(f"Starting Elm Spam Classification Server...", flush=True)
    
    # 2. Register signal handlers for cleanup
    global socket_path_to_clean
    socket_path_to_clean = args.socket
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 3. Load ML models and tokenizer into memory once at startup
    print(f"Loading joblib classifier from {args.classifier_path}...", flush=True)
    classifier = joblib.load(args.classifier_path)
    
    # Safe fallback patching for scikit-learn version mismatches (e.g. 1.9.x trained model loaded in 1.6.x)
    if not hasattr(classifier, "multi_class"):
        print("Patching missing 'multi_class' attribute on classifier for compatibility...", flush=True)
        classifier.multi_class = "auto"
        
    total_features = classifier.n_features_in_
    
    embedding_dim, metadata_dim = load_config(args.classifier_path, total_features)
    
    onnx_dir = os.path.dirname(args.onnx_path)
    print(f"Loading AutoTokenizer from {onnx_dir}...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(onnx_dir)
    
    print(f"Loading ONNX Session from {args.onnx_path}...", flush=True)
    session = ort.InferenceSession(args.onnx_path, providers=["CPUExecutionProvider"])
    
    # 4. Initialize and bind UNIX domain socket
    socket_dir = os.path.dirname(os.path.abspath(args.socket))
    if socket_dir:
        os.makedirs(socket_dir, exist_ok=True)
        
    if os.path.exists(args.socket):
        try:
            os.remove(args.socket)
        except OSError as e:
            print(f"Error removing stale socket file: {e}", file=sys.stderr, flush=True)
            sys.exit(1)

    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server_sock.bind(args.socket)
        # Ensure correct broad permissions so mail processes like exim/maildrop can read/write
        os.chmod(args.socket, 0o666)
    except Exception as e:
        print(f"Error binding UNIX domain socket: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

    server_sock.listen(128)
    print(f"Server is listening on UNIX domain socket: {args.socket}", flush=True)

    # 5. Main accept loop
    while True:
        try:
            client_sock, client_addr = server_sock.accept()
            # Spawn a lightweight worker thread for concurrent execution
            t = threading.Thread(
                target=handle_client,
                args=(client_sock, session, tokenizer, classifier, metadata_dim),
                daemon=True
            )
            t.start()
        except Exception as e:
            print(f"Error accepting connection: {e}", file=sys.stderr, flush=True)

if __name__ == "__main__":
    main()
