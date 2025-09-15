import json
import logging
import os
from contextlib import asynccontextmanager

import pandas as pd  # type: ignore
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer
from openbb_ai.models import QueryRequest  # type: ignore[import-untyped]
from sse_starlette.sse import EventSourceResponse

from .agent import execution_loop
from .config import config
from .storage import load_allocations, load_tasks
from .utils import validate_api_key
from .validation import validate_environment


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: run startup validations before serving."""
    await validate_environment(config)
    logging.info("Startup complete")
    yield


app = FastAPI(lifespan=lifespan)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    if not validate_api_key(token=token, api_key=config.app_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


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

logging.info("API module loaded")


@app.get("/", openapi_extra={"widget_config": {"exclude": True}})
async def read_root():
    return {"info": "Asset basket allocator"}


@app.get("/assets/image.png", openapi_extra={"widget_config": {"exclude": True}})
async def get_image():
    """Serve the image file."""
    image_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "assets", "image.png")
    )
    return FileResponse(image_path, media_type="image/png")


@app.get("/agents.json", openapi_extra={"widget_config": {"exclude": True}})
async def get_agent_description():
    """Agents configuration file for the OpenBB Workspace"""
    return JSONResponse(
        content={
            "allocator_bot": {
                "name": "Allocator Bot",
                "description": "AI-powered allocator bot to answer questions about the asset basket allocation.",
                "image": f"{config.agent_host_url}/assets/image.png",
                "endpoints": {"query": f"{config.agent_host_url}/v1/query"},
                "features": {
                    "streaming": True,
                    "widget-dashboard-select": False,
                    "widget-dashboard-search": False,
                },
            }
        }
    )


@app.get("/apps.json", openapi_extra={"widget_config": {"exclude": True}})
async def get_apps_description():
    """Apps configuration file for the OpenBB Workspace"""
    with open(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "apps.json")), "r"
    ) as f:
        apps_config = json.load(f)

    for config_key in ["img", "img_dark", "img_light"]:
        apps_config[config_key] = f"{config.agent_host_url}/assets/image.png"

    return JSONResponse(content=apps_config)


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
                    "chartView": {
                        "enabled": True,
                        "chartType": "donut",
                        "cellRangeCols": {"donut": ["Ticker", "Weight"]},
                    },
                    "showAll": True,
                    "transpose": False,
                    "columnDefs": [
                        {
                            "field": "Ticker",
                            "headerName": "Ticker",
                            "cellDataType": "text",
                            "width": 100,
                            "pinned": "left",
                        },
                        {
                            "field": "Weight",
                            "headerName": "Weight",
                            "headerTooltip": "Asset weight in allocation",
                            "cellDataType": "number",
                            "formatterFn": "normalizedPercent",
                            "width": 100,
                        },
                        {
                            "field": "Quantity",
                            "headerName": "Quantity",
                            "headerTooltip": "Asset quantity in allocation",
                            "cellDataType": "number",
                            "formatterFn": "int",
                            "width": 100,
                        },
                        {
                            "field": "Risk Model",
                            "headerName": "Risk Model",
                            "cellDataType": "text",
                            "width": 150,
                            "pinned": "right",
                        },
                    ],
                },
            },
        }
    },
)
async def get_allocation_data(
    allocation_id: str | None = None,
    risk_model: str | None = None,
    weights_or_quantities: str = "weights",
    token: str = Depends(get_current_user),
) -> JSONResponse:
    """Fetch allocation data.

    This is an endpoint that powers the relevant widget.
    """
    if not allocation_id:
        return JSONResponse(content={"error": "Allocation ID is required"})

    allocations = await load_allocations()

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


@app.get(
    "/task_data",
    openapi_extra={
        "widget_config": {
            "name": "Allocation Task History",
            "description": "Asset basket allocation task history",
            "endpoint": "/task_data",
            "category": "Allocations",
            "sub_category": "Allocation",
            "source": ["Allocator bot"],
            "gridData": {
                "x": 0,
                "y": 0,
                "w": 40,
                "h": 15,
                "minH": 10,
                "minW": 20,
                "maxH": 100,
                "maxW": 100,
            },
            "widgetId": "task-data",
            "type": "table",
            "params": [
                {
                    "paramName": "start_date",
                    "label": "Start Date",
                    "type": "date",
                    "description": "Filter tasks from this date (YYYY-MM-DD)",
                },
                {
                    "paramName": "end_date",
                    "label": "End Date",
                    "type": "date",
                    "description": "Filter tasks until this date (YYYY-MM-DD)",
                },
                {
                    "paramName": "symbol_search",
                    "label": "Symbol Search",
                    "type": "text",
                    "description": "Filter by asset symbol (partial match)",
                },
            ],
            "data": {
                "dataKey": "tasks",
                "table": {
                    "enableCharts": False,
                    "showAll": True,
                    "transpose": False,
                    "columnDefs": [
                        {
                            "field": "Task ID",
                            "headerName": "Task ID",
                            "cellDataType": "text",
                            "width": 80,
                            "pinned": "left",
                        },
                        {
                            "field": "Timestamp",
                            "headerName": "Task Date",
                            "cellDataType": "date",
                            "width": 80,
                        },
                        {
                            "field": "Assets",
                            "headerName": "Assets",
                            "cellDataType": "text",
                            "width": 100,
                        },
                        {
                            "field": "Investment",
                            "headerName": "Investment (USD)",
                            "cellDataType": "number",
                            "formatterFn": "int",
                            "width": 80,
                        },
                        {
                            "field": "Start Date",
                            "headerName": "Start Date",
                            "cellDataType": "date",
                            "width": 80,
                        },
                        {
                            "field": "End Date",
                            "headerName": "End Date",
                            "cellDataType": "date",
                            "width": 80,
                        },
                        {
                            "field": "Risk Free Rate",
                            "headerName": "% Risk Free Rate",
                            "cellDataType": "number",
                            "formatterFn": "normalizedPercent",
                            "width": 80,
                        },
                        {
                            "field": "Target Return",
                            "headerName": "% Target Return",
                            "cellDataType": "number",
                            "formatterFn": "normalizedPercent",
                            "width": 80,
                        },
                        {
                            "field": "Target Volatility",
                            "headerName": "% Target Volatility",
                            "cellDataType": "number",
                            "formatterFn": "normalizedPercent",
                            "width": 80,
                        },
                    ],
                },
            },
        }
    },
)
async def get_task_data(
    start_date: str | None = None,
    end_date: str | None = None,
    symbol_search: str | None = None,
    token: str = Depends(get_current_user),
) -> JSONResponse:
    """Fetch task data with filtering by date range and symbol search."""
    tasks = await load_tasks()

    if not tasks:
        return JSONResponse(content={"tasks": []})

    df = pd.DataFrame(
        [
            {
                "Task ID": task_id,
                "Timestamp": task_data.get("timestamp", ""),
                "Assets": ", ".join(task_data.get("asset_symbols", [])),
                "Investment": task_data.get("total_investment", 0),
                "Start Date": task_data.get("start_date", "N/A"),
                "End Date": task_data.get("end_date", "N/A"),
                "Risk Free Rate": task_data.get("risk_free_rate", 0),
                "Target Return": task_data.get("target_return", 0),
                "Target Volatility": task_data.get("target_volatility", 0),
            }
            for task_id, task_data in tasks.items()
        ]
    )

    # Apply filters
    if start_date:
        df = df[df["Timestamp"].str[:10] >= start_date]
    if end_date:
        df = df[df["Timestamp"].str[:10] <= end_date]
    if symbol_search:
        df = df[df["Assets"].str.upper().str.contains(symbol_search.upper(), na=False)]

    # Sort by timestamp (newest first)
    df = df.sort_values("Timestamp", ascending=False)

    return JSONResponse(content={"tasks": df.to_dict(orient="records")})


@app.post("/v1/query")
async def query(
    request: QueryRequest, token: str = Depends(get_current_user)
) -> EventSourceResponse:
    """Query the Allocator Bot."""
    return EventSourceResponse(
        (event.model_dump() async for event in execution_loop(request))
    )
