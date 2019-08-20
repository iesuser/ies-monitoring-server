#!/usr/bin/python3
# -*- coding: utf-8 -*-

# 1. response_ies_monitor_messages ფუნქციაში database_pull_request პაკეტის მოსვლის შემთხვევაში თუ ies_monitoring_server
#    ვერ დაუკავშირდა mysql-ს უკან პასუხი გავუგზავნოთ თუ არა ies_monitor-ს

import sys
import socket
import threading
import pickle
import time
import pymysql
import os
import logging
import argparse
import select
import datetime


# სერვერის ip მისამართი
server_ip = "10.0.0.194"

# სერვერის პორტი, რომელზეც ვუსმენთ client-ების შეტყობინებებს
port = 12345

# socket - ებიექტის შექმნა
socket_object = socket.socket()

# შეტყობინებების მაქსიმალური ზომა ბაიტებში
buffer_size = 8192

# application_is_closing გლობალური ცვლადის საშუალებით გაშვებული thread-ები ხვდებიან რო უნდა დაიხურონ
application_is_closing = False

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

# დაყოვნება პროგრამის ისეთ ციკლებში სადაც საჭიროა/რეკომენდირებულია შენელებული მუშაობა
delay = 0.1

# ლოდინის დრო, თუ რამდენხანს დაველოდებით შეტყობინების მიღებას კავშირის დამყარების შემდეგ
waiting_message_timeout = 60

# ლოდინის დრო, თუ რამდენხანს დაველოდებით შეტყობინების შემდეგი ნაწილის (ბაიტების) მიღებას
next_message_bytes_timeout = 30


# -------------------------------------------------------------------------------------------------


# მესიჯის ჰედერის სიგრძე
HEADERSIZE = 10

# ies_monitor აპლიკაციის ip-ები და პორტი
ies_monitor_ips_and_port = {}


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

    if addr is None:
        logger.debug("სოკეტის დახურვა " + str(connection.getsockname()))
    else:
        logger.debug("კავშირის დახურვა " + str(addr))
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

            # გამოაქვს დაკავშირებული კლიენტის მისამართი
            logger.debug("კავშირი დამყარდა " + str(addr) + " - თან")

            # თითოეულ დაკავშირებულ client-ისთვის შევქმნათ და გავუშვათ
            # ცალკე thread-ი client_handler_thread ფუნქციის საშუალებით
            threading.Thread(target=client_handler_thread, args=(connection, addr)).start()
        except socket.error:
            break
        except Exception as ex:
            logger.error("შეცდომა accept_connections Thread-ში:\n" + str(ex))
            break


def dictionary_message_to_bytes(message):
    """ ფუნქციას dictionary ტიპის მესიჯი გადაყავს bytes ტიპში და თავში უმატებს header-ს """

    # dictionary გადადის bytes ტიპში (serialization)
    message_bytes = pickle.dumps(message)

    # მესიჯის სიგრძე დათვლა
    message_length = len(message_bytes)

    # header-ი გადავიყვანოთ ბაიტებში და დავუმატოთ გადაყვანილი მესიჯი byte-ებში
    message_bytes = bytes(str(message_length).ljust(HEADERSIZE), 'utf-8') + message_bytes

    # ფუნქცია აბრუნებს მესიჯს გადაყვანილს ბაიტებში თავისი header-ით
    return message_bytes


