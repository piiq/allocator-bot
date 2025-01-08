import argparse
import logging
import os
from dotenv import load_dotenv
import uvicorn

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logging.info("Starting allocator bot")


def main(args):
    from allocator_bot.api import app

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Allocator Bot")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP address")
    parser.add_argument("--port", type=int, default=4322, help="Port number")

    args = parser.parse_args()
    main(args)
