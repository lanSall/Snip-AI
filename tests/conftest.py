from pathlib import Path

import pytest
from PIL import Image

from snipai.capture import prepare_png


@pytest.fixture
def tiny_png(tmp_path: Path) -> bytes:
    image = Image.new("RGB", (64, 40), color=(32, 64, 128))
    return prepare_png(image, max_width=1600)


@pytest.fixture
def math_problem_png(tmp_path: Path) -> Path:
    from PIL import ImageDraw, ImageFont

    image = Image.new("RGB", (640, 240), color=(248, 250, 252))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 36)
        small = ImageFont.truetype("DejaVuSans.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
        small = font
    draw.text((32, 40), "Solve:", fill=(15, 23, 42), font=small)
    draw.text((32, 90), "17 × 24 = ?", fill=(15, 23, 42), font=font)
    path = tmp_path / "math.png"
    image.save(path, format="PNG")
    return path
