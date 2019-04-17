#!/usr/bin/python3
# -*- coding: utf-8 -*-
import sys
import socket
import asyncio
import json

host = "10.0.0.16"
port = 12345                # Reserve a port for your service.
s = socket.socket()         # Create a socket object

# from PyQt5 import QtCore, QtGui, QtWidgets, uic
# class MainWindow(QtWidgets.QMainWindow):
#   def __init__(self):
#       super(MainWindow, self).__init__()
#       uic.loadUi('main_window.ui', self)
#       self.test_button.clicked.connect(self.test_button_clicked)

#   def test_button_clicked(self, test):
#       self.test_label.setText("Heloo")

# app = QtWidgets.QApplication(sys.argv)
# main_window = MainWindow()
# main_window.show()
# sys.exit(app.exec_())

def start_listening():
    print('start_listening')
    s.bind((host, port))        # Bind to the port
    s.listen(5)                 # Now wait for client connection.
    print(type(s))

async def accept_connections():
    print('accept_connections')
    while True:
       connection, addr = s.accept()     # Establish connection with client.
       connection_hendler(connection, addr)
     
def connection_hendler(connection, addr):
    print ('Got connection from', addr)
    json_message = connection.recv(4096)

    # print(json_message.decode("utf-8"))
    # a = json_message.decode("utf-8")
    message = json.loads(json_message.decode("utf-8"))

    print(message["message_type"])
    print(message["text"])

    connection.send(b'Thank you for connecting')
    # connection.close()



async def main():
    start_listening()       
    accept_connections_task = loop.create_task(accept_connections())
    await asyncio.wait([accept_connections_task])

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except Exception as e:
        pass
    finally:
        loop.close()