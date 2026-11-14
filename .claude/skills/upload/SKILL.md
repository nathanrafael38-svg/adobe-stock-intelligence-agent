---
name: upload
description: Upload semua platform dalam satu perintah (Adobe Stock, Vecteezy, Dreamstime) tanpa menekan .bat. Pakai saat Nathan mengetik /upload atau minta upload ke Vecteezy/Dreamstime/Adobe.
---

# /upload — Adobe + Vecteezy + Dreamstime

Nathan tidak menjalankan .bat. Sesi ini **tidak punya shell di PC** dan tidak boleh menjalankan WinSCP atau membaca kredensial.
Jadi: orchestrator menyiapkan antrean + `READY.flag`, task Windows di PC yang mengirim, orchestrator memantau log dan merekam hasil dengan bukti.
Upload ≠ submission ≠ acceptance. `/upload` tidak pernah submit ke Adobe.

## 0. Start
Ikuti dailyrun step 0 (RUN.lock, setup, stage `_state\C*.json`). Lalu `python -m msp day-status`.
Tentukan batch yang belum ke setiap platform:
- **Adobe**: aset `qc_passed`+metadata yang belum `sftp_uploaded` → dailyrun stage G/H (`msp enqueue` dua fase, READY.flag terakhir; setelah antrean kosong `msp reconcile --log`; lalu `browser-operator` mode=prepare).
- **Vecteezy + Dreamstime**: hanya **foto** (bukan ilustrasi), lolos QC, punya metadata, **tanpa foto orang** (kecuali Nathan bilang lain).

## 1. Seleksi VZ/DT
```
python -m msp stock-select --ns 198,199 --skip <file orang,...>   # files, keep_k, dt_skip_k per batch
python -m msp vz-csv --ns 198,199 --skip <...> --out vecteezy-photos-<batches>.csv
python -m msp dt-csv --n N --skip <dt_skip_k batch N>              # satu per batch
```
`vz-csv` harus `errors: []` (vz_title 3–8 kata, keyword 5–50). Hanya file yang sudah ada di `Day N\` (final ter-embed).

## 2. Staging (urutan wajib, flag terakhir)
1. Commit JPG final ke `_UPLOAD_QUEUE_VZ\` dan `_UPLOAD_QUEUE_DT\`; CSV Dreamstime ke `_UPLOAD_QUEUE_DT\csv\`.
2. Verifikasi isi antrean (`device_list_dir`) = daftar `files`.
3. Commit `READY.flag` ke masing-masing antrean **paling akhir**.
4. Task PC "Microstock Upload Watch" (tiap 10 menit, `_tools\upload_watch.bat`) memanggil `vecteezy_upload.bat` / `dreamstime_upload.bat` dengan `NOPAUSE=1`. Adobe tetap lewat task "Adobe Stock SFTP Upload".
5. Task belum ada → minta Nathan menjalankan `_tools\setup_tasks.bat` sekali (admin). Jangan jalankan WinSCP sendiri.

## 3. Pantau dan rekam
- Poll antrean (≤30 menit): VZ pindah ke `_UPLOAD_QUEUE_VZ\_sent`; DT kosong setelah JPG + CSV terkirim; flag terhapus = selesai.
- Stage `_logs\upload_watch.log`, `winscp.log`; baca exit code, bukan asumsi.
- Bukti ada → catat hasil per aset (`msp mark` dengan evidence: log + waktu). Tanpa bukti: jangan tandai.
- Antrean tidak bergerak dalam 30 menit → lapor, tahan flag, jangan retry sendiri.

## 4. Langkah manual Nathan (tidak bisa otomatis)
- **Vecteezy**: import `vecteezy-photos-*.csv` di situs (kolom Filename tanpa underscore, mis. `C19901.jpg`).
- **Dreamstime**: cek "Unfinished" untuk kategori.
- **Adobe**: Terms + CAPTCHA + submit.

## 5. Finish
`msp status`, commit state, `RUN.lock` → `state=done`, ringkasan pendek: terkirim per platform / tertunda / langkah Nathan.
