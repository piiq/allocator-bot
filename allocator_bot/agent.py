import json
import logging
from typing import AsyncGenerator
from uuid import uuid4


from magentic import (
    AssistantMessage,
    AsyncStreamedStr,
    OpenaiChatModel,
    SystemMessage,
    UserMessage,
    chatprompt,
    prompt,
)

from .models import (
    AgentQueryRequest,
    ArtifactSSE,
    ArtifactSSEData,
    StatusUpdateSSE,
    StatusUpdateSSEData,
    TaskStructure,
)
from .prompts import (
    DO_I_NEED_TO_ALLOCATE_THE_PORTFOLIO_PROMPT,
    PARSE_USER_MESSAGE_TO_STRUCTURE_THE_TASK,
    SYSTEM_PROMPT,
)
from .utils import is_last_message, sanitize_message, generate_id

from .portfolio import prepare_allocation, save_allocation

logger = logging.getLogger(__name__)


def need_to_allocate_portfolio(conversation: str) -> bool:
    """Determine if the user needs to allocate the portfolio right now."""

    @prompt(
        DO_I_NEED_TO_ALLOCATE_THE_PORTFOLIO_PROMPT,
        model=OpenaiChatModel(model="gpt-4o-mini", temperature=0.0),
    )
    def _need_to_allocate_portfolio(conversation: str) -> bool: ...

    # I'm using a while loop here for exception handling. This is to retry
    # the prompt if the LLM returns something that is not a boolean.
    attempt = 0
    while attempt <= 5:
        try:
            need_to_allocate = _need_to_allocate_portfolio(conversation)
            if isinstance(need_to_allocate, bool):
                return need_to_allocate
            else:
                raise ValueError("Need to allocate portfolio is not a boolean")
        except Exception as e:
            attempt += 1
            if attempt > 5:
                logger.error(f"Error parsing user message: {e}")
                raise e


def get_task_structure(messages: str) -> dict:
    """Get the task structure from the user messages."""

    @prompt(
        PARSE_USER_MESSAGE_TO_STRUCTURE_THE_TASK,
        model=OpenaiChatModel(model="gpt-4o", temperature=0.0),
    )
    def parse_user_message(conversation: str) -> TaskStructure: ...

    # I'm using a while loop here for exception handling. This is to retry the
    # prompt if the LLM fails to return a an answer with the requires structure.
    attempt = 0
    while attempt <= 5:
        try:
            task_structure = parse_user_message(messages)
            return task_structure
        except Exception as e:
            attempt += 1
            if attempt > 5:
                logger.error(f"Error parsing user message: {e}")
                raise e


async def execution_loop(request: AgentQueryRequest) -> AsyncGenerator[dict, None]:
    """Process the query and generate responses."""

    chat_messages = []
    for message in request.messages:
        if message.role == "ai":
            chat_messages.append(
                AssistantMessage(content=sanitize_message(message.content))
            )
        elif message.role == "human":
            user_message_content = sanitize_message(message.content)
            chat_messages.append(UserMessage(content=user_message_content))
            if is_last_message(message, request.messages):

                # I intentionally am not using function calling in this example
                # because I want all the logic that is under the hood to be exposed
                # explicitly so that others can use this code as a reference to learn
                # what's going on under the hood and how server sent events
                # are being yielded.
                if need_to_allocate_portfolio(str(chat_messages)):
                    yield StatusUpdateSSE(
                        data=StatusUpdateSSEData(
                            eventType="INFO",
                            message="Starting asset basket allocation...\n"
                            + "Fetching task structure...",
                        ),
                    ).model_dump()

                    task_structure = get_task_structure(str(chat_messages))

                    yield StatusUpdateSSE(
                        data=StatusUpdateSSEData(
                            eventType="INFO",
                            message="Task structure:",
                            details=[task_structure.__pretty_dict__()],
                        ),
                    ).model_dump()

                    yield StatusUpdateSSE(
                        data=StatusUpdateSSEData(
                            eventType="INFO", message="Fetching historical prices..."
                        ),
                    ).model_dump()

                    task_dict = task_structure.model_dump()
                    task_dict.pop("task")
                    allocation = None
                    try:
                        allocation = prepare_allocation(**task_dict)

                    except Exception as e:
                        yield StatusUpdateSSE(
                            event="copilotStatusUpdate",
                            data=StatusUpdateSSEData(
                                eventType="ERROR",
                                message=f"Error preparing allocation. {str(e)}",
                            ),
                        ).model_dump()
                        chat_messages.append(
                            AssistantMessage(
                                content=f"Error preparing allocation. {str(e)}"
                            )
                        )
                        chat_messages.append(UserMessage(content="What should I do?"))

                    if allocation is not None:
                        try:
                            yield StatusUpdateSSE(
                                event="copilotStatusUpdate",
                                data=StatusUpdateSSEData(
                                    eventType="INFO",
                                    message="Basket weights optimized. Saving allocation...",
                                ),
                            ).model_dump()

                            allocation_id = save_allocation(
                                allocation_id=generate_id(length=2),
                                allocation_data=allocation.to_dict(orient="records"),
                            )

                            yield StatusUpdateSSE(
                                event="copilotStatusUpdate",
                                data=StatusUpdateSSEData(
                                    eventType="INFO",
                                    message="Allocation saved successfully.",
                                ),
                            ).model_dump()

                            yield ArtifactSSE(
                                data=ArtifactSSEData(
                                    type="table",
                                    name="Allocation",
                                    description="Allocation of assets to the in the basket.",
                                    uuid=uuid4(),
                                    content=allocation.to_dict(orient="records"),
                                ),
                            ).model_dump()

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
                        except Exception as e:
                            yield StatusUpdateSSE(
                                event="copilotStatusUpdate",
                                data=StatusUpdateSSEData(
                                    eventType="ERROR",
                                    message=f"Error saving allocation. {str(e)}",
                                ),
                            ).model_dump()

    @chatprompt(
        SystemMessage(SYSTEM_PROMPT),
        *chat_messages,
        model=OpenaiChatModel(model="gpt-4o", temperature=0.7),
    )
    async def _llm() -> AsyncStreamedStr | str: ...

    llm_result = await _llm()

    if isinstance(llm_result, str):
        yield {
            "event": "copilotMessageChunk",
            "data": json.dumps({"delta": llm_result}),
        }
    else:
        async for chunk in llm_result:
            yield {"event": "copilotMessageChunk", "data": json.dumps({"delta": chunk})}
