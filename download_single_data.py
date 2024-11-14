import time
from downloader_async import *


start_time = time.time()

# PARAMETERS
zoom_level = 16
n_tasks = 100

# Define the base URL for the tiles
TILE_URL_TEMPLATE = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"

# EXTENT
extent = (86.58625005238095, 26.37634325, 86.824588323, 26.48126687208723)

# CALCULATE ROW COL RANGE
row1, col1 = latlon_to_rowcol(*extent[:2][::-1], zoom_level)
row2, col2 = latlon_to_rowcol(*extent[2:][::-1], zoom_level)

col1, col2 = (col1, col2 +1) if col1 == col2 else (col1, col2)
row1, row2 = (row1, row2 +1) if row1 == row2 else (row1, row2)
x_range = (col1, col2) if col1 < col2 else (col2, col1) 
y_range = (row1, row2) if row1 < row2 else (row2, row1) 

# EXPORT 
output_file = f'map_{x_range}_{y_range}_{zoom_level}.tif'
asyncio.run(fetch_and_merge_tiles(TILE_URL_TEMPLATE, zoom_level ,x_range, y_range, n_tasks ,output_file))
print(f"Elapsed time: {time.time() - start_time} seconds")