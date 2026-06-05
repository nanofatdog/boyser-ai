---
name: api-design
description: ออกแบบ REST/JSON API ใช้เมื่อผู้ใช้ขอออกแบบ endpoint, API, หรือโครงสร้าง request/response
---

# Skill: api-design

1. **Resource เป็นคำนาม** + ใช้ HTTP verb ให้ถูก: `GET /users`, `POST /users`, `GET /users/{id}`, `PATCH /users/{id}`, `DELETE /users/{id}` — ไม่เอา verb ใน path (`/getUsers` ❌)
2. **Status code ถูกความหมาย**: 200/201/204, 400 (input ผิด), 401/403 (auth), 404, 409 (conflict), 422 (validation), 500
3. **JSON shape สม่ำเสมอ**: ตั้งชื่อ field แบบเดียวกันทั้ง API; error format กลาง เช่น `{"error": {"code","message"}}`
4. **List**: รองรับ pagination (`?page`/`?limit` หรือ cursor), filter, sort
5. **Versioning**: `/v1/...` หรือ header ตั้งแต่แรก
6. **Validate input** ทุก endpoint; **auth** ชัดเจน; idempotency สำหรับ POST ที่ซ้ำได้
7. ระบุ contract: method, path, request body, response body, error — ให้ frontend เอาไปใช้ได้เลย