def insert_message_into_mysql(message):
    """ მესიჯის ჩაწერა მონაცემთა ბაზაში """

    # mysql ბაზასთან კავშირის დამყარების ცდა
    mysql_connection = connect_to_mysql()

    # შევამოწმოთ კავშირი mysql ბაზასთან
    if mysql_connection is False:
        # logger -ის გამოძახება
        logger.error("არ ჩაიწერა შემდეგი მესიჯი ბაზაში: " + str(message))
        # ფუნქციიდან გამოსვლა
        return

    # mysql კურსორის შექმნა
    cursor = mysql_connection.cursor()

    # წავიკითხოთ შეტყობინების id
    message_id = message["message_id"]

    # დავთვალოთ მონაცემთა ბაზაში დუპლიკატი შეტყობინებების რაოდენობა
    count = "SELECT COUNT(*) as cnt FROM messages WHERE message_id = '{}'".format(message_id)
    cursor.execute(count)
    duplicate_message_count = cursor.fetchone()[0]

    # ვამოწმებთ მოცემული შეტყობინება მეორდება თუ არა მონაცემთა ბაზაში
    if duplicate_message_count == 0:

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
            return True
        except Exception as ex:
            logger.error("არ ჩაიწერა შემდეგი მესიჯი ბაზაში: " + str(message) + "\n" + str(ex))
            return False
        cursor.close()
        mysql_connection.close()
    # დუპლიკატ შეტყობინებას არ ვწერთ მონაცემთა ბაზაში
    else:
        return False
        logger.warning("მონაცემთა ბაზაში შეტყობინება {" + message_id + "} "
                       "უკვე არსებობს და აღარ მოხდა მისი ხელმეორედ ჩაწერა")


def connect_ies_monitor(ies_monitor_ip, ies_monitor_port):
    """ ფუნქცია უკავშირდება ies_monitoring_server-ს """

    # connection სოკეტის შექმნა
    ies_monitor_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # დავუკავშირდეთ ies_monitoring_server-ს
        ies_monitor_connection.connect((ies_monitor_ip, ies_monitor_port))
        logger.info("ies_monitor-თან კავშირი დამყარებულია ({}, {})".format(ies_monitor_ip, ies_monitor_port))
    except Exception as ex:
        logger.info("სერვერთან კავშირი ვერ დამყარდა ({}, {})\n".format(ies_monitor_ip, ies_monitor_port) + str(ex))
        return False
    return ies_monitor_connection


def send_message_to_ies_monitor(ies_monitor_ip, ies_monitor_port, message, verbose=True):
    """ ფუნქციიის საშუალებით შეიძლება შეტყობინების გაგზავნა ies_monitor-თან """

    # სოკეტის შექმნა
    ies_monitor_connection = connect_ies_monitor(ies_monitor_ip, ies_monitor_port)

    # ies_monitor-თან დაკავშირება
    if ies_monitor_connection is False:
        if verbose is True:
            logger.warning("შეტყობინება ვერ გაიგზავნა, ies_monitor-თან კავშირი ვერ დამყარდა ({},{})\n{}"
                           .format(ies_monitor_ip, ies_monitor_port, message))
        else:
            logger.warning("შეტყობინება ვერ გაიგზავნა, ies_monitor-თან კავშირი ვერ დამყარდა ({},{})"
                           .format(ies_monitor_ip, ies_monitor_port))
        return

    try:
        # შეტყობინების გაგზავნა
        ies_monitor_connection.sendall(dictionary_message_to_bytes(message))
        if verbose is True:
            logger.debug("შეტყობინება გაიგზავნა ies_monitor-თან({},{})\n{}"
                         .format(ies_monitor_ip, ies_monitor_port, message))
        else:
            logger.debug("შეტყობინება გაიგზავნა ies_monitor-თან({},{})"
                         .format(ies_monitor_ip, ies_monitor_port))
    except Exception as ex:
        if verbose is True:
            logger.warning("შეტყობინება ვერ გაიგზავნა ies_monitor-თან({},{})\n{}\n{}"
                           .format(ies_monitor_ip, ies_monitor_port, message, str(ex)))
        else:
            logger.warning("შეტყობინება ვერ გაიგზავნა ies_monitor-თან({},{})\n{}"
                           .format(ies_monitor_ip, ies_monitor_port, str(ex)))

    # სოკეტის დახურვა
    connection_close(ies_monitor_connection, ies_monitor_connection.getsockname())


