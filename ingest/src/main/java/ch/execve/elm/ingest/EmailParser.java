package ch.execve.elm.ingest;

import jakarta.mail.BodyPart;
import jakarta.mail.MessagingException;
import jakarta.mail.Multipart;
import jakarta.mail.Part;
import jakarta.mail.internet.ContentType;
import jakarta.mail.internet.MimeMessage;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import java.util.regex.Pattern;
import java.util.regex.Matcher;

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
            body = stripUrlsToDomain(body.trim());
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
            return getPartText(part);
        } else if (part.isMimeType("text/html")) {
            String html = getPartText(part);
            if (html == null) {
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
     * Safely retrieves the text content of a Part, decoding charset and handling fallback if needed.
     */
    private static String getPartText(Part part) throws MessagingException, IOException {
        try {
            Object content = part.getContent();
            if (content instanceof String) {
                return (String) content;
            } else if (content instanceof InputStream) {
                return readInputStream((InputStream) content, part.getContentType());
            }
        } catch (Exception e) {
            // Fall back to manual InputStream decoding in case of UnsupportedEncodingException or other decoding failures
            try (InputStream is = part.getInputStream()) {
                return readInputStream(is, part.getContentType());
            }
        }
        return null;
    }

    /**
     * Normalizes and resolves standard and non-standard charset names to a supported Charset object.
     * Defaults to ISO-8859-1 if the charset is unsupported, to ensure robust decoding.
     */
    private static java.nio.charset.Charset resolveCharset(String charsetName) {
        if (charsetName == null || charsetName.trim().isEmpty()) {
            return StandardCharsets.UTF_8;
        }
        String normalized = charsetName.trim().toLowerCase(java.util.Locale.ENGLISH);

        // Map common aliases that standard JVMs or JavaMail may fail to resolve natively
        if (normalized.equals("cp-850") || normalized.equals("cp850") || normalized.equals("ibm850") || normalized.equals("ibm-850")) {
            try {
                if (java.nio.charset.Charset.isSupported("Cp850")) {
                    return java.nio.charset.Charset.forName("Cp850");
                }
            } catch (Exception ignored) {}
            try {
                if (java.nio.charset.Charset.isSupported("IBM850")) {
                    return java.nio.charset.Charset.forName("IBM850");
                }
            } catch (Exception ignored) {}
        }
        if (normalized.equals("iso-8859-14") || normalized.equals("iso_8859-14")) {
            try {
                if (java.nio.charset.Charset.isSupported("ISO8859_14")) {
                    return java.nio.charset.Charset.forName("ISO8859_14");
                }
            } catch (Exception ignored) {}
            try {
                if (java.nio.charset.Charset.isSupported("ISO-8859-14")) {
                    return java.nio.charset.Charset.forName("ISO-8859-14");
                }
            } catch (Exception ignored) {}
        }
        if (normalized.equals("iso-8859-10") || normalized.equals("iso_8859-10")) {
            try {
                if (java.nio.charset.Charset.isSupported("ISO8859_10")) {
                    return java.nio.charset.Charset.forName("ISO8859_10");
                }
            } catch (Exception ignored) {}
            try {
                if (java.nio.charset.Charset.isSupported("ISO-8859-10")) {
                    return java.nio.charset.Charset.forName("ISO-8859-10");
                }
            } catch (Exception ignored) {}
        }

        try {
            if (java.nio.charset.Charset.isSupported(charsetName)) {
                return java.nio.charset.Charset.forName(charsetName);
            }
        } catch (Exception ignored) {}

        // Fall back to ISO-8859-1 which is standard and decodes any byte stream without throwing exceptions
        return StandardCharsets.ISO_8859_1;
    }

    /**
     * Decodes and reads an InputStream using the charset specified in the content type,
     * falling back to UTF-8 or ISO-8859-1 if the charset is unsupported.
     */
    private static String readInputStream(InputStream is, String contentType) throws IOException {
        String charsetName = StandardCharsets.UTF_8.name();
        if (contentType != null) {
            try {
                ContentType ct = new ContentType(contentType);
                String paramCharset = ct.getParameter("charset");
                if (paramCharset != null && !paramCharset.trim().isEmpty()) {
                    charsetName = paramCharset;
                }
            } catch (Exception ignored) {
                // Ignore parsing errors and use fallback charset
            }
        }
        java.nio.charset.Charset resolved = resolveCharset(charsetName);
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, resolved))) {
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

    /**
     * Finds HTTP/HTTPS URLs in the text and strips them to their bare domain.
     */
    public static String stripUrlsToDomain(String text) {
        if (text == null) {
            return "";
        }
        Pattern pattern = Pattern.compile("https?://[^\\s<>\"'()]+", Pattern.CASE_INSENSITIVE);
        Matcher matcher = pattern.matcher(text);
        StringBuilder sb = new StringBuilder();
        int lastEnd = 0;
        while (matcher.find()) {
            sb.append(text, lastEnd, matcher.start());
            String urlStr = matcher.group();

            // Trim trailing punctuation that are likely part of the surrounding sentence
            String trailingPunctuation = "";
            int trimLen = urlStr.length();
            while (trimLen > 0) {
                char lastChar = urlStr.charAt(trimLen - 1);
                if (lastChar == '.' || lastChar == ',' || lastChar == '!' || lastChar == '?' || lastChar == ';' || lastChar == ':' || lastChar == '*' || lastChar == '-') {
                    trimLen--;
                } else {
                    break;
                }
            }
            if (trimLen < urlStr.length()) {
                trailingPunctuation = urlStr.substring(trimLen);
                urlStr = urlStr.substring(0, trimLen);
            }

            String domain = extractDomain(urlStr);
            sb.append(domain).append(trailingPunctuation);
            lastEnd = matcher.end();
        }
        sb.append(text, lastEnd, text.length());
        return sb.toString();
    }

    /**
     * Extracts the host from a URL and strips "www." if present.
     */
    private static String extractDomain(String urlStr) {
        try {
            java.net.URI uri = new java.net.URI(urlStr);
            String host = uri.getHost();
            if (host != null) {
                return host.startsWith("www.") ? host.substring(4) : host;
            }
        } catch (Exception ignored) {
            // Fallback to regex host extraction if URI parsing fails
        }
        Pattern hostPattern = Pattern.compile("^https?://([^/?:#]+)", Pattern.CASE_INSENSITIVE);
        Matcher m = hostPattern.matcher(urlStr);
        if (m.find()) {
            String host = m.group(1);
            int colonIdx = host.indexOf(':');
            if (colonIdx != -1) {
                host = host.substring(0, colonIdx);
            }
            return host.startsWith("www.") ? host.substring(4) : host;
        }
        return urlStr;
    }
}
