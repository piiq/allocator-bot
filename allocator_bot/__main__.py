import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


def get_app():
    """Get the FastAPI app instance."""
    import os

    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    from .api import app

    return app


if __name__ == "__main__":
    print(
        "Launch the app with `openbb-api --app allocator_bot.__main__:get_app --factory"
    )
