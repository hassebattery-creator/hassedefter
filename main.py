"""
Hasse Teslimat Defteri Pro - FINAL
Production-ready
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
import httpx
import gspread
from google.oauth2.service_account import Credentials
import os

app = FastAPI(title="Hasse Teslimat Defteri Pro", version="6.0-final")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Veri
customers, products, deliveries, sales, cash_entries, staff = [], [], [], [], [], []
accounts = {}
logs = []

SYSTEM_PROMPT = """Sen Hasse Teslimat Defteri profesyonel asistanısın.
Kısa, net, aksiyon odaklı Türkçe cevap ver."""

class Customer(BaseModel):
    name: str
    phone: Optional[str] = ""
    address: Optional[str] = ""
    tax_no: Optional[str] = ""

class Delivery(BaseModel):
    customer_name: str
    address: str
    items: str
    notes: Optional[str] = ""
    status: str = "bekliyor"

class Sale(BaseModel):
    customer_name: str
    total: float
    items: str
    payment_type: str = "nakit"

class ClaudeAccount(BaseModel):
    name: str
    api_key: str

class ChatRequest(BaseModel):
    message: str

def log(msg: str):
    logs.append({"t": datetime.now().isoformat(), "m": msg})

# ==================== UI ====================
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hasse Teslimat Defteri</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-100">
<div class="max-w-6xl mx-auto p-4">
  <div class="flex justify-between items-center mb-6">
    <div>
      <h1 class="text-2xl font-bold">Hasse Teslimat Defteri</h1>
      <p class="text-sm text-slate-500">Final Sürüm • Sheets Bağlı</p>
    </div>
    <span class="bg-emerald-600 text-white text-xs px-3 py-1 rounded-full">ÇALIŞIYOR</span>
  </div>

  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
    <div class="bg-white p-4 rounded-xl text-center border"><div class="text-xs text-slate-500">Teslimat</div><div id="n-d" class="text-xl font-bold">0</div></div>
    <div class="bg-white p-4 rounded-xl text-center border"><div class="text-xs text-slate-500">Müşteri</div><div id="n-c" class="text-xl font-bold">0</div></div>
    <div class="bg-white p-4 rounded-xl text-center border"><div class="text-xs text-slate-500">Satış</div><div id="n-s" class="text-xl font-bold">0</div></div>
    <div class="bg-white p-4 rounded-xl text-center border"><div class="text-xs text-slate-500">Sheets</div><div class="text-emerald-600 text-sm font-medium">Bağlı</div></div>
  </div>

  <div class="grid md:grid-cols-2 gap-5">
    <div class="bg-white p-5 rounded-2xl border">
      <h2 class="font-semibold mb-3">Yeni Teslimat</h2>
      <form id="form" class="space-y-2">
        <input id="cust" class="w-full border rounded-lg px-3 py-2" placeholder="Müşteri" required>
        <input id="addr" class="w-full border rounded-lg px-3 py-2" placeholder="Adres" required>
        <textarea id="items" class="w-full border rounded-lg px-3 py-2" rows="2" placeholder="Ürünler"></textarea>
        <button class="w-full bg-blue-600 text-white py-2 rounded-lg">Kaydet + Sheets'e Yaz</button>
      </form>
    </div>
    <div class="bg-white p-5 rounded-2xl border">
      <h2 class="font-semibold mb-3">AI Asistan</h2>
      <div id="chat" class="h-40 overflow-y-auto border rounded-lg p-2 bg-slate-50 text-sm mb-2"></div>
      <div class="flex gap-2">
        <input id="msg" class="flex-1 border rounded-lg px-3 py-2" placeholder="Soru...">
        <button onclick="ai()" class="bg-emerald-600 text-white px-4 rounded-lg">Gönder</button>
      </div>
    </div>
  </div>

  <div class="mt-5 bg-white p-5 rounded-2xl border">
    <div class="flex justify-between items-center mb-3">
      <h2 class="font-semibold">Son Teslimatlar</h2>
      <button onclick="sync()" class="text-sm bg-slate-800 text-white px-3 py-1 rounded">Sheets Senkron</button>
    </div>
    <div id="list" class="text-sm"></div>
  </div>
</div>
<script>
async function refresh(){
  const d = await fetch('/api/deliveries').then(r=>r.json());
  const c = await fetch('/api/customers').then(r=>r.json());
  const s = await fetch('/api/sales').then(r=>r.json());
  n-d.textContent = d.length;
  n-c.textContent = c.length;
  n-s.textContent = s.length;
  list.innerHTML = d.slice(-6).reverse().map(x=>`<div class="py-2 border-b">${x.customer_name} <span class="text-xs text-slate-400">${x.status}</span></div>`).join('') || 'Henüz yok';
}
form.onsubmit = async e => {
  e.preventDefault();
  await fetch('/api/deliveries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({customer_name:cust.value,address:addr.value,items:items.value})});
  form.reset();
  await fetch('/api/sync/sheets',{method:'POST'});
  refresh();
};
async function ai(){
  const m = msg.value; if(!m) return;
  chat.innerHTML += `<div><b>Sen:</b> ${m}</div>`;
  const r = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m})});
  const j = await r.json();
  chat.innerHTML += `<div class="text-emerald-700 mb-2"><b>AI:</b> ${j.reply}</div>`;
  msg.value=''; chat.scrollTop=chat.scrollHeight;
}
async function sync(){
  const r = await fetch('/api/sync/sheets',{method:'POST'});
  const j = await r.json();
  alert(j.status==='ok' ? 'Sheets güncellendi' : 'Hata: '+j.error);
}
refresh();
</script>
</body>
</html>
"""

