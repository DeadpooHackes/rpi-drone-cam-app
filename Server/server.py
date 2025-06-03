# server.py (Windows PC)
import socket
import cv2
import numpy as np
import threading
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import time

HOST = ''
PORT = 5001

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except:
        return '127.0.0.1'
    finally:
        s.close()

class MJPEGServerApp:
    def __init__(self, master):
        self.master = master
        master.title("📷 RPi Video Stream")

        self.label = ttk.Label(master)
        self.label.pack()

        self.record_button = ttk.Button(master, text="⏺ Start Recording", command=self.toggle_recording)
        self.record_button.pack(pady=10)

        self.recording = False
        self.out = None
        self.frame_size = (640, 480)
        self.fps = 20

        self.buffer = b''
        self.latest_frame = None  # ✅ FIXED: define it before update_frame()

        threading.Thread(target=self.start_server, daemon=True).start()
        self.update_frame()

    def toggle_recording(self):
        if not self.recording:
            filename = f"recording_{int(time.time())}.avi"
            self.out = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'XVID'), self.fps, self.frame_size)
            self.record_button.config(text="⏹ Stop Recording")
            self.recording = True
        else:
            self.recording = False
            if self.out:
                self.out.release()
                self.out = None
            self.record_button.config(text="⏺ Start Recording")

    def start_server(self):
        print(f"📡 Server running on: {get_local_ip()}:{PORT}")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((HOST, PORT))
        server_socket.listen(1)

        conn, addr = server_socket.accept()
        print(f"✅ Connected by {addr}")

        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                self.buffer += data

                # Extract JPEG frames
                while b'\xff\xd8' in self.buffer and b'\xff\xd9' in self.buffer:
                    start = self.buffer.find(b'\xff\xd8')
                    end = self.buffer.find(b'\xff\xd9') + 2
                    jpg = self.buffer[start:end]
                    self.buffer = self.buffer[end:]

                    img_array = np.frombuffer(jpg, dtype=np.uint8)
                    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                    if frame is not None:
                        self.latest_frame = frame
            except Exception as e:
                print("❌ Error:", e)
                break

        conn.close()
        server_socket.close()

    def update_frame(self):
        if self.latest_frame is not None:
            # Convert to RGB and display using tkinter
            frame_rgb = cv2.cvtColor(self.latest_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.label.imgtk = imgtk
            self.label.configure(image=imgtk)

            # Save if recording
            if self.recording and self.out:
                self.out.write(self.latest_frame)

        self.master.after(10, self.update_frame)

if __name__ == "__main__":
    root = tk.Tk()
    app = MJPEGServerApp(root)
    root.mainloop()
