import socket
import cv2
import numpy as np
import threading
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from pyngrok import ngrok
import time
import os
from flask import Flask, Response, render_template_string

# Configuration
HOST = ''
PORT = 5001  # Socket server port
HTTP_PORT = 8080  # HTTP camera viewer port

# Globals for HTTP stream
latest_frame = None
rotation_angle = 0

# Flask App for MJPEG viewer
app_flask = Flask(__name__)

@app_flask.route('/')
def index():
    return render_template_string('''
        <html>
<head>
    <title>RPi Camera</title>
    <style>
        body { text-align: center; font-family: Arial, sans-serif; }
        #video-container { display: inline-block; position: relative; }
        #fullview-btn {
            margin-top: 10px;
            padding: 8px 16px;
            font-size: 16px;
            cursor: pointer;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <h2>RPi Camera Stream [created by Tarun Sharma]</h2>
    <div id="video-container">
        <img id="video-stream" src="/video" width="640" />
    </div>
    <br>
    <button id="fullview-btn" onclick="toggleFullScreen()">Full View</button>

    <script>
        function toggleFullScreen() {
            let img = document.getElementById("video-stream");
            if (img.requestFullscreen) {
                img.requestFullscreen();
            } else if (img.mozRequestFullScreen) { // Firefox
                img.mozRequestFullScreen();
            } else if (img.webkitRequestFullscreen) { // Chrome, Safari, Opera
                img.webkitRequestFullscreen();
            } else if (img.msRequestFullscreen) { // IE/Edge
                img.msRequestFullscreen();
            }
        }
    </script>
</body>
</html>
    ''')

