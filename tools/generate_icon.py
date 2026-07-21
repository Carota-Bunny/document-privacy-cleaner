# Copyright (C) 2026 Carota-Bunny
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    size = 512
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((18, 18, 494, 494), radius=105, fill="#173f5f")
    draw.rounded_rectangle((34, 34, 478, 478), radius=92, outline="#2f7795", width=10)

    shield = [(256, 88), (389, 137), (376, 288), (348, 362), (256, 430), (164, 362), (136, 288), (123, 137)]
    draw.polygon(shield, fill="#f5fbfd")
    draw.line(shield + [shield[0]], fill="#b7d7e3", width=13, joint="curve")

    draw.line((187, 263, 235, 311), fill="#1d8a61", width=35)
    draw.line((235, 311, 330, 207), fill="#1d8a61", width=35)

    png = image.resize((256, 256), Image.Resampling.LANCZOS)
    png.save(ASSETS / "app_icon.png")
    image.save(
        ASSETS / "app.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Generated {ASSETS / 'app.ico'}")


if __name__ == "__main__":
    main()
