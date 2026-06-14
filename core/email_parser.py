# Copyright 2026 Paweł Zuzelski
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import email
from email.header import decode_header
import re
import urllib.parse
from bs4 import BeautifulSoup

def get_decoded_header(header_value: str) -> str:
    """Decodes MIME encoded-word syntax in headers (e.g., subjects)."""
    if not header_value:
        return ""
    try:
        decoded_parts = decode_header(header_value)
        result_parts = []
        for text, charset in decoded_parts:
            if isinstance(text, bytes):
                if charset:
                    result_parts.append(text.decode(charset, errors="replace"))
                else:
                    result_parts.append(text.decode("utf-8", errors="replace"))
            else:
                result_parts.append(str(text))
        return "".join(result_parts)
    except Exception:
        return str(header_value)

def html_to_text(html_content: str) -> str:
    """Strips HTML tags while preserving layout breaks, mimicking Java Jsoup cleanup."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Append line break markers after breaks and blocks
    for br in soup.find_all("br"):
        br.insert_after("\\n")
        
    for el in soup.find_all(["p", "div", "li", "tr"]):
        el.insert_after("\\n")
        
    text = soup.get_text()
    
    # Standardize whitespace and linebreaks to match Java's regex replacements
    text = text.replace("\\n", "\n")
    text = text.replace("\r", "")
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n +", "\n", text)
    text = re.sub(r"\n+", "\n\n", text)
    return text.strip()

def extract_domain(url_str: str) -> str:
    """Extracts the hostname domain from a URL and strips 'www.' if present."""
    try:
        parsed = urllib.parse.urlparse(url_str)
        host = parsed.netloc
        if host:
            if ":" in host:
                host = host.split(":")[0]
            return host[4:] if host.lower().startswith("www.") else host
    except Exception:
        pass
        
    # Fallback host extraction matching Java's pattern matching
    m = re.match(r"^https?://([^/?:#]+)", url_str, re.IGNORECASE)
    if m:
        host = m.group(1)
        if ":" in host:
            host = host.split(":")[0]
        return host[4:] if host.lower().startswith("www.") else host
    return url_str

def strip_urls_to_domain(text: str) -> str:
    """Finds HTTP/HTTPS URLs in text and reduces them to their bare domains."""
    if not text:
        return ""
    
    pattern = re.compile(r"https?://[^\s<>\"'()]+", re.IGNORECASE)
    
    def replace_url(match):
        url_str = match.group(0)
        
        # Trim trailing punctuation (e.g. from the end of sentences)
        trailing_punctuation = ""
        trim_len = len(url_str)
        while trim_len > 0:
            last_char = url_str[trim_len - 1]
            if last_char in ".,!?;;*-":
                trim_len -= 1
            else:
                break
        if trim_len < len(url_str):
            trailing_punctuation = url_str[trim_len:]
            url_str = url_str[:trim_len]
            
        domain = extract_domain(url_str)
        return domain + trailing_punctuation
        
    return pattern.sub(replace_url, text)

def resolve_charset(charset_name: str) -> str:
    """Resolves standard and non-standard charsets to Python codec names, defaulting to latin-1."""
    if not charset_name:
        return "utf-8"
    normalized = charset_name.strip().lower()
    
    # Map common aliases that standard libraries might fail on
    if normalized in ["cp-850", "cp850", "ibm850", "ibm-850"]:
        return "cp850"
    if normalized in ["iso-8859-14", "iso_8859-14"]:
        return "iso8859-14"
    if normalized in ["iso-8859-10", "iso_8859-10"]:
        return "iso8859-10"
        
    try:
        import codecs
        codecs.lookup(normalized)
        return normalized
    except LookupError:
        # Fall back to latin-1 (ISO-8859-1) which safely decodes any byte string without errors
        return "latin-1"

def get_part_text(part) -> str:
    """Decodes and retrieves the payload of a MIME body part."""
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset()
    resolved = resolve_charset(charset)
    try:
        return payload.decode(resolved, errors="replace")
    except Exception:
        # Absolute safety fallback
        return payload.decode("latin-1", errors="replace")

def extract_body(part) -> str:
    """Recursively extracts the cleaned plain text body of an email part, skipping attachments."""
    # Skip attachments
    disposition = part.get_content_disposition()
    filename = part.get_filename()
    if (disposition and disposition.lower() == "attachment") or filename:
        return None
        
    content_type = part.get_content_type()
    
    if content_type == "text/plain":
        return get_part_text(part)
    elif content_type == "text/html":
        html = get_part_text(part)
        return html_to_text(html) if html else ""
    elif content_type == "multipart/alternative":
        plain_text = None
        html_text = None
        payload = part.get_payload()
        if isinstance(payload, list):
            for subpart in payload:
                sub_content_type = subpart.get_content_type()
                if sub_content_type == "text/plain":
                    plain_text = extract_body(subpart)
                elif sub_content_type == "text/html":
                    html_text = extract_body(subpart)
                elif sub_content_type.startswith("multipart/"):
                    content = extract_body(subpart)
                    if content and content.strip():
                        if sub_content_type == "multipart/alternative":
                            return content
                        else:
                            if plain_text is None:
                                plain_text = content
                                
        if plain_text and plain_text.strip():
            return plain_text
        if html_text and html_text.strip():
            return html_text
            
    elif content_type.startswith("multipart/"):
        parts = []
        payload = part.get_payload()
        if isinstance(payload, list):
            for subpart in payload:
                content = extract_body(subpart)
                if content and content.strip():
                    parts.append(content)
        return "\n".join(parts)
        
    return None

import email.utils

CONSUMER_DOMAINS = {
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.com",
    "yahoo.fr",
    "yandex.ru",
    "icloud.com",
    "me.com",
    "mac.com",
    "protonmail.com",
    "proton.me",
    "pm.me",
    "protonmail.ch",
    "zoho.com",
    "aol.com",
    "gmx.com",
    "gmx.de",
    "mail.com",
    "fastmail.com",
    "tutanota.com",
}

def get_email_domain(header_value: str) -> str:
    """Extracts the domain portion of the first email address found in a header."""
    if not header_value:
        return ""
    try:
        _, addr = email.utils.parseaddr(header_value)
        if addr and "@" in addr:
            return addr.split("@")[-1].strip().lower()
    except Exception:
        pass
    return ""

def has_reply_to_mismatch(msg) -> float:
    """
    Returns 1.0 if the From domain is a custom/private domain AND
    the Reply-To domain is a large consumer email service (and they do not match).
    Otherwise, returns 0.0.
    """
    from_raw = msg.get("From", "")
    reply_to_raw = msg.get("Reply-To", "")
    
    if not from_raw or not reply_to_raw:
        return 0.0
        
    from_domain = get_email_domain(from_raw)
    reply_to_domain = get_email_domain(reply_to_raw)
    
    if not from_domain or not reply_to_domain:
        return 0.0
        
    if from_domain == reply_to_domain:
        return 0.0
        
    if from_domain not in CONSUMER_DOMAINS and reply_to_domain in CONSUMER_DOMAINS:
        return 1.0
        
    return 0.0

def parse(raw_email_bytes: bytes, label: int = 0) -> dict:
    """Parses raw email bytes into a structured dictionary equivalent to EmailRecord."""
    msg = email.message_from_bytes(raw_email_bytes)
    
    subject_raw = msg.get("Subject", "")
    subject = get_decoded_header(subject_raw)
    
    body = extract_body(msg)
    if body is None:
        body = ""
    else:
        body = strip_urls_to_domain(body.strip())
        
    mismatch_val = has_reply_to_mismatch(msg)
    
    return {
        "subject": subject,
        "body": body,
        "metadata_features": [mismatch_val],
        "label": label
    }

