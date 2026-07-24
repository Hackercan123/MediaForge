"""İş (indirme / ffmpeg) sınıfları ve kuyruk yöneticisi."""
from __future__ import annotations

import collections
import itertools
import os
import re
import time

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from araclar import insan_zaman

BEKLIYOR = "Bekliyor"
CALISIYOR = "Çalışıyor"
BITTI = "Bitti"
HATA = "Hata"
IPTAL = "İptal"

AKTIF = (BEKLIYOR, CALISIYOR)


class Is(QObject):
    """Tek bir kuyruk işi. Alt sınıflar komut() ve satir_isle() tanımlar."""

    ilerleme = Signal(int)      # 0-100, -1 = belirsiz
    degisti = Signal()          # başlık/durum/detay metni değişti
    bitti_sinyali = Signal(object)

    tur = "genel"
    tur_ad = "İş"
    _sayac = itertools.count()

    def __init__(self, baslik: str):
        super().__init__()
        self.is_no = next(Is._sayac)   # tablo eşlemesi için kalıcı kimlik
        self.baslik = baslik
        self.durum = BEKLIYOR
        self.detay = ""
        self.yuzde = -1
        self.gunluk: collections.deque[str] = collections.deque(maxlen=400)
        self.surec: QProcess | None = None
        self.cikti_dosya = ""       # bittiğinde açılacak dosya/klasör için
        self.cikti_klasor = ""
        self._iptal_istendi = False
        self._tampon_out = ""
        self._tampon_err = ""
        self._son_detay_zamani = 0.0

    def _detay_yay(self):
        """İlerleme kaynaklı detay güncellemelerini en çok ~3/sn'ye sınırlar
        (yt-dlp/ffmpeg çok sık satır basınca arayüz yazısı titriyor)."""
        simdi = time.monotonic()
        if simdi - self._son_detay_zamani >= 0.3:
            self._son_detay_zamani = simdi
            self.degisti.emit()

    # --- alt sınıflar ---
    def komut(self) -> list[str]:
        raise NotImplementedError

    def satir_isle(self, satir: str, hata_kanali: bool):
        pass

    def iptal_temizligi(self):
        pass

    def bitis_temizligi(self):
        """Her sonlanmada (başarı/hata/iptal) çağrılır."""
        pass

    # --- çalıştırma ---
    def baslat(self):
        cmd = self.komut()
        self.gunluk.append("$ " + " ".join(cmd))
        self.surec = QProcess(self)
        ortam = QProcessEnvironment.systemEnvironment()
        ortam.insert("PYTHONIOENCODING", "utf-8")
        ortam.insert("PYTHONUTF8", "1")
        self.surec.setProcessEnvironment(ortam)
        self.surec.readyReadStandardOutput.connect(self._oku_out)
        self.surec.readyReadStandardError.connect(self._oku_err)
        self.surec.finished.connect(self._sonlandi)
        self.surec.errorOccurred.connect(self._surec_hatasi)
        self.durum = CALISIYOR
        self.detay = "Başlatıldı"
        self.degisti.emit()
        self.surec.setProgram(cmd[0])
        self.surec.setArguments(cmd[1:])
        self.surec.start()

    def iptal(self):
        self._iptal_istendi = True
        if self.surec and self.surec.state() != QProcess.NotRunning:
            self.surec.kill()
        elif self.durum == BEKLIYOR:
            self.durum = IPTAL
            self.detay = ""
            self.degisti.emit()
            self.bitti_sinyali.emit(self)

    # --- iç işleyiş ---
    def _oku_out(self):
        self._tampon_out = self._dagit(
            self._tampon_out + bytes(self.surec.readAllStandardOutput()).decode("utf-8", "replace"),
            False,
        )

    def _oku_err(self):
        self._tampon_err = self._dagit(
            self._tampon_err + bytes(self.surec.readAllStandardError()).decode("utf-8", "replace"),
            True,
        )

    def _dagit(self, metin: str, hata_kanali: bool) -> str:
        satirlar = re.split(r"[\r\n]", metin)
        kalan = satirlar.pop()  # son parça henüz tamamlanmamış olabilir
        for satir in satirlar:
            satir = satir.strip()
            if satir:
                self.gunluk.append(satir)
                self.satir_isle(satir, hata_kanali)
        return kalan

    def _surec_hatasi(self, hata):
        if hata == QProcess.FailedToStart:
            self.durum = HATA
            self.detay = "Program başlatılamadı — Ayarlar'dan yolu denetleyin"
            self.bitis_temizligi()
            self.degisti.emit()
            self.bitti_sinyali.emit(self)

    def _sonlandi(self, cikis_kodu: int, _durum):
        if self._iptal_istendi:
            self.durum = IPTAL
            self.detay = ""
            self.iptal_temizligi()
        elif cikis_kodu == 0:
            self.durum = BITTI
            self.yuzde = 100
            self.detay = "Tamamlandı"
            self.ilerleme.emit(100)
        else:
            self.durum = HATA
            hata_satiri = next(
                (s for s in reversed(self.gunluk) if "error" in s.lower() or "invalid" in s.lower()),
                None,
            )
            self.detay = (hata_satiri or f"Çıkış kodu {cikis_kodu}")[:160]
        self.bitis_temizligi()
        self.degisti.emit()
        self.bitti_sinyali.emit(self)


