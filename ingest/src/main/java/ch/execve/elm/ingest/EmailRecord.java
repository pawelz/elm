package ch.execve.elm.ingest;

import com.google.common.collect.ImmutableList;

/**
 * Represents the structured JSON output schema for preprocessed emails.
 */
public record EmailRecord(
    String subject,
    String body,
    ImmutableList<Float> metadata_features,
    int label
) {}
