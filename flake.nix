{
  description = "check-unicode - detect and fix non-ASCII Unicode characters in source files";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";

    # uv2nix builds the dev tooling straight from uv.lock, so the dev shell and
    # `nix flake check` use the same ruff/ty/pytest versions as CI and
    # pre-commit. uv.lock is the single source of truth; nothing here restates a
    # version number.
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      flake-utils,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        lib = pkgs.lib;

        # Track the version declared in the source so bump-my-version stays the
        # single source of truth.
        version = builtins.head (
          builtins.match ''.*__version__ = "([^"]+)".*''
            (builtins.readFile ./src/check_unicode/__init__.py)
        );

        # Dev tooling, resolved from uv.lock. Wheels are preferred because ruff
        # and ty ship prebuilt binaries.
        workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
        pythonSet =
          (pkgs.callPackage pyproject-nix.build.packages { python = pkgs.python311; }).overrideScope
            (lib.composeManyExtensions [
              pyproject-build-systems.overlays.default
              (workspace.mkPyprojectOverlay { sourcePreference = "wheel"; })
            ]);
        devEnv = pythonSet.mkVirtualEnv "check-unicode-dev-env" workspace.deps.all;

        # What we ship is built from nixpkgs, not from the dev lock: the CLI has
        # zero runtime dependencies, so there is nothing for uv.lock to pin here,
        # and this keeps `nix build` a plain, idiomatic Python application.
        check-unicode = pkgs.python312Packages.buildPythonApplication {
          pname = "check-unicode";
          inherit version;
          pyproject = true;
          src = ./.;

          build-system = [ pkgs.python312Packages.hatchling ];
          # Zero runtime dependencies by design.

          nativeCheckInputs = with pkgs.python312Packages; [
            pytestCheckHook
            pytest-cov
            pytest-sugar
          ];

          nativeBuildInputs = [ pkgs.installShellFiles ];
          postInstall = ''
            installManPage docs/check-unicode.1
          '';

          meta = {
            description = "Detect and fix non-ASCII Unicode characters in source files";
            homepage = "https://github.com/mit-d/check-unicode";
            license = pkgs.lib.licenses.mit;
            mainProgram = "check-unicode";
          };
        };
      in
      {
        packages.default = check-unicode;
        packages.check-unicode = check-unicode;

        apps.default = {
          type = "app";
          program = "${check-unicode}/bin/check-unicode";
        };

        devShells.default = pkgs.mkShell {
          packages = [
            devEnv # python, pytest, ruff, ty, bump-my-version -- all from uv.lock
            pkgs.uv
            pkgs.pre-commit
          ];
          # src-layout: put the working tree ahead of the copy of check_unicode
          # that devEnv installed, so edits take effect without a reinstall.
          #
          # Assigned, not appended: other Python packages in this shell (nixpkgs'
          # pre-commit is a python3.14 application) otherwise leak their
          # site-packages onto PYTHONPATH via the Python setup hook and shadow
          # devEnv's own pytest.
          shellHook = ''
            export PYTHONPATH="$PWD/src"

            # Install the git hook on first entry so `git commit` runs the
            # checks. Guarded on the config being in the current directory so
            # entering this shell from elsewhere cannot touch another repo;
            # --git-path resolves correctly inside worktrees.
            if [ -f .pre-commit-config.yaml ]; then
              hooksDir=$(git rev-parse --git-path hooks 2>/dev/null || true)
              if [ -n "$hooksDir" ] && [ ! -e "$hooksDir/pre-commit" ]; then
                pre-commit install
              fi
            fi
          '';
        };

        # `nix flake check` runs the deterministic gate: tests, lint, types.
        #
        # ty is a gate now that its version comes from uv.lock instead of
        # nixpkgs. It is pre-1.0 with a ruleset that shifts between releases, so
        # what makes this safe is the pin, not the tool's maturity: CI, the
        # pre-commit hook, and this check all run the one locked version.
        #
        # pre-commit itself is not a gate: it fetches its hook repos over the
        # network, which the build sandbox forbids. It is provided in the dev
        # shell and installed as a git hook there -- run `pre-commit run -a`.
        checks = {
          # Deliberately nixpkgs' pytest, not the pinned one: this exercises the
          # built application, and passing under a second pytest shows the suite
          # is not coupled to the exact version we develop against.
          pytest = check-unicode;

          ruff = pkgs.runCommand "check-unicode-ruff" { } ''
            cd ${./.}
            ${devEnv}/bin/ruff check --no-cache src/ tests/
            ${devEnv}/bin/ruff format --check --no-cache src/ tests/
            touch $out
          '';

          ty = pkgs.runCommand "check-unicode-ty" { } ''
            cd ${./.}
            ${devEnv}/bin/ty check src/
            touch $out
          '';
        };
      }
    );
}
