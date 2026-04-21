from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.canvas import hex_to_ffmpeg_color, resolve
from app.models import Canvas, CustomCrop


# ---------- preset mode ----------

def test_preset_source_preserves_dims() -> None:
    r = resolve(Canvas(preset="source"), 1280, 720)
    assert (r.target_w, r.target_h) == (1280, 720)
    assert r.ffmpeg_filter == ""


def test_preset_source_audio_only_falls_back_9_16() -> None:
    r = resolve(Canvas(preset="source"), 0, 0)
    assert (r.target_w, r.target_h) == (1080, 1920)


def test_preset_audio_only_uses_preset() -> None:
    r = resolve(Canvas(preset="16:9"), 0, 0)
    assert (r.target_w, r.target_h) == (1920, 1080)
    assert r.ffmpeg_filter == ""


def test_preset_all_aspects_audio_only() -> None:
    for p, wh in [("9:16", (1080, 1920)), ("16:9", (1920, 1080)), ("1:1", (1080, 1080)), ("4:5", (1080, 1350))]:
        r = resolve(Canvas(preset=p), 0, 0)
        assert (r.target_w, r.target_h) == wh


def test_preset_horizontal_crop_center_from_1920x1080_to_9_16() -> None:
    r = resolve(Canvas(preset="9:16", crop_anchor="center"), 1920, 1080)
    assert (r.target_w, r.target_h) == (1080, 1920)
    # crop_w = 1080 * 9/16 = 608 (rounded to even)
    # crop_x = (1920-608)/2 = 656
    assert "crop=608:1080:656:0" in r.ffmpeg_filter
    assert "scale=1080:1920" in r.ffmpeg_filter


def test_preset_horizontal_crop_left() -> None:
    r = resolve(Canvas(preset="9:16", crop_anchor="left"), 1920, 1080)
    assert "crop=608:1080:0:0" in r.ffmpeg_filter


def test_preset_horizontal_crop_right() -> None:
    r = resolve(Canvas(preset="9:16", crop_anchor="right"), 1920, 1080)
    # crop_x = 1920 - 608 = 1312
    assert "crop=608:1080:1312:0" in r.ffmpeg_filter


def test_preset_pad_when_source_narrower_than_target() -> None:
    r = resolve(Canvas(preset="16:9", crop_anchor="center", bg_color="#123456"), 720, 1280)
    assert (r.target_w, r.target_h) == (1920, 1080)
    # Source 720×1280 → scaled to match target_h=1080: scale_w = 720*1080/1280 = 608, scale_h=1080
    # Then pad to 1920×1080: pad_left = (1920-608)/2 = 656
    assert "scale=608:1080" in r.ffmpeg_filter
    assert "pad=1920:1080:656:0:0x123456" in r.ffmpeg_filter
    assert "crop=" not in r.ffmpeg_filter


def test_preset_1_1_from_square_source_no_op() -> None:
    r = resolve(Canvas(preset="1:1"), 1080, 1080)
    assert r.ffmpeg_filter == ""
    assert (r.target_w, r.target_h) == (1080, 1080)


def test_preset_4_5_on_horizontal_uses_crop() -> None:
    r = resolve(Canvas(preset="4:5", crop_anchor="center"), 1920, 1080)
    # 4:5 aspect is 0.8. Source 1920×1080 ratio 1.78 >> 0.8. Horizontal crop.
    # crop_w = 1080 * 4/5 = 864, crop_x = (1920-864)/2 = 528
    assert "crop=864:1080:528:0" in r.ffmpeg_filter
    assert "scale=1080:1350" in r.ffmpeg_filter


# ---------- custom mode ----------

def test_custom_full_frame_is_noop() -> None:
    r = resolve(
        Canvas(mode="custom", custom=CustomCrop(x_pct=0, y_pct=0, w_pct=100, h_pct=100)),
        1920, 1080,
    )
    assert r.ffmpeg_filter == ""
    assert (r.target_w, r.target_h) == (1920, 1080)


def test_custom_half_width_vertical_strip() -> None:
    r = resolve(
        Canvas(mode="custom", custom=CustomCrop(x_pct=25, y_pct=0, w_pct=50, h_pct=100)),
        1920, 1080,
    )
    assert r.ffmpeg_filter == "crop=960:1080:480:0"
    assert (r.target_w, r.target_h) == (960, 1080)


def test_custom_upper_half() -> None:
    r = resolve(
        Canvas(mode="custom", custom=CustomCrop(x_pct=0, y_pct=0, w_pct=100, h_pct=50)),
        1920, 1080,
    )
    assert r.ffmpeg_filter == "crop=1920:540:0:0"
    assert (r.target_w, r.target_h) == (1920, 540)


def test_custom_offset_small_box() -> None:
    r = resolve(
        Canvas(mode="custom", custom=CustomCrop(x_pct=10, y_pct=20, w_pct=15, h_pct=30)),
        1920, 1080,
    )
    # cw=288, ch=324, cx=192, cy=216
    assert r.ffmpeg_filter == "crop=288:324:192:216"
    assert (r.target_w, r.target_h) == (288, 324)


def test_custom_dims_always_even() -> None:
    # 33% on 1001 px source — rounding must produce even.
    r = resolve(
        Canvas(mode="custom", custom=CustomCrop(x_pct=0, y_pct=0, w_pct=33, h_pct=33)),
        1001, 999,
    )
    assert r.target_w % 2 == 0
    assert r.target_h % 2 == 0


def test_custom_audio_only_falls_back_to_preset_target() -> None:
    # No source → custom can't be honoured; resolver returns something usable.
    r = resolve(Canvas(mode="custom"), 0, 0)
    assert r.target_w > 0 and r.target_h > 0


# ---------- pydantic validator ----------

def test_custom_crop_out_of_bounds_rejected_x_plus_w() -> None:
    with pytest.raises(ValidationError):
        CustomCrop(x_pct=80, y_pct=0, w_pct=30, h_pct=100)


def test_custom_crop_out_of_bounds_rejected_y_plus_h() -> None:
    with pytest.raises(ValidationError):
        CustomCrop(x_pct=0, y_pct=50, w_pct=100, h_pct=60)


def test_custom_crop_min_w_h_enforced() -> None:
    with pytest.raises(ValidationError):
        CustomCrop(x_pct=0, y_pct=0, w_pct=0.5, h_pct=50)


# ---------- helpers ----------

def test_hex_to_ffmpeg_color() -> None:
    assert hex_to_ffmpeg_color("#00B140") == "0x00B140"
    assert hex_to_ffmpeg_color("00b140") == "0x00B140"
    assert hex_to_ffmpeg_color("#fff") == "0xFFFFFF"
