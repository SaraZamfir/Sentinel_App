import os
import zipfile
from datetime import date, timedelta
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt
import matplotlib.pyplot as plt
import rasterio
import numpy as np
import glob
from PIL import Image, ImageEnhance

def process_images(aoi, year, cloud_cover, bands, width, height, download_dir, max_black_percentage):
    # Connect to API
    api = SentinelAPI('alex11micu', '11079c3facI', 'https://scihub.copernicus.eu/dhus')

    # Cauta imagini
    footprint = geojson_to_wkt(read_geojson(aoi))

    def get_product_for_month(year, month, start_day=1):
        while start_day <= 28:
            start_date = date(year, month, start_day)
            end_date = start_date + timedelta(days=1)
            products = api.query(footprint, date=(start_date, end_date), area_relation='Intersects', platformname='Sentinel-2', processinglevel='Level-2A', cloudcoverpercentage=cloud_cover,)
            if len(products) > 0:
                return products
            start_day += 1
        return None

    cont = 0
    # Iterate through months and request one product for each month
    for month in range(1, 13):
        products = get_product_for_month(year, month)
        if not products:
            print(f"No product found for year {year} and month {month}")
            continue
        print(f"{len(products)} products found for year {year} and month {month}")

        # Download and unzip images
        os.makedirs(download_dir, exist_ok=True)
        product_id, product_info = next(iter(products.items()))
        local_path = api.download(product_id, directory_path=download_dir)
        with zipfile.ZipFile(local_path['path'], 'r') as zip_ref:
            zip_ref.extractall(download_dir)
        os.remove(local_path['path'])  # Delete the archive file after extracting it

        # Your existing image processing code goes here
        # ...
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
                imgdir = f'images'
                os.makedirs(imgdir, exist_ok=True)
                image_path = f'{imgdir}/result{cont}.png'
                plt.imsave(image_path, stack)
                adjust_image(image_path, brightness=1.6, saturation=1.6, contrast=1.6)
                cont += 1

    print("Done")

# Functie pentru a genera un gif din imaginile salvate (not tested)
def generate_gif(directory):
    images = []
    for filename in os.listdir(directory):
        if filename.endswith('.png'):
            filepath = os.path.join(directory, filename)
            img = Image.open(filepath)
            images.append(img)

    output_file = os.path.join(directory, 'output.gif')
    images[0].save(output_file, format='GIF', append_images=images[1:], save_all=True, duration=5000, loop=0)

aoi = './campina_aoi.geojson'
year = 2023
cloud_cover = (0, 30)
bands = ['B04', 'B03', 'B02']
width = 512
height = 512
download_dir = 'sentinel_downloads'
max_black_percentage = 25

process_images(aoi, year, cloud_cover, bands, width, height, download_dir, max_black_percentage)