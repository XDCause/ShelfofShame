"""The app's own HTTPS certificate (run by make-cert.ps1 inside the API image, which has the cryptography library).

  /ca/ca.key, /ca/ca.crt      "Off the Clock local CA": made once, kept in %USERPROFILE%\\.offtheclock\\ca (outside both
                              app folders, so dev and prod share it). Install ca.crt on each phone / PC once: after that,
                              every certificate it signs is trusted - no warnings, and passkeys work.
  /certs/server.key, .crt     this copy's certificate, for every name and address the app is reached at (the PC's name
                              and name.local, its Wi-Fi and Tailscale addresses, localhost). Signed by the CA.
  /certs/offtheclock-ca.crt   a copy of ca.crt, offered for download at http://<PC>:8080/ca.crt.

Nothing here is ever committed (certs/ is git-ignored; the CA lives outside the repo). The CA key never leaves this PC.

    python make_cert.py --name travel-laptop --ip 10.0.0.33 --ip 100.76.51.75 [--force]
"""
import argparse
import datetime as dt
import ipaddress
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

CA_DIR, OUT = Path("/ca"), Path("/certs")
SERVER_DAYS = 800          # Apple won't trust a server certificate valid for more than 825 days
CA_YEARS = 10
NOW = dt.datetime.now(dt.timezone.utc)


def save_key(key, path: Path):
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
    path.chmod(0o600)


def load_or_make_ca():
    key_path, crt_path = CA_DIR / "ca.key", CA_DIR / "ca.crt"
    if key_path.exists() and crt_path.exists():
        return (serialization.load_pem_private_key(key_path.read_bytes(), None),
                x509.load_pem_x509_certificate(crt_path.read_bytes()), False)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Off the Clock local CA"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Off the Clock (this home only)")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(NOW - dt.timedelta(days=1))
            .not_valid_after(NOW + dt.timedelta(days=365 * CA_YEARS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
                                         encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .sign(key, hashes.SHA256()))
    CA_DIR.mkdir(parents=True, exist_ok=True)
    save_key(key, key_path)
    crt_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key, cert, True


def wanted(names, ips):
    dns = sorted({"localhost", "web", *names, *(f"{n}.local" for n in names if "." not in n)})
    return dns, sorted({"127.0.0.1", "::1", *ips})


def current_ok(dns, ips, ca_cert) -> bool:
    """Keep the certificate there if it covers the same names, isn't near its end and came from this CA."""
    crt = OUT / "server.crt"
    if not crt.exists() or not (OUT / "server.key").exists():
        return False
    cert = x509.load_pem_x509_certificate(crt.read_bytes())
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    have = (sorted(san.get_values_for_type(x509.DNSName)), sorted(str(i) for i in san.get_values_for_type(x509.IPAddress)))
    return (have == (dns, sorted(str(ipaddress.ip_address(i)) for i in ips))
            and cert.not_valid_after_utc - NOW > dt.timedelta(days=30) and cert.issuer == ca_cert.subject)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", action="append", default=[], help="a host name the app is reached by")
    parser.add_argument("--ip", action="append", default=[], help="an address the app is reached at")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    names = [n.lower() for n in args.name]
    ca_key, ca_cert, made_ca = load_or_make_ca()
    dns, ips = wanted(names, args.ip)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "offtheclock-ca.crt").write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    if not args.force and not made_ca and current_ok(dns, ips, ca_cert):
        print("The certificate is up to date.")
        return 0
    key = ec.generate_private_key(ec.SECP256R1())
    first = names[0] if names else "localhost"
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"{first}.local" if "." not in first else first)]))
            .issuer_name(ca_cert.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(NOW - dt.timedelta(days=1)).not_valid_after(NOW + dt.timedelta(days=SERVER_DAYS))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(d) for d in dns]
                                                       + [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    save_key(key, OUT / "server.key")
    (OUT / "server.key").chmod(0o644)          # nginx (another container) reads it; the folder is yours only
    (OUT / "server.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM) + ca_cert.public_bytes(serialization.Encoding.PEM))
    print(("Made the local CA (install it on your devices). " if made_ca else "")
          + f"Certificate made for {', '.join(dns + ips)}; valid until {cert.not_valid_after_utc:%d %b %Y}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
