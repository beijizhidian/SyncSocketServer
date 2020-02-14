import io
import json
import socket
from threading import Thread

import struct
import sys

ADDRESS = ('', 8080)

g_socket_server = None
g_conn_pool = []
g_addr_pool = []

def init():
    global g_socket_server
    g_socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    g_socket_server.bind(ADDRESS)
    g_socket_server.listen(5)
    print("服务器已启动，等待连接。。。")

def accept_client():
    while True:
        client, addr = g_socket_server.accept()
        g_conn_pool.append(client)
        g_addr_pool.append(addr)
        thread = Thread(target=message_handle, args=(client,))
        thread.setDaemon(True)
        thread.start()
        print("接收到一个新客户端：{}".format(addr))

def message_handle(client):
    client.sendall("连接服务器成功！".encode('utf-8'))
    message = Message(client, g_conn_pool, g_addr_pool)
    message.run()



class Message():
    def __init__(self, client, conn_pool, addr_pool):
        self.client = client
        self.conn_pool = conn_pool
        self.addr_pool = addr_pool
        self.recv_buffer = None
        self.send_buffer = None
        self.jsonheader_len = None
        self.jsonheader = None
        self.send_jsonheader = None
        self.send_jsonheader_len = None
        self.content_len = None
        self.content = None

    def json_encode(self, data, encoding):
        return json.dumps(data, ensure_ascii=False).encode(encoding)

    def json_decode(self, data, encoding):
        tiow = io.TextIOWrapper(
            io.BytesIO(data), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj

    def recv_first(self):
        if self.recv_buffer is None:
            self.recv_buffer = self.client.recv(1024)
        else:
            self.recv_buffer += self.client.recv(1024)

    def get_jsonheader_len(self):
        hdrlen = 2
        self.jsonheader_len = struct.unpack(
            ">H", self.recv_buffer[:hdrlen]
        )[0]
        self.recv_buffer = self.recv_buffer[hdrlen:]

    def get_jsonheader(self):
        self.jsonheader = self.json_decode(self.recv_buffer[:self.jsonheader_len], "utf-8")
        print("***jsonheader:{}***".format(self.jsonheader))
        self.recv_buffer = self.recv_buffer[self.jsonheader_len:]
        for header in (
            "byteorder",
            "content-type",
            "content-length",
            "content-encoding",
        ):
            if header not in self.jsonheader:
                print("***头文件缺失：{}缺失***".format(header))

    def create_response_message(self, content_byte):
        self.send_jsonheader = {
            "byteorder": sys.byteorder,
            "content-type":self.jsonheader["content-type"],
            "content-encoding":self.jsonheader["content-encoding"],
            "content-length":len(content_byte)
        }
        send_jsonheader_byte = self.json_encode(self.send_jsonheader, self.jsonheader["content-encoding"])
        self.send_jsonheader_len = struct.pack(">H", len(send_jsonheader_byte))
        send_message = self.send_jsonheader_len + send_jsonheader_byte + content_byte
        return send_message

    def recv_message(self):
        self.content_len = self.jsonheader["content-length"]
        current_content_len = len(self.recv_buffer)
        if current_content_len<self.content_len:
            print("***数据较大正在接收***")
            while True:
                data = self.client.recv(1024)
                current_content_len += len(data)
                self.recv_buffer += data
                print("数据接收中（{}/{}".format(current_content_len, self.content_len))
                if current_content_len == self.content_len:
                    print("***数据接收完成***")
                    self.content = self.recv_buffer
                    break
        else:
            self.content = self.recv_buffer

    def process_message(self):
        print("***处理消息***")
        print("消息内容：{}".format(self.content))
        content = self.json_decode(self.content, self.jsonheader["content-encoding"])
        print("消息是：{}".format(content))
        if self.jsonheader["content-type"] == "cmd":
            action = content.get("action")
            value = content.get("value")
            print("acton is {}, value is {}".format(action,value))

            if action == "search":
                content_byte = self.json_encode(self.addr_pool,self.jsonheader["content-encoding"])
                send_message = self.create_response_message(content_byte)
                print("***发送消息{}***".format(send_message))
                self.client.sendall(send_message)

        elif self.jsonheader["content-type"] == "sendString":
            addr = content.get("addr")
            value = content.get("value")
            print("addr_num = {}, value = {}".format(addr, value))
            print("addr = {}".format(self.addr_pool[int(addr)]))
            content_byte = self.json_encode(value, self.jsonheader["content-encoding"])
            send_message = self.create_response_message(content_byte)
            self.targetclient = self.conn_pool[addr]
            print("***发送消息：{}".format(send_message))
            self.targetclient.sendall(send_message)

        else:
            print("***content:{}***".format(content))




    def run(self):
        while True:
            self.recv_buffer = self.client.recv(1024)
            self.get_jsonheader_len()
            self.get_jsonheader()

            self.recv_message()
            self.process_message()

if __name__ == '__main__':
    init()
    thread = Thread(target=accept_client())
    thread.setDaemon(True)
    thread.start()
    while True:
        cmd = input("输入指令：")
        if cmd == "1":
            print("总连接数：{}".format(len(g_addr_pool)))

