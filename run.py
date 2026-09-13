import uvicorn
import socket
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def get_ip_addresses():
    ips = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        primary = s.getsockname()[0]
        s.close()
        if primary not in ips:
            ips.insert(0, primary)
    except Exception:
        pass
        
    return ips

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)
    sys.path.insert(0, current_dir)
    
    port = 8000
    ips = get_ip_addresses()
    
    print("\n" + "="*60)
    print("      [+] KOPI BANK - SERVER STARTED [+]")
    print("="*60)
    print(f" Localhost:               http://127.0.0.1:{port}")
    print(f" Android Emulator:        http://10.0.2.2:{port}")
    print(f" API Documentation (Docs): http://127.0.0.1:{port}/docs")
    print("-" * 60)
    print(" Wi-Fi IP addresses for friends:")
    for ip in ips:
        print(f"   -> http://{ip}:{port}")
    print("="*60 + "\n")
    
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
