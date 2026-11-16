#!/usr/bin/env python3
"""
BoltDrop - Yüksek Hızlı Yerel Ağ (LAN) Veri Aktarım Platformu
Aynı ağdaki cihazlar arasında gigabit hızında doğrudan P2P dosya transferi.
"""

import os
import sys
import json
import time
import socket
import select
import random
import string
import platform
import threading
from urllib.parse import urlparse, parse_qs, unquote
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

# Konfigürasyon
DEFAULT_PORT = 7890
BROADCAST_PORT = 54545
CHUNK_SIZE = 16 * 1024 * 1024  # 16 MB chunking for optimal LAN throughput
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Benzersiz cihaz kimliği ve adı
DEVICE_ID = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
HOSTNAME = socket.gethostname()

def get_friendly_name():
    os_name = platform.system()
    return f"{HOSTNAME} ({os_name})"

DEVICE_NAME = get_friendly_name()

def get_lan_ip():
    """Cihazın yerel ağdaki (LAN) gerçek IP adresini tespit eder."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Dışarıya paket göndermez, sadece yönlendirilen arayüz IP'sini öğrenir
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
    finally:
        s.close()
    return ip

CURRENT_LAN_IP = get_lan_ip()

# Paylaşılan durumlar (Thread-Safe)
state_lock = threading.Lock()
peers = {}  # { peer_id: { name, ip, port, last_seen } }
incoming_transfers = {}  # { transfer_id: { filename, size, received_bytes, sender, status, file_path, start_time } }
shared_files = {}  # { share_id: { filename, path, size, mime_type } }

def prune_peers():
    """6 saniyeden uzun süredir sinyal vermeyen cihazları listeden kaldırır."""
    while True:
        time.sleep(3)
        now = time.time()
        with state_lock:
            stale = [pid for pid, p in peers.items() if now - p['last_seen'] > 7]
            for pid in stale:
                del peers[pid]

def udp_broadcast_sender(http_port):
    """Her 2 saniyede bir yerel ağa 'Ben buradayım' anonsu yapar."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    payload = json.dumps({
        "type": "boltdrop_beacon",
        "id": DEVICE_ID,
        "name": DEVICE_NAME,
        "ip": CURRENT_LAN_IP,
        "port": http_port
    }).encode('utf-8')
    
    while True:
        try:
            sock.sendto(payload, ('255.255.255.255', BROADCAST_PORT))
        except Exception:
            pass
        time.sleep(2)

