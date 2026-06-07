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
#include <sys/socket.h>
#include <sys/un.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/time.h>
#include <getopt.h>
#include <errno.h>

#include "libmaildir.h"


int main(int argc, char **argv) {
    char *socket_path = NULL;
    char *maildir_path = NULL;
    char *threshold_str = NULL;
    double threshold = 0.50;
    int filter_mode = 0;

    static struct option long_options[] = {
        {"socket", required_argument, 0, 's'},
        {"maildir", required_argument, 0, 'm'},
        {"threshold", required_argument, 0, 't'},
        {"filter", no_argument, 0, 'f'},
        {"help", no_argument, 0, 'h'},
        {0, 0, 0, 0}
    };

    int opt;
    int option_index = 0;
    while ((opt = getopt_long(argc, argv, "s:m:t:fh", long_options, &option_index)) != -1) {
        switch (opt) {
            case 's':
                socket_path = optarg;
                break;
            case 'm':
                maildir_path = optarg;
                break;
            case 't':
                threshold_str = optarg;
                break;
            case 'f':
                filter_mode = 1;
                break;
            case 'h':
                printf("Usage: %s [options]\n", argv[0]);
                printf("Options:\n");
                printf("  -s, --socket <path>     Path to the UNIX domain socket (required)\n");
                printf("  -m, --maildir <path>    Base path to the Maildir (required unless --filter is used)\n");
                printf("  -t, --threshold <val>   Spam classification threshold (default: 0.50)\n");
                printf("  -f, --filter            Filter mode: add headers to stdout and exit 0 (ideal for maildrop/exim)\n");
                printf("  -h, --help              Show this help message\n");
                return 0;
            default:
                fprintf(stderr, "Try '%s --help' for more information.\n", argv[0]);
                return 1;
        }
    }

    if (socket_path == NULL) {
        fprintf(stderr, "Error: --socket (-s) is required.\n");
        fprintf(stderr, "Try '%s --help' for more information.\n", argv[0]);
        return 1;
    }

    if (!filter_mode && maildir_path == NULL) {
        fprintf(stderr, "Error: either --maildir (-m) or --filter (-f) must be specified.\n");
        fprintf(stderr, "Try '%s --help' for more information.\n", argv[0]);
        return 1;
    }

    if (threshold_str != NULL) {
        char *endptr;
        threshold = strtod(threshold_str, &endptr);
        if (*endptr != '\0' || threshold < 0.0 || threshold > 1.0) {
            fprintf(stderr, "Invalid threshold parameter: %s. Must be a float between 0.0 and 1.0.\n", threshold_str);
            return 1;
        }
    }

    // 1. Read the entire email from stdin into a buffer.
    char *email_buffer = NULL;
    size_t email_buffer_size = 0;
    FILE *email_stream = open_memstream(&email_buffer, &email_buffer_size);
    if (email_stream == NULL) {
        perror("open_memstream failed");
        return 1;
    }

    char *line_buffer = NULL;
    size_t line_buffer_size = 0;
    ssize_t bytes_read;
    while ((bytes_read = getline(&line_buffer, &line_buffer_size, stdin)) != -1) {
        fwrite(line_buffer, 1, bytes_read, email_stream);
    }
    fclose(email_stream);
    free(line_buffer);

    int sockfd;
    struct sockaddr_un addr;
    sockfd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sockfd == -1) {
        if (filter_mode) {
            printf("X-Spam-Status: Error, score=0.0000, threshold=%.4f, error=\"socket error: %s\"\n", threshold, strerror(errno));
            printf("X-Spam-Score: 0.0000\n");
            printf("X-Spam-Threshold: %.4f\n", threshold);
            fwrite(email_buffer, 1, email_buffer_size, stdout);
            free(email_buffer);
            return 0;
        } else {
            fprintf(stderr, "socket error (%s): ", socket_path);
            perror(NULL);
            free(email_buffer);
            return 1;
        }
    }

    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, socket_path, sizeof(addr.sun_path) - 1);

    if (connect(sockfd, (struct sockaddr*)&addr, sizeof(addr)) == -1) {
        if (filter_mode) {
            printf("X-Spam-Status: Error, score=0.0000, threshold=%.4f, error=\"connect error: %s\"\n", threshold, strerror(errno));
            printf("X-Spam-Score: 0.0000\n");
            printf("X-Spam-Threshold: %.4f\n", threshold);
            fwrite(email_buffer, 1, email_buffer_size, stdout);
            close(sockfd);
            free(email_buffer);
            return 0;
        } else {
            fprintf(stderr, "connect error (%s): ", socket_path);
            perror(NULL);
            close(sockfd);
            free(email_buffer);
            return 1;
        }
    }

    // Set a 3-second timeout for receiving data.
    struct timeval tv;
    tv.tv_sec = 3;
    tv.tv_usec = 0;
    if (setsockopt(sockfd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)) < 0) {
        perror("setsockopt failed");
        close(sockfd);
        free(email_buffer);
        return 1;
    }

    // 2. Send the buffered email to the server.
    if (send(sockfd, email_buffer, email_buffer_size, 0) == -1) {
        if (filter_mode) {
            printf("X-Spam-Status: Error, score=0.0000, threshold=%.4f, error=\"send error: %s\"\n", threshold, strerror(errno));
            printf("X-Spam-Score: 0.0000\n");
            printf("X-Spam-Threshold: %.4f\n", threshold);
            fwrite(email_buffer, 1, email_buffer_size, stdout);
            close(sockfd);
            free(email_buffer);
            return 0;
        } else {
            perror("send error");
            close(sockfd);
            free(email_buffer);
            return 1;
        }
    }

    // 3. Shutdown the "write" part of the connection.
    shutdown(sockfd, SHUT_WR);

    // 4. Receive the spam score from the server.
    char response_buffer[1024];
    ssize_t response_bytes = recv(sockfd, response_buffer, sizeof(response_buffer) - 1, 0);
    if (response_bytes == -1) {
        if (filter_mode) {
            printf("X-Spam-Status: Error, score=0.0000, threshold=%.4f, error=\"recv error: %s\"\n", threshold, strerror(errno));
            printf("X-Spam-Score: 0.0000\n");
            printf("X-Spam-Threshold: %.4f\n", threshold);
            fwrite(email_buffer, 1, email_buffer_size, stdout);
        } else {
            perror("recv error");
        }
    } else if (response_bytes > 0) {
        response_buffer[response_bytes] = '\0';

        // Strip any trailing whitespace/newlines
        char *end = response_buffer + response_bytes - 1;
        while (end >= response_buffer && (*end == '\r' || *end == '\n' || *end == ' ' || *end == '\t')) {
            *end = '\0';
            end--;
        }

        char *score_endptr;
        double score = strtod(response_buffer, &score_endptr);
        if (score_endptr == response_buffer || score < 0.0 || score > 1.0) {
            if (filter_mode) {
                printf("X-Spam-Status: Error, score=0.0000, threshold=%.4f, error=\"invalid score: %s\"\n", threshold, response_buffer);
                printf("X-Spam-Score: 0.0000\n");
                printf("X-Spam-Threshold: %.4f\n", threshold);
                fwrite(email_buffer, 1, email_buffer_size, stdout);
            } else {
                fprintf(stderr, "Invalid score received from server: %s\n", response_buffer);
            }
            close(sockfd);
            free(email_buffer);
            return filter_mode ? 0 : 1;
        }

        if (filter_mode) {
            printf("X-Spam-Status: %s, score=%.4f, threshold=%.4f\n", (score >= threshold) ? "Yes" : "No", score, threshold);
            printf("X-Spam-Score: %.4f\n", score);
            printf("X-Spam-Threshold: %.4f\n", threshold);
            fwrite(email_buffer, 1, email_buffer_size, stdout);
        } else {
            // Determine spam or ham based on user threshold
            const char *folder_name = (score >= threshold) ? "spam" : "ham";

            size_t full_path_size = strlen(maildir_path) + 1 + strlen(folder_name) + 1;
            char *full_maildir_path = malloc(full_path_size);
            if (full_maildir_path == NULL) {
                perror("malloc for full_maildir_path failed");
                close(sockfd);
                free(email_buffer);
                return 1;
            }

            snprintf(full_maildir_path, full_path_size, "%s/%s", maildir_path, folder_name);

            if (deliver_to_maildir(full_maildir_path, email_buffer, email_buffer_size) != 0) {
                fprintf(stderr, "maildir_deliver failed for path: %s\n", full_maildir_path);
                free(full_maildir_path);
                close(sockfd);
                free(email_buffer);
                return 1;
            } else {
                printf("Delivered to: %s (score: %.4f, threshold: %.4f)\n", full_maildir_path, score, threshold);
            }

            free(full_maildir_path);
        }
    } else {
        if (filter_mode) {
            printf("X-Spam-Status: Error, score=0.0000, threshold=%.4f, error=\"empty response\"\n", threshold);
            printf("X-Spam-Score: 0.0000\n");
            printf("X-Spam-Threshold: %.4f\n", threshold);
            fwrite(email_buffer, 1, email_buffer_size, stdout);
        } else {
            fprintf(stderr, "Empty response received from server.\n");
        }
    }

    close(sockfd);
    free(email_buffer);

    return 0;
}
