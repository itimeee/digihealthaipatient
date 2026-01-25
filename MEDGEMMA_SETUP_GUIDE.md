# MedGemma 1.5 API Setup Guide / คู่มือการตั้งค่า MedGemma 1.5 API

## Overview / ภาพรวม

MedGemma 1.5 เป็นโมเดล AI ทางการแพทย์จาก Google ที่ออกแบบมาเพื่อการทำความเข้าใจข้อความและภาพทางการแพทย์
สามารถเข้าถึงได้ผ่าน Hugging Face และ Google Cloud Vertex AI

**MedGemma 1.5 Models ที่มีให้ใช้:**
- `google/medgemma-1.5-4b-it` - โมเดล 4B parameters (แนะนำสำหรับใช้งานทั่วไป)
- `google/medgemma-27b-text-it` - โมเดล 27B parameters (ต้องการ resources มากกว่า)

---

## ขั้นตอนที่ 1: สมัครบัญชี Hugging Face

1. ไปที่ [https://huggingface.co/join](https://huggingface.co/join)
2. สมัครบัญชีใหม่หรือล็อกอินด้วยบัญชีที่มีอยู่
3. ยืนยันอีเมลของคุณ

---

## ขั้นตอนที่ 2: ยอมรับ Terms of Use ของ MedGemma

**สำคัญมาก:** คุณต้องยอมรับ Terms of Use ก่อนจึงจะใช้งาน MedGemma ได้

1. ไปที่หน้า MedGemma 1.5 บน Hugging Face:
   - [MedGemma 1.5 4B](https://huggingface.co/google/medgemma-1.5-4b-it)
   - หรือ [MedGemma 27B Text](https://huggingface.co/google/medgemma-27b-text-it)

2. ล็อกอินเข้าสู่ Hugging Face

3. คลิกที่ปุ่ม **"Agree and access repository"** หรือ **"Accept license"**
   - คุณจะเห็นข้อความแจ้งเกี่ยวกับ Health AI Developer Foundation Terms of Use
   - อ่านและยอมรับเงื่อนไข

4. รอการอนุมัติ (โดยปกติจะได้รับทันที)

---

## ขั้นตอนที่ 3: สร้าง Hugging Face API Token

1. ไปที่ [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)

2. คลิก **"Create new token"** หรือ **"New token"**

3. ตั้งค่า Token:
   - **Name:** ตั้งชื่อที่จำได้ง่าย เช่น `digihealthai-medgemma`
   - **Type:** เลือก **"Read"** (สำหรับ Inference API) หรือ **"Fine-grained"**
   - ถ้าเลือก Fine-grained: ให้เลือก permissions ที่เกี่ยวกับ Inference

4. คลิก **"Create token"**

5. **คัดลอก Token ทันที!** (จะแสดงเพียงครั้งเดียว)
   - Token จะมีรูปแบบ: `hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

---

## ขั้นตอนที่ 4: เพิ่ม Token ใน Streamlit Secrets

### สำหรับ Local Development

แก้ไขไฟล์ `.streamlit/secrets.toml`:

```toml
# Hugging Face API Token for MedGemma
HF_API_TOKEN = "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# (Optional) Keep Gemini as fallback
GEMINI_API_KEY = "your-gemini-api-key"
```

### สำหรับ Streamlit Cloud

1. ไปที่ Settings ของ App บน Streamlit Cloud
2. คลิก **"Secrets"**
3. เพิ่ม:

```toml
HF_API_TOKEN = "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

---

## ขั้นตอนที่ 5: ตั้งค่าใน feedback_config.py

แก้ไขไฟล์ `feedback_config.py`:

```python
# ใช้ MedGemma เป็น provider หลัก
FEEDBACK_PROVIDER = "medgemma"

# เลือกโมเดล MedGemma
FEEDBACK_MODEL_NAME = "google/medgemma-1.5-4b-it"

# ตั้ง Gemini เป็น fallback (ถ้า MedGemma ไม่ทำงาน)
FEEDBACK_FALLBACK_PROVIDER = "gemini"
FEEDBACK_FALLBACK_MODEL = "gemini-2.0-flash-exp"
```

---

## ทางเลือกอื่น: ใช้ Hugging Face Inference Endpoints (Dedicated)

หาก Serverless API ไม่รองรับ MedGemma หรือต้องการประสิทธิภาพที่ดีกว่า:

### 1. สร้าง Dedicated Endpoint

1. ไปที่ [https://ui.endpoints.huggingface.co/](https://ui.endpoints.huggingface.co/)
2. คลิก **"Create new endpoint"**
3. เลือกโมเดล: `google/medgemma-1.5-4b-it`
4. เลือก Cloud Provider และ Region
5. เลือก Instance Type (แนะนำ GPU)
6. คลิก **"Create Endpoint"**
7. รอจนกว่า Endpoint จะ Running

### 2. ตั้งค่าใน feedback_config.py

```python
# ใช้ Dedicated Endpoint
HF_ENDPOINT_TYPE = "dedicated"
HF_DEDICATED_ENDPOINT_URL = "https://xxxxx.us-east-1.aws.endpoints.huggingface.cloud"
```

---

## ทางเลือก: ใช้ Google Cloud Vertex AI

หากต้องการใช้ MedGemma ผ่าน Google Cloud:

### 1. เปิดใช้งาน Vertex AI

1. ไปที่ [Google Cloud Console](https://console.cloud.google.com/)
2. สร้าง Project ใหม่หรือเลือก Project ที่มีอยู่
3. เปิดใช้งาน Vertex AI API
4. ไปที่ [Model Garden](https://console.cloud.google.com/vertex-ai/publishers/google/model-garden/medgemma)
5. ค้นหา "MedGemma" และ Deploy

### 2. ตั้งค่า Authentication

ใช้ Service Account Key หรือ Application Default Credentials

**หมายเหตุ:** การใช้ Vertex AI ต้องแก้ไขโค้ดเพิ่มเติมใน feedback_service.py

---

## การแก้ปัญหาที่พบบ่อย

### Error: "Model is loading"

**สาเหตุ:** โมเดลยังไม่ถูกโหลดใน Serverless API

**วิธีแก้:**
- รอ 20-60 วินาที แล้วลองใหม่
- ระบบจะ retry อัตโนมัติ (ตั้งค่าใน `HF_MAX_RETRIES`)

### Error: "You need to agree to the license"

**สาเหตุ:** ยังไม่ได้ยอมรับ Terms of Use

**วิธีแก้:**
- ไปที่หน้า [MedGemma Model](https://huggingface.co/google/medgemma-1.5-4b-it)
- คลิก "Agree and access repository"

### Error: "Authorization header is incorrect"

**สาเหตุ:** HF_API_TOKEN ไม่ถูกต้องหรือหมดอายุ

**วิธีแก้:**
- ตรวจสอบ Token ใน secrets.toml
- สร้าง Token ใหม่ถ้าจำเป็น

### Error: "Model too large for serverless"

**สาเหตุ:** โมเดลใหญ่เกินไปสำหรับ Serverless API

**วิธีแก้:**
- ใช้ Dedicated Inference Endpoints
- หรือเปลี่ยนไปใช้โมเดลที่เล็กกว่า

### Fallback ใช้ Gemini แทน

**สาเหตุ:** MedGemma ไม่สามารถ generate ได้

**วิธีแก้:**
- ตรวจสอบว่า HF_API_TOKEN ถูกต้อง
- ตรวจสอบว่ายอมรับ Terms of Use แล้ว
- ดู console log สำหรับรายละเอียด error

---

## ราคาและ Rate Limits

### Hugging Face Serverless (Free Tier)
- ~100-500 requests/hour
- อาจมี cold start delay
- บางโมเดลอาจไม่รองรับ

### Hugging Face PRO ($9/month)
- Higher rate limits
- Priority access
- Faster response times

### Hugging Face Inference Endpoints
- Pay per compute time
- No rate limits
- Dedicated resources
- ราคาเริ่มต้น ~$0.06/hour สำหรับ CPU, ~$1.30/hour สำหรับ GPU

### Google Cloud Vertex AI
- Pay per prediction
- ดู [Vertex AI Pricing](https://cloud.google.com/vertex-ai/pricing)

---

## Resources เพิ่มเติม

- [MedGemma Model Card](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card)
- [MedGemma GitHub](https://github.com/Google-Health/medgemma)
- [Hugging Face Inference API Docs](https://huggingface.co/docs/api-inference/index)
- [Health AI Developer Foundations](https://developers.google.com/health-ai-developer-foundations)

---

## ข้อควรระวังในการใช้งาน MedGemma

> **คำเตือน:** MedGemma มีจุดประสงค์เพื่อเป็นจุดเริ่มต้นสำหรับการพัฒนา application ทางการแพทย์
> ไม่ได้มีจุดประสงค์ให้ใช้โดยตรงในการวินิจฉัยทางคลินิก การตัดสินใจในการรักษา
> หรือการใช้งานทางคลินิกโดยตรงอื่นๆ โดยไม่มีการ validation และ adaptation ที่เหมาะสม

---

*Last updated: January 2025*
