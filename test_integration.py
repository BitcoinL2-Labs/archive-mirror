#!/usr/bin/env python3

import hashlib
import http.server
import socketserver
import threading

import pytest
from _pytest.tmpdir import TempPathFactory

from mirror import fetch_file


# ruff: noqa: ANN001, ANN002, ANN003, A002
# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportIncompatibleMethodOverride=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnusedImport=false
class SimpleFileServer(http.server.SimpleHTTPRequestHandler):
    """Simple HTTP server for testing."""

    def __init__(self, *args, **kwargs) -> None:
        # Set directory to the temporary directory
        directory = kwargs.pop("directory", None)
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args) -> None:
        """Silence the log messages."""


def test_integration_download(tmp_path_factory: TempPathFactory) -> None:
    """Integration test for downloading a file from a real HTTP server."""
    # Create temporary directories for server and client
    server_dir_path = tmp_path_factory.mktemp("server")
    client_dir_path = tmp_path_factory.mktemp("client")

    # Create a test file to serve
    test_content = b"This is a test file for the integration test"
    test_file_path = server_dir_path / "test_file.txt"
    test_file_path.write_bytes(test_content)

    # Calculate the SHA-256 hash of the file
    file_hash = hashlib.sha256(test_content).hexdigest()
    hash_file_path = server_dir_path / "test_file.txt.sha256"
    hash_file_path.write_text(f"{file_hash}  test_file.txt")

    # Start a simple HTTP server in a separate thread
    def create_handler(*args, **kwargs) -> SimpleFileServer:
        return SimpleFileServer(*args, directory=str(server_dir_path), **kwargs)

    httpd = socketserver.TCPServer(("localhost", 0), create_handler)
    port = httpd.server_address[1]
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        # Define URLs for the file and its hash
        base_url = f"http://localhost:{port}"
        file_url = f"{base_url}/test_file.txt"
        hash_url = f"{base_url}/test_file.txt.sha256"

        # Define output path
        output_path = client_dir_path / "downloaded_file.txt"

        # Download the file
        result = fetch_file(file_url, output_path, hash_url)

        # Verify the result
        assert result is True
        assert output_path.exists()
        assert output_path.read_bytes() == test_content

        # Verify hash cache was created
        hash_cache_path = output_path.with_suffix(".sha256")
        assert hash_cache_path.exists()
        assert file_hash in hash_cache_path.read_text()

        # Test downloading the same file again (should be skipped)
        result = fetch_file(file_url, output_path, hash_url)
        assert result is False  # No update needed

    finally:
        # Shut down the server
        httpd.shutdown()
        server_thread.join(timeout=1)


if __name__ == "__main__":
    pytest.main(["-v", __file__])

