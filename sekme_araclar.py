"""Araçlar sekmesi: medya bilgisi, video kesme, ses çıkarma, video birleştirme."""
from __future__ import annotations

import os
import tempfile

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QScrollArea,
    QTextEdit, QVBoxLayout, QWidget,
)

from araclar import benzersiz_yol, ffprobe_bilgi, medya_ozeti, sure_saniye, zaman_ayristir
from kuyruk import FfmpegIsi
from sekme_donustur import MEDYA_FILTRE

# ses codec'i → kayıpsız çıkarma için dosya uzantısı
KOPYA_UZANTI = {
    "aac": "m4a", "alac": "m4a", "mp3": "mp3", "opus": "opus",
    "vorbis": "ogg", "flac": "flac", "ac3": "ac3", "eac3": "eac3",
}


class SekmeAraclar(QWidget):
    def __init__(self, kuyruk_yon, ayarlar, kuyruga_git):
        super().__init__()
        self.kuyruk_yon = kuyruk_yon
        self.ayarlar = ayarlar
        self.kuyruga_git = kuyruga_git

        dis_duzen = QVBoxLayout(self)
        dis_duzen.setContentsMargins(0, 0, 0, 0)
        kaydirma = QScrollArea()
        kaydirma.setWidgetResizable(True)
        kaydirma.setFrameShape(QScrollArea.NoFrame)
        icerik = QWidget()
        duzen = QVBoxLayout(icerik)
        duzen.setSpacing(12)
        duzen.addWidget(self._bilgi_grubu())
        duzen.addWidget(self._kesme_grubu())
        duzen.addWidget(self._ses_grubu())
        duzen.addWidget(self._birlestirme_grubu())
        duzen.addStretch()
        kaydirma.setWidget(icerik)
        dis_duzen.addWidget(kaydirma)

    # --- ortak parçalar ---
    def _dosya_satiri(self) -> tuple[QHBoxLayout, QLineEdit]:
        kutu = QLineEdit()
        kutu.setPlaceholderText("Dosya seçin…")
        sec = QPushButton("Seç…")

        def tikla():
            yol, _ = QFileDialog.getOpenFileName(self, "Dosya seç", "", MEDYA_FILTRE)
            if yol:
                kutu.setText(yol)

        sec.clicked.connect(tikla)
        satir = QHBoxLayout()
        satir.addWidget(QLabel("Dosya:"))
        satir.addWidget(kutu, 1)
        satir.addWidget(sec)
        return satir, kutu

    def _dosya_dogrula(self, kutu: QLineEdit) -> str | None:
        yol = kutu.text().strip().strip('"')
        if not yol or not os.path.isfile(yol):
            QMessageBox.warning(self, "Dosya yok", "Önce geçerli bir dosya seçin.")
            return None
        return yol

    # --- 1) Medya bilgisi ---
    def _bilgi_grubu(self) -> QGroupBox:
        grup = QGroupBox("Medya Bilgisi (ffprobe)")
        duzen = QVBoxLayout(grup)
        satir, self.bilgi_dosya = self._dosya_satiri()
        duzen.addLayout(satir)
        goster = QPushButton("Bilgiyi Göster")
        goster.clicked.connect(self._bilgi_goster)
        duzen.addWidget(goster)
        return grup

    def _bilgi_goster(self):
        yol = self._dosya_dogrula(self.bilgi_dosya)
        if not yol:
            return
        ffprobe = self.ayarlar.ffprobe()
        if not ffprobe:
            QMessageBox.warning(self, "ffprobe yok", "ffprobe bulunamadı (ffmpeg paketiyle gelir).")
            return
        bilgi = ffprobe_bilgi(yol, ffprobe)
        if not bilgi:
            QMessageBox.warning(self, "Okunamadı", "Dosya bilgisi alınamadı — bozuk ya da desteklenmeyen dosya.")
            return
        pencere = QDialog(self)
        pencere.setWindowTitle(os.path.basename(yol))
        pencere.resize(560, 380)
        v = QVBoxLayout(pencere)
        metin = QTextEdit()
        metin.setReadOnly(True)
        metin.setFontFamily("Consolas")
        metin.setPlainText(medya_ozeti(bilgi, yol))
        v.addWidget(metin)
        pencere.exec()

    # --- 2) Video kesme ---
    def _kesme_grubu(self) -> QGroupBox:
        grup = QGroupBox("Video / Ses Kes")
        duzen = QVBoxLayout(grup)
        satir, self.kes_dosya = self._dosya_satiri()
        duzen.addLayout(satir)

        satir2 = QHBoxLayout()
        satir2.addWidget(QLabel("Başlangıç:"))
        self.kes_bas = QLineEdit()
        self.kes_bas.setPlaceholderText("0:00 veya 90 (saniye)")
        satir2.addWidget(self.kes_bas)
        satir2.addWidget(QLabel("Bitiş:"))
        self.kes_bit = QLineEdit()
        self.kes_bit.setPlaceholderText("boş = sona kadar")
        satir2.addWidget(self.kes_bit)
        duzen.addLayout(satir2)

        self.kes_hassas = QCheckBox("Kare hassas kesim (yeniden kodlama yapılır)")
        duzen.addWidget(self.kes_hassas)
        ipucu = QLabel("Kapalıyken kesim yeniden kodlama yapılmadan gerçekleştirilir; "
                       "başlangıç noktası en yakın anahtar kareye hizalanır.")
        ipucu.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        duzen.addWidget(ipucu)

        ekle = QPushButton("Kuyruğa Ekle")
        ekle.clicked.connect(self._kes_ekle)
        duzen.addWidget(ekle)
        return grup

    def _kes_ekle(self):
        yol = self._dosya_dogrula(self.kes_dosya)
        if not yol:
            return
        ffmpeg = self.ayarlar.ffmpeg()
        if not ffmpeg:
            QMessageBox.warning(self, "ffmpeg yok", "ffmpeg bulunamadı. Ayarlar'dan yolunu gösterin.")
            return

        bas = zaman_ayristir(self.kes_bas.text()) or 0.0
        bit = zaman_ayristir(self.kes_bit.text())
        if bit is not None and bit <= bas:
            QMessageBox.warning(self, "Zaman hatası", "Bitiş, başlangıçtan büyük olmalı.")
            return

        govde, uzanti = os.path.splitext(yol)
        cikti = benzersiz_yol(f"{govde} (kesit){uzanti}")

        args = ["-ss", str(bas), "-i", yol]
        toplam = sure_saniye(yol, self.ayarlar.ffprobe()) if self.ayarlar.ffprobe() else None
        if bit is not None:
            args += ["-t", str(bit - bas)]
            is_suresi = bit - bas
        else:
            is_suresi = (toplam - bas) if toplam else None

        if self.kes_hassas.isChecked():
            args += ["-c:v", "libx264", "-crf", "20", "-preset", "medium",
                     "-c:a", "aac", "-b:a", "192k"]
        else:
            args += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
        args.append(cikti)

        self.kuyruk_yon.ekle(FfmpegIsi(os.path.basename(cikti), ffmpeg, args, cikti, is_suresi))
        self.kuyruga_git()

    # --- 3) Ses çıkarma ---
    def _ses_grubu(self) -> QGroupBox:
        grup = QGroupBox("Videodan Ses Çıkar")
        duzen = QVBoxLayout(grup)
        satir, self.ses_dosya = self._dosya_satiri()
        duzen.addLayout(satir)

        satir2 = QHBoxLayout()
        satir2.addWidget(QLabel("Biçim:"))
        self.ses_bicim = QComboBox()
        self.ses_bicim.addItems([
            "Kayıpsız — orijinal codec, yeniden kodlama yok",
            "MP3 — 192 kb/s",
            "MP3 — 320 kb/s",
        ])
        satir2.addWidget(self.ses_bicim, 1)
        duzen.addLayout(satir2)

        ekle = QPushButton("Kuyruğa Ekle")
        ekle.clicked.connect(self._ses_ekle)
        duzen.addWidget(ekle)
        return grup

    def _ses_ekle(self):
        yol = self._dosya_dogrula(self.ses_dosya)
        if not yol:
            return
        ffmpeg = self.ayarlar.ffmpeg()
        ffprobe = self.ayarlar.ffprobe()
        if not ffmpeg:
            QMessageBox.warning(self, "ffmpeg yok", "ffmpeg bulunamadı. Ayarlar'dan yolunu gösterin.")
            return

        govde = os.path.splitext(yol)[0]
        secim = self.ses_bicim.currentIndex()
        sure = sure_saniye(yol, ffprobe) if ffprobe else None

        if secim == 0:
            codec = ""
            if ffprobe:
                bilgi = ffprobe_bilgi(yol, ffprobe)
                if bilgi:
                    codec = next((a.get("codec_name", "") for a in bilgi.get("streams", [])
                                  if a.get("codec_type") == "audio"), "")
            if not codec:
                QMessageBox.warning(self, "Ses yok", "Dosyada ses akışı bulunamadı.")
                return
            uzanti = KOPYA_UZANTI.get(codec, "wav" if codec.startswith("pcm") else "mka")
            cikti = benzersiz_yol(f"{govde}.{uzanti}")
            args = ["-i", yol, "-vn", "-c:a", "copy", cikti]
        else:
            bitrate = "192k" if secim == 1 else "320k"
            cikti = benzersiz_yol(f"{govde}.mp3")
            args = ["-i", yol, "-vn", "-c:a", "libmp3lame", "-b:a", bitrate, cikti]

        self.kuyruk_yon.ekle(FfmpegIsi(os.path.basename(cikti), ffmpeg, args, cikti, sure))
        self.kuyruga_git()

    # --- 4) Video birleştirme ---
    def _birlestirme_grubu(self) -> QGroupBox:
        grup = QGroupBox("Video Birleştir")
        duzen = QVBoxLayout(grup)

        self.b_liste = QListWidget()
        self.b_liste.setMaximumHeight(110)
        self.b_liste.setAcceptDrops(True)
        self.b_liste.dragEnterEvent = self._b_surukle
        self.b_liste.dragMoveEvent = self._b_surukle
        self.b_liste.dropEvent = self._b_birak
        duzen.addWidget(self.b_liste)

        satir = QHBoxLayout()
        ekle = QPushButton("Dosya Ekle…")
        ekle.clicked.connect(self._b_dosya_ekle)
        yukari = QPushButton("Yukarı")
        yukari.clicked.connect(lambda: self._b_tasi(-1))
        asagi = QPushButton("Aşağı")
        asagi.clicked.connect(lambda: self._b_tasi(1))
        cikar = QPushButton("Çıkar")
        cikar.clicked.connect(self._b_cikar)
        temizle = QPushButton("Temizle")
        temizle.clicked.connect(self.b_liste.clear)
        for d in (ekle, yukari, asagi, cikar, temizle):
            satir.addWidget(d)
        satir.addStretch()
        duzen.addLayout(satir)

        self.b_kayipsiz = QCheckBox("Kayıpsız birleştir (yeniden kodlama yok)")
        self.b_kayipsiz.setToolTip(
            "Tüm parçalar aynı codec, çözünürlük ve parametrelerdeyse (örn. bölünmüş tek kayıt) "
            "anında birleştirir. Kaynaklar farklıysa işareti kaldırın; parçalar ilk videonun "
            "çözünürlüğüne ve kare hızına uyumlanarak yeniden kodlanır.")
        duzen.addWidget(self.b_kayipsiz)

        birlestir = QPushButton("Kuyruğa Ekle")
        birlestir.clicked.connect(self._birlestir_ekle)
        duzen.addWidget(birlestir)
        return grup

    def _b_surukle(self, olay):
        if olay.mimeData().hasUrls():
            olay.acceptProposedAction()

    def _b_birak(self, olay):
        for url in olay.mimeData().urls():
            yol = url.toLocalFile()
            if yol and os.path.isfile(yol):
                self.b_liste.addItem(yol)
        olay.acceptProposedAction()

    def _b_dosya_ekle(self):
        dosyalar, _ = QFileDialog.getOpenFileNames(self, "Birleştirilecek dosyalar", "", MEDYA_FILTRE)
        for d in dosyalar:
            self.b_liste.addItem(d)

    def _b_cikar(self):
        for oge in self.b_liste.selectedItems():
            self.b_liste.takeItem(self.b_liste.row(oge))

    def _b_tasi(self, yon: int):
        satir = self.b_liste.currentRow()
        hedef = satir + yon
        if satir < 0 or not (0 <= hedef < self.b_liste.count()):
            return
        oge = self.b_liste.takeItem(satir)
        self.b_liste.insertItem(hedef, oge)
        self.b_liste.setCurrentRow(hedef)

    def _birlestir_ekle(self):
        dosyalar = [self.b_liste.item(i).text() for i in range(self.b_liste.count())]
        if len(dosyalar) < 2:
            QMessageBox.information(self, "Dosya eksik", "Birleştirme için en az iki dosya ekleyin.")
            return
        ffmpeg = self.ayarlar.ffmpeg()
        ffprobe = self.ayarlar.ffprobe()
        if not ffmpeg or not ffprobe:
            QMessageBox.warning(self, "Araç eksik", "ffmpeg/ffprobe bulunamadı. Ayarlar'dan yol gösterin.")
            return

        sureler = [sure_saniye(d, ffprobe) for d in dosyalar]
        toplam_sure = sum(sureler) if all(s is not None for s in sureler) else None
        ilk = dosyalar[0]
        govde = os.path.splitext(os.path.basename(ilk))[0]

        if self.b_kayipsiz.isChecked():
            uzanti = os.path.splitext(ilk)[1] or ".mp4"
            cikti = benzersiz_yol(os.path.join(os.path.dirname(ilk), f"{govde} (birleşik){uzanti}"))
            fd, liste_yolu = tempfile.mkstemp(suffix=".txt", prefix="mediaforge_concat_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for d in dosyalar:
                    duz = d.replace("\\", "/").replace("'", "'\\''")
                    f.write(f"file '{duz}'\n")
            args = ["-f", "concat", "-safe", "0", "-i", liste_yolu, "-c", "copy", cikti]
            is_ = FfmpegIsi(os.path.basename(cikti), ffmpeg, args, cikti, toplam_sure)
            is_.gecici_dosyalar.append(liste_yolu)
        else:
            cikti = benzersiz_yol(os.path.join(os.path.dirname(ilk), f"{govde} (birleşik).mp4"))
            is_ = self._yeniden_kodlamali_birlestirme(dosyalar, cikti, toplam_sure, ffmpeg, ffprobe)
            if is_ is None:
                return

        self.kuyruk_yon.ekle(is_)
        self.b_liste.clear()
        self.kuyruga_git()

    def _yeniden_kodlamali_birlestirme(self, dosyalar, cikti, toplam_sure,
                                       ffmpeg, ffprobe) -> FfmpegIsi | None:
        """Parçaları ilk videonun çözünürlük/fps değerine uyumlayıp concat filtresiyle birleştirir."""
        bilgiler = [ffprobe_bilgi(d, ffprobe) for d in dosyalar]
        if any(b is None for b in bilgiler):
            QMessageBox.warning(self, "Okunamadı", "Dosyalardan biri çözümlenemedi; günlük için tek tek deneyin.")
            return None

        def video_akisi(b):
            return next((a for a in b.get("streams", []) if a.get("codec_type") == "video"), None)

        ilk_video = video_akisi(bilgiler[0])
        if not ilk_video:
            QMessageBox.warning(self, "Video yok", "İlk dosyada video akışı bulunamadı.")
            return None
        genislik = int(ilk_video.get("width", 1920))
        yukseklik = int(ilk_video.get("height", 1080))
        fps = ilk_video.get("avg_frame_rate", "30")
        if not fps or fps.startswith("0"):
            fps = "30"

        # Ses: tüm parçalarda varsa taşınır, yoksa çıktı sessiz olur
        ses_var = all(any(a.get("codec_type") == "audio" for a in b.get("streams", []))
                      for b in bilgiler)

        args: list[str] = []
        for d in dosyalar:
            args += ["-i", d]
        parcalar, girisler = [], ""
        for i in range(len(dosyalar)):
            parcalar.append(
                f"[{i}:v]scale={genislik}:{yukseklik}:force_original_aspect_ratio=decrease,"
                f"pad={genislik}:{yukseklik}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{i}]")
            girisler += f"[v{i}]"
            if ses_var:
                parcalar.append(f"[{i}:a]aresample=48000[a{i}]")
                girisler += f"[a{i}]"
        parcalar.append(
            f"{girisler}concat=n={len(dosyalar)}:v=1:a={1 if ses_var else 0}"
            + ("[v][a]" if ses_var else "[v]"))

        args += ["-filter_complex", ";".join(parcalar), "-map", "[v]"]
        if ses_var:
            args += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
        args += ["-c:v", "libx264", "-crf", "20", "-preset", "medium",
                 "-movflags", "+faststart", cikti]
        return FfmpegIsi(os.path.basename(cikti), ffmpeg, args, cikti, toplam_sure)
