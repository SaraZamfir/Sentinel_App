import tkinter as tk
from tkinter import ttk
import geopy.distance
from tkintermapview import TkinterMapView
import geojson
import os
import zipfile
from datetime import date, timedelta
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt
import matplotlib.pyplot as plt
import rasterio
import numpy as np
import glob
from PIL import Image, ImageEnhance

clicked_coordinates = (0.0, 0.0)
topleft_coordinates = (0.0, 0.0)
topright_coordinates = (0.0, 0.0)
bottomleft_coordinates = (0.0, 0.0)
bottomright_coordinates = (0.0, 0.0)
cloud_coverage = (0, 0)
black_coverage = 0
filepath = './out.geojson'
downloaddir = 'sentinel_downloads'
current_year = 0
bands = ['B04', 'B03', 'B02']


def on_click(coordinates_tuple, map_widget, latitude_label, longitude_label):
    global clicked_coordinates
    lat, lng = coordinates_tuple
    lat, lng = round(lat, 6), round(lng, 6)
    calculate_square_corners(lat, lng)
    clicked_coordinates = (lat, lng)

    if hasattr(on_click, "marker"):
        marker = on_click.marker
        marker.set_position(lat, lng)
    else:
        marker = map_widget.set_marker(lat, lng)
        on_click.marker = marker

    latitude_label.config(text=f"Clicked point latitude: {lat}")
    longitude_label.config(text=f"Clicked point longitude: {lng}")



def calculate_square_corners(lat, lng):
    global topleft_coordinates, topright_coordinates, bottomleft_coordinates, bottomright_coordinates
    center = (lat, lng)
    side_length = 5
    diagonal_distance = (2 * side_length ** 2) ** 0.5

    top_left = geopy.distance.great_circle(kilometers=diagonal_distance).destination(center, 45)
    top_right = geopy.distance.great_circle(kilometers=diagonal_distance).destination(center, 315)
    bottom_left = geopy.distance.great_circle(kilometers=diagonal_distance).destination(center, 135)
    bottom_right = geopy.distance.great_circle(kilometers=diagonal_distance).destination(center, 225)

    tl_lat, tl_lng = round(top_left.latitude, 6), round(top_left.longitude, 6)
    tr_lat, tr_lng = round(top_right.latitude, 6), round(top_right.longitude, 6)
    bl_lat, bl_lng = round(bottom_left.latitude, 6), round(bottom_left.longitude, 6)
    br_lat, br_lng = round(bottom_right.latitude, 6), round(bottom_right.longitude, 6)

    topleft_coordinates = (tl_lat, tl_lng)
    topright_coordinates = (tr_lat, tr_lng)
    bottomleft_coordinates = (bl_lat, bl_lng)
    bottomright_coordinates = (br_lat, br_lng)



def create_geojson(top_left, top_right, bottom_left, bottom_right):
    coordinates = [
        top_left,
        top_right,
        bottom_right,
        bottom_left,
        top_left
    ]

    properties = {
        "name": "Selected Area",
    }

    polygon = geojson.Polygon([coordinates])
    feature = geojson.Feature(properties=properties, geometry=polygon)
    feature_collection = geojson.FeatureCollection([feature])

    with open("out.geojson", "w+") as f:
        dump_kwargs = {
            "indent": 2,
            "separators": (",", ": ")
        }
        geojson.dump(feature_collection, f, **dump_kwargs)



def confirm_button_pressed():
    global topleft_coordinates, topright_coordinates, bottomleft_coordinates, bottomright_coordinates
    global filepath, current_year, cloud_coverage, bands, downloaddir, black_coverage
    create_geojson(topleft_coordinates, topright_coordinates, bottomleft_coordinates, bottomright_coordinates)

    process_images(filepath, current_year, cloud_coverage, bands, 512, 512, downloaddir, black_coverage)



def update_cloud_label(value, cloud_percentage):
    global cloud_coverage
    cloud_percentage.set("{:.0f}".format(float(value)))
    cloud_coverage = (0, round(float(value)))



def update_black_label(value, black_percentage):
    global black_coverage
    black_percentage.set("{:.0f}".format(float(value)))
    black_coverage = round(float(value))



def update_year(year_entry):
    global current_year
    current_year = round(float(year_entry.get()))



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



def main():
    root = tk.Tk()
    root.title("Interactive World Map")
    root.attributes('-fullscreen', True)

    main_frame = ttk.Frame(root, padding="10")
    main_frame.grid(column=0, row=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding="30")
    filter_frame.grid(column=0, row=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    map_widget = TkinterMapView(main_frame, width=1220, height=850)
    map_widget.grid(column=1, row=0)
    map_widget.set_tile_server("https://mt0.google.com/vt/lrys=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
    map_widget.set_zoom(7)
    map_widget.add_left_click_map_command(lambda coords: on_click(coords, map_widget, latitude_label, longitude_label))

    latitude_label = ttk.Label(filter_frame, text="Clicked point latitude: ")
    latitude_label.grid(column=0, row=3, padx=5, pady=5, sticky=tk.W)

    longitude_label = ttk.Label(filter_frame, text="Clicked point longitude: ")
    longitude_label.grid(column=0, row=4, padx=5, pady=5, sticky=tk.W)

    year_label = ttk.Label(filter_frame, text="Year:")
    year_label.grid(column=0, row=5, padx=5, pady=5, sticky=tk.W)
    year_entry = ttk.Entry(filter_frame)
    year_entry.grid(column=0, row=5, padx=15, pady=5)
    year_entry.bind("<KeyRelease>", lambda event: update_year(year_entry))

    cloud_frame = ttk.Frame(filter_frame)
    cloud_frame.grid(column=0, row=6, padx=5, pady=5, sticky=tk.W)
    cloud_label = ttk.Label(cloud_frame, text="Cloud coverage: ")
    cloud_label.pack(side=tk.LEFT, padx=5, pady=5)
    cloud_value = tk.DoubleVar()
    cloud_slider = ttk.Scale(cloud_frame, from_=0, to=100, variable=cloud_value, command=lambda val: update_cloud_label(val, cloud_percentage))
    cloud_slider.pack(side=tk.LEFT, padx=5, pady=5)
    cloud_percentage = tk.StringVar(value="0")
    cloud_percentage_label = ttk.Label(cloud_frame, textvariable=cloud_percentage)
    cloud_percentage_label.pack(side=tk.LEFT, padx=5, pady=5)

    black_frame = ttk.Frame(filter_frame)
    black_frame.grid(column=0, row=7, padx=5, pady=5, sticky=tk.W)
    black_label = ttk.Label(black_frame, text="Black percentage: ")
    black_label.pack(side=tk.LEFT, padx=5, pady=5)
    black_value = tk.DoubleVar()
    black_slider = ttk.Scale(black_frame, from_=0, to=100, variable=black_value, command=lambda val: update_black_label(val, black_percentage))
    black_slider.pack(side=tk.LEFT, padx=5, pady=5)
    black_percentage = tk.StringVar(value="0")
    black_percentage_label = ttk.Label(black_frame, textvariable=black_percentage)
    black_percentage_label.pack(side=tk.LEFT, padx=5, pady=5)

    enter_button = ttk.Button(filter_frame, text="Confirm", command=confirm_button_pressed)
    enter_button.grid(column=0, row=8, padx=5, pady=5, sticky=tk.W)

    root.mainloop()

if __name__ == "__main__":
    main()