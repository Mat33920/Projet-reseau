#!/usr/bin/python3
import socket
import threading
import json
import os
from game import Boat, isAStrike, WIDTH

PORT = 5000
SCORES_FILE = "scores.json"

lock = threading.Lock()

def load_scores():
    if os.path.exists(SCORES_FILE):
        with open(SCORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_scores(scores):
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f)

def recv_line(conn):
    data = b""
    while not data.endswith(b"\n"):
        part = conn.recv(4096)
        if not part:
            return None
        data += part
    return data.decode().strip()

def send_line(conn, s):
    try:
        conn.sendall((s + "\n").encode())
    except Exception:
        pass

class GameState:
    def __init__(self):
        # boats: dict name -> list of boats (each boat as dict)
        self.boats = {}
        # shots: dict name -> list of (x,y,hit)
        self.shots = {}
        # order: [player_name0, player_name1] if two players assigned
        self.players = []
        self.current_index = 0  # whose turn index in players
        self.over = False

    def reset_for_next_round(self):
        self.boats = {}
        self.shots = {}
        self.players = []
        self.current_index = 0
        self.over = False

    def to_json(self):
        return json.dumps({
            "boats": self.boats,
            "shots": self.shots,
            "players": self.players,
            "current_index": self.current_index,
            "over": self.over
        })

    def from_json(self, s):
        d = json.loads(s)
        self.boats = d["boats"]
        self.shots = d["shots"]
        self.players = d["players"]
        self.current_index = d["current_index"]
        self.over = d["over"]

# server-wide state
state = GameState()
clients = {}       # name -> (conn, role) role in {"PLAYER", "OBSERVER"}
addr2name = {}     # socket fileno -> name
scores = load_scores()

def boat_from_dict(bd):
    return Boat(bd["x"], bd["y"], bd["length"], bd["isHorizontal"])

def check_victory(shots_by_player, opponent_name):
    # count distinct hit squares on opponent boats
    hits = 0
    opp_boats = state.boats.get(opponent_name, [])
    for shot in shots_by_player:
        if shot[2]:
            hits += 1
    # TOTAL_LENGTH = 17 in your game.py
    return hits >= 17

