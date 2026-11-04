import os
import sys
import uvicorn

if __name__ == "__main__":
    port_str = os.environ.get("PORT", "8000")
    try:
        port = int(port_str)
    except (ValueError, TypeError):
        port = 8000
    
    print(f"[STARTUP] Launching MachineGuard FastAPI backend on 0.0.0.0:{port}...", flush=True)
    try:
        uvicorn.run("backend.app.main:app", host="0.0.0.0", port=port, log_level="info")
    except Exception as e:
        print(f"[FATAL] Server terminated with error: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
