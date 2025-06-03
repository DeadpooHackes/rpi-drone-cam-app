# client_mjpeg.py (Raspberry Pi)
import socket
import subprocess
import time

PORT = 5001
RECONNECT_DELAY = 5  # seconds between reconnect attempts

def get_server_address():
    print("📡 Enter connection method:")
    print(" 1. Direct IP")
    print(" 2. Hosted Link (e.g., ngrok or Cloudflare Tunnel)")
    choice = input("Select option (1/2): ").strip()

    if choice == "1":
        return input("Enter server IP: ").strip()
    elif choice == "2":
        host = input("Enter host link (without http/https): ").strip()
        try:
            ip = socket.gethostbyname(host)
            print(f"✅ Resolved {host} to {ip}")
            return ip
        except socket.gaierror:
            print("❌ Could not resolve hostname.")
            return None
    else:
        print("❌ Invalid option.")
        return None

def start_stream(sock):
    # Start libcamera-vid to output MJPEG to stdout
    cmd = [
        "libcamera-vid",
        "-t", "0",  # no timeout
        "--width", "640",
        "--height", "480",
        "--codec", "mjpeg",
        "-o", "-"  # output to stdout
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    if proc.poll() is not None:
        print("❌ Failed to start libcamera-vid.")
        return

    try:
        while True:
            data = proc.stdout.read(4096)
            if not data:
                break
            try:
                sock.sendall(data)
            except socket.error as e:
                print(f"⚠️ Socket error: {e}")
                break
    except KeyboardInterrupt:
        print("🔌 Stream manually stopped.")
    finally:
        proc.terminate()
        sock.close()

def main():
    while True:
        server_ip = None
        while not server_ip:
            server_ip = get_server_address()

        try:
            print(f"🔗 Connecting to {server_ip}:{PORT} ...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((server_ip, PORT))
            print("✅ Connected to server.")
            start_stream(sock)
        except (socket.error, KeyboardInterrupt) as e:
            print(f"❌ Connection error: {e}")
            print(f"🔄 Reconnecting in {RECONNECT_DELAY} seconds...")
            time.sleep(RECONNECT_DELAY)

if __name__ == "__main__":
    main()
