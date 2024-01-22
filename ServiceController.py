#
# ServiceController  - (MQTT Client)
#
# SubscribeThread Topic:
# systemd/status
# systemd/[service]/start
# systemd/[service]/stop
#
# PublishThread Topic:
# application/status
# application/
#

import subprocess
import sys
import time
import paho.mqtt.client as mqClient
import logging
import json
import threading
import signal

log = logging.getLogger('ServiceController')

SERVICE_LIST = []
SERVICE_JSON = {}
DEVICE_ID="dev1"
CLOSE_SERVICE=0

#signal handler
def signal_handler(sig, frame):
    global CLOSE_SERVICE
    log.info('You pressed Ctrl+C!')
    CLOSE_SERVICE=1

# Shell Command -------------------------------------------
def shellCmd(list):
    try:
        proc = subprocess.Popen(list, stdout=subprocess.PIPE, shell=True)
        (out, err) = proc.communicate()
        return out.decode('utf').replace("\n", "")
    except:
        log.error("Shell command failed %s" % str(list))
        return ""
    
def isActive(service):
    cmd = str("systemctl is-active %s" % service)
    result = shellCmd([cmd])
    if result == 'active':
        return True
    return False

def isEnable(service):
    cmd = str("systemctl is-enabled %s" % service)
    result = shellCmd([cmd])
    if result == 'enabled':
        return True
    return False



# MQTT Status Client --------------------------------------------------
def status_msg(mosq, obj, msg):
    log.debug("%-20s %d %s" % (msg.topic, msg.qos, msg.payload))
    try:
        payload = {}
        payload["systemd"] = shellCmd(['systemctl is-system-running'])
        payload["services"] = SERVICE_LIST   
        #for service in SERVICE_LIST:
        #    payload[service] = [isActive(service),isEnable(service)]     
        mosq.publish(str("systemd/status/%s" % DEVICE_ID), json.dumps(payload))
    except:
        log.error("status msg failed")

class ServicesTask(threading.Thread):
    TOPIC="systemd/%s" % DEVICE_ID
    def __init__(self):
        threading.Thread.__init__(self)
        self.stop = False

    def msg_in(self, mosq, obj, msg ):
        log.debug("%-20s %d %s" % (msg.topic, msg.qos, msg.payload))
        topicTree = msg.topic.split("/")
        service = topicTree[-2]
        outTopic = self.TOPIC + "/" + service
        try:
            cmd = msg.payload.decode('utf8')
            payload = "no such service"
            if service in SERVICE_LIST:
                payload = "unknown cmd"
                if topicTree[-1] == "get":
                    if( isActive(service) and isEnable(service) ):
                        payload = "running"
                    else:
                        payload = "stopped"
                elif topicTree[-1] == "set":
                    if (cmd == "stop"):
                        shellCmd("systemctl stop %s" % service)
                        payload = "stopped"
                    elif (cmd == "start"):
                        shellCmd("systemctl start %s" % service)
                        payload = "running"
                        
            log.debug("%s, %s" % (outTopic,payload))
            mosq.publish(outTopic, payload)
        except:
            log.error("failed to set status")

    def msg_out(self, mosq, obj, mid):
        pass

    def run(self):
        client = mqClient.Client()
        client.on_message = self.msg_in
        client.on_publish = self.msg_out
        client.connect("localhost", 1883) #Default 60 keepAlive
        client.subscribe([(str("systemd/%s/+/get" % DEVICE_ID),0),(str("systemd/%s/+/set" % DEVICE_ID),0),("systemd/all/+/get",0), ("systemd/all/+/set",0)]) #Default 0 QOS

        while(client.loop() == 0 and self.stop is False):
            pass

        client.disconnect()
        log.info("Service Task stopped")
        


def pub_msg_out(mosq, obj, mid):
    pass


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    #Set logger format
    logging.basicConfig(format='%(asctime)-15s %(threadName)-8s %(levelname)-8s %(lineno)-3s:%(module)-15s  %(message)s', level=logging.DEBUG)

    #Get Inputtet Serices (Limit published services to this list)
    SERVICE_LIST = sys.argv[1:]   

    #Get all Services
    jservices = shellCmd("systemctl list-unit-files -t service  --plain --no-legend --output json")
    SERVICE_JSON = json.loads(jservices)
    
    servicelist=[]
    for service in SERVICE_JSON:
        servicelist.append(service['unit_file'].replace(".service",""))
    
    #Check if service is in the inputted service list
    if len(SERVICE_LIST) > 0:
        haslist = []
        for service in SERVICE_LIST:
            if service in servicelist:
                haslist.append(service)
            else:
                log.error("%s not available on %d" % (service, DEVICE_ID))

        SERVICE_LIST = haslist
    else:
        #Make all services available
        SERVICE_LIST = servicelist



    statusClient = mqClient.Client()
    statusClient.on_message = status_msg
    statusClient.on_publish = pub_msg_out
    statusClient.connect("localhost", 1883) #Default 60 keepAlive
    statusClient.subscribe("systemd") #Default 0 QOS
    
    #Start Service task Handle service commands
    serviceClient = ServicesTask()
    serviceClient.start()

    now = time.time()
    while(statusClient.loop() == 0 and CLOSE_SERVICE == 0):
        pass

    statusClient.disconnect()
    
    #Stop ServiceTask and wait for service client task to finish
    serviceClient.stop = True
    serviceClient.join()


    log.info("Exiting ServiceController...")