def notify_ies_monitors_to_update_database(message):
    """ ies_monitor.py-ებს ეგზავნება მესიჯი ახალი შეტყობინების ბაზაში დამატების შესახებ """

    # mysql ბაზასთან კავშირის დამყარების ცდა
    mysql_connection = connect_to_mysql(verbose=False)

    # mysql კურსორის შექმნა
    cursor = mysql_connection.cursor(pymysql.cursors.DictCursor)

    query = """SELECT * FROM messages WHERE message_id = '{}'""".format(message["message_id"])

    cursor.execute(query)

    message = cursor.fetchall()

    mysql_connection.commit()

    for ies_monitor_ip, ies_monitor_port in ies_monitor_ips_and_port.items():

        # შეტყობინების შექმნა ბაზის განახლების შესახებ
        message = {
            "who_am_i": "ies_monitoring_server",
            "message_category": "database_updated",
            "message_data": message
        }

        # ies_monitor-თან იგზავბება შეტყობინება ბაზის განახლების შესახებ
        send_message_to_ies_monitor(ies_monitor_ip, ies_monitor_port, message)

    cursor.close()
    mysql_connection.close()


def response_ies_monitor_messages(message, addr):
    """ ფუნქცია უზრუნველყოფს ies_monitor-იდან გამოგზავნილი შეტყობინებების წაკითხვას და ახდენს შესაბამის რეაგირებას """

    # შევამოწმოთ message dictionary-ის თუ აქვს message_category ინდექსი
    if "message_category" not in message:
        logger.warning("response_ies_monitor_messages ფუნქციას მიეწოდა message dictionary \
                        რომელსაც არ აქვს message_category key-ი")
        return

    if message["message_category"] == "registration":
        # ip წაკითხვა მესიჯიდან
        ies_monitor_ip = message["ip"]

        # port-ის წაკითხვა მესიჯიდან
        ies_monitor_port = message["port"]

        # შევამოწმოთ თუ მუსული ies_monitor.py ის ip არ არის რეგისტრირებული
        # ies_monitor_ips_and_port dictionary-ში
        if ies_monitor_ip not in ies_monitor_ips_and_port:
            # დავარეგისტრიროთ ies_monitor.py-ის ip-ი და პორტი
            ies_monitor_ips_and_port[ies_monitor_ip] = ies_monitor_port

            logger.debug("ies_monitor.py - " + str(addr) + " - დან მოვიდა რეგისტრაციის შეტყობინება: \n" + str(message))

        else:
            logger.debug("ies_monitor.py - " + str(addr) + " - დან მოვიდა რეგისტრაციის შეტყობინება, "
                         "მაგრამ მოთხოვნილი ip უკვე რეგისტრირებულია: \n" + str(message))
        response_message = {
            "who_am_i": "ies_monitoring_server",
            "message_category": "registration_verified"
        }

        # იგზავნება შეყობინება ies_monitor-თან რეგისტრაციის წარმატებით გავლის შესახებ
        send_message_to_ies_monitor(ies_monitor_ip, ies_monitor_port, response_message)

    elif message["message_category"] == "hello":
        # ip წაკითხვა მესიჯიდან
        ies_monitor_ip = message["ip"]

        # port-ის წაკითხვა მესიჯიდან
        ies_monitor_port = message["port"]

        response_message = {
            "who_am_i": "ies_monitoring_server",
            "message_category": "hello"
        }

        send_message_to_ies_monitor(ies_monitor_ip, ies_monitor_port, response_message)

    elif message["message_category"] == "database_pull_request":

        # mysql ბაზასთან კავშირის დამყარების ცდა
        mysql_connection = connect_to_mysql(verbose=False)

        # შევამოწმოთ კავშირი mysql ბაზასთან
        if mysql_connection is False:
            # logger -ის გამოძახება
            logger.warning("მონაცემთა ბაზასთან კავშირი წარუმატებელია და ვერ გაიგზავნა პასუხი ies_monitor-თან შემდეგი მოთხოვნისთვის:\n" + str(message))
            # ფუნქციიდან გამოსვლა
            return

        # ip წაკითხვა მესიჯიდან
        ies_monitor_ip = message["ip"]

        # port-ის წაკითხვა მესიჯიდან
        ies_monitor_port = message["port"]

        # ბოლო შეტყობინების id
        last_message_id = message["last_message_id"]

        # mysql კურსორის შექმნა
        cursor = mysql_connection.cursor(pymysql.cursors.DictCursor)

        # დავთვალოთ მონაცემთა ბაზაში დუპლიკატი შეტყობინებების რაოდენობა
        query = "SELECT * FROM messages WHERE id > {}".format(last_message_id)
        cursor.execute(query)
        message_data = cursor.fetchall()
        mysql_connection.commit()
        for message_row in message_data:
            message_row["sent_message_datetime"] = message_row["sent_message_datetime"].strftime("%Y-%d-%m %H:%M:%S")

        response_message = {
            "who_am_i": "ies_monitoring_server",
            "message_category": "message_data",
            "message_data": message_data
        }

        print("-------------------MESSAGE_DATA-----------------------------\n", message_data)
        cursor.close()
        mysql_connection.close()

        send_message_to_ies_monitor(ies_monitor_ip, ies_monitor_port, response_message, False)
    else:
        logger.warning("ies_monitor -დან მოვიდა უცნობი კატეგორიის შეტყობინება: \n{}".format(message))


