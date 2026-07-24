"""MediaForge — indirme (yt-dlp) + dönüştürme (ffmpeg) araç kutusu.

Çalıştırma:  python MediaForge.py
Gereksinim:  PySide6 (pip install -r requirements.txt) + bin\\ klasöründe
             veya PATH'te ffmpeg ve yt-dlp
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QTabWidget, QWidget,
)

from araclar import KAYNAK_KLASORU, calisan_donanim_kodlayicilar
from ayarlar import Ayarlar, AyarlarPenceresi
from guncelleme import GuncellemePenceresi
from kuyruk import KuyrukYoneticisi
from sekme_araclar import SekmeAraclar
from sekme_donustur import SekmeDonustur
from sekme_indir import SekmeIndir
from sekme_kuyruk import SekmeKuyruk


class DonanimSondasi(QObject):
    """Donanım kodlayıcı denemeleri birkaç saniye sürebildiği için ayrı iş parçacığında koşar."""
    sonuc = Signal(object)   # set[str]

    def basla(self, ffmpeg: str):
        threading.Thread(target=lambda: self.sonuc.emit(calisan_donanim_kodlayicilar(ffmpeg)),
                         daemon=True).start()


class AnaPencere(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MediaForge")
        self.resize(980, 640)

        self.ayarlar = Ayarlar()
        self.kuyruk_yon = KuyrukYoneticisi(self.ayarlar)

        self.sekmeler = QTabWidget()
        self.setCentralWidget(self.sekmeler)

        self.sekme_kuyruk = SekmeKuyruk(self.kuyruk_yon)
        self.sekme_indir = SekmeIndir(self.kuyruk_yon, self.ayarlar, self._kuyruga_git)
        self.sekme_donustur = SekmeDonustur(self.kuyruk_yon, self.ayarlar, self._kuyruga_git)
        self.sekme_araclar = SekmeAraclar(self.kuyruk_yon, self.ayarlar, self._kuyruga_git)

        self.sekmeler.addTab(self.sekme_indir, "⤓  İndir")
        self.sekmeler.addTab(self.sekme_donustur, "⟳  Dönüştür")
        self.sekmeler.addTab(self.sekme_araclar, "🛠  Araçlar")
        self.sekmeler.addTab(self.sekme_kuyruk, "☰  Kuyruk")

        kose = QWidget()
        kose_duzen = QHBoxLayout(kose)
        kose_duzen.setContentsMargins(0, 0, 4, 0)
        guncelle_dugme = QPushButton("⇩  Güncelle")
        guncelle_dugme.setFlat(True)
        guncelle_dugme.setToolTip("yt-dlp ve ffmpeg sürümlerini denetle, gerekirse bin\\ klasörüne indir")
        guncelle_dugme.clicked.connect(self._guncelleme_ac)
        ayar_dugme = QPushButton("⚙  Ayarlar")
        ayar_dugme.setFlat(True)
        ayar_dugme.clicked.connect(self._ayarlar_ac)
        kose_duzen.addWidget(guncelle_dugme)
        kose_duzen.addWidget(ayar_dugme)
        self.sekmeler.setCornerWidget(kose, Qt.TopRightCorner)

        self._durum_cubugu()
        self.kuyruk_yon.yapi_degisti.connect(self._rozet_guncelle)

        # Donanım kodlayıcılar (NVENC/AMF/QSV) arka planda denenir;
        # çalışanların GPU presetleri Dönüştür sekmesine eklenir.
        self._sonda = DonanimSondasi()
        if self.ayarlar.ffmpeg():
            self._sonda.sonuc.connect(self._donanim_sonucu)
            self._sonda.basla(self.ayarlar.ffmpeg())

    def _durum_cubugu(self):
        self.arac_durumu = QLabel()
        self.statusBar().addPermanentWidget(self.arac_durumu)
        self._arac_durumu_yaz()

    def _arac_durumu_yaz(self):
        parcalar = []
        for ad, yol in (("ffmpeg", self.ayarlar.ffmpeg()), ("yt-dlp", self.ayarlar.ytdlp())):
            parcalar.append(f"{ad} {'✓' if yol else '✗ BULUNAMADI'}")
        metin = "   ".join(parcalar)
        self.arac_durumu.setText(metin)
        if "✗" in metin:
            self.arac_durumu.setStyleSheet("color: #f28b82;")
            self.statusBar().showMessage("Eksik araç var — Ayarlar'dan yol gösterin.")
        else:
            self.arac_durumu.setStyleSheet("color: #81c995;")

    def _donanim_sonucu(self, kodlayicilar: set):
        if not kodlayicilar:
            return
        self.sekme_donustur.donanim_etkinlestir(kodlayicilar)
        aileler = []
        if any(k.endswith("nvenc") for k in kodlayicilar):
            aileler.append("NVENC (NVIDIA)")
        if any(k.endswith("amf") for k in kodlayicilar):
            aileler.append("AMF (AMD)")
        if any(k.endswith("qsv") for k in kodlayicilar):
            aileler.append("QSV (Intel)")
        self.statusBar().showMessage(
            "Donanım kodlayıcı bulundu: " + ", ".join(aileler) + " — GPU presetleri eklendi.", 8000)

    def _kuyruga_git(self):
        self.sekmeler.setCurrentWidget(self.sekme_kuyruk)

    def _rozet_guncelle(self):
        aktif = self.kuyruk_yon.aktif_sayisi()
        indeks = self.sekmeler.indexOf(self.sekme_kuyruk)
        self.sekmeler.setTabText(indeks, f"☰  Kuyruk ({aktif})" if aktif else "☰  Kuyruk")

    def _ayarlar_ac(self):
        if AyarlarPenceresi(self.ayarlar, self).exec():
            self._arac_durumu_yaz()
            self.kuyruk_yon.pompala()

    def _guncelleme_ac(self):
        GuncellemePenceresi(self.ayarlar, self.kuyruk_yon,
                            self._arac_durumu_yaz, self).exec()

    def closeEvent(self, olay):
        if self.kuyruk_yon.aktif_sayisi():
            yanit = QMessageBox.question(
                self, "Çıkılsın mı?",
                "Devam eden işler var. Çıkılırsa iptal edilecek.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if yanit != QMessageBox.Yes:
                olay.ignore()
                return
            self.kuyruk_yon.hepsini_iptal_et()
        olay.accept()


def _koyu_tema(uygulama: QApplication):
    uygulama.setStyle("Fusion")
    p = QPalette()
    arka = QColor(32, 33, 36)
    panel = QColor(41, 42, 45)
    metin = QColor(232, 234, 237)
    vurgu = QColor(38, 166, 154)
    p.setColor(QPalette.Window, arka)
    p.setColor(QPalette.WindowText, metin)
    p.setColor(QPalette.Base, panel)
    p.setColor(QPalette.AlternateBase, arka)
    p.setColor(QPalette.Text, metin)
    p.setColor(QPalette.Button, panel)
    p.setColor(QPalette.ButtonText, metin)
    p.setColor(QPalette.Highlight, vurgu)
    p.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    p.setColor(QPalette.ToolTipBase, panel)
    p.setColor(QPalette.ToolTipText, metin)
    p.setColor(QPalette.PlaceholderText, QColor(154, 160, 166))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(120, 124, 130))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(120, 124, 130))
    uygulama.setPalette(p)
    uygulama.setStyleSheet("""
        QProgressBar { border: 1px solid #3c4043; border-radius: 4px;
                       text-align: center; background: #292a2d; }
        QProgressBar::chunk { background-color: #26a69a; border-radius: 3px; }
        QGroupBox { border: 1px solid #3c4043; border-radius: 6px;
                    margin-top: 12px; padding-top: 6px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
    """)


def _koyu_baslik_cubugu(pencere: QWidget):
    """Windows'ta pencere başlık çubuğunu koyulaştırır (destek yoksa sessizce geçer)."""
    try:
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            int(pencere.winId()), 20, ctypes.byref(ctypes.c_int(1)), 4)
    except (AttributeError, OSError):
        pass


def main():
    uygulama = QApplication(sys.argv)
    uygulama.setApplicationName("MediaForge")
    ikon_yolu = os.path.join(KAYNAK_KLASORU, "ikon.ico")
    if os.path.isfile(ikon_yolu):
        uygulama.setWindowIcon(QIcon(ikon_yolu))
    _koyu_tema(uygulama)
    pencere = AnaPencere()
    pencere.show()
    _koyu_baslik_cubugu(pencere)
    sys.exit(uygulama.exec())


if __name__ == "__main__":
    main()
