import json
import os
import secrets
from dataclasses import dataclass
import signal
import subprocess
from time import sleep
from typing import Tuple, List
from datetime import datetime
import psutil

CONFIG = "/server/controlm.json"
LOGPATH = "/server/controlm/log.txt"
PIPE_PATH_LISTENER = "/tmp/controlm.pipe0"
PIPE_PATH_SENDER = "/tmp/controlm.pipe1"

if os.path.exists(PIPE_PATH_LISTENER):
    os.remove(PIPE_PATH_LISTENER)
if os.path.exists(PIPE_PATH_SENDER):
    os.remove(PIPE_PATH_SENDER)
os.mkfifo(PIPE_PATH_LISTENER)
os.mkfifo(PIPE_PATH_SENDER)

def log(t: str, data: str):
    with open(LOGPATH, 'a') as f:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg = f'{t} {now}: {data}'
        f.write(msg+'\n')
        print(msg)


def rndstr() -> str:
    return ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(15))


@dataclass
class SafeDataEntry:
    is_err: bool
    err: str
    value: object


class SafeData:
    data: List[SafeDataEntry]
    name: str
    def __init__(self, data_: list | None = None):
        self.data = []
        self.name = rndstr()
        print(f"init SafeData({self.name})")
        if data_ is not None:
            for d in data_:
                self.append(d)
    def __getitem__(self, index):
        if index < 0 or index >= len(self.data):
            log("ERROR", f"some function try to get unknown data from SafeData({self.name})")
            return
        return self.data[index]
    def __setitem__(self, index, value):
        if index < 0 or index > len(self.data):
            log("ERROR", f"some function try to set unknown data to SafeData({self.name})")
            return
        if index == len(self.data):
            self.data.append(value)
            return
        self.data[index] = value
    def append(self, value):
        if type(value) != SafeDataEntry:
            self.data.append(SafeDataEntry(False, "", value))
            return
        self.data.append(value)
    def __str__(self):
        return str(self.data)


def make_safe_data(*args) -> SafeData:
    s: SafeData = SafeData()
    for arg in args:
        s.append(arg)
    return s

def safe_run_function(func, inp: SafeData) -> SafeData:
    o: SafeData = None
    try:
        o = func(inp)
    except Exception as e:
        r = f"function error:\n{e.__str__()}"
        log("ERROR", r)
        o = SafeData([SafeDataEntry(True, r, None)])
    return o

def safe_wrap(inp: SafeData) -> SafeData:
    f = inp[0].value
    if not f:
        raise Exception("cant get function")
    return SafeData([SafeDataEntry(False, None, f(*[i.value for i in inp.data[1:]]))])


processes = {}

def start(inp: SafeData) -> SafeData:
    app_data = inp[0].value
    if not app_data:
        raise Exception("incorrect input for start()")
    if app_data['id'] in processes:
        raise Exception("already runned")
    pid = os.fork()
    if pid == 0:
        os.setsid()
        while True:
            pid = os.fork()
            if pid == 0:
                os.chdir(app_data["dir"])
                os.system(f'sudo -u {app_data['user']} {app_data['run']}')
                exit()
            else:
                log("INFO", f'opened server {app_data['run']}, with user {app_data['user']} at {app_data['dir']} with pid {pid}')
                os.waitpid(pid, 0)
                if os.WIFEXITED(status) or os.WIFSIGNALED(status):
                    log("INFO", f'process {pid} exit')
                    sleep(1)
    else:
        processes[app_data['id']] = pid
    return SafeData()


def stop(inp: SafeData) -> SafeData:
    app_id = inp[0].value["id"]
    if app_id not in processes:
        raise Exception("can't stop")

    main_pid = processes[app_id]
    try:
        parent = psutil.Process(main_pid)
        children = parent.children(recursive=True)

        for child in children:
            log("INFO", f"Killing child process {child.pid}")
            child.terminate()

        os.waitpid(main_pid, 0)
        processes.pop(app_id)

        log("INFO", f"Application {app_id} stopped successfully")

    except psutil.NoSuchProcess:
        log("WARNING", f"Main process {main_pid} already stopped")
        processes.pop(app_id)
        raise Exception("already stopped")

    return SafeData()



def status(inp: SafeData) -> SafeData:
    id = inp[0].value['id']
    return SafeData([id in processes, processes.get(id, None)])


def restart(inp: SafeData) -> SafeData:
    safe_run_function(stop, inp)
    safe_run_function(start, inp)
    return SafeData()


def get_app_from_id(i: str) -> dict:
    c = json.loads(open(CONFIG, 'r').read())["tasks"]
    for l in c:
        if l["id"] == i:
            return l


def main():
    log("INFO", "start")
    listener = os.open(PIPE_PATH_LISTENER, os.O_RDONLY | os.O_NONBLOCK)
    sender = os.open(PIPE_PATH_SENDER, os.O_RDWR | os.O_NONBLOCK)
    while True:
        try:
            try:
                command = os.read(listener, 50).decode()
            except BlockingIOError:
                sleep(0.05)
                continue
            if not command:
                sleep(0.1)
                continue
            print(command)
            sp = command.split()
            if sp[0] == 'OPEN':
                i = safe_run_function(start, SafeData([get_app_from_id(sp[1])]))[0]
                if i:
                    os.write(sender, b"fail run")
                else:
                    os.write(sender, b"runned")
            if sp[0] == 'STOP':
                i = safe_run_function(stop, SafeData([get_app_from_id(sp[1])]))[0]
                if i:
                    os.write(sender, b"fail stop")
                else:
                    os.write(sender, b"stopped")
            if sp[0] == 'RESTART':
                i = safe_run_function(restart, SafeData([get_app_from_id(sp[1])]))[0]
                if i:
                    os.write(sender, b"fail restart")
                else:
                    os.write(sender, b"restarted")
            if sp[0] == 'STATUS':
                has, pid = safe_run_function(status, SafeData([get_app_from_id(sp[1])])).data
                os.write(sender, f'status: {'run' if has.value else 'stop'}, pid: {pid.value}'.encode())
        except Exception as e:
            log("ERROR", e.__str__())

main()