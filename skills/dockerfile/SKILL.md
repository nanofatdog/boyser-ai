---
name: dockerfile
description: เขียน Dockerfile หรือ docker-compose ใช้เมื่อผู้ใช้ขอ containerize แอป ทำ image หรือตั้ง docker
---

# Skill: dockerfile

1. เลือก base image **slim + pin เวอร์ชัน** (`python:3.12-slim` ไม่ใช่ `latest`)
2. **เรียงเลเยอร์ให้ cache ทำงาน**: copy ไฟล์ deps (requirements.txt/package.json) → install → ค่อย copy โค้ด (โค้ดเปลี่ยนบ่อย deps ไม่ค่อยเปลี่ยน)
3. **multi-stage build** ถ้าต้อง compile/build — แยก stage build กับ runtime ให้ image เล็ก
4. รันด้วย **non-root user** (`USER app`) เพื่อความปลอดภัย
5. มี `.dockerignore` (ตัด .git, .venv, node_modules, .env)
6. **ห้าม bake secret** ลง image — ใช้ env/secret ตอน run
7. ใส่ `EXPOSE`, `CMD`/`ENTRYPOINT` ชัดเจน; healthcheck ถ้าเป็น service
8. ทดสอบ: `docker build` แล้ว `docker run` ดูว่าใช้งานได้จริง ก่อนบอกว่าเสร็จ
