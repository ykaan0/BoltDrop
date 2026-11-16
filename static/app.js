// BoltDrop Frontend Motoru
let myInfo = null;
let selectedFile = null;
let isTransferring = false;
const CHUNK_SIZE = 16 * 1024 * 1024; // 16 MB chunking

// DOM Elemanları
const myDeviceNameEl = document.getElementById("myDeviceName");
const myDeviceIpEl = document.getElementById("myDeviceIp");
const peersListEl = document.getElementById("peersList");
const peerCountEl = document.getElementById("peerCount");
const dropzoneEl = document.getElementById("dropzone");
const fileInputEl = document.getElementById("fileInput");
const selectedFileInfoEl = document.getElementById("selectedFileInfo");
const selectedFileNameEl = document.getElementById("selectedFileName");
const selectedFileSizeEl = document.getElementById("selectedFileSize");
const btnCancelFileEl = document.getElementById("btnCancelFile");
const filesListEl = document.getElementById("filesList");
const btnRefreshFilesEl = document.getElementById("btnRefreshFiles");

// Transfer Monitörü Elemanları
const transferSectionEl = document.getElementById("transferSection");
const transferFileNameEl = document.getElementById("transferFileName");
const transferPeerEl = document.getElementById("transferPeer");
const transferSpeedEl = document.getElementById("transferSpeed");
const transferSizeEl = document.getElementById("transferSize");
const transferEtaEl = document.getElementById("transferEta");
const progressBarEl = document.getElementById("progressBar");
const progressPercentEl = document.getElementById("progressPercent");
const transferChunksEl = document.getElementById("transferChunks");

// Boyut biçimlendirici
function formatBytes(bytes, decimals = 2) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Zaman biçimlendirici
function formatSeconds(secs) {
  if (isNaN(secs) || !isFinite(secs) || secs < 0) return 'Hesaplanıyor...';
  if (secs < 60) return `${Math.round(secs)} saniye`;
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return `${m} dk ${s} sn`;
}

// 1. Cihaz Bilgisini Al
async function fetchMyInfo() {
  try {
    const res = await fetch("/api/info");
    myInfo = await res.json();
    myDeviceNameEl.textContent = myInfo.name;
    myDeviceIpEl.textContent = `IP: ${myInfo.ip}`;
  } catch (err) {
    myDeviceNameEl.textContent = "Bağlantı Hatası";
  }
}

// 2. Ağdaki Cihazları Periyodik Tara
async function fetchPeers() {
  try {
    const res = await fetch("/api/peers");
    const data = await res.json();
    renderPeers(data.peers || []);
  } catch (err) {
    console.error("Peers fetch error:", err);
  }
}

function renderPeers(peers) {
  peerCountEl.textContent = `${peers.length} Cihaz`;

  if (peers.length === 0) {
    peersListEl.innerHTML = `
      <div class="empty-peers">
        <div style="font-size: 32px; opacity: 0.6;">🔍</div>
        <p style="font-weight: 500;">Ağ taranıyor...</p>
        <p style="font-size: 12px;">Arkadaşın aynı Wi-Fi/ağda BoltDrop'u açtığında burada anında görünecektir.</p>
      </div>
    `;
    return;
  }

  peersListEl.innerHTML = "";
  peers.forEach(peer => {
    const card = document.createElement("div");
    card.className = "peer-card";
    card.innerHTML = `
      <div class="peer-info">
        <div class="peer-avatar">💻</div>
        <div>
          <div class="peer-name">${escapeHtml(peer.name)}</div>
          <div class="peer-ip">${peer.ip}:${peer.port}</div>
        </div>
      </div>
      <button class="btn btn-success btn-send-peer" data-ip="${peer.ip}" data-port="${peer.port}" data-name="${escapeHtml(peer.name)}" ${!selectedFile || isTransferring ? 'disabled' : ''}>
        ⚡ Gönder
      </button>
    `;
    peersListEl.appendChild(card);
  });

  // Gönder butonları dinleyicileri
  document.querySelectorAll(".btn-send-peer").forEach(btn => {
    btn.addEventListener("click", () => {
      const ip = btn.getAttribute("data-ip");
      const port = btn.getAttribute("data-port");
      const name = btn.getAttribute("data-name");
      startTransfer(ip, port, name);
    });
  });
}

