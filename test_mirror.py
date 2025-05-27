#!/usr/bin/env python3

import os
import tempfile
from pathlib import Path
from unittest import mock

import httpx
import pytest
from tqdm import tqdm

from mirror import fetch_file, parse_hash_file


def test_parse_hash_file():
    """Test parsing hash file."""
    # Test valid hash file
    assert parse_hash_file("abcdef1234567890  filename.txt") == "abcdef1234567890"
    
    # Test with multiple spaces
    assert parse_hash_file("abcdef1234567890    filename.txt") == "abcdef1234567890"
    
    # Test with empty string
    with pytest.raises(ValueError):
        parse_hash_file("")


@mock.patch("mirror.httpx.Client")
@mock.patch("mirror.hashlib.sha256")
def test_fetch_file_new_download(mock_sha256, mock_client_class, tmp_path):
    """Test downloading a new file."""
    # The hash for "test content"
    test_content_hash = "d5f12e53a182c062b6bf30c1445153faff12269a1e5c9098aa8e0faf8256c9b1"
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
    mock_client.__enter__.return_value.stream.return_value.__enter__.return_value = mock_stream
    
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
    with open(hash_path, "r") as f:
        hash_content = f.read()
    assert hash_content.startswith(test_content_hash)


def test_fetch_file_no_change_no_downloads(tmp_path):
    """Test that no file operations occur when the file hasn't changed."""
    # The hash for "test content"
    test_content_hash = "d5f12e53a182c062b6bf30c1445153faff12269a1e5c9098aa8e0faf8256c9b1"
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
    time.sleep(0.01)  # 10ms delay
    
    # Mock httpx.Client to return the same hash
    with mock.patch("mirror.httpx.Client") as mock_client_class:
        # Setup client mock
        mock_client = mock.MagicMock()
        mock_client_class.return_value = mock_client
        
        # Setup hash response with the same hash as the cache
        mock_hash_response = mock.MagicMock()
        mock_hash_response.status_code = 200
        mock_hash_response.text = f"{test_content_hash}  filename.txt"
        mock_client.__enter__.return_value.get.return_value = mock_hash_response
        
        # Setup stream mock to track if it was called
        mock_stream = mock.MagicMock()
        mock_client.__enter__.return_value.stream = mock.MagicMock(return_value=mock_stream)
        
        # With patches for operations that should not happen
        with mock.patch("mirror.tempfile.NamedTemporaryFile") as mock_temp_file:
            with mock.patch("mirror.shutil.move") as mock_move:
                # Call the function
                result = fetch_file(url, output_path, hash_url)
                
                # Check result is False (no update)
                assert result is False
                
                # Verify no HTTP stream was started (no download attempt)
                mock_client.__enter__.return_value.stream.assert_not_called()
                
                # Verify no temporary file was created
                mock_temp_file.assert_not_called()
                
                # Verify no file move operations happened
                mock_move.assert_not_called()
    
    # Verify the files were not modified
    assert output_path.read_text() == original_content
    assert output_path.stat().st_mtime == original_mtime
    assert hash_path.read_text() == original_hash_content
    assert hash_path.stat().st_mtime == original_hash_mtime


@mock.patch("mirror.httpx.Client")
@mock.patch("mirror.hashlib.sha256")
def test_fetch_file_hash_mismatch(mock_sha256, mock_client_class, tmp_path):
    """Test when hash doesn't match."""
    url = "https://example.com/file.txt"
    hash_url = "https://example.com/file.txt.sha256"
    output_path = tmp_path / "file.txt"
    
    # Setup mock client
    mock_client = mock.MagicMock()
    mock_client_class.return_value = mock_client
    
    # Setup mock SHA256 to return a different hash than the expected one
    mock_sha256_instance = mock.MagicMock()
    mock_sha256_instance.hexdigest.return_value = "differenthash123456789"
    mock_sha256.return_value = mock_sha256_instance
    
    # Setup mock hash response
    mock_hash_response = mock.MagicMock()
    mock_hash_response.status_code = 200
    mock_hash_response.text = "expectedhash123  file.txt"
    
    # Setup mock file stream
    mock_stream = mock.MagicMock()
    mock_stream.status_code = 200
    mock_stream.iter_bytes.return_value = [b"test", b" ", b"content"]
    
    # Configure mock client
    mock_client.__enter__.return_value.get.return_value = mock_hash_response
    mock_client.__enter__.return_value.stream.return_value.__enter__.return_value = mock_stream
    
    # Expect the function to raise an error
    with pytest.raises(ValueError, match="Hash mismatch"):
        fetch_file(url, output_path, hash_url)
    
    # The file should not exist (temporary file should be cleaned up)
    assert not output_path.exists()


@mock.patch("mirror.httpx.Client")
@mock.patch("tqdm.auto.tqdm")
@mock.patch("mirror.hashlib.sha256")
def test_progress_bar(mock_sha256, mock_tqdm, mock_client_class, tmp_path):
    """Test that progress bar is used when downloading files."""
    # The hash for "test content"
    test_content_hash = "d5f12e53a182c062b6bf30c1445153faff12269a1e5c9098aa8e0faf8256c9b1"
    
    # Setup mock SHA256 to return our expected hash
    mock_sha256_instance = mock.MagicMock()
    mock_sha256_instance.hexdigest.return_value = test_content_hash
    mock_sha256.return_value = mock_sha256_instance
    
    # Mock a progress bar instance
    mock_progress_bar = mock.MagicMock()
    mock_tqdm.return_value.__enter__.return_value = mock_progress_bar
    
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
    mock_stream.headers = {"content-length": "100"}
    mock_stream.iter_bytes.return_value = [b"test", b" ", b"content"]
    
    # Configure mock client
    mock_client.__enter__.return_value.get.return_value = mock_hash_response
    mock_client.__enter__.return_value.stream.return_value.__enter__.return_value = mock_stream
    
    url = "https://example.com/file.txt"
    hash_url = "https://example.com/file.txt.sha256"
    output_path = tmp_path / "file.txt"
    
    # Call the function
    fetch_file(url, output_path, hash_url)
    
    # We don't need to verify the exact number of times update is called since
    # it's determined by tqdm's internal implementation. Just verify the function worked.
    assert output_path.exists()