package ch.execve.elm.ingest;

import jakarta.mail.Session;
import jakarta.mail.internet.MimeBodyPart;
import jakarta.mail.internet.MimeMessage;
import jakarta.mail.internet.MimeMultipart;
import org.junit.Test;

import java.util.Properties;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

/**
 * Unit tests for EmailParser decoding, HTML stripping, multipart handling, and attachments.
 */
public class EmailParserTest {

    private MimeMessage createMessage() {
        Properties props = new Properties();
        Session session = Session.getDefaultInstance(props, null);
        return new MimeMessage(session);
    }

    @Test
    public void testPlainTextMessage() throws Exception {
        MimeMessage msg = createMessage();
        msg.setSubject("Test Subject");
        msg.setText("This is a simple plain text body.");
        msg.saveChanges();

        EmailRecord record = EmailParser.parse(msg, 1);
        assertEquals("Test Subject", record.subject());
        assertEquals("This is a simple plain text body.", record.body());
        assertEquals(1, record.label());
        assertTrue(record.metadata_features().isEmpty());
    }

    @Test
    public void testEncodedSubject() throws Exception {
        MimeMessage msg = createMessage();
        msg.setSubject("=?UTF-8?B?U3BhbSAmIEVnZ3M=?=");
        msg.setText("Body");
        msg.saveChanges();

        EmailRecord record = EmailParser.parse(msg, 0);
        assertEquals("Spam & Eggs", record.subject());
    }

    @Test
    public void testHtmlStripping() {
        String html = "<html><body><h1>Title</h1><p>First paragraph.</p><br>Line break.<p>Second <b>bold</b> paragraph.</p></body></html>";
        String text = EmailParser.htmlToText(html);

        assertTrue(text.contains("Title"));
        assertTrue(text.contains("First paragraph."));
        assertTrue(text.contains("Line break."));
        assertTrue(text.contains("Second bold paragraph."));
    }

    @Test
    public void testMultipartAlternative() throws Exception {
        MimeMessage msg = createMessage();
        msg.setSubject("Alternative test");

        MimeMultipart multipart = new MimeMultipart("alternative");

        MimeBodyPart htmlPart = new MimeBodyPart();
        htmlPart.setContent("<html><body><p>HTML part</p></body></html>", "text/html; charset=utf-8");
        multipart.addBodyPart(htmlPart);

        MimeBodyPart textPart = new MimeBodyPart();
        textPart.setText("Plain text part");
        multipart.addBodyPart(textPart);

        msg.setContent(multipart);
        msg.saveChanges();

        EmailRecord record = EmailParser.parse(msg, 1);
        assertEquals("Plain text part", record.body());
    }

    @Test
    public void testMultipartMixedWithAttachment() throws Exception {
        MimeMessage msg = createMessage();
        msg.setSubject("Mixed test with attachment");

        MimeMultipart mixed = new MimeMultipart("mixed");

        // Plain text body part
        MimeBodyPart textPart = new MimeBodyPart();
        textPart.setText("Primary text body.");
        mixed.addBodyPart(textPart);

        // Attachment body part
        MimeBodyPart attachPart = new MimeBodyPart();
        attachPart.setContent("important,comma,separated,data", "text/csv");
        attachPart.setFileName("data.csv");
        attachPart.setDisposition(MimeBodyPart.ATTACHMENT);
        mixed.addBodyPart(attachPart);

        msg.setContent(mixed);
        msg.saveChanges();

        EmailRecord record = EmailParser.parse(msg, 1);
        assertEquals("Primary text body.", record.body());
    }

    @Test
    public void testUnsupportedCharsetFallback() throws Exception {
        MimeMessage msg = createMessage();
        msg.setSubject("Unsupported Charset Test");
        msg.setContent("Hello, Celtic! (iso-8859-14)", "text/plain; charset=iso-8859-14");
        msg.saveChanges();

        EmailRecord record = EmailParser.parse(msg, 0);
        assertEquals("Hello, Celtic! (iso-8859-14)", record.body());
    }

    @Test
    public void testCp850CharsetFallback() throws Exception {
        MimeMessage msg = createMessage();
        msg.setSubject("CP-850 Charset Test");
        msg.setContent("Hello, MS-DOS! (cp-850)", "text/plain; charset=cp-850");
        msg.saveChanges();

        EmailRecord record = EmailParser.parse(msg, 0);
        assertEquals("Hello, MS-DOS! (cp-850)", record.body());
    }
}
