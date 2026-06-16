"""
Kontur-Bild in ASCII-Art umwandeln.

Quelle ist das Kontur-PNG aus konturen.py (weiße Linien auf Schwarz);
nur die Linien werden zu Zeichen, der Rest bleibt Leerraum.

Vorbereitung (einmalig):
    pip install opencv-python numpy

Aufruf:
    python ascii_art.py pfad/zum/konturen.png

Erzeugt ascii.txt (echter Text) und ascii.png (gerendert, weiß auf schwarz).
"""

import sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

LINIENZEICHEN = "█"  # Vollblock für eine Kontur-Linie
FONT_PFAD = "/System/Library/Fonts/Menlo.ttc"  # echte Monospace-Schrift

# Poppige Füllfarben für geschlossene Flächen (RGB)
PALETTE = [
    (255, 59, 48), (255, 149, 0), (255, 204, 0), (52, 199, 89),
    (0, 199, 190), (48, 176, 255), (88, 86, 255), (175, 82, 222),
    (255, 45, 146), (50, 215, 75), (255, 105, 180), (0, 245, 212),
]


def _font_laden(groesse):
    """Font + Block-Zellmaße + Ursprungs-Offset, damit Blöcke nahtlos kacheln."""
    font = ImageFont.truetype(FONT_PFAD, groesse)
    x0, y0, x1, y1 = font.getbbox(LINIENZEICHEN)
    char_w = int(round(font.getlength(LINIENZEICHEN)))
    line_h = y1 - y0
    return font, char_w, line_h, (x0, y0)


def ascii_erzeugen(
    bildpfad,
    txt_pfad="ascii.txt",
    png_pfad="ascii.png",
    breite_zeichen=160,   # Detailgrad: Anzahl Zeichen pro Zeile
    schwelle=20,          # ab welcher Helligkeit eine Zelle als Linie zählt
    schriftgroesse=10,    # Block-Größe in px fürs PNG-Rendering
):
    grau = cv2.imread(bildpfad, cv2.IMREAD_GRAYSCALE)
    if grau is None:
        raise FileNotFoundError(f"Bild nicht gefunden: {bildpfad}")
    h, w = grau.shape

    # Seitenverhältnis aus den echten Block-Maßen ableiten -> kein verzerrtes PNG
    font, char_w, line_h, offset = _font_laden(schriftgroesse)
    zeichen_seitenverhaeltnis = char_w / line_h
    breite = breite_zeichen
    hoehe = max(1, int(breite * (h / w) * zeichen_seitenverhaeltnis))

    # Dünne Linien überleben das Verkleinern nicht -> leicht verdicken
    # (nur so viel, dass sie pro Zelle registriert werden, ohne zu Blobs zu füllen)
    faktor = max(1, w // breite // 3)
    kernel = np.ones((faktor, faktor), np.uint8)
    dick = cv2.dilate(grau, kernel)
    klein = cv2.resize(dick, (breite, hoehe), interpolation=cv2.INTER_AREA)

    linie = klein > schwelle  # bool-Raster: True = Kontur

    # .txt: Linie -> Block, sonst Leerzeichen
    zeilen = ["".join(LINIENZEICHEN if v else " " for v in reihe) for reihe in linie]
    with open(txt_pfad, "w") as f:
        f.write("\n".join(zeilen))

    farbgitter = _flaechen_faerben(linie)
    _als_png_rendern(farbgitter, png_pfad, font, char_w, line_h, offset)
    print(f"{breite}x{hoehe} Zeichen -> {txt_pfad}, {png_pfad}")


def _flaechen_faerben(linie):
    """Farbe pro Zelle: Linie=weiß, geschlossene Fläche=poppige Farbe, sonst schwarz."""
    hoehe, breite = linie.shape
    farbgitter = np.zeros((hoehe, breite, 3), dtype=np.uint8)
    farbgitter[linie] = (255, 255, 255)

    # Hintergrund-Komponenten finden; alles, was den Rand berührt, ist "außen"
    hintergrund = (~linie).astype(np.uint8)
    anzahl, labels = cv2.connectedComponents(hintergrund, connectivity=4)
    rand = set(labels[0]) | set(labels[-1]) | set(labels[:, 0]) | set(labels[:, -1])

    i = 0
    for lab in range(1, anzahl):
        if lab in rand:
            continue  # offene Fläche -> bleibt schwarz
        farbgitter[labels == lab] = PALETTE[i % len(PALETTE)]
        i += 1
    return farbgitter


def _als_png_rendern(farbgitter, png_pfad, font, char_w, line_h, offset):
    """Zeichnet farbige Blöcke auf ein exaktes Raster -> nahtlose Kacheln."""
    ox, oy = offset
    hoehe, breite = farbgitter.shape[:2]
    bild = Image.new("RGB", (char_w * breite, line_h * hoehe), (0, 0, 0))
    zeichner = ImageDraw.Draw(bild)
    for r in range(hoehe):
        for c in range(breite):
            farbe = tuple(int(x) for x in farbgitter[r, c])
            if farbe == (0, 0, 0):
                continue
            zeichner.text((c * char_w - ox, r * line_h - oy),
                          LINIENZEICHEN, font=font, fill=farbe)

    bild.save(png_pfad)


if __name__ == "__main__":
    pfad = sys.argv[1] if len(sys.argv) > 1 else "schule_von_athen.jpg"
    ascii_erzeugen(pfad)
