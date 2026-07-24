{
  description = "Rat hindlimb musculoskeletal model";

  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

  outputs = { nixpkgs, ... }:
    let
      systems = [
        "aarch64-darwin"
        "aarch64-linux"
        "x86_64-darwin"
        "x86_64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs {
            inherit system;
            config.allowUnfree = true;
          };

          tools = with pkgs; [
            pyright
            ruff
            uv
            git
            cmake
            gcc
            gnumake
          ];
        in
        {
          default = pkgs.mkShell {
            packages = tools;
            shellHook = ''
              echo "rat-hindlimb-model dev shell"
              echo "  uv sync           — install deps"
              echo "  make               — run full model pipeline"
              echo "  make 01            — non-muscle edits"
              echo "  make 02            — muscle edits"
              echo "  make 03            — bilateral mirroring"
            '';
          };
        });
    };
}
