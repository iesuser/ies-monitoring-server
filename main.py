#!/usr/bin/python3
# -*- coding: utf-8 -*-
import sys
import socket
import threading
import json
import time

host = "10.0.0.16"
port = 12345                # Reserve a port for your service.
s = socket.socket()         # Create a socket object
buffer_size = 8192
exit_flag = False

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
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(5)

# ფუნქცია ელოდება client-ებს და ამყარებს კავშირს.
# კავშირის დათანხმების შემდეგ იძახებს connection_hendler - ფუნქციას
def accept_connections():
    # global exit_flag
    # print(threading.enumerate())
    print('Ready for accept connections...')
    while True:
        try:
            connection, addr = s.accept()
            threading.Thread(target = client_handler_thread, args = (connection, addr)).start()
        except Exception as err:
            pass
        if exit_flag:
            break

# json ტექსტს აკონვერტირებს dictionary ტიპში
def bytes_to_dictionary(json_text):
    teqsti = json_text.decode("utf-8")
    print(type(teqsti))
    print("|" + teqsti + "|")
    dictionary = json.loads(teqsti)
    return dictionary

    # return json.loads(json_text.decode("utf-8"))

# client-თან კავშირის დამყარების შემდეგ ფუნქცია კითხულობს
# მის შეტყობინებას
def client_handler_thread(connection, addr):
    print ('|Got connection from', addr, "|")
    while True:
        time.sleep(0.5)
        json_message = connection.recv(buffer_size)
        if not json_message.decode("utf-8"):
            print("Message not receved")
            continue
        else:
            message = bytes_to_dictionary(json_message)
            # clien-ს გავუგზავნოთ მესიჯის id იმის პასუხად რომ შეტყობინება მივიღეთ
            if message["message_type"] != "blockkk":
                connection.send(bytes(message["message_id"],"utf-8"))
                print("|sending : " + message["message_id"] + "|")
            connection.close()
            print("|Closed client connection", addr, "|")
            break

   

def command_listener():
    global exit_flag
    while True:
        if input("") == "exit":
            print("Bye...")
            s.shutdown(socket.SHUT_RDWR)
            s.close()
            exit_flag = True
            break

# ფუნქცია რომელიც ეშვება პირველი პროგრამის ჩართვის დროს
def main():
    start_listening()
    threading.Thread(target = accept_connections).start()
    command_listener()

if __name__ == "__main__":
    main()
