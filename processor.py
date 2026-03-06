import os
import sys
import cv2
import numpy as np
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import black, white, Color
from reportlab.lib.utils import ImageReader


# Metric Measurements
SCALE_HEIGHT_MM = 32.0  # Target height of the tallest miniature
FLAP_HEIGHT_MM = 3.0
SPACING_MM = 5.0
BORDER_WIDTH_MM = 0.15
DILATION_PIXELS = 7
THRESHOLD_WHITE = 230
BLUR_SIZE_MM = 25

# ReportLab uses points (1 point = 1/72 inch). reportlab.lib.units.mm handles the conversion.
PAGE_WIDTH, PAGE_HEIGHT = A4
GREY_COLOUR = Color(0.7, 0.7, 0.7)


def process_image(filepath: str, dilation_pixels=DILATION_PIXELS) -> Image.Image | None:
    # Load image with alpha channel
    img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None

    # Ensure 4 channels (BGRA)
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

    h, w = img.shape[:2]
    # Flood mask must be 2 pixels larger than the image
    flood_mask = np.zeros((h + 2, w + 2), np.uint8)
    temp_img = img[:, :, :3].copy()

    # --- MULTI-SEED BORDER PROBE ---
    # We check every pixel on the border. If it's "white-ish", we click it.
    # This eats all background pockets but cannot enter the character's
    # silhouette to nuke the shield.
    edge_threshold = 245
    tolerance = (10, 10, 10)  # Handles slight compression noise in the white

    # Check top/bottom edges
    for x in range(w):
        for y in [0, h - 1]:
            if np.all(temp_img[y, x] >= edge_threshold):
                cv2.floodFill(
                    temp_img,
                    flood_mask,
                    (x, y),
                    (255, 255, 255),
                    tolerance,
                    tolerance,
                )

    # Check left/right edges
    for y in range(h):
        for x in [0, w - 1]:
            if np.all(temp_img[y, x] >= edge_threshold):
                cv2.floodFill(
                    temp_img,
                    flood_mask,
                    (x, y),
                    (255, 255, 255),
                    tolerance,
                    tolerance,
                )

    # --- THE MASK FIX ---
    # background_mask is 1 where the background was filled, 0 elsewhere
    background_mask = flood_mask[1:-1, 1:-1]

    # Create a 0/255 mask: 255 for the Figure, 0 for the Background
    # This fixes the "99.6% opaque" bug.
    figure_mask = np.where(background_mask == 1, 0, 255).astype(np.uint8)

    # Create the white halo
    kernel = np.ones((3, 3), np.uint8)
    dilated_mask = cv2.dilate(figure_mask, kernel, iterations=dilation_pixels)
    blurred_mask = cv2.GaussianBlur(dilated_mask, (BLUR_SIZE_MM, BLUR_SIZE_MM), 0)

    # Set the Alpha Channel
    img[:, :, 3] = blurred_mask

    # Crop to content
    coords = cv2.findNonZero(blurred_mask)
    if coords is None:
        return None
    x, y, crop_w, crop_h = cv2.boundingRect(coords)
    cropped = img[y : y + crop_h, x : x + crop_w]

    # Convert to PIL RGBA (ReportLab requires this specific order)
    return Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGRA2RGBA))


def generate_pdf(input_dir: str, output_pdf: str) -> None:
    minis = []
    max_pixel_height = 0

    for root, _, files in os.walk(input_dir):
        front_file = next((f for f in files if "-01-Front.png" in f), None)
        back_file = next((f for f in files if "-02-Back.png" in f), None)

        if front_file and back_file:
            f_img = process_image(os.path.join(root, front_file))
            b_img = process_image(os.path.join(root, back_file))
            if f_img and b_img:
                minis.append({"front": f_img, "back": b_img})
                max_pixel_height = max(max_pixel_height, f_img.height, b_img.height)

    if not minis:
        print("No minis found. Check the INPUT_DIR path.")
        return

    # Mathematical Layout
    px_to_mm = SCALE_HEIGHT_MM / max_pixel_height
    backdrop_h = (SCALE_HEIGHT_MM + SPACING_MM) * mm
    flap_h = FLAP_HEIGHT_MM * mm
    total_assembly_h = (backdrop_h + flap_h) * 2

    c = canvas.Canvas(output_pdf, pagesize=A4)
    curr_x = SPACING_MM * mm
    curr_y = A4[1] - (SPACING_MM * mm) - total_assembly_h

    for mini in minis:
        mini_w = mini["front"].width * px_to_mm * mm
        mini_h = mini["front"].height * px_to_mm * mm
        back_w = mini["back"].width * px_to_mm * mm
        back_h = mini["back"].height * px_to_mm * mm
        box_w = mini_w + (SPACING_MM * mm)

        # Page wrapping logic
        if curr_x + box_w > A4[0] - (SPACING_MM * mm):
            curr_x = SPACING_MM * mm
            curr_y -= total_assembly_h + (SPACING_MM * mm)
            if curr_y < (SPACING_MM * mm):
                c.showPage()
                curr_y = A4[1] - (SPACING_MM * mm) - total_assembly_h

        # Define Y-coordinates for the "stack"
        y_bottom_flap = curr_y
        y_front_box = y_bottom_flap + flap_h
        y_back_box = y_front_box + backdrop_h  # This is the FOLD LINE
        y_top_flap = y_back_box + backdrop_h

        # 1. DRAW BACKDROPS (Front and Back)
        c.setStrokeColor(white)
        c.setLineWidth(BORDER_WIDTH_MM * mm)
        c.setDash([1 * mm, 1 * mm], 0)
        c.setFillColor(black)
        c.rect(curr_x, y_front_box, box_w, backdrop_h, fill=1, stroke=1)
        c.rect(curr_x, y_back_box, box_w, backdrop_h, fill=1, stroke=1)

        # 2. DRAW FLAPS
        c.setFillColor(GREY_COLOUR)
        c.setDash([], 0)
        c.rect(curr_x, y_bottom_flap, box_w, flap_h, fill=1, stroke=1)
        c.rect(curr_x, y_top_flap, box_w, flap_h, fill=1, stroke=1)

        # 3. PLACE MINIATURES (Mirrored at the fold)
        img_x = curr_x + (box_w - mini_w) / 2

        # Front: Anchored to the bottom flap
        c.drawImage(
            ImageReader(mini["front"]),
            img_x,
            y_front_box,
            width=mini_w,
            height=mini_h,
            mask="auto",
        )

        # Back: Anchored to the top flap and rotated 180
        c.saveState()
        c.translate(curr_x + (box_w / 2), y_top_flap)
        c.rotate(180)
        # In this rotated space, (0,0) is the top-middle of the card
        c.drawImage(
            ImageReader(mini["back"]),
            -back_w / 2,
            0,
            width=back_w,
            height=back_h,
            mask="auto",
        )
        c.restoreState()

        curr_x += box_w

    c.save()
    print(f"Success! Generated {output_pdf}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python processor.py <input_folder>")
        sys.exit(1)

    input_folder = sys.argv[1]
    if not os.path.isdir(input_folder):
        print(f"Error: '{input_folder}' is not a valid directory")
        sys.exit(1)

    output_pdf = (
        input_folder
        + "/"
        + os.path.splitext(os.path.basename(input_folder))[0]
        + ".pdf"
    )
    generate_pdf(input_folder, output_pdf)
