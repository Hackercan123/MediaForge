"""İndir sekmesi: yt-dlp ile bağlantıdan video/ses indirme."""
from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from kuyruk import IndirmeIsi

# (etiket, yt-dlp argümanları, ses mi?)
BICIMLER = [
    ("Video — en yüksek kalite (MP4)",
     ["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b", "--merge-output-format", "mp4"],
     False),
    ("Video — en yüksek kalite (orijinal format)",
     ["-f", "bv*+ba/b"],
     False),
    ("Video — 1080p (MP4)",
     ["-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b",
      "--merge-output-format", "mp4"],
     False),
    ("Video — 720p (MP4)",
     ["-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]/b",
      "--merge-output-format", "mp4"],
     False),
    ("Ses — MP3",
     ["-x", "--audio-format", "mp3", "--audio-quality", "0"],
     True),
    ("Ses — orijinal biçim (m4a/opus)",
     ["-x"],
     True),
]


class SekmeIndir(QWidget):
    def __init__(self, kuyruk_yon, ayarlar, kuyruga_git):
        super().__init__()
        self.kuyruk_yon = kuyruk_yon
        self.ayarlar = ayarlar
        self.kuyruga_git = kuyruga_git

        duzen = QVBoxLayout(self)
        duzen.setSpacing(10)

        duzen.addWidget(QLabel("Bağlantılar (her satıra bir adet):"))
        self.url_kutusu = QPlainTextEdit()
        self.url_kutusu.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self.url_kutusu.setMaximumHeight(120)
        duzen.addWidget(self.url_kutusu)

        yapistir = QPushButton("Panodan Yapıştır")
        yapistir.clicked.connect(self._yapistir)
        satir0 = QHBoxLayout()
        satir0.addWidget(yapistir)
        satir0.addStretch()
        duzen.addLayout(satir0)

        satir1 = QHBoxLayout()
        satir1.addWidget(QLabel("Biçim:"))
        self.bicim = QComboBox()
        self.bicim.addItems([b[0] for b in BICIMLER])
        self.bicim.setCurrentIndex(int(ayarlar["indirme_bicimi"]))
        satir1.addWidget(self.bicim, 1)
        duzen.addLayout(satir1)

        satir2 = QHBoxLayout()
        satir2.addWidget(QLabel("Klasör:"))
        self.klasor_kutusu = QLineEdit(ayarlar["indirme_klasoru"])
        satir2.addWidget(self.klasor_kutusu, 1)
        klasor_sec = QPushButton("Seç…")
        klasor_sec.clicked.connect(self._klasor_sec)
        satir2.addWidget(klasor_sec)
        duzen.addLayout(satir2)

        self.playlist_kutusu = QCheckBox("Oynatma listesi bağlantılarında listenin tamamını indir")
        self.playlist_kutusu.setChecked(bool(ayarlar["playlist_tamami"]))
        duzen.addWidget(self.playlist_kutusu)

        self.etiket_kutusu = QCheckBox("Ses dosyalarına kapak görseli ve üstveri göm")
        self.etiket_kutusu.setChecked(bool(ayarlar["ses_etiket_gom"]))
        duzen.addWidget(self.etiket_kutusu)

        self.indir_dugme = QPushButton("İndir  ⤓")
        self.indir_dugme.setMinimumHeight(36)
        self.indir_dugme.clicked.connect(self._indir)
        duzen.addWidget(self.indir_dugme)

        self.durum = QLabel("")
        self.durum.setStyleSheet("color: #9aa0a6;")
        duzen.addWidget(self.durum)
        duzen.addStretch()

    def _yapistir(self):
        metin = QApplication.clipboard().text().strip()
        if metin:
            mevcut = self.url_kutusu.toPlainText().rstrip()
            self.url_kutusu.setPlainText((mevcut + "\n" + metin).strip())

    def _klasor_sec(self):
        yol = QFileDialog.getExistingDirectory(self, "İndirme klasörü", self.klasor_kutusu.text())
        if yol:
            self.klasor_kutusu.setText(yol)

    def _indir(self):
        ytdlp = self.ayarlar.ytdlp()
        if not ytdlp:
            QMessageBox.warning(self, "yt-dlp yok",
                                "yt-dlp bulunamadı. Ayarlar'dan yolunu gösterin\n"
                                "veya 'pip install yt-dlp' ile kurun.")
            return

        urller = [s.strip() for s in self.url_kutusu.toPlainText().splitlines()
                  if s.strip().startswith(("http://", "https://"))]
        if not urller:
            QMessageBox.information(self, "Bağlantı yok", "Geçerli bir bağlantı yapıştırın (http… ile başlamalı).")
            return

        klasor = self.klasor_kutusu.text().strip()
        if not os.path.isdir(klasor):
            QMessageBox.warning(self, "Klasör yok", f"İndirme klasörü bulunamadı:\n{klasor}")
            return

        # Seçimleri hatırla
        a = self.ayarlar
        a["indirme_klasoru"] = klasor
        a["indirme_bicimi"] = self.bicim.currentIndex()
        a["playlist_tamami"] = self.playlist_kutusu.isChecked()
        a["ses_etiket_gom"] = self.etiket_kutusu.isChecked()
        a.kaydet()

        _, bicim_args, ses_mi = BICIMLER[self.bicim.currentIndex()]
        args = list(bicim_args)
        args.append("--yes-playlist" if self.playlist_kutusu.isChecked() else "--no-playlist")
        if ses_mi and self.etiket_kutusu.isChecked():
            args += ["--embed-thumbnail", "--embed-metadata"]

        for url in urller:
            self.kuyruk_yon.ekle(IndirmeIsi(url, klasor, args, ytdlp, a.ffmpeg()))

        self.url_kutusu.clear()
        self.durum.setText(f"{len(urller)} indirme kuyruğa eklendi.")
        self.kuyruga_git()
