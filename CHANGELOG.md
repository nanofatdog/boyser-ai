# Changelog

## 2026-06-06
- ESC = ย้อนกลับในเมนู (แบบ Claude Code): wizard เมนูลึกถอยกลับไปเลือก backend, ส่วนเมนูแรก / /model / /theme กด ESC = ยกเลิกเฉยๆ ไม่หลุดโปรแกรม (เดิมยกเลิกได้ทางเดียวคือ Ctrl+C ซึ่งปิดโปรแกรมเลย) — ลูกศรยังใช้ปกติ, ESC ตอบไวใน 90ms
- ใหม่: `@ไฟล์` ในช่องแชต — พิมพ์ @ เด้งเมนูรายชื่อไฟล์ใน cwd (filter ได้), ส่งแล้วแนบเนื้อไฟล์ให้โมเดลอัตโนมัติ (cap 100k ตัวอักษร, โชว์ 📎); พิมพ์ `./` เด้งเมนูเดียวกันแต่เติมแค่ path
- แก้ wizard เติม `:11434` ทับ URL https — ใส่โดเมน (เช่นผ่าน Cloudflare Tunnel) แล้วพังเพราะกลายเป็นพอร์ตผิด ตอนนี้เติมพอร์ตเฉพาะ http
- ใช้ Ollama นอกบ้านผ่านโดเมน/auth proxy ได้: wizard Ollama ถาม API key (optional) + native path แนบ Authorization ทุก call (probe/chat/vote/list) — คู่กับ auth proxy + Cloudflare Tunnel ฝั่ง server
- โชว์เวอร์ชันบนหน้า CLI: banner + /status แสดง `v<n> (<hash> · <วันที่>)` คำนวณจาก git อัตโนมัติ — /update แล้วเลขขยับเอง (ติดตั้งแบบไม่มี git จะซ่อนบรรทัดนี้)
- ใหม่: `/vote` — เอกสารยาว (>150k ตัวอักษร) ถามซ้ำ 3 รอบอัตโนมัติแล้วหา consensus (รอบ 2-3 แทบฟรีเพราะ KV cache) — แก้อาการโมเดล local ตอบไม่นิ่งบน context ยาวแม้ temp 0 (เทสพบเงื่อนไขเดิมเป๊ะให้คนละคำตอบ/บางทีติด loop); ตรงกันหมดใช้เลย ไม่ตรงให้โมเดลตัดสินเสียงข้างมาก; เปิดเป็น default ปิดได้ด้วย /vote
- ถอน repeat_penalty ออกจากโหมดเอกสารยาว (เหลือแค่ num_predict cap) — เทสซ้ำทั้งชุดพบผลไม่นิ่ง: บางเอกสารช่วย multi-hop บางเอกสารไม่ช่วย แถมทำ recall รายการยาวพัง (9/10 → 0/10)
- แก้ crash เมื่อโมเดลส่ง todos เป็น list ของ string (ไม่ใช่ dict) — todo_write ห่อเป็น dict ให้เอง (เจอจากเทสเอกสารยาวจริง: โมเดลตอบเสร็จแล้วเรียก todo_write format เพี้ยน ทำทั้ง turn พัง)
- ฉลาดขึ้นกับเอกสารยาว: request ที่ context เกิน ~150k ตัวอักษรจะใส่ `repeat_penalty 1.3` + `num_predict 4096` ให้อัตโนมัติ (Ollama) — แก้อาการวน loop ตอน generate และจับคู่ข้อมูลข้าม context ผิดตัว (พิสูจน์ด้วย stress test จริงที่ 190k token: multi-hop 0/2 → 2/2) โดยไม่กระทบ codegen ปกติ

## 2026-06-05
- แก้ ESC ไม่ทำงานบางครั้ง: ตอนนี้หยุดได้ทันทีแม้กำลังรอ token แรก (โหลดโมเดล/prompt eval) และระหว่างรัน tools (ไม่ยิงรอบใหม่ต่อ) — รวมถึงฆ่า bash ที่กำลังรันอยู่ทันที
- ใช้ Ollama ผ่าน LAN ได้: wizard ถาม URL/IP (ใส่แค่ IP ได้) + วิธีเปิด server รับ LAN ใน README
- ระบบแจ้งเตือนอัปเดต + คำสั่ง /update
- เพิ่ม screenshot ใน README
- เผยแพร่ครั้งแรก: agent.py + 42 skills + install.sh
