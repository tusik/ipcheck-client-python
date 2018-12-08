from flask import Flask
import socket,json,time,binascii,os
import uuid,configparser,requests
from ipaddress import *
import pingparsing

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
__SERVER_DEBUG__ = False if conf.getint("server","debug")==0 else True
__version__="0.0.4"
if len(__SERVER_UUID__)<10:
    conf.set("server","uuid",str(uuid.uuid1()))
    with open(__CONFILE__,"w+",encoding='utf8') as f:
        conf.write(f)
__SERVER_CHECKSUM__ = checkSum()+binascii.crc32(__SERVER_UUID__.encode())

app = Flask(__name__)

# IP Class for save ping result
class IP:
    address = None
    reachable = False
    min = -0.1
    max = -0.1
    avg = -0.1
    loss = 0
# Result Class for whole ping test result
class Result:
    f = __SERVER_NAME__
    ipv4 = IP()
    ipv6 = IP()
    checkSum = __SERVER_CHECKSUM__
    version = __version__
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
    transmitter.count = 5
    transmitter.destination_host = ip
    ping_res = transmitter.ping()
    if ping_res.returncode == 1 or ping_res.returncode == 0:
        return ping_parser.parse(ping_res).as_dict()
    else:
        return None
@app.route('/getPing/<domain>/<cs>/<ts>', methods=['POST','GET'])
def getPing(domain,cs,ts):
    if str(cs)!=requestCheckSum(domain,ts):
        return 'None'
    result = Result()
    dns_res=socket.getaddrinfo(domain,None)

    ip_list=[]
    for i in dns_res:
        ip_list.append(i[4][0])
    ip_list=set(ip_list)

    for i in ip_list:
        if isinstance(ip_address(i),IPv4Address) and result.ipv4.address == None:
            result.ipv4.address=i
            continue
        if isinstance(ip_address(i),IPv6Address) and result.ipv6.address == None:
            result.ipv6.address=i
            continue


    res_tmp = []

    if result.ipv4.address != None:
        tmp_res = startPing(result.ipv4.address)
        if tmp_res != None:
            res_tmp.append([result.ipv4,tmp_res])

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
    return json.dumps(result,default=to_json,ensure_ascii=False)
def checkClient():
    res = requests.post("https://if.uy/client/"+__version__+"/"+str(checkSum())).text
    return res
if __name__ == '__main__':
    print(":::::::::::::::::::::System Info::::::::::::::::::::::")
    print("My Client version is: ",__version__)
    print("My Client Check Sum is: ",checkSum())
    if checkClient()!="true":
        print("The Client is not a vaildate Client, Please Check your file")
        print(":::::::::::::::::::::ERROR::::::::::::::::::::::")
        os._exit(1)
    print(":::::::::::::::::::::System Info::::::::::::::::::::::")
    app.config['JSON_AS_ASCII'] = False
    app.run(debug=__SERVER_DEBUG__,port=__SERVER_PORT__)
    
