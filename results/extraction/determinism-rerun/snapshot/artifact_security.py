"""Credential detection shared by extraction, workflow publication, and trace redaction."""
import os
import re

KEY_NAMES = ('FREYA_API_KEY', 'FREYA_BANK_TEAM_KEY', 'ANTHROPIC_API_KEY')
TOKEN = re.compile(r'(?:sk-ant-|fak_)[A-Za-z0-9_-]{12,}')
BEARER = re.compile(r'(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]{8,}')


def redact(text):
    for name in KEY_NAMES:
        secret = os.environ.get(name)
        if secret:
            text = text.replace(secret, '[REDACTED]')
    text = TOKEN.sub('[REDACTED]', text)
    return BEARER.sub(r'\1[REDACTED]', text)


def check_artifact(text):
    """Fail without printing the credential or surrounding artifact contents."""
    if redact(text) != text:
        raise ValueError('credential detected in generated artifact')
