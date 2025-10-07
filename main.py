# file: main.py
import jwt
import requests
import time, hmac, hashlib, base64, json
from fastapi import FastAPI, HTTPException
import httpx
import dotenv, os
import uuid

from urllib.parse import urlencode
dotenv.load_dotenv()
API_BASE = "https://api.bithumb.com"
ACCESS_KEY = os.getenv("BITHUMB_API_KEY", "NO_ACCESS_KEY")
SECRET_KEY = os.getenv("BITHUMB_API_SECRET_KEY", "NO_SECRET_KEY")

app = FastAPI()

BITHUMB_ALL_KRW = "https://api.bithumb.com/public/ticker/ALL_KRW"

def auth_headers():
    payload = {
        "access_key": ACCESS_KEY,
        "nonce": str(uuid.uuid4()),
        "timestamp": round(time.time() * 1000),
    }
    token = jwt.encode(payload, SECRET_KEY)
    return {"Authorization": f"Bearer {token}"}

def parse_balance_payload(payload):
    coins = []
    if isinstance(payload, dict):
        # 기존 키 접두사 방식
        for k, v in payload.items():
            if k.startswith("total_"):
                base = k[len("total_"):]
                try:
                    total = float(v or 0)
                except (TypeError, ValueError):
                    total = 0.0
                available = payload.get(f"available_{base}", 0)
                in_use = payload.get(f"in_use_{base}", 0)
                try:
                    available = float(available or 0)
                except (TypeError, ValueError):
                    available = 0.0
                try:
                    in_use = float(in_use or 0)
                except (TypeError, ValueError):
                    in_use = 0.0
                if total > 0 or available > 0 or in_use > 0:
                    coins.append({
                        "symbol": base.upper(),
                        "total": total,
                        "available": available,
                        "in_use": in_use,
                    })
    elif isinstance(payload, list):
        # 배열 형태: 각 원소가 코인별 정보일 수 있음
        # 가능한 필드명 패턴을 최대한 유연하게 매핑
        for item in payload:
            if not isinstance(item, dict):
                continue
            # 심볼 후보 키
            symbol = item.get("currency") or item.get("symbol") or item.get("coin")
            if not symbol:
            # 키가 없는 경우 스킵
                continue
            # 수량 후보 키
            total = item.get("total") or item.get("balance") or item.get("qty") or item.get("quantity")
            available = item.get("available") or item.get("available_balance") or item.get("free")
            avg_buy_price = item.get("avg_buy_price")
            in_use = item.get("in_use") or item.get("locked") or item.get("hold")
            # 숫자 변환
            def to_f(x):
                try:
                    return float(x or 0)
                except (TypeError, ValueError):
                    return 0.0
            entry = {
                "symbol": str(symbol).upper(),
                "total": to_f(total),
                "avg_buy_price": to_f(avg_buy_price),
                "available": to_f(available),
                "in_use": to_f(in_use),
            }
            # 전부 0인 경우는 스킵
            if entry["total"] > 0 or entry["available"] > 0 or entry["in_use"] > 0:
                coins.append(entry)

    # 정렬
    coins.sort(key=lambda x: x["total"], reverse=True)
    return coins

async def fetch_wallet_coins():
    url = f"{API_BASE}/v1/accounts"
    r = requests.get(url, headers=auth_headers(), timeout=10)
    r.raise_for_status()
    raw = r.json()
    if isinstance(raw, dict):
        if raw.get("status") and raw["status"] != "0000":
            raise RuntimeError(f"Bithumb error: {raw}")
        payload = raw.get("data", raw)
        return parse_balance_payload(payload)
    if isinstance(raw, list):
        return parse_balance_payload(raw)
    raise TypeError(f"Unexpected response type: {type(raw)}; content: {raw}")


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


@app.get("/wallet/coins")
async def wallet_coins():
    try:
        coins = await fetch_wallet_coins()
        return coins
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

