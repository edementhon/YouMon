"""Grid layout and PDF export for printing cards."""
from __future__ import annotations

import io
import math
from PIL import Image
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.utils import ImageReader

# Physical card size in inches (standard trading card)
CARD_W_IN = 2.5
CARD_H_IN = 3.5

PAPER_SIZES = {
    "letter": (8.5, 11.0),
    "a4": (8.27, 11.69),
}

# Points per inch
PPI = 72

# Horizontal offset to compensate for printer alignment (3mm ≈ 0.118 inches)
H_OFFSET_IN = 3.0 / 25.4  # 3mm in inches


def _compute_grid(paper_size: str, cols: int, rows: int):
    """Compute card positions with even margins, centered on the page."""
    pw, ph = PAPER_SIZES[paper_size]

    total_card_w = cols * CARD_W_IN
    total_card_h = rows * CARD_H_IN

    # Even spacing: distribute remaining space as margins + gaps
    h_margin = (pw - total_card_w) / 2
    v_margin = (ph - total_card_h) / 2

    positions = []
    for r in range(rows):
        for c in range(cols):
            x = h_margin + c * CARD_W_IN
            y = v_margin + r * CARD_H_IN
            positions.append((x, y))

    return positions, pw, ph


def _draw_crop_marks(c, x_pt, y_pt, w_pt, h_pt):
    """Draw small crop marks at the corners of a card position."""
    mark_len = 8  # points
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.setLineWidth(0.25)

    corners = [
        (x_pt, y_pt),                    # top-left
        (x_pt + w_pt, y_pt),             # top-right
        (x_pt, y_pt + h_pt),             # bottom-left
        (x_pt + w_pt, y_pt + h_pt),      # bottom-right
    ]
    for cx, cy in corners:
        # horizontal mark
        dx = -mark_len if cx == x_pt + w_pt else mark_len
        c.line(cx - (0 if dx > 0 else mark_len), cy, cx + (mark_len if dx > 0 else 0), cy)
        # vertical mark
        dy = -mark_len if cy == y_pt + h_pt else mark_len
        c.line(cx, cy - (0 if dy > 0 else mark_len), cx, cy + (mark_len if dy > 0 else 0))


def _pil_to_reader(img: Image.Image) -> ImageReader:
    """Convert a PIL Image to a ReportLab ImageReader."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def export_pdf(
    images: list[Image.Image],
    paper_size: str,
    cols: int,
    rows: int,
    output_path: str,
    back_images: list[Image.Image] | None = None,
    mirror_for_duplex: bool = True,
):
    """
    Export card images to a PDF.

    If back_images is provided, fronts and backs alternate on separate pages.
    When mirror_for_duplex is True, back columns are mirrored so they align
    when the paper is flipped on its long edge.
    """
    positions, pw, ph = _compute_grid(paper_size, cols, rows)
    cards_per_page = cols * rows
    pw_pt = pw * PPI
    ph_pt = ph * PPI
    card_w_pt = CARD_W_IN * PPI
    card_h_pt = CARD_H_IN * PPI

    c = pdf_canvas.Canvas(output_path, pagesize=(pw_pt, ph_pt))

    total_pages = math.ceil(len(images) / cards_per_page)

    for page_idx in range(total_pages):
        start = page_idx * cards_per_page
        page_images = images[start:start + cards_per_page]

        # --- Fronts page ---
        for i, img in enumerate(page_images):
            if i >= len(positions):
                break
            x_in, y_in = positions[i]
            # ReportLab origin is bottom-left; flip y
            x_pt = x_in * PPI
            y_pt = ph_pt - (y_in + CARD_H_IN) * PPI

            reader = _pil_to_reader(img)
            draw_x = x_pt + H_OFFSET_IN * PPI
            c.drawImage(reader, draw_x, y_pt, width=card_w_pt, height=card_h_pt)
            _draw_crop_marks(c, draw_x, y_pt, card_w_pt, card_h_pt)

        c.showPage()

        # --- Backs page (if provided) ---
        if back_images:
            page_backs = back_images[start:start + cards_per_page]
            for i, img in enumerate(page_backs):
                if i >= len(positions):
                    break

                x_in, y_in = positions[i]

                if mirror_for_duplex:
                    # Mirror column position for duplex alignment
                    col = i % cols
                    row = i // cols
                    mirrored_col = (cols - 1) - col
                    mirrored_idx = row * cols + mirrored_col
                    if mirrored_idx < len(positions):
                        x_in, y_in = positions[mirrored_idx]

                x_pt = x_in * PPI
                y_pt = ph_pt - (y_in + CARD_H_IN) * PPI

                reader = _pil_to_reader(img)
                draw_x = x_pt + H_OFFSET_IN * PPI
                c.drawImage(reader, draw_x, y_pt, width=card_w_pt, height=card_h_pt)
                _draw_crop_marks(c, draw_x, y_pt, card_w_pt, card_h_pt)

            c.showPage()

    c.save()
