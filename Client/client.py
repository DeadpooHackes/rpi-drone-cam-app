# client_mjpeg.py (Raspberry Pi)
import socket
import subprocess

SERVER_IP = input("Enter server IP: ").strip()
PORT = 5001

# Connect to the server
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((SERVER_IP, PORT))
print("✅ Connected to server.")

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

try:
    while True:
        data = proc.stdout.read(4096)
        if not data:
            break
        sock.sendall(data)
except KeyboardInterrupt:
    print("🔌 Stopping stream...")
finally:
    proc.terminate()
    sock.close()