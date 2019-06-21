#!/usr/bin/python3
# -*- coding: utf-8 -*-
import sys
import socket
import threading
import json
import time
import pymysql
import os
import logging
import argparse


# სერვერის ip მისამართი
server_ip = "10.0.0.124"

# სერვერის პორტი, რომელზეც ვუსმენთ client-ების შეტყობინებებს
port = 12345

# socket - ებიექტის შექმნა
socket_object = socket.socket()

# შეტყობინებების მაქსიმალური ზომა ბაიტებში
buffer_size = 8192

# must_close გლობალური ცვლადის საშუალებით გაშვებული thread-ები ხვდებიან რო უნდა დაიხურონ
must_close = False

# mysql სერვერის ip
mysql_server_ip = "localhost"

# mysql სერვერის პორტი
mysql_server_port = 3306

# mysql სერვერის მონაცემთა ბაზის სახელი
mysql_database_name = "ies_monitoring_server"

# mysql სერვერის მომხარებელი (მოთავსებულია .bashrc ფაილში: export mysql_server_user="")
mysql_server_user = os.environ.get('mysql_server_user')

# mysql სერვერის მომხმარებლის პაროლი (მოთავსებულია .bashrc ფაილში: export mysql_user_pass="")
mysql_user_pass = os.environ.get('mysql_user_pass')

# log ფაილის დასახელება
log_filename = "log"

# ies_monitor აპლიკაციის ip
ies_monitor_ip_dict = {}


class ConsoleFormatter(logging.Formatter):
    """
    კლასით განვსაზღვრავთ ტერმინალში გამოტანილი მესიჯის ფორმატს.

    """
    date_format = "%H:%M:%S"
    default_format = "%(asctime)s [%(levelname)s] %(msg)s"
    info_format = "%(msg)s"

    def __init__(self):
        super().__init__(fmt=ConsoleFormatter.default_format, datefmt=ConsoleFormatter.date_format, style='%')

    def format(self, record):
        # დავიმახსოვროთ თავდაპირველი ფორმატი
        format_orig = self._style._fmt

        if record.levelno == logging.INFO:
            self._style._fmt = ConsoleFormatter.info_format

        # შევცვალოთ თავდაპირველი ფორმატი
        result = logging.Formatter.format(self, record)

        # დავაბრუნოთ თავდაპირველი ფორმატი
        self._style._fmt = format_orig

        return result


# parser - ის შექმნა
parser = argparse.ArgumentParser(description="?!! ...დასაწერია პროგრამის განმარტება")
parser.add_argument('-d', '--debug', action='store_true', help='ლოგგერის დონის შეცვლა debug ზე')
args = parser.parse_args()

# logger - ის შექმნა
logger = logging.getLogger('ies_monitoring_server_logger')
logger.setLevel(logging.DEBUG)

# შევქმნათ console handler - ი და განვსაზღვროთ დონე და ფორმატი
console_handler = logging.StreamHandler(sys.stdout)

# არგუმენტიდან გამომდინარე დავაყენოთ ტერმინალში ლოგგერის დონე
if args.debug:
    console_handler.setLevel(logging.DEBUG)
else:
    console_handler.setLevel(logging.INFO)

console_formatter = ConsoleFormatter()
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# FileHandler - ის შექმნა. დონის და ფორმატის განსაზღვრა
log_file_handler = logging.FileHandler(log_filename)
log_file_handler.setLevel(logging.DEBUG)
log_file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
log_file_handler.setFormatter(log_file_formatter)
logger.addHandler(log_file_handler)


def connection_close(connection, addr=None):
    """ ხურავს (კავშირს სერვერთან) პარამეტრად გადაცემულ connection socket ობიექტს """

    # print(dir(connection))
    if addr is None:
        logger.debug("სოკეტის დახურვა " + str(connection.getsockname()))
    else:
        logger.debug("კლიენტთან კავშირის დახურვა " + str(addr))
    connection.shutdown(socket.SHUT_RDWR)
    connection.close()


def start_listening():
    """ ფუნქცია ხსნის პორტს და იწყებს მოსმენას """

    # ვუთითებთ სოკეტის პარამეტრებს
    socket_object.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # მოსმენის დაწყება
    socket_object.bind((server_ip, port))

    # ვუთითებთ მაქსიმალურ კლიენტების რაოდენობას ვინც ელოდება კავშირის დამყარებაზე თანხმობას
    socket_object.listen(10)

    logger.debug("სოკეტის ინიციალიზაცია")


