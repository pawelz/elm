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

import unittest
import email
from core import email_parser

class TestEmailParserMismatch(unittest.TestCase):

    def test_get_email_domain(self):
        # Test basic domain extraction
        self.assertEqual(email_parser.get_email_domain("test@gmail.com"), "gmail.com")
        self.assertEqual(email_parser.get_email_domain("John Doe <test@outlook.com>"), "outlook.com")
        self.assertEqual(email_parser.get_email_domain("test@YAHOO.FR"), "yahoo.fr")
        
        # Test edge cases
        self.assertEqual(email_parser.get_email_domain(""), "")
        self.assertEqual(email_parser.get_email_domain("invalid-email"), "")
        self.assertEqual(email_parser.get_email_domain(None), "")

    def test_has_reply_to_mismatch_same_domain(self):
        # Both same consumer domain
        msg1 = email.message_from_string("From: test@gmail.com\nReply-To: other@gmail.com\n\nBody")
        self.assertEqual(email_parser.has_reply_to_mismatch(msg1), 0.0)
        
        # Both same custom domain
        msg2 = email.message_from_string("From: test@my-company.com\nReply-To: other@my-company.com\n\nBody")
        self.assertEqual(email_parser.has_reply_to_mismatch(msg2), 0.0)

    def test_has_reply_to_mismatch_different_consumer(self):
        # From consumer to different consumer
        msg = email.message_from_string("From: test@gmail.com\nReply-To: other@outlook.com\n\nBody")
        self.assertEqual(email_parser.has_reply_to_mismatch(msg), 0.0)

    def test_has_reply_to_mismatch_consumer_to_custom(self):
        # From consumer to custom domain
        msg = email.message_from_string("From: test@gmail.com\nReply-To: support@my-company.com\n\nBody")
        self.assertEqual(email_parser.has_reply_to_mismatch(msg), 0.0)

    def test_has_reply_to_mismatch_custom_to_custom(self):
        # From custom domain to different custom domain
        msg = email.message_from_string("From: test@partner.com\nReply-To: billing@my-company.com\n\nBody")
        self.assertEqual(email_parser.has_reply_to_mismatch(msg), 0.0)

    def test_has_reply_to_mismatch_spam_pattern(self):
        # From custom domain to consumer domain (SPAM PATTERN)
        msg1 = email.message_from_string("From: hr@my-company.com\nReply-To: attacker@gmail.com\n\nBody")
        self.assertEqual(email_parser.has_reply_to_mismatch(msg1), 1.0)

        # From custom domain to yahoo.fr (Newly added consumer domain)
        msg2 = email.message_from_string("From: boss@my-company.com\nReply-To: attacker@yahoo.fr\n\nBody")
        self.assertEqual(email_parser.has_reply_to_mismatch(msg2), 1.0)

        # From custom domain to yandex.ru (Newly added consumer domain)
        msg3 = email.message_from_string("From: admin@my-company.com\nReply-To: attacker@yandex.ru\n\nBody")
        self.assertEqual(email_parser.has_reply_to_mismatch(msg3), 1.0)

    def test_has_reply_to_mismatch_missing_headers(self):
        # Missing Reply-To
        msg1 = email.message_from_string("From: test@my-company.com\n\nBody")
        self.assertEqual(email_parser.has_reply_to_mismatch(msg1), 0.0)

        # Missing From
        msg2 = email.message_from_string("Reply-To: test@gmail.com\n\nBody")
        self.assertEqual(email_parser.has_reply_to_mismatch(msg2), 0.0)

    def test_parse_includes_mismatch_feature(self):
        # Parse returns structured dict with feature included
        raw_email = b"From: hr@my-company.com\nReply-To: attacker@gmail.com\nSubject: Test\n\nBody text"
        record = email_parser.parse(raw_email)
        self.assertEqual(record["metadata_features"], [1.0])

if __name__ == "__main__":
    unittest.main()
