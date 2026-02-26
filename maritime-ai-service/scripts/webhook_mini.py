"""Minimal FastAPI webhook server for Facebook Messenger verification + message logging."""
import sys, os, json, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("webhook")

VERIFY_TOKEN = "wiii_fb_verify_s3cr3t_2026"
app = FastAPI()


@app.get("/api/v1/messenger/webhook")
async def verify(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("[OK] Webhook verified! Challenge: %s", hub_challenge)
        return PlainTextResponse(hub_challenge)
    return PlainTextResponse("Verification failed", status_code=403)


@app.post("/api/v1/messenger/webhook")
async def incoming(request: Request):
    body = await request.json()
    logger.info("[WEBHOOK] Received: %s", json.dumps(body, ensure_ascii=False)[:500])

    for entry in body.get("entry", []):
        for event in entry.get("messaging", []):
            sender = event.get("sender", {}).get("id", "?")
            text = event.get("message", {}).get("text", "")
            logger.info("[MESSAGE] From %s: %s", sender, text)

    return {"status": "ok"}


@app.get("/")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
