#!/usr/bin/python3
import socket
import sys
import json
import threading
import time
from game import Boat, isAStrike, isANewShot, Game
from main import randomConfiguration, displayGame, addShot, displayConfiguration

PORT = 5000

def recv_line(sock):
    data = b""
    while not data.endswith(b"\n"):
        part = sock.recv(4096)
        if not part:
            return None
        data += part
    return data.decode().strip()

def send_line(sock, s):
    sock.sendall((s + "\n").encode())

def boats_to_json(boats):
   
    arr = []
    for b in boats:
        arr.append({"x": b.x, "y": b.y, "length": b.length, "isHorizontal": b.isHorizontal})
    return json.dumps(arr)

def boats_from_json(j):
    arr = json.loads(j)
    boats = []
    for bd in arr:
        boats.append(Boat(bd["x"], bd["y"], bd["length"], bd["isHorizontal"]))
    return boats

def handle_incoming(sock, local):
    
    while True:
        line = recv_line(sock)
        if line is None:
            print("Disconnected from server.")
            break
        if line.startswith("WELCOME"):
            print("Server says WELCOME")
            continue
        if line.startswith("ASSIGNED"):
            print(line)
            if "PLAYER" in line:
                local["role"] = "PLAYER"
            else:
                local["role"] = "OBSERVER"
            continue
        if line.startswith("START"):
            print("La partie commence !")
            continue
        if line.startswith("YOUR_TURN"):
            local["your_turn"] = True
            print("C'EST TON TOUR.")
            continue
        if line.startswith("WAIT"):
            local["your_turn"] = False
            continue
        if line.startswith("RESULT"):
            _, r = line.split()
            print("Résultat :", "TOUCHÉ" if r == "1" else "À L'EAU")
            continue
        if line.startswith("OPPONENT_PLAYED"):
            _, xs, ys, hr = line.split()
            x = int(xs); y = int(ys); hit = (hr == "1")
            print(f"Adversaire a joué {chr(x+64)}{y} -> {'TOUCHÉ' if hit else 'EAU'}")
           
            local["last_opponent_play"] = (x,y,hit)
            continue
        if line.startswith("STATE "):
            j = line[len("STATE "):]
            d = json.loads(j)
            
            local["state_from_server"] = d
            print("Etat reçu du serveur (sync).")
            continue
        if line.startswith("SCOREBOARD"):
            j = line[len("SCOREBOARD "):]
            sb = json.loads(j)
            print("SCOREBOARD:", sb)
            continue
        if line.startswith("INFO"):
            print(line)
            continue
        if line.startswith("WIN"):
            print("Vous avez gagné la manche !")
            local["your_turn"] = False
            continue
        if line.startswith("LOSE"):
            print("Vous avez perdu la manche.")
            local["your_turn"] = False
            continue
        if line.startswith("ERROR"):
            print("SERVER ERROR:", line)
            continue

def run_client(host, name, role):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, PORT))
   
    local = {"your_turn": False, "role": role, "state_from_server": None}
    threading.Thread(target=handle_incoming, args=(sock, local), daemon=True).start()

    
    send_line(sock, f"JOIN {name} {role}")

    if role == "PLAYER":
        
        boats = randomConfiguration()
        send_line(sock, "READY " + boats_to_json(boats))
        print("Bateaux envoyés au serveur (READY).")
    else:
        boats = []

    
    try:
        while True:
            time.sleep(0.1)
            if local.get("your_turn", False) and local.get("role") == "PLAYER":
                col = input("Colonne (A-J): ").strip().upper()
                if not col:
                    continue
                try:
                    x = ord(col[0]) - ord("A") + 1
                    y = int(input("Ligne (1-10): ").strip())
                except Exception:
                    print("Coordonnée invalide.")
                    continue
                send_line(sock, f"PLAY {x} {y}")
            
            
            
            cmd = None
    except KeyboardInterrupt:
        try:
            send_line(sock, "QUIT")
        except Exception:
            pass
        sock.close()
        print("Client quitté.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python client.py <server> [name] [ROLE]")
        print("ROLE: PLAYER or OBSERVER (default PLAYER)")
        sys.exit(1)
    host = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) >= 3 else input("Ton nom : ").strip()
    role = sys.argv[3].upper() if len(sys.argv) >= 4 else input("ROLE (PLAYER/OBSERVER) [PLAYER]: ").strip().upper() or "PLAYER"
    run_client(host, name, role)
