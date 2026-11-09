"""Run the server: python -m unpackai_server [--host 127.0.0.1] [--port 8000]"""
import argparse

import uvicorn

from .app import create_app
from .safe_logging import uvicorn_log_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the UnpackAI server.")
    parser.add_argument("--host", default="127.0.0.1", help="Address to listen on. The default only accepts connections from this computer.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(create_app(), host=args.host, port=args.port, log_config=uvicorn_log_config(), access_log=False)


if __name__ == "__main__":
    main()
