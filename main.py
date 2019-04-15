#!/usr/bin/python3
# -*- coding: utf-8 -*-
import sys
import socket
import asyncore

host = "10.0.0.16"
port = 12345                # Reserve a port for your service.

# from PyQt5 import QtCore, QtGui, QtWidgets, uic
# class MainWindow(QtWidgets.QMainWindow):
# 	def __init__(self):
# 		super(MainWindow, self).__init__()
# 		uic.loadUi('main_window.ui', self)
# 		self.test_button.clicked.connect(self.test_button_clicked)

# 	def test_button_clicked(self, test):
# 		self.test_label.setText("Heloo")

# app = QtWidgets.QApplication(sys.argv)
# main_window = MainWindow()
# main_window.show()
# sys.exit(app.exec_())


class IesMonitoringServer(asyncore.dispatcher):
    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(5)

    def handle_accept(self):
    	print('handle_accept')
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            print 'Incoming connection from %s' % repr(addr)
            handler = ClientHandler(sock)


class ClientHandler(asyncore.dispatcher_with_send):

    def handle_read(self):
    	print('handle_read')
        data = self.recv(8192)
        if data:
            self.send(data)




ies_monitoring_server = IesMonitoringServer(host, port)
asyncore.loop()












s = socket.socket()         # Create a socket object
# host = socket.gethostname() # Get local machine name
s.bind((host, port))        # Bind to the port

s.listen(5)                 # Now wait for client connection.
while True:
   c, addr = s.accept()     # Establish connection with client.
   print ('Got connection from', addr)
   c.send(b'Thank you for connecting')
   # c.close()                # Close the connection