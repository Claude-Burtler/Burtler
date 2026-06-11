from __future__ import annotations

from datetime import datetime, timedelta, timezone
import ipaddress
from pathlib import Path
import socket

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


CERT_DIR = Path("certs")
CERT_FILE = CERT_DIR / "localhost.pem"
KEY_FILE = CERT_DIR / "localhost-key.pem"


def local_ip_addresses() -> list[str]:
    addresses = {"127.0.0.1"}

    try:
        hostname = socket.gethostname()
        addresses.update(socket.gethostbyname_ex(hostname)[2])
    except OSError:
        pass

    return sorted(addresses)


def main() -> None:
    CERT_DIR.mkdir(exist_ok=True)
    ip_addresses = local_ip_addresses()

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "KR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Local FastAPI Dev"),
            x509.NameAttribute(NameOID.COMMON_NAME, "A/B Laptop Chat"),
        ]
    )

    alt_names: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName(socket.gethostname()),
    ]
    alt_names.extend(x509.IPAddress(ipaddress.ip_address(ip)) for ip in ip_addresses)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=5))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(private_key, hashes.SHA256())
    )

    KEY_FILE.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    CERT_FILE.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))

    print(f"Created {CERT_FILE}")
    print(f"Created {KEY_FILE}")
    print("Included IP addresses:")
    for ip in ip_addresses:
        print(f"- {ip}")


if __name__ == "__main__":
    main()
