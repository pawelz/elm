# Implementation Plan: Client Deployment & Exim4 Pipeline Integration

This document outlines the design and integration plan for running the real-time spam-filtering system in a production mail environment using Exim4, Maildrop, and our C socket client in **Filter Mode**.

---

## Architectural Overview

The system uses a pipeline model where Exim4 acts as the MTA, pipes incoming emails through the C client to inject classification headers, and then delivers the decorated email to Maildrop (the MDA).

```mermaid
graph TD
    A["Internet / SMTP"] --> B["Exim4 (MTA)"]
    subgraph "Exim4 Transport Pipeline"
        B --> C["C Client (Filter Mode)"]
        C -->|1. Query MIME| D["ElmServer (JVM Service)"]
        D -->|2. Return Score| C
        C -->|3. Inject Headers| E["Maildrop (MDA)"]
    end
    E -->|4. if X-Spam-Status: Yes| F["Maildir/.Spam/"]
    E -->|5. Else (Ham)| G["Maildir/ (Inbox)"]

    style D fill:#2d3748,stroke:#4a5568,stroke-width:2px,color:#fff
    style C fill:#1a365d,stroke:#2b6cb0,stroke-width:2px,color:#fff
```

---

## Components

### 1. C Client (`client/client.c`) [MODIFIED]
The C client has been upgraded with a native `--filter` (or `-f`) flag. This mode makes it fully compatible with Unix pipe standards (reading from `stdin`, querying the socket, prepending status headers, and outputting to `stdout`).

#### Robustness and Fail-Safe Fallbacks
Because email delivery is critical, the client handles socket failures gracefully:
* If the Java server is down, crashes, or a timeout occurs, the client writes a failure header (`X-Spam-Status: Error, ...`) and outputs the complete email unmodified with exit code `0`.
* This ensures that **no email will ever be lost or bounced** due to a spam-filtering service interruption.

### 2. Java Server (`ElmServer`) [DEPLOYABLE]
The Java server is built as a self-contained, executable "deploy" fat JAR containing all necessary dependencies:
```bash
bazel build //java/ch/execve/elm/serving:serving_server_deploy.jar
```
It is designed to run as a background service managed by `systemd`.

---

## Proposed Changes

We will introduce two documentation guides to provide clear paths to production deployment:

### 1. [NEW] [exim4-setup.md](file:///Users/pawelz/git/elm/docs/exim4-setup.md)
A comprehensive guide outlining step-by-step instructions for:
* Building the deployable artifact.
* Setting up the systemd service.
* Managing secure directory permissions for UNIX domain sockets.
* Configuring Exim4 via its `transport_filter` pipeline.
* Setting up Maildrop (`~/.mailfilter`) for shadow (dry-run) and production modes.

### 2. [NEW] [serving-implementation-plan.md](file:///Users/pawelz/git/elm/docs/serving-implementation-plan.md)
*This document.*

---

## Verification Plan

### Stage 1: Local Loopback Testing
1. Compile the C client and verify the standard `--filter` response when the server is offline:
   ```bash
   echo "Subject: Test" | ./bazel-bin/client/client --socket /tmp/nonexistent.sock --filter
   ```
2. Start the local server and verify the output contains active scores:
   ```bash
   # Start server
   bazel run //java/ch/execve/elm/serving:serving_server -- --socket /tmp/elm_test.sock &
   # Query with C client
   echo "Subject: replica watches" | ./bazel-bin/client/client --socket /tmp/elm_test.sock --filter
   ```

### Stage 2: Shadow Deployment (Dry-Run Mode)
To ensure the model is classifying mail correctly before automating any folder actions:
1. Wire up Exim4 with the `transport_filter` pipeline.
2. Observe delivered mail in your regular inbox. Every email should now contain custom headers like:
   ```rfc822
   X-Spam-Status: No, score=0.0150, threshold=0.5000
   X-Spam-Score: 0.0150
   X-Spam-Threshold: 0.5000
   ```
3. Audit your mailbox to verify that no real emails receive high scores (false positives).

### Stage 3: Full Production Mode
1. Update `~/.mailfilter` to check the `X-Spam-Status: Yes` header and deliver it directly to the designated spam Maildir.
