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

package ch.execve.elm.serving;

import ch.execve.elm.core.EmailParser;
import ch.execve.elm.core.EmailRecord;
import jakarta.mail.Session;
import jakarta.mail.internet.MimeMessage;
import picocli.CommandLine;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.StandardProtocolFamily;
import java.net.UnixDomainSocketAddress;
import java.nio.channels.Channels;
import java.nio.channels.ServerSocketChannel;
import java.nio.channels.SocketChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Properties;
import java.util.concurrent.Callable;

/**
 * Modern UNIX domain socket server that listens for raw email submissions,
 * parses them using the core EmailParser, runs spam classification, and
 * returns the verdict probability as a float.
 */
@Command(
    name = "elm-server",
    mixinStandardHelpOptions = true,
    version = "1.0.0",
    description = "Listens on a UNIX domain socket, parses incoming emails, and returns a spam probability verdict."
)
public class ElmServer implements Callable<Integer> {

    @Option(names = {"-s", "--socket"}, description = "Path to the UNIX domain socket file", required = true)
    private File socketFile;

    @Override
    public Integer call() throws Exception {
        Path socketPath = socketFile.toPath();

        // 1. Delete pre-existing socket file if it exists
        if (Files.exists(socketPath)) {
            System.out.printf("Deleting pre-existing socket file: %s%n", socketPath);
            Files.delete(socketPath);
        }

        // 2. Ensure parent directory of socket exists
        Path parentDir = socketPath.getParent();
        if (parentDir != null && !Files.exists(parentDir)) {
            Files.createDirectories(parentDir);
        }

        // 3. Initialize JavaMail Session for raw parsing
        Properties props = new Properties();
        Session session = Session.getDefaultInstance(props, null);

        UnixDomainSocketAddress address = UnixDomainSocketAddress.of(socketPath);

        System.out.printf("Starting ElmServer. Listening on UNIX socket: %s...%n", socketPath);

        // 4. Bind Server Socket
        try (ServerSocketChannel serverChannel = ServerSocketChannel.open(StandardProtocolFamily.UNIX)) {
            serverChannel.bind(address);

            // Add a shutdown hook to clean up the socket file when the server exits
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                try {
                    if (Files.exists(socketPath)) {
                        Files.delete(socketPath);
                        System.out.println("Cleaned up UNIX socket file.");
                    }
                } catch (IOException e) {
                    System.err.printf("Error cleaning up socket file: %s%n", e.getMessage());
                }
            }));

            // 5. Connection Accept Loop
            while (true) {
                try (SocketChannel clientChannel = serverChannel.accept()) {
                    handleConnection(clientChannel, session);
                } catch (Exception e) {
                    System.err.printf("Error handling client connection: %s%n", e.getMessage());
                }
            }
        }
    }

    /**
     * Handles an incoming client connection, reading the raw email bytes until EOF,
     * parsing it, calculating the verdict, and writing back the float probability.
     */
    private void handleConnection(SocketChannel clientChannel, Session session) throws IOException {
        InputStream is = Channels.newInputStream(clientChannel);
        OutputStream os = Channels.newOutputStream(clientChannel);

        // 1. Read entire incoming stream into memory buffer (until client closes its write half/sends EOF)
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] readBuffer = new byte[4096];
        int bytesRead;
        while ((bytesRead = is.read(readBuffer)) != -1) {
            buffer.write(readBuffer, 0, bytesRead);
        }

        byte[] rawEmailBytes = buffer.toByteArray();
        if (rawEmailBytes.length == 0) {
            System.err.println("Received empty stream connection. Skipping.");
            return;
        }

        // 2. Parse MIME email using core EmailParser
        EmailRecord record;
        try (ByteArrayInputStream bais = new ByteArrayInputStream(rawEmailBytes)) {
            MimeMessage message = new MimeMessage(session, bais);
            record = EmailParser.parse(message, 0);
        } catch (Exception e) {
            System.err.printf("Error: Failed to parse raw email: %s%n", e.getMessage());
            // Write default error response and return
            os.write("0.50".getBytes());
            os.flush();
            return;
        }

        // 3. Compute verdict (spam probability float)
        float score = predict(record);

        // 4. Format and respond with the EXACT float string, NO trailing newlines
        String response = String.format("%.4f", score);
        System.out.printf("Received email. Subject: '%s' | Prediction: %s%n", record.subject(), response);

        os.write(response.getBytes());
        os.flush();
    }

    /**
     * Rule-based prediction model (verdict engine).
     * This will be extended to load and evaluate the actual machine learning model weights.
     */
    private float predict(EmailRecord record) {
        String combined = (record.subject() + " " + record.body()).toLowerCase();

        // High confidence spam keywords
        if (combined.contains("cheap replica") ||
            combined.contains("replica watches") ||
            combined.contains("click here to buy") ||
            combined.contains("sale ends soon") ||
            combined.contains("get cheap") ||
            combined.contains("winner of our lottery")) {
            return 0.985f;
        }

        // Medium confidence spam keywords
        if (combined.contains("limited offer") ||
            combined.contains("extra income") ||
            combined.contains("earn cash") ||
            combined.contains("make money online")) {
            return 0.75f;
        }

        // Default: highly likely ham
        return 0.015f;
    }

    public static void main(String[] args) {
        int exitCode = new CommandLine(new ElmServer()).execute(args);
        System.exit(exitCode);
    }
}
