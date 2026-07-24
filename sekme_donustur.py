"""Dönüştür sekmesi: toplu codec/kap dönüştürme (HandBrake usulü preset + kalite)."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QRadioButton, QSlider, QVBoxLayout, QWidget,
)

from araclar import benzersiz_yol, sure_saniye
from kuyruk import FfmpegIsi

MEDYA_FILTRE = ("Medya dosyaları (*.mp4 *.mkv *.avi *.mov *.webm *.ts *.m2ts *.flv *.wmv "
                "*.mpg *.mpeg *.3gp *.mp3 *.m4a *.wav *.flac *.ogg *.opus *.aac *.wma);;"
                "Tüm dosyalar (*.*)")

HIZ_SECENEKLERI = ["Hızlı", "Dengeli", "Yavaş (yüksek sıkıştırma)"]


def _gpu_presetleri(kodlayicilar: frozenset | set) -> list[dict]:
    """Makinede çalıştığı doğrulanan donanım kodlayıcıların presetleri."""
    tanimlar = {
        "h264_nvenc": {
            "ad": "H.264 (NVIDIA NVENC) — donanım hızlandırmalı",
            "crf": 23,
            "hiz": {"Hızlı": "p4", "Dengeli": "p5", "Yavaş (yüksek sıkıştırma)": "p7"},
            "v_args": lambda crf, hiz: ["-c:v", "h264_nvenc", "-preset", hiz,
                                        "-rc", "vbr", "-cq", str(crf), "-b:v", "0"],
        },
        "hevc_nvenc": {
            "ad": "H.265 (NVIDIA NVENC) — donanım hızlandırmalı",
            "crf": 27,
            "hiz": {"Hızlı": "p4", "Dengeli": "p5", "Yavaş (yüksek sıkıştırma)": "p7"},
            "v_args": lambda crf, hiz: ["-c:v", "hevc_nvenc", "-preset", hiz,
                                        "-rc", "vbr", "-cq", str(crf), "-b:v", "0"],
            "mp4_ek": ["-tag:v", "hvc1"],
        },
        "av1_nvenc": {
            "ad": "AV1 (NVIDIA NVENC) — donanım hızlandırmalı",
            "crf": 30,
            "hiz": {"Hızlı": "p4", "Dengeli": "p5", "Yavaş (yüksek sıkıştırma)": "p7"},
            "v_args": lambda crf, hiz: ["-c:v", "av1_nvenc", "-preset", hiz,
                                        "-rc", "vbr", "-cq", str(crf), "-b:v", "0"],
        },
        "h264_amf": {
            "ad": "H.264 (AMD AMF) — donanım hızlandırmalı",
            "crf": 23,
            "hiz": {"Hızlı": "speed", "Dengeli": "balanced", "Yavaş (yüksek sıkıştırma)": "quality"},
            "v_args": lambda crf, hiz: ["-c:v", "h264_amf", "-quality", hiz,
                                        "-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf)],
        },
        "hevc_amf": {
            "ad": "H.265 (AMD AMF) — donanım hızlandırmalı",
            "crf": 26,
            "hiz": {"Hızlı": "speed", "Dengeli": "balanced", "Yavaş (yüksek sıkıştırma)": "quality"},
            "v_args": lambda crf, hiz: ["-c:v", "hevc_amf", "-quality", hiz,
                                        "-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf)],
            "mp4_ek": ["-tag:v", "hvc1"],
        },
        "av1_amf": {
            "ad": "AV1 (AMD AMF) — donanım hızlandırmalı",
            "crf": 30,
            "hiz": {"Hızlı": "speed", "Dengeli": "balanced", "Yavaş (yüksek sıkıştırma)": "quality"},
            "v_args": lambda crf, hiz: ["-c:v", "av1_amf", "-quality", hiz,
                                        "-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf)],
        },
        "h264_qsv": {
            "ad": "H.264 (Intel QSV) — donanım hızlandırmalı",
            "crf": 23,
            "hiz": {"Hızlı": "veryfast", "Dengeli": "medium", "Yavaş (yüksek sıkıştırma)": "veryslow"},
            "v_args": lambda crf, hiz: ["-c:v", "h264_qsv", "-preset", hiz,
                                        "-global_quality", str(crf)],
        },
        "hevc_qsv": {
            "ad": "H.265 (Intel QSV) — donanım hızlandırmalı",
            "crf": 26,
            "hiz": {"Hızlı": "veryfast", "Dengeli": "medium", "Yavaş (yüksek sıkıştırma)": "veryslow"},
            "v_args": lambda crf, hiz: ["-c:v", "hevc_qsv", "-preset", hiz,
                                        "-global_quality", str(crf)],
            "mp4_ek": ["-tag:v", "hvc1"],
        },
        "av1_qsv": {
            "ad": "AV1 (Intel QSV) — donanım hızlandırmalı",
            "crf": 30,
            "hiz": {"Hızlı": "veryfast", "Dengeli": "medium", "Yavaş (yüksek sıkıştırma)": "veryslow"},
            "v_args": lambda crf, hiz: ["-c:v", "av1_qsv", "-preset", hiz,
                                        "-global_quality", str(crf)],
        },
    }
    presetler = []
    for kodlayici in ("h264_nvenc", "hevc_nvenc", "av1_nvenc",
                      "h264_amf", "hevc_amf", "av1_amf",
                      "h264_qsv", "hevc_qsv", "av1_qsv"):
        if kodlayici in kodlayicilar:
            p = dict(tanimlar[kodlayici])
            p.update({"tip": "video", "video": True, "kaplar": ["mp4", "mkv"]})
            presetler.append(p)
    return presetler


def _preset_listesi(kodlayicilar: frozenset | set = frozenset()) -> list[dict]:
    presetler = [
        {
            "ad": "H.264 (libx264) — geniş uyumluluk",
            "tip": "video",
            "crf": 22, "kaplar": ["mp4", "mkv", "mov"], "video": True,
            "hiz": {"Hızlı": "veryfast", "Dengeli": "medium", "Yavaş (yüksek sıkıştırma)": "slow"},
            "v_args": lambda crf, hiz: ["-c:v", "libx264", "-crf", str(crf), "-preset", hiz],
        },
        {
            "ad": "H.265 (libx265) — yüksek sıkıştırma",
            "tip": "video",
            "crf": 26, "kaplar": ["mp4", "mkv"], "video": True,
            "hiz": {"Hızlı": "fast", "Dengeli": "medium", "Yavaş (yüksek sıkıştırma)": "slow"},
            "v_args": lambda crf, hiz: ["-c:v", "libx265", "-crf", str(crf), "-preset", hiz],
            "mp4_ek": ["-tag:v", "hvc1"],
        },
        {
            "ad": "AV1 (SVT-AV1) — en yüksek sıkıştırma",
            "tip": "video",
            "crf": 30, "kaplar": ["mkv", "mp4", "webm"], "video": True,
            "hiz": {"Hızlı": "8", "Dengeli": "6", "Yavaş (yüksek sıkıştırma)": "4"},
            "v_args": lambda crf, hiz: ["-c:v", "libsvtav1", "-crf", str(crf), "-preset", hiz],
        },
    ]
    presetler += _gpu_presetleri(kodlayicilar)
    presetler += [
        {
            "ad": "Remux — yeniden kodlama olmadan format değişimi",
            "tip": "remux",
            "crf": None, "kaplar": ["mp4", "mkv", "mov"], "video": False,
        },
        {
            "ad": "Ses çıkar — MP3",
            "tip": "mp3",
            "crf": None, "kaplar": ["mp3"], "video": False,
        },
    ]
    return presetler


class SekmeDonustur(QWidget):
    def __init__(self, kuyruk_yon, ayarlar, kuyruga_git):
        super().__init__()
        self.kuyruk_yon = kuyruk_yon
        self.ayarlar = ayarlar
        self.kuyruga_git = kuyruga_git
        self.presetler = _preset_listesi()

        duzen = QVBoxLayout(self)
        duzen.setSpacing(8)

        duzen.addWidget(QLabel("Dosyalar (sürükle-bırak desteklenir):"))
        self.liste = QListWidget()
        self.liste.setSelectionMode(QListWidget.ExtendedSelection)
        self.liste.setAcceptDrops(True)
        self.liste.dragEnterEvent = self._surukle_gir
        self.liste.dragMoveEvent = self._surukle_gir
        self.liste.dropEvent = self._birak
        duzen.addWidget(self.liste, 1)

        satir_d = QHBoxLayout()
        ekle = QPushButton("Dosya Ekle…")
        ekle.clicked.connect(self._dosya_ekle)
        cikar = QPushButton("Seçileni Çıkar")
        cikar.clicked.connect(self._secileni_cikar)
        temizle = QPushButton("Listeyi Temizle")
        temizle.clicked.connect(self.liste.clear)
        satir_d.addWidget(ekle)
        satir_d.addWidget(cikar)
        satir_d.addWidget(temizle)
        satir_d.addStretch()
        duzen.addLayout(satir_d)

        satir_p = QHBoxLayout()
        satir_p.addWidget(QLabel("Preset:"))
        self.preset_kutu = QComboBox()
        self.preset_kutu.addItems([p["ad"] for p in self.presetler])
        self.preset_kutu.currentIndexChanged.connect(self._preset_degisti)
        satir_p.addWidget(self.preset_kutu, 1)
        satir_p.addWidget(QLabel("Format:"))
        self.kap_kutu = QComboBox()
        satir_p.addWidget(self.kap_kutu)
        duzen.addLayout(satir_p)

        self.crf_etiket = QLabel()
        duzen.addWidget(self.crf_etiket)

        satir_crf = QHBoxLayout()
        self.crf_sol = QLabel("Yüksek kalite")
        self.crf_sag = QLabel("Küçük dosya")
        for uc in (self.crf_sol, self.crf_sag):
            uc.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        self.crf = QSlider(Qt.Horizontal)
        self.crf.setRange(14, 40)
        self.crf.valueChanged.connect(self._crf_etiketle)
        satir_crf.addWidget(self.crf_sol)
        satir_crf.addWidget(self.crf, 1)
        satir_crf.addWidget(self.crf_sag)
        duzen.addLayout(satir_crf)

        satir_k = QHBoxLayout()
        satir_k.addWidget(QLabel("Hız:"))
        self.hiz_kutu = QComboBox()
        self.hiz_kutu.addItems(HIZ_SECENEKLERI)
        self.hiz_kutu.setCurrentIndex(1)
        satir_k.addWidget(self.hiz_kutu)
        satir_k.addWidget(QLabel("Çözünürlük:"))
        self.cozunurluk = QComboBox()
        self.cozunurluk.addItems(["Orijinal", "1080p", "720p", "480p"])
        satir_k.addWidget(self.cozunurluk)
        satir_k.addWidget(QLabel("FPS:"))
        self.fps_kutu = QComboBox()
        self.fps_kutu.addItems(["Orijinal", "60", "30", "25", "24"])
        self.fps_kutu.setToolTip("Çıktının kare hızı; Orijinal seçiliyken değiştirilmez.")
        satir_k.addWidget(self.fps_kutu)
        duzen.addLayout(satir_k)

        satir_c = QHBoxLayout()
        self.ayni_klasor = QRadioButton("Kaynak klasörüne kaydet ('[MF]' ekiyle)")
        self.baska_klasor = QRadioButton("Şu klasöre:")
        if self.ayarlar["donusturme_ayni_klasore"]:
            self.ayni_klasor.setChecked(True)
        else:
            self.baska_klasor.setChecked(True)
        self.cikti_kutusu = QLineEdit(self.ayarlar["donusturme_klasoru"])
        cikti_sec = QPushButton("Seç…")
        cikti_sec.clicked.connect(self._cikti_sec)
        satir_c.addWidget(self.ayni_klasor)
        satir_c.addWidget(self.baska_klasor)
        satir_c.addWidget(self.cikti_kutusu, 1)
        satir_c.addWidget(cikti_sec)
        duzen.addLayout(satir_c)

        self.baslat_dugme = QPushButton("Kuyruğa Ekle  ▶")
        self.baslat_dugme.setMinimumHeight(36)
        self.baslat_dugme.clicked.connect(self._kuyruga_ekle)
        duzen.addWidget(self.baslat_dugme)

        self._preset_degisti(0)

    # --- donanım kodlayıcı sondası bitince ana pencere çağırır ---
    def donanim_etkinlestir(self, kodlayicilar: set[str]):
        secili_ad = self.preset_kutu.currentText()
        self.presetler = _preset_listesi(kodlayicilar)
        adlar = [p["ad"] for p in self.presetler]
        self.preset_kutu.blockSignals(True)
        self.preset_kutu.clear()
        self.preset_kutu.addItems(adlar)
        # Seçim ada göre korunur; indeks GPU eklemeleriyle kayabilir
        indeks = adlar.index(secili_ad) if secili_ad in adlar else 0
        self.preset_kutu.setCurrentIndex(indeks)
        self.preset_kutu.blockSignals(False)
        self._preset_degisti(indeks)

    # --- sürükle-bırak ---
    def _surukle_gir(self, olay):
        if olay.mimeData().hasUrls():
            olay.acceptProposedAction()

    def _birak(self, olay):
        for url in olay.mimeData().urls():
            yol = url.toLocalFile()
            if yol and os.path.isfile(yol):
                self._tekil_ekle(yol)
        olay.acceptProposedAction()

    def _tekil_ekle(self, yol: str):
        mevcut = [self.liste.item(i).text() for i in range(self.liste.count())]
        if yol not in mevcut:
            self.liste.addItem(yol)

    def _dosya_ekle(self):
        dosyalar, _ = QFileDialog.getOpenFileNames(self, "Dosya seç", "", MEDYA_FILTRE)
        for d in dosyalar:
            self._tekil_ekle(d)

    def _secileni_cikar(self):
        for oge in self.liste.selectedItems():
            self.liste.takeItem(self.liste.row(oge))

    def _cikti_sec(self):
        yol = QFileDialog.getExistingDirectory(self, "Çıktı klasörü", self.cikti_kutusu.text())
        if yol:
            self.cikti_kutusu.setText(yol)
            self.baska_klasor.setChecked(True)

    # --- preset/kalite arayüzü ---
    def _preset_degisti(self, indeks: int):
        p = self.presetler[indeks]
        self.kap_kutu.clear()
        self.kap_kutu.addItems(p["kaplar"])
        video = p.get("video", False)
        for w in (self.crf, self.crf_etiket, self.crf_sol, self.crf_sag,
                  self.hiz_kutu, self.cozunurluk, self.fps_kutu):
            w.setEnabled(video)
        if p.get("crf") is not None:
            self.crf.setValue(p["crf"])
        self._crf_etiketle(self.crf.value())

    def _crf_etiketle(self, deger: int):
        # Açıklama, seçili presetin önerilen değerine uzaklığa göre verilir;
        # böylece codec'ler arası ölçek farkı (x264 22 ≈ x265 26 ≈ AV1 30) sorun olmaz.
        varsayilan = self.presetler[self.preset_kutu.currentIndex()].get("crf")
        aciklama = ""
        if varsayilan is not None:
            fark = deger - varsayilan
            if fark <= -6:
                aciklama = "görsel olarak kayıpsıza yakın, dosya çok büyür"
            elif fark <= -2:
                aciklama = "yüksek kalite, daha büyük dosya"
            elif fark <= 1:
                aciklama = "önerilen denge"
            elif fark <= 5:
                aciklama = "daha küçük dosya, hafif kalite kaybı"
            else:
                aciklama = "en küçük dosya, belirgin kalite kaybı"
        self.crf_etiket.setText(f"Kalite (CRF): {deger}" + (f"  —  {aciklama}" if aciklama else ""))
        self.crf.setToolTip(
            "CRF (Constant Rate Factor): kodlayıcının kalite hedefi.\n"
            "Sola çekmek kaliteyi ve dosya boyutunu artırır, sağa çekmek dosyayı küçültür.\n"
            "Önerilen değer preset seçildiğinde kendiliğinden ayarlanır.")

    # --- iş üretimi ---
    def _kuyruga_ekle(self):
        ffmpeg = self.ayarlar.ffmpeg()
        if not ffmpeg:
            QMessageBox.warning(self, "ffmpeg yok",
                                "ffmpeg bulunamadı. Ayarlar'dan yolunu gösterin.")
            return
        dosyalar = [self.liste.item(i).text() for i in range(self.liste.count())]
        if not dosyalar:
            QMessageBox.information(self, "Dosya yok", "Önce dönüştürülecek dosyaları ekleyin.")
            return
        if self.baska_klasor.isChecked() and not os.path.isdir(self.cikti_kutusu.text().strip()):
            QMessageBox.warning(self, "Klasör yok", "Geçerli bir çıktı klasörü seçin.")
            return

        a = self.ayarlar
        a["donusturme_ayni_klasore"] = self.ayni_klasor.isChecked()
        a["donusturme_klasoru"] = self.cikti_kutusu.text().strip()
        a.kaydet()

        p = self.presetler[self.preset_kutu.currentIndex()]
        kap = self.kap_kutu.currentText()
        ffprobe = a.ffprobe()

        for dosya in dosyalar:
            govde = os.path.splitext(os.path.basename(dosya))[0]
            if self.ayni_klasor.isChecked():
                hedef_klasor = os.path.dirname(dosya)
                cikti = os.path.join(hedef_klasor, f"{govde} [MF].{kap}")
            else:
                cikti = os.path.join(self.cikti_kutusu.text().strip(), f"{govde}.{kap}")
            if os.path.abspath(cikti) == os.path.abspath(dosya):
                cikti = os.path.join(os.path.dirname(dosya), f"{govde} [MF].{kap}")
            cikti = benzersiz_yol(cikti)

            args = self._args_uret(p, dosya, cikti, kap)
            sure = sure_saniye(dosya, ffprobe) if ffprobe else None
            self.kuyruk_yon.ekle(FfmpegIsi(os.path.basename(cikti), ffmpeg, args, cikti, sure))

        self.liste.clear()
        self.kuyruga_git()

    def _args_uret(self, p: dict, girdi: str, cikti: str, kap: str) -> list[str]:
        args = ["-i", girdi]

        if p["tip"] == "remux":
            # remux: mkv hedefinde tüm akışları taşı, mp4/mov'da varsayılan seçim
            if kap == "mkv":
                args += ["-map", "0", "-c", "copy"]
            else:
                args += ["-c", "copy"]
        elif p["tip"] == "mp3":
            args += ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]
        else:
            hiz = p["hiz"][self.hiz_kutu.currentText()]
            args += p["v_args"](self.crf.value(), hiz)
            if kap == "mp4" and p.get("mp4_ek"):
                args += p["mp4_ek"]
            secim = self.cozunurluk.currentText()
            if secim != "Orijinal":
                args += ["-vf", f"scale=-2:'min({secim[:-1]},ih)'"]
            fps = self.fps_kutu.currentText()
            if fps != "Orijinal":
                args += ["-r", fps]
            # ses: mp4/mov → aac, mkv/webm → opus
            if kap in ("mp4", "mov"):
                args += ["-c:a", "aac", "-b:a", "192k"]
            else:
                args += ["-c:a", "libopus", "-b:a", "128k"]

        if kap in ("mp4", "mov"):
            args += ["-movflags", "+faststart"]
        args.append(cikti)
        return args
