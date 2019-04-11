#!/usr/bin/env python
# -*- coding: utf-8 -*-

import socket
import sys
import time

# print sys.argv
if len(sys.argv) == 2:
	UDP_IP = sys.argv[1]
else:
	UDP_IP = '255.255.255.255' #"192.168.1.182"
	# UDP_IP = '192.168.1.236' #"192.168.1.182"
UDP_PORT = 62070 #60411

print("UDP target IP:", UDP_IP)
print("UDP target port:", UDP_PORT)

sock = socket.socket(socket.AF_INET, # Internets
                     socket.SOCK_DGRAM)#,
                     # socket.IPPROTO_UDP) # UDP
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

for i in range(100):
    # sock.sendto("4", (UDP_IP, UDP_PORT))
    msg = input("Command: ")
    sock.sendto(msg.encode(), (UDP_IP, UDP_PORT))
    # print i, time.time()
    # time.sleep(0.1)