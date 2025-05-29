{ lib, config, pkgs, ... }:

with lib;

let
  cfg = config.services.archive-mirror;

  createName = name: "stacks-archive-mirror-${name}";

  # Helper function to create a mirror service
  createMirrorService = name: mirrorCfg:
    let
      # Service command to run mirror.py
      mirrorCommand =
        "${cfg.package}/bin/mirror ${mirrorCfg.url} ${mirrorCfg.outputPath} ${mirrorCfg.hashUrl}";

      # Service name
      serviceName = createName name;
    in {
      # Define the systemd service
      "${serviceName}" = {
        description = "Stacks Archive Mirror Service for ${mirrorCfg.url}";

        # Service configuration
        serviceConfig = {
          Type = "oneshot";
          ExecStart = mirrorCommand;
          User = mirrorCfg.user;
          Group = mirrorCfg.group;

          PrivateTmp = "true";
          ProtectSystem = "full";
          NoNewPrivileges = "true";
          PrivateDevices = "true";
          MemoryDenyWriteExecute = "true";

          # Create the output directory if it doesn't exist
          ExecStartPre =
            [ "${pkgs.coreutils}/bin/mkdir -p ${dirOf mirrorCfg.outputPath}" ];
        };
      };
    };

  createMirrorTimer = name: mirrorCfg:
    let
      # Service name
      serviceName = createName name;
    in {
      # Define the timer
      "${serviceName}-timer" = {
        description =
          "Timer for Stacks Archive Mirror Service (${mirrorCfg.url})";

        # Define the timer configuration
        timerConfig = {
          OnBootSec = "1min";
          OnUnitActiveSec = mirrorCfg.interval;
          RandomizedDelaySec = "30s";
          Unit = "${serviceName}.service";
        };

        # Enable the timer
        wantedBy = [ "timers.target" ];
      };
    };
in {
  # Module options
  options.services.archive-mirror = {
    enable = mkEnableOption "Enable Stacks Archive Mirror services";

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
    systemd.timers = mkMerge (mapAttrsToList createMirrorTimer cfg.mirrors);
  };
}

