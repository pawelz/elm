package ch.execve.elm.ingest;

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
    description = "Parses a Maildir, preprocesses emails, and outputs a JSONL file for ML pipelines."
)
public class IngestPipeline implements Callable<Integer> {

    @Option(names = {"-i", "--input"}, description = "Path to the Maildir input directory", required = true)
    private File maildir;

    @Option(names = {"-o", "--output"}, description = "Path to the output JSONL file", required = true)
    private File outputFile;

    @Option(names = {"-l", "--label"}, description = "Label to assign to all emails (0 or 1)", required = true)
    private int label;

    @Override
    public Integer call() {
        // Validate label
        if (label != 0 && label != 1) {
            System.err.printf("Error: Invalid label %d. Label must be 0 or 1.%n", label);
            return 1;
        }

        // Validate Maildir
        if (!maildir.exists() || !maildir.isDirectory()) {
            System.err.printf("Error: Input path '%s' does not exist or is not a directory.%n", maildir.getAbsolutePath());
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

        // Scan for email files
        List<File> emailFiles = scanMaildir(maildir);
        System.out.printf("Scanning '%s'... Found %d email file(s) to process.%n", maildir.getAbsolutePath(), emailFiles.size());

        if (emailFiles.isEmpty()) {
            System.out.println("No email files to process. Exiting.");
            return 0;
        }

        // Initialize session and object mapper
        Properties props = new Properties();
        Session session = Session.getDefaultInstance(props, null);
        ObjectMapper mapper = new ObjectMapper();

        int successCount = 0;
        int failureCount = 0;

        try (BufferedWriter writer = new BufferedWriter(new FileWriter(outputFile))) {
            for (File file : emailFiles) {
                try (FileInputStream fis = new FileInputStream(file)) {
                    MimeMessage message = new MimeMessage(session, fis);
                    EmailRecord record = EmailParser.parse(message, label);

                    // Serialize to JSON and write as a single line
                    String jsonLine = mapper.writeValueAsString(record);
                    writer.write(jsonLine);
                    writer.newLine();
                    successCount++;
                } catch (Exception e) {
                    System.err.printf("Warning: Failed to process email file '%s': %s%n", file.getName(), e.getMessage());
                    failureCount++;
                }
            }
            writer.flush();
        } catch (IOException e) {
            System.err.printf("Error writing to output file '%s': %s%n", outputFile.getAbsolutePath(), e.getMessage());
            return 1;
        }

        System.out.println("Ingestion pipeline finished successfully.");
        System.out.printf("Summary: %d processed, %d failed.%n", successCount, failureCount);
        return 0;
    }

    /**
     * Scans Maildir for email files, looking under cur/ and new/ folders with a flat fallback.
     */
    private static List<File> scanMaildir(File maildir) {
        List<File> emailFiles = new ArrayList<>();
        File curDir = new File(maildir, "cur");
        File newDir = new File(maildir, "new");

        // Scan cur/ directory
        if (curDir.exists() && curDir.isDirectory()) {
            addFilesFromDir(curDir, emailFiles);
        }

        // Scan new/ directory
        if (newDir.exists() && newDir.isDirectory()) {
            addFilesFromDir(newDir, emailFiles);
        }

        // Fallback: If no files found under standard Maildir layout, check flat root directory
        if (emailFiles.isEmpty()) {
            addFilesFromDir(maildir, emailFiles);
        }

        return emailFiles;
    }

    private static void addFilesFromDir(File dir, List<File> list) {
        File[] files = dir.listFiles();
        if (files != null) {
            for (File f : files) {
                // Ignore subdirectories and hidden/system files starting with "."
                if (f.isFile() && !f.getName().startsWith(".")) {
                    list.add(f);
                }
            }
        }
    }

    public static void main(String[] args) {
        int exitCode = new CommandLine(new IngestPipeline()).execute(args);
        System.exit(exitCode);
    }
}
