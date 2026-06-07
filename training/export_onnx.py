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
import os
import sys
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel
import onnx
from onnxruntime.quantization import quantize_dynamic, QuantType

# Define a custom wrapper that packages both the Hugging Face transformer and mean pooling into a single ONNX graph
class SentenceEmbeddingPipeline(nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, input_ids, attention_mask):
        # Forward pass through the Transformer backbone
        outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
        token_embeddings = outputs.last_hidden_state  # Shape: [batch_size, seq_len, hidden_size]
        
        # Perform Mean Pooling, taking attention mask into account
        # Expand attention_mask from [batch_size, seq_len] to [batch_size, seq_len, hidden_size]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        
        # Sum embeddings across tokens (dimension 1)
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
        
        # Sum attention mask and clamp to avoid division by zero
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        
        # Calculate mean
        mean_embeddings = sum_embeddings / sum_mask
        return mean_embeddings

def parse_args():
    parser = argparse.ArgumentParser(description="Export a pre-trained sentence-transformer to quantized ONNX format.")
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Directory to save the exported ONNX model files."
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        help="Pretrained multilingual model path or ID."
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Loading tokenizer and model: {args.embedding_model}...")
    tokenizer = AutoTokenizer.from_pretrained(args.embedding_model)
    base_model = AutoModel.from_pretrained(args.embedding_model)
    
    # Wrap model with pooling layer
    embedding_pipeline = SentenceEmbeddingPipeline(base_model)
    embedding_pipeline.eval()  # Put in evaluation mode
    
    # Create dummy inputs for ONNX export tracing
    dummy_text = "Subject: Hello World\nThis is a test email message for ONNX tracing."
    inputs = tokenizer(
        dummy_text,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512
    )
    
    input_ids = inputs["input_ids"]
    attention_mask = inputs["attention_mask"]
    
    onnx_filename = "model.onnx"
    quantized_filename = "model_quantized.onnx"
    
    onnx_path = os.path.join(args.output_dir, onnx_filename)
    quantized_path = os.path.join(args.output_dir, quantized_filename)
    
    print(f"Exporting model to ONNX at: {onnx_path}...")
    
    # Export using PyTorch's ONNX export
    torch.onnx.export(
        embedding_pipeline,
        args=(input_ids, attention_mask),
        f=onnx_path,
        input_names=["input_ids", "attention_mask"],
        output_names=["embeddings"],
        dynamic_axes={
            "input_ids": {0: "batch_size", 1: "sequence_length"},
            "attention_mask": {0: "batch_size", 1: "sequence_length"},
            "embeddings": {0: "batch_size"}
        },
        opset_version=14,
        do_constant_folding=True
    )
    
    # Save the tokenizer files to the same directory so the deployment runner on the Pi has access to them
    print(f"Saving tokenizer files to {args.output_dir}...")
    tokenizer.save_pretrained(args.output_dir)
    
    print("Verifying exported ONNX model...")
    try:
        onnx_model = onnx.load(onnx_path)
        onnx.checker.check_model(onnx_model)
        print("ONNX model verification succeeded.")
    except Exception as e:
        print(f"Error: ONNX model verification failed: {e}")
        sys.exit(1)
        
    print(f"Applying Post-Training INT8 Dynamic Quantization to: {quantized_path}...")
    try:
        quantize_dynamic(
            model_input=onnx_path,
            model_output=quantized_path,
            weight_type=QuantType.QUInt8
        )
        
        orig_size_mb = os.path.getsize(onnx_path) / (1024 * 1024)
        quant_size_mb = os.path.getsize(quantized_path) / (1024 * 1024)
        
        print("========================================================================")
        echo_str = "ONNX Export and Quantization Complete!\n"
        echo_str += f"Original ONNX Model Size:  {orig_size_mb:.2f} MB\n"
        echo_str += f"Quantized ONNX Model Size: {quant_size_mb:.2f} MB (Shrunk by {((orig_size_mb - quant_size_mb)/orig_size_mb)*100:.1f}%!)"
        print(echo_str)
        print("========================================================================")
    except Exception as e:
        print(f"Error: Quantization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
