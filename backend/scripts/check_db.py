import socket
import sys

s = socket.socket()
s.settimeout(2)
result = s.connect_ex(("localhost", 5432))
s.close()
sys.exit(result)
