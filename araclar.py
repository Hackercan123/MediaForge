"""Ortak yardımcılar: harici araç bulma, ffprobe, biçimleme."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

if getattr(sys, "frozen", False):
    # PyInstaller: ayarlar/bin exe'nin yanında, gömülü veriler _MEIPASS'ta
    UYGULAMA_KLASORU = os.path.dirname(sys.executable)
    KAYNAK_KLASORU = getattr(sys, "_MEIPASS", UYGULAMA_KLASORU)
else:
    UYGULAMA_KLASORU = os.path.dirname(os.path.abspath(__file__))
    KAYNAK_KLASORU = UYGULAMA_KLASORU
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

_yol_onbellek: dict[str, str | None] = {}


def yol_onbellegini_temizle():
    """Araç güncellemesi sonrası bin\\ yeniden taransın diye çağrılır."""
    _yol_onbellek.clear()


def arac_yolu(ad: str, ozel_yol: str = "") -> str | None:
    """ffmpeg/ffprobe/yt-dlp yolunu bulur.

    Öncelik: ayarlardaki özel yol → uygulama yanındaki bin/ → PATH.
    """
    if ozel_yol and os.path.isfile(ozel_yol):
        return ozel_yol
    if ad in _yol_onbellek:
        return _yol_onbellek[ad]
    aday = os.path.join(UYGULAMA_KLASORU, "bin", ad + (".exe" if os.name == "nt" else ""))
    yol = aday if os.path.isfile(aday) else shutil.which(ad)
    _yol_onbellek[ad] = yol
    return yol


def ffprobe_bilgi(dosya: str, ffprobe: str) -> dict | None:
    try:
        sonuc = subprocess.run(
            [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", dosya],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, creationflags=CREATE_NO_WINDOW,
        )
        if sonuc.returncode == 0:
            return json.loads(sonuc.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return None


def sure_saniye(dosya: str, ffprobe: str) -> float | None:
    bilgi = ffprobe_bilgi(dosya, ffprobe)
    if bilgi:
        try:
            return float(bilgi["format"]["duration"])
        except (KeyError, ValueError):
            pass
    return None


# Sınanacak donanım kodlayıcılar: NVIDIA (nvenc), AMD (amf), Intel (qsv)
# AV1 kodlama yeni nesil kartlarda var (RTX 40+, RX 7000+, Arc) —
# deneme kodlaması geçemeyen makinede preset zaten görünmez.
DONANIM_KODLAYICILAR = (
    "h264_nvenc", "hevc_nvenc", "av1_nvenc",
    "h264_amf", "hevc_amf", "av1_amf",
    "h264_qsv", "hevc_qsv", "av1_qsv",
)


def kodlayici_calisiyor(ffmpeg: str, kodlayici: str) -> bool:
    """Kodlayıcı bu makinede gerçekten çalışıyor mu (1 karelik deneme kodlaması).

    Listede görünmesi yetmez: sürücü/donanım yoksa kodlayıcı açılışta hata verir.
    """
    try:
        sonuc = subprocess.run(
            [ffmpeg, "-hide_banner", "-f", "lavfi", "-i", "nullsrc=s=256x256:d=0.1",
             "-c:v", kodlayici, "-f", "null", "-"],
            capture_output=True, timeout=15, creationflags=CREATE_NO_WINDOW,
        )
        return sonuc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def calisan_donanim_kodlayicilar(ffmpeg: str) -> set[str]:
    return {k for k in DONANIM_KODLAYICILAR if kodlayici_calisiyor(ffmpeg, k)}


def benzersiz_yol(yol: str) -> str:
    """Dosya varsa 'ad (1).uz', 'ad (2).uz' diye ilerler."""
    if not os.path.exists(yol):
        return yol
    govde, uzanti = os.path.splitext(yol)
    n = 1
    while os.path.exists(f"{govde} ({n}){uzanti}"):
        n += 1
    return f"{govde} ({n}){uzanti}"


def insan_boyut(bayt: float) -> str:
    for birim in ("B", "KB", "MB", "GB"):
        if bayt < 1024:
            return f"{bayt:.1f} {birim}"
        bayt /= 1024
    return f"{bayt:.1f} TB"


def insan_zaman(saniye: float) -> str:
    saniye = int(saniye)
    s, dk, sn = saniye // 3600, (saniye % 3600) // 60, saniye % 60
    return f"{s:02d}:{dk:02d}:{sn:02d}" if s else f"{dk:02d}:{sn:02d}"


def zaman_ayristir(metin: str) -> float | None:
    """'90', '1:30', '01:02:03.5' gibi girdileri saniyeye çevirir."""
    metin = metin.strip().replace(",", ".")
    if not metin:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", metin):
        return float(metin)
    parcalar = metin.split(":")
    if len(parcalar) in (2, 3):
        try:
            toplam = 0.0
            for p in parcalar:
                toplam = toplam * 60 + float(p)
            return toplam
        except ValueError:
            return None
    return None


def medya_ozeti(bilgi: dict, dosya: str) -> str:
    """ffprobe çıktısından okunur özet üretir."""
    satirlar = [f"Dosya : {os.path.basename(dosya)}"]
    fmt = bilgi.get("format", {})
    try:
        satirlar.append(f"Boyut : {insan_boyut(float(fmt.get('size', 0)))}")
    except ValueError:
        pass
    try:
        satirlar.append(f"Süre  : {insan_zaman(float(fmt['duration']))}")
    except (KeyError, ValueError):
        pass
    if fmt.get("bit_rate"):
        satirlar.append(f"Bitrate : {int(fmt['bit_rate']) // 1000} kb/s (toplam)")
    satirlar.append(f"Format : {fmt.get('format_long_name', fmt.get('format_name', '?'))}")
    satirlar.append("")

    for akis in bilgi.get("streams", []):
        tur = akis.get("codec_type")
        codec = akis.get("codec_name", "?")
        dil = akis.get("tags", {}).get("language", "")
        dil = f" [{dil}]" if dil else ""
        if tur == "video":
            fps = akis.get("avg_frame_rate", "0/1")
            try:
                pay, payda = fps.split("/")
                fps = f"{float(pay) / float(payda):.2f}" if float(payda) else "?"
            except ValueError:
                fps = "?"
            br = akis.get("bit_rate")
            br = f", {int(br) // 1000} kb/s" if br else ""
            satirlar.append(
                f"Video #{akis.get('index')}: {codec}, "
                f"{akis.get('width')}x{akis.get('height')}, {fps} fps{br}{dil}"
            )
        elif tur == "audio":
            br = akis.get("bit_rate")
            br = f", {int(br) // 1000} kb/s" if br else ""
            satirlar.append(
                f"Ses   #{akis.get('index')}: {codec}, "
                f"{akis.get('channels', '?')} kanal, {akis.get('sample_rate', '?')} Hz{br}{dil}"
            )
        elif tur == "subtitle":
            satirlar.append(f"Altyazı #{akis.get('index')}: {codec}{dil}")
        else:
            satirlar.append(f"{tur or '?'} #{akis.get('index')}: {codec}")
    return "\n".join(satirlar)
