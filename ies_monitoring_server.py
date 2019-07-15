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
import select


# სერვერის ip მისამართი
server_ip = "10.0.0.113"

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


# -------------------------------------------------------------------------------------------------


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


def dictionary_to_bytes(dictionary_message):
    """
        dictionary ტიპის ობიექტი გადაყავს bytes ტიპში
        რადგან socket ობიექტის გამოყენებით მონაცემები იგზავნება bytes ტიპში
        მოსახერხებელია რომ გვქონდეს ფუნქციები რომელიც dictionary-ის გადაიყვანს
        bytes ტიპში და პირიქით
    """
    return bytes(json.dumps(dictionary_message), 'utf-8')

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


def send_message_to_ies_monitor(ies_monitor_ip, ies_monitor_port, message, write_to_log=True):
    """
        ფუნქციიის საშუალებით შეიძლება შეტყობინების გაგზავნა ies_monitor-თან.
        write_to_log პარამეტრი გამოიყენება იმ შემთხვევაში როდესაც მესიჯის იგზავნება ძალიან ხშირად
        და არ გვინდა ლოგ ფაილში ჩაიწეროს ბევრჯერ
    """

    # სოკეტის შექმნა
    ies_monitor_connection = connect_ies_monitor(ies_monitor_ip, ies_monitor_port)

    # ies_monitor-თან დაკავშირება
    if ies_monitor_connection is False:
        logger.warning("შეტყობინება ვერ გაიგზავნა, ies_monitor-თან კავშირი ვერ დამყარდა ({},{})\n{}"
                       .format(ies_monitor_ip, ies_monitor_port, message))
        return

    try:
        # შეტყობინების გაგზავნა
        ies_monitor_connection.send(dictionary_to_bytes(message))
        if write_to_log:
            logger.info("შეტყობინება გაიგზავნა ies_monitor-თან({},{})\n{}"
                        .format(ies_monitor_ip, ies_monitor_port, message))
    except Exception as ex:
        logger.warning("შეტყობინება ვერ გაიგზავნა ies_monitor-თან({},{})\n{}\n{}"
                       .format(ies_monitor_ip, ies_monitor_port, message, str(ex)))

    # სოკეტის დახურვა
    connection_close(ies_monitor_connection, ies_monitor_connection.getsockname())


def notify_ies_monitors_to_update_database():
    """ ies_monitor.py-ებს ეგზავნება მესიჯი ახალი შეტყობინების ბაზაში დამატების შესახებ """

    for ies_monitor_ip, ies_monitor_port in ies_monitor_ips_and_port.items():

        # შეტყობინების შექმნა ბაზის განახლების შესახებ
        message = {
            "who_am_i": "ies_monitoring_server",
            "message_category": "database_updated"
        }
        # ies_monitor-თან იგზავბება შეტყოვინება ბაზის განახლების შესახებ
        send_message_to_ies_monitor(ies_monitor_ip, ies_monitor_port, message)


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
            logger.debug("ies_monitor.py - " + str(addr) + " - დან მოვიდა რეგისტრაციის შეტყობინება, \
                          მაგრამ მოთხოვნილი ip უკვე რეგისტრირებულია: \n" + str(message))
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


def response_ies_monitoring_client_messages(connection, addr, message):
    """
        ფუნქცია უზრუნველყოფს ies_monitoring_client-იდან გამოგზავნილი შეტყობინებების წაკითხვას.
        წაკითხული შეტყობინება იწერება mysql ბაზაში და ბაზის განახლების შესახებ ვატყობინებთ ies_monitor-ებს.
        ies_monitoring_client-ს ვუგზავნით დასტურს შეტყობინების მიღების შესახებ.
    """

    logger.debug("ies_monitoring_client.py - " + str(addr) + " - დან მიღებული შეტყობინება: " + str(message))
    # მესიჯის ჩაწერა მონაცემთა ბაზაში
    if insert_message_into_mysql(message):
        notify_ies_monitors_to_update_database()

    # client-ს გავუგზავნოთ მესიჯის id იმის პასუხად რომ შეტყობინება მივიღეთ
    try:
        connection.send(bytes(message["message_id"], "utf-8"))
        logger.debug("ies_monitoring_client.py - " + str(addr) + " - თვის პასუხის დაბრუნება: " + message["message_id"])
    except Exception as ex:
        logger.error("ies_monitoring_client.py - " + str(addr) + " - ს ვერ ვუგზავნით შეტყობინებას უკან: " + message["message_id"] + "\n" + str(ex))


def client_handler_thread(connection, addr):
    """ client-თან კავშირის დამყარების შემდეგ ფუნქცია კითხულობს მის შეტყობინებას """

    while True:
        # შევამოწმოთ დავხუროთ თუ არა თრედი
        if application_is_closing:
            # ციკლიდან გამოსვლა. ამ შემთხვევაში თრედის დახურვა
            break

        # ციკლის შეჩერება 0.5 წამით
        time.sleep(0.5)  # ??? 0.5 დრო აროს დასაზუსტებელი

        # select.select ფუნქცია აბრუნებს readers list-ში ისეთ socket-ებს რომელშიც მოსულია წასაკითხი ინფორმაცია
        # ბოლო პარამეტრად მითითებული გვაქვს 0 რადგან ფუნქცია არ დაელოდოს ისეთ სოკეტს რომელზეც შეიძლება წაკითხვა
        readers, _, _, = select.select([connection], [], [], 0)

        # შევამოწმოთ readers list-ი თუ არ არის ცარიელი, რაც ამ შემთხვევაში ნიშნავს იმას რომ connection
        # socket-ზე მოსულია წასაკითხი ინფორმაცია
        if readers:
            # წავიკითხოთ client-სგან გამოგზავნილი შეტყობინება
            json_message = connection.recv(buffer_size)

            # იმ შემთხვევაში თუ კავშირი გაწყდა json_message იქნბა ცარიელი
            if not json_message.decode("utf-8"):
                # ციკლიდან გამოსვლა. ამ შემთხვევაში თრედის დახურვა
                break
            else:
                # წაკითხული შეტყობინება bytes ობიექტიდან გადავიყვანოთ dictionary ობიექტში
                message = bytes_to_dictionary(json_message)

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
    # წაკითხული შეტყობინების მერე დავხუროთ კავშირი
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

    # გავხსნათ პორტი და დაველოდოთ client-ის დაკავშირებას
    start_listening()

    # შევქმნათ thread-ი accept_connections ფუნქციის საშუალებით რომელიც ამყარებს კავშირს client-ებთან
    threading.Thread(target=accept_connections).start()

    # დავიწყოთ მომხმარებლის ბრძანებების მოსმენა
    threading.Thread(target=command_listener).start()


if __name__ == "__main__":
    main()
