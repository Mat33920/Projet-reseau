#!/usr/bin/python3


import socket
import threading

def recv_line(conn):
    data = b""
    while not data.endswith(b"\n"):
        part = conn.recv(1024)
        if not part:
            return None
        data += part
    return data.decode().strip()

def send(conn, msg):
    conn.sendall((msg + "\n").encode())

def handle_player(conn, player_id, other_conn):
    pass  

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 5000))
    s.listen(2)
    print("Serveur en attente de 2 joueurs...")

    conn1, _ = s.accept()
    send(conn1, "WELCOME 0")

    conn2, _ = s.accept()
    send(conn2, "WELCOME 1")

    print("Les 2 joueurs sont connectés.")

    send(conn1, "START")
    send(conn2, "START")

    current = conn1
    other = conn2

    while True:
        send(current, "YOUR_TURN")
        send(other, "WAIT")

        msg = recv_line(current)
        if msg is None:
            break

        if msg.startswith("PLAY"):
            _, x, y = msg.split()
            send(other, msg) 

            res = recv_line(other) 
            send(current, res)      

            if res == "RESULT 1":  
            
                pass

           
            if res == "WIN":
                send(other, "LOSE")
                break
            if res == "LOSE":
                send(other, "WIN")
                break

       
        current, other = other, current

    conn1.close()
    conn2.close()
    s.close()

if __name__ == "__main__":
    main()
