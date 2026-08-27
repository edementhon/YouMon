from __future__ import annotations
import base64
import io
from PIL import Image
from api.openai_client import get_client
import config


def generate_card_back(
    user_name: str,
    settings: config.GenSettings | None = None,
) -> Image.Image:
    """Single call to generate a card back with '{Name}Mon' branding."""
    settings = settings or config.DEFAULT_GEN
    client = get_client()

    label = f"{user_name}Mon" if user_name else "YouMon"

    response = client.responses.create(
        model=settings.text_model,
        input=(
            f'Design the back of a trading card for a kids\' monster card game called "{label}".\n\n'
            f'- Center the text "{label}" prominently in a stylized, fun font\n'
            f"- Include a decorative swirling pattern around the text\n"
            f"- Color scheme: deep purple and blue gradients with gold accents\n"
            f"- The design should be symmetrical and look like a real trading card back\n"
            f"- Include a small monster silhouette or icon as part of the pattern\n"
            f"- Portrait orientation (taller than wide)\n"
            f"- Professional trading card quality, polished look\n"
            f"- Text must be spelled correctly\n"
            f"- The design must reach all four edges with no white margin"
        ),
        tools=[{
            "type": "image_generation",
            "model": settings.image_model,
            "quality": settings.image_quality,
            "size": settings.image_size,
        }],
    )

    for output in response.output:
        if output.type == "image_generation_call" and getattr(output, "result", None):
            image_bytes = base64.b64decode(output.result)
            return Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    raise RuntimeError(f"{settings.text_model} did not generate a card back image")