// 3. İndirilen Dosyaları Getir
async function fetchFiles() {
  try {
    const res = await fetch("/api/files");
    const data = await res.json();
    renderFiles(data.files || []);
  } catch (err) {
    console.error("Files fetch error:", err);
  }
}

function renderFiles(files) {
  if (files.length === 0) {
    filesListEl.innerHTML = `<p style="text-align: center; color: var(--text-muted); font-size: 13px; padding: 20px;">Henüz alınan dosya yok.</p>`;
    return;
  }

  filesListEl.innerHTML = "";
  files.forEach(f => {
    const item = document.createElement("div");
    item.className = "file-item";
    item.innerHTML = `
      <div style="display: flex; align-items: center; gap: 12px; overflow: hidden;">
        <span style="font-size: 20px;">📦</span>
        <div>
          <div style="font-weight: 600; font-size: 14px;">${escapeHtml(f.name)}</div>
          <div style="font-size: 12px; color: var(--text-muted);">${formatBytes(f.size)}</div>
        </div>
      </div>
      <a href="/download/${encodeURIComponent(f.name)}" class="btn" style="text-decoration: none; font-size: 12px; padding: 6px 12px;">
        💾 İndir
      </a>
    `;
    filesListEl.appendChild(item);
  });
}

// 4. Dosya Seçimi ve Sürükle & Bırak
dropzoneEl.addEventListener("click", () => fileInputEl.click());

dropzoneEl.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzoneEl.classList.add("dragover");
});

dropzoneEl.addEventListener("dragleave", () => {
  dropzoneEl.classList.remove("dragover");
});

dropzoneEl.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzoneEl.classList.remove("dragover");
  if (e.dataTransfer.files.length > 0) {
    handleFileSelect(e.dataTransfer.files[0]);
  }
});

fileInputEl.addEventListener("change", (e) => {
  if (e.target.files.length > 0) {
    handleFileSelect(e.target.files[0]);
  }
});

function handleFileSelect(file) {
  selectedFile = file;
  selectedFileNameEl.textContent = file.name;
  selectedFileSizeEl.textContent = formatBytes(file.size);
  selectedFileInfoEl.style.display = "flex";
  dropzoneEl.style.display = "none";
  fetchPeers(); // Butonların durumunu güncelle
}

btnCancelFileEl.addEventListener("click", () => {
  if (isTransferring) {
    if (!confirm("Transfer devam ediyor, iptal etmek istediğinize emin misiniz?")) return;
  }
  selectedFile = null;
  fileInputEl.value = "";
  selectedFileInfoEl.style.display = "none";
  dropzoneEl.style.display = "block";
  fetchPeers();
});

