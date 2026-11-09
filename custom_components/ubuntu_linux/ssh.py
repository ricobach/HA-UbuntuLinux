"""SSH transport with mandatory pinned host-key verification."""
import asyncio
import json
import asyncssh

from .const import COMMAND


class PinnedSSHClient(asyncssh.SSHClient):
    """Trust only a fingerprint entered during setup."""

    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint.strip()

    def validate_host_public_key(self, host, addr, port, key):
        return key.get_fingerprint("sha256") == self.fingerprint


async def fetch_metrics(host: str, port: int, user: str, private_key: str, fingerprint: str) -> dict:
    """Read one JSON object from the fixed remote monitor executable."""
    async with asyncssh.connect(
        host,
        port=port,
        username=user,
        client_keys=[asyncssh.import_private_key(private_key)],
        known_hosts=([], [], []),  # No trusted keys; callback validates the pinned fingerprint
        client_factory=lambda: PinnedSSHClient(fingerprint),
        connect_timeout=10,
        login_timeout=10,
    ) as conn:
        result = await asyncio.wait_for(conn.run(COMMAND, check=True), timeout=20)
    data = json.loads(result.stdout)
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Unexpected response from Ubuntu monitor")
    return data
