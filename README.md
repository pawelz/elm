# Elm: Personal Email Spam Classifier

Elm is a highly private, local machine learning solution that allows you to train and deploy a custom spam-filtering model based entirely on your own personal email corpus. 

Instead of relying on generic public filters or cloud-based classification services, Elm processes your unique email communication history locally, building a tailored model optimized specifically for your personal inbox.

---

## Key Highlights

*   **Privacy-First & Local:** Your email data never leaves your machine. Training, quantization, and inference run completely offline.
*   **Hybrid Feature Representation:** Combines rich semantic text embeddings (via multilingual Sentence Transformers) with standard tabular metadata features.
*   **Lightweight Deployment:** Leverages post-training INT8 quantization and ONNX Runtime execution, making the model fast enough to run seamlessly on low-power hardware (such as a Raspberry Pi).
*   **Structured Architecture:**
    *   **`ingest/`**: A high-performance Java pipeline designed to parse, decode, strip URLs, and cleanly process raw email structures (Maildir format) into structured dataset JSONL records.
    *   **`training/`**: A Python pipeline to extract embeddings, train a custom classifier, export the pipeline to ONNX, and run accelerated local inference.

---

## Documentation & Usage

For detailed design specifications, implementation details, and step-by-step instructions on how to set up the ingestion pipeline, train your classifier, and run local inference, please refer to the comprehensive guides in the `docs/` directory:

*   [Training Pipeline Documentation](docs/training.md) — Step-by-step guide to data preparation, training, exporting, and inference.
*   [Technical Implementation Plan](docs/training-pipeline-implementation-plan.md) — Deep-dive into architecture choices, quantization strategies, and schema definitions.

---

## License

This project is open-source software released under the [Apache License 2.0](LICENSE.txt).

Copyright &copy; 2026 Paweł Zuzelski