class FfmpegIsi(Is):
    """`-progress pipe:1` çıktısından yüzde/hız/kalan süre çıkarır."""

    tur = "ffmpeg"
    tur_ad = "Dönüştürme"

    def __init__(self, baslik: str, ffmpeg: str, args: list[str],
                 cikti_dosya: str, sure: float | None):
        super().__init__(baslik)
        self.ffmpeg = ffmpeg
        self.args = args
        self.cikti_dosya = cikti_dosya
        self.cikti_klasor = os.path.dirname(cikti_dosya)
        self.sure = sure
        self.gecici_dosyalar: list[str] = []   # iş bitince silinecekler (concat listesi vb.)
        self._hiz = 0.0

    def komut(self) -> list[str]:
        return [self.ffmpeg, "-hide_banner", "-y",
                "-progress", "pipe:1", "-nostats", *self.args]

    def satir_isle(self, satir: str, hata_kanali: bool):
        if hata_kanali or "=" not in satir:
            return
        anahtar, _, deger = satir.partition("=")
        if anahtar in ("out_time_us", "out_time_ms"):
            try:
                gecen = int(deger) / 1_000_000
            except ValueError:
                return
            if self.sure and self.sure > 0:
                self.yuzde = min(99, int(gecen / self.sure * 100))
                self.ilerleme.emit(self.yuzde)
                parcalar = []
                if self._hiz > 0:
                    parcalar.append(f"{self._hiz:.1f}x")
                    parcalar.append("kalan " + insan_zaman((self.sure - gecen) / self._hiz))
                self.detay = " • ".join(parcalar)
            else:
                self.detay = "İşlenen: " + insan_zaman(gecen)
            self._detay_yay()
        elif anahtar == "speed":
            esle = re.match(r"([\d.]+)x", deger.strip())
            if esle:
                self._hiz = float(esle.group(1))

    def iptal_temizligi(self):
        # Yarım kalan çıktıyı sil
        try:
            if self.cikti_dosya and os.path.isfile(self.cikti_dosya):
                os.remove(self.cikti_dosya)
        except OSError:
            pass

    def bitis_temizligi(self):
        for yol in self.gecici_dosyalar:
            try:
                if os.path.isfile(yol):
                    os.remove(yol)
            except OSError:
                pass


