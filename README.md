# MediaForge

HandBrake + YouTube indirici karışımı, Türkçe arayüzlü medya araç kutusu.
Arka planda **ffmpeg** ve **yt-dlp** çalıştırır. Araç arama sırası:
Ayarlar'daki özel yol → program yanındaki `bin\` klasörü → PATH.

## Portable dağıtım

`dist\` klasörü kendi başına taşınabilir paket:

```
dist\
  MediaForge.exe
  bin\
    ffmpeg.exe      (statik derleme)
    ffprobe.exe     (statik derleme)
    yt-dlp.exe      (bağımsız GitHub sürümü — pip başlatıcısı DEĞİL)
```

Klasörü olduğu gibi kopyala/zipleyip ver; kurulum gerektirmez. `paketle.bat`
bu klasörü `MediaForge-portable.zip` olarak sıkıştırır.

Araç güncelleme: pencerenin sağ üstündeki **⇩ Güncelle** düğmesi yt-dlp ve
ffmpeg sürümlerini denetler; yeni sürüm varsa `bin\` klasörüne indirir
(yt-dlp: resmî GitHub sürümü, ffmpeg: BtbN win64-gpl derlemesi).

## Kaynaktan çalıştırma / derleme

```
pip install -r requirements.txt
python MediaForge.py
```

`derle.bat` PyInstaller ile `dist\MediaForge.exe` üretir (`bin\` klasörüne dokunmaz).

## Sekmeler

- **İndir** — bağlantı yapıştır (her satıra bir adet), biçim seç (en yüksek kalite /
  1080p / 720p / MP3), oynatma listesi desteği, ses dosyalarına kapak ve üstveri gömme.
- **Dönüştür** — dosyaları sürükle-bırak, preset seç (H.264 / H.265 / AV1 / remux / MP3),
  CRF kalite kaydırıcısı, hız, çözünürlük ve FPS seçimi. Donanım kodlayıcılar açılışta
  sınanır; çalışanların presetleri otomatik eklenir: NVIDIA (NVENC), AMD (AMF), Intel (QSV) —
  H.264, H.265 ve destekleyen kartlarda AV1.
- **Araçlar** — medya bilgisi (ffprobe), kayıpsız/kare hassas video kesme, videodan ses çıkarma,
  video birleştirme (kayıpsız concat veya farklı kaynakları uyumlayan yeniden kodlama).
- **Kuyruk** — tüm işler tek tabloda: ilerleme çubuğu, hız, kalan süre, iptal, günlük
  (satıra çift tıklayınca ffmpeg/yt-dlp çıktısı).

## Notlar

- Ayarlar `ayarlar.json` dosyasında tutulur (program klasöründe).
- Aynı anda kaç indirme/dönüştürme koşacağı Ayarlar'dan değişir.
- Dönüştürme çıktıları kaynak klasöre `[MF]` ekiyle yazılır (Ayarlar'dan sabit klasör seçilebilir).
