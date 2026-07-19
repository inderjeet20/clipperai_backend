import os
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
FONTS_DIR = DATA_DIR / "fonts"
FONTS_DIR.mkdir(parents=True, exist_ok=True)

fonts = {
    "Inter": "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
    "Geist": "https://github.com/google/fonts/raw/main/ofl/geist/Geist%5Bwght%5D.ttf",
    "Poppins": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf",
    "Sora": "https://github.com/google/fonts/raw/main/ofl/sora/Sora%5Bwght%5D.ttf",
    "Space Grotesk": "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf",
    "Playfair Display": "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
    "Montserrat": "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    "Bebas Neue": "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf"
}

for name, url in fonts.items():
    safe_name = name.replace(" ", "")
    dest = FONTS_DIR / f"{safe_name}.ttf"
    if not dest.exists():
        print(f"Downloading {name}...")
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"Downloaded {name} to {dest}")
        except Exception as e:
            print(f"Failed to download {name}: {e}")
    else:
        print(f"{name} already exists.")
