import socket
import threading
import struct
import json
import hashlib
import os

HOST = '127.0.0.1'
PORT = 55555

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()

os.makedirs('data', exist_ok=True)
USERS_FILE = 'data/users.json'
REQUESTS_FILE = 'data/requests.json'
FRIENDS_FILE = 'data/friends.json'
GROUPS_FILE = 'data/groups.json'
GROUP_REQUESTS_FILE = 'data/group_requests.json'
OFFLINE_MESSAGES_FILE = 'data/offline_messages.json'
PUBLIC_KEYS_FILE = 'data/public_keys.json'
AVATARS_FILE = 'data/avatars.json'

active_clients = {}

def load_json(filename, default=None):
    if default is None: default = {}
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def send_msg(sock, msg_dict):
    try:
        data = json.dumps(msg_dict).encode('utf-8')
        packet = struct.pack('!I', len(data)) + data
        sock.sendall(packet)
    except:
        pass

def receive_all(sock, n):
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet: return None
        data.extend(packet)
    return bytes(data)

def disconnect_user(username, sock):
    if username in active_clients and active_clients[username] == sock:
        del active_clients[username]
        print(f"[*] {username} çevrimdışı oldu.")
        for c_user, c_sock in list(active_clients.items()):
            send_msg(c_sock, {"type": "REFRESH_DASHBOARD"})
    sock.close()

def deliver_offline_messages(username, sock):
    offline_msgs = load_json(OFFLINE_MESSAGES_FILE)
    if username in offline_msgs and offline_msgs[username]:
        print(f"[*] {username} için bekleyen {len(offline_msgs[username])} çevrimdışı mesaj iletiliyor...")
        for msg in offline_msgs[username]:
            send_msg(sock, msg)
        offline_msgs[username] = []
        save_json(OFFLINE_MESSAGES_FILE, offline_msgs)

