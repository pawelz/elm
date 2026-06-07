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
import sys
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
import joblib
import numpy as np

def parse_args():
    parser = argparse.ArgumentParser(description="Train a multilingual spam classifier using sentence embeddings and metadata features.")
    parser.add_argument(
        "--data-path",
        type=str,
        required=True,
        help="Path to the training.jsonl file."
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        required=True,
        help="Directory to save the trained classifier and config files."
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        help="Pretrained multilingual SentenceTransformer model to use."
    )
    return parser.parse_args()

def load_data(data_path):
    print(f"Loading data from {data_path}...")
    texts = []
    labels = []
    metadata_vectors = []
    
    if not os.path.exists(data_path):
        print(f"Error: Data path {data_path} does not exist.")
        sys.exit(1)
        
    with open(data_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                subject = item.get("subject", "")
                body = item.get("body", "")
                label = item.get("label")
                metadata = item.get("metadata_features", [])
                
                # Combine subject and body for a richer text representation
                combined_text = f"Subject: {subject}\n{body}"
                texts.append(combined_text)
                labels.append(int(label))
                
                # Treat metadata_features as a list of numbers
                # Gracefully convert non-numeric elements if any exist
                numeric_metadata = [float(x) for x in metadata if x is not None]
                metadata_vectors.append(numeric_metadata)
            except Exception as e:
                print(f"Warning: Failed to parse line {i + 1}: {e}")
                
    print(f"Successfully loaded {len(texts)} samples.")
    return texts, np.array(labels), metadata_vectors

def process_metadata(metadata_vectors):
    # Determine metadata dimension M
    # Find the maximum metadata feature dimension in the dataset
    m_dim = 0
    for vec in metadata_vectors:
        if len(vec) > m_dim:
            m_dim = len(vec)
            
    print(f"Detected metadata feature dimension (M): {m_dim}")
    
    # Standardize all metadata vectors to have the same length M by zero-padding or truncating
    processed_vectors = []
    for vec in metadata_vectors:
        if len(vec) < m_dim:
            # Pad with zeros
            padded = vec + [0.0] * (m_dim - len(vec))
            processed_vectors.append(padded)
        else:
            # Truncate if somehow longer
            processed_vectors.append(vec[:m_dim])
            
    return np.array(processed_vectors), m_dim

def main():
    args = parse_args()
    
    # Ensure model directory exists
    os.makedirs(args.model_dir, exist_ok=True)
    
    # 1. Load data
    texts, labels, raw_metadata = load_data(args.data_path)
    
    # 2. Process metadata
    metadata_features, m_dim = process_metadata(raw_metadata)
    
    # 3. Load pre-trained SentenceTransformer and extract embeddings
    print(f"Loading sentence embedding model: {args.embedding_model}...")
    model = SentenceTransformer(args.embedding_model)
    
    print("Extracting text embeddings (this might take a few minutes on CPU)...")
    # Set show_progress_bar=True to give nice output
    text_embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    print(f"Text embeddings shape: {text_embeddings.shape}")
    
    # 4. Concatenate Text Embeddings with Tabular Metadata Features
    if m_dim > 0:
        print("Concatenating text embeddings with metadata features...")
        final_features = np.hstack((text_embeddings, metadata_features))
    else:
        print("No metadata features found. Using text embeddings only.")
        final_features = text_embeddings
        
    print(f"Final training features shape: {final_features.shape}")
    
    # 5. Train standard Logistic Regression classifier
    print("Training Logistic Regression classifier...")
    # Use L2 regularization, class_weight='balanced' to handle any label imbalance gracefully
    classifier = LogisticRegression(max_iter=1000, C=1.0, class_weight="balanced", random_state=42)
    classifier.fit(final_features, labels)
    
    # Evaluate simple training accuracy
    train_acc = classifier.score(final_features, labels)
    print(f"Model Training Accuracy: {train_acc:.4f}")
    
    # 6. Save model and metadata configuration
    classifier_path = os.path.join(args.model_dir, "spam_classifier.joblib")
    print(f"Saving classifier model to {classifier_path}...")
    joblib.dump(classifier, classifier_path)
    
    config_path = os.path.join(args.model_dir, "metadata_config.json")
    config = {
        "metadata_dim": m_dim,
        "embedding_model": args.embedding_model,
        "embedding_dim": text_embeddings.shape[1],
        "total_features": final_features.shape[1]
    }
    print(f"Saving pipeline configuration to {config_path}...")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
        
    print("Training pipeline run complete!")

if __name__ == "__main__":
    main()
