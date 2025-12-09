from open_ai.gpt import get_openai_client
from core.config import app_settings
from log.logger import get_app_logger
import base64


logger = get_app_logger(__name__)


def extract_text_from_image(image_bytes: bytes) -> str:
    client = get_openai_client()
    response = client.responses.create(
        model=app_settings.openai_image_model, 
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Extract all text from this image."},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
                    }
                ]
            } # type: ignore
        ]
    )
    return response.output_text
