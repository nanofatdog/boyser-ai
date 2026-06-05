# Changelog

## 2026-06-05
- แก้ ESC ไม่ทำงานบางครั้ง: ตอนนี้หยุดได้ทันทีแม้กำลังรอ token แรก (โหลดโมเดล/prompt eval) และระหว่างรัน tools (ไม่ยิงรอบใหม่ต่อ) — รวมถึงฆ่า bash ที่กำลังรันอยู่ทันที
- ใช้ Ollama ผ่าน LAN ได้: wizard ถาม URL/IP (ใส่แค่ IP ได้) + วิธีเปิด server รับ LAN ใน README
- ระบบแจ้งเตือนอัปเดต + คำสั่ง /update
- เพิ่ม screenshot ใน README
- เผยแพร่ครั้งแรก: agent.py + 42 skills + install.sh