def udp_broadcast_listener():
    """Ağdaki diğer BoltDrop cihazlarının anonslarını dinler."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, 'SO_REUSEPORT'):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except Exception:
                pass
        sock.bind(('0.0.0.0', BROADCAST_PORT))
    except Exception as e:
        print(f"[!] UDP dinleyici başlatılamadı: {e}")
        return

    while True:
        try:
            data, addr = sock.recvfrom(2048)
            msg = json.loads(data.decode('utf-8'))
            if msg.get("type") == "boltdrop_beacon" and msg.get("id") != DEVICE_ID:
                peer_id = msg["id"]
                with state_lock:
                    peers[peer_id] = {
                        "id": peer_id,
                        "name": msg["name"],
                        "ip": addr[0] if msg.get("ip") in ("127.0.0.1", "") else msg.get("ip", addr[0]),
                        "port": msg["port"],
                        "last_seen": time.time()
                    }
        except Exception:
            pass


class BoltDropHandler(SimpleHTTPRequestHandler):
    """Yüksek hızlı veri transferi ve API yöneticisi"""

    def log_message(self, format, *args):
        # Konsolu gereksiz log kalabalığıyla doldurmamak için sessize alıyoruz
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Content-Range, X-Transfer-Id, X-Chunk-Index')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Content-Range, X-Transfer-Id, X-Chunk-Index')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. API: Cihaz Bilgisi
        if path == "/api/info":
            self.send_json({
                "id": DEVICE_ID,
                "name": DEVICE_NAME,
                "ip": CURRENT_LAN_IP,
                "downloads_dir": DOWNLOADS_DIR
            })
            return

        # 2. API: Aktif Cihazlar (Peers)
        if path == "/api/peers":
            with state_lock:
                peer_list = list(peers.values())
            self.send_json({"peers": peer_list})
            return

        # 3. API: Gelen Transferler Durumu
        if path == "/api/transfers":
            with state_lock:
                data = {
                    tid: {
                        "id": tid,
                        "filename": t["filename"],
                        "size": t["size"],
                        "received_bytes": t["received_bytes"],
                        "sender": t["sender"],
                        "status": t["status"],
                        "elapsed": time.time() - t["start_time"] if t["start_time"] else 0
                    }
                    for tid, t in incoming_transfers.items()
                }
            self.send_json({"transfers": data})
            return

        # 4. API: İndirilen Dosyalar Listesi
        if path == "/api/files":
            files = []
            for f in os.listdir(DOWNLOADS_DIR):
                full_p = os.path.join(DOWNLOADS_DIR, f)
                if os.path.isfile(full_p):
                    files.append({
                        "name": f,
                        "size": os.path.getsize(full_p),
                        "modified": os.path.getmtime(full_p)
                    })
            files.sort(key=lambda x: x["modified"], reverse=True)
            self.send_json({"files": files})
            return

        # 5. Dosya İndirme (Doğrudan Link / Web İndirme - Kernel Zero-Copy)
        if path.startswith("/download/"):
            fname = unquote(path[len("/download/"):])
            # Güvenlik kontrolü (path traversal engelleme)
            safe_name = os.path.basename(fname)
            filepath = os.path.join(DOWNLOADS_DIR, safe_name)

            if not os.path.isfile(filepath):
                self.send_error(404, "Dosya bulunamadi")
                return

            file_size = os.path.getsize(filepath)
            range_header = self.headers.get('Range')

            start = 0
            end = file_size - 1
            status_code = 200

            if range_header:
                # HTTP Range (Kaldığı yerden devam etme)
                try:
                    ranges = range_header.replace('bytes=', '').split('-')
                    start = int(ranges[0])
                    if ranges[1]:
                        end = int(ranges[1])
                    status_code = 206
                except Exception:
                    pass

            content_length = end - start + 1

            self.send_response(status_code)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{safe_name}"')
            self.send_header('Accept-Ranges', 'bytes')
            if status_code == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
            self.send_header('Content-Length', str(content_length))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            # Yüksek Hızlı Disk -> Soket Akışı (Zero-Copy sendfile veya geniş tampon)
            try:
                with open(filepath, 'rb') as f:
                    f.seek(start)
                    # Linux'ta os.sendfile kullanarak çekirdek düzeyinde sıfır RAM kopyasıyla transfer:
                    if hasattr(os, 'sendfile') and hasattr(self.wfile, 'fileno'):
                        try:
                            sent = 0
                            out_fd = self.wfile.fileno()
                            in_fd = f.fileno()
                            while sent < content_length:
                                chunk = min(content_length - sent, 16 * 1024 * 1024)
                                res = os.sendfile(out_fd, in_fd, None, chunk)
                                if res == 0:
                                    break
                                sent += res
                            return
                        except Exception:
                            # sendfile başarısız olursa standart geniş tamponlu akışa geç
                            pass

                    # Standart 4MB tamponlu akış
                    remaining = content_length
                    buffer_size = 4 * 1024 * 1024
                    while remaining > 0:
                        read_bytes = min(remaining, buffer_size)
                        chunk_data = f.read(read_bytes)
                        if not chunk_data:
                            break
                        self.wfile.write(chunk_data)
                        remaining -= len(chunk_data)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        # 6. Statik Arayüz Dosyaları (HTML, CSS, JS)
        if path == "/" or path == "/index.html":
            self.serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
            return
        elif path == "/app.js":
            self.serve_file(os.path.join(STATIC_DIR, "app.js"), "application/javascript; charset=utf-8")
            return
        elif path == "/style.css":
            self.serve_file(os.path.join(STATIC_DIR, "style.css"), "text/css; charset=utf-8")
            return

        self.send_error(404, "Sayfa bulunamadi")

    def serve_file(self, filepath, content_type):
        if not os.path.exists(filepath):
            self.send_error(404, "Dosya bulunamadi")
            return
        with open(filepath, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Transfer Başlatma İsteği (Initiate / Handshake)
        if path == "/api/transfer/init":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            raw_filename = data.get("filename", "isimsiz_dosya")
            filename = os.path.basename(raw_filename)
            size = int(data.get("size", 0))
            sender = data.get("sender", "Bilinmeyen Cihaz")

            transfer_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
            dest_path = os.path.join(DOWNLOADS_DIR, filename)

            # Dosya adı çakışmasını önle
            counter = 1
            base, ext = os.path.splitext(filename)
            while os.path.exists(dest_path):
                dest_path = os.path.join(DOWNLOADS_DIR, f"{base}_{counter}{ext}")
                counter += 1

            with state_lock:
                incoming_transfers[transfer_id] = {
                    "filename": os.path.basename(dest_path),
                    "size": size,
                    "received_bytes": 0,
                    "sender": sender,
                    "status": "active",  # Doğrudan aktarım başlasın
                    "file_path": dest_path,
                    "start_time": time.time()
                }

            # Dosyayı sıfır boyutlu olarak hazırla
            with open(dest_path, "wb") as f:
                pass

            self.send_json({
                "status": "ready",
                "transfer_id": transfer_id,
                "resume_from": 0
            })
            return

        # 2. Yüksek Hızlı Chunk Yükleme (Direct Chunk Streaming)
        if path == "/api/transfer/chunk":
            transfer_id = self.headers.get('X-Transfer-Id')
            chunk_offset_str = self.headers.get('X-Chunk-Offset', '0')
            chunk_offset = int(chunk_offset_str)

            with state_lock:
                transfer = incoming_transfers.get(transfer_id)

            if not transfer:
                self.send_json({"error": "Gecersiz veya tamamlanmis transfer ID"}, status=400)
                return

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length <= 0:
                self.send_json({"error": "Bos veri"}, status=400)
                return

            dest_path = transfer["file_path"]

            # Veriyi doğrudan diskte ilgili ofsete yaz (RAM harcamadan 16MB chunk akışı)
            with open(dest_path, "r+b") as f:
                f.seek(chunk_offset)
                remaining = content_length
                read_buffer = 1024 * 1024  # 1 MB'lik tamponla oku
                while remaining > 0:
                    step = min(remaining, read_buffer)
                    block = self.rfile.read(step)
                    if not block:
                        break
                    f.write(block)
                    remaining -= len(block)

            with state_lock:
                if transfer_id in incoming_transfers:
                    incoming_transfers[transfer_id]["received_bytes"] += content_length
                    # Transfer bitti mi?
                    if incoming_transfers[transfer_id]["received_bytes"] >= incoming_transfers[transfer_id]["size"]:
                        incoming_transfers[transfer_id]["status"] = "completed"

            self.send_json({
                "status": "ok",
                "received": content_length,
                "total_received": incoming_transfers[transfer_id]["received_bytes"]
            })
            return

        self.send_error(404, "Endpoint bulunamadi")


def main():
    port = DEFAULT_PORT

    # Port çakışması varsa boş port bul
    for p in range(DEFAULT_PORT, DEFAULT_PORT + 20):
        try:
            test_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_s.bind(('0.0.0.0', p))
            test_s.close()
            port = p
            break
        except OSError:
            continue

    server = ThreadingHTTPServer(('0.0.0.0', port), BoltDropHandler)

    # Arka plan iş parçacıkları
    t_sender = threading.Thread(target=udp_broadcast_sender, args=(port,), daemon=True)
    t_listener = threading.Thread(target=udp_broadcast_listener, daemon=True)
    t_pruner = threading.Thread(target=prune_peers, daemon=True)

    t_sender.start()
    t_listener.start()
    t_pruner.start()

    lan_ip = CURRENT_LAN_IP
    print("=" * 65)
    print(" 🚀 BoltDrop - Yüksek Hızlı LAN Veri Aktarım Motoru")
    print("=" * 65)
    print(f" [*] Cihaz Adı      : {DEVICE_NAME}")
    print(f" [*] Yerel Ağ IP'si : {lan_ip}")
    print(f" [*] Web Arayüzü    : http://localhost:{port}")
    print(f" [*] Ağdaki Erişim  : http://{lan_ip}:{port}")
    print(f" [*] İndirme Dizini : {DOWNLOADS_DIR}")
    print("=" * 65)
    print(" [✓] Aynı ağdaki diğer cihazlar otomatik taranıyor...")
    print(" [✓] Tarayıcınızı açıp hemen dosya göndermeye başlayabilirsiniz.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Sunucu kapatılıyor...")
        server.server_close()
        sys.exit(0)

if __name__ == "__main__":
    main()
