from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve


BASE_URL = "https://download.osgeo.org/geotiff/samples/usgs"

PUBLIC_DEM_SAMPLES = {
    "usgs_o41078a5": "o41078a5.tif",
    "usgs_o41078a1": "o41078a1.tif",
    "usgs_o41078a2": "o41078a2.tif",
    "usgs_o41078a3": "o41078a3.tif",
    "usgs_o41078a4": "o41078a4.tif",
    "usgs_o41078a6": "o41078a6.tif",
    "usgs_o41078a7": "o41078a7.tif",
    "usgs_i30dem": "i30dem.tif",
}

DEFAULT_SAMPLE = "usgs_o41078a5"


def sample_names() -> tuple[str, ...]:
    return tuple(PUBLIC_DEM_SAMPLES)


def ensure_public_dem(target_dir: str | Path, sample: str = DEFAULT_SAMPLE) -> Path:
    if sample not in PUBLIC_DEM_SAMPLES:
        available = ", ".join(sample_names())
        raise ValueError(f"unknown public DEM sample {sample!r}; available: {available}")
    filename = PUBLIC_DEM_SAMPLES[sample]
    target = Path(target_dir) / filename
    if target.exists() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(f"{BASE_URL}/{filename}", target)
    return target


def ensure_public_dems(target_dir: str | Path) -> list[Path]:
    return [ensure_public_dem(target_dir, sample) for sample in sample_names()]
