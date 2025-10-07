# file: main.py
import time, hmac, hashlib, base64, json
from fastapi import FastAPI, HTTPException
import httpx
from urllib.parse import urlencode

API_BASE = "https://api.bithumb.com"
API_KEY = "1deea37ce554fffa65601bbbcf0c77ca8dfe2a662bacee"
API_SECRET = "MjAxYzg0MjZjZmMyMGY5N2E4N2VlMjUxZmNmODE2MTAxZGI5YzIwMzc5YzA4ZmY2MjU2MDI4YWVlZWMxMQ=="
app = FastAPI()

BITHUMB_ALL_KRW = "https://api.bithumb.com/public/ticker/ALL_KRW"

@app.get("/coins")
async def coins():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(BITHUMB_ALL_KRW)
            r.raise_for_status()
            data = r.json()
        if data.get("status") != "0000" or "data" not in data:
            raise ValueError("Unexpected response")
        symbols = [k for k in data["data"].keys() if k != "date"]
        return {"market": "KRW", "count": len(symbols), "symbols": symbols}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

def canonical_json(d: dict) -> str:
    return json.dumps({k: d[k] for k in sorted(d.keys())}, separators=(',', ':'))

def sign_v2(method: str, path: str, canonical: str, ts: str) -> str:
    payload = f"{method.upper()}\n{path}\n{canonical}\n{ts}"
    digest = hmac.new(API_SECRET.encode(), payload.encode(), hashlib.sha512).digest()
    return base64.b64encode(digest).decode()

async def v2_private(method: str, path: str, params: dict | None = None):
    params = params or {}
    ts = str(int(time.time() * 1000))
    headers = {
        "X-API-KEY": API_KEY,
        "X-API-SIGNATURE": "",
        "X-API-TIMESTAMP": ts,
    }

    url = f"{API_BASE}{path}"
    canonical = ""
    data = None

    if method.upper() == "GET":
        # 정렬 쿼리
        from urllib.parse import urlencode
        q = urlencode(sorted(params.items(), key=lambda x: x[0]))
        canonical = q
        if q:
            url = f"{url}?{q}"
    else:
        canonical = canonical_json(params)
        data = canonical
        headers["Content-Type"] = "application/json"

    headers["X-API-SIGNATURE"] = sign_v2(method, path, canonical, ts)

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.request(method.upper(), url, headers=headers, data=data)
        r.raise_for_status()
        j = r.json()

    if j.get("status") and j["status"] != "0000":
        raise HTTPException(status_code=502, detail=f"Bithumb error: {j}")
    return j

@app.get("/wallet/coins")
async def wallet_coins():
    try:
        # 문서에 맞는 v2 경로/파라미터 확인 필요
        resp = await v2_private("POST", "/v2/info/balance", {"currency": "ALL"})
        d = resp.get("data", resp)
        coins = []
        for k, v in d.items():
            if k.startswith("total_"):
                base = k[len("total_"):]
                total = float(v or 0)
                if total > 0:
                    coins.append({
                        "symbol": base.upper(),
                        "total": total,
                        "available": float(d.get(f"available_{base}", 0) or 0),
                        "in_use": float(d.get(f"in_use_{base}", 0) or 0),
                    })
        coins.sort(key=lambda x: x["total"], reverse=True)
        return {"count": len(coins), "coins": coins}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))