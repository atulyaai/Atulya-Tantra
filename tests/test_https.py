import datetime
import stat

from cryptography import x509

from atulya.sevak import https


def load(d):
    return x509.load_pem_x509_certificate((d / "cert.pem").read_bytes())


def san(cert):
    ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return set(ext.get_values_for_type(x509.DNSName)), {str(i) for i in ext.get_values_for_type(x509.IPAddress)}


def test_certificate_covers_this_computers_names_and_addresses(tmp_path):
    cert_file, key_file = https.ensure_certs(tmp_path, ["localhost", "mypc"], ["127.0.0.1", "192.168.1.15"])
    assert san(load(tmp_path)) == ({"localhost", "mypc"}, {"127.0.0.1", "192.168.1.15"})
    c = load(tmp_path)
    assert c.not_valid_after_utc - datetime.datetime.now(datetime.timezone.utc) > datetime.timedelta(days=360)
    assert c.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is False        # not a certificate authority
    assert oct((tmp_path / "key.pem").stat().st_mode & 0o777) == "0o600"
    assert cert_file.endswith("cert.pem") and key_file.endswith("key.pem")


def test_reuses_a_good_pair_and_renews_when_the_address_changes_or_it_is_unreadable(tmp_path):
    https.ensure_certs(tmp_path, ["localhost"], ["127.0.0.1"])
    first = (tmp_path / "cert.pem").read_bytes()
    https.ensure_certs(tmp_path, ["localhost"], ["127.0.0.1"])
    assert (tmp_path / "cert.pem").read_bytes() == first                                         # nothing changed: kept
    https.ensure_certs(tmp_path, ["localhost"], ["127.0.0.1", "192.168.1.99"])                   # a new network address
    assert "192.168.1.99" in san(load(tmp_path))[1] and (tmp_path / "cert.pem").read_bytes() != first
    (tmp_path / "cert.pem").write_text("garbage")
    https.ensure_certs(tmp_path, ["localhost"], ["127.0.0.1"])
    assert san(load(tmp_path))[0] == {"localhost"}


def test_switch_and_local_names(monkeypatch):
    monkeypatch.delenv("ATULYA_HTTPS", raising=False)
    assert not https.enabled()
    for v in ("on", "1", "TRUE"):
        monkeypatch.setenv("ATULYA_HTTPS", v)
        assert https.enabled()
    names, ips = https.local_names()
    assert "localhost" in names and "127.0.0.1" in ips


def test_the_key_is_never_world_readable(tmp_path):
    https.ensure_certs(tmp_path, ["localhost"], ["127.0.0.1"])
    mode = (tmp_path / "key.pem").stat().st_mode
    assert not mode & (stat.S_IRWXG | stat.S_IRWXO)
