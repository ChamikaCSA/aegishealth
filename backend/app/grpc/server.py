"""gRPC server for the Central Orchestrator."""

from __future__ import annotations

import logging
import subprocess
from concurrent import futures
from pathlib import Path

import grpc

from app.grpc import federated_pb2_grpc
from app.grpc.servicer import FederatedLearningServicer

logger = logging.getLogger(__name__)

_server = None


def _ensure_dev_certs(cert_dir: Path) -> None:
    """Auto-generate self-signed dev certs if they don't exist yet."""
    ca_key = cert_dir / "ca.key"
    ca_crt = cert_dir / "ca.crt"
    srv_key = cert_dir / "server.key"
    srv_crt = cert_dir / "server.crt"

    if srv_crt.exists() and srv_key.exists() and ca_crt.exists():
        return

    cert_dir.mkdir(parents=True, exist_ok=True)
    logger.warning("TLS certs not found — auto-generating self-signed dev certs in %s", cert_dir)

    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:4096", "-nodes",
            "-keyout", str(ca_key), "-out", str(ca_crt),
            "-days", "365", "-subj", "/CN=AegisHealth Dev CA",
        ],
        check=True,
        capture_output=True,
    )

    csr = cert_dir / "server.csr"
    subprocess.run(
        [
            "openssl", "req", "-newkey", "rsa:4096", "-nodes",
            "-keyout", str(srv_key), "-out", str(csr),
            "-subj", "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )

    subprocess.run(
        [
            "openssl", "x509", "-req",
            "-in", str(csr),
            "-CA", str(ca_crt), "-CAkey", str(ca_key), "-CAcreateserial",
            "-out", str(srv_crt),
            "-days", "365",
            "-extfile", "/dev/stdin",
        ],
        input=b"subjectAltName=DNS:localhost,IP:127.0.0.1",
        check=True,
        capture_output=True,
    )

    for tmp in (csr, cert_dir / "ca.srl"):
        tmp.unlink(missing_ok=True)

    logger.warning("Dev certs generated. For production, supply real certificates.")


async def serve_grpc(
    port: int = 50051,
    orchestrator=None,
    tls_cert: str | None = None,
    tls_key: str | None = None,
):
    """Start the gRPC server with mandatory TLS."""
    global _server

    from app.core.config import settings

    if orchestrator is None:
        from app.core.orchestrator import get_orchestrator
        orchestrator = get_orchestrator()

    cert_path = Path(tls_cert) if tls_cert else Path(settings.grpc_tls_cert)
    key_path = Path(tls_key) if tls_key else Path(settings.grpc_tls_key)

    _ensure_dev_certs(cert_path.parent)

    if not cert_path.exists() or not key_path.exists():
        raise RuntimeError(
            f"TLS certificate ({cert_path}) or key ({key_path}) not found and "
            "auto-generation failed. gRPC cannot start without TLS."
        )

    with open(key_path, "rb") as f:
        private_key = f.read()
    with open(cert_path, "rb") as f:
        certificate = f.read()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = FederatedLearningServicer(orchestrator)
    federated_pb2_grpc.add_FederatedLearningServicer_to_server(servicer, server)

    creds = grpc.ssl_server_credentials([(private_key, certificate)])
    server.add_secure_port(f"[::]:{port}", creds)
    logger.info("gRPC server starting on port %d (TLS)", port)

    server.start()
    _server = server
    server.wait_for_termination()