// 5. Yüksek Hızlı Chunk Transfer Motoru (Direct P2P Stream)
async function startTransfer(targetIp, targetPort, targetName) {
  if (!selectedFile || isTransferring) return;

  isTransferring = true;
  transferSectionEl.style.display = "block";
  transferFileNameEl.textContent = selectedFile.name;
  transferPeerEl.textContent = `Hedef Cihaz: ${targetName} (${targetIp})`;
  transferSpeedEl.textContent = "0.0 MB/s";
  transferEtaEl.textContent = "Başlatılıyor...";
  progressBarEl.style.width = "0%";
  progressPercentEl.textContent = "0%";

  const targetUrl = `http://${targetIp}:${targetPort}`;

  try {
    // Adım 1: Handshake / Init
    const initRes = await fetch(`${targetUrl}/api/transfer/init`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: selectedFile.name,
        size: selectedFile.size,
        sender: myInfo ? myInfo.name : "BoltDrop İstemcisi"
      })
    });

    if (!initRes.ok) {
      throw new Error(`Hedef cihaz transferi kabul etmedi (HTTP ${initRes.status})`);
    }

    const initData = await initRes.json();
    const transferId = initData.transfer_id;

    // Adım 2: 16 MB'lik Chunk'larla Akış (Kernel Seviyesinde Doğrudan Sokete Yazım)
    const totalSize = selectedFile.size;
    const totalChunks = Math.ceil(totalSize / CHUNK_SIZE);
    let offset = 0;
    let chunkIndex = 0;

    let startTime = Date.now();
    let lastTime = startTime;
    let lastBytes = 0;

    while (offset < totalSize) {
      const end = Math.min(offset + CHUNK_SIZE, totalSize);
      const chunkBlob = selectedFile.slice(offset, end);

      const chunkRes = await fetch(`${targetUrl}/api/transfer/chunk`, {
        method: "POST",
        headers: {
          "Content-Type": "application/octet-stream",
          "X-Transfer-Id": transferId,
          "X-Chunk-Offset": offset.toString()
        },
        body: chunkBlob
      });

      if (!chunkRes.ok) {
        throw new Error(`Parça iletim hatası (${chunkIndex + 1}/${totalChunks})`);
      }

      offset = end;
      chunkIndex++;

      // Hız ve Süre Hesaplamaları (1 saniyelik pencereler)
      const now = Date.now();
      const timeDiff = (now - lastTime) / 1000;

      if (timeDiff >= 0.6 || offset === totalSize) {
        const bytesDiff = offset - lastBytes;
        const currentSpeedBytesSec = bytesDiff / timeDiff; // Bytes/sec
        const speedMBps = currentSpeedBytesSec / (1024 * 1024);

        const remainingBytes = totalSize - offset;
        const etaSeconds = currentSpeedBytesSec > 0 ? (remainingBytes / currentSpeedBytesSec) : 0;

        transferSpeedEl.textContent = `${speedMBps.toFixed(1)} MB/s`;
        transferEtaEl.textContent = formatSeconds(etaSeconds);

        lastTime = now;
        lastBytes = offset;
      }

      // İlerleme Çubuğu Güncellemesi
      const percent = Math.min(100, (offset / totalSize) * 100).toFixed(1);
      progressBarEl.style.width = `${percent}%`;
      progressPercentEl.textContent = `${percent}%`;
      transferSizeEl.textContent = `${formatBytes(offset)} / ${formatBytes(totalSize)}`;
      transferChunksEl.textContent = `Parça: ${chunkIndex} / ${totalChunks}`;
    }

    // Tamamlandı!
    const totalSeconds = ((Date.now() - startTime) / 1000).toFixed(1);
    const avgSpeed = ((totalSize / (1024 * 1024)) / (totalSeconds || 1)).toFixed(1);

    transferSpeedEl.textContent = `Ort. ${avgSpeed} MB/s`;
    transferEtaEl.textContent = `Tamamlandı! (${totalSeconds} sn)`;
    progressBarEl.style.width = "100%";
    progressPercentEl.textContent = "100%";
    alert(`🎉 Harika! ${selectedFile.name} başarıyla aktarıldı!\nOrtalama Hız: ${avgSpeed} MB/s (${totalSeconds} saniye)`);

  } catch (err) {
    console.error("Transfer hatası:", err);
    alert(`Transfer Hatası: ${err.message}`);
    transferEtaEl.textContent = "Hata oluştu";
  } finally {
    isTransferring = false;
    fetchPeers();
  }
}

// 6. Alıcı Tarafı İçin Gelen Transferleri İzleme
async function checkIncomingTransfers() {
  if (isTransferring) return; // Gönderen durumundaysak yerel monitor açık kalır

  try {
    const res = await fetch("/api/transfers");
    const data = await res.json();
    const active = Object.values(data.transfers).filter(t => t.status === "active");

    if (active.length > 0) {
      const t = active[0];
      transferSectionEl.style.display = "block";
      transferFileNameEl.textContent = t.filename;
      transferPeerEl.textContent = `Gönderen: ${t.sender}`;

      const percent = Math.min(100, (t.received_bytes / (t.size || 1)) * 100).toFixed(1);
      progressBarEl.style.width = `${percent}%`;
      progressPercentEl.textContent = `${percent}%`;
      transferSizeEl.textContent = `${formatBytes(t.received_bytes)} / ${formatBytes(t.size)}`;
      
      const speed = t.elapsed > 0 ? (t.received_bytes / (1024 * 1024) / t.elapsed).toFixed(1) : "0.0";
      transferSpeedEl.textContent = `${speed} MB/s`;
      transferEtaEl.textContent = "Alınıyor...";
    }
  } catch (err) {}
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

btnRefreshFilesEl.addEventListener("click", fetchFiles);

// Başlatma ve Döngüler
fetchMyInfo();
fetchPeers();
fetchFiles();

setInterval(fetchPeers, 2000);
setInterval(checkIncomingTransfers, 1000);
setInterval(fetchFiles, 4000);
