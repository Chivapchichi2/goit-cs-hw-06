import mimetypes
import socket
import logging
from pathlib import Path
from urllib.parse import unquote_plus
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process
from pymongo import MongoClient
from datetime import datetime

URI_DB = "mongodb://mongodb:27017"
BASE_DIR = Path(__file__).parent
CHUNK_SIZE = 1024
HTTP_PORT = 3000
SOCKET_PORT = 5000
HTTP_HOST = "0.0.0.0"
SOCKET_HOST = "0.0.0.0"
DATA_FILE = BASE_DIR.joinpath("storage", "data.json")


class TheBestFramework(BaseHTTPRequestHandler):
    def do_GET(self):
        router = self.path
        if router == "/":
            self.send_html("index.html")
        elif router == "/message":
            self.send_html("message.html")
        else:
            file = BASE_DIR.joinpath(router[1:])
            if file.exists():
                self.send_static(file)
            else:
                self.send_html("error.html", 404)

    def do_POST(self):
        size = int(self.headers["Content-Length"])
        data = self.rfile.read(size)

        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((SOCKET_HOST, SOCKET_PORT))
            client_socket.sendall(data)
            client_socket.close()
        except socket.error:
            logging.error("Failed to send data")

        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()
        save_to_db(data.decode())

    def send_html(self, filename, status=200):
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        with open(filename, "rb") as f:
            self.wfile.write(f.read())

    def send_static(self, filename, status=200):
        self.send_response(status)
        mimetype = mimetypes.guess_type(filename)[0] or "text/plain"
        self.send_header("Content-type", mimetype)
        self.end_headers()
        with open(filename, "rb") as f:
            self.wfile.write(f.read())


def run_http_server():
    httpd = HTTPServer((HTTP_HOST, HTTP_PORT), TheBestFramework)  # noqa
    try:
        logging.info(f"HTTP Server started: http://{HTTP_HOST}:{HTTP_PORT}")
        httpd.serve_forever()
    except Exception as e:
        logging.error(e)
    finally:
        logging.info("HTTP Server stopped")
        httpd.server_close()


def save_to_db(data):
    client = MongoClient(URI_DB)
    db = client['homework']
    collection = db['messages']
    try:
        data = unquote_plus(data)
        parse_data = dict([i.split("=") for i in data.split("&")])
        parse_data['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        print(parse_data)
        collection.insert_one(parse_data)
    except Exception as e:
        logging.error(e)
    finally:
        client.close()


def run_socket_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((SOCKET_HOST, SOCKET_PORT))
    s.listen(1)
    logging.info(f"Socket Server started: socket://{SOCKET_HOST}:{SOCKET_PORT}")
    try:
        while True:
            conn, addr = s.accept()
            logging.info(f"Connected by {addr}")
            data = conn.recv(CHUNK_SIZE)
            if data:
                logging.info(f"Received from {addr}: {data.decode()}")
                save_to_db(data.decode())
    except Exception as e:
        logging.error(e)
    finally:
        logging.info("Socket Server stopped")
        s.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(processName)s - %(message)s")
    http_server_process = Process(target=run_http_server, name="HTTP_Server")
    socket_server_process = Process(target=run_socket_server, name="SOCKET_Server")
    http_server_process.start()
    socket_server_process.start()
    http_server_process.join()
    socket_server_process.join()
