import ssl

from spilberg.pexels import PexelsClient


def test_pexels_uses_verified_tls_context():
    client = PexelsClient(api_key="test-key")
    context = client._ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
