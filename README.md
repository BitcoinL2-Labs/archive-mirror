# Archive Mirror

A reliable file mirroring tool that downloads and verifies files based on their hashes.

## Features

- Downloads files from HTTP(S) sources
- Verifies file integrity using SHA256 hashes
- Only downloads when files have changed (hash-based)
- Safe concurrent operation with download locking
- Progress bar with download speed and ETA
- NixOS module for automatic periodic downloads
- Hardened systemd services with security confinement

## Usage

### Command Line

```bash
# Basic usage
mirror <url> <output_path> <hash_url>

# Example
mirror https://example.com/file.tar.gz /path/to/save/file.tar.gz https://example.com/file.tar.gz.sha256

# With verbose output
mirror -v https://example.com/file.tar.gz /path/to/save/file.tar.gz https://example.com/file.tar.gz.sha256

# Quiet mode (only errors)
mirror -q https://example.com/file.tar.gz /path/to/save/file.tar.gz https://example.com/file.tar.gz.sha256
```

### Safe Concurrent Operation

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

### Security Features

The NixOS module implements extensive security hardening for the systemd services:

#### Filesystem Restrictions
- `ProtectSystem = "strict"`: Mounts `/usr` and `/boot` as read-only, makes `/etc` inaccessible
- `ProtectHome = true`: Makes home directories inaccessible
- `PrivateTmp = true`: Uses a private `/tmp` directory
- `ReadWritePaths`: Only allows writing to the configured output directory

#### Process Isolation
- `PrivateDevices = true`: Blocks access to physical devices
- `ProtectKernelTunables/Modules/ControlGroups`: Restricts kernel access
- `RestrictNamespaces = true`: Prevents creating namespaces
- `NoNewPrivileges = true`: Prevents gaining new privileges
- `MemoryDenyWriteExecute = true`: Prevents memory that is both writable and executable
- `ProcSubset = "pid"`: Limits the visible `/proc` filesystem to only PIDs

#### Network Restrictions
- `RestrictAddressFamilies = "AF_INET AF_INET6"`: Only allows IPv4/IPv6 networking
- `PrivateNetwork = false`: Network access is allowed (needed for HTTP downloads)
- `IPAddressAllow = "any"`: Allows connecting to any IP address

#### System Call Filtering
- Uses `SystemCallFilter` to restrict syscalls to only those needed:
  - `@system-service`: Allows basic system service calls
  - `~@privileged @resources`: Blocks privileged and resource management calls
  - Explicitly allows necessary networking syscalls (`connect`, `socket`, `bind`)
- `SystemCallArchitectures = "native"`: Prevents using non-native architectures for syscalls

These security measures ensure that even if the service is compromised, the damage is limited to the output directory. The service runs with minimal privileges and access to system resources.

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