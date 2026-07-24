"""Kalıcı ayarlar (ayarlar.json) ve ayarlar penceresi."""
from __future__ import annotations

import json
import os

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
)

from araclar import UYGULAMA_KLASORU, arac_yolu

AYAR_DOSYASI = os.path.join(UYGULAMA_KLASORU, "ayarlar.json")

VARSAYILAN = {
    "indirme_klasoru": os.path.join(os.path.expanduser("~"), "Downloads"),
    "donusturme_ayni_klasore": True,
    "donusturme_klasoru": "",
    "es_zamanli_indirme": 2,
    "es_zamanli_ffmpeg": 1,
    "ffmpeg_yolu": "",
    "ffprobe_yolu": "",
    "ytdlp_yolu": "",
    "playlist_tamami": False,
    "ses_etiket_gom": True,
    "indirme_bicimi": 0,
}


class Ayarlar:
    def __init__(self):
        self.d = dict(VARSAYILAN)
        try:
            with open(AYAR_DOSYASI, encoding="utf-8") as f:
                self.d.update(json.load(f))
        except (OSError, json.JSONDecodeError):
            pass

    def kaydet(self):
        try:
            with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(self.d, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def __getitem__(self, anahtar):
        return self.d.get(anahtar, VARSAYILAN.get(anahtar))

    def __setitem__(self, anahtar, deger):
        self.d[anahtar] = deger

    # Araç yolları (özel yol boşsa otomatik bulunur)
    def ffmpeg(self):
        return arac_yolu("ffmpeg", self["ffmpeg_yolu"])

    def ffprobe(self):
        return arac_yolu("ffprobe", self["ffprobe_yolu"])

    def ytdlp(self):
        return arac_yolu("yt-dlp", self["ytdlp_yolu"])


class AyarlarPenceresi(QDialog):
    def __init__(self, ayarlar: Ayarlar, ebeveyn=None):
        super().__init__(ebeveyn)
        self.ayarlar = ayarlar
        self.setWindowTitle("Ayarlar")
        self.setMinimumWidth(520)

        duzen = QVBoxLayout(self)
        form = QFormLayout()
        duzen.addLayout(form)

        self.es_indirme = QSpinBox()
        self.es_indirme.setRange(1, 8)
        self.es_indirme.setValue(int(ayarlar["es_zamanli_indirme"]))
        form.addRow("Aynı anda indirme:", self.es_indirme)

        self.es_ffmpeg = QSpinBox()
        self.es_ffmpeg.setRange(1, 4)
        self.es_ffmpeg.setValue(int(ayarlar["es_zamanli_ffmpeg"]))
        form.addRow("Aynı anda dönüştürme:", self.es_ffmpeg)

        self.ffmpeg_kutu = self._yol_satiri(form, "ffmpeg yolu:", ayarlar["ffmpeg_yolu"])
        self.ffprobe_kutu = self._yol_satiri(form, "ffprobe yolu:", ayarlar["ffprobe_yolu"])
        self.ytdlp_kutu = self._yol_satiri(form, "yt-dlp yolu:", ayarlar["ytdlp_yolu"])

        ipucu = QLabel(
            "Yollar boş bırakılırsa program yanındaki bin\\ klasörüne ve PATH'e bakılır.\n"
            f"Bulunan: ffmpeg → {ayarlar.ffmpeg() or 'YOK'}\n"
            f"Bulunan: yt-dlp → {ayarlar.ytdlp() or 'YOK'}"
        )
        ipucu.setWordWrap(True)
        ipucu.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        duzen.addWidget(ipucu)

        dugmeler = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dugmeler.accepted.connect(self.accept)
        dugmeler.rejected.connect(self.reject)
        duzen.addWidget(dugmeler)

    def _yol_satiri(self, form: QFormLayout, etiket: str, deger: str) -> QLineEdit:
        kutu = QLineEdit(deger)
        kutu.setPlaceholderText("(otomatik)")
        sec = QPushButton("Seç…")

        def sec_tikla():
            yol, _ = QFileDialog.getOpenFileName(self, etiket, "", "Program (*.exe);;Tümü (*.*)")
            if yol:
                kutu.setText(yol)

        sec.clicked.connect(sec_tikla)
        satir = QHBoxLayout()
        satir.addWidget(kutu)
        satir.addWidget(sec)
        form.addRow(etiket, satir)
        return kutu

    def accept(self):
        a = self.ayarlar
        a["es_zamanli_indirme"] = self.es_indirme.value()
        a["es_zamanli_ffmpeg"] = self.es_ffmpeg.value()
        a["ffmpeg_yolu"] = self.ffmpeg_kutu.text().strip()
        a["ffprobe_yolu"] = self.ffprobe_kutu.text().strip()
        a["ytdlp_yolu"] = self.ytdlp_kutu.text().strip()
        a.kaydet()
        super().accept()