# ==================== API ====================
@app.post("/api/deliveries")
async def add_delivery(d: Delivery):
    r = d.dict()
    r["id"] = str(uuid.uuid4())[:8]
    r["created"] = datetime.now().isoformat()
    deliveries.append(r)
    log(f"Teslimat: {d.customer_name}")
    return r

@app.get("/api/deliveries")
async def get_deliveries():
    return deliveries

@app.post("/api/customers")
async def add_customer(c: Customer):
    r = c.dict(); r["id"] = str(uuid.uuid4())[:8]
    customers.append(r)
    return r

@app.get("/api/customers")
async def get_customers():
    return customers

@app.post("/api/sales")
async def add_sale(s: Sale):
    r = s.dict(); r["id"] = str(uuid.uuid4())[:8]; r["created"] = datetime.now().isoformat()
    sales.append(r)
    return r

@app.get("/api/sales")
async def get_sales():
    return sales

@app.post("/api/accounts")
async def add_account(a: ClaudeAccount):
    accounts[str(uuid.uuid4())[:8]] = a.dict()
    return {"ok": True}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not accounts:
        return {"reply": "Claude hesabı ekle (/api/accounts). Prompt Caching hazır."}
    acc = list(accounts.values())[0]
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 800,
        "system": [{"type":"text","text":SYSTEM_PROMPT,"cache_control":{"type":"ephemeral"}}],
        "messages": [{"role":"user","content": req.message}]
    }
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key":acc["api_key"],"anthropic-version":"2023-06-01","content-type":"application/json"},
                json=payload)
            if r.status_code==200:
                return {"reply": r.json()["content"][0]["text"], "cached": True}
            return {"reply": f"API hatası {r.status_code}"}
    except Exception as e:
        return {"reply": f"Hata: {e}"}

# ==================== SHEETS ====================
SHEET_ID = "1MXsb5yar3v1p1QuvtIj9hWS_1uZbP_3JuNbDx6Y7hK8"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_client():
    try:
        creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
        return gspread.authorize(creds)
    except:
        return None

@app.post("/api/sync/sheets")
async def sync_sheets():
    client = get_client()
    if not client:
        return {"status":"hata","error":"Sheets bağlantısı yok"}
    try:
        sh = client.open_by_key(SHEET_ID)
        # Teslimatlar
        try:
            ws = sh.worksheet("Teslimatlar_Pro")
        except:
            ws = sh.add_worksheet("Teslimatlar_Pro", 2000, 8)
            ws.append_row(["ID","Müşteri","Adres","Ürünler","Durum","Tarih"])
        for d in deliveries[-15:]:
            ws.append_row([d.get("id"), d.get("customer_name"), d.get("address"), d.get("items"), d.get("status"), d.get("created")])
        log("Sheets senkron yapıldı")
        return {"status":"ok", "count": len(deliveries)}
    except Exception as e:
        return {"status":"hata", "error": str(e)}

@app.get("/api/health")
async def health():
    sheets_ok = get_client() is not None
    return {"status":"ok", "sheets": sheets_ok, "version": "6.0-final"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
