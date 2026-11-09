"""SSH transport with trust-on-first-use host key pinning."""
import asyncio
import json

import asyncssh

from .const import COMMAND


class HostKeyClient(asyncssh.SSHClient):
    """Record a first-use host key or verify the previously pinned fingerprint."""

    def __init__(self, expected_fingerprint=None):
        self.expected_fingerprint = expected_fingerprint
        self.observed_fingerprint = None

    def validate_host_public_key(self, host, addr, port, key):
        fingerprint = key.get_fingerprint("sha256")
        if self.expected_fingerprint is not None and fingerprint != self.expected_fingerprint:
            return False
        self.observed_fingerprint = fingerprint
        return True


async def fetch_metrics_with_host_key(host, port, user, private_key, fingerprint=None):
    """Return monitor metrics and the SSH host key fingerprint.

    On initial enrollment the first observed key is trusted (TOFU). After enrollment,
    every SSH connection rejects any host key which differs from the stored fingerprint.
    """
    client = HostKeyClient(fingerprint)
    async with asyncssh.connect(
        host,
        port=port,
        username=user,
        client_keys=[asyncssh.import_private_key(private_key)],
        known_hosts=([], [], []),
        server_host_key_algs="default",
        client_factory=lambda: client,
        connect_timeout=10,
        login_timeout=10,
    ) as conn:
        result = await asyncio.wait_for(conn.run(COMMAND, check=True), timeout=20)
    data = json.loads(result.stdout)
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Unexpected response from Ubuntu monitor")
    if not client.observed_fingerprint:
        raise ValueError("SSH server host key was not verified")
    return data, client.observed_fingerprint


async def fetch_metrics(host, port, user, private_key, fingerprint):
    """Read a monitor response using the SSH host key pinned at enrollment."""
    if not fingerprint:
        raise ValueError("Missing pinned SSH host key")
    data, _ = await fetch_metrics_with_host_key(host, port, user, private_key, fingerprint)
    return data
