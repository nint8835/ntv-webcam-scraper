from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .config import config
from .database import session
from .models import Image


class AnalysisResult(BaseModel):
    interesting: bool
    interesting_reason: str | None = Field(
        default=None,
        description="If the image is interesting, provide an extremely brief reason why.",
    )


class BaseResponse(BaseModel):
    current_summary: str = Field(
        description="A very brief summary of the current image. This will be provided in the system prompt for future images."
    )


class StartEvent(BaseResponse):
    """Begin a new event."""

    action: Literal["start_event"]
    title: str = Field(description="A brief title for the event.")


class EndEvent(BaseResponse):
    """Flag the current event as no longer ongoing. You should only use this if you are CERTAIN that the event has ended and that there is nothing related to it still ongoing."""

    action: Literal["end_event"]
    explanation: str = Field(
        description="A brief explanation for why the event is ending now. This is required to ensure that the event is being ended for a good reason and not just because the image is not interesting."
    )


class NoAction(BaseResponse):
    """Take no action on this image. Use this when there is no change observed."""

    action: Literal["none"]


NoEventActions = Annotated[StartEvent | NoAction, Field(discriminator="action")]
EventActions = Annotated[EndEvent | NoAction, Field(discriminator="action")]


@dataclass
class AnalysisState:
    image: Image
    event_title: str | None = None
    summaries: list[str] = dataclass_field(default_factory=list)


model = OpenAIChatModel(
    "Qwen3.5-35B-A3B",
    provider=OpenAIProvider(base_url="http://llama.internal.bootleg.technology/v1"),
)

agent = Agent(
    model=model,
    deps_type=AnalysisState,
    instructions="""
You are an assistant tasked with flagging whether images taken from NTV's webcams contain something that should be flagged as interesting.
""",
)


@agent.instructions
def camera_specific_prompt(ctx: RunContext[AnalysisState]) -> str:
    match ctx.deps.image.camera:
        case "quidividivillage":
            return "The camera is located on a stage in Quidi Vidi Village, St. John's, Newfoundland and Labrador, Canada. It overlooks a portion of the harbour and the stages on the other side of the harbour."
        case _:
            return ""


@agent.instructions
def current_event(ctx: RunContext[AnalysisState]) -> str:
    if ctx.deps.event_title:
        return f"You have flagged an ongoing event titled '{ctx.deps.event_title}'."
    else:
        return "There is not currently an ongoing event."


@agent.instructions
def previous_summaries(ctx: RunContext[AnalysisState]) -> str:
    if ctx.deps.summaries:
        return (
            f"You have summarized the past {min(len(ctx.deps.summaries), 5)} images as: "
            + "; ".join(ctx.deps.summaries[-5:])
        )
    else:
        return "You have not yet summarized any images."


TEST_SUBJECTS: list[tuple[str, str, datetime, datetime]] = [
    (
        "Quidi Vidi Fire",
        "quidividivillage",
        datetime(2025, 7, 29, hour=23, minute=5, tzinfo=ZoneInfo("America/St_Johns")),
        datetime(2025, 7, 30, tzinfo=ZoneInfo("America/St_Johns")),
    )
]


def test_analysis():
    for subject_name, camera_slug, start_time, end_time in TEST_SUBJECTS:
        with session() as db:
            images = (
                db.query(Image)
                .filter(
                    Image.camera == camera_slug,
                    Image.captured_at >= start_time,
                    Image.captured_at <= end_time,
                )
                .order_by(Image.captured_at.asc())
                .all()
            )

        event_title = None
        summaries = []

        for image in images:
            # print(f"Analyzing {image.path} for subject '{subject_name}'...")

            full_path = config.output_path / image.path

            with open(full_path, "rb") as f:
                image_bytes = f.read()

            result = agent.run_sync(
                [BinaryContent(data=image_bytes, media_type="image/jpeg")],
                deps=AnalysisState(
                    image=image, event_title=event_title, summaries=summaries
                ),
                output_type=NoEventActions if event_title is None else EventActions,
            )

            if result.output.action == "start_event":
                event_title = result.output.title
            elif result.output.action == "end_event":
                event_title = None

            summaries.append(result.output.current_summary)

            print(f"Result: {result.output}")
