#
# Application  - (MQTT Client)
#

from PySide6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit, QVBoxLayout, QWidget, QTreeView, QPushButton, QMenu, QAbstractItemView
from PySide6.QtCore import Qt, Signal, Slot, QThread, QMutex
from PySide6.QtGui import QAction, QStandardItem, QStandardItemModel
import sys
import logging
import paho.mqtt.client as mqClient
import json


log = logging.getLogger('Application')

class StatusClient(QThread):
    TOPIC="systemd"
    serviceDictSignal = Signal(dict)
    stdoutSignal = Signal(str)
    def __init__(self):
        QThread.__init__(self)
        self._sList = []
        self.stop = False
        self.mutex = QMutex()
        self.devs = {}
        self._cnt = 0
        
        self._topic = "systemd"
        self._payload = ""
        

    def msg_in(self, mosq, obj, msg ):
        log.debug("%-30s %d %s" % (msg.topic, msg.qos, msg.payload))
        topicTree = msg.topic.split("/")
        if len(msg.payload) > 0:
            try:
                txt = json.loads(msg.payload)
                if self.mutex.tryLock(10000):
                    self.devs[topicTree[-1]] = txt
                    self._cnt = 2
                    self.mutex.unlock()
                else:
                    log.error("Failed to lock")
                #self.serviceDictSignal.emit(msg.payload)
                self.stdoutSignal.emit("%-30s %s" % (msg.topic, txt))
            except:
                log.error("failed to set status")

    def msg_out(self, mosq, obj, mid):
        pass
        

    def getStatus(self):
        #self.client.publish("systemd", "")
        # log.debug("getStatus")
        if self.mutex.tryLock(1000):
            self._topic = "systemd"
            self._payload = ""
            self.mutex.unlock()
        else:
            log.error("failed to getStatus(mtx)")


    def run(self):
        client = mqClient.Client()
        client.on_message = self.msg_in
        client.on_publish = self.msg_out
        client.connect("localhost", 1883) #Default 60 keepAlive
        client.subscribe("systemd/status/#") #Default 0 QOS
        #self.client = client

        while(client.loop() == 0 and self.stop is False):
            self.sleep(0.5)
            #log.debug("Hello %d" % self._cnt)
            if self.mutex.tryLock(1000):
                if self._cnt > 0:
                    if self._cnt == 1:
                        self.serviceDictSignal.emit(self.devs)
                    self._cnt -= 1

                if self._topic != "":
                    log.debug("Topic%-20s Payload:%s" % (self._topic,self._payload))
                    client.publish(self._topic, self._payload)
                    self._topic =""
                    self._payload=""
                self.mutex.unlock()
        client.disconnect()
        log.debug("closing status client")
            
            
class ServiceCtrlClient(QThread):
    stdoutSignal = Signal(str)
    def __init__(self, name, data, parent=None):
        QThread.__init__(self)
        self.name = name
        self.data = data
        self.stop = False
        self.mutex = QMutex()
        self._topic = ""
        self._payload = ""

    def msg_in(self, mosq, obj, msg ):
        payload = msg.payload.decode("utf8")
        log.debug("%-20s %d %s" % (msg.topic, msg.qos, payload))
        self.stdoutSignal.emit("%-30s %s" % (msg.topic, payload))

    def msg_out(self, mosq, obj, mid):
        pass

    def get_service(self, sname):
        log.debug("get %s" % sname)
        if self.mutex.tryLock(1000):
            self._topic = "systemd/%s/%s/get" % (self.name, sname)
            self._payload = ""
            self.mutex.unlock()

    def set_service(self, sname, cmd):
        if self.mutex.tryLock(1000):
            self._topic = "systemd/%s/%s/set" % (self.name, sname)
            self._payload = cmd
            self.mutex.unlock()

    def run(self):
        client = mqClient.Client()
        client.on_message = self.msg_in
        client.on_publish = self.msg_out
        client.connect("localhost", 1883) #Default 60 keepAlive
        client.subscribe("systemd/%s/+" % self.name) #Default 0 QOS
        

        while(client.loop() == 0 and self.stop is False):
            self.sleep(0.2)
            if self.mutex.tryLock(1000):
                if self._topic != "":
                    log.debug("Topic-%-20s Payload:%s" % (self._topic,self._payload))
                    client.publish(self._topic, self._payload)
                    self._topic =""
                    self._payload=""

                self.mutex.unlock()
            
        client.disconnect()
        log.debug("%s client closed" % self.name)

