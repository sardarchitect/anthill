"""Stub MCP client for Rhino/Grasshopper integration.

Will be expanded to perform real communication. For now it will expose a
`send_message` method returning a placeholder response so the chat UI can be
developed independently of the backend integration.
"""

class MCPClient:
    """Minimal stub of an MCP client.

    Future responsibilities:
    - Connection lifecycle (connect/disconnect)
    - Authentication / session management
    - Request/response correlation & streaming
    - Error normalization & retry logic
    """

    def __init__(self):
        self._connected = False

    def connect(self):
        self._connected = True

    def is_connected(self) -> bool:
        return self._connected

    def send_message(self, prompt: str) -> str:
        """Return a placeholder response.

        Parameters
        ----------
        prompt: str
            User prompt to send.
        """
        if not self._connected:
            self.connect()
        return f"[MCP Stub] Received: {prompt[:120]}"
