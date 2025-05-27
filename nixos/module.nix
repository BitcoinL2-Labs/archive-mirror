{ lib, config, pkgs, ... }:

with lib;

let
  cfg = config.services.archive-mirror;

  # Helper function to create a mirror service
  createMirrorService = name: mirrorCfg:
    let
      # Service command to run mirror.py
      mirrorCommand =
        "${cfg.package}/bin/mirror ${mirrorCfg.url} ${mirrorCfg.outputPath} ${mirrorCfg.hashUrl}";

      # Service name
      serviceName = "archive-mirror-${name}";
    in {
      # Define the systemd service
      "${serviceName}" = {
        description = "Archive Mirror Service for ${mirrorCfg.url}";

        # Service configuration
        serviceConfig = {
          Type = "oneshot";
          ExecStart = mirrorCommand;
          User = mirrorCfg.user;
          Group = mirrorCfg.group;

          # File system restrictions
          ProtectSystem = "strict";
          ProtectHome = true;
          PrivateTmp = true;
          PrivateDevices = true;
          ProtectKernelTunables = true;
          ProtectKernelModules = true;
          ProtectControlGroups = true;
          RestrictNamespaces = true;

          # Process restrictions
          NoNewPrivileges = true;
          RestrictRealtime = true;
          MemoryDenyWriteExecute = true;
          LockPersonality = true;
          RestrictSUIDSGID = true;
          ProtectHostname = true;
          ProtectClock = true;
          ProtectProc = "invisible";
          ProcSubset = "pid";

          # Capability restrictions
          CapabilityBoundingSet = "";

          # Only allow network access (for HTTP downloads)
          PrivateNetwork = false;
          RestrictAddressFamilies = "AF_INET AF_INET6";
          IPAddressAllow = "any";

          # Only allow writing to the output directory
          ReadWritePaths = [
            # Allow writing to the output directory
            (dirOf mirrorCfg.outputPath)
          ];

          # Create the output directory if it doesn't exist
          ExecStartPre =
            [ "${pkgs.coreutils}/bin/mkdir -p ${dirOf mirrorCfg.outputPath}" ];

          # Sandbox settings
          SystemCallFilter = [
            "@system-service"
            "~@privileged @resources"
            # Allow necessary networking syscalls for HTTP requests
            "connect"
            "socket"
            "bind"
          ];
          SystemCallArchitectures = "native";
        };
      };

      # Define the timer
      "archive-mirror-${name}-timer" = {
        description = "Timer for Archive Mirror Service (${mirrorCfg.url})";

        # Define the timer configuration
        timerConfig = {
          OnBootSec = "1min";
          OnUnitActiveSec = mirrorCfg.interval;
          RandomizedDelaySec = "30s";
          Unit = "archive-mirror-${name}.service";
        };

        # Enable the timer
        wantedBy = [ "timers.target" ];
      };
    };
in {
  # Module options
  options.services.archive-mirror = {
    enable = mkEnableOption "Enable Archive Mirror services";

    package = mkOption {
      type = types.package;
      description = "The archive-mirror package to use";
    };

    mirrors = mkOption {
      type = types.attrsOf (types.submodule {
        options = {
          url = mkOption {
            type = types.str;
            description = "URL to download";
            example = "https://example.com/file.tar.gz";
          };

          hashUrl = mkOption {
            type = types.str;
            description = "URL of the file containing the hash";
            example = "https://example.com/file.tar.gz.sha256";
          };

          outputPath = mkOption {
            type = types.str;
            description = "Path where to save the downloaded file";
            example = "/var/lib/archive-mirror/file.tar.gz";
          };

          interval = mkOption {
            type = types.str;
            description = "How often to run the mirror service";
            default = "30min";
            example = "1h";
          };

          user = mkOption {
            type = types.str;
            description = "User to run the service as";
            default = "nobody";
          };

          group = mkOption {
            type = types.str;
            description = "Group to run the service as";
            default = "nogroup";
          };
        };
      });
      default = { };
      description = "Attribute set of mirror configurations";
    };
  };

  # Module implementation
  config = mkIf cfg.enable {
    # Create a systemd service and timer for each mirror
    systemd.services = mkMerge (mapAttrsToList createMirrorService cfg.mirrors);

    # Create a systemd timer for each mirror
    systemd.timers = mkMerge (mapAttrsToList createMirrorService cfg.mirrors);
  };
}

