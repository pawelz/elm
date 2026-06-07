import argparse
import json
import os
import sys
import numpy as np
import joblib
import onnxruntime as ort
from transformers import AutoTokenizer

def parse_args():
    parser = argparse.ArgumentParser(description="Run lightweight, ONNX-accelerated inference to detect email spam.")
    parser.add_argument(
        "--subject",
        type=str,
        default="",
        help="Email subject text."
    )
    parser.add_argument(
        "--body",
        type=str,
        default="",
        help="Email body text."
    )
    parser.add_argument(
        "--metadata",
        type=str,
        default="[]",
        help="JSON list of numeric metadata features (e.g. '[0, 1, 3]')."
    )
    parser.add_argument(
        "--onnx-path",
        type=str,
        required=True,
        help="Path to the quantized ONNX embedding model file."
    )
    parser.add_argument(
        "--classifier-path",
        type=str,
        required=True,
        help="Path to the trained joblib classifier file."
    )
    return parser.parse_args()

def parse_metadata_input(metadata_str, expected_dim):
    try:
        features = json.loads(metadata_str)
        if not isinstance(features, list):
            raise ValueError("Metadata features must be formatted as a JSON list.")
        
        # Convert all to floats
        numeric_features = [float(x) for x in features]
    except Exception as e:
        print(f"Warning: Failed to parse metadata string: {e}. Defaulting to zeros.")
        numeric_features = []
        
    # Standardize length to match expected_dim (M)
    if len(numeric_features) < expected_dim:
        numeric_features = numeric_features + [0.0] * (expected_dim - len(numeric_features))
    elif len(numeric_features) > expected_dim:
        numeric_features = numeric_features[:expected_dim]
        
    return np.array([numeric_features])

def main():
    args = parse_args()
    
    # 1. Load the trained classifier
    if not os.path.exists(args.classifier_path):
        print(f"Error: Classifier model not found at {args.classifier_path}")
        sys.exit(1)
        
    print(f"Loading classifier: {args.classifier_path}...")
    classifier = joblib.load(args.classifier_path)
    
    # Self-describe feature dimensionality
    total_features = classifier.n_features_in_
    
    # 2. Look for config file in the classifier's directory to find dimensions
    classifier_dir = os.path.dirname(args.classifier_path)
    config_path = os.path.join(classifier_dir, "metadata_config.json")
    
    embedding_dim = 384  # Default for paraphrase-multilingual-MiniLM-L12-v2
    metadata_dim = total_features - embedding_dim
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                embedding_dim = config.get("embedding_dim", embedding_dim)
                metadata_dim = config.get("metadata_dim", metadata_dim)
                print(f"Loaded config: Embedding Dim = {embedding_dim}, Metadata Dim = {metadata_dim}")
        except Exception as e:
            print(f"Warning: Failed to load config file: {e}. Falling back to default dimensions.")
            
    # Double check sanity
    if embedding_dim + metadata_dim != total_features:
        # Re-calculate metadata_dim based on actual classifier
        metadata_dim = total_features - embedding_dim
        print(f"Adjusted metadata dimension to match classifier: {metadata_dim}")
        
    # 3. Load the Tokenizer
    # We look for tokenizer files in the same directory as the ONNX model
    onnx_dir = os.path.dirname(args.onnx_path)
    print(f"Loading tokenizer from: {onnx_dir}...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(onnx_dir)
    except Exception as e:
        print(f"Error: Failed to load tokenizer from ONNX directory: {e}")
        sys.exit(1)
        
    # 4. Load the ONNX Inference Session
    if not os.path.exists(args.onnx_path):
        print(f"Error: ONNX model not found at {args.onnx_path}")
        sys.exit(1)
        
    print(f"Loading ONNX Session: {args.onnx_path}...")
    # Use CPU provider for lightweight execution (standard on Raspberry Pi)
    session = ort.InferenceSession(args.onnx_path, providers=["CPUExecutionProvider"])
    
    # 5. Tokenize text input
    combined_text = f"Subject: {args.subject}\n{args.body}"
    inputs = tokenizer(
        combined_text,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="np"  # Return numpy arrays directly
    )
    
    # Format inputs for ONNX
    onnx_inputs = {
        "input_ids": inputs["input_ids"].astype(np.int64),
        "attention_mask": inputs["attention_mask"].astype(np.int64)
    }
    
    # 6. Run ONNX inference to get text embedding
    outputs = session.run(["embeddings"], onnx_inputs)
    text_embedding = outputs[0]  # Shape: [1, embedding_dim]
    
    # 7. Process and format metadata features
    metadata_features = parse_metadata_input(args.metadata, metadata_dim)
    
    # 8. Synthesize final joint feature vector
    if metadata_dim > 0:
        final_features = np.hstack((text_embedding, metadata_features))
    else:
        final_features = text_embedding
        
    # 9. Execute classifier decision
    prob = classifier.predict_proba(final_features)[0]
    prediction = classifier.predict(final_features)[0]
    
    spam_probability = prob[1] * 100
    label_str = "SPAM" if prediction == 1 else "HAM"
    
    print("\n" + "=" * 40)
    print(" INFERENCE RESULT")
    print("=" * 40)
    print(f"Subject:     {args.subject}")
    print(f"Prediction:  {label_str}")
    print(f"Spam Prob:   {spam_probability:.2f}%")
    print(f"Ham Prob:    {(prob[0] * 100):.2f}%")
    print("=" * 40 + "\n")

if __name__ == "__main__":
    main()
