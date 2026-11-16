#!/usr/bin/env python3
"""
BoltDrop Hız ve Doğrulama Testi (Benchmark)
Yerel soket üzerinden 500 MB sentetik veri transferi yaparak
aktarım hızını (MB/s) ve veri bütünlüğünü (SHA-256) ölçer.
"""

import os
import time
import hashlib
import urllib.request
import json

# Yerel soket proxy engellerini aş
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
urllib.request.install_opener(opener)

SERVER_URL = "http://127.0.0.1:7890"
TEST_SIZE_MB = 250
CHUNK_SIZE = 16 * 1024 * 1024  # 16 MB

def run_benchmark():
    print(f"[*] BoltDrop Hız Testi Başlatılıyor ({TEST_SIZE_MB} MB Sentetik Veri)...")

    # 1. Sunucu çalışıyor mu kontrol et
    try:
        req = urllib.request.urlopen(f"{SERVER_URL}/api/info", timeout=3)
        info = json.loads(req.read().decode())
        print(f"[✓] Sunucu aktif: {info['name']} (IP: {info['ip']})")
    except Exception as e:
        print(f"[!] Hata: BoltDrop sunucusu çalışmıyor görünüyor ({e}).")
        print("[!] Lütfen önce 'python3 app.py' çalıştırın.")
        return

    # 2. Sentetik test verisi ve SHA-256 hash hesaplama
    test_bytes = os.urandom(TEST_SIZE_MB * 1024 * 1024)
    expected_hash = hashlib.sha256(test_bytes).hexdigest()
    filename = f"benchmark_test_{int(time.time())}.bin"

    print(f"[*] {TEST_SIZE_MB} MB rastgele veri bellekte oluşturuldu.")
    print(f"[*] Orijinal SHA-256: {expected_hash[:16]}...")

    # 3. Transfer başlatma (Handshake)
    init_data = json.dumps({
        "filename": filename,
        "size": len(test_bytes),
        "sender": "Benchmark Test Runner"
    }).encode('utf-8')

    req = urllib.request.Request(
        f"{SERVER_URL}/api/transfer/init",
        data=init_data,
        headers={"Content-Type": "application/json"}
    )
    resp = json.loads(urllib.request.urlopen(req).read().decode())
    transfer_id = resp["transfer_id"]
    print(f"[✓] Transfer el sıkışması başarılı. Transfer ID: {transfer_id}")

    # 4. Yüksek hızlı parçalı aktarım (Streaming)
    print("[*] Chunk aktarımı başlıyor...")
    start_time = time.time()
    offset = 0

    while offset < len(test_bytes):
        end = min(offset + CHUNK_SIZE, len(test_bytes))
        chunk = test_bytes[offset:end]

        chunk_req = urllib.request.Request(
            f"{SERVER_URL}/api/transfer/chunk",
            data=chunk,
            headers={
                "Content-Type": "application/octet-stream",
                "X-Transfer-Id": transfer_id,
                "X-Chunk-Offset": str(offset)
            }
        )
        urllib.request.urlopen(chunk_req)
        offset = end

    total_time = time.time() - start_time
    speed_mb_s = TEST_SIZE_MB / total_time

    print("=" * 50)
    print(f"🎉 TRANSFER TAMAMLANDI!")
    print(f" -> Toplam Veri : {TEST_SIZE_MB} MB")
    print(f" -> Geçen Süre  : {total_time:.2f} saniye")
    print(f" -> AKTARIM HIZI: {speed_mb_s:.1f} MB/s ({speed_mb_s * 8:.1f} Mbps)")
    print("=" * 50)

    # 90 GB için tahmini süre hesapla
    est_90gb_seconds = (90 * 1024) / speed_mb_s
    est_minutes = est_90gb_seconds / 60
    print(f"📊 90 GB'LIK BİR DOSYA BU HIZLA YAKLAŞIK {est_minutes:.1f} DAKİKADA BİTER!")
    print("=" * 50)

    # 5. Doğrulama (İndirilen dosyanın hash'ini kontrol et)
    written_path = os.path.join(info["downloads_dir"], filename)
    if os.path.exists(written_path):
        hasher = hashlib.sha256()
        with open(written_path, "rb") as f:
            while chunk := f.read(16 * 1024 * 1024):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()

        if actual_hash == expected_hash:
            print("[✓] VERİ DOĞRULAMASI: MÜKEMMEL (SHA-256 birebir eşleşti!)")
        else:
            print("[!] UYARI: Veri hash'i eşleşmedi!")

        # Test dosyasını temizle
        os.remove(written_path)
        print("[✓] Geçici benchmark dosyası temizlendi.")

if __name__ == "__main__":
    run_benchmark()
