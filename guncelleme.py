"""Araç güncelleme: yt-dlp ve ffmpeg'i denetleyip bin\\ klasörüne indirir.

Kaynaklar:
- yt-dlp : resmî GitHub sürümü (bağımsız exe)
- ffmpeg : BtbN/FFmpeg-Builds GitHub derlemeleri (win64 gpl, zip)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import urllib.request
import zipfile

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
    QVBoxLayout,
)

from araclar import CREATE_NO_WINDOW, UYGULAMA_KLASORU, insan_boyut, yol_onbellegini_temizle

BIN_KLASORU = os.path.join(UYGULAMA_KLASORU, "bin")
YTDLP_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
FFMPEG_API = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"


def _istek(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": "MediaForge"})


def _json_al(url: str) -> dict:
    with urllib.request.urlopen(_istek(url), timeout=20) as yanit:
        return json.load(yanit)


def _surum_ciktisi(exe: str | None, arg: str) -> str:
    if not exe:
        return ""
    try:
        sonuc = subprocess.run([exe, arg], capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               timeout=20, creationflags=CREATE_NO_WINDOW)
        return sonuc.stdout.strip().splitlines()[0] if sonuc.stdout.strip() else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


class Guncelleyici(QObject):
    """Denetleme/indirme işlemleri ayrı iş parçacığında; sonuçlar sinyalle döner."""

    kontrol_sonucu = Signal(dict)
    ilerleme = Signal(int)
    durum = Signal(str)
    is_bitti = Signal(bool, str)    # başarı, mesaj

    def __init__(self, ayarlar):
        super().__init__()
        self.ayarlar = ayarlar

    # --- denetleme ---
    def kontrol_baslat(self):
        threading.Thread(target=self._kontrol, daemon=True).start()

    def _kontrol(self):
        sonuc = {"hata": ""}
        try:
            # yt-dlp: sürüm etiketi doğrudan karşılaştırılabilir (ör. 2026.07.04)
            sonuc["ytdlp_kurulu"] = _surum_ciktisi(self.ayarlar.ytdlp(), "--version")
            sonuc["ytdlp_son"] = _json_al(YTDLP_API).get("tag_name", "")

            # ffmpeg: kurulu sürüm satırından hat (n8.0 gibi) okunur;
            # BtbN sürüm hattı zip'lerinden en yükseği seçilir
            satir = _surum_ciktisi(self.ayarlar.ffmpeg(), "-version")
            esle = re.search(r"\bn(\d+(?:\.\d+)+)", satir)
            sonuc["ffmpeg_kurulu_hat"] = esle.group(1) if esle else ""
            sonuc["ffmpeg_kurulu_metin"] = (re.search(r"version (\S+)", satir).group(1)
                                            if "version" in satir else "")

            en_yuksek, secilen = (), None
            for varlik in _json_al(FFMPEG_API).get("assets", []):
                ad = varlik.get("name", "")
                esle = re.fullmatch(r"ffmpeg-n(\d+(?:\.\d+)+)-latest-win64-gpl-[\d.]+\.zip", ad)
                if esle:
                    hat = tuple(int(p) for p in esle.group(1).split("."))
                    if hat > en_yuksek:
                        en_yuksek, secilen = hat, varlik
            if secilen:
                sonuc["ffmpeg_son_hat"] = ".".join(str(p) for p in en_yuksek)
                sonuc["ffmpeg_url"] = secilen["browser_download_url"]
                sonuc["ffmpeg_boyut"] = secilen.get("size", 0)
        except OSError as h:
            sonuc["hata"] = f"Sürüm bilgisi alınamadı: {h}"
        self.kontrol_sonucu.emit(sonuc)

    # --- indirme ---
    def _indir(self, url: str, hedef: str):
        with urllib.request.urlopen(_istek(url), timeout=30) as yanit, open(hedef, "wb") as f:
            toplam = int(yanit.headers.get("Content-Length") or 0)
            inen = 0
            while parca := yanit.read(1 << 16):
                f.write(parca)
                inen += len(parca)
                if toplam:
                    self.ilerleme.emit(int(inen * 100 / toplam))

    def ytdlp_guncelle(self):
        threading.Thread(target=self._ytdlp_guncelle, daemon=True).start()

    def _ytdlp_guncelle(self):
        try:
            os.makedirs(BIN_KLASORU, exist_ok=True)
            hedef = os.path.join(BIN_KLASORU, "yt-dlp.exe")
            gecici = hedef + ".indiriliyor"
            self.durum.emit("yt-dlp indiriliyor…")
            self._indir(YTDLP_URL, gecici)
            os.replace(gecici, hedef)
            yol_onbellegini_temizle()
            self.is_bitti.emit(True, "yt-dlp güncellendi.")
        except (OSError, PermissionError) as h:
            self.is_bitti.emit(False, f"yt-dlp güncellenemedi: {h}")

    def ffmpeg_guncelle(self, url: str):
        threading.Thread(target=self._ffmpeg_guncelle, args=(url,), daemon=True).start()

    def _ffmpeg_guncelle(self, url: str):
        gecici_zip = os.path.join(BIN_KLASORU, "ffmpeg.indiriliyor.zip")
        try:
            os.makedirs(BIN_KLASORU, exist_ok=True)
            self.durum.emit("ffmpeg arşivi indiriliyor…")
            self._indir(url, gecici_zip)

            self.durum.emit("Arşivden çıkarılıyor…")
            self.ilerleme.emit(-1)
            cikarilan = 0
            with zipfile.ZipFile(gecici_zip) as arsiv:
                for uye in arsiv.namelist():
                    for exe in ("ffmpeg.exe", "ffprobe.exe"):
                        if uye.endswith("bin/" + exe):
                            hedef = os.path.join(BIN_KLASORU, exe)
                            with arsiv.open(uye) as kaynak, open(hedef + ".yeni", "wb") as f:
                                shutil.copyfileobj(kaynak, f)
                            os.replace(hedef + ".yeni", hedef)
                            cikarilan += 1
            if cikarilan < 2:
                raise OSError("arşivde ffmpeg.exe/ffprobe.exe bulunamadı")
            yol_onbellegini_temizle()
            self.is_bitti.emit(True, "ffmpeg ve ffprobe güncellendi.")
        except (OSError, PermissionError, zipfile.BadZipFile) as h:
            self.is_bitti.emit(False, f"ffmpeg güncellenemedi: {h}")
        finally:
            try:
                if os.path.isfile(gecici_zip):
                    os.remove(gecici_zip)
            except OSError:
                pass


class GuncellemePenceresi(QDialog):
    def __init__(self, ayarlar, kuyruk_yon, yenilendi_cb, ebeveyn=None):
        super().__init__(ebeveyn)
        self.kuyruk_yon = kuyruk_yon
        self.yenilendi_cb = yenilendi_cb
        self.ffmpeg_url = ""
        self.setWindowTitle("Araç Güncelleme")
        self.setMinimumWidth(560)

        self.guncelleyici = Guncelleyici(ayarlar)
        self.guncelleyici.kontrol_sonucu.connect(self._kontrol_geldi)
        self.guncelleyici.ilerleme.connect(self._ilerleme)
        self.guncelleyici.durum.connect(lambda m: self.durum_etiketi.setText(m))
        self.guncelleyici.is_bitti.connect(self._is_bitti)

        duzen = QVBoxLayout(self)
        izgara = QGridLayout()
        izgara.setHorizontalSpacing(16)
        duzen.addLayout(izgara)

        izgara.addWidget(QLabel("<b>yt-dlp</b>"), 0, 0)
        self.ytdlp_durum = QLabel("Denetleniyor…")
        izgara.addWidget(self.ytdlp_durum, 0, 1)
        self.ytdlp_dugme = QPushButton("Güncelle")
        self.ytdlp_dugme.setEnabled(False)
        self.ytdlp_dugme.clicked.connect(self._ytdlp_tikla)
        izgara.addWidget(self.ytdlp_dugme, 0, 2)

        izgara.addWidget(QLabel("<b>ffmpeg</b>"), 1, 0)
        self.ffmpeg_durum = QLabel("Denetleniyor…")
        izgara.addWidget(self.ffmpeg_durum, 1, 1)
        self.ffmpeg_dugme = QPushButton("Güncelle")
        self.ffmpeg_dugme.setEnabled(False)
        self.ffmpeg_dugme.clicked.connect(self._ffmpeg_tikla)
        izgara.addWidget(self.ffmpeg_dugme, 1, 2)
        izgara.setColumnStretch(1, 1)

        self.cubuk = QProgressBar()
        self.cubuk.setVisible(False)
        duzen.addWidget(self.cubuk)
        self.durum_etiketi = QLabel("")
        self.durum_etiketi.setStyleSheet("color: #9aa0a6;")
        duzen.addWidget(self.durum_etiketi)

        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.accept)
        duzen.addWidget(kapat)

        self.guncelleyici.kontrol_baslat()

    # --- denetleme sonucu ---
    def _kontrol_geldi(self, s: dict):
        if s.get("hata"):
            self.ytdlp_durum.setText("—")
            self.ffmpeg_durum.setText("—")
            self.durum_etiketi.setText(s["hata"])
            return

        kurulu, son = s.get("ytdlp_kurulu", ""), s.get("ytdlp_son", "")
        if not kurulu:
            self.ytdlp_durum.setText(f"Kurulu değil.  En son: {son}")
            self.ytdlp_dugme.setText("İndir")
            self.ytdlp_dugme.setEnabled(bool(son))
        elif son and kurulu != son:
            self.ytdlp_durum.setText(f"Kurulu: {kurulu}   →   En son: {son}")
            self.ytdlp_dugme.setEnabled(True)
        else:
            self.ytdlp_durum.setText(f"Güncel ({kurulu})")

        self.ffmpeg_url = s.get("ffmpeg_url", "")
        kurulu_hat, son_hat = s.get("ffmpeg_kurulu_hat", ""), s.get("ffmpeg_son_hat", "")
        boyut = insan_boyut(s.get("ffmpeg_boyut", 0)) if s.get("ffmpeg_boyut") else "?"
        if not s.get("ffmpeg_kurulu_metin"):
            self.ffmpeg_durum.setText(f"Kurulu değil.  En son: {son_hat} ({boyut})")
            self.ffmpeg_dugme.setText("İndir")
            self.ffmpeg_dugme.setEnabled(bool(self.ffmpeg_url))
        elif not kurulu_hat:
            self.ffmpeg_durum.setText(
                f"Kurulu: {s['ffmpeg_kurulu_metin']} (farklı kaynak, karşılaştırılamıyor)   "
                f"En son: {son_hat} ({boyut})")
            self.ffmpeg_dugme.setEnabled(bool(self.ffmpeg_url))
        elif son_hat and kurulu_hat != son_hat:
            self.ffmpeg_durum.setText(f"Kurulu: n{kurulu_hat}   →   En son: n{son_hat} ({boyut})")
            self.ffmpeg_dugme.setEnabled(True)
        else:
            self.ffmpeg_durum.setText(f"Güncel (n{kurulu_hat})")

    # --- düğmeler ---
    def _mesgul_mu(self) -> bool:
        if self.kuyruk_yon.aktif_sayisi():
            QMessageBox.warning(self, "İşler sürüyor",
                                "Kuyrukta devam eden işler varken araçlar güncellenemez.")
            return True
        return False

    def _indirme_basladi(self):
        self.ytdlp_dugme.setEnabled(False)
        self.ffmpeg_dugme.setEnabled(False)
        self.cubuk.setVisible(True)
        self.cubuk.setRange(0, 100)
        self.cubuk.setValue(0)

    def _ytdlp_tikla(self):
        if not self._mesgul_mu():
            self._indirme_basladi()
            self.guncelleyici.ytdlp_guncelle()

    def _ffmpeg_tikla(self):
        if not self._mesgul_mu():
            self._indirme_basladi()
            self.guncelleyici.ffmpeg_guncelle(self.ffmpeg_url)

    # --- ilerleme/sonuç ---
    def _ilerleme(self, yuzde: int):
        if yuzde < 0:
            self.cubuk.setRange(0, 0)
        else:
            self.cubuk.setRange(0, 100)
            self.cubuk.setValue(yuzde)

    def _is_bitti(self, basarili: bool, mesaj: str):
        self.cubuk.setVisible(False)
        self.durum_etiketi.setText(mesaj)
        if basarili:
            self.yenilendi_cb()
            self.ytdlp_durum.setText("Denetleniyor…")
            self.ffmpeg_durum.setText("Denetleniyor…")
            self.guncelleyici.kontrol_baslat()
        else:
            self.ytdlp_dugme.setEnabled(True)
            self.ffmpeg_dugme.setEnabled(bool(self.ffmpeg_url))
