import os
import zipfile
from datetime import date
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt
import matplotlib.pyplot as plt
import rasterio
import numpy as np
import glob
from PIL import Image, ImageEnhance

def process_images(aoi, start_date, end_date, cloud_cover, bands, width, height, download_dir, max_black_percentage):
    # Connect to API
    api = SentinelAPI('alex11micu', '11079c3facI', 'https://scihub.copernicus.eu/dhus')

    # Cauta imagini
    footprint = geojson_to_wkt(read_geojson(aoi))
    products = api.query(footprint, date=(start_date, end_date), area_relation='Intersects', platformname='Sentinel-2', processinglevel='Level-2A', cloudcoverpercentage=cloud_cover,)
    print(f"{len(products)} products found")

    # Descarca si dezarhiveaza imaginile
    os.makedirs(download_dir, exist_ok=True)

    for product_id, product_info in products.items():
        local_path = api.download(product_id, directory_path=download_dir)
        with zipfile.ZipFile(local_path['path'], 'r') as zip_ref:
            zip_ref.extractall(download_dir)
        os.remove(local_path['path'])  # Delete the archive file after extracting it

    # Calculeaza procenutul pixelilor negri
    def check_black_percentage(image):
        black_pixels = np.count_nonzero(image == 0)
        total_pixels = image.size
        return (black_pixels / total_pixels) * 100
    
    # Modifica brightness, saturation si contrast
    def adjust_image(image_path, brightness=1.0, saturation=1.0, contrast=1.0):
        image = Image.open(image_path)

        enhancer_brightness = ImageEnhance.Brightness(image)
        image = enhancer_brightness.enhance(brightness)

        enhancer_saturation = ImageEnhance.Color(image)
        image = enhancer_saturation.enhance(saturation)

        enhancer_contrast = ImageEnhance.Contrast(image)
        image = enhancer_contrast.enhance(contrast)

        image.save(image_path)

    # Itereaza prin fiecare produs si extrage banda selectata
    cont = 0
    for product in products.items():
        stack = np.empty((0, 0, len(bands)), dtype=np.float32)
        stack = None
        for i, band in enumerate(bands):
            file_paths = glob.glob(f'{download_dir}/{product[1]["title"]}.SAFE/GRANULE/*/IMG_DATA/R10m/*_{band}_10m.jp2')
            if len(file_paths) == 0:
                print(f"No file found for product {product[1]['title']} and band {band}")
                continue
            filepath = file_paths[0]
            with rasterio.open(filepath) as src:
                data = src.read(1).astype(np.float32)
                if check_black_percentage(data) < max_black_percentage:
                    if i == 0:
                        stack = np.empty((src.height, src.width, len(bands)), dtype=np.float32)
                    stack[..., i] = data
                else:
                    break

        if stack is not None:
            # Normalizare
            Imin, Imax = np.min(stack), np.max(stack)
            stack = (stack - Imin) / (Imax - Imin)

            # Clip de la 0 la 1 pentru a evita overflow
            stack = np.clip(stack, 0, 1)

            # Save image
            image_path = f'result{cont}.png'
            plt.imsave(image_path, stack)
            adjust_image(image_path, brightness=1.6, saturation=1.6, contrast=1.6)
            cont += 1

    print("Done")

# Usage
aoi = './campina_aoi.geojson'
start_date = date(2023, 1, 1)
end_date = date(2023, 1, 5)
cloud_cover = (0, 20)
bands = ['B04', 'B03', 'B02']
width = 512
height = 512
download_dir = 'sentinel_downloads'
max_black_percentage = 25

process_images(aoi, start_date, end_date, cloud_cover, bands, width, height, download_dir, max_black_percentage)