def response_ies_monitoring_client_messages(connection, addr, message):
    """
        ფუნქცია უზრუნველყოფს ies_monitoring_client-იდან გამოგზავნილი შეტყობინებების წაკითხვას.
        წაკითხული შეტყობინება იწერება mysql ბაზაში და ბაზის განახლების შესახებ ვატყობინებთ ies_monitor-ებს.
        ies_monitoring_client-ს ვუგზავნით დასტურს შეტყობინების მიღების შესახებ.
    """

    logger.debug("ies_monitoring_client.py - " + str(addr) + " - დან მიღებული შეტყობინება: " + str(message))
    # მესიჯის ჩაწერა მონაცემთა ბაზაში
    if insert_message_into_mysql(message):
        notify_ies_monitors_to_update_database(message)

    # client-ს გავუგზავნოთ მესიჯის id იმის პასუხად რომ შეტყობინება მივიღეთ
    try:
        connection.send(bytes(message["message_id"], "utf-8"))
        logger.debug("ies_monitoring_client.py - " + str(addr) + " - თვის პასუხის დაბრუნება: " + message["message_id"])
    except Exception as ex:
        logger.error("ies_monitoring_client.py - " + str(addr) + " - ს ვერ ვუგზავნით შეტყობინებას უკან: " + message["message_id"] + "\n" + str(ex))


