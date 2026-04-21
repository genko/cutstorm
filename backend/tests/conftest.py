import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_VIDEO = FIXTURES_DIR / "sample_5s.mp4"

_TMP_ROOT = Path(tempfile.mkdtemp(prefix="cutstorm-test-"))
os.environ.setdefault("UPLOADS_DIR", str(_TMP_ROOT / "uploads"))
os.environ.setdefault("OUTPUTS_DIR", str(_TMP_ROOT / "outputs"))
os.environ.setdefault("MODELS_DIR", str(_TMP_ROOT / "models"))


def _generate_sample() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    if SAMPLE_VIDEO.exists():
        return
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi", "-i", "testsrc=duration=5:size=320x240:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-c:a", "aac", "-shortest",
        str(SAMPLE_VIDEO),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


@pytest.fixture(scope="session")
def sample_video() -> Path:
    _generate_sample()
    return SAMPLE_VIDEO


