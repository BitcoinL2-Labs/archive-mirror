# Archive Mirror

Mirror remote HTTP files by downloading them and verifying their hashes.

## Usage

### Command Line

```bash
# With uv
uv run mirror.py <url> <output_path> <hash_url>

# Basic usage
mirror <url> <output_path> <hash_url>

# Example
mirror https://example.com/file.tar.gz /path/to/save/file.tar.gz https://example.com/file.tar.gz.sha256

# With verbose output
mirror -v https://example.com/file.tar.gz /path/to/save/file.tar.gz https://example.com/file.tar.gz.sha256

# Quiet mode (only errors)
mirror -q https://example.com/file.tar.gz /path/to/save/file.tar.gz https://example.com/file.tar.gz.sha256
```

### Locking

The tool uses a file locking mechanism to prevent concurrent downloads of the same file:

- When a download starts, a lock file with the `.downloading` suffix is created
- If another process tries to download the same file, it detects the lock file and skips the download
- The lock file is automatically removed when the download completes or fails
- This ensures that multiple instances (e.g., from timer-triggered services) won't conflict

Example lock file path: `/path/to/save/file.tar.gz.downloading`

### NixOS Module

This project includes a NixOS module that allows you to set up periodic file mirroring as a service with strong security hardening.

#### Adding to your NixOS configuration (flake-based)

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    archive-mirror.url = "github:your-username/archive_mirror";
  };

  outputs = { self, nixpkgs, archive-mirror, ... }: {
    nixosConfigurations.your-host = nixpkgs.lib.nixosSystem {
      # ...
      modules = [
        # ...
        archive-mirror.nixosModules.default
      ];
    };
  };
}
```

#### Configuration

```nix
{ config, pkgs, ... }:

{
  services.archive-mirror = {
    enable = true;
    
    # Required - specify the package to use
    package = pkgs.archive-mirror;
    
    mirrors = {
      # Example: download the stacks blockchain archive
      stacks-blockchain = {
        url = "https://host/mainnet/stacks-blockchain/mainnet-stacks-blockchain-latest.tar.gz";
        hashUrl = "https://host/mainnet/stacks-blockchain/mainnet-stacks-blockchain-latest.sha256";
        outputPath = "/var/lib/archive-mirror/stacks-blockchain/mainnet-stacks-blockchain-latest.tar.gz";
        interval = "30min";  # Run every 30 minutes (default)
        user = "archive-mirror";  # User to run as (default: nobody)
        group = "archive-mirror";  # Group to run as (default: nogroup)
      };
      
      # Add more mirrors as needed
      another-file = {
        url = "https://example.com/some-file.zip";
        hashUrl = "https://example.com/some-file.zip.sha256";
        outputPath = "/var/lib/archive-mirror/example/some-file.zip";
        interval = "1h";  # Run every hour
      };
    };
  };
  
  # Create the user and group for the service (recommended)
  users.users.archive-mirror = {
    isSystemUser = true;
    group = "archive-mirror";
    description = "Archive Mirror Service User";
    home = "/var/lib/archive-mirror";
    createHome = true;
  };
  
  users.groups.archive-mirror = {};
  
  # Ensure the data directory exists with correct permissions
  systemd.tmpfiles.rules = [
    "d /var/lib/archive-mirror 0755 archive-mirror archive-mirror -"
    "d /var/lib/archive-mirror/stacks-blockchain 0755 archive-mirror archive-mirror -"
    "d /var/lib/archive-mirror/example 0755 archive-mirror archive-mirror -"
  ];
}
```

### Module Options

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `enable` | Enable Archive Mirror services | `false` | `true` |
| `package` | The archive-mirror package to use | (required) | - |
| `mirrors.<name>.url` | URL to download | (required) | `"https://example.com/file.tar.gz"` |
| `mirrors.<name>.hashUrl` | URL of the file containing the hash | (required) | `"https://example.com/file.tar.gz.sha256"` |
| `mirrors.<name>.outputPath` | Path where to save the downloaded file | (required) | `"/var/lib/archive-mirror/file.tar.gz"` |
| `mirrors.<name>.interval` | How often to run the mirror service | `"30min"` | `"1h"` |
| `mirrors.<name>.user` | User to run the service as | `"nobody"` | `"archive-mirror"` |
| `mirrors.<name>.group` | Group to run the service as | `"nogroup"` | `"archive-mirror"` |

Each mirror configuration will create:

1. A systemd service that performs the download
2. A systemd timer that runs the service periodically
3. A properly sandboxed execution environment with minimal privileges

## Development

### Requirements

- Nix with flakes enabled

### Setup Development Environment

```bash
# Enter the development shell
nix develop

# Run the tool
mirror <url> <output_path> <hash_url>

# Run tests
pytest
```

## License

MIT

