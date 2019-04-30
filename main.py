#!/usr/bin/python3
# -*- coding: utf-8 -*-
import sys
import socket
import threading
import json
import time

# სერვერის ip მისამართი
host = "10.0.0.16"

# სერვეროს პორტი, რომელზეც ვუსმენთ client-ების შეტყობინებებს
port = 12345
# socket - ებიექტის შექმნა         
socket_object = socket.socket()

# შეტყობინებების მაქსიმალური ზომა ბაიტებში
buffer_size = 8192

# must_close გლობალური ცვლადის საშუალებით გაშვებული thread-ები ხვდებიან რო უნდა დაიხურონ
must_close = False

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
    """ ფუნქცია ხსნის პორტს და იწყებს მოსმენას """

    # ვუთითებთ სოკეტის პარამეტრებს
    socket_object.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # მოსმენის დაწყება
    socket_object.bind((host, port))

    # ვუთითებთ მაქსიმალურ კლიენტების რაოდენობას ვინც ელოდება კავშირის დამყარებაზე თანხმობას
    socket_object.listen(10)

def accept_connections():
    """ ფუნქცია ელოდება client-ებს და ამყარებს კავშირს. 
    კავშირის დათანხმების შემდეგ იძახებს connection_hendler - ფუნქციას """

    print('Ready for accept connections...')

    while True:
        try:
            # თუ client-ი მზად არის კავშირის დასამყარებლად დავეთანხმოთ
            connection, addr = socket_object.accept()

            # თითოეულ დაკავშირებულ client-ისთვის შევქმნათ და გავუშვათ
            # ცალკე thread-ი client_handler_thread ფუნქციის საშუალებით
            threading.Thread(target = client_handler_thread, args = (connection, addr)).start()
        except Exception as err:
            pass

        # შევამოწმოთ თუ must_close არის True
        if must_close:
            # გამოვიდეთ ციკლიდან რაც გამოიწვევს Thread-ის დახურვას
            break

def bytes_to_dictionary(json_text):
    """ json ტექსტს აკონვერტირებს dictionary ტიპში """

    return json.loads(json_text.decode("utf-8"))

def client_handler_thread(connection, addr):
    """ client-თან კავშირის დამყარების შემდეგ ფუნქცია კითხულობს მის შეტყობინებას """

    # გამოაქვს დაკავშირებული კლიენტის მისამართი
    print ('Got connection from', addr)

    while True:
        # ციკლის შეჩერება 0.5 წამით
        time.sleep(0.5)

        # წავიკითხოთ client-სგან გამოგზავნილი შეტყობინება 
        json_message = connection.recv(buffer_size)

        # წაკითხული შეტყობინება თუ ცარიელია გამოვტოვოთ ციკლის მიმდინარე ბიჯი
        if not json_message.decode("utf-8"):
            continue
        else:
            # წაკითხული შეტყობინება bytes ობიექტიდან გადავიყვანოთ dictionary ობიექტში
            message = bytes_to_dictionary(json_message)

            # წასაშლელია if-ის პირობა მარტო
            if message["message_type"] != "blockkk":
                # clien-ს გავუგზავნოთ მესიჯის id იმის პასუხად რომ შეტყობინება მივიღეთ
                connection.send(bytes(message["message_id"],"utf-8"))
                # წასაშლელია
                print("sending : " + message["message_id"])
            # წაკითხული შეტყობინების მერე დავხუროთ კავშირი
            connection.close()

            print("Closed client connection", addr)

            # გამოვიდეთ ციკლიდან რაც გულისხმობს client_handler_thread დასრულებას და შესაბამისი Tread-ის დახურვას
            break

def command_listener():
    """ ფუნქცია კითხულობს მომხმარებლის ბრძანებებს """

    global must_close

    while True:
        # დაველოდოთ მომხმარებლის ბრძანებას
        command = input("")

        # თუ მომხმარებლის მიერ შეყვანილი ბრძანება არის `exit` დავხუროთ პროგრამა და socket_object ობიექტი
        if command == "exit":
            print("Bye...")
            socket_object.shutdown(socket.SHUT_RDWR)
            socket_object.close()
            must_close = True
            break

def main():
    """ მთავარი ფუნქცია რომელიც ეშვება პირველი პროგრამის ჩართვის დროს """
    
    # გავხსნათ პორტი და დაველოდოთ client-ის დაკავშირებას
    start_listening()

    # შევქმნათ thread-ი accept_connections ფუნქციის საშუალებით რომელიც ამყარებს კავშირს client-ებთან
    threading.Thread(target = accept_connections).start()

    # დავიწყოთ მომხმარებლის ბრძანებების მოსმენა
    command_listener()

if __name__ == "__main__":
    main()