def handle_client(sock):
    username = None
    try:
        while True:
            raw_msglen = receive_all(sock, 4)
            if not raw_msglen: break
            msglen = struct.unpack('!I', raw_msglen)[0]
            
            data = receive_all(sock, msglen)
            if not data: break
            
            msg = json.loads(data.decode('utf-8'))
            cmd = msg.get('type')
            
            users = load_json(USERS_FILE)
            requests = load_json(REQUESTS_FILE)
            friends = load_json(FRIENDS_FILE)
            groups = load_json(GROUPS_FILE)
            group_requests = load_json(GROUP_REQUESTS_FILE)
            
            if cmd == 'REGISTER':
                u = msg.get('username')
                p = msg.get('password')
                if u in users:
                    send_msg(sock, {"type": "AUTH_REPLY", "status": "FAIL", "message": "Kullanıcı adı alınmış."})
                else:
                    users[u] = hash_password(p)
                    save_json(USERS_FILE, users)
                    friends[u] = []
                    save_json(FRIENDS_FILE, friends)
                    send_msg(sock, {"type": "AUTH_REPLY", "status": "SUCCESS"})
                    username = u
                    active_clients[username] = sock
                    deliver_offline_messages(username, sock)
                    
                    for c_user, c_sock in list(active_clients.items()):
                        if c_user != username:
                            send_msg(c_sock, {"type": "REFRESH_DASHBOARD"})
                            
            elif cmd == 'LOGIN':
                u = msg.get('username')
                p = msg.get('password')
                if u not in users or users[u] != hash_password(p):
                    send_msg(sock, {"type": "AUTH_REPLY", "status": "FAIL", "message": "Hatalı bilgi."})
                elif u in active_clients:
                    send_msg(sock, {"type": "AUTH_REPLY", "status": "FAIL", "message": "Hesap şu an aktif."})
                else:
                    send_msg(sock, {"type": "AUTH_REPLY", "status": "SUCCESS"})
                    username = u
                    active_clients[username] = sock
                    deliver_offline_messages(username, sock)
                    
                    for c_user, c_sock in list(active_clients.items()):
                        if c_user != username:
                            send_msg(c_sock, {"type": "REFRESH_DASHBOARD"})
                            
            elif cmd == 'CHANGE_PASSWORD' and username:
                old_p = msg.get('old_password')
                new_p = msg.get('new_password')
                if users.get(username) == hash_password(old_p):
                    users[username] = hash_password(new_p)
                    save_json(USERS_FILE, users)
                    send_msg(sock, {"type": "CHANGE_PASSWORD_REPLY", "status": "SUCCESS"})
                else:
                    send_msg(sock, {"type": "CHANGE_PASSWORD_REPLY", "status": "FAIL", "message": "Mevcut şifrenizi yanlış girdiniz."})

            elif cmd == 'UPLOAD_PUBLIC_KEY' and username:
                pubkey = msg.get('public_key')
                if pubkey:
                    public_keys = load_json(PUBLIC_KEYS_FILE)
                    public_keys[username] = pubkey
                    save_json(PUBLIC_KEYS_FILE, public_keys)
                    for c_user, c_sock in list(active_clients.items()):
                        if c_user != username:
                            send_msg(c_sock, {"type": "REFRESH_DASHBOARD"})

            elif cmd == 'UPLOAD_AVATAR' and username:
                avatar = msg.get('avatar')
                if avatar:
                    avatars = load_json(AVATARS_FILE)
                    avatars[username] = avatar
                    save_json(AVATARS_FILE, avatars)
                    for c_user, c_sock in list(active_clients.items()):
                        send_msg(c_sock, {"type": "REFRESH_DASHBOARD"})

            elif cmd == 'GET_DASHBOARD' and username:
                all_users = list(users.keys())
                if username in all_users: all_users.remove(username)
                
                my_reqs = requests.get(username, [])
                my_friends = friends.get(username, [])
                all_online = list(active_clients.keys())
                
                my_groups = [g for g, mems in groups.items() if username in mems]
                my_groups_dict = {g: mems for g, mems in groups.items() if username in mems}
                my_group_reqs = group_requests.get(username, [])
                public_keys = load_json(PUBLIC_KEYS_FILE)
                avatars = load_json(AVATARS_FILE)
                
                send_msg(sock, {
                    "type": "DASHBOARD_DATA", 
                    "users": all_users, 
                    "friends": my_friends, 
                    "requests": my_reqs,
                    "online_users": all_online,
                    "groups": my_groups,
                    "groups_info": my_groups_dict,
                    "group_requests": my_group_reqs,
                    "public_keys": public_keys,
                    "avatars": avatars
                })
                
            elif cmd == 'SEND_REQUEST' and username:
                target = msg.get('target')
                if target in users and target != username:
                    if target not in requests: requests[target] = []
                    if username not in requests[target] and username not in friends.get(target, []):
                        requests[target].append(username)
                        save_json(REQUESTS_FILE, requests)
                        if target in active_clients:
                            send_msg(active_clients[target], {"type": "NEW_REQUEST", "from": username})
            
            elif cmd == 'ACCEPT_REQUEST' and username:
                target = msg.get('target')
                if target in requests.get(username, []):
                    requests[username].remove(target)
                    save_json(REQUESTS_FILE, requests)
                    
                    if username not in friends: friends[username] = []
                    if target not in friends: friends[target] = []
                    if target not in friends[username]: friends[username].append(target)
                    if username not in friends[target]: friends[target].append(username)
                    save_json(FRIENDS_FILE, friends)
                    
                    send_msg(sock, {"type": "NEW_FRIEND", "friend": target})
                    if target in active_clients:
                        send_msg(active_clients[target], {"type": "NEW_FRIEND", "friend": username})
                        
            # --- GRUP KOMUTLARI ---
            elif cmd == 'CREATE_GROUP' and username:
                gname = msg.get('group_name')
                if gname and gname not in groups:
                    groups[gname] = [username]
                    save_json(GROUPS_FILE, groups)
                    send_msg(sock, {"type": "REFRESH_DASHBOARD"})
                    
            elif cmd == 'INVITE_GROUP' and username:
                gname = msg.get('group_name')
                target = msg.get('target')
                if gname in groups:
                    # Kurucu doğrulaması (İlk eklenen kişi kurucudur)
                    if groups[gname][0] != username:
                        send_msg(sock, {"type": "ERROR", "message": "Sadece grup kurucusu gruba davetiye gönderebilir!"})
                    elif target in groups[gname]:
                        send_msg(sock, {"type": "ERROR", "message": "Bu kullanıcı zaten grupta yer alıyor!"})
                    elif target in users:
                        if target not in group_requests: group_requests[target] = []
                        if gname not in group_requests[target]:
                            group_requests[target].append(gname)
                            save_json(GROUP_REQUESTS_FILE, group_requests)
                            if target in active_clients:
                                send_msg(active_clients[target], {"type": "NEW_GROUP_REQUEST", "group": gname})
                            send_msg(sock, {"type": "INFO", "message": f"{target} başarıyla gruba davet edildi!"})
                        else:
                            send_msg(sock, {"type": "ERROR", "message": "Bu kullanıcıya daha önce davetiye gönderilmiş!"})

            elif cmd == 'ACCEPT_GROUP' and username:
                gname = msg.get('group_name')
                if gname in group_requests.get(username, []):
                    group_requests[username].remove(gname)
                    save_json(GROUP_REQUESTS_FILE, group_requests)
                    if gname in groups and username not in groups[gname]:
                        groups[gname].append(username)
                        save_json(GROUPS_FILE, groups)
                    send_msg(sock, {"type": "REFRESH_DASHBOARD"})

            elif cmd == 'LEAVE_GROUP' and username:
                gname = msg.get('group_name')
                if gname in groups and username in groups[gname]:
                    groups[gname].remove(username)
                    if not groups[gname]:
                        del groups[gname]
                    save_json(GROUPS_FILE, groups)
                    send_msg(sock, {"type": "REFRESH_DASHBOARD"})
                    for mem in groups.get(gname, []):
                        if mem in active_clients:
                            send_msg(active_clients[mem], {"type": "REFRESH_DASHBOARD"})

            elif cmd == 'REMOVE_FRIEND' and username:
                target = msg.get('target')
                if username in friends and target in friends[username]:
                    friends[username].remove(target)
                if target in friends and username in friends.get(target, []):
                    friends[target].remove(username)
                save_json(FRIENDS_FILE, friends)
                send_msg(sock, {"type": "REFRESH_DASHBOARD"})
                if target in active_clients:
                    send_msg(active_clients[target], {"type": "REFRESH_DASHBOARD"})

            # --- MESAJLAŞMA (STORE & FORWARD DESTEĞİ İLE) ---
            elif cmd == 'SEND_MESSAGE' and username:
                target = msg.get('target')
                payload = msg.get('payload_b64')
                if target in friends.get(username, []):
                    msg_obj = {
                        "type": "RECEIVE_MESSAGE",
                        "from": username,
                        "payload_b64": payload
                    }
                    if target in active_clients:
                        send_msg(active_clients[target], msg_obj)
                    else:
                        offline_msgs = load_json(OFFLINE_MESSAGES_FILE)
                        if target not in offline_msgs: offline_msgs[target] = []
                        offline_msgs[target].append(msg_obj)
                        save_json(OFFLINE_MESSAGES_FILE, offline_msgs)
                    
            elif cmd == 'SEND_GROUP_MESSAGE' and username:
                gname = msg.get('target')
                payload = msg.get('payload_b64')
                if gname in groups and username in groups[gname]:
                    offline_msgs = load_json(OFFLINE_MESSAGES_FILE)
                    modified = False
                    for mem in groups[gname]:
                        if mem != username:
                            msg_obj = {
                                "type": "RECEIVE_GROUP_MESSAGE",
                                "group": gname,
                                "from": username,
                                "payload_b64": payload
                            }
                            if mem in active_clients:
                                send_msg(active_clients[mem], msg_obj)
                            else:
                                if mem not in offline_msgs: offline_msgs[mem] = []
                                offline_msgs[mem].append(msg_obj)
                                modified = True
                    if modified:
                        save_json(OFFLINE_MESSAGES_FILE, offline_msgs)

    except Exception as e:
        pass
    finally:
        disconnect_user(username, sock)

def receive():
    print("[*] Yeni Nesil Yönlendirici (Router) Sunucu Başlatıldı...")
    print("[*] Çevrimdışı Mesaj Depolama (Store & Forward) Devrede.")
    server.settimeout(1.0)
    try:
        while True:
            try:
                client, address = server.accept()
                t = threading.Thread(target=handle_client, args=(client,))
                t.daemon = True
                t.start()
            except socket.timeout:
                continue
    except KeyboardInterrupt:
        print("\n[!] Kapatılıyor...")
    finally:
        server.close()

if __name__ == "__main__":
    receive()
