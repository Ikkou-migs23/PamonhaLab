"""Vetorização de imagem em SVG colorido, em camadas.
Adaptado do projeto Vetorizar-Imagem (k-means no espaço Lab + contornos suavizados)."""
import cv2
import numpy as np
from PIL import Image, ImageOps
from sklearn.cluster import KMeans

LIMPEZA_MASCARA = 3   # filtro de mediana nas máscaras (0 desliga)
AREA_MINIMA = 6       # descarta manchinhas menores que N pixels
EPSILON = 0.9         # simplificação do contorno: menor = mais detalhe
LADO_MAXIMO = 1600    # no site, reduz imagens grandes para não travar o servidor
SEED = 0


def carregar_rgb(arquivo, fundo=(255, 255, 255)):
    img = ImageOps.exif_transpose(Image.open(arquivo))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        base = Image.new("RGBA", img.size, tuple(fundo) + (255,))
        img = Image.alpha_composite(base, img)
    img = img.convert("RGB")
    if max(img.size) > LADO_MAXIMO:
        img.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)
    return np.asarray(img)


def quantizar(rgb, n_cores):
    entrada = cv2.bilateralFilter(rgb, d=5, sigmaColor=25, sigmaSpace=5)
    lab = cv2.cvtColor(entrada, cv2.COLOR_RGB2LAB)
    h, w = lab.shape[:2]
    pixels = lab.reshape(-1, 3)

    rng = np.random.default_rng(SEED)
    idx = rng.choice(len(pixels), size=min(200_000, len(pixels)), replace=False)
    km = KMeans(n_clusters=n_cores, n_init=3, random_state=SEED).fit(pixels[idx])
    rotulos = km.predict(pixels).reshape(h, w)

    paleta = np.zeros((n_cores, 3), dtype=np.uint8)
    for k in range(n_cores):
        m = rotulos == k
        paleta[k] = rgb[m].mean(axis=0).round() if m.any() else (0, 0, 0)
    return rotulos, paleta


def contorno_para_path(pts):
    n = len(pts)
    if n < 3:
        return ""
    mid = (pts + np.roll(pts, -1, axis=0)) / 2.0
    partes = [f"M{mid[-1][0]:.1f} {mid[-1][1]:.1f}"]
    for i in range(n):
        p, m = pts[i], mid[i]
        partes.append(f"Q{p[0]:.1f} {p[1]:.1f} {m[0]:.1f} {m[1]:.1f}")
    partes.append("Z")
    return "".join(partes)


def mascara_para_path(mascara):
    if LIMPEZA_MASCARA:
        mascara = cv2.medianBlur(mascara, LIMPEZA_MASCARA)
    contornos, _ = cv2.findContours(mascara, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    partes = []
    for c in contornos:
        if abs(cv2.contourArea(c)) < AREA_MINIMA:
            continue
        c = cv2.approxPolyDP(c, EPSILON, True)
        pts = c.reshape(-1, 2).astype(np.float64) + 0.5
        d = contorno_para_path(pts)
        if d:
            partes.append(d)
    return "".join(partes)


def vetorizar(rgb, n_cores=24):
    h, w = rgb.shape[:2]
    n_cores = max(2, min(int(n_cores), 48))
    rotulos, paleta = quantizar(rgb, n_cores)

    areas = np.bincount(rotulos.ravel(), minlength=n_cores)
    ordem = [int(k) for k in np.argsort(-areas) if areas[k] > 0]

    fundo = paleta[ordem[0]]
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="rgb({fundo[0]},{fundo[1]},{fundo[2]})"/>',
    ]
    for pos in range(1, len(ordem)):
        k = ordem[pos]
        mascara = np.isin(rotulos, ordem[pos:]).astype(np.uint8) * 255
        d = mascara_para_path(mascara)
        if not d:
            continue
        r, g, b = paleta[k]
        svg.append(f'<path fill="rgb({r},{g},{b})" fill-rule="evenodd" d="{d}"/>')
    svg.append("</svg>")
    return "\n".join(svg)
