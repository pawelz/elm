// Copyright 2026 Paweł Zuzelski
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <stdio.h>
#include <sys/stat.h>
#include <errno.h>
#include <unistd.h>
#include <time.h>
#include <stdlib.h>
#include <string.h>

/**
 * Recursively creates a directory path, similar to `mkdir -p`.
 * @param path The full directory path to create.
 * @return 0 on success, -1 on failure.
 */
static int mkdir_p(const char *path) {
    char *p, *path_copy;

    // Make a copy of the path because we will be modifying it.
    path_copy = strdup(path);
    if (path_copy == NULL) {
        perror("strdup failed");
        return -1;
    }

    // Iterate over the path, creating each component.
    // Start from p = path_copy + 1 to skip the leading '/'.
    for (p = path_copy + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0'; // Temporarily truncate the string.
            if (mkdir(path_copy, 0700) != 0 && errno != EEXIST) {
                free(path_copy);
                return -1;
            }
            *p = '/'; // Restore the slash.
        }
    }

    // Create the final directory.
    if (mkdir(path_copy, 0700) != 0 && errno != EEXIST) {
        free(path_copy);
        return -1;
    }

    free(path_copy);
    return 0;
}

int deliver_to_maildir(const char *maildir_path, const char *email_buffer, size_t email_buffer_size) {
    int ret = -1; // Default return value is error

    size_t maildir_path_len = strlen(maildir_path);
    size_t tmp_path_len = maildir_path_len + 5; // /tmp + \0
    size_t new_path_len = maildir_path_len + 5; // /new + \0
    size_t cur_path_len = maildir_path_len + 5; // /cur + \0

    char *tmp_path = malloc(tmp_path_len);
    char *new_path = malloc(new_path_len);
    char *cur_path = malloc(cur_path_len);

    if (!tmp_path || !new_path || !cur_path) {
        perror("malloc for subdirectories failed");
        goto cleanup;
    }

    snprintf(tmp_path, tmp_path_len, "%s/tmp", maildir_path);
    snprintf(new_path, new_path_len, "%s/new", maildir_path);
    snprintf(cur_path, cur_path_len, "%s/cur", maildir_path);

    // Ensure the entire directory path exists.
    if (mkdir_p(maildir_path) != 0) {
        goto cleanup;
    }
    if ((mkdir(tmp_path, 0700) && errno != EEXIST) ||
        (mkdir(new_path, 0700) && errno != EEXIST) ||
        (mkdir(cur_path, 0700) && errno != EEXIST)) {
        goto cleanup;
    }

    // 1. Generate a unique filename: timestamp.pid.hostname
    long host_name_max = sysconf(_SC_HOST_NAME_MAX);
    if (host_name_max == -1) host_name_max = 255; // POSIX fallback
    char *hostname = malloc(host_name_max + 1);
    if (!hostname) {
        perror("malloc for hostname failed");
        goto cleanup;
    }
    gethostname(hostname, host_name_max + 1);

    // Allocate space for unique name: time + '.' + pid + '.' + hostname + '\0'
    // 20 for time, 10 for pid, should be plenty.
    size_t unique_name_len = 20 + 1 + 10 + 1 + strlen(hostname) + 1;
    char *unique_name = malloc(unique_name_len);
    if (!unique_name) {
        perror("malloc for unique_name failed");
        free(hostname);
        goto cleanup;
    }
    snprintf(unique_name, unique_name_len, "%ld.%d.%s", (long)time(NULL), getpid(), hostname);
    free(hostname);

    size_t tmp_file_path_len = tmp_path_len + strlen(unique_name) + 1;
    char *tmp_file_path = malloc(tmp_file_path_len);
    if (!tmp_file_path) {
        perror("malloc for tmp_file_path failed");
        free(unique_name);
        goto cleanup;
    }
    snprintf(tmp_file_path, tmp_file_path_len, "%s/%s", tmp_path, unique_name);

    // 2. Write the email to the temporary file.
    FILE *fp = fopen(tmp_file_path, "w");
    if (!fp) {
        perror("fopen tmp file failed");
        free(unique_name);
        free(tmp_file_path);
        goto cleanup;
    }
    fwrite(email_buffer, 1, email_buffer_size, fp);
    fclose(fp);

    // 3. Atomically move the file to the 'new' directory.
    size_t new_file_path_len = new_path_len + strlen(unique_name) + 1;
    char *new_file_path = malloc(new_file_path_len);
    if (!new_file_path) {
        perror("malloc for new_file_path failed");
        free(unique_name);
        free(tmp_file_path);
        goto cleanup;
    }
    snprintf(new_file_path, new_file_path_len, "%s/%s", new_path, unique_name);

    if (rename(tmp_file_path, new_file_path) != 0) {
        perror("rename to new failed");
    } else {
        ret = 0;
    }

    free(unique_name);
    free(tmp_file_path);
    free(new_file_path);

cleanup:
    free(tmp_path);
    free(new_path);
    free(cur_path);
    return ret;
}