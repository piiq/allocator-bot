import json
import logging
import os
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from .agent import execution_loop
from .models import AgentQueryRequest
from .utils import require_api_key

# Load environment variables and configuration
DATA_FOLDER_PATH = os.getenv("DATA_FOLDER_PATH", None)
API_KEYS_FILE_PATH = os.getenv("API_KEYS_FILE_PATH", None)
HOST_URL = os.getenv("HOST_URL", None)

if not DATA_FOLDER_PATH or not API_KEYS_FILE_PATH or not HOST_URL:
    raise ValueError(
        "DATA_FOLDER_PATH, API_KEYS_FILE_PATH and HOST_URL must be set in the environment variables"
    )

# Load API keys
with open(API_KEYS_FILE_PATH, "r") as f:
    api_keys = [line.strip() for line in f.readlines()]

# Load configuration files
widgets_json_path = os.path.join(os.path.dirname(__file__), "widgets.json")
copilots_json_path = os.path.join(os.path.dirname(__file__), "copilots.json")

with open(widgets_json_path, "r") as f:
    widgets_json = json.load(f)

with open(copilots_json_path, "r") as f:
    copilots_json = json.load(f)

app = FastAPI()

# Configure CORS
origins = [
    "http://localhost",
    "http://localhost:1420",
    "http://localhost:5050",
    "https://pro.openbb.co",
    "https://excel.openbb.co",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.info("Startup complete")


@app.get("/")
def read_root():
    return {"info": "Asset basket allocator"}


@app.get("/widgets.json")
def get_widgets(header: str = Depends(require_api_key(api_keys=api_keys))):
    """Widgets configuration file for OpenBB Workspace."""
    return JSONResponse(content=widgets_json)


@app.get("/copilots.json")
def get_copilot_description(
    header: str = Depends(require_api_key(api_keys=api_keys)),
):
    """Copilot configuration file for OpenBB Workspace."""
    return JSONResponse(content=copilots_json)


@app.get("/allocation_data")
def get_allocation_data(
    allocation_id: str = None,
    risk_model: str = None,
    weights_or_quantities: str = "weights",
    header: str = Depends(require_api_key(api_keys=api_keys)),
):
    """Fetch allocation data.

    This is an endpoint that powers the relevant widget.
    """
    if not allocation_id:
        return JSONResponse(content={"error": "Allocation ID is required"})

    with open(os.path.join(DATA_FOLDER_PATH, "allocations.json"), "r") as f:
        allocations = json.load(f)

    selected_allocation = allocations.get(
        allocation_id, [{"Ticker": "N/A", "Quantity": 0}]
    )

    if risk_model:
        if isinstance(risk_model, str):
            risk_model = [risk_model]
        selected_allocation = [
            allocation
            for allocation in selected_allocation
            if allocation["Risk Model"] in risk_model
        ]

    if weights_or_quantities == "quantities":
        selected_allocation = [
            {key: allocation[key] for key in allocation if key != "Weight"}
            for allocation in selected_allocation
        ]
    else:
        selected_allocation = [
            {key: allocation[key] for key in allocation if key != "Quantity"}
            for allocation in selected_allocation
        ]

    return JSONResponse(content={"allocation": selected_allocation})


@app.post("/v1/query")
async def query(request: AgentQueryRequest) -> EventSourceResponse:
    """Query the Allocator Bot."""
    return EventSourceResponse(execution_loop(request))
