package ch.execve.elm.ingest;

import jakarta.mail.BodyPart;
import jakarta.mail.MessagingException;
import jakarta.mail.Multipart;
import jakarta.mail.Part;
import jakarta.mail.internet.ContentType;
import jakarta.mail.internet.MimeMessage;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.stream.Collectors;

/**
 * Handles MIME email parsing, decoding, alternative resolution, and HTML stripping.
 */
public class EmailParser {

    /**
     * Parses a raw MIME message and returns an EmailRecord.
     */
    public static EmailRecord parse(MimeMessage message, int label) throws MessagingException, IOException {
        String subject = message.getSubject();
        if (subject == null) {
            subject = "";
        }

        String body = extractBody(message);
        if (body == null) {
            body = "";
        } else {
            body = body.trim();
        }

        return new EmailRecord(subject, body, com.google.common.collect.ImmutableList.of(), label);
    }

    /**
     * Recursively extracts the plain-text body of a Part, ignoring attachments.
     */
    public static String extractBody(Part part) throws MessagingException, IOException {
        // If it's an attachment, skip
        if (Part.ATTACHMENT.equalsIgnoreCase(part.getDisposition()) || part.getFileName() != null) {
            return null;
        }

        if (part.isMimeType("text/plain")) {
            Object content = part.getContent();
            if (content instanceof String) {
                return (String) content;
            } else if (content instanceof InputStream) {
                return readInputStream((InputStream) content, part.getContentType());
            }
        } else if (part.isMimeType("text/html")) {
            Object content = part.getContent();
            String html;
            if (content instanceof String) {
                html = (String) content;
            } else if (content instanceof InputStream) {
                html = readInputStream((InputStream) content, part.getContentType());
            } else {
                html = "";
            }
            return htmlToText(html);
        } else if (part.isMimeType("multipart/alternative")) {
            Multipart multipart = (Multipart) part.getContent();
            String plainText = null;
            String htmlText = null;

            for (int i = 0; i < multipart.getCount(); i++) {
                BodyPart bodyPart = multipart.getBodyPart(i);
                if (bodyPart.isMimeType("text/plain")) {
                    plainText = extractBody(bodyPart);
                } else if (bodyPart.isMimeType("text/html")) {
                    htmlText = extractBody(bodyPart);
                } else if (bodyPart.isMimeType("multipart/*")) {
                    String content = extractBody(bodyPart);
                    if (content != null && !content.trim().isEmpty()) {
                        if (bodyPart.isMimeType("multipart/alternative")) {
                            return content;
                        } else {
                            if (plainText == null) {
                                plainText = content;
                            }
                        }
                    }
                }
            }

            if (plainText != null && !plainText.trim().isEmpty()) {
                return plainText;
            }
            if (htmlText != null && !htmlText.trim().isEmpty()) {
                return htmlText;
            }
        } else if (part.isMimeType("multipart/*")) {
            Multipart multipart = (Multipart) part.getContent();
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < multipart.getCount(); i++) {
                BodyPart bodyPart = multipart.getBodyPart(i);
                String content = extractBody(bodyPart);
                if (content != null && !content.trim().isEmpty()) {
                    if (sb.length() > 0) {
                        sb.append("\n");
                    }
                    sb.append(content);
                }
            }
            return sb.toString();
        }

        return null;
    }

    /**
     * Decodes and reads an InputStream using the charset specified in the content type,
     * falling back to UTF-8.
     */
    private static String readInputStream(InputStream is, String contentType) throws IOException {
        String charset = StandardCharsets.UTF_8.name();
        if (contentType != null) {
            try {
                ContentType ct = new ContentType(contentType);
                String paramCharset = ct.getParameter("charset");
                if (paramCharset != null && !paramCharset.trim().isEmpty()) {
                    charset = paramCharset;
                }
            } catch (Exception ignored) {
                // Ignore parsing errors and use fallback charset
            }
        }
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, charset))) {
            return reader.lines().collect(Collectors.joining("\n"));
        }
    }

    /**
     * Strives to strip HTML structures while preserving human-readable text breaks.
     */
    public static String htmlToText(String html) {
        if (html == null) {
            return "";
        }
        Document document = Jsoup.parse(html);
        // Append text line break markers after breaks and blocks
        document.select("br").after("\\n");
        document.select("p, div, li, tr").after("\\n");
        String text = document.text();
        return text.replace("\\n", "\n")
                   .replaceAll("\r", "")
                   .replaceAll(" +", " ")
                   .replaceAll("\n +", "\n")
                   .replaceAll("\n+", "\n\n")
                   .trim();
    }
}
