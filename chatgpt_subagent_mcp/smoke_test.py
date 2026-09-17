"""Syntax/import smoke test. Does not spend API credits."""
import importlib


def main() -> None:
    mod = importlib.import_module("server")
    assert hasattr(mod, "mcp")
    assert callable(mod.delegate)
    assert callable(mod.swarm)
    print("OK: MCP server imports and subagent tools are registered in module scope.")


if __name__ == "__main__":
    main()
