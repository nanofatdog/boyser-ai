---
name: backtest-review
description: ตรวจสอบ backtest/กลยุทธ์เทรดว่าน่าเชื่อถือไหม ใช้เมื่อรีวิวผล backtest, strategy, หรือผู้ใช้ถามว่ากลยุทธ์นี้ใช้ได้จริงไหม
---

# Skill: backtest-review

ตั้งใจ**หาเหตุที่มันจะพัง** ไม่ใช่เชียร์ ผลที่ดูดีเกินไปมักมีบั๊ก:

1. **Lookahead bias**: ใช้ข้อมูลอนาคตไหม? (เช่น close ของแท่งปัจจุบันตอนตัดสินใจ, normalize ด้วยค่าทั้งชุด, label รั่ว)
2. **Overfitting**: param เยอะไปไหม? fit noise? — ขอผล **out-of-sample / walk-forward** ไม่ใช่ in-sample
3. **ต้นทุนจริง**: รวม fee + slippage + spread + funding หรือยัง? ของจริงกินกำไรเยอะ
4. **Survivorship/selection bias**: เลือกเฉพาะเหรียญที่รอด? ช่วงเวลาที่สวย?
5. **Sample size & regime**: เทรดกี่ครั้ง? ผ่านทั้ง bull/bear/sideways ไหม? กำไรกระจุกไม่กี่ดีล?
6. **ตัวเลขที่ต้องสงสัย**: Sharpe สูงผิดปกติ, DD ต่ำเกิน, win rate ~100%
7. สรุปตรงๆ: เชื่อได้แค่ไหน, ความเสี่ยงอะไร — **อย่าเชียร์ให้ deploy จาก backtest อย่างเดียว** ต้อง paper/forward test ก่อน

ซื่อสัตย์ดีกว่าถูกใจ
