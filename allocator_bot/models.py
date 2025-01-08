import json
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue, field_validator, model_validator


class RoleEnum(str, Enum):
    ai = "ai"
    human = "human"
    tool = "tool"


class ChartParameters(BaseModel):
    chartType: Literal["line", "bar", "scatter"]
    xKey: str
    yKey: list[str]


class DataFormat(BaseModel):
    """Describe the format of the data, and how it should be handled."""

    type: Literal["text", "table", "chart"] | None = None
    chart_params: ChartParameters | None = None


class DataContent(BaseModel):
    content: JsonValue = Field(
        description="The data content, which must be JSON-serializable. Can be a primitive type (str, int, float, bool), list, or dict."  # noqa: E501
    )
    data_format: DataFormat | None = Field(
        default=None,
        description="Optional. How the data should be parsed. If not provided, a best-effort attempt will be made to automatically determine the data format.",  # noqa: E501
    )


class LlmFunctionCall(BaseModel):
    function: str
    input_arguments: dict[str, Any]


class LlmMessage(BaseModel):
    role: RoleEnum = Field(
        description="The role of the entity that is creating the message"
    )
    content: LlmFunctionCall | str = Field(
        description="The content of the message or the result of a function call."
    )

    @field_validator("content", mode="before")
    def parse_content(cls, v):
        # We do this to make sure, if the client appends the function call to
        # the messages that we're able to parse it correctly since the client
        # will send the LlmFunctionCall encoded as a string, rather than JSON.
        if isinstance(v, str):
            try:
                parsed_content = json.loads(v)
                if isinstance(parsed_content, str):
                    # Sometimes we need a second decode if the content is
                    # escaped and string-encoded
                    parsed_content = json.loads(parsed_content)
                return LlmFunctionCall(**parsed_content)
            except (json.JSONDecodeError, TypeError, ValueError):
                return v


class LlmClientFunctionCallResult(BaseModel):
    """Contains the result of a function call made against a client."""

    role: RoleEnum = RoleEnum.tool
    function: str = Field(description="The name of the called function.")
    input_arguments: dict[str, Any] | None = Field(
        default=None, description="The input arguments passed to the function"
    )
    data: list[DataContent] = Field(description="The content of the function call.")


class RawContext(BaseModel):
    uuid: UUID = Field(description="The UUID of the widget.")
    name: str = Field(description="The name of the widget.")
    description: str = Field(
        description="A description of the data contained in the widget"
    )
    data: DataContent = Field(description="The data content of the widget")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional widget metadata (eg. the selected ticker, etc)",
    )


class Widget(BaseModel):
    uuid: str = Field(description="The UUID of the widget.")
    name: str = Field(description="The name of the widget.")
    description: str = Field(
        description="A description of the data contained in the widget"
    )
    metadata: dict[Any, Any] | None = Field(
        default=None,
        description="Additional widget metadata (eg. the selected ticker, etc)",
    )


class AgentQueryRequest(BaseModel):
    messages: list[LlmClientFunctionCallResult | LlmMessage] = Field(
        description="A list of messages to submit to the copilot."
    )
    context: str | list[RawContext] | None = Field(
        default=None, description="Additional context."
    )
    use_docs: bool = Field(
        default=None, description="Set True to use uploaded docs when answering query."
    )
    widgets: list[Widget] = Field(
        default=None, description="A list of widgets for the copilot to consider."
    )

    @field_validator("messages")
    @classmethod
    def check_messages_not_empty(cls, value):
        if not value:
            raise ValueError("messages list cannot be empty.")
        return value


class BaseSSE(BaseModel):
    event: Any
    data: Any

    def model_dump(self, *args, **kwargs) -> dict:
        return {
            "event": self.event,
            "data": self.data.model_dump_json(exclude_none=True),
        }


class FunctionCallSSEData(BaseModel):
    function: Literal["get_widget_data"]
    input_arguments: dict
    copilot_function_call_arguments: dict | None = Field(
        default=None,
        description="The original arguments of the function call to copilot. This may be different to what is actually returned as the function call to the client.",  # noqa: E501
    )


class FunctionCallSSE(BaseSSE):
    event: Literal["copilotFunctionCall"] = "copilotFunctionCall"
    data: FunctionCallSSEData


class StatusUpdateSSEData(BaseModel):
    eventType: Literal["INFO", "WARNING", "ERROR"]
    message: str
    group: Literal["reasoning"] = "reasoning"
    details: list[dict[str, str | int | float | None]] | None = None

    @model_validator(mode="before")
    @classmethod
    def exclude_fields(cls, values):
        # Exclude these fields from being in the "details" field.  (since this
        # pollutes the JSON output)
        _exclude_fields = []

        if details := values.get("details"):
            for detail in details:
                for key in list(detail.keys()):
                    if key.lower() in _exclude_fields:
                        detail.pop(key, None)
        return values


class StatusUpdateSSE(BaseSSE):
    event: Literal["copilotStatusUpdate"] = "copilotStatusUpdate"
    data: StatusUpdateSSEData


class ArtifactSSEData(BaseModel):
    type: Literal["text", "table", "chart"]
    name: str
    description: str
    uuid: UUID
    content: str | list[dict]


class ArtifactSSE(BaseSSE):
    event: Literal["copilotMessageArtifact"] = "copilotMessageArtifact"
    data: ArtifactSSEData


class TaskStructure(BaseModel):
    task: str = Field(
        description="The task to perform. Human readable description of the task."
    )
    asset_symbols: list[str] = Field(
        description="A list of asset symbols to include in the portfolio. List of capitalized tickers."
    )
    total_investment: float | int = Field(
        description="The total investment amount to allocate to the portfolio.",
        default=100000,
    )
    start_date: str = Field(
        description="The start date of the portfolio simulation.",
        default="2019-01-01",
    )
    end_date: str | None = Field(
        description="The end date of the portfolio simulation.",
        default=None,
    )
    risk_free_rate: float = Field(
        description="The risk-free rate of the portfolio simulation. Normalized percentage to 1.",
        default=0.05,
    )
    target_return: float = Field(
        description="The target return of the portfolio simulation. Normalized percentage to 1.",
        default=0.15,
    )
    target_volatility: float = Field(
        description="The target volatility of the portfolio simulation. Normalized percentage to 1.",
        default=0.15,
    )

    def __repr__(self):
        return f"TaskStructure(task={self.task}, asset_symbols={self.asset_symbols}, total_investment={self.total_investment}, start_date={self.start_date}, end_date={self.end_date}, risk_free_rate={self.risk_free_rate}, target_return={self.target_return}, target_volatility={self.target_volatility})"

    def __str__(self):
        return f"Task structure:\nAssets:{self.asset_symbols}\nTotal investment:{self.total_investment}\nStart date:{self.start_date}\nEnd date:{self.end_date}\nRisk free rate:{self.risk_free_rate}\nTarget return:{self.target_return}\nTarget volatility:{self.target_volatility}"

    def __pretty_dict__(self):
        return {
            "Assets": ", ".join(self.asset_symbols),
            "Total investment": self.total_investment,
            "Start date": self.start_date,
            "End date": self.end_date,
            "Risk free rate": self.risk_free_rate,
            "Target return": self.target_return,
            "Target volatility": self.target_volatility,
        }