def client_handler_thread(connection, addr):
    """ client-თან კავშირის დამყარების შემდეგ ფუნქცია კითხულობს მის შეტყობინებას """

    receiving_message_time_duration = datetime.datetime.now()

    while application_is_closing is False:

        # ციკლის შეჩერება 0.1 წამით
        time.sleep(delay)

        if (datetime.datetime.now() - receiving_message_time_duration) > datetime.timedelta(seconds=waiting_message_timeout):
            #  ლოგია ჩასამატებელი???

            # კავშირის დახურვა
            connection_close(connection, addr)

            # ფუნქციიდან გამოსვლა
            return

        # select.select ფუნქცია აბრუნებს readers list-ში ისეთ socket-ებს რომელშიც მოსულია წასაკითხი ინფორმაცია
        # ბოლო პარამეტრად მითითებული გვაქვს 0 რადგან ფუნქცია არ დაელოდოს ისეთ სოკეტს რომელზეც შეიძლება წაკითხვა
        readers, _, _, = select.select([connection], [], [], 0)

        # შევამოწმოთ readers list-ი თუ არ არის ცარიელი, რაც ამ შემთხვევაში ნიშნავს იმას რომ connection
        # socket-ზე მოსულია წასაკითხი ინფორმაცია
        if readers:
            # ცვლადი სადაც ვინახავთ მესიჯის ჰედერს და თვითონ მესიჯს
            header_and_message = b''

            # ახალი მესიჯი
            new_message = True

            # მესიჯის მოსვლის დრო
            message_receive_time = datetime.datetime.now()

            # მუდმივი ციკლი მესიჯის წასაკითხათ
            while application_is_closing is False:
                # დაყოვნება
                time.sleep(delay)

                if (datetime.datetime.now() - message_receive_time) > datetime.timedelta(seconds=next_message_bytes_timeout):
                    # კავშირის დახურვა
                    connection_close(connection, addr)

                    # logger ის გამოძახება
                    # logger.warning("{} გამოგზავნილი მესიჯი არ მოვიდა სრულად. გამოგზავნილი მესიჯის ბაიტების რაოდენობა: {}."
                    #                "მიღებული მესიჯის ბაიტების რაოდენობა: {}."
                    #                " მიღებული მესიჯის ნაწილი:\n{}"
                    #                .format(str(addr), message_length, received_message_length, header_and_message.decode("utf-8")))

                    # ფუნქციიდან გამოსვლა
                    return

                readers, _, _, = select.select([connection], [], [], 0)

                # შევამოწმოთ readers list-ი თუ არ არის ცარიელი, რაც ამ შემთხვევაში ნიშნავს იმას რომ connection
                # socket-ზე მოსულია წასაკითხი ინფორმაცია
                if readers:
                    # ახალი მესიჯი
                    # new_message = True

                    # წავიკითხოთ გამოგზავნილი მესიჯის ან მესიჯის ნაწილი
                    message_bytes = connection.recv(buffer_size)

                    # იმ შემთხვევაში თუ კავშირი გაწყდა message_bytes იქნება ცარიელი
                    if not message_bytes:
                        # კავშირის დახურვა
                        connection_close(connection)

                        # ფუნქციიდან გამოსვლა
                        return

                    # მესიჯის მიღების დრო
                    message_receive_time = datetime.datetime.now()

                    # თუ მესიჯის წაკითხვა დაიწყო
                    if new_message is True:

                        # მესიჯის სიგრძის/ჰედერის წაკითხვა.
                        message_length = int(message_bytes[:HEADERSIZE])

                        # მესიჯის ჰედერის წაკითხვის დასასრული
                        new_message = False

                    # მესიჯის შეგროვება
                    header_and_message += message_bytes

                    # დავთვალოთ წაკითხული მესიჯის სიგრძე ჰედერის გარეშე
                    received_message_length = len(header_and_message) - HEADERSIZE
                    # print("received_message_length ======", received_message_length)
                    # შევამოწმოთ თუ წავიკითხეთ მთლიანი მესიჯი
                    if received_message_length == message_length:
                        try:
                            # მესიჯის აღდგენა, bytes-ს ტიპიდან dictionary ობიექტში გადაყვანა
                            message = pickle.loads(header_and_message[HEADERSIZE:])
                        except Exception as ex:
                            # logger -ის გამოძახება
                            logger.warning("მიღებული მესიჯის bytes-ს ტიპიდან dictionary ობიექტში გადაყვანისას დაფიქსირდა შეცდომა: \n{}".format(str(ex)))

                            # კავშირის დახურვა
                            connection_close(connection, addr)
                            # ფუნქციიდან გამოსვლა
                            return

                        # ციკლიდან გამოსვლა
                        break
                    elif received_message_length > message_length:
                        try:
                            # მესიჯის აღდგენა, bytes-ს ტიპიდან dictionary ობიექტში გადაყვანა
                            message = pickle.loads(header_and_message[HEADERSIZE:])
                        except Exception as ex:
                            # logger -ის გამოძახება
                            logger.warning("მოსული მესიჯის სიგრძემ გადააჭარბა ჰედერში მითითებულ მოსალოდნელ სიგრძეს")

                            # logger -ის გამოძახება
                            logger.warning("მიღებული მესიჯის bytes-ს ტიპიდან dictionary ობიექტში გადაყვანისას დაფიქსირდა შეცდომა: \n{}"
                                           .format(str(ex)))

                            # კავშირის დახურვა
                            connection_close(connection, addr)
                            # ფუნქციიდან გამოსვლა
                            return

                        # logger -ის გამოძახება
                        logger.warning("მოსული მესიჯის სიგრძემ გადააჭარბა ჰედერში მითითებულ მოსალოდნელ სიგრძეს. მესიჯი: \n{}".format(message))

                        # კავშირის დახურვა
                        connection_close(connection, addr)
                        # ფუნქციიდან გამოსვლა
                        return

            # შევამოწმოთ თუ message dictionary-ის არ აქვს who_am_i key-ი
            if "who_am_i" not in message:
                # თუ არ გვაქვს who_am_i key-ი ესეიგი მოსულია საეჭვო მესიჯი და ვხურავთ თრედს
                break

            # შევამოწმოთ თუ შეტყობინება მოსულია ies_monitor.py - სგან
            elif message["who_am_i"] == "ies_monitor":
                response_ies_monitor_messages(message, addr)
                break

            # შევამოწმოთ თუ შეტყობინება მოსულია ies_monitoring_client.py - სგან
            elif message["who_am_i"] == "ies_monitoring_client":
                response_ies_monitoring_client_messages(connection, addr, message)
                # გამოვიდეთ ციკლიდან რაც გულისხმობს client_handler_thread დასრულებას და შესაბამისი Thread-ის დახურვას
                break

    # წაკითხული მესიჯის მერე დავხუროთ კავშირი
    connection_close(connection, addr)


