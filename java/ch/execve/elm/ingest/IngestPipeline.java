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

package ch.execve.elm.ingest;

import ch.execve.elm.core.EmailParser;
import ch.execve.elm.core.EmailRecord;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.mail.Session;
import jakarta.mail.internet.MimeMessage;
import picocli.CommandLine;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileWriter;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;
import java.util.concurrent.Callable;

/**
 * Main command-line application that runs the email ingestion pipeline.
 */
@Command(
    name = "ingest-pipeline",
    mixinStandardHelpOptions = true,
    version = "1.0.0",
    description = "Parses good and bad flat directories, preprocesses emails, and outputs a single JSONL file."
)
public class IngestPipeline implements Callable<Integer> {

    @Option(names = {"-g", "--good"}, description = "Path to the local directory containing good emails", required = false)
    private File goodDir;

    @Option(names = {"-b", "--bad"}, description = "Path to the local directory containing bad emails", required = false)
    private File badDir;

    @Option(names = {"-o", "--output"}, description = "Path to the output JSONL file", required = true)
    private File outputFile;

    @Override
    public Integer call() {
        // Validate that at least one input directory is specified
        if (goodDir == null && badDir == null) {
            System.err.println("Error: At least one of --good or --bad must be specified.");
            return 1;
        }

        // Ensure parent of output file exists
        File parentDir = outputFile.getParentFile();
        if (parentDir != null && !parentDir.exists()) {
            if (!parentDir.mkdirs()) {
                System.err.printf("Error: Failed to create parent directory for output file '%s'.%n", outputFile.getAbsolutePath());
                return 1;
            }
        }

        // Initialize sessions and mapper
        Properties props = new Properties();
        Session session = Session.getDefaultInstance(props, null);
        ObjectMapper mapper = new ObjectMapper();

        int goodSuccessCount = 0;
        int badSuccessCount = 0;
        int failureCount = 0;

        try (BufferedWriter writer = new BufferedWriter(new FileWriter(outputFile))) {
            // Process good directory (Label = 0)
            if (goodDir != null) {
                if (!goodDir.exists() || !goodDir.isDirectory()) {
                    System.err.printf("Error: Good emails directory '%s' does not exist or is not a directory.%n", goodDir.getAbsolutePath());
                    return 1;
                }
                List<File> goodFiles = scanDirectory(goodDir);
                System.out.printf("Scanning good emails... Found %d file(s) in '%s'.%n", goodFiles.size(), goodDir.getAbsolutePath());

                for (File file : goodFiles) {
                    try (FileInputStream fis = new FileInputStream(file)) {
                        MimeMessage message = new MimeMessage(session, fis);
                        EmailRecord record = EmailParser.parse(message, 0); // 0 = Good

                        writer.write(mapper.writeValueAsString(record));
                        writer.newLine();
                        goodSuccessCount++;
                    } catch (Exception e) {
                        System.err.printf("Warning: Failed to process good email '%s': %s%n", file.getName(), e.getMessage());
                        failureCount++;
                    }
                }
            }

            // Process bad directory (Label = 1)
            if (badDir != null) {
                if (!badDir.exists() || !badDir.isDirectory()) {
                    System.err.printf("Error: Bad emails directory '%s' does not exist or is not a directory.%n", badDir.getAbsolutePath());
                    return 1;
                }
                List<File> badFiles = scanDirectory(badDir);
                System.out.printf("Scanning bad emails... Found %d file(s) in '%s'.%n", badFiles.size(), badDir.getAbsolutePath());

                for (File file : badFiles) {
                    try (FileInputStream fis = new FileInputStream(file)) {
                        MimeMessage message = new MimeMessage(session, fis);
                        EmailRecord record = EmailParser.parse(message, 1); // 1 = Bad

                        writer.write(mapper.writeValueAsString(record));
                        writer.newLine();
                        badSuccessCount++;
                    } catch (Exception e) {
                        System.err.printf("Warning: Failed to process bad email '%s': %s%n", file.getName(), e.getMessage());
                        failureCount++;
                    }
                }
            }

            writer.flush();
        } catch (IOException e) {
            System.err.printf("Error writing to output file '%s': %s%n", outputFile.getAbsolutePath(), e.getMessage());
            return 1;
        }

        System.out.println("Ingestion pipeline finished successfully.");
        System.out.printf("Summary: %d good parsed, %d bad parsed, %d failed.%n", goodSuccessCount, badSuccessCount, failureCount);
        return 0;
    }

    /**
     * Lists all regular, non-hidden files in the given directory.
     */
    private static List<File> scanDirectory(File dir) {
        List<File> list = new ArrayList<>();
        File[] files = dir.listFiles();
        if (files != null) {
            for (File f : files) {
                if (f.isFile() && !f.getName().startsWith(".")) {
                    list.add(f);
                }
            }
        }
        return list;
    }

    public static void main(String[] args) {
        int exitCode = new CommandLine(new IngestPipeline()).execute(args);
        System.exit(exitCode);
    }
}
