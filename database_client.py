import socket
class DatabaseClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def execute_query(self, sql):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            s.connect((self.host, self.port))
        except:
            raise ConnectionError(f"Не удалось подключиться к БД на {self.host}:{self.port}")

        _ = s.recv(4096).decode('utf-8')
        s.sendall(sql.encode("utf-8"))

        buffer = ""
        while True:
            pack = s.recv(4096)
            if not pack:
                break
            buffer += pack.decode('utf-8')

            if "Всего строк:" in buffer or "SUCCESS:" in buffer or "ERROR:" in buffer:
                break

        s.sendall(b"EXIT")
        s.close()
        return self._parse_response(buffer)

    def _parse_response(self, response_text):
        response_text = response_text.strip()

        if response_text.startswith("ERROR"):
            raise Exception(response_text)

        if response_text.startswith("SUCCESS"):
            return True

        strings = response_text.split('\n')

        if len(strings) < 2:
            return []

        headers = [h.strip() for h in strings[0].split(" | ")]

        result = []
        for i in range(1, len(strings) - 1):
            line = strings[i].strip()

            if not line or line.startswith("Всего строк:"):
                continue

            cols = [c.strip() for c in line.split(" | ")]

            row_dict = {}
            for j in range(len(headers)):
                if j < len(cols):
                    row_dict[headers[j]] = cols[j]

            result.append(row_dict)
        return result

    def execute_select(self, sql):
        print(sql)
        result = self.execute_query(sql)
        print(f"Result: {result}")
        if result == True:
            return []
        if result is None:
            return []
        return result

    def execute_insert(self, sql):
        result = self.execute_query(sql)
        return result is True

    def execute_delete(self, sql):
        result = self.execute_query(sql)
        return result is True





