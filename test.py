#!/usr/bin/python3
# -*- coding: utf-8 -*-




# ies_monitor აპლიკაციის ip
ies_monitor_ip_dict = {}
ies_monitor_ip_dict.update({"ies_monitor": ("10.0.0.220", 2341)})
ies_monitor_ip_dict.update({"ies_monitor2": ("10.0.0.221", 2342)})
ies_monitor_ip_dict.update({"ies_monitor3": ("10.0.0.222", 2343)})
ies_monitor_ip_dict.update({"ies_monitor4": ("10.0.0.223", 2344)})

# print(ies_monitor_ip_dict)
    # logger.debug("ies_monitor - " + str(addr) + " - დან მიღებული შეტყობინება: " + str(message))



for key in ies_monitor_ip_dict:
    if "ies_monitor" in ies_monitor_ip_dict:
        print("++++++")
    print("key = ", key)
    ies_monitor_ip = ies_monitor_ip_dict.get(key)[0]
    ies_monitor_port = ies_monitor_ip_dict.get(key)
    print(ies_monitor_ip)
    print(ies_monitor_port[1])

    # ies_monitor_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # ies_monitor_connection.connect((ies_monitor_ip, ies_monitor_port))
    # ies_monitor_connection.send(bytes("test2", "utf-8"))
    # print("შეტყობინება გაეგზავნა ies_monitor -ს")