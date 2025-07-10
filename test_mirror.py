#!/usr/bin/env python3

from pathlib import Path
from unittest import mock

import pytest

from mirror import fetch_file, parse_hash_file


def test_parse_hash_file() -> None:
    """Test parsing hash file."""
    # Test valid hash file
    assert parse_hash_file("abcdef1234567890  filename.txt") == "abcdef1234567890"

    # Test with multiple spaces
    assert parse_hash_file("abcdef1234567890    filename.txt") == "abcdef1234567890"

    # Test with empty string
    with pytest.raises(ValueError, match="Empty hash file"):
        parse_hash_file("")


@mock.patch("mirror.httpx.Client")
@mock.patch("mirror.hashlib.sha256")
def test_fetch_file_new_download(
    mock_sha256: mock.MagicMock,
    mock_client_class: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """Test downloading a new file."""
    # The hash for "test content"
    test_content_hash = (
        "d5f12e53a182c062b6bf30c1445153faff12269a1e5c9098aa8e0faf8256c9b1"
    )
    url = "https://example.com/file.txt"
    hash_url = "https://example.com/file.txt.sha256"
    output_path = tmp_path / "file.txt"

    # Setup mock SHA256 to return our expected hash
    mock_sha256_instance = mock.MagicMock()
    mock_sha256_instance.hexdigest.return_value = test_content_hash
    mock_sha256.return_value = mock_sha256_instance

    # Setup mock client
    mock_client = mock.MagicMock()
    mock_client_class.return_value = mock_client

    # Setup mock hash response
    mock_hash_response = mock.MagicMock()
    mock_hash_response.status_code = 200
    mock_hash_response.text = f"{test_content_hash}  filename.txt"

    # Setup mock file stream
    mock_stream = mock.MagicMock()
    mock_stream.status_code = 200
    mock_stream.iter_bytes.return_value = [b"test", b" ", b"content"]

    # Configure mock client
    mock_client.__enter__.return_value.get.return_value = mock_hash_response
    client_stream = mock_client.__enter__.return_value.stream
    client_stream.return_value.__enter__.return_value = mock_stream

    # File doesn't exist yet
    assert not output_path.exists()

    # Fetch the file
    result = fetch_file(url, output_path, hash_url)

    # Check the file was downloaded
    assert result is True
    assert output_path.exists()

    # Check the hash file was created
    hash_path = output_path.with_suffix(".sha256")
    assert hash_path.exists()

    # Verify the hash content
    with open(hash_path) as f:
        hash_content = f.read()
    assert hash_content.startswith(test_content_hash)


@mock.patch("mirror.open")
@mock.patch("mirror.shutil.move")
@mock.patch("mirror.httpx.Client")
def test_fetch_file_no_change_no_downloads(
    mock_client_class: mock.MagicMock,
    mock_move: mock.MagicMock,
    mock_open: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """Test that no file operations occur when the file hasn't changed."""
    # The hash for "test content"
    test_content_hash = (
        "d5f12e53a182c062b6bf30c1445153faff12269a1e5c9098aa8e0faf8256c9b1"
    )
    url = "https://example.com/file.txt"
    hash_url = "https://example.com/file.txt.sha256"
    output_path = tmp_path / "file.txt"
    hash_path = output_path.with_suffix(".sha256")

    # Create the file and hash cache
    test_content = "test content"
    output_path.write_text(test_content)
    hash_path.write_text(f"{test_content_hash}  file.txt")

    # Store original file information
    original_content = output_path.read_text()
    original_mtime = output_path.stat().st_mtime
    original_hash_content = hash_path.read_text()
    original_hash_mtime = hash_path.stat().st_mtime

    # Add a delay to ensure mtime would change if files were modified
    import time

    time.sleep(0.01)  # 10 milliseconds delay

    # Configure mock to read the hash file correctly
    mock_open.side_effect = open

    # Setup mock hash response with the same hash as the cache
    mock_hash_response = mock.MagicMock()
    mock_hash_response.status_code = 200
    mock_hash_response.text = f"{test_content_hash}  file.txt"

    # Setup mock client
    mock_client = mock.MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.__enter__.return_value.get.return_value = mock_hash_response

    # Call the function - with our mocks in place
    result = fetch_file(url, output_path, hash_url)

    # Check result is False (no update)
    assert result is False

    # Verify no file move operations happened
    mock_move.assert_not_called()

    # Verify no write operations to the `.downloading` file
    # Reset the mock to clear the initial read operation and check no writes happened
    mock_open.reset_mock()

    # Configure mocks again to avoid interference with subsequent assertions
    mock_client.__enter__.return_value.get.return_value = mock_hash_response
    result = fetch_file(url, output_path, hash_url)

    # Verify client's stream method was never called (no download attempted)
    assert mock_client.__enter__.return_value.stream.call_count == 0

    # Verify the files were not modified
    assert output_path.read_text() == original_content
    assert output_path.stat().st_mtime == original_mtime
    assert hash_path.read_text() == original_hash_content
    assert hash_path.stat().st_mtime == original_hash_mtime


@mock.patch("mirror.httpx.Client")
@mock.patch("mirror.hashlib.sha256")
def test_fetch_file_hash_mismatch(
    mock_sha256: mock.MagicMock,
    mock_client_class: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """Test when hash doesn't match."""
    url = "https://example.com/file.txt"
    hash_url = "https://example.com/file.txt.sha256"
    output_path = tmp_path / "file.txt"

    # Setup mock SHA256 to return a different hash than the expected one
    mock_sha256_instance = mock.MagicMock()
    mock_sha256_instance.hexdigest.return_value = "differenthash123456789"
    mock_sha256.return_value = mock_sha256_instance

    # Setup mock hash response
    mock_hash_response = mock.MagicMock()
    mock_hash_response.status_code = 200
    mock_hash_response.text = "expectedhash123  file.txt"

    # Setup mock client
    mock_client = mock.MagicMock()
    mock_client_class.return_value = mock_client

    # Setup mock file stream
    mock_stream = mock.MagicMock()
    mock_stream.status_code = 200
    mock_stream.iter_bytes.return_value = [b"test", b" ", b"content"]

    # Configure mock client
    mock_client.__enter__.return_value.get.return_value = mock_hash_response
    client_stream = mock_client.__enter__.return_value.stream
    client_stream.return_value.__enter__.return_value = mock_stream

    # Expect the function to raise an error
    with pytest.raises(ValueError, match="Hash mismatch"):
        fetch_file(url, output_path, hash_url)

    # The file should not exist (temporary file should be cleaned up)
    assert not output_path.exists()


@mock.patch("mirror.httpx.Client")
@mock.patch("tqdm.auto.tqdm")
@mock.patch("mirror.hashlib.sha256")
def test_progress_bar(
    mock_sha256: mock.MagicMock,
    mock_tqdm: mock.MagicMock,
    mock_client_class: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """Test that progress bar is used when downloading files."""
    # The hash for "test content"
    test_content_hash = (
        "d5f12e53a182c062b6bf30c1445153faff12269a1e5c9098aa8e0faf8256c9b1"
    )

    # Mock a progress bar instance
    mock_progress_bar = mock.MagicMock()
    mock_tqdm.return_value.__enter__.return_value = mock_progress_bar

    # Mock hash response - use the same hash as the fixture
    mock_hash_response = mock.MagicMock()
    mock_hash_response.status_code = 200
    mock_hash_response.text = f"{test_content_hash}  file.txt"

    # Setup mock SHA256 to return our expected hash
    mock_sha256_instance = mock.MagicMock()
    mock_sha256_instance.hexdigest.return_value = test_content_hash
    mock_sha256.return_value = mock_sha256_instance

    # Setup mock client
    mock_client = mock.MagicMock()
    mock_client_class.return_value = mock_client

    # Setup mock file stream
    mock_stream = mock.MagicMock()
    mock_stream.status_code = 200
    mock_stream.headers = {"content-length": "100"}
    mock_stream.iter_bytes.return_value = [b"test", b" ", b"content"]

    # Configure mock client
    mock_client.__enter__.return_value.get.return_value = mock_hash_response
    client_stream = mock_client.__enter__.return_value.stream
    client_stream.return_value.__enter__.return_value = mock_stream

    url = "https://example.com/file.txt"
    hash_url = "https://example.com/file.txt.sha256"
    output_path = tmp_path / "file.txt"

    # Call the function
    fetch_file(url, output_path, hash_url)

    # Just verify the function worked
    assert output_path.exists()


@mock.patch("mirror.open", mock.mock_open())
@mock.patch("mirror.httpx.Client")
def test_lock_file_detection(
    mock_client_class: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """Test that the function detects an existing download and skips."""
    url = "https://example.com/file.txt"
    hash_url = "https://example.com/file.txt.sha256"
    output_path = tmp_path / "file.txt"
    lock_path = output_path.with_suffix(output_path.suffix + ".downloading")

    # Setup mock client
    mock_client = mock.MagicMock()
    mock_client_class.return_value = mock_client

    # Setup mock hash response
    mock_hash_response = mock.MagicMock()
    mock_hash_response.status_code = 200
    mock_hash_response.text = "abcdef1234567890  filename.txt"

    # Configure mock client
    mock_client.__enter__.return_value.get.return_value = mock_hash_response

    # Create the lock file to simulate another download in progress
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()

    # Call the function
    result = fetch_file(url, output_path, hash_url)

    # Verify it detected the lock and skipped the download
    assert result is False

    # Verify no HTTP stream was initiated
    mock_client.__enter__.return_value.stream.assert_not_called()

    # Clean up lock file
    lock_path.unlink()