def accept_connections():
    """ ფუნქცია ელოდება client-ებს და ამყარებს კავშირს.
    კავშირის დათანხმების შემდეგ იძახებს connection_hendler - ფუნქციას """

    logger.info("პროგრამა მზად არის შეტყობინების მისაღებად...")

    while True:
        try:
            # თუ client-ი მზად არის კავშირის დასამყარებლად დავეთანხმოთ
            connection, addr = socket_object.accept()

            # თითოეულ დაკავშირებულ client-ისთვის შევქმნათ და გავუშვათ
            # ცალკე thread-ი client_handler_thread ფუნქციის საშუალებით
            threading.Thread(target=client_handler_thread, args=(connection, addr)).start()
        except Exception as ex:
            # logger.error("კლიენტი ვერ გვიკავშირდება\n" + str(ex))
            pass

        # შევამოწმოთ თუ must_close არის True
        if must_close:
            # გამოვიდეთ ციკლიდან რაც გამოიწვევს Thread-ის დახურვას
            break


def bytes_to_dictionary(json_text):
    """ json ტექსტს აკონვერტირებს dictionary ტიპში """

    return json.loads(json_text.decode("utf-8"))


def insert_message_into_mysql(message):
    """ მესიჯის ჩაწერა მონაცემთა ბაზაში """

    # mysql ბაზასთან კავშირის დამყარების ცდა
    mysql_connection = connect_to_mysql()

    cursor = mysql_connection.cursor()

    # წავიკითხოთ შეტყობინების id
    message_id = message["message_id"]

    # დავთვალოთ მონაცემთა ბაზაში დუპლიკატი შეტყობინებების რაოდენობა
    count = "SELECT COUNT(*) as cnt FROM messages WHERE message_id = '{}'".format(message_id)
    cursor.execute(count)
    duplicate_message_count = cursor.fetchone()[0]

    # ვამოწმებთ მოცემული შეტყობინება მეორდება თუ არა მონაცემთა ბაზაში
    if duplicate_message_count == 0:
        # თუ ვერ დაუკავშირდა mysql-ს
        if not mysql_connection:
            logger.error("არ ჩაიწერა შემდეგი მესიჯი ბაზაში: " + str(message))
            return

        # წავიკითხოთ შეტყობინების დრო
        sent_message_datetime = message["sent_message_datetime"]

        # წავიკითხოთ შეტყობინების ტიპი
        message_type = message["message_type"]

        # წავიკითხოთ შეტყობინების სათაური
        message_title = message["message_title"]

        # წავიკითხოთ შეტყობინების ტექსტი
        text = message["text"]

        # წავიკითხოთ Client-ის ip მისამართი საიდანაც მოვიდა შეტყობინება
        client_ip = message["client_ip"]

        # წავიკითხოთ client-ის სკრიპტის სახელი საიდანაც მოვიდა შეტყობინება
        client_script_name = message["client_script_name"]

        insert_statement = "INSERT INTO `messages` \
        (`message_id`, `sent_message_datetime`, `message_type`, `message_title`, `text`, `client_ip`, `client_script_name`) \
        VALUES('{}', '{}', '{}', '{}', '{}', '{}', '{}')".format(message_id, sent_message_datetime, message_type,
                                                                 message_title, text, client_ip, client_script_name)

        try:
            cursor.execute(insert_statement)
            mysql_connection.commit()
            logger.debug("შეტყობინება ჩაიწერა ბაზაში. შეტყობინების ID: " + message["message_id"])
        except Exception as ex:
            logger.error("არ ჩაიწერა შემდეგი მესიჯი ბაზაში: " + str(message) + "\n" + str(ex))
        cursor.close()
        mysql_connection.close()
    # დუპლიკატ შეტყობინებას არ ვწერთ მონაცემთა ბაზაში
    else:
        logger.warning("მონაცემთა ბაზაში შეტყობინება {" + message_id + "} "
                       "უკვე არსებობს და აღარ მოხდა მისი ხელმეორედ ჩაწერა")


