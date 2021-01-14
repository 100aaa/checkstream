import os
import sys
import threading
import time
import signal
from datetime import datetime
import socket
import json

VERSION = 'v1.0.4'


def signal_handler(signal, frame):
    print ('good bye :)')
    exit(0)


def main(argv=sys.argv):
    global VERSION
    signal.signal(signal.SIGINT, signal_handler)

    # parameter check
    options = ['-h', '-c', '-p', '-i', '-psw', '-msi']
    target_hashrate = 0
    reboot_count = 5
    port = 3333
    password = ''
    interval = 20
    msi_profiles = []

    args = argv[1:]
    if len(args) > 0 and args[0] == '--help':
        print ('usage: streamcheck'
               '\t-h {target hashrate} | default: 0 [0-]'
               '\n\t\t\t-c {reboot counts} | default: 3 [0-] | reboot if it fails {reboot_counts} in a row'
               '\n\t\t\t-p {port} | default: 3333 [0-65535] | cdm port'
               '\n\t\t\t-psw {password} | default: "" | cdm password'
               '\n\t\t\t-i {interval} | default : 10 | hashrate check interval'
               '\n\t\t\t-msi {msi_profiles} | default "" | -msi 0:Profile1, 100:Profile2')
        return

    if len(args) > 0 and (args[0] == '--version' or args[0] == 'v'):
        print (VERSION)
        return

    i = 0

    while i < len(args):
        option = args[i]
        if option not in options:
            print ('invalid parameter name of ' + option)
            return
        if option in ['-msi']:
            n = i + 1
            while n < len(args):
                if args[n] in options:
                    break
                n += 1
            value = ''.join(args[i+1:n])
            i = n
        else:
            value = args[i + 1]
            i = i + 2

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
        if option == '-msi':
            values = value.split(',')
            for v in values:
                try:
                    share = int(v.split(':')[0].replace(' ', ''))
                    directory = v.split(':')[1]
                    msi_profiles.append({
                        'share': share,
                        'directory': directory,
                        'done': False
                    })
                except ValueError as e:
                    print ('invalid parameter value of ' + value)

    stream_check = StreamCheck(target_hashrate=target_hashrate,
                               reboot_count=reboot_count,
                               interval=interval,
                               port=port,
                               password=password,
                               msi_profiles=msi_profiles)
    stream_check.daemon = True
    stream_check.start()
    while stream_check.is_alive:
        time.sleep(1)


class StreamCheck(threading.Thread):
    def __init__(self, target_hashrate=0, reboot_count=3, interval=30, port=3333, password='', msi_profiles=[]):
        self.__target_hashrate = target_hashrate
        self.__reboot_count = reboot_count
        self.__port = port
        self.__interval = interval
        self.__password = password
        self.__msi_profiles = msi_profiles
        self.__initial = True

        threading.Thread.__init__(self)

    def run(self):
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        elif __file__:
            application_path = os.path.dirname(__file__)
        else:
            application_path = ''

        response = self.get_response()

        for profile in self.__msi_profiles:
            if profile['share'] == 0:
                self.copy_profile_relaunch(profile['directory'])
                profile['done'] = True

        while True:
            hashrate = self.get_hashrate(response)
            if hashrate > 0:
                break
            else:
                time.sleep(5)
                print ('waiting... (' + str(hashrate) + ')')
            response = self.get_response()

        print ('hashrate checkup has started.')
        reboot_count = 0
        previous_share = -1

        while True:
            passed = False
            response = self.get_response()
            hashrate = self.get_hashrate(response)
            share = self.get_share(response)

            if share < previous_share:
                for profile in  self.__msi_profiles:
                    profile['done'] = False

            if hashrate > self.__target_hashrate:
                reboot_count = 0
                passed = True

            for profile in self.__msi_profiles:
                if profile['done']:
                    continue
                if profile['share'] <= share:
                    self.copy_profile_relaunch(profile['directory'])
                    profile['done'] = True

            print ('current hashrate: {hashrate} target hashrate: {target_hashrate} share: {share} status: {status}'.format(
                hashrate=hashrate,
                target_hashrate=self.__target_hashrate,
                share=share,
                status='OK' if passed else 'ERR'
            ))

            if not passed:
                reboot_count += 1
                print ('not passed count: {not_passed_count} this program will reboot your PC if count hits {reboot_count}'.format(
                    not_passed_count=reboot_count,
                    reboot_count=self.__reboot_count
                ))

            if self.__reboot_count <= reboot_count:
                err_logfile = os.path.join(application_path, 'streamcheck.log')
                timestamp = datetime.today().strftime('%Y%m%d%H%M%S')
                with open(err_logfile, 'a') as f:
                    f.write('{timestamp}: current hashrate: {hashrate} target hashrate: {target_hashrate} shares found: {share} reboot_count: {reboot_count}'.format(
                        timestamp=timestamp,
                        hashrate=hashrate,
                        target_hashrate=self.__target_hashrate,
                        share=share,
                        reboot_count=reboot_count
                    ))
                    f.close()
                print ('reboot in 5 seconds')
                os.system('shutdown -t 5 -r -f')
                break

            previous_share = share
            time.sleep(self.__interval)

    def get_response(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        address = ('127.0.0.1', self.__port)
        try:
            sock.connect(address)
        except Exception as err:
            print ('connection error')
            return ''
        query = {'id': 0, 'jsonrpc': '2.0', 'method': 'miner_getstat1'}
        if self.__password:
            query['params'] = {'psw': self.__password}
        try:
            sock.sendall((json.dumps(query) + "\n").encode('utf-8'))
        except Exception as err:
            print ('failed to send the invoking socket')
            return ''
        try:
            received = sock.recv(4096)
            response = json.loads(received.decode('utf-8'))
            sock.close()
        except Exception as err:
            print ('failed to receive a packet from the miner')
            return ''

        return response

    def get_hashrate(self, response):
        if response == '':
            return 0
        try:
            result = response['result']
            hashrate = result[2].split(';')[0]
            hashrate = float(hashrate[:-3] + '.' + hashrate[-3:])
            return hashrate
        except Exception as err:
            print ('parsing error')
            return 0

    def get_share(self, response):
        if response == '':
            return 0
        try:
            result = response['result']
            share = int(result[2].split(';')[1])
            return share
        except Exception as err:
            print ('parsing error')
            return 0

    def copy_profile_relaunch(self, directory):
        after_burner_path =  os.path.join('c:\\', 'Program Files (x86)', 'MSI Afterburner')
        try:
            os.system('taskkill /F /IM MSIAfterburner.exe /T')
        except Exception as err:
            print (err)
        try:
            os.chdir(after_burner_path)
            os.system('copy ' + directory + ' Profiles /Y')
        except Exception as err:
            print (err)
        try:
            os.system('start MSIAfterburner.exe')
        except Exception as err:
            print (err)


if __name__ == '__main__':
    main()
