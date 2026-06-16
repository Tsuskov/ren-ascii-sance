"""
Figuren in einem Bild erkennen und als weiße Konturlinien auf schwarzem
Hintergrund rendern (z. B. "Die Schule von Athen").

Vorbereitung (einmalig):
    pip install ultralytics opencv-python numpy

Beim ersten Lauf lädt sich das Modellgewicht yolo11x-seg.pt automatisch
herunter (ein paar hundert MB) – dafür wird einmalig Internet benötigt.

Aufruf:
    python konturen.py pfad/zum/bild.jpg
"""

import sys
import cv2
import numpy as np
from ultralytics import YOLO


def polygon_glaetten(punkte, fenster=5):
    """Glättet eine geschlossene Kontur per gleitendem Mittel (wrap-around)."""
    if fenster < 2 or len(punkte) < fenster:
        return punkte
    kernel = np.ones(fenster) / fenster
    rand = fenster
    geschlossen = np.concatenate([punkte[-rand:], punkte, punkte[:rand]])
    x = np.convolve(geschlossen[:, 0], kernel, mode="same")[rand:-rand]
    y = np.convolve(geschlossen[:, 1], kernel, mode="same")[rand:-rand]
    return np.stack([x, y], axis=1)


def konturen_rendern(
    bildpfad,
    ausgabepfad="konturen.png",
    linienstaerke=2,
    mit_nummern=False,
    confidence=0.10,   # niedrig: gemalte Figuren als Person durchgehen lassen
    bildgroesse=2048,  # hoch: kleine, dichte Figuren werden eher getrennt
    glaettung=7,       # Fenster fürs Glätten der Polygone (0/1 = aus)
    min_flaeche=150,   # Konturfragmente kleiner als das (in px²) verwerfen
    iou=0.85,          # hoch: stark überlappende Figuren nicht wegunterdrücken
):
    bild = cv2.imread(bildpfad)
    if bild is None:
        raise FileNotFoundError(f"Bild nicht gefunden: {bildpfad}")
    hoehe, breite = bild.shape[:2]

    # Segmentierungsmodell laden und nur die Klasse "person" (0) suchen
    modell = YOLO("yolo11x-seg.pt")
    ergebnis = modell.predict(
        source=bild,
        conf=confidence,
        imgsz=bildgroesse,
        iou=iou,
        classes=[0],
        retina_masks=True,  # Masken in voller Auflösung -> sauberere Konturen
        verbose=False,
    )[0]

    # Leere schwarze Leinwand in Bildgröße
    leinwand = np.zeros((hoehe, breite, 3), dtype=np.uint8)

    if ergebnis.masks is None:
        print("Keine Figuren erkannt – conf senken oder imgsz erhöhen.")
        cv2.imwrite(ausgabepfad, leinwand)
        return

    weiss = (255, 255, 255)
    masken = ergebnis.masks.data.cpu().numpy()  # [N, H, W], Werte 0/1

    for i, maske in enumerate(masken, start=1):
        bitmaske = (maske > 0.5).astype(np.uint8)
        if bitmaske.shape != (hoehe, breite):
            bitmaske = cv2.resize(bitmaske, (breite, hoehe),
                                  interpolation=cv2.INTER_NEAREST)

        # Jede zusammenhängende Komponente als eigene Kontur -> kein Quer-Verbinden
        konturen, _ = cv2.findContours(bitmaske, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        for kontur in konturen:
            if cv2.contourArea(kontur) < min_flaeche:
                continue
            punkte = polygon_glaetten(kontur.reshape(-1, 2), glaettung)
            punkte = punkte.astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(leinwand, [punkte], isClosed=True,
                          color=weiss, thickness=linienstaerke,
                          lineType=cv2.LINE_AA)

        if mit_nummern:
            ys, xs = np.where(bitmaske)
            cv2.putText(leinwand, str(i), (int(xs.mean()), int(ys.mean())),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, weiss, 1, cv2.LINE_AA)

    cv2.imwrite(ausgabepfad, leinwand)
    print(f"{len(masken)} Figuren erkannt -> {ausgabepfad}")


if __name__ == "__main__":
    pfad = sys.argv[1] if len(sys.argv) > 1 else "schule_von_athen.jpg"
    konturen_rendern(pfad)
