from datetime import datetime
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


model = OpenAIChatModel(
    "Qwen3-VL-Instruct-4B",
    provider=OpenAIProvider(base_url="http://llama.internal.bootleg.technology/v1"),
)

agent = Agent(
    model=model,
    deps_type=Image,
    output_type=AnalysisResult,
    system_prompt="""
You are an assistant tasked with flagging whether images taken from NTV's webcams contain something that should be flagged as interesting.
""",
)


@agent.system_prompt(dynamic=True)
def camera_specific_prompt(ctx: RunContext[Image]) -> str:
    match ctx.deps.camera:
        case "quidividivillage":
            return "The camera is located on a stage in Quidi Vidi Village, St. John's, Newfoundland and Labrador, Canada. It overlooks a portion of the harbour and the stages on the other side of the harbour."
        case _:
            return ""


TEST_SUBJECTS: list[tuple[str, str, datetime, datetime]] = [
    (
        "Quidi Vidi Fire",
        "quidividivillage",
        datetime(2025, 7, 29, hour=22, minute=28, tzinfo=ZoneInfo("America/St_Johns")),
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

        for image in images:
            print(f"Analyzing {image.path} for subject '{subject_name}'...")

            full_path = config.output_path / image.path

            with open(full_path, "rb") as f:
                image_bytes = f.read()

            result = agent.run_sync(
                [BinaryContent(data=image_bytes, media_type="image/jpeg")], deps=image
            )

            print(f"\t{result}")
