"""
Originalbild in farbige, schattierte Block-ASCII-Art umwandeln.

Hybrid aus zwei Signalen:
  * Helligkeit des Originals  -> Zeichendichte aus der Rampe " ░▒▓█" (die Form)
  * Figur-ID aus figuren.png  -> Farbton pro erkannter Figur (die Farbe)

Hintergrundzellen (keine Figur) bleiben grau schattiert, Figurzellen werden in
ihrer poppigen Farbe eingefärbt – jeweils per Helligkeit abgedunkelt, damit das
Volumen lesbar bleibt.

Vorbereitung (einmalig):
    pip install opencv-python numpy pillow

Aufruf:
    python ascii_art.py pfad/zum/original.jpg [figuren.png]

Erzeugt ascii.txt (echter Text) und ascii.png (gerendert, farbig auf schwarz).
"""

import sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RAMPE = " ░▒▓█"  # hell -> dunkel: zunehmende Zeichendichte
FONT_PFAD = "/System/Library/Fonts/Menlo.ttc"  # echte Monospace-Schrift

# Poppige Farbtöne pro Figur (RGB)
PALETTE = [
    (255, 59, 48), (255, 149, 0), (255, 204, 0), (52, 199, 89),
    (0, 199, 190), (48, 176, 255), (88, 86, 255), (175, 82, 222),
    (255, 45, 146), (50, 215, 75), (255, 105, 180), (0, 245, 212),
]


def _font_laden(groesse):
    """Font + Block-Zellmaße + Ursprungs-Offset, damit Zeichen nahtlos kacheln."""
    font = ImageFont.truetype(FONT_PFAD, groesse)
    x0, y0, x1, y1 = font.getbbox("█")
    char_w = int(round(font.getlength("█")))
    line_h = y1 - y0
    return font, char_w, line_h, (x0, y0)


def _normieren(grau):
    """Kontrast auf vollen Bereich strecken -> die ganze Rampe wird genutzt."""
    lo, hi = np.percentile(grau, 2), np.percentile(grau, 98)
    if hi <= lo:
        return np.zeros_like(grau, dtype=np.float32)
    gestreckt = (grau.astype(np.float32) - lo) / (hi - lo)
    return np.clip(gestreckt, 0.0, 1.0)


def ascii_erzeugen(
    bildpfad,
    labelpfad="figuren.png",
    txt_pfad="ascii.txt",
    png_pfad="ascii.png",
    breite_zeichen=160,   # Detailgrad: Anzahl Zeichen pro Zeile
    schriftgroesse=10,    # Zellgröße in px fürs PNG-Rendering
):
    farbe_bgr = cv2.imread(bildpfad, cv2.IMREAD_COLOR)
    if farbe_bgr is None:
        raise FileNotFoundError(f"Bild nicht gefunden: {bildpfad}")
    h, w = farbe_bgr.shape[:2]

    # Seitenverhältnis aus den echten Block-Maßen ableiten -> kein verzerrtes PNG
    font, char_w, line_h, offset = _font_laden(schriftgroesse)
    breite = breite_zeichen
    hoehe = max(1, int(breite * (h / w) * (char_w / line_h)))

    grau = cv2.cvtColor(farbe_bgr, cv2.COLOR_BGR2GRAY)
    klein = cv2.resize(grau, (breite, hoehe), interpolation=cv2.INTER_AREA)
    hell = _normieren(klein)                       # 0..1 pro Zelle (Helligkeit)
    stufe = np.round(hell * (len(RAMPE) - 1)).astype(int)

    # Label-Karte (Figur-IDs) zum Raster verkleinern; fehlt sie -> nur Graustufen
    label = cv2.imread(labelpfad, cv2.IMREAD_GRAYSCALE)
    if label is None:
        label_klein = np.zeros((hoehe, breite), dtype=np.uint8)
    else:
        label_klein = cv2.resize(label, (breite, hoehe),
                                 interpolation=cv2.INTER_NEAREST)

    # .txt: reine Helligkeitsrampe (die Form, monochrom lesbar)
    zeilen = ["".join(RAMPE[s] for s in reihe) for reihe in stufe]
    with open(txt_pfad, "w") as f:
        f.write("\n".join(zeilen))

    farbgitter = _einfaerben(stufe, hell, label_klein)
    _als_png_rendern(stufe, farbgitter, png_pfad, font, char_w, line_h, offset)
    print(f"{breite}x{hoehe} Zeichen -> {txt_pfad}, {png_pfad}")


def _einfaerben(stufe, hell, label):
    """Farbe pro Zelle: Figur -> Farbton, sonst grau; jeweils per Helligkeit skaliert."""
    hoehe, breite = stufe.shape
    farbgitter = np.zeros((hoehe, breite, 3), dtype=np.uint8)
    v = (0.25 + 0.75 * hell)[..., None]  # nie ganz schwarz -> dunkle Zonen bleiben sichtbar

    grau = np.full((hoehe, breite, 3), 235, dtype=np.float32)
    palette = np.array(PALETTE, dtype=np.float32)
    figur = palette[(label.astype(int) - 1) % len(PALETTE)]  # Farbton je ID
    basis = np.where(label[..., None] > 0, figur, grau)

    farbgitter[:] = np.clip(basis * v, 0, 255).astype(np.uint8)
    return farbgitter


def _als_png_rendern(stufe, farbgitter, png_pfad, font, char_w, line_h, offset):
    """Zeichnet je Zelle das Rampenzeichen in seiner Farbe auf ein exaktes Raster."""
    ox, oy = offset
    hoehe, breite = stufe.shape
    bild = Image.new("RGB", (char_w * breite, line_h * hoehe), (0, 0, 0))
    zeichner = ImageDraw.Draw(bild)
    for r in range(hoehe):
        for c in range(breite):
            zeichen = RAMPE[stufe[r, c]]
            if zeichen == " ":
                continue
            farbe = tuple(int(x) for x in farbgitter[r, c])
            zeichner.text((c * char_w - ox, r * line_h - oy),
                          zeichen, font=font, fill=farbe)
    bild.save(png_pfad)


if __name__ == "__main__":
    pfad = sys.argv[1] if len(sys.argv) > 1 else "eingabe/schule_von_athen.jpg"
    labels = sys.argv[2] if len(sys.argv) > 2 else "figuren.png"
    ascii_erzeugen(pfad, labels)
