from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


Point = tuple[int, int]
FloatLayer = list[list[float]]
BoolLayer = list[list[bool]]


@dataclass(frozen=True, slots=True)
class Heightmap:
    path: Path
    width: int
    height: int
    elevation: FloatLayer
    resistance: FloatLayer
    mask: BoolLayer
    blocked_cells: int
    min_elevation: float
    max_elevation: float

    @property
    def cell_count(self) -> int:
        return self.width * self.height


def load_heightmap(
    path: str | Path,
    *,
    elevation_scale: float = 12.0,
    roughness_weight: float = 1.8,
    block_below: float | None = None,
    block_above: float | None = None,
    max_size: int | None = 96,
) -> Heightmap:
    image_path = Path(path)
    if elevation_scale <= 0:
        raise ValueError("elevation_scale must be positive")
    if roughness_weight < 0:
        raise ValueError("roughness_weight must be non-negative")

    image = Image.open(image_path).convert("L")
    if max_size is not None:
        if max_size < 2:
            raise ValueError("max_size must be at least 2")
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    width, height = image.size
    if width < 2 or height < 2:
        raise ValueError("heightmap must be at least 2x2")

    pixels = list(image.getdata())
    normalised = [pixel / 255.0 for pixel in pixels]
    elevation = [
        [normalised[y * width + x] * elevation_scale for x in range(width)]
        for y in range(height)
    ]
    mask = _derive_mask(normalised, width, height, block_below, block_above)
    resistance = _derive_resistance(elevation, mask, roughness_weight)
    flat_elevation = [value for row in elevation for value in row]

    return Heightmap(
        path=image_path,
        width=width,
        height=height,
        elevation=elevation,
        resistance=resistance,
        mask=mask,
        blocked_cells=sum(1 for row in mask for blocked in row if blocked),
        min_elevation=min(flat_elevation),
        max_elevation=max(flat_elevation),
    )


def parse_point(value: str) -> Point:
    try:
        x_text, y_text = value.split(",", maxsplit=1)
        point = (int(x_text), int(y_text))
    except ValueError as exc:
        raise ValueError(f"point must be formatted as x,y: {value!r}") from exc
    return point


def validate_point(point: Point, heightmap: Heightmap, label: str) -> None:
    x, y = point
    if not (0 <= x < heightmap.width and 0 <= y < heightmap.height):
        raise ValueError(f"{label} point {point!r} is outside the heightmap")
    if heightmap.mask[y][x]:
        raise ValueError(f"{label} point {point!r} is blocked")


def _derive_mask(
    normalised: list[float],
    width: int,
    height: int,
    block_below: float | None,
    block_above: float | None,
) -> BoolLayer:
    mask: BoolLayer = []
    for y in range(height):
        row: list[bool] = []
        for x in range(width):
            value = normalised[y * width + x]
            blocked = False
            if block_below is not None and value < block_below:
                blocked = True
            if block_above is not None and value > block_above:
                blocked = True
            row.append(blocked)
        mask.append(row)
    return mask


def _derive_resistance(
    elevation: FloatLayer,
    mask: BoolLayer,
    roughness_weight: float,
) -> FloatLayer:
    height = len(elevation)
    width = len(elevation[0])
    resistance: FloatLayer = []
    for y in range(height):
        row: list[float] = []
        for x in range(width):
            if mask[y][x]:
                row.append(0.0)
                continue
            centre = elevation[y][x]
            neighbours = []
            if x > 0:
                neighbours.append(elevation[y][x - 1])
            if x + 1 < width:
                neighbours.append(elevation[y][x + 1])
            if y > 0:
                neighbours.append(elevation[y - 1][x])
            if y + 1 < height:
                neighbours.append(elevation[y + 1][x])
            roughness = max((abs(centre - neighbour) for neighbour in neighbours), default=0.0)
            row.append(roughness * roughness_weight)
        resistance.append(row)
    return resistance