def handle_client(conn, addr):
    try:
        send_line(conn, "WELCOME")
        name = None
        role = None

        while True:
            line = recv_line(conn)
            if line is None:
                break
            parts = line.split(" ", 2)
            cmd = parts[0]

            if cmd == "JOIN":
                # JOIN <name> <ROLE>
                if len(parts) < 3:
                    send_line(conn, "ERROR JOIN requires name and ROLE")
                    continue
                name = parts[1]
                role = parts[2].upper()
                with lock:
                    clients[name] = (conn, role)
                    addr2name[conn.fileno()] = name
                    if name not in scores:
                        scores[name] = {"wins": 0, "losses": 0}
                if role == "PLAYER":
                    # assign player slot if less than 2 players
                    with lock:
                        if name not in state.players and len(state.players) < 2:
                            state.players.append(name)
                            state.shots.setdefault(name, [])
                            state.boats.setdefault(name, [])
                            send_line(conn, f"ASSIGNED PLAYER {state.players.index(name)}")
                        else:
                            # if two players already, become observer
                            state.shots.setdefault(name, [])
                            state.boats.setdefault(name, [])
                            send_line(conn, "ASSIGNED OBSERVER")
                            clients[name] = (conn, "OBSERVER")
                else:
                    send_line(conn, "ASSIGNED OBSERVER")

                # send scoreboard
                send_line(conn, "SCOREBOARD " + json.dumps(scores))

                # if both players present and both have sent READY, start
                with lock:
                    if len(state.players) == 2:
                        p0, p1 = state.players
                        if state.boats.get(p0) and state.boats.get(p1):
                            state.over = False
                            state.current_index = 0
                            broadcast("START")
                            notify_turns()
                continue

            if cmd == "READY":
                # READY <json_boats>
                if name is None:
                    send_line(conn, "ERROR must JOIN first")
                    continue
                if len(parts) < 2:
                    send_line(conn, "ERROR READY requires boat json")
                    continue
                boats_json = parts[1]
                try:
                    b = json.loads(boats_json)
                    # validate structure? minimal check
                    state.boats[name] = b
                    state.shots.setdefault(name, [])
                    send_line(conn, "INFO boats registered")
                except Exception as e:
                    send_line(conn, f"ERROR invalid boats json {e}")
                # maybe start game if both players ready
                with lock:
                    if len(state.players) == 2:
                        p0, p1 = state.players
                        if state.boats.get(p0) and state.boats.get(p1):
                            state.over = False
                            state.current_index = 0
                            broadcast("START")
                            notify_turns()
                continue

            if cmd == "PLAY":
            
                if name is None:
                    send_line(conn, "ERROR must JOIN first")
                    continue
                if state.over:
                    send_line(conn, "ERROR game is over")
                    continue
                if name not in state.players:
                    send_line(conn, "ERROR you are not a player right now")
                    continue
               
                with lock:
                    current_name = state.players[state.current_index]
                    if name != current_name:
                        send_line(conn, "ERROR not your turn")
                        continue
                try:
                    _, xs, ys = line.split()
                    x = int(xs); y = int(ys)
                except Exception:
                    send_line(conn, "ERROR invalid PLAY syntax")
                    continue

                
                with lock:
                    idx = state.players.index(name)
                    opp = state.players[1 - idx]
                   
                    if not (1 <= x <= WIDTH and 1 <= y <= WIDTH):
                        send_line(conn, "ERROR coordinate out of bounds")
                        continue
                    
                    already = False
                    for s in state.shots[name]:
                        if s[0] == x and s[1] == y:
                            already = True; break
                    if already:
                        send_line(conn, "ERROR already shot here")
                        continue

                   
                    opp_boats = [boat_from_dict(bd) for bd in state.boats.get(opp,[])]
                    hit = isAStrike(opp_boats, x, y)
                    state.shots[name].append([x, y, bool(hit)])
                  
                    send_line(conn, f"RESULT {1 if hit else 0}")
                    
                    if opp in clients:
                        cconn, crole = clients[opp]
                        send_line(cconn, f"OPPONENT_PLAYED {x} {y} {1 if hit else 0}")
                    broadcast_to_observers(f"OPPONENT_PLAYED {x} {y} {1 if hit else 0}")

                    
                    if check_victory(state.shots[name], opp):
                        state.over = True
                        scores[name]["wins"] = scores.get(name,{}).get("wins",0) + 1
                        scores[opp]["losses"] = scores.get(opp,{}).get("losses",0) + 1
                        save_scores(scores)
                        send_line(conn, "WIN")
                        if opp in clients:
                            send_line(clients[opp][0], "LOSE")
                        broadcast(f"SCOREBOARD {json.dumps(scores)}")
                    else:
                        # next player's turn
                        with lock:
                            state.current_index = 1 - state.current_index
                            notify_turns()
                continue

            if cmd == "RECONNECT":
                
                if len(parts) < 2:
                    send_line(conn, "Erreur lors de la reconnection : le nom est a spécifié")
                    continue
                rname = parts[1]
                with lock:
                    if rname in state.boats:
                        
                        name = rname
                        clients[name] = (conn, "PLAYER")
                        addr2name[conn.fileno()] = name
                        
                        send_line(conn, "STATE " + state.to_json())
                        send_line(conn, "SCOREBOARD " + json.dumps(scores))
                    else:
                        send_line(conn, "ERROR unknown player to reconnect")
                continue

            if cmd == "QUIT":
                break

            
            send_line(conn, "ERREUR: commande inconnu")
    except Exception as e:
        print(e)
    finally:
        try:
            if conn.fileno() in addr2name:
                n = addr2name.pop(conn.fileno())
                with lock:
                    if n in clients:
                        clients.pop(n, None)
                        
            conn.close()
        except Exception:
            pass

def broadcast(msg):
    with lock:
        for n, (c, role) in list(clients.items()):
            try:
                send_line(c, msg)
            except Exception:
                pass

def broadcast_to_observers(msg):
    with lock:
        for n, (c, role) in list(clients.items()):
            if role == "OBSERVER":
                try:
                    send_line(c, msg)
                except Exception:
                    pass

def notify_turns():
    with lock:
        if len(state.players) < 2:
            return
        current = state.players[state.current_index]
        for name, (c, role) in clients.items():
            if name == current:
                send_line(c, "YOUR_TURN")
            elif name in state.players:
                send_line(c, "WAIT")
            else:
                
                send_line(c, f"INFO observeur; current turn: {current}")

def main():
    print("Connecté au serveur. En attente de 2 joueurs ...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", PORT))
    sock.listen(50)
    try:
        while True:
            conn, addr = sock.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    finally:
        sock.close()

if __name__ == "__main__":
    main()
