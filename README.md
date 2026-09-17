# Bad Cyber Shop

Bad Cyber Shop là game CTF mini cho beginner về ba lỗi phổ biến trong logic ứng dụng:

- **Level 1 - Loose Change:** ví tiền được tin hoàn toàn từ save file JSON phía client.
- **Level 2 - Signed, Not Safe:** player packet được Base64 encode rồi dùng MD5 để kiểm tra, nhưng không có secret key.
- **Level 3 - Point Zero:** số lượng bị ép thành integer khi trừ inventory nhưng vẫn giữ số thập phân khi cộng tiền.

## Chạy local

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py app.py
```

Mở `http://127.0.0.1:5000`. Mỗi browser session là một sandbox riêng; nút `RESET SESSION` xoá tiến trình hiện tại.

Đây là game intentionally vulnerable. Không deploy app này lên internet hoặc dùng làm code production.
