# ⚡ BoltDrop - Yüksek Hızlı Yerel Ağ (LAN) Veri Aktarım Platformu

> **90 GB veriyi 1 gün beklemek yerine 5-10 dakikada aktarın.**

BoltDrop; aynı yerel ağda (Wi-Fi veya Ethernet) bulunan cihazlar arasında internet kotası veya upload hız sınırlamalarına takılmadan, doğrudan **donanımın maksimum hızında (P2P)** dosya transferi yapmanızı sağlayan hafif ve modern bir platformdur.

---

## 🚀 Neden 1 Gün Süren İş 5-10 Dakikaya İniyor?

* **İnternet Upload Darboğazı Yok:** Geleneksel bulut veya mesajlaşma uygulamaları verinizi internete (genelde 10-20 Mbps upload hızına) yükler. 90 GB bu hızla **~24 saat (1 tam gün)** sürer.
* **Doğrudan P2P LAN İletimi:** BoltDrop veriyi modemin internet çıkışına göndermez; iki bilgisayar arasında yerel ağ üzerinden doğrudan akar.
* **Kernel Seviyesinde Sıfır Kopyalama (Zero-Copy Streaming):** 90 GB veri belleği (RAM) şişirmez, işletim sistemi çekirdeği üzerinden diskten doğrudan ağ kartına 16 MB'lık optimize parçalarla pompalanır.

### ⏱️ 90 GB Aktarım Süresi Karşılaştırması

| Bağlantı Türü | Ortalama Hız | 90 GB Tahmini Süre |
| :--- | :--- | :--- |
| **İnternet / Bulut (Standart VDSL/Fiber)** | ~1 MB/s (8-10 Mbps) | **~24 saat (1 Gün)** |
| **Standart Wi-Fi 5 (5 GHz)** | 35 – 50 MB/s | **~30 – 40 dakika** |
| **Gigabit Kablo (Cat5e / Cat6)** | 110 – 115 MB/s | **~12 – 14 dakika** |
| **Wi-Fi 6 / 2.5 Gbps Ethernet** | 180 – 250 MB/s | **~6 – 8 dakika** |

---

## 🛠️ Nasıl Çalıştırılır?

Hiçbir harici kütüphane veya paket kurmanıza gerek yoktur (sıfır bağımlılık). Sadece Python 3 yeterlidir.

### 🐧 Linux & macOS
Terminalden veya çift tıklayarak:
```bash
./start.sh
# veya
python3 app.py
```

### 🪟 Windows
Klasör içindeki `start.bat` dosyasına çift tıklayın veya CMD/PowerShell üzerinden:
```cmd
python app.py
```

---

## 💻 Kullanım Adımları

1. **İki bilgisayarı aynı Wi-Fi ağına bağlayın** (Veya en yüksek hız için iki bilgisayar arasına doğrudan bir Ethernet kablosu takın).
2. Her iki bilgisayarda da programı çalıştırın.
3. Tarayıcınızda açılan adrese gidin: `http://localhost:7890`
4. **"Ağdaki Cihazlar"** bölümünde arkadaşınızın bilgisayarı otomatik olarak görünecektir.
5. Göndermek istediğiniz dosyayı ekrandaki alana sürükleyip bırakın ve arkadaşınızın yanındaki **"⚡ Gönder"** butonuna basın.
6. Anlık aktarım hızı (MB/s) ve kalan süre canlı olarak akmaya başlayacaktır!

---

## ⚡ Canlı Hız Testi (Benchmark)

Sisteminizdeki transfer motorunu ve yerel soket hızını test etmek için:
```bash
python3 test_speed.py
```
*Test sonucunda sentetik veri aktarım hızı ve SHA-256 veri doğrulaması otomatik olarak kontrol edilir.*