def command_listener():
    """ ფუნქცია კითხულობს მომხმარებლის ბრძანებებს """

    global application_is_closing

    while True:
        # დაველოდოთ მომხმარებლის ბრძანებას
        command = input("")

        # თუ მომხმარებლის მიერ შეყვანილი ბრძანება არის `exit` დავხუროთ პროგრამა და socket_object ობიექტი
        if command == "exit":
            application_is_closing = True
            connection_close(socket_object)
            logger.debug("პროგრამის ითიშება")
            # os._exit(0)  # !!!!!!!!!!!!!!!!!!!
            break


def connect_to_mysql(verbose=True):
    """ ფუნქცია უკავშირდება Mysql სერვერს"""

    try:
        mysql_connection = pymysql.connect(mysql_server_ip,
                                           mysql_server_user,
                                           mysql_user_pass,
                                           mysql_database_name,
                                           port=mysql_server_port)
        if verbose is True:
            logger.debug("მონაცემთა ბაზასთან კავშირი დამყარებულია")
    except Exception as ex:
        if verbose is True:
            logger.error("მონაცემთა ბაზასთან კავშირი წარუმატებელია\n" + str(ex))
        else:
            logger.error("Exception: ", str(ex))
        return False
    return mysql_connection


def main():
    """ მთავარი ფუნქცია რომელიც ეშვება პირველი პროგრამის ჩართვის დროს """

    # გავხსნათ პორტი და დაველოდოთ client-ის დაკავშირებას
    start_listening()

    # შევქმნათ thread-ი accept_connections ფუნქციის საშუალებით რომელიც ამყარებს კავშირს client-ებთან
    threading.Thread(target=accept_connections).start()

    # დავიწყოთ მომხმარებლის ბრძანებების მოსმენა
    threading.Thread(target=command_listener).start()


if __name__ == "__main__":
    main()
