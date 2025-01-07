import json
import os
import sys
import time
from typing import List

CONFIG = "/server/controlm.json"
PIPE_PATH_LISTENER = "/tmp/controlm.pipe0"
PIPE_PATH_SENDER = "/tmp/controlm.pipe1"

def send_command(cmd: str) -> str:
    with open(PIPE_PATH_LISTENER, 'wb') as f:
        f.write(cmd.encode())
    time.sleep(3)
    f = os.open(PIPE_PATH_SENDER, os.O_RDONLY)
    b = os.read(f, 50)
    os.close(f)
    return b.decode()

def run(args: List[str]) -> None:
    n = args[0].lower()
    if n == "help":
        print("commands:\n- status <id>\n- help <id>\n- start <id> \n- stop <id>\n- restart <id>\n- all")
    elif n == 'status':
        print(send_command(f"STATUS {args[1]}"))
    elif n == 'start':
        print(send_command(f"OPEN {args[1]}"))
    elif n == 'stop':
        print(send_command(f"STOP {args[1]}"))
    elif n == 'restart':
        print(send_command(f"RESTART {args[1]}"))
    elif n == 'all':
        with open(CONFIG) as f:
            cs = json.load(f)["tasks"]
            for c in cs:
                print(c['id'], send_command(f"OPEN {c['id']}"))

argv = sys.argv
argc = len(argv)

if argc == 1:
    run(["help"])
    sys.exit(1)

if argc == 2:
    if argv[1] == 'con':
        while True:
            i = input(">>>")
            if i == "exit":
                exit()
            run(i.split(' '))
    elif argv[1] == 'all':
        run(["all"])
    elif argv[1] == 'list':
        c = json.load(open(CONFIG))["tasks"]
        for l in c:
            print(l["id"])
    else:
        run(["help"])
        sys.exit(1)

run(argv[1:])