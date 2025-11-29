import socket
from game import *
from main import randomConfiguration, displayGame, addShot

def recv_line(sock):
    data = b""
    while not data.endswith(b"\n"):
        data += sock.recv(1024)
    return data.decode().strip()

def send(sock, msg):
    sock.sendall((msg + "\n").encode())

def main():
    import sys
    if len(sys.argv) != 2:
        print("Usage: python client.py <serveur>")
        return

    host = sys.argv[1]

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, 5000))

    print("Connecté au serveur")

    
    msg = recv_line(sock)
    _, pid = msg.split()
    pid = int(pid)

    
    boats = randomConfiguration()
    other_shots = []
    my_shots = []
    game = Game(boats, randomConfiguration())  

    print("Vos bateaux sont placés :")
    displayGame(game, pid)

    while True:
        msg = recv_line(sock)

        if msg == "YOUR_TURN":
            print("\nÀ TON TOUR !")
            col = input("Colonne (A-J) : ").upper()
            x = ord(col) - ord("A") + 1
            y = int(input("Ligne (1-10) : "))

            send(sock, f"PLAY {x} {y}")

        elif msg.startswith("PLAY"):
            _, x, y = msg.split()
            x, y = int(x), int(y)

            is_hit = isAStrike(boats, x, y)
            send(sock, f"RESULT {1 if is_hit else 0}")

            result_text = "TOUCHE" if is_hit else "à l'eau"
            print(f"L'adversaire a tiré en {chr(x+64)} {y} : {result_text}")
        elif msg.startswith("RESULT"):
            _, r = msg.split()
            print("==> TOUCHÉ !" if r == "1" else "==> À l'eau")
        
        elif msg == "WAIT":
            pass
        
        elif msg == "WIN":
            print("Vous avez GAGNÉ !")
            break

        elif msg == "LOSE":
            print("Vous avez PERDU !")
            break

    sock.close()

if __name__ == "__main__":
    main()
