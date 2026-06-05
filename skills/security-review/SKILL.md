---
name: security-review
description: ตรวจหาช่องโหว่ความปลอดภัยในโค้ด ใช้เมื่อผู้ใช้ขอ security review ตรวจความปลอดภัย หรือหาช่องโหว่ (เพื่อการป้องกัน)
---

# Skill: security-review

ตรวจเพื่อ**ป้องกัน** (defensive) เท่านั้น รายงานช่องโหว่ + วิธีแก้ ไม่เขียน exploit

ไล่เช็ค:
1. **Injection**: SQL (ต่อ string), command injection (`os.system`/`subprocess shell=True` กับ input), path traversal (`../`)
2. **Secrets**: API key/password/token hardcode ในโค้ด หรือ commit ลง git
3. **Input validation**: เชื่อ input จากผู้ใช้/เน็ตโดยไม่ตรวจ, deserialization ไม่ปลอดภัย (pickle/yaml.load)
4. **Auth/authz**: เช็คสิทธิ์ครบไหม, IDOR (เข้าถึง id คนอื่นได้), session/JWT จัดการถูกไหม
5. **Crypto**: ใช้ MD5/SHA1 กับ password (ควร bcrypt/argon2), random ไม่ปลอดภัย (`random` แทน `secrets`), hardcode IV/key
6. **Web**: XSS (output ไม่ escape), CSRF, SSRF (fetch URL จาก input), CORS หละหลวม
7. **Dependencies**: lib เก่ามี CVE รู้จัก

แต่ละ finding: `file:line` · severity · ผลกระทบ · วิธีแก้ที่ทำได้จริง — เรียงจากร้ายแรงสุด
