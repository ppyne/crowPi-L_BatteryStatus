#!/usr/bin/env python3

import smbus
import array
import time
import logging
import PyQt5
from PyQt5.QtGui import (
    QIcon,
)
from PyQt5.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QAction,
)
from PyQt5.QtCore import (
    QObject,
    QThread,
    pyqtSignal,
    pyqtSlot,
    QMutex,
)

address   = 0x03
power_reg = 0x35
bus = smbus.SMBus(1)

mustHalt = False
mutex = QMutex()
def halt(self):
    global mustHalt
    global mutex
    mutex.lock()
    mustHalt = True
    mutex.unlock()

logging.basicConfig(format="%(message)s", level=logging.INFO)

class Worker(QObject):
    finished = pyqtSignal()
    trayMessage = pyqtSignal(int, float, float)
    logMessage = pyqtSignal(str)

    count_charging = 0
    def writePowerNumber(self, power_mark, power_value):
        power_number = 0
        power_Vol = (((power_value*3.0)/1024)*260)/100
        p = power_Vol - 6.0
        if (p < 0.0):
            p = 0
        if (p > 1.2):
            p = 1.2
        p = (p / 1.2) * 100.0

        if (power_mark != 0 and power_mark != 1 and power_mark != 2):
            power_number = 10 # icon unknown
            power_Vol = 0.0
            p = 0.0
        elif (power_mark == 1):
            power_number = 8 # icon charging
        elif (power_Vol >= 7.2):
            power_number = 7 #icon 100%
        elif (power_Vol >= 7.032):
            power_number = 6 # icon 86%
        elif (power_Vol >= 6.852):
            power_number = 5 # icon 71%
        elif (power_Vol >= 6.684):
            power_number = 4 # icon 57%
        elif (power_Vol >= 6.516):
            power_number = 3 # icon 43%
        elif (power_Vol >= 6.348):
            power_number = 2 # icon 29%
        elif (power_Vol >= 6.168):
            power_number = 1 # icon 14%
        elif (power_Vol >= 6.024):
            power_number = 0 # icon 2%
        else:
            power_number = 9 # icon alert

        #self.logMessage.emit(str(power_mark) + "," + str(power_value) +"," + str(power_Vol) +"," + str(power_number))
        self.trayMessage.emit(power_number, power_Vol, p)

        #self.logMessage.emit( "powerInfo: " + str(power_mark) + "," + str(power_number))

        if (power_mark == 0): # If not charging
            #self.logMessage.emit(str(power_mark) + "," + str(power_value) + "," + str(power_Vol) + "," + str(power_number))
            self.count_charging = 0
        elif(power_mark != 0 and self.count_charging == 0): # charging
            #self.logMessage.emit(str(power_mark) + "," + "charging")
            self.count_charging = 1

    power_data = 0
    new_power_data = 0
    flag = 0
    def getPowerValue(self):
        read_power_init = {0,0,0,0,0,0}
        while(1):
            try:   
                read_power_init = bus.read_i2c_block_data(address,power_reg, 6)
                if int(read_power_init[0]) != 170 or int(read_power_init[5]) != 85:
                    self.logMessage.emit("Incomplete data acquisition exception, reread")
                    time.sleep(0.5)
                    continue
                break
            except:
                self.logMessage.emit("IIC read failed, reread")
                #self.logMessage.emit( "powerInfo: 0,5")
                #self.writePowerNumber(-1, 0)
                time.sleep(0.5)
        read_value_init = int(read_power_init[2] * 256 + read_power_init[3]) # High eight bits low eight bits
        #self.logMessage.emit("reread")
        #self.logMessage.emit(str(read_power_init[1]) + " " + str(read_value_init))
        if (int(read_power_init[1]) != 0): # charging data
            #self.logMessage.emit("charging")
            if (int(read_power_init[1]) >=3 and int(read_power_init[1]) < 0): # Abnormal charging data
                #self.logMessage.emit("Abnormal charging status")
                pass
            else:
                self.writePowerNumber(read_power_init[1], read_value_init) # Update data by default
            self.flag = 0
        else:
            #self.logMessage.emit("Not charging, start initializing data")
            self.power_data = self.new_power_data
            if ((self.power_data - read_value_init) >= 0 and self.flag > 1 and (self.power_data > read_value_init)):
                self.writePowerNumber(read_power_init[1], self.new_power_data)
                self.new_power_data = read_value_init
            elif (self.flag <= 1):
                self.writePowerNumber(read_power_init[1], read_value_init)
                self.new_power_data = read_value_init
                self.flag = self.flag + 1

    def run(self):
        global mustHalt
        global mutex
        i = 0
        while True:
            mh = False
            mutex.lock()
            mh = mustHalt
            mutex.unlock()
            if mh:
                break
            self.getPowerValue()
            time.sleep(1);
        self.finished.emit()

def message(msg):
    logging.info("Message: " + str(msg))

app = QApplication([])
app.setQuitOnLastWindowClosed(False)

icons = [
    QIcon("battery_0.png"),
    QIcon("battery_1.png"),
    QIcon("battery_2.png"),
    QIcon("battery_3.png"),
    QIcon("battery_4.png"),
    QIcon("battery_5.png"),
    QIcon("battery_6.png"),
    QIcon("battery_7.png"),
    QIcon("battery_charging.png"), # 8
    QIcon("battery_alert.png"), # 9
    QIcon("battery_unknown.png"), # 10
]

iconnames = [
    "2%", # 2%
    "14%", # 14%
    "29%", # 29%
    "43%", # 43%
    "57%", # 57%
    "71%", # 71%
    "86%", # 86%
    "100%", # 100%
    "Charging", # 8
    "Low battery", # 9
    "Waiting for data", # 10
]

tray = QSystemTrayIcon()

def changeBatteryStatus(n, v, p):
    global tray
    global icons
    tray.setIcon(icons[n])
    v = round(v, 2);
    p = round(p, 1);
    s = ""
    if (n > 7):
        s = iconnames[n] + " " + str(p) + "% " + str(v) + "v"
    else:
        s = str(p) + "% " + str(v) + "v"
    tray.setToolTip(s)
    localTime = time.localtime(time.time())
    logging.info(f"{localTime.tm_year:04d}-{localTime.tm_mon:02d}-{localTime.tm_mday:02d} {localTime.tm_hour:02d}:{localTime.tm_min:02d}:{localTime.tm_sec:02d} Icon: {n} ({iconnames[n]}) ToolTip: {s}")

tray.setIcon(icons[10])
tray.setVisible(True)

thread = QThread()
worker = Worker()
worker.moveToThread(thread)
thread.started.connect(worker.run)
worker.finished.connect(thread.quit)
worker.finished.connect(worker.deleteLater)
worker.finished.connect(app.quit)
thread.finished.connect(thread.deleteLater)
worker.trayMessage.connect(changeBatteryStatus)
worker.logMessage.connect(message)

# Create the menu
menu = QMenu()
quit = QAction("Quit")
quit.triggered.connect(halt)
menu.addAction(quit)
tray.setContextMenu(menu)


thread.start()

app.exec_()
