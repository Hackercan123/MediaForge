"""Kuyruk sekmesi: tüm indirme/dönüştürme işleri tek tabloda."""
from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from kuyruk import BITTI, CALISIYOR, HATA, Is


class SekmeKuyruk(QWidget):
    def __init__(self, kuyruk_yon):
        super().__init__()
        self.kuyruk_yon = kuyruk_yon
        self._baglananlar: set[int] = set()   # sinyali bağlanmış iş numaraları
        self._satirlar: dict[int, int] = {}   # is_no → satır no

        duzen = QVBoxLayout(self)

        self.tablo = QTableWidget(0, 4)
        self.tablo.setHorizontalHeaderLabels(["Tür", "Başlık", "İlerleme", "Durum"])
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setSelectionBehavior(QTableWidget.SelectRows)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        baslik = self.tablo.horizontalHeader()
        baslik.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        baslik.setSectionResizeMode(1, QHeaderView.Stretch)
        baslik.setSectionResizeMode(2, QHeaderView.Fixed)
        # Durum sütunu sabit: içeriğe göre boyutlanırsa hız yazısı her
        # güncellemede sütunu oynatıp titremeye yol açıyor.
        baslik.setSectionResizeMode(3, QHeaderView.Fixed)
        self.tablo.setColumnWidth(2, 160)
        self.tablo.setColumnWidth(3, 260)
        self.tablo.itemDoubleClicked.connect(lambda _o: self._gunluk_goster())
        duzen.addWidget(self.tablo)

        satir = QHBoxLayout()
        iptal = QPushButton("Seçileni İptal Et")
        iptal.clicked.connect(self._secileni_iptal)
        klasor = QPushButton("Klasörü Aç")
        klasor.clicked.connect(self._klasor_ac)
        gunluk = QPushButton("Günlüğü Göster")
        gunluk.clicked.connect(self._gunluk_goster)
        temizle = QPushButton("Bitenleri Temizle")
        temizle.clicked.connect(self.kuyruk_yon.temizle_bitenler)
        satir.addWidget(iptal)
        satir.addWidget(klasor)
        satir.addWidget(gunluk)
        satir.addStretch()
        satir.addWidget(temizle)
        duzen.addLayout(satir)

        kuyruk_yon.yapi_degisti.connect(self._tabloyu_kur)
        self._tabloyu_kur()

    # --- tablo kurulumu ---
    def _tabloyu_kur(self):
        isler = self.kuyruk_yon.isler
        self._satirlar = {is_.is_no: i for i, is_ in enumerate(isler)}
        self.tablo.setRowCount(len(isler))
        for i, is_ in enumerate(isler):
            self.tablo.setItem(i, 0, QTableWidgetItem(is_.tur_ad))
            self.tablo.setItem(i, 1, QTableWidgetItem(is_.baslik))
            cubuk = QProgressBar()
            cubuk.setTextVisible(True)
            self._cubuk_ayarla(cubuk, is_)
            self.tablo.setCellWidget(i, 2, cubuk)
            self.tablo.setItem(i, 3, QTableWidgetItem(self._durum_metni(is_)))
            if is_.is_no not in self._baglananlar:
                self._baglananlar.add(is_.is_no)
                is_.degisti.connect(lambda is_=is_: self._satir_guncelle(is_))
                is_.ilerleme.connect(lambda _y, is_=is_: self._cubuk_guncelle(is_))

    @staticmethod
    def _durum_metni(is_: Is) -> str:
        return f"{is_.durum} — {is_.detay}" if is_.detay else is_.durum

    @staticmethod
    def _cubuk_ayarla(cubuk: QProgressBar, is_: Is):
        if is_.yuzde < 0:
            if is_.durum == CALISIYOR:
                cubuk.setRange(0, 0)          # belirsiz (animasyonlu)
            else:
                cubuk.setRange(0, 100)
                cubuk.setValue(0)
        else:
            cubuk.setRange(0, 100)
            cubuk.setValue(is_.yuzde)

    def _satir_guncelle(self, is_: Is):
        satir = self._satirlar.get(is_.is_no)
        if satir is None or satir >= self.tablo.rowCount():
            return
        self.tablo.item(satir, 1).setText(is_.baslik)
        self.tablo.item(satir, 3).setText(self._durum_metni(is_))
        self._cubuk_guncelle(is_)

    def _cubuk_guncelle(self, is_: Is):
        satir = self._satirlar.get(is_.is_no)
        if satir is None:
            return
        cubuk = self.tablo.cellWidget(satir, 2)
        if cubuk:
            self._cubuk_ayarla(cubuk, is_)

    # --- düğmeler ---
    def _secili_is(self) -> Is | None:
        satir = self.tablo.currentRow()
        if 0 <= satir < len(self.kuyruk_yon.isler):
            return self.kuyruk_yon.isler[satir]
        return None

    def _secileni_iptal(self):
        is_ = self._secili_is()
        if is_:
            is_.iptal()

    def _klasor_ac(self):
        is_ = self._secili_is()
        if not is_:
            return
        if is_.durum == BITTI and is_.cikti_dosya and os.path.isfile(is_.cikti_dosya):
            os.startfile(os.path.dirname(is_.cikti_dosya))
        elif is_.cikti_klasor and os.path.isdir(is_.cikti_klasor):
            os.startfile(is_.cikti_klasor)

    def _gunluk_goster(self):
        is_ = self._secili_is()
        if not is_:
            return
        pencere = QDialog(self)
        pencere.setWindowTitle(f"Günlük — {is_.baslik}")
        pencere.resize(760, 420)
        v = QVBoxLayout(pencere)
        metin = QTextEdit()
        metin.setReadOnly(True)
        metin.setFontFamily("Consolas")
        metin.setPlainText("\n".join(is_.gunluk))
        if is_.durum == HATA:
            metin.moveCursor(metin.textCursor().MoveOperation.End)
        v.addWidget(metin)
        pencere.exec()
