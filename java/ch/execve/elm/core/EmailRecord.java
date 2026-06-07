/*
 * Copyright 2026 Paweł Zuzelski
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package ch.execve.elm.core;

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