class ServiceTree(QTreeView):
    def __init__(self, stdout, parent=None):
        super(ServiceTree, self).__init__(parent)
        self._devs = {}
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.onContextMenu)
        #self.setSelectionMode(QAbstractItemView.MultiSelection)
        model = QStandardItemModel(0,1)
        self.setModel(model)
        self.menu = QMenu()
        self.header().setVisible(False)
        self.statusMenu = QAction("Status")
        self.stopMenu = QAction("Stop")
        self.startMenu = QAction("Start")
        self.statusMenu.triggered.connect(self.statusObj)
        self.stopMenu.triggered.connect(self.stopObj)
        self.startMenu.triggered.connect(self.startObj)
        self.menu.addAction(self.statusMenu)
        self.menu.addAction(self.stopMenu)
        self.menu.addAction(self.startMenu)
        self.selection = []
        self.stdout = stdout

    @Slot()
    def startObj(self):
        if len(self.selection) != 2:
            return
        
        if self.selection[1] in self._devs:
            self._devs[self.selection[1]].set_service(self.selection[0],"start")

    @Slot()
    def stopObj(self):
        if len(self.selection) != 2:
            return
        
        if self.selection[1] in self._devs:
            self._devs[self.selection[1]].set_service(self.selection[0],"stop")

    @Slot()
    def statusObj(self):
        if len(self.selection) != 2:
            return
        
        if self.selection[1] in self._devs:
            self._devs[self.selection[1]].get_service(self.selection[0])

    @Slot(int)
    def onContextMenu(self, position):
        indexes = self.selectedIndexes()
        self.selection.clear()
        for item in indexes:
            itemData = self.model().itemData(item)
            parentData = [""]
            if item.parent().isValid():
                parentData = self.model().itemData(item.parent())
                self.selection = [itemData[0], parentData[0]]
                self.menu.exec(self.viewport().mapToGlobal(position))
            #log.debug("%s,%s" % (itemData[0], parentData[0]) )



    @Slot(dict)
    def createTree(self, devdict):
        log.debug("Create tree %s" % str(devdict))
        for dev in devdict:
            if dev not in self._devs:
                scc = ServiceCtrlClient(dev, devdict[dev])
                scc.start()
                scc.stdoutSignal.connect(self.stdout)
                self._devs[dev] = scc

        model = self.model()
        if(model is not None):
            if(model.hasChildren() == True):
                model.removeRows(0, model.rowCount())

        cnt = 0
        for dev in self._devs:
            siname = QStandardItem(self._devs[dev].name)
            data = self._devs[dev].data
            model.setItem(cnt, 0, siname)

            services = data.get("services",[])
            for service in services:
                siname.appendRow(QStandardItem(service))
            cnt += 1

    def close(self):
        for dev in self._devs:
            self._devs[dev].stop = True
            self._devs[dev].wait()



if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)-15s %(threadName)-8s %(levelname)-8s %(lineno)-3s:%(module)-15s  %(message)s', level=logging.DEBUG)

    app = QApplication()
    win = QMainWindow()
    win.setWindowFlags(Qt.Widget)
    win.resize(500, 380)
    statusClient = StatusClient()
    layout = QVBoxLayout()
    widget1 = QWidget()
    widget1.setLayout(layout)

    #widgets in centalWidget
    txtedit = QPlainTextEdit()
    pushbutton = QPushButton("Refresh")
    serviceTree = ServiceTree(stdout=txtedit.appendPlainText)

    #connect Signals
    statusClient.stdoutSignal.connect(txtedit.appendPlainText)
    pushbutton.clicked.connect(statusClient.getStatus)
    statusClient.serviceDictSignal.connect(serviceTree.createTree)

    #add layouts
    layout.addWidget(pushbutton)
    layout.addWidget(serviceTree)
    layout.addWidget(txtedit)
    layout.setStretch(1, 80)
    layout.setStretch(2, 20)
    win.setWindowTitle("Application")
    statusClient.start()
    win.setCentralWidget(widget1)
    win.show()

    app.exec()
    statusClient.stop = True
    statusClient.wait()
    serviceTree.close()
    log.debug("exiting system")
    sys.exit()
