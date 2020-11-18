import os
import sys
import threading
import time
import re
import codecs


def main(argv=sys.argv):
    options = ['-h']

    # parameter check
    hashrate = 0
    args = sys.argv[1:]
    if len(args) > 0 and len(args) % 2 != 0:
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
                hashrate = int(value)
            except ValueError as e:
                print ('invalid parameter value of ' + value)

    check_stream = CheckStream(hashrate=hashrate)
    check_stream.start()


class CheckStream(threading.Thread):
    def __init__(self, hashrate = 0):
        self.__violated = 0
        self.__hashrate = hashrate
        threading.Thread.__init__(self)

    def run(self):
        while True:
            files = sorted(filter(os.path.isfile, os.listdir('.')), key=os.path.getmtime, reverse=True)
            files = [f for f in files if '.log' in f or '.txt' in f]
            passed = False
            hashrate = 0
            if len(files) > 0:
                log_file = os.path.join(sys.path[0], files[0])
                with codecs.open(log_file, encoding='utf-8', errors='ignore') as f:
                    for line in reversed(f.readlines()):
                        line = line.rstrip()
                        separator = None
                        if ', shares' in line:
                            separator = ', shares'
                        elif 'Total Shares:' in line:
                            separator = 'Total Shares:'
                        if not separator:
                            continue
                        head = line.strip(separator)
                        floats = re.findall('\d+\.\d+', head)
                        hashrate = int(floats[0].split('.')[0]) if len(floats) > 0 else 0
                        if self.__hashrate > 0 and hashrate < self.__hashrate or hashrate < 20:
                            self.__violated += 1
                        else:
                            passed = True
                        break
                    f.close()

            if passed:
                if 'pheonix.log' in log_file or 'claymore.log' in log_file:
                    self.__violated = 0
                else:
                    with open(log_file, 'w') as f:
                        f.write('')
                        f.close()
                        self.__violated = 0
            else:
                self.__violated += 1
                print ('not passed count: ' + str(self.__violated))

            if self.__violated >= 3:
                print ('reboot in 5 seconds')
                time.sleep(5)
                os.system('reboot')
                break

            print ('current hashrate: {hashrate} | target hashrate: {target}'.format(
                hashrate=hashrate,
                target=self.__hashrate
            ))
            time.sleep(15)


if __name__ == '__main__':
    main()
