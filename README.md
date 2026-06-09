# Elm: Personal Email Spam Classifier

Elm is a highly private, local machine learning solution that allows you to train and deploy a custom spam-filtering model based entirely on your own personal email corpus. 

Instead of relying on generic public filters or cloud-based classification services, Elm processes your unique email communication history locally, building a tailored model optimized specifically for your personal inbox.

---

## Key Highlights

*   **Privacy-First & Local:** Your email data never leaves your machine. Training, quantization, and inference run completely offline.
*   **Hybrid Feature Representation:** Combines rich semantic text embeddings (via multilingual Sentence Transformers) with standard tabular metadata features.
*   **Lightweight Deployment:** Leverages post-training INT8 quantization and ONNX Runtime execution, making the model fast enough to run seamlessly on low-power hardware (such as a Raspberry Pi).
*   **Pure Python & C Stack:** Zero JVM or external service dependencies. High performance combined with complete architectural simplicity.

---

## Structured Architecture

*   **`core/`**: Shared, unified Python library containing standard email parser and HTML stripping logic. Used for both training ingestion and production serving to prevent any feature mismatch.
*   **`client/`**: Lightweight native C client designed to read an email stream from `stdin`, communicate with the daemon via socket, prepend classification headers to `stdout`, and stream back the unaltered email body.
*   **`serving/`**: High-performance UNIX domain socket server daemon written in pure Python using concurrent threading.
*   **`training/`**: A Python pipeline to ingest raw Maildirs, extract embeddings, train a custom classifier, and export the sentence transformer model to quantized ONNX.
*   **`pkg/`**: Bazel packaging rules that bundle the client, daemon, and systemd configurations into a lightweight, hermetic `.deb` package.

---

## Documentation & Usage

For a concise, step-by-step walkthrough of how to ingest your data, train the classifier, build the package, and deploy the entire system, please refer to the comprehensive reference guide:

*   **[Quick Reference Guide](docs/quick-reference.md)** — Core step-by-step commands to build, train, and deploy.

---

## License

This project is open-source software released under the [Apache License 2.0](LICENSE.txt).

Copyright &copy; 2026 Paweł Zuzelski
