import logging
from datetime import date
from typing import AsyncGenerator, Callable

from magentic import (
    AssistantMessage,
    AsyncStreamedStr,
    SystemMessage,
    UserMessage,
    chatprompt,
    prompt,
)
from magentic.chat_model.openrouter_chat_model import OpenRouterChatModel
from magentic.chat_model.retry_chat_model import RetryChatModel
from openbb_ai.helpers import (  # type: ignore[import-untyped]
    citations,
    cite,
    message_chunk,
    reasoning_step,
    table,
)
from openbb_ai.models import (  # type: ignore[import-untyped]
    BaseSSE,
    QueryRequest,
    Widget,
    WidgetParam,
)

from .models import TaskStructure
from .portfolio import prepare_allocation
from .prompts import (
    DO_I_NEED_TO_ALLOCATE_THE_PORTFOLIO_PROMPT,
    PARSE_USER_MESSAGE_TO_STRUCTURE_THE_TASK,
    SYSTEM_PROMPT,
)
from .storage import save_allocation, save_task
from .utils import generate_id, is_last_message, sanitize_message

logger = logging.getLogger(__name__)


@prompt(
    DO_I_NEED_TO_ALLOCATE_THE_PORTFOLIO_PROMPT,
    model=RetryChatModel(
        OpenRouterChatModel(
            model="deepseek/deepseek-chat-v3-0324",
            temperature=0.0,
            provider_sort="latency",
            require_parameters=True,
            provider_ignore=["GMICloud"],
        ),
        max_retries=5,
    ),
)
async def _need_to_allocate_portfolio(conversation: str) -> bool: ...  # type: ignore[empty-body]


@prompt(
    PARSE_USER_MESSAGE_TO_STRUCTURE_THE_TASK,
    model=RetryChatModel(
        OpenRouterChatModel(
            model="deepseek/deepseek-chat-v3-0324",
            temperature=0.0,
            provider_sort="latency",
            require_parameters=True,
            provider_ignore=["GMICloud"],
        ),
        max_retries=5,
    ),
)
async def _get_task_structure(conversation: str) -> TaskStructure: ...  # type: ignore[empty-body]


def make_llm(chat_messages: list) -> Callable:
    @chatprompt(
        SystemMessage(SYSTEM_PROMPT),
        *chat_messages,
        model=OpenRouterChatModel(
            model="deepseek/deepseek-chat-v3-0324",
            temperature=0.7,
            provider_sort="latency",
            require_parameters=True,
        ),
        max_retries=5,
    )
    async def _llm() -> AsyncStreamedStr | str: ...  # type: ignore[empty-body]

    return _llm


async def execution_loop(request: QueryRequest) -> AsyncGenerator[BaseSSE, None]:
    """Process the query and generate responses."""

    chat_messages: list = []
    citations_list: list = []
    for message in request.messages:
        if message.role == "ai":
            if hasattr(message, "content") and isinstance(message.content, str):
                chat_messages.append(
                    AssistantMessage(content=await sanitize_message(message.content))
                )
        elif message.role == "human":
            if hasattr(message, "content") and isinstance(message.content, str):
                user_message_content = await sanitize_message(message.content)
                chat_messages.append(UserMessage(content=user_message_content))
            if await is_last_message(message, request.messages):

                # I intentionally am not using function calling in this example
                # because I want all the logic that is under the hood to be exposed
                # explicitly so that others can use this code as a reference to learn
                # what's going on under the hood and how server sent events
                # are being yielded.
                if await _need_to_allocate_portfolio(str(chat_messages)):
                    yield reasoning_step(
                        message="Starting asset basket allocation...\n"
                        + "Fetching task structure..."
                    )

                    task_structure = await _get_task_structure(str(chat_messages))
                    yield reasoning_step(
                        message="Task structure:",
                        details=task_structure.__pretty_dict__(),
                    )

                    yield reasoning_step(
                        message="Fetching historical prices...",
                        details={"symbols": ", ".join(task_structure.asset_symbols)},
                    )

                    task_dict = task_structure.model_dump()
                    task_dict.pop("task")

                    allocation = None
                    try:
                        allocation = await prepare_allocation(**task_dict)

                    except Exception as e:
                        yield reasoning_step(
                            event_type="ERROR",
                            message=f"Error preparing allocation. {str(e)}",
                        )
                        chat_messages.append(
                            AssistantMessage(
                                content=f"Error preparing allocation. {str(e)}"
                            )
                        )
                        chat_messages.append(UserMessage(content="What should I do?"))

                    if allocation is not None:
                        try:
                            yield reasoning_step(
                                message="Basket weights optimized. Saving task and results...",
                            )

                            allocation_id = await save_allocation(
                                allocation_id=await generate_id(length=2),
                                allocation_data=allocation.to_dict(orient="records"),
                            )

                            task_to_save = task_structure.model_dump()
                            task_to_save.pop("task")
                            # Add current date as the first key of the task data
                            task_to_save["date"] = date.today().isoformat()
                            await save_task(
                                allocation_id=allocation_id,
                                task_data=task_to_save,
                            )

                            yield reasoning_step(
                                message="Allocation saved successfully.",
                            )

                            yield table(
                                data=allocation.to_dict(orient="records"),
                                name=f"Allocation {allocation_id}",
                                description="Allocation of assets to the in the basket.",
                            )

                            chat_messages.append(
                                AssistantMessage(
                                    content=sanitize_message(
                                        f"Allocation created. Allocation id: is `{allocation_id}`. Allocation data is {allocation.to_markdown()}."
                                    )
                                )
                            )
                            chat_messages.append(
                                UserMessage(
                                    content="Write short sub-paragraph summary reports on the allocation for each of the risk models."
                                    + "At the end of your message include the allocation id formatted as an inline code block."
                                )
                            )
                            if allocation_id:
                                citations_list = [
                                    cite(
                                        widget=Widget(
                                            name="Asset allocation data",
                                            widget_id="allocation-data",
                                            description="Allocation data for the portfolio.",
                                            origin="Allocator Bot Backend",
                                            params=[
                                                WidgetParam(
                                                    name="allocation_id",
                                                    type="text",
                                                    description="Unique identifier for the allocation",
                                                )
                                            ],
                                        ),
                                        input_arguments={
                                            "allocation_id": allocation_id
                                        },
                                        extra_details={"allocation_id": allocation_id},
                                    )
                                ]
                        except Exception as e:
                            yield reasoning_step(
                                event_type="ERROR",
                                message=f"Error saving allocation. {str(e)}",
                            )
    _llm = make_llm(chat_messages)
    llm_result = await _llm()

    if isinstance(llm_result, str):
        yield message_chunk(text=llm_result)
    else:
        async for chunk in llm_result:
            yield message_chunk(text=chunk)
    if len(citations_list) > 0:
        yield citations(citations_list)
