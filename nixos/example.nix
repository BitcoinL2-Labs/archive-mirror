# Example NixOS configuration to use the archive-mirror module
{ config, pkgs, ... }:

{
  # Import the module
  imports = [ 
    # In an actual configuration, you would import from the flake:
    # inputs.archive-mirror.nixosModules.default
    ./module.nix 
  ];

  # Enable the archive-mirror service
  services.archive-mirror = {
    enable = true;
    
    # Uncomment this in a real configuration
    # package = pkgs.archive-mirror;
    
    # Define mirrors to download
    mirrors = {
      # Example: download the stacks blockchain archive
      stacks-blockchain = {
        url = "https://host/mainnet/stacks-blockchain/mainnet-stacks-blockchain-latest.tar.gz";
        hashUrl = "https://host/mainnet/stacks-blockchain/mainnet-stacks-blockchain-latest.sha256";
        outputPath = "/var/lib/archive-mirror/stacks-blockchain/mainnet-stacks-blockchain-latest.tar.gz";
        interval = "30min";  # Run every 30 minutes
        user = "archive-mirror";
        group = "archive-mirror";
      };
      
      # Example: download another file
      another-file = {
        url = "https://example.com/some-file.zip";
        hashUrl = "https://example.com/some-file.zip.sha256";
        outputPath = "/var/lib/archive-mirror/example/some-file.zip";
        interval = "1h";  # Run every hour
        user = "archive-mirror";
        group = "archive-mirror";
      };
    };
  };
  
  # Create the user and group for the service
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