def client_handler_thread(connection, addr):
    """ client-თან კავშირის დამყარების შემდეგ ფუნქცია კითხულობს მის შეტყობინებას """

    # გამოაქვს დაკავშირებული კლიენტის მისამართი
    logger.debug("კავშირი დამყარდა " + str(addr) + " - თან")

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
        for name in message:
            if "ies_monitor" in message:
                ies_monitor_ip_dict.update(message)
                logger.debug("ies_monitor - " + str(addr) + " - დან მიღებული შეტყობინება: " + str(message))
        if "ies_monitor" in message:
            pass
        else:
            logger.debug(str(addr) + " - დან მიღებული შეტყობინება: " + str(message))
            try:
                # მესიჯის ჩაწერა მონაცემთა ბაზაში
                insert_message_into_mysql(message)
                # connection.send(bytes(message, "utf-8"))
                ies_monitor_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                for key in ies_monitor_ip_dict:
                    ies_monitor_ip = ies_monitor_ip_dict.get(key)[0]
                    ies_monitor_port = ies_monitor_ip_dict.get(key)[1]
                    ies_monitor_connection.connect((ies_monitor_ip, ies_monitor_port))
                    ies_monitor_connection.send(bytes("test2", "utf-8"))
                    ies_monitor_connection.close()
                    print("შეტყობინება გაეგზავნა ies_monitor -ს")
            except Exception as ex:
                print(str(ex))

            # client-ს გავუგზავნოთ მესიჯის id იმის პასუხად რომ შეტყობინება მივიღეთ
            try:
                connection.send(bytes(message["message_id"], "utf-8"))
                logger.debug(str(addr) + " - თვის პასუხის დაბრუნება: " + message["message_id"])
            except Exception as ex:
                logger.error(str(addr) + " - ს ვერ ვუგზავნით შეტყობინებას უკან: " + message["message_id"] + "\n" + str(ex))

        # წაკითხული შეტყობინების მერე დავხუროთ კავშირი
        connection_close(connection, addr)

        # გამოვიდეთ ციკლიდან რაც გულისხმობს client_handler_thread დასრულებას და შესაბამისი Thread-ის დახურვას
        break


def command_listener():
    """ ფუნქცია კითხულობს მომხმარებლის ბრძანებებს """

    global must_close

    while True:
        # დაველოდოთ მომხმარებლის ბრძანებას
        command = input("")

        # თუ მომხმარებლის მიერ შეყვანილი ბრძანება არის `exit` დავხუროთ პროგრამა და socket_object ობიექტი
        if command == "exit":
            must_close = True
            connection_close(socket_object)
            logger.info("პროგრამის გათიშვა")
            break


def connect_to_mysql():
    """ ფუნქცია უკავშირდება Mysql სერვერს"""

    try:
        mysql_connection = pymysql.connect(mysql_server_ip,
                                           mysql_server_user,
                                           mysql_user_pass,
                                           mysql_database_name,
                                           port=mysql_server_port)
        logger.debug("მონაცემთა ბაზასთან კავშირი დამყარებულია")
    except Exception as ex:
        logger.error("მონაცემთა ბაზასთან კავშირი წარუმატებელია\n" + str(ex))
        return False
    return mysql_connection


def main():
    """ მთავარი ფუნქცია რომელიც ეშვება პირველი პროგრამის ჩართვის დროს """
    # mysql - თან დაკავშირება
    # global mysql_connection
    # mysql_connection = connect_to_mysql()

    # mysql - თან კავშირის არ ქონის შემთხვევაში იხურება პროგრამა
    # if not mysql_connection:
    #     print("Bye...")
    #     sys.exit(1)

    # გავხსნათ პორტი და დაველოდოთ client-ის დაკავშირებას
    start_listening()

    # შევქმნათ thread-ი accept_connections ფუნქციის საშუალებით რომელიც ამყარებს კავშირს client-ებთან
    threading.Thread(target=accept_connections).start()

    # დავიწყოთ მომხმარებლის ბრძანებების მოსმენა
    threading.Thread(target=command_listener).start()


if __name__ == "__main__":
    main()
    # pass


# def load_gui():
#     from PyQt5 import QtCore, QtGui, QtWidgets, uic

#     class MainWindow(QtWidgets.QMainWindow):
#       def __init__(self):
#           super(MainWindow, self).__init__()
#           uic.loadUi('main_window.ui', self)
#           self.test_button.clicked.connect(self.test_button_clicked)

#       def test_button_clicked(self, test):
#           self.test_label.setText("Hi")
#     global app
#     app = QtWidgets.QApplication(sys.argv)
#     main_window = MainWindow()

#     print(1)
#     main_window.show()
#     print(2)
#     app.exec_()
#     # app.processEvents()
#     # sys.exit(app.exec_())

#     print(3)

#     print(4)
