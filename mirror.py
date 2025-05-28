#!/usr/bin/env python3

import hashlib
import logging
import os
import shutil
import sys
from http import HTTPStatus
from pathlib import Path

import httpx
from tqdm.auto import tqdm

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def get_hash_cache_path(output_path: Path) -> Path:
    """Get the path to the hash cache file.

    Args:
        output_path: Path to the main file

    Returns:
        Path: Path to the hash cache file
    """
    return output_path.with_suffix(".sha256")


def parse_hash_file(content: str) -> str:
    """Parse the hash from a sha256 file.

    Args:
        content: The content of the hash file

    Returns:
        str: The hash value

    Raises:
        ValueError: If the hash file format is invalid
    """
    parts = content.strip().split()
    if not parts:
        msg = "Empty hash file"
        raise ValueError(msg)

    # Format is: "hash filename"
    return parts[0]


def fetch_file(url: str, output_path: Path, hash_url: str) -> bool:
    """Fetch a file from URL and store it locally if it has changed.

    Args:
        url: The URL to fetch the file from
        output_path: The path where to save the file
        hash_url: URL to a file containing the hash

    Returns:
        bool: True if the file was updated, False otherwise

    Raises:
        ValueError: If hash_url is not provided or if the hash cannot be retrieved
    """
    logging.debug("Starting fetch_file operation")
    logging.debug("URL: %s", url)
    logging.debug("Output path: %s", output_path)
    logging.debug("Hash URL: %s", hash_url)

    if not hash_url:
        msg = "hash_url must be provided"
        raise ValueError(msg)

    # Create parent directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logging.debug("Output directory exists: %s", output_path.parent)

    # Path for storing the hash
    hash_cache_path = get_hash_cache_path(output_path)

    # Fetch the expected hash
    with httpx.Client() as client:
        hash_response = client.get(hash_url, follow_redirects=True)
        if hash_response.status_code != HTTPStatus.OK:
            msg = f"Failed to fetch hash from {hash_url}: {hash_response.status_code}"
            raise ValueError(msg)

        # Parse the hash file (format: "hash filename")
        try:
            expected_hash = parse_hash_file(hash_response.text)
        except ValueError as e:
            msg = f"Invalid hash file format: {e}"
            raise ValueError(msg) from e

        if not expected_hash:
            msg = f"Empty hash received from {hash_url}"
            raise ValueError(msg)

    # Check if file exists locally and compare with cached hash
    if output_path.exists() and hash_cache_path.exists():
        try:
            with open(hash_cache_path) as f:
                cached_hash = parse_hash_file(f.read())

            if cached_hash == expected_hash:
                logging.info(
                    "File %s hasn't changed (hash match), skipping download",
                    url,
                )
                return False
        except (OSError, ValueError):
            # If we can't read the hash cache or it's invalid, continue with download
            logging.warning(
                "Could not read hash cache at %s, will download file",
                hash_cache_path,
            )

    # Create the output directory if it doesn't exist
    output_dir = output_path.parent
    os.makedirs(output_dir, exist_ok=True)

    # Use a consistent temporary file name with .downloading suffix as a lock
    downloading_path = output_path.with_suffix(output_path.suffix + ".downloading")

    # Check if another process is already downloading this file
    if downloading_path.exists():
        logging.info(
            "Another process is already downloading %s (lock file %s exists)",
            url,
            downloading_path,
        )
        return False

    logging.info("Creating temporary file at %s", downloading_path)
    logging.info("Will download to %s after verification", output_path)

    # Create the temporary file
    with open(downloading_path, "wb") as temp_file:
        # Stream the file to disk to avoid loading the entire file into memory
        sha256 = hashlib.sha256()
        success = False

        try:
            # Use HTTP client to stream the file
            with (
                httpx.Client() as client,
                client.stream("GET", url, follow_redirects=True) as response,
            ):
                # If there was an error, bail
                if response.status_code != HTTPStatus.OK:
                    logging.error(
                        "Error fetching %s: %s",
                        url,
                        response.status_code,
                    )
                    return False

                # Get total size if available
                total_size = int(response.headers.get("content-length", 0)) or None

                # Set up progress bar description
                desc = f"Downloading {url.split('/')[-1]}"

                # Use progress bar for streaming download
                with tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=desc,
                    # Auto-disable in non-interactive sessions
                    disable=None,
                ) as progress_bar:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        temp_file.write(chunk)
                        sha256.update(chunk)
                        progress_bar.update(len(chunk))
                        # Ensure data is written to disk
                        temp_file.flush()

            # Verify hash
            downloaded_hash = sha256.hexdigest()
            if downloaded_hash != expected_hash:
                logging.warning("Hash mismatch for %s", url)
                logging.warning("Expected: %s", expected_hash)
                logging.warning("Got: %s", downloaded_hash)
                msg = f"Hash mismatch for {url}"
                raise ValueError(msg)

            # If we got here, the download was successful and hash matches
            success = True

            # Move the temporary file to the final destination
            logging.info(
                "Moving temporary file from %s to %s",
                downloading_path,
                output_path,
            )
            shutil.move(downloading_path, output_path)

            # Store the hash in cache file with proper format
            logging.info("Saving hash to %s", hash_cache_path)
            with open(hash_cache_path, "w") as f:
                f.write(f"{expected_hash}  {output_path}")

            logging.info("Successfully downloaded %s to %s", url, output_path)
            return success

        finally:
            # Clean up the temporary file if something went wrong
            if not success and downloading_path.exists():
                logging.info("Cleaning up temporary file %s", downloading_path)
                os.unlink(downloading_path)


def main() -> int:
    """Main function to mirror a file."""
    import argparse

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Mirror a file with hash verification")
    parser.add_argument("url", help="URL of the file to download")
    parser.add_argument("output_path", help="Path where to save the file")
    parser.add_argument("hash_url", help="URL of the file containing the hash")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress all output except errors",
    )

    # Parse arguments
    args = parser.parse_args()

    # Configure log level based on verbosity flags
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Verbose logging enabled")
    elif args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
    else:
        logging.getLogger().setLevel(logging.INFO)

    # Convert output path to Path object
    output_path = Path(args.output_path).resolve()

    logging.info("Starting download of %s to %s", args.url, output_path)
    logging.info("Using hash URL: %s", args.hash_url)

    try:
        result = fetch_file(args.url, output_path, args.hash_url)
        if result:
            logging.info("File successfully updated")
        else:
            logging.info("No update needed (file unchanged)")
    except Exception:
        logging.exception("Error occurred during file download")
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
