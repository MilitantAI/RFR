# Topographic Maps

A standalone heightmap pathing demo for topographic terrain: elevation, slope cost, blocked terrain, contours, and side-by-side process simulation for multiple pathing strategies.

The demo downloads/caches unique public USGS DEM raster samples by default, or loads a supplied greyscale DEM/heightmap with Pillow. It converts elevation into terrain layers, then records the actual search process for terrain Dijkstra and terrain RFR so they can be compared while they run.

## Run

From the repository root:

```powershell
cd TopographicMaps
```

Or from `TopographicMaps/`:

```powershell
python -m pip install -e .
topographic-route --all-samples --output outputs
```

Or run the module directly:

```powershell
python -m topographic_maps.demo --sample usgs_o41078a5 --output outputs
```

The demo writes:

- `outputs/latest_metrics.json`
- `outputs/latest_report.md`
- `outputs/latest_visualisation.html`

Open `outputs/latest_visualisation.html` in a browser to choose between the public DEM samples and watch the comparative simulator: Dijkstra and RFR run on the same terrain with their own settled cells, current frontier, relaxed neighbours, target discovery, and final route reconstruction only after that algorithm reaches the target.

## Test

```powershell
python -m unittest discover -s tests
```
