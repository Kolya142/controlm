#!/bin/python3
import json
import os
import signal
import sys
import time
from typing import List

CONFIG = "controlm.json"
PIPE_PATH_LISTENER = "/tmp/controlm.pipe0"
PIPE_PATH_SENDER = "/tmp/controlm.pipe1"
TEMP_FILE_PATH = "/tmp/controlm.temp"

def send_command(cmd: str) -> str:
    for i in range(3):
        f = os.fork()
        if f == 0:
            with open(PIPE_PATH_LISTENER, 'wb') as f:
                f.write(cmd.encode())
            time.sleep(1)
            f = os.open(PIPE_PATH_SENDER, os.O_RDONLY)
            b = os.read(f, 500)
            os.close(f)
            with open(TEMP_FILE_PATH, 'wb') as f:
                f.write(b)
            exit()
        else:
            print(f"try {i+1}")
            time.sleep(3)
            try:
                with open(TEMP_FILE_PATH, 'rb') as f:
                    b = f.read()
                    if not b:
                        os.kill(f, signal.SIGKILL)
                        os.waitpid(f)
                        continue
                    return b.decode()
            except Exception:
                os.kill(f, signal.SIGKILL)
                os.waitpid(f)
                continue
            with open(TEMP_FILE_PATH, 'wb') as f:
                f.write(b'')
    print("connect to daemon failed")
    sys.exit(1)

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