class IndirmeIsi(Is):
    """yt-dlp süreci; --progress-template ile yüzde/hız/ETA ayrıştırılır."""

    tur = "indirme"
    tur_ad = "İndirme"

    SABLON = "download:MFP|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s"

    def __init__(self, url: str, klasor: str, secenek_args: list[str],
                 ytdlp: str, ffmpeg: str | None):
        super().__init__(url)
        self.url = url
        self.klasor = klasor
        self.cikti_klasor = klasor
        self.secenek_args = secenek_args
        self.ytdlp = ytdlp
        self.ffmpeg_klasoru = os.path.dirname(ffmpeg) if ffmpeg else ""
        self._oge = ""

    def komut(self) -> list[str]:
        cmd = [self.ytdlp, "--newline", "--color", "no_color",
               "--progress-template", self.SABLON,
               "--windows-filenames",
               "-P", self.klasor, "-o", "%(title)s.%(ext)s",
               *self.secenek_args]
        if self.ffmpeg_klasoru:
            cmd += ["--ffmpeg-location", self.ffmpeg_klasoru]
        cmd.append(self.url)
        return cmd

    def satir_isle(self, satir: str, hata_kanali: bool):
        if satir.startswith("MFP|"):
            parcalar = satir.split("|")
            if len(parcalar) >= 4:
                try:
                    self.yuzde = int(float(parcalar[1].strip().rstrip("%")))
                    self.ilerleme.emit(self.yuzde)
                except ValueError:
                    pass
                hiz, eta = parcalar[2].strip(), parcalar[3].strip()
                detaylar = []
                if hiz and hiz not in ("NA", "Unknown"):
                    detaylar.append(hiz)
                if eta and eta not in ("NA", "Unknown"):
                    detaylar.append(f"kalan {eta}")
                self.detay = self._oge + " • ".join(detaylar)
                self._detay_yay()
            return

        esle = re.search(r"\[download\] Downloading item (\d+) of (\d+)", satir)
        if esle:
            self._oge = f"Parça {esle.group(1)}/{esle.group(2)} • "
            return
        if satir.startswith("[download] Destination:"):
            self.baslik = os.path.basename(satir.split("Destination:", 1)[1].strip())
            self.degisti.emit()
        elif satir.startswith("[Merger]"):
            self.detay = self._oge + "Görüntü ve ses birleştiriliyor…"
            self.degisti.emit()
        elif satir.startswith("[ExtractAudio]"):
            self.detay = self._oge + "Ses dönüştürülüyor…"
            self.degisti.emit()
        elif satir.startswith(("[EmbedThumbnail]", "[Metadata]")):
            self.detay = self._oge + "Etiketler işleniyor…"
            self.degisti.emit()


class KuyrukYoneticisi(QObject):
    """Bekleyen işleri tür başına eşzamanlılık sınırıyla çalıştırır."""

    yapi_degisti = Signal()   # listeye ekleme/çıkarma oldu

    def __init__(self, ayarlar):
        super().__init__()
        self.ayarlar = ayarlar
        self.isler: list[Is] = []

    def ekle(self, is_: Is):
        self.isler.append(is_)
        is_.bitti_sinyali.connect(self._is_bitti)
        self.yapi_degisti.emit()
        self.pompala()

    def pompala(self):
        limitler = {
            "indirme": int(self.ayarlar["es_zamanli_indirme"]),
            "ffmpeg": int(self.ayarlar["es_zamanli_ffmpeg"]),
        }
        for tur, limit in limitler.items():
            kosan = sum(1 for i in self.isler if i.tur == tur and i.durum == CALISIYOR)
            for is_ in self.isler:
                if kosan >= limit:
                    break
                if is_.tur == tur and is_.durum == BEKLIYOR and not is_._iptal_istendi:
                    is_.baslat()
                    if is_.durum == CALISIYOR:
                        kosan += 1

    def _is_bitti(self, _is):
        self.pompala()

    def aktif_sayisi(self) -> int:
        return sum(1 for i in self.isler if i.durum in AKTIF)

    def temizle_bitenler(self):
        self.isler = [i for i in self.isler if i.durum in AKTIF]
        self.yapi_degisti.emit()

    def hepsini_iptal_et(self):
        for is_ in self.isler:
            if is_.durum in AKTIF:
                is_.iptal()
