import asyncio
import aiohttp
import rasterio
from rasterio.windows import Window
from rasterio.transform import from_bounds
import imageio
import math
from tqdm import tqdm


def latlon_to_rowcol(lat, lon, z):
    tile_size = 256  # TMS tile size in pixels
    n = 2.0 ** z
    x = (lon + 180.0) / 360.0 * n * tile_size
    y = (1.0 - (math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi)) / 2.0 * n * tile_size
    col = int(x / tile_size)
    row = int(y / tile_size)

    return row, col


def rowcol_to_latlon(row, col, z):
    tile_size = 256  # TMS tile size in pixels
    n = 2.0 ** z
    lon = col / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * row / n)))
    lat = math.degrees(lat_rad)

    return lat, lon


# Function to fetch a tile and return it with its affine transform
async def fetch_tile(TILE_URL_TEMPLATE, z, x, y, session, return_transform=False):
    try:
        url = TILE_URL_TEMPLATE.format(z=z, x=x, y=y)
        async with session.get(url) as response:
            response.raise_for_status()
            image = await response.read()
            img_data = imageio.v2.imread(image)
            img_data = img_data.transpose((-1, 0, 1))[0:3]  # Adjust to RGB

            if return_transform:
                _, height, width = img_data.shape
                (south, west), (north, east) = rowcol_to_latlon(y, x, z), rowcol_to_latlon(y + 1, x + 1, z)
                transform = from_bounds(west=west, south=south, east=east, north=north, width=width, height=height)
                return img_data, transform
            else:
                return img_data, None
    except Exception as e:
        print(f"\nError fetching tile {x}, {y}: {e}")
        return None, None


# Function to write fetched tiles into a target output raster
def write_tile_to_raster(output, tile_data, window):
    output.write(tile_data, window=window)


# Function to create the output raster dataset
def create_output_raster(file_name, width, height, transform, crs="+proj=longlat +datum=WGS84 +no_defs +type=crs"):
    profile = {
        'driver': 'GTiff',
        'dtype': 'uint8',
        'count': 3,
        'width': width,
        'height': height,
        'crs': crs,
        'compress': 'LZW',
        'transform': transform
    }
    return rasterio.open(file_name, 'w', **profile)


# Main function to fetch and merge tiles using rasterio window writing
async def fetch_and_merge_tiles(TILE_URL_TEMPLATE, z, x_range, y_range, n_tasks, output_file):
    tile_size = 256  # Tile size in pixels

    # Calculate full width and height of raster
    full_width = (x_range[1] - x_range[0]) * tile_size
    full_height = (y_range[1] - y_range[0]) * tile_size

    # Build geotransform matrix
    (north, west), (south, east) = rowcol_to_latlon(y_range[0], x_range[0], z), rowcol_to_latlon(y_range[1], x_range[1], z)
    transform = from_bounds(west=west, south=south,  east=east, north=north, width=full_width, height = full_height)
    
    # init progressbar 
    progress_bar = tqdm(total=(x_range[1] - x_range[0]) * (y_range[1] - y_range[0]), desc ='Downloading..')
    
    # request api
    async with aiohttp.ClientSession() as session:
        # Open the output raster for writing
        with create_output_raster(output_file, full_width, full_height, transform) as output_raster:
            batch_tasks = []
            tasks = ((asyncio.ensure_future(fetch_tile(TILE_URL_TEMPLATE, z, x, y, session)), x, y) for x in range(x_range[0], x_range[1]) for y in range(y_range[0], y_range[1]))
            
            for task, x, y in tasks:
                batch_tasks.append((task, x, y))

                if len(batch_tasks) >= n_tasks or ((x == x_range[-1] -1) and (y == y_range[-1] -1)):
                    
                    # Process completed tasks and write tiles to the output raster
                    for task, lx, ly in batch_tasks:
                        tile_data, _ = await task
                        if tile_data is not None:
                            col_offset = (lx - x_range[0]) * tile_size
                            row_offset = (ly - y_range[0]) * tile_size
                            window = Window(col_offset, row_offset, tile_size, tile_size)
                            write_tile_to_raster(output_raster, tile_data, window)
                        
                        # update progress
                        progress_bar.update()

                    # reset task array
                    batch_tasks = [] 
