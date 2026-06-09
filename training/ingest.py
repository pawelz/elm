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
import sys

from core import email_parser

def scan_paths(paths):
    """Scans list of paths for files, handling both files and directories recursively."""
    all_files = []
    # Normalize paths: they can be comma-separated strings inside list elements
    normalized_paths = []
    for p in paths:
        if "," in p:
            normalized_paths.extend(p.split(","))
        else:
            normalized_paths.append(p)

    for path in normalized_paths:
        path = path.strip()
        if not path:
            continue
        if os.path.isfile(path):
            all_files.append(path)
        elif os.path.isdir(path):
            for root, dirs, filenames in os.walk(path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in filenames:
                    if not f.startswith('.'):
                        all_files.append(os.path.join(root, f))
        else:
            print(f"Warning: Path not found: {path}", file=sys.stderr)
    return all_files

def main():
    parser = argparse.ArgumentParser(description="Ingest good and bad emails into a training JSONL dataset.")
    parser.add_argument("-g", "--good", nargs="+", required=True, help="List of good email files/directories or comma-separated paths.")
    parser.add_argument("-b", "--bad", nargs="+", required=True, help="List of bad email files/directories or comma-separated paths.")
    parser.add_argument("-o", "--output", required=True, help="Path to write the parsed JSONL dataset.")

    args = parser.parse_args()

    good_files = scan_paths(args.good)
    bad_files = scan_paths(args.bad)

    print(f"Found {len(good_files)} good and {len(bad_files)} bad email files.")

    total_processed = 0
    errors = 0

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as out_f:
        # Process good emails (label = 0)
        for idx, file_path in enumerate(good_files, 1):
            try:
                with open(file_path, "rb") as f:
                    raw_bytes = f.read()
                record = email_parser.parse(raw_bytes, label=0)
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_processed += 1
                if idx % 500 == 0 or idx == len(good_files):
                    print(f"Processed good: {idx}/{len(good_files)}...", flush=True)
            except Exception as e:
                print(f"Error parsing good file {file_path}: {e}", file=sys.stderr)
                errors += 1

        # Process bad emails (label = 1)
        for idx, file_path in enumerate(bad_files, 1):
            try:
                with open(file_path, "rb") as f:
                    raw_bytes = f.read()
                record = email_parser.parse(raw_bytes, label=1)
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_processed += 1
                if idx % 500 == 0 or idx == len(bad_files):
                    print(f"Processed bad: {idx}/{len(bad_files)}...", flush=True)
            except Exception as e:
                print(f"Error parsing bad file {file_path}: {e}", file=sys.stderr)
                errors += 1

    print(f"Ingestion complete. Output written to {args.output}")
    print(f"Successfully processed: {total_processed} emails. Errors: {errors}")

if __name__ == "__main__":
    main()
