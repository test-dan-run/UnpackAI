"""Run the server: python -m unpackai_server [--host 127.0.0.1] [--port 8000]

python -m unpackai_server --check-schemas checks that the Claude API accepts
the output schema of each call, and then exits. It reads the key from the
Docker secret, so run it in the app container:

    docker exec unpackai-app-1 python -m unpackai_server --check-schemas
"""
import argparse
import os
import sys

import uvicorn

from .app import create_app
from .safe_logging import configure_logging, uvicorn_log_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the UnpackAI server.")
    parser.add_argument("--host", default="127.0.0.1", help="Address to listen on. The default only accepts connections from this computer.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--check-schemas", action="store_true", help="Check that the Claude API accepts the schema of each call, and exit.")
    args = parser.parse_args()
    if args.check_schemas:
        sys.exit(check_schemas())
    uvicorn.run(create_app(), host=args.host, port=args.port, log_config=uvicorn_log_config(), access_log=False)


def check_schemas() -> int:
    from .db import Database
    from .unpack import Unpacker, describe_error

    configure_logging()
    unpacker = Unpacker(Database(":memory:"), model=os.environ.get("UNPACKAI_MODEL", "claude-opus-5-5"))
    try:
        results = unpacker.check_schemas()
    except Exception as exc:
        print(f"The check stopped: {describe_error(exc)}")
        return 2
    for name, result in results:
        print(f"{name}: {result}")
    return 0 if all(result == "accepted" for name, result in results if "." not in name) else 1


if __name__ == "__main__":
    main()
