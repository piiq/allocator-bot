import json
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openbb_ai.models import QueryRequest  # type: ignore[import-untyped]
from sse_starlette.sse import EventSourceResponse

from .agent import execution_loop
from .config import config, load_allocations_from_s3

app = FastAPI()

# Configure CORS
origins = [
    "http://localhost",
    "http://localhost:1420",
    "http://localhost:5050",
    "https://pro.openbb.co",
    "https://pro.openbb.dev",
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


@app.get("/agents.json")
def get_agent_description():
    """Widgets configuration file for the OpenBB Terminal Pro"""
    return JSONResponse(
        content={
            "vanilla_agent_raw_context": {
                "name": "Allocator Bot",
                "description": "AI-powered allocator bot to answer questions about the asset basket allocation.",
                "image": "https://github.com/OpenBB-finance/copilot-for-terminal-pro/assets/14093308/7da2a512-93b9-478d-90bc-b8c3dd0cabcf",
                "endpoints": {"query": f"{config.agent_host_url}/v1/query"},
                "features": {
                    "streaming": True,
                    "widget-dashboard-select": True,
                    "widget-dashboard-search": False,
                },
            }
        }
    )





@app.get(
    "/allocation_data",
    openapi_extra={
        "widget_config": {
            "name": "Asset basket allocation",
            "description": "Asset basket allocation",
            "endpoint": "/allocation_data",
            "category": "Allocations",
            "sub_category": "Allocation",
            "source": ["Allocator bot"],
            "gridData": {
                "x": 0,
                "y": 0,
                "w": 40,
                "h": 10,
                "minH": 10,
                "minW": 10,
                "maxH": 100,
                "maxW": 100,
            },
            "widgetId": "allocation-data",
            "type": "table",
            "params": [
                {
                    "paramName": "allocation_id",
                    "value": "",
                    "label": "Allocation ID",
                    "type": "text",
                    "description": "Unique identifier for the allocation",
                },
                {
                    "paramName": "risk_model",
                    "label": "Risk Model",
                    "type": "text",
                    "options": [
                        {"label": "Max Sharpe", "value": "max_sharpe"},
                        {"label": "Min Volatility", "value": "min_volatility"},
                        {"label": "Efficient Risk", "value": "efficient_risk"},
                        {"label": "Efficient Return", "value": "efficient_return"},
                    ],
                    "description": "Select the risk model for allocation",
                },
                {
                    "paramName": "weights_or_quantities",
                    "value": "weights",
                    "label": "Weights or Quantities",
                    "type": "text",
                    "options": [
                        {"label": "Weights", "value": "weights"},
                        {"label": "Quantities", "value": "quantities"},
                    ],
                    "description": "Choose between weights or quantities for allocation",
                },
            ],
            "data": {
                "dataKey": "allocation",
                "table": {
                    "enableCharts": True,
                    "chartView": {"enabled": True, "chartType": "donut"},
                    "showAll": True,
                    "transpose": False,
                },
            },
        }
    },
)
def get_allocation_data(
    allocation_id: str | None = None,
    risk_model: str | None = None,
    weights_or_quantities: str = "weights",
    # header: str = Depends(require_api_key(api_key=config.app_api_key)),
) -> JSONResponse:
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
            risk_model_list = [risk_model]
        selected_allocation = [
            allocation
            for allocation in selected_allocation
            if allocation["Risk Model"] in risk_model_list
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
