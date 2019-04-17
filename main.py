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

# ფუნქცია ხსნის პორტს და იწყებს მოსმენას
def start_listening():
    print('Start listening...')
    s.bind((host, port))        # Bind to the port
    s.listen(5)                 # Now wait for client connection.

# ფუნქცია ელოდება client-ებს და ამყარებს კავშირს
# კავშირის დათანხმების შემდეგ იძახებს connection_hendler - ფუნქციას
async def accept_connections():
    print('Ready to accept connections')
    while True:
       connection, addr = s.accept()     # Establish connection with client.
       connection_hendler(connection, addr)

# json ტექსტს აკონვერტირებს dictionary ტიპში
def json_to_dictionary(json_text):
    return json.loads(json_text.decode("utf-8"))

# client-თან კავშირის დამყარების შემდეგ ფუნქცია კითხულობს
# მის შეტყობინებას
def connection_hendler(connection, addr):
    print ('Got connection from', addr)
    json_message = connection.recv(4096)

    message = json_to_dictionary(json_message)

    print(message["message_type"])
    print(message["text"])

    connection.send(b'Thank you for connecting')
    connection.close()

# ფუნქცია რომელიც ეშვება პირველი პროგრამის ჩართვის დროს
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