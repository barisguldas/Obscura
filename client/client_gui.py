import socket
import threading
import sys
import tkinter as tk
from tkinter import messagebox, filedialog
import tkinter.simpledialog as simpledialog
import customtkinter as ctk
import json
import struct
import base64
import uuid
import os
import io
import rsa
from PIL import Image, ImageTk, ImageDraw
from cryptography.fernet import Fernet
from stegano import lsb
import tkinter.scrolledtext as scrolledtext

ctk.set_appearance_mode("dark")

SHARED_KEY = b'vS-dG5rU4E9a7j5fV1qW_U3m0gBwZq_8rD8X4E5Vp1g='
cipher_suite = Fernet(SHARED_KEY)
DUMMY_IMAGE_PATH = 'assets/dummy.png'

BG_COLOR = "#1e1e2e"
FRAME_BG = "#181825"
ENTRY_BG = "#313244"
TEXT_FG = "#cdd6f4"
BTN_BG = "#89b4fa"
BTN_FG = "#11111b"
BTN_SUCCESS = "#a6e3a1"
BTN_WARN = "#f9e2af"
BTN_DANGER = "#f38ba8"
SELECT_BG = "#cba6f7"
SELECT_FG = "#11111b"
FONT_MAIN = ("Segoe UI", 12)

def make_circular(img, size=(128, 128)):
    img = img.resize(size, Image.Resampling.LANCZOS).convert("RGBA")
    
    # 3x çözünürlükte maske çizip küçülterek donanımsal Super Sample Anti-Aliasing (SSAA) elde ediyoruz
    mask_size = (size[0] * 3, size[1] * 3)
    mask = Image.new('L', mask_size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + mask_size, fill=255)
    mask = mask.resize(size, Image.Resampling.LANCZOS)
    
    result = Image.new('RGBA', size, (0, 0, 0, 0))
    result.paste(img, (0, 0), mask=mask)
    return result

def get_avatar_image(b64_str, size=(32, 32)):
    # CTkImage'nin High-DPI ekranlarda (Windows %125-150 ölçek) bozulmasını önlemek için 
    # arka planda 4 katı çözünürlükte render alıyoruz.
    render_size = (size[0] * 4, size[1] * 4)
    if not b64_str:
        img = Image.new('RGB', render_size, color=(44, 62, 80))
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    try:
        img_data = base64.b64decode(b64_str)
        img = Image.open(io.BytesIO(img_data)).convert("RGBA")
        circ = make_circular(img, size=render_size)
        return ctk.CTkImage(light_image=circ, dark_image=circ, size=size)
    except:
        img = Image.new('RGB', render_size, color=(44, 62, 80))
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)

class SelectableList(ctk.CTkScrollableFrame):
    def __init__(self, master, on_select=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_select = on_select
        self.selected_value = None
        self.buttons = []
        
    def clear(self):
        for btn in self.buttons:
            btn.destroy()
        self.buttons = []
        self.selected_value = None
        
    def add_item(self, text, image=None, value=None, text_color=TEXT_FG):
        val = value if value is not None else text
        btn = ctk.CTkButton(self, text=f"  {text}", image=image, anchor="w", fg_color="transparent", text_color=text_color, hover_color="#45475a", font=FONT_MAIN, height=40)
        
        def click_handler(v=val, b=btn):
            self.selected_value = v
            for ob in self.buttons: 
                ob.configure(fg_color="transparent")
                if hasattr(ob, "orig_color"): ob.configure(text_color=ob.orig_color)
            b.configure(fg_color=SELECT_BG, text_color=SELECT_FG)
            if self.on_select: self.on_select(v)
            
        btn.orig_color = text_color
        btn.configure(command=click_handler)
        btn.pack(fill="x", pady=2)
        self.buttons.append(btn)
        
    def get_selected(self):
        return self.selected_value

class ImageCropper(ctk.CTkToplevel):
    def __init__(self, master, image_path, on_crop_done):
        super().__init__(master)
        self.title("Görseli Kırp")
        self.geometry("600x650")
        self.attributes("-topmost", True)
        self.on_crop_done = on_crop_done
        
        self.orig_img = Image.open(image_path).convert("RGB")
        self.disp_img = self.orig_img.copy()
        self.disp_img.thumbnail((500, 500))
        self.ratio = self.orig_img.width / self.disp_img.width if self.disp_img.width > 0 else 1.0
        
        lbl = ctk.CTkLabel(self, text="Farenizle profil karesini seçin", font=("Segoe UI", 14, "bold"), text_color=TEXT_FG)
        lbl.pack(pady=10)
        
        self.canvas = tk.Canvas(self, width=self.disp_img.width, height=self.disp_img.height, cursor="cross", bg="#1e1e2e", bd=0, highlightthickness=0)
        self.canvas.pack(pady=10)
        
        self.tk_img = ImageTk.PhotoImage(self.disp_img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        
        self.rect_id = None
        self.start_x = self.start_y = 0
        self.cur_x = self.cur_y = 0
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        ctk.CTkButton(btn_frame, text="Kırp ve Kaydet", fg_color=BTN_SUCCESS, text_color=BTN_FG, font=("Segoe UI", 12, "bold"), command=self.crop).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="İptal", fg_color=BTN_DANGER, text_color=BTN_FG, font=("Segoe UI", 12, "bold"), command=self.destroy).pack(side="left", padx=10)
        
    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        if self.rect_id: self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="#a6e3a1", width=3, dash=(4,4))
        
    def on_drag(self, event):
        self.cur_x, self.cur_y = event.x, event.y
        size = max(abs(self.cur_x - self.start_x), abs(self.cur_y - self.start_y))
        x1, y1 = self.start_x, self.start_y
        x2 = self.start_x + (size if self.cur_x > self.start_x else -size)
        y2 = self.start_y + (size if self.cur_y > self.start_y else -size)
        
        x1, x2 = max(0, min(x1, self.disp_img.width)), max(0, min(x2, self.disp_img.width))
        y1, y2 = max(0, min(y1, self.disp_img.height)), max(0, min(y2, self.disp_img.height))
        self.canvas.coords(self.rect_id, x1, y1, x2, y2)
        
    def crop(self):
        if not self.rect_id: return
        coords = self.canvas.coords(self.rect_id)
        if not coords or len(coords) != 4: return
        x1, y1, x2, y2 = coords
        left, right = min(x1, x2), max(x1, x2)
        top, bottom = min(y1, y2), max(y1, y2)
        
        if right - left < 10 or bottom - top < 10:
            messagebox.showerror("Hata", "Çok küçük bir alan seçtiniz!")
            return
            
        crop_box = (int(left * self.ratio), int(top * self.ratio), int(right * self.ratio), int(bottom * self.ratio))
        cropped = self.orig_img.crop(crop_box)
        self.on_crop_done(cropped)
        self.destroy()

class ChatClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.client = None
        self.username = ""
        self.running = False
        self.client_id = str(uuid.uuid4())[:8]
        self.chat_history = {} 
        self.active_chat_friend = None
        self.is_group_chat = False
        self.online_users = []
        self.groups_info = {}
        self.public_keys = {}
        self.server_avatars = {}
        self.carrier_image = DUMMY_IMAGE_PATH
        self.unread_chats = set()
        self.chat_images = []
        self.friends = []
        
        os.makedirs('assets', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        
        if not os.path.exists(DUMMY_IMAGE_PATH):
            img = Image.new('RGB', (200, 200), color=(44, 62, 80))
            img.save(DUMMY_IMAGE_PATH)

        self.root = ctk.CTk()
        self.root.title("Obscura")
        self.root.geometry("1000x700")
        self.root.minsize(850, 550)
        self.root.configure(fg_color=BG_COLOR)
        
        self.auth_frame = ctk.CTkFrame(self.root, fg_color=BG_COLOR, corner_radius=0)
        self.dashboard_frame = ctk.CTkFrame(self.root, fg_color=BG_COLOR, corner_radius=0)
        self.settings_frame = ctk.CTkFrame(self.root, fg_color=BG_COLOR, corner_radius=0)
        self.contacts_frame = ctk.CTkFrame(self.root, fg_color=BG_COLOR, corner_radius=0)
        
        self.build_auth_screen()
        self.build_dashboard_screen()
        self.build_settings_screen()
        self.build_contacts_screen()
        
        self.show_frame(self.auth_frame)
        
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        self.root.mainloop()

    def show_frame(self, frame):
        if hasattr(self, 'profile_menu') and self.profile_menu.winfo_ismapped():
            self.profile_menu.place_forget()
            
        self.auth_frame.pack_forget()
        self.dashboard_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.contacts_frame.pack_forget()
        frame.pack(fill="both", expand=True)

    def load_settings(self):
        self.carrier_image = DUMMY_IMAGE_PATH
        try:
            with open(f"data/settings_{self.username}.json", 'r') as f:
                st = json.load(f)
                img_path = st.get("carrier_image", "")
                if os.path.exists(img_path):
                    self.carrier_image = img_path
        except: pass
        self.refresh_preview()
        self.update_my_profile_ui()

    def refresh_preview(self):
        if hasattr(self, 'preview_label'):
            try:
                if os.path.exists(self.carrier_image):
                    img = Image.open(self.carrier_image).convert("RGB")
                    # Daha keskin görünüm için 400x400 maskeliyoruz
                    circ = make_circular(img, size=(400, 400))
                    ctk_img = ctk.CTkImage(light_image=circ, dark_image=circ, size=(100, 100))
                    self.preview_label.configure(image=ctk_img)
            except: pass

    def get_tk_avatar(self, username, size=(28, 28)):
        render_size = (size[0]*3, size[1]*3)
        b64_str = self.server_avatars.get(username)
        
        if not b64_str and username == self.username:
            try:
                img = Image.open(self.carrier_image).convert("RGB")
                circ = make_circular(img, size=render_size)
                circ = circ.resize(size, Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(circ)
            except: pass
            
        if b64_str:
            try:
                img_data = base64.b64decode(b64_str)
                img = Image.open(io.BytesIO(img_data)).convert("RGBA")
                circ = make_circular(img, size=render_size)
                circ = circ.resize(size, Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(circ)
            except: pass
            
        img = Image.new('RGB', render_size, color=(44, 62, 80))
        circ = make_circular(img, size=render_size)
        circ = circ.resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(circ)

    def render_message(self, sender_raw, text, tag):
        real_user = sender_raw
        if real_user.startswith("🖼️🔒 "): real_user = real_user.replace("🖼️🔒 ", "")
        elif real_user == "Sen": real_user = self.username
            
        img_tk = self.get_tk_avatar(real_user, size=(28, 28))
        self.chat_images.append(img_tk)
        
        display_name = "Sen" if real_user == self.username else real_user
        
        self.chat_text_area.image_create('end', image=img_tk, align="center")
        self.chat_text_area.insert('end', f"  {display_name}: {text}\n\n", tag)

    def save_settings(self):
        try:
            with open(f"data/settings_{self.username}.json", 'w') as f:
                json.dump({"carrier_image": self.carrier_image}, f)
        except: pass

    def get_history_file(self):
        return f"data/history_{self.username}.dat"

    def load_history(self):
        try:
            filename = self.get_history_file()
            if os.path.exists(filename):
                with open(filename, 'rb') as f:
                    encrypted_data = f.read()
                decrypted_data = cipher_suite.decrypt(encrypted_data).decode('utf-8')
                self.chat_history = json.loads(decrypted_data)
            else:
                self.chat_history = {}
        except Exception:
            self.chat_history = {}

    def save_history(self):
        try:
            filename = self.get_history_file()
            json_str = json.dumps(self.chat_history)
            encrypted_data = cipher_suite.encrypt(json_str.encode('utf-8'))
            with open(filename, 'wb') as f:
                f.write(encrypted_data)
        except Exception: pass

    def add_to_history(self, chat_target, sender_label, text, tag):
        if chat_target not in self.chat_history:
            self.chat_history[chat_target] = []
        self.chat_history[chat_target].append({"sender": sender_label, "text": text, "tag": tag})
        self.save_history()

    def mark_unread(self, target):
        self.unread_chats.add(target)
        self.send_msg({"type": "GET_DASHBOARD"})

    def send_msg(self, msg_dict):
        try:
            data = json.dumps(msg_dict).encode('utf-8')
            packet = struct.pack('!I', len(data)) + data
            self.client.sendall(packet)
        except: pass

    def receive_all(self, n):
        data = bytearray()
        while len(data) < n:
            packet = self.client.recv(n - len(data))
            if not packet: return None
            data.extend(packet)
        return bytes(data)

    def force_logout_on_disconnect(self):
        messagebox.showerror("Bağlantı Koptu", "Sunucu ile bağlantınız kesildi!")
        self.logout()

    def listen_server(self):
        while self.running:
            try:
                raw_msglen = self.receive_all(4)
                if not raw_msglen: break
                msglen = struct.unpack('!I', raw_msglen)[0]
                data = self.receive_all(msglen)
                if not data: break
                
                msg = json.loads(data.decode('utf-8'))
                self.root.after(0, self.handle_server_msg, msg)
            except: break
        
        if self.running:
            self.root.after(0, self.force_logout_on_disconnect)

    def handle_server_msg(self, msg):
        cmd = msg.get('type')
        if cmd == 'REFRESH_DASHBOARD':
            self.send_msg({"type": "GET_DASHBOARD"})
        elif cmd == 'DASHBOARD_DATA':
            self.update_lists(
                msg.get('users', []), 
                msg.get('requests', []), 
                msg.get('friends', []), 
                msg.get('online_users', []),
                msg.get('groups', []),
                msg.get('groups_info', {}),
                msg.get('group_requests', []),
                msg.get('public_keys', {}),
                msg.get('avatars', {})
            )
        elif cmd == 'NEW_REQUEST': self.send_msg({"type": "GET_DASHBOARD"})
        elif cmd == 'NEW_FRIEND': self.send_msg({"type": "GET_DASHBOARD"})
        elif cmd == 'NEW_GROUP_REQUEST': self.send_msg({"type": "GET_DASHBOARD"})
        elif cmd == 'RECEIVE_MESSAGE':
            self.process_incoming_image(msg.get('from'), msg.get('payload_b64'))
        elif cmd == 'RECEIVE_GROUP_MESSAGE':
            self.process_incoming_group_image(msg.get('group'), msg.get('from'), msg.get('payload_b64'))
        elif cmd == 'CHANGE_PASSWORD_REPLY':
            if msg.get("status") == "SUCCESS": messagebox.showinfo("Başarılı", "Şifreniz güncellendi!")
            else: messagebox.showerror("Hata", msg.get("message"))
        elif cmd == 'ERROR': messagebox.showerror("Hata", msg.get("message"))
        elif cmd == 'INFO': messagebox.showinfo("Bilgi", msg.get("message"))

    def build_auth_screen(self):
        inner = ctk.CTkFrame(self.auth_frame, fg_color=FRAME_BG, corner_radius=15)
        inner.place(relx=0.5, rely=0.5, anchor="center") 
        
        ctk.CTkLabel(inner, text="Obscura", font=("Segoe UI", 28, "bold"), text_color=BTN_BG).pack(pady=(30, 20), padx=50)
        
        self.ip_entry = ctk.CTkEntry(inner, placeholder_text="Sunucu IP", font=("Segoe UI", 14), width=250, height=40, corner_radius=8, fg_color=ENTRY_BG, border_width=0)
        self.ip_entry.insert(0, self.host)
        self.ip_entry.pack(pady=(10, 10), padx=30)
        
        self.u_entry = ctk.CTkEntry(inner, placeholder_text="Kullanıcı Adı", font=("Segoe UI", 14), width=250, height=40, corner_radius=8, fg_color=ENTRY_BG, border_width=0)
        self.u_entry.pack(pady=(5, 10), padx=30)
        
        self.p_entry = ctk.CTkEntry(inner, placeholder_text="Şifre", show="*", font=("Segoe UI", 14), width=250, height=40, corner_radius=8, fg_color=ENTRY_BG, border_width=0)
        self.p_entry.pack(pady=(5, 30), padx=30)
        
        btn_login = ctk.CTkButton(inner, text="Giriş Yap", font=("Segoe UI", 14, "bold"), fg_color=BTN_BG, text_color=BTN_FG, width=250, height=40, corner_radius=8, command=lambda: self.auth("LOGIN"))
        btn_login.pack(pady=5, padx=30)
        
        btn_reg = ctk.CTkButton(inner, text="Kayıt Ol", font=("Segoe UI", 14, "bold"), fg_color=BTN_SUCCESS, text_color=BTN_FG, width=250, height=40, corner_radius=8, command=lambda: self.auth("REGISTER"))
        btn_reg.pack(pady=(5, 30), padx=30)

    def auth(self, action):
        self.host = self.ip_entry.get().strip()
        u = self.u_entry.get().strip()
        p = self.p_entry.get().strip()
        if not u or not p or not self.host: return
        
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((self.host, self.port))
            self.send_msg({"type": action, "username": u, "password": p})
            
            raw_msglen = self.receive_all(4)
            msglen = struct.unpack('!I', raw_msglen)[0]
            data = self.receive_all(msglen)
            resp = json.loads(data.decode('utf-8'))
            
            if resp.get('status') == 'SUCCESS':
                self.username = u
                self.running = True
                self.load_history()
                self.load_settings()
                
                priv_file = f"data/private_{self.username}.pem"
                pub_file = f"data/public_{self.username}.pem"
                if not os.path.exists(priv_file):
                    pub_key, priv_key = rsa.newkeys(1024)
                    with open(pub_file, 'wb') as f: f.write(pub_key.save_pkcs1())
                    with open(priv_file, 'wb') as f: f.write(priv_key.save_pkcs1())
                else:
                    with open(pub_file, 'rb') as f: pub_key = rsa.PublicKey.load_pkcs1(f.read())
                    with open(priv_file, 'rb') as f: priv_key = rsa.PrivateKey.load_pkcs1(f.read())
                self.private_key = priv_key
                self.public_key = pub_key
                
                self.send_msg({"type": "UPLOAD_PUBLIC_KEY", "public_key": pub_key.save_pkcs1().decode('utf-8')})
                self.lbl_current_image.configure(text=f"Mevcut Görsel: {self.carrier_image}")
                
                self.root.title(f"Obscura | {self.username}")
                self.update_my_profile_ui()
                self.show_frame(self.dashboard_frame)
                
                threading.Thread(target=self.listen_server, daemon=True).start()
                self.send_msg({"type": "GET_DASHBOARD"})
            else:
                messagebox.showerror("Hata", resp.get('message'))
                self.client.close()
        except Exception as e:
            messagebox.showerror("Hata", f"Bağlantı sorunu: {e}")

    def logout(self):
        if hasattr(self, 'profile_menu') and self.profile_menu.winfo_ismapped():
            self.profile_menu.place_forget()
        self.running = False
        if self.client:
            try: self.client.close()
            except: pass
            self.client = None
            
        self.username = ""
        self.chat_history = {}
        self.groups_info = {}
        self.public_keys = {}
        self.server_avatars = {}
        self.online_users = []
        self.unread_chats.clear()
        self.friends.clear()
        
        self.u_entry.delete(0, tk.END)
        self.p_entry.delete(0, tk.END)
        self.list_friends.clear()
        self.list_users.clear()
        self.list_requests.clear()
        
        self.active_chat_friend = None
        self.chat_container.pack_forget()
        self.placeholder_frame.pack(fill="both", expand=True)
        
        self.root.title("Obscura")
        self.show_frame(self.auth_frame)

    def build_settings_screen(self):
        top_bar = ctk.CTkFrame(self.settings_frame, fg_color=FRAME_BG, height=60, corner_radius=0)
        top_bar.pack(side="top", fill="x")
        
        btn_back = ctk.CTkButton(top_bar, text="◄ Menüye Dön", font=("Segoe UI", 12, "bold"), fg_color=BTN_BG, text_color=BTN_FG, width=120, height=35, corner_radius=8, command=lambda: self.show_frame(self.dashboard_frame))
        btn_back.pack(side="left", padx=15, pady=12)
        
        ctk.CTkLabel(top_bar, text="Ayarlar", font=("Segoe UI", 16, "bold"), text_color=TEXT_FG).pack(side="left", padx=15, pady=12)
        
        body = ctk.CTkFrame(self.settings_frame, fg_color=BG_COLOR)
        body.pack(fill="both", expand=True, padx=40, pady=40)
        
        pw_frame = ctk.CTkFrame(body, fg_color=FRAME_BG, corner_radius=15)
        pw_frame.pack(fill="x", pady=10, ipady=15)
        
        ctk.CTkLabel(pw_frame, text="Şifre Değiştir", font=("Segoe UI", 16, "bold"), text_color=TEXT_FG).pack(pady=(15, 10))
        self.old_pw_entry = ctk.CTkEntry(pw_frame, placeholder_text="Eski Şifre", show="*", font=("Segoe UI", 14), width=250, height=35, corner_radius=8, fg_color=ENTRY_BG, border_width=0)
        self.old_pw_entry.pack(pady=5)
        self.new_pw_entry = ctk.CTkEntry(pw_frame, placeholder_text="Yeni Şifre", show="*", font=("Segoe UI", 14), width=250, height=35, corner_radius=8, fg_color=ENTRY_BG, border_width=0)
        self.new_pw_entry.pack(pady=5)
        btn_pw = ctk.CTkButton(pw_frame, text="Şifreyi Güncelle", font=("Segoe UI", 12, "bold"), fg_color=BTN_WARN, text_color=BTN_FG, width=150, height=35, corner_radius=8, command=self.change_password)
        btn_pw.pack(pady=10)
        
        img_frame = ctk.CTkFrame(body, fg_color=FRAME_BG, corner_radius=15)
        img_frame.pack(fill="x", pady=10, ipady=15)
        
        ctk.CTkLabel(img_frame, text="Profil & Steganografi Görseli", font=("Segoe UI", 16, "bold"), text_color=TEXT_FG).pack(pady=(15, 10))
        
        self.preview_label = ctk.CTkLabel(img_frame, text="")
        self.preview_label.pack(pady=10)
        
        self.lbl_current_image = ctk.CTkLabel(img_frame, text="Mevcut Görsel: dummy.png", font=("Segoe UI", 12), text_color="#a6adc8")
        self.lbl_current_image.pack(pady=5)
        
        btn_img = ctk.CTkButton(img_frame, text="Yeni Görsel Seç (.jpg / .png)", font=("Segoe UI", 12, "bold"), fg_color=BTN_SUCCESS, text_color=BTN_FG, width=200, height=35, corner_radius=8, command=self.select_carrier_image)
        btn_img.pack(pady=10)
        
        self.refresh_preview()

    def change_password(self):
        old_p = self.old_pw_entry.get()
        new_p = self.new_pw_entry.get()
        if old_p and new_p:
            self.send_msg({"type": "CHANGE_PASSWORD", "old_password": old_p, "new_password": new_p})
            self.old_pw_entry.delete(0, tk.END)
            self.new_pw_entry.delete(0, tk.END)
            
    def select_carrier_image(self):
        filepath = filedialog.askopenfilename(filetypes=[("Görsel Dosyaları", "*.png;*.jpg;*.jpeg;*.bmp")])
        if filepath:
            ImageCropper(self.root, filepath, self.handle_crop_done)

    def handle_crop_done(self, cropped_img):
        save_path = f"assets/carrier_{self.username}.png"
        cropped_img.thumbnail((800, 800))
        cropped_img.save(save_path, "PNG")
        self.carrier_image = save_path
        self.save_settings()
        self.lbl_current_image.configure(text=f"Mevcut Görsel: {self.carrier_image}")
        self.refresh_preview()
        self.update_my_profile_ui()
        
        # Ağ paketini küçültmek ve çözünürlüğü artırmak için RGB'ye çevirip JPEG kullanıyoruz
        avatar_img = cropped_img.resize((256, 256), Image.Resampling.LANCZOS).convert("RGB")
        buf = io.BytesIO()
        avatar_img.save(buf, format="JPEG", quality=85)
        b64_avatar = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        self.send_msg({"type": "UPLOAD_AVATAR", "avatar": b64_avatar})
        messagebox.showinfo("Başarılı", "Profil fotoğrafı ve steganografi görseli güncellendi!")

    def build_contacts_screen(self):
        top_bar = ctk.CTkFrame(self.contacts_frame, fg_color=FRAME_BG, height=60, corner_radius=0)
        top_bar.pack(side="top", fill="x")
        
        btn_back = ctk.CTkButton(top_bar, text="◄ Menüye Dön", font=("Segoe UI", 12, "bold"), fg_color=BTN_BG, text_color=BTN_FG, width=120, height=35, corner_radius=8, command=lambda: self.show_frame(self.dashboard_frame))
        btn_back.pack(side="left", padx=15, pady=12)
        
        ctk.CTkLabel(top_bar, text="Kişiler ve İstekler", font=("Segoe UI", 16, "bold"), text_color=TEXT_FG).pack(side="left", padx=15, pady=12)
        
        body = ctk.CTkFrame(self.contacts_frame, fg_color=BG_COLOR)
        body.pack(fill="both", expand=True, padx=20, pady=20)
        
        left_p = ctk.CTkFrame(body, fg_color=FRAME_BG, corner_radius=15)
        left_p.pack(side="left", fill="both", expand=True, padx=(0, 10))
        ctk.CTkLabel(left_p, text="Kullanıcıları Keşfet", font=("Segoe UI", 14, "bold"), text_color=TEXT_FG).pack(pady=(15, 10))
        self.list_users = SelectableList(left_p, fg_color=ENTRY_BG, corner_radius=8)
        self.list_users.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        btn_req = ctk.CTkButton(left_p, text="İstek Gönder", font=("Segoe UI", 12, "bold"), fg_color=BTN_SUCCESS, text_color=BTN_FG, height=35, command=self.send_request)
        btn_req.pack(fill="x", padx=15, pady=15)
        
        right_p = ctk.CTkFrame(body, fg_color=FRAME_BG, corner_radius=15)
        right_p.pack(side="right", fill="both", expand=True, padx=(10, 0))
        ctk.CTkLabel(right_p, text="Gelen İstekler", font=("Segoe UI", 14, "bold"), text_color=TEXT_FG).pack(pady=(15, 10))
        self.list_requests = SelectableList(right_p, fg_color=ENTRY_BG, corner_radius=8)
        self.list_requests.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        btn_acc = ctk.CTkButton(right_p, text="Kabul Et", font=("Segoe UI", 12, "bold"), fg_color=BTN_WARN, text_color=BTN_FG, height=35, command=self.accept_request)
        btn_acc.pack(fill="x", padx=15, pady=15)

    def toggle_profile_menu(self):
        if self.profile_menu.winfo_ismapped():
            self.profile_menu.place_forget()
        else:
            self.profile_menu.configure(width=260)
            self.profile_menu.place(x=10, y=70)
            self.profile_menu.lift()

    def open_settings(self):
        self.profile_menu.place_forget()
        self.show_frame(self.settings_frame)
        
    def open_contacts(self):
        self.profile_menu.place_forget()
        self.show_frame(self.contacts_frame)

    def update_my_profile_ui(self):
        if hasattr(self, 'profile_btn'):
            try:
                if os.path.exists(self.carrier_image):
                    img = Image.open(self.carrier_image).convert("RGB")
                    circ = make_circular(img, size=(128, 128))
                    ctk_img = ctk.CTkImage(light_image=circ, dark_image=circ, size=(32, 32))
                    self.profile_btn.configure(text=f"  {self.username}", image=ctk_img)
                    return
            except: pass
            
            img = Image.new('RGB', (128, 128), color=(44, 62, 80))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(32, 32))
            self.profile_btn.configure(text=f"  {self.username}", image=ctk_img)

    def build_dashboard_screen(self):
        main_frame = ctk.CTkFrame(self.dashboard_frame, fg_color=BG_COLOR)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        left_panel = ctk.CTkFrame(main_frame, fg_color=FRAME_BG, corner_radius=15, width=280)
        left_panel.pack(side="left", fill="y", expand=False, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        self.profile_btn = ctk.CTkButton(left_panel, text=" Profil", anchor="w", fg_color="transparent", text_color=TEXT_FG, hover_color=ENTRY_BG, height=50, font=("Segoe UI", 14, "bold"), command=self.toggle_profile_menu)
        self.profile_btn.pack(fill="x", padx=10, pady=(15, 5))
        
        self.profile_menu = ctk.CTkFrame(left_panel, fg_color=ENTRY_BG, corner_radius=8, border_width=1, border_color="#45475a")
        ctk.CTkButton(self.profile_menu, text="👥 Kişiler ve İstekler", fg_color="transparent", anchor="w", text_color=TEXT_FG, hover_color=FRAME_BG, command=self.open_contacts).pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(self.profile_menu, text="⚙️ Ayarlar", fg_color="transparent", anchor="w", text_color=TEXT_FG, hover_color=FRAME_BG, command=self.open_settings).pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(self.profile_menu, text="🚪 Çıkış Yap", fg_color="transparent", anchor="w", text_color=BTN_DANGER, hover_color=FRAME_BG, command=self.logout).pack(fill="x", padx=5, pady=5)
        
        sep = ctk.CTkFrame(left_panel, height=2, fg_color=ENTRY_BG)
        sep.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(left_panel, text="Sohbetlerim", font=("Segoe UI", 16, "bold"), text_color=TEXT_FG).pack(pady=(10, 10))
        self.list_friends = SelectableList(left_panel, fg_color=ENTRY_BG, corner_radius=8, on_select=self.open_chat)
        self.list_friends.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        btn_create_group = ctk.CTkButton(left_panel, text="Yeni Grup Kur", font=("Segoe UI", 12, "bold"), fg_color=BTN_SUCCESS, text_color=BTN_FG, corner_radius=8, height=35, command=self.create_group)
        btn_create_group.pack(fill="x", padx=15, pady=(15, 15))
        
        self.right_panel = ctk.CTkFrame(main_frame, fg_color=BG_COLOR)
        self.right_panel.pack(side="right", fill="both", expand=True)
        
        self.placeholder_frame = ctk.CTkFrame(self.right_panel, fg_color=FRAME_BG, corner_radius=15)
        self.placeholder_frame.pack(fill="both", expand=True)
        
        ph_label = ctk.CTkLabel(self.placeholder_frame, text="Sohbet etmek için sol taraftan bir kişi seçin.", font=("Segoe UI", 18, "bold"), text_color="#6c7086")
        ph_label.place(relx=0.5, rely=0.5, anchor="center")
        
        self.chat_container = ctk.CTkFrame(self.right_panel, fg_color=BG_COLOR, corner_radius=0)
        self.build_chat_screen()

    def update_lists(self, users, requests, friends, online_users, groups, groups_info, group_requests, public_keys, avatars):
        self.online_users = online_users
        self.groups_info = groups_info
        self.public_keys = public_keys
        self.server_avatars = avatars
        self.friends = friends
        
        self.list_users.clear()
        for u in users:
            img = get_avatar_image(self.server_avatars.get(u), size=(32,32))
            self.list_users.add_item(u, image=img, value=u)
            
        self.list_requests.clear()
        for r in requests: 
            img = get_avatar_image(self.server_avatars.get(r), size=(32,32))
            self.list_requests.add_item(r, image=img, value=f"USER:{r}")
        for gr in group_requests: 
            img = get_avatar_image(None, size=(32,32))
            self.list_requests.add_item(f"{gr} (Grup Daveti)", image=img, value=f"GROUP:{gr}")
            
        self.list_friends.clear()
        for g in groups:
            img = get_avatar_image(None, size=(32,32))
            color = BTN_SUCCESS if g in self.unread_chats else TEXT_FG
            self.list_friends.add_item(g, image=img, value=f"GROUP:{g}", text_color=color)
        for f in friends:
            img = get_avatar_image(self.server_avatars.get(f), size=(32,32))
            stat = "🟢" if f in online_users else "⚪"
            color = BTN_SUCCESS if f in self.unread_chats else TEXT_FG
            self.list_friends.add_item(f"{f} {stat}", image=img, value=f"USER:{f}", text_color=color)
                
        if self.active_chat_friend and self.is_group_chat and hasattr(self, 'members_listbox'):
            self.members_listbox.clear()
            for m in self.groups_info.get(self.active_chat_friend, []):
                img = get_avatar_image(self.server_avatars.get(m), size=(32,32))
                stat = "🟢" if m in self.online_users else "⚪"
                self.members_listbox.add_item(f"{m} {stat}", image=img, value=m)

    def send_request(self):
        target = self.list_users.get_selected()
        if target:
            self.send_msg({"type": "SEND_REQUEST", "target": target})
            messagebox.showinfo("Bilgi", "İstek gönderildi.")

    def accept_request(self):
        val = self.list_requests.get_selected()
        if val:
            if val.startswith("GROUP:"):
                gname = val.split("GROUP:")[1]
                self.send_msg({"type": "ACCEPT_GROUP", "group_name": gname})
            elif val.startswith("USER:"):
                target = val.split("USER:")[1]
                self.send_msg({"type": "ACCEPT_REQUEST", "target": target})

    def create_group(self):
        gname = simpledialog.askstring("Yeni Grup", "Grubunuzun adını giriniz:")
        if gname and gname.strip():
            self.send_msg({"type": "CREATE_GROUP", "group_name": gname.strip()})

    def build_chat_screen(self):
        top_bar = ctk.CTkFrame(self.chat_container, fg_color=FRAME_BG, height=60, corner_radius=15)
        top_bar.pack(side="top", fill="x", pady=(0, 10))
        top_bar.pack_propagate(False)
        
        self.chat_title_label = ctk.CTkLabel(top_bar, text="Sohbet", font=("Segoe UI", 16, "bold"), text_color=TEXT_FG)
        self.chat_title_label.pack(side="left", padx=20, pady=12)
        
        self.btn_invite = ctk.CTkButton(top_bar, text="+ Kişi Davet Et", font=("Segoe UI", 12, "bold"), fg_color=BTN_SUCCESS, text_color=BTN_FG, width=120, height=35, corner_radius=8, command=self.invite_to_group)
        self.btn_chat_action = ctk.CTkButton(top_bar, text="", font=("Segoe UI", 12, "bold"), fg_color="#e06c75", text_color=BTN_FG, width=120, height=35, corner_radius=8, command=self.chat_action)
        
        input_frame = ctk.CTkFrame(self.chat_container, fg_color=BG_COLOR)
        input_frame.pack(side="bottom", fill="x", pady=(15, 0))
        
        self.chat_entry = ctk.CTkEntry(input_frame, placeholder_text="Mesajınızı yazın...", font=("Segoe UI", 14), height=45, corner_radius=8, fg_color=ENTRY_BG, border_width=0)
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        btn_send = ctk.CTkButton(input_frame, text="Gönder", font=("Segoe UI", 14, "bold"), fg_color=BTN_BG, text_color=BTN_FG, width=100, height=45, corner_radius=8, command=self.send_msg_ui)
        btn_send.pack(side="right")
        self.chat_entry.bind("<Return>", self.send_msg_ui)
        
        body_frame = ctk.CTkFrame(self.chat_container, fg_color=BG_COLOR)
        body_frame.pack(side="top", fill="both", expand=True)
        
        chat_frame = ctk.CTkFrame(body_frame, fg_color=FRAME_BG, corner_radius=15)
        chat_frame.pack(side="left", fill="both", expand=True)
        
        self.chat_text_area = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, font=("Segoe UI", 12), bg=FRAME_BG, fg=TEXT_FG, bd=0, highlightthickness=0, state='disabled')
        self.chat_text_area.pack(fill="both", expand=True, padx=15, pady=15)
        
        self.chat_text_area.tag_config('me', foreground=BTN_SUCCESS, font=("Segoe UI", 12, "bold"), justify="right")
        self.chat_text_area.tag_config('them', foreground=SELECT_BG, font=("Segoe UI", 12, "bold"))
        self.chat_text_area.tag_config('info', foreground="#6c7086", font=("Segoe UI", 10, "italic"), justify="center")

        self.members_frame = ctk.CTkFrame(body_frame, fg_color=FRAME_BG, corner_radius=15, width=220)
        
        ctk.CTkLabel(self.members_frame, text="Grup Üyeleri", font=("Segoe UI", 14, "bold"), text_color=TEXT_FG).pack(pady=(15, 10))
        self.members_listbox = SelectableList(self.members_frame, fg_color=ENTRY_BG, corner_radius=8)
        self.members_listbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def open_chat(self, val=None):
        if not val:
            val = self.list_friends.get_selected()
        if not val: return
        
        if val.startswith("GROUP:"):
            friend = val.split("GROUP:")[1]
            self.is_group_chat = True
        else:
            friend = val.split("USER:")[1]
            self.is_group_chat = False
            
        self.active_chat_friend = friend
        self.chat_title_label.configure(text=f"{friend}")
        
        if friend in self.unread_chats:
            self.unread_chats.remove(friend)
            self.send_msg({"type": "GET_DASHBOARD"})
        
        if self.is_group_chat:
            self.btn_chat_action.configure(text="Gruptan Ayrıl")
            self.btn_chat_action.pack(side="right", padx=10, pady=12)
            members = self.groups_info.get(friend, [])
            if members and members[0] == self.username:
                self.btn_invite.pack(side="right", padx=10, pady=12)
            else:
                self.btn_invite.pack_forget()
                
            self.members_frame.pack(side="right", fill="y", padx=(10, 0))
            self.members_frame.pack_propagate(False)
            self.members_listbox.clear()
            for m in members:
                img = get_avatar_image(self.server_avatars.get(m), size=(32,32))
                stat = "🟢" if m in self.online_users else "⚪"
                self.members_listbox.add_item(f"{m} {stat}", image=img, value=m)
        else:
            self.btn_chat_action.configure(text="Arkadaştan Çıkar")
            self.btn_chat_action.pack(side="right", padx=10, pady=12)
            self.btn_invite.pack_forget()
            self.members_frame.pack_forget()
        
        self.chat_text_area.config(state='normal')
        self.chat_text_area.delete('1.0', tk.END) 
        self.chat_images.clear()
        
        history_list = self.chat_history.get(friend, [])
        if history_list:
            self.chat_text_area.insert('end', f"--- Şifreli Geçmiş Kasa Yüklendi ---\n\n", 'info')
        for msg in history_list:
            self.render_message(msg['sender'], msg['text'], msg['tag'])
            
        self.chat_text_area.yview('end')
        self.chat_text_area.config(state='disabled')
        
        self.placeholder_frame.pack_forget()
        self.chat_container.pack(fill="both", expand=True)
        self.chat_entry.focus()

    def chat_action(self):
        target = self.active_chat_friend
        if not target: return
        
        if self.is_group_chat:
            confirm = messagebox.askyesno("Onay", f"'{target}' grubundan ayrılmak istediğinize emin misiniz?")
            if confirm:
                self.send_msg({"type": "LEAVE_GROUP", "group_name": target})
                self.chat_container.pack_forget()
                self.placeholder_frame.pack(fill="both", expand=True)
                self.active_chat_friend = None
        else:
            confirm = messagebox.askyesno("Onay", f"'{target}' adlı kullanıcıyı arkadaşlıktan çıkarmak istediğinize emin misiniz?")
            if confirm:
                self.send_msg({"type": "REMOVE_FRIEND", "target": target})
                self.chat_container.pack_forget()
                self.placeholder_frame.pack(fill="both", expand=True)
                self.active_chat_friend = None

    def invite_to_group(self):
        if not self.is_group_chat: return
        
        invite_win = ctk.CTkToplevel(self.root)
        invite_win.title("Davet Et")
        invite_win.geometry("400x450")
        invite_win.configure(fg_color=BG_COLOR)
        invite_win.attributes("-topmost", True)
        
        ctk.CTkLabel(invite_win, text=f"'{self.active_chat_friend}' Grubuna Davet Et", font=("Segoe UI", 14, "bold"), text_color=TEXT_FG).pack(pady=15)
        
        lst = SelectableList(invite_win, fg_color=ENTRY_BG, corner_radius=8)
        lst.pack(fill="both", expand=True, padx=15, pady=0)
        
        current_members = self.groups_info.get(self.active_chat_friend, [])
        for f in self.friends:
            if f not in current_members:
                img = get_avatar_image(self.server_avatars.get(f), size=(32,32))
                lst.add_item(f, image=img, value=f)
                
        def do_invite():
            target = lst.get_selected()
            if target:
                self.send_msg({"type": "INVITE_GROUP", "group_name": self.active_chat_friend, "target": target})
                invite_win.destroy()
        
        btn = ctk.CTkButton(invite_win, text="Seç ve Davet Et", font=("Segoe UI", 12, "bold"), fg_color=BTN_SUCCESS, text_color=BTN_FG, height=35, corner_radius=8, command=do_invite)
        btn.pack(fill="x", padx=15, pady=15)

    def send_msg_ui(self, event=None):
        if not self.active_chat_friend: return
        txt = self.chat_entry.get()
        if not txt.strip(): return
        self.chat_entry.delete(0, tk.END)
        
        target = self.active_chat_friend
        
        self.chat_text_area.config(state='normal')
        self.render_message(self.username, txt, 'me')
        self.chat_text_area.yview('end')
        self.chat_text_area.config(state='disabled')
        
        self.add_to_history(target, self.username, txt, "me")
        
        message_key = Fernet.generate_key()
        f = Fernet(message_key)
        enc_text = f.encrypt(txt.encode('utf-8'))
        
        payload_dict = {}
        
        if self.is_group_chat:
            keys_dict = {}
            members = self.groups_info.get(target, [])
            for mem in members:
                if mem in self.public_keys:
                    mem_pub = rsa.PublicKey.load_pkcs1(self.public_keys[mem].encode('utf-8'))
                    mem_enc_key = rsa.encrypt(message_key, mem_pub)
                    keys_dict[mem] = base64.b64encode(mem_enc_key).decode('utf-8')
            payload_dict = {
                "keys": keys_dict,
                "m": base64.b64encode(enc_text).decode('utf-8')
            }
        else:
            if target in self.public_keys:
                target_pub = rsa.PublicKey.load_pkcs1(self.public_keys[target].encode('utf-8'))
                enc_key = rsa.encrypt(message_key, target_pub)
                payload_dict = {
                    "k": base64.b64encode(enc_key).decode('utf-8'),
                    "m": base64.b64encode(enc_text).decode('utf-8')
                }
            else:
                messagebox.showerror("Hata", "Karşı tarafın Public Key'i bulunamadı. Mesaj şifrelenemez.")
                return

        b64_payload = base64.b64encode(json.dumps(payload_dict).encode('utf-8')).decode('utf-8')
        
        temp_file = f'temp_send_{self.client_id}.png'
        lsb.hide(self.carrier_image, b64_payload).save(temp_file)
        
        with open(temp_file, "rb") as file_img:
            img_data = file_img.read()
            
        final_payload_b64 = base64.b64encode(img_data).decode('utf-8')
        os.remove(temp_file)
        
        if self.is_group_chat:
            self.send_msg({"type": "SEND_GROUP_MESSAGE", "target": target, "payload_b64": final_payload_b64})
        else:
            self.send_msg({"type": "SEND_MESSAGE", "target": target, "payload_b64": final_payload_b64})

    def process_incoming_image(self, sender, payload_b64):
        temp_recv = f'temp_recv_{self.client_id}.png'
        img_bytes = base64.b64decode(payload_b64)
        with open(temp_recv, 'wb') as f:
            f.write(img_bytes)
            
        try:
            hidden_str = lsb.reveal(temp_recv)
            payload_dict = json.loads(base64.b64decode(hidden_str).decode('utf-8'))
            
            enc_key = base64.b64decode(payload_dict['k'])
            enc_text = base64.b64decode(payload_dict['m'])
            
            message_key = rsa.decrypt(enc_key, self.private_key)
            f = Fernet(message_key)
            dec_txt = f.decrypt(enc_text).decode('utf-8')
            
            self.add_to_history(sender, sender, dec_txt, "them")
            
            if self.active_chat_friend == sender and not self.is_group_chat:
                self.chat_text_area.config(state='normal')
                self.render_message(sender, dec_txt, 'them')
                self.chat_text_area.yview('end')
                self.chat_text_area.config(state='disabled')
            else:
                self.mark_unread(sender)
        except Exception: pass
        finally:
            if os.path.exists(temp_recv): os.remove(temp_recv)

    def process_incoming_group_image(self, group, sender, payload_b64):
        temp_recv = f'temp_recv_group_{self.client_id}.png'
        img_bytes = base64.b64decode(payload_b64)
        with open(temp_recv, 'wb') as f:
            f.write(img_bytes)
            
        try:
            hidden_str = lsb.reveal(temp_recv)
            payload_dict = json.loads(base64.b64decode(hidden_str).decode('utf-8'))
            
            enc_key_b64 = payload_dict['keys'].get(self.username)
            if not enc_key_b64:
                return
                
            enc_key = base64.b64decode(enc_key_b64)
            enc_text = base64.b64decode(payload_dict['m'])
            
            message_key = rsa.decrypt(enc_key, self.private_key)
            f = Fernet(message_key)
            dec_txt = f.decrypt(enc_text).decode('utf-8')
            
            self.add_to_history(group, sender, dec_txt, "them")
            
            if self.active_chat_friend == group and self.is_group_chat:
                self.chat_text_area.config(state='normal')
                self.render_message(sender, dec_txt, 'them')
                self.chat_text_area.yview('end')
                self.chat_text_area.config(state='disabled')
            else:
                self.mark_unread(group)
        except Exception: pass
        finally:
            if os.path.exists(temp_recv): os.remove(temp_recv)

    def stop(self):
        self.running = False
        if self.client: self.client.close()
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    ChatClient('127.0.0.1', 55555)
