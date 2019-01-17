from flask import Flask
import socket,json,time,binascii,os
import uuid,configparser,requests
from ipaddress import *
import pingparsing
from threading import Timer, Thread
from time import sleep, time
from flask_cors import CORS
def checkSum():
    blocksize = 1024 * 64
    f = open(__file__,"rb")
    str = f.read(blocksize)
    crc = 0
    while(len(str) != 0):
        crc = binascii.crc32(str, crc)
        str = f.read(blocksize)
    f.close()
    return crc

__CONFILE__ = "conf"
conf = configparser.ConfigParser()
conf.read_file(open(__CONFILE__,'r',encoding='UTF-8'))
__SERVER_PORT__ = conf.getint("server","port")
__SERVER_NAME__ = conf.get("server","name")
__SERVER_UUID__ = conf.get("server","uuid")
__SERVER_HOST__ = conf.get("server","host")
__SERVER_DEBUG__ = False if conf.getint("server","debug")==0 else True
__version__="0.1.1"
if len(__SERVER_UUID__)<10:
    conf.set("server","uuid",str(uuid.uuid1()))
    with open(__CONFILE__,"w+",encoding='utf8') as f:
        conf.write(f)
__SERVER_CHECKSUM__ = checkSum()+binascii.crc32(__SERVER_UUID__.encode())

app = Flask(__name__)
CORS(app, resources=r'/*')
class ReportScheduler(object):
    def __init__(self, sleep_time, function):
        self.sleep_time = sleep_time
        self.function = function
        self._t = None

    def start(self):
        if self._t is None:
            self._t = Timer(self.sleep_time, self._run)
            self._t.start()
        else:
            raise Exception("this timer is already running")

    def _run(self):
        self.function()
        self._t = Timer(self.sleep_time, self._run)
        self._t.start()

    def stop(self):
        if self._t is not None:
            self._t.cancel()
            self._t = None

# IP Class for save ping result
class IP:
    def __init__(self):
        self.address = None
        self.reachable = False
        self.min = -0.1
        self.max = -0.1
        self.avg = -0.1
        self.loss = 0
# Result Class for whole ping test result
class Result:
    def __init__(self):
        self.f = __SERVER_NAME__
        self.ipv4 = IP()
        self.ipv6 = IP()
        self.checkSum = __SERVER_CHECKSUM__
        self.version = __version__
def to_json(obj):
    return{
        "from": obj.f,
        "checkSum":obj.checkSum,
        "version":obj.version,
        "ipv6": {
            "address": obj.ipv6.address,
            "reachable": obj.ipv6.reachable,
            "min": obj.ipv6.min,
            "avg": obj.ipv6.avg,
            "max": obj.ipv6.avg,
            "loss": obj.ipv6.loss
        },
        "ipv4":{
            "address": obj.ipv4.address,
            "reachable": obj.ipv4.reachable,
            "min": obj.ipv4.min,
            "avg": obj.ipv4.avg,
            "max": obj.ipv4.avg,
            "loss": obj.ipv4.loss
        }
    }
def requestCheckSum(domain,ts):
    return str(binascii.crc32((__SERVER_UUID__+domain+str(ts)).encode()))

def startPing(ip):
    ping_parser = pingparsing.PingParsing()
    transmitter = pingparsing.PingTransmitter()
    transmitter.count = 1
    transmitter.destination_host = ip
    ping_res = transmitter.ping()
    if ping_res.returncode == 0:
        return ping_parser.parse(ping_res).as_dict()
    else:
        return None
def tcpTest(ip,port=80):
    sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.settimeout(1)
    return sock.connect_ex((ip,port))
def dns_query(domain):
    return socket.getaddrinfo(domain,None)
def clean_ip_list(dns_res):
    ip_list = []
    for i in dns_res:
        ip_list.append(i[4][0])
    return set(ip_list)
def get_ipaddress(ip_list):
    v4=None
    v6=None
    for i in ip_list:
        if (isinstance(ip_address(i),IPv4Address) and v4 == None):
            v4=i
            continue
        if (isinstance(ip_address(i),IPv6Address) and v6 == None):
            v6=i
            continue
    return v4,v6
@app.route('/justPing/<nt>/<domain>/', methods=['GET'])
def justPing(domain,nt):
    ip_list = clean_ip_list((dns_query(domain)))
    v4, v6 = get_ipaddress(ip_list)
    if nt == 'v4':
        obj = startPing(v4)
    else:
        obj = startPing(v6)
    if obj!=None :
        return json.dumps(obj['rtt_avg'])
    else:
        return "-1"
@app.route('/getIP/<domain>/', methods=['GET'])
def getIP(domain):
    ip_list = clean_ip_list((dns_query(domain)))
    v4, v6 = get_ipaddress(ip_list)
    return v4
@app.route('/getPing/<nt>/<domain>/<cs>/<ts>', methods=['POST','GET'])
def getPing(nt,domain,cs,ts):
    # if str(cs)!=requestCheckSum(domain,ts):
    #     return 'None'
    result = Result()
    dns_res = dns_query

    ip_list = clean_ip_list(dns_query(domain))

    result.ipv4.address , result.ipv6.address = get_ipaddress(ip_list)

    res_tmp = []
    if nt == "v4" or nt == "v4v6":
        if result.ipv4.address != None:
            tmp_res = startPing(result.ipv4.address)
            if tmp_res != None:
                res_tmp.append([result.ipv4,tmp_res])
    if nt == "v6" or nt == "v4v6":
        if result.ipv6.address != None:
            tmp_res = startPing(result.ipv6.address)
            if tmp_res != None:
                res_tmp.append([result.ipv6,tmp_res])

    for i in res_tmp:
        i[0].min = i[1]['rtt_min']
        i[0].max = i[1]['rtt_max']
        i[0].avg = i[1]['rtt_avg']
        i[0].reachable = True if (i[1]['packet_receive']>0) else False
        i[0].loss = i[1]['packet_loss_rate']
    res_txt = json.dumps(result,default=to_json,ensure_ascii=False)
    del result
    return res_txt
def checkClient():
    res = requests.post("https://if.uy/client/"+__version__+"/"+str(checkSum())).text
    return res

def sendAlive():
    if requests.get("https://if.uy/client/alive/"+__SERVER_UUID__).status_code != 200:
        print("Get error from server")

if __name__ == '__main__':
    print(":::::::::::::::::::::System Info::::::::::::::::::::::")
    print("My Client version is: ",__version__)
    print("My Client Check Sum is: ",checkSum())
    if checkClient()!="true":
        print("The Client is not a vaildate Client, Please Check your file")
        print(":::::::::::::::::::::ERROR::::::::::::::::::::::")
        #os._exit(1)
    print(":::::::::::::::::::::System Info::::::::::::::::::::::")

    # scheduler = ReportScheduler(0.25*60*60, sendAlive)
    # scheduler.start()

    app.config['JSON_AS_ASCII'] = False
    app.run(debug=__SERVER_DEBUG__,port=__SERVER_PORT__,host=__SERVER_HOST__)