@app_flask.route('/video')
def video_feed():
    def generate():
        global latest_frame, rotation_angle
        while True:
            if latest_frame is not None:
                frame = latest_frame.copy()
                for _ in range(rotation_angle // 90):
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                ret, jpeg = cv2.imencode('.jpg', frame)
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(0.05)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

def start_http_server():
    app_flask.run(host="0.0.0.0", port=HTTP_PORT, debug=False, threaded=True)

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

        try:
            master.iconbitmap("icon.ico")
        except:
            print("⚠️ icon.ico not found")

        top_frame = ttk.Frame(master)
        top_frame.pack(pady=5)

        try:
            logo = Image.open("logo.png").resize((32, 32))
            self.logo_img = ImageTk.PhotoImage(logo)
            logo_label = tk.Label(top_frame, image=self.logo_img)
            logo_label.pack(side=tk.LEFT)
        except:
            print("⚠️ logo.png not found")

        title_label = ttk.Label(top_frame, text="RPi Stream Viewer", font=("Helvetica", 14, "bold"))
        title_label.pack(side=tk.LEFT, padx=10)

        self.label = ttk.Label(master)
        self.label.pack()

        self.status_label = ttk.Label(master, text="Starting local server...", foreground="blue")
        self.status_label.pack(pady=5)

        self.local_ip_var = tk.StringVar()
        self.ngrok_ip_var = tk.StringVar()

        ip_frame = ttk.Frame(master)
        ip_frame.pack(pady=5, padx=10)

        ttk.Label(ip_frame, text="🌐 Local:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(ip_frame, textvariable=self.local_ip_var).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Button(ip_frame, text="Copy Full IP", command=self.copy_full_ip).grid(row=0, column=2, padx=5, sticky="ew")

        ttk.Label(ip_frame, text="☁️ Ngrok:").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Label(ip_frame, textvariable=self.ngrok_ip_var).grid(row=1, column=1, sticky="w", padx=5)
        self.ngrok_button = ttk.Button(ip_frame, text="▶ Start Ngrok", command=self.toggle_ngrok)
        self.ngrok_button.grid(row=1, column=2, padx=5, sticky="ew")

        self.camera_link_button = ttk.Button(ip_frame, text="📡 Camera Hosting Link", command=self.copy_camera_link)
        self.camera_link_button.grid(row=2, column=2, padx=5, sticky="ew")

        control_frame = ttk.Frame(master)
        control_frame.pack(pady=10)

        self.record_button = ttk.Button(control_frame, text="⏺ Start Recording", command=self.toggle_recording)
        self.record_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.picture_button = ttk.Button(control_frame, text="📸 Take Picture", command=self.take_picture)
        self.picture_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.rotate_button = ttk.Button(control_frame, text="🔄 Rotate View", command=self.rotate_camera)
        self.rotate_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        self.footer_label = ttk.Label(master, text="Created by Tarun Sharma", foreground="gray")
        self.footer_label.pack(pady=5)

        control_frame.grid_columnconfigure(0, weight=1)
        control_frame.grid_columnconfigure(1, weight=1)
        control_frame.grid_columnconfigure(2, weight=1)
        ip_frame.grid_columnconfigure(0, weight=1)
        ip_frame.grid_columnconfigure(1, weight=1)
        ip_frame.grid_columnconfigure(2, weight=2)

        self.recording = False
        self.out = None
        self.frame_size = (640, 480)
        self.fps = 20

        self.buffer = b''
        self.latest_frame = None
        self.conn_alive = False
        self.rotation_angle = 0

        self.local_ip_var.set(f"{get_local_ip()}:{PORT}")

        threading.Thread(target=self.start_server, daemon=True).start()
        threading.Thread(target=start_http_server, daemon=True).start()
        self.update_frame()

        self.master.resizable(False, False)

    def set_status(self, msg, color="black"):
        self.status_label.config(text=msg, foreground=color)

    def copy_full_ip(self):
        full_ip = self.local_ip_var.get()
        self.master.clipboard_clear()
        self.master.clipboard_append(full_ip)
        self.set_status(f"📋 Copied: {full_ip}", "green")

    def copy_ngrok_url(self):
        ngrok_url = self.ngrok_ip_var.get().replace("tcp://", "")
        self.master.clipboard_clear()
        self.master.clipboard_append(ngrok_url)
        self.set_status(f"📋 Copied: {ngrok_url}", "green")

    def copy_camera_link(self):
        camera_link = f"http://{get_local_ip()}:{HTTP_PORT}/"
        self.master.clipboard_clear()
        self.master.clipboard_append(camera_link)
        self.set_status(f"📋 Copied: {camera_link}", "green")

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

    def take_picture(self):
        if self.latest_frame is not None:
            filename = f"snapshot_{int(time.time())}.jpg"
            cv2.imwrite(filename, self.latest_frame)
            self.set_status(f"📸 Saved: {filename}", "purple")
        else:
            self.set_status("⚠️ No image to save!", "red")

    def rotate_camera(self):
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self.set_status(f"🔄 View rotated {self.rotation_angle}°", "blue")

    def start_ngrok(self):
        try:
            tunnel = ngrok.connect(PORT, "tcp")
            url = tunnel.public_url.replace("tcp://", "")
            self.ngrok_ip_var.set(f"{url}")
            self.set_status("☁️ Ngrok connected", "blue")
        except Exception as e:
            self.set_status("❌ Ngrok error", "red")
            print("Ngrok error:", e)

    def toggle_ngrok(self):
        if self.ngrok_ip_var.get() == "":
            self.start_ngrok()
            self.ngrok_button.config(text="Copy Ngrok URL")
        else:
            self.copy_ngrok_url()

    def start_server(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen(1)

        while True:
            self.set_status("⏳ Waiting for connection...", "blue")
            try:
                conn, addr = server_socket.accept()
                self.conn_alive = True
                self.set_status(f"✅ Connected: {addr[0]}", "green")
                self.buffer = b''

                while True:
                    data = conn.recv(4096)
                    if not data:
                        raise Exception("Disconnected")
                    self.buffer += data

                    while b'\xff\xd8' in self.buffer and b'\xff\xd9' in self.buffer:
                        start = self.buffer.find(b'\xff\xd8')
                        end = self.buffer.find(b'\xff\xd9') + 2
                        jpg = self.buffer[start:end]
                        self.buffer = self.buffer[end:]

                        arr = np.frombuffer(jpg, dtype=np.uint8)
                        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if frame is not None:
                            self.latest_frame = frame
            except Exception as e:
                self.set_status("⚠️ Disconnected", "orange")
                self.latest_frame = None
                self.conn_alive = False
                time.sleep(1)

    def update_frame(self):
        global latest_frame, rotation_angle
        if self.latest_frame is not None:
            rotated_frame = self.latest_frame
            for _ in range(self.rotation_angle // 90):
                rotated_frame = cv2.rotate(rotated_frame, cv2.ROTATE_90_CLOCKWISE)

            rgb = cv2.cvtColor(rotated_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.label.imgtk = imgtk
            self.label.configure(image=imgtk)

            latest_frame = rotated_frame.copy()

            if self.recording and self.out:
                self.out.write(rotated_frame)
        else:
            if not self.conn_alive:
                self.label.configure(image='')

        self.master.after(10, self.update_frame)

if __name__ == "__main__":
    root = tk.Tk()
    app = MJPEGServerApp(root)
    root.mainloop()
