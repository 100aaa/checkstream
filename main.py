import os
import sys
import threading
import time
import signal
from datetime import datetime
import socket
import json
VERSION = 'v1.0.1'


def signal_handler(signal, frame):
    print ('good bye :)')
    exit(0)


def main(argv=sys.argv):
    global VERSION
    signal.signal(signal.SIGINT, signal_handler)

    # parameter check
    options = ['-h', '-c', '-p', '-i', '-psw']
    target_hashrate = 0
    reboot_count = 3
    port = 3333
    password = ''
    interval = 10

    args = argv[1:]

    if len(args) > 0 and args[0] == '--help':
        print ('usage: streamcheck'
               '\t-h {target hashrate} | default: 0 [0-]'
               '\n\t\t\t-c {reboot counts} | default: 3 [0-] | reboot if it fails {reboot_counts} in a row'
               '\n\t\t\t-p {port} | default: 3333 [0-65535] | cdm port'
               '\n\t\t\t-psw {password} | default: "" | cdm password'
               '\n\t\t\t-i {interval} | default : 10 | hashrate check interval')
        return

    if len(args) > 0 and args[0] == '--version':
        print (VERSION)
        return

    elif len(args) % 2 != 0:
        print ('invalid number of parameters')
        return

    for idx, arg in enumerate(args):
        if idx % 2 != 0:
            continue
        option = arg
        value = args[idx + 1]
        if option not in options:
            print ('invalid parameter name of ' + sys.argv[1])
            return
        ## options...
        if option == '-h':
            try:
                target_hashrate = int(value)
            except ValueError as e:
                print ('invalid parameter value of ' + value)
        if option == '-i':
            interval = int(value)
        if option == '-c':
            reboot_count = int(value)
        if option == '-p':
            port = int(value)
        if option == '-psw':
            password = value

    stream_check = StreamCheck(target_hashrate=target_hashrate, reboot_count=reboot_count, interval=interval, port=port, password=password)
    stream_check.daemon = True
    stream_check.start()
    while stream_check.is_alive:
        time.sleep(1)


class StreamCheck(threading.Thread):
    def __init__(self, target_hashrate=0, reboot_count=3, interval=30, port=3333, password=''):
        self.__target_hashrate = target_hashrate
        self.__reboot_count = reboot_count
        self.__port = port
        self.__interval = interval
        self.__password = password
        threading.Thread.__init__(self)

    def run(self):
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        elif __file__:
            application_path = os.path.dirname(__file__)
        else:
            application_path = ''
        while True:
            hashrate = self.get_hashrate()
            if hashrate > 0:
                break
            else:
                print ('waiting for another 5 seconds...')
                time.sleep(5)

        print ('hashrate checkup has started.')
        reboot_count = 0

        while True:
            passed = False
            hashrate = self.get_hashrate()

            if hashrate > self.__target_hashrate:
                reboot_count = 0
                passed = True

            print ('current hashrate: {hashrate} target hashrate: {target_hashrate} status: {status}'.format(
                hashrate=hashrate,
                target_hashrate=self.__target_hashrate,
                status='OK' if passed else 'ERR'
            ))

            if not passed:
                reboot_count += 1
                print ('not passed count: {not_passed_count} this program will reboot your PC if count hits {reboot_count}'.format(
                    not_passed_count=reboot_count,
                    reboot_count=self.__reboot_count
                ))

            if self.__reboot_count <= reboot_count:
                err_logfile = os.path.join(application_path, 'streamcheck' + datetime.today().strftime('%Y%m%d%H%M%S') + '.log')
                with open(err_logfile, 'w') as f:
                    f.write('current hashrate: {hashrate} target hashrate: {target_hashrate} reboot_count: {reboot_count}'.format(
                        hashrate=hashrate,
                        target_hashrate=self.__target_hashrate,
                        reboot_count=reboot_count
                    ))
                    f.close()
                print ('reboot in 5 seconds')
                os.system('shutdown -t 5 -r -f')
                break

            time.sleep(self.__interval)

    def get_hashrate(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        address = ('127.0.0.1', self.__port)
        try:
            sock.connect(address)
        except Exception as err:
            print ('connection error')
            return 0
        query = {'id': 0, 'jsonrpc': '2.0', 'method': 'miner_getstat1'}
        if self.__password:
            query['params'] = {'psw': self.__password}
        try:
            sock.sendall((json.dumps(query) + "\n").encode('utf-8'))
        except Exception as err:
            print ('failed to send the invoking socket')
            return 0
        try:
            received = sock.recv(4096)
            response = json.loads(received.decode('utf-8'))
        except Exception as err:
            print ('failed to receive a packet from the miner')
            return 0

        sock.close()
        try:
            result = response['result']
            hashrate = result[2].split(';')[0]
            hashrate = float(hashrate[:-3] + '.' + hashrate[-3:])
            return hashrate
        except Exception as err:
            print ('parsing error')
            return 0

if __name__ == '__main__':
    main()
