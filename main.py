import os
import sys
import threading
import time
import re
import codecs
import signal
from datetime import datetime
VERSION = 'v1.0.0'


def signal_handler(signal, frame):
    print ('good bye :)')
    exit(0)


def main(argv=sys.argv):
    global VERSION
    signal.signal(signal.SIGINT, signal_handler)

    # parameter check
    options = ['-h', '-l', '-c']
    target_hashrate = 0
    delete_log = True
    reboot_count = 3

    args = argv[1:]

    if len(args) > 0 and args[0] == '--help':
        print ('usage: streamcheck'
               '\t[-h {target hashrate} | default: 0, 0~any number | reboot miner if the current hashrate does not exceed the given target hashrate]'
               '\n\t\t\t[-l {delete_log} | default: 0,  {0, 1} | 0: delete log, 1: keep log]'
               '\n\t\t\t[-c {reboot counts} | default: 3, 0~any number | if it fails to pass the checkup {reboot counts} times in a row, miner will be rebooted]')
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
        if option == '-l' and value == '1':
            delete_log = False
        if option == '-c':
            reboot_count = int(value)

    stream_check = StreamCheck(target_hashrate=target_hashrate, delete_log=delete_log, reboot_count=reboot_count)
    stream_check.daemon = True
    stream_check.start()
    while stream_check.is_alive:
        time.sleep(1)


class StreamCheck(threading.Thread):
    def __init__(self, target_hashrate=0, delete_log=True, reboot_count=3):
        self.__target_hashrate = target_hashrate
        self.__delete_log = delete_log
        self.__reboot_count = reboot_count
        threading.Thread.__init__(self)

    def run(self):
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        elif __file__:
            application_path = os.path.dirname(__file__)
        else:
            application_path = ''

        print ('checking your mining status based on the log stream generated by the miner...')
        time.sleep(60)
        reboot_count = 0

        while True:
            files = sorted(filter(os.path.isfile, os.listdir('.')), key=os.path.getmtime, reverse=True)
            files = [f for f in files if '.log' in f or '.txt' in f]
            passed = False
            hashrate = 0
            if len(files) > 0:
                log_file = os.path.join(application_path, files[0])
                with codecs.open(log_file, encoding='utf-8', errors='ignore') as f:
                    for line in reversed(f.readlines()):
                        line = line.rstrip()
                        head = None
                        if ', shares' in line:
                            head = line.split(', shares')[0].split('speed: ')[1]
                        elif 'Total Shares:' in line:
                            head = line.split('Total Shares:')[0]
                        if not head:
                            continue
                        floats = re.findall('\d+\.\d+', head)
                        hashrate = float(floats[0]) if len(floats) > 0 else 0
                        if self.__target_hashrate != 0 and self.__target_hashrate < int(hashrate) or \
                                self.__target_hashrate == 0 and int(hashrate) > 0:
                            passed = True
                        break
                    f.close()

            if passed:
                reboot_count = 0
                if self.__delete_log:
                    with open(log_file, 'w') as f:
                        f.write('')
                        f.close()

            print ('current hashrate: {hashrate} target hashrate: {target_hashrate} status: {status}'.format(
                hashrate=hashrate,
                target_hashrate=self.__target_hashrate,
                status='OK' if passed else 'ERR'
            ))

            if not passed:
                reboot_count += 1
                print ('not passed count: {not_passed_count} this program will reboot your PC if count hits {reboot_count}').format(
                    not_passed_count=reboot_count,
                    reboot_count=self.__reboot_count
                )

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

            time.sleep(30)


if __name__ == '__main__':
    main()
