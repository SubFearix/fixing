#include "server.h"

#include <cstring>
using namespace std;

string clearing(const string& str) {
    stringstream ss(str);
    string result;
    if (ss >> result) {
        string temp;
        while (ss >> temp) {
            result += " " + temp;
        }
    }
    return result;
}

int createServer(){
    const int serverSocket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (serverSocket == -1)
    {
        perror("socket failed");
        exit(EXIT_FAILURE);
    }
    const int options = 1;
    setsockopt(serverSocket, SOL_SOCKET, SO_REUSEADDR, &options, sizeof(options));

    sockaddr_in serverAddress;
    serverAddress.sin_family = AF_INET;
    serverAddress.sin_addr.s_addr = INADDR_ANY;
    serverAddress.sin_port = htons(7432);
    if (bind(serverSocket, reinterpret_cast<sockaddr*>(&serverAddress), sizeof(serverAddress)) == -1)
    {
        perror("bind failed");
        exit(EXIT_FAILURE);
    }

    if (listen(serverSocket, 10) == -1)
    {
        perror("listen failed");
        exit(EXIT_FAILURE);
    }
    cout << "Server listening on port 7432" << endl;
    return serverSocket;
}

void handleClient(const int clientSocket, Database& db)
{
    char buffer[8192];

    const string welcome = "Connected to database server. Type 'EXIT' to disconnect.\n";
    send(clientSocket, welcome.c_str(), welcome.length(), 0);
    while (true)
    {
        memset(buffer, 0, sizeof(buffer));
        const size_t bytesReceived = recv(clientSocket, buffer, sizeof(buffer), 0);
        if (bytesReceived == -1)
        {
            perror("recv failed");
            exit(EXIT_FAILURE);
            break;
        }

        buffer[bytesReceived] = '\0';
        const string query = clearing(buffer);

        if (query == "EXIT" || query == "exit" || query == "QUIT" || query == "quit")
        {
            const string exit = "Goodbye!\n";
            send(clientSocket, exit.c_str(), exit.length(), 0);
            cout << "Client requested disconnect" << endl;
            break;
        }

        if (query.empty())
        {
        }
        cout << "Received query: " << query << endl;

        try
        {
            const string result = db.executeSQL(query);
            send(clientSocket, result.c_str(), result.length(), 0);
        } catch (const exception& e)
        {
            const string error = "ERROR: " + string(e.what()) + "\n";
            send(clientSocket, error.c_str(), error.length(), 0);
        }
    }
    close(clientSocket);
}

void multiThreadServer(const int serverSocket, Database& db)
{
    while (true)
    {
        int clientSocket = accept(serverSocket, nullptr, nullptr);
        if (clientSocket == -1)
        {
            perror("accept failed");
        }
        cout << "New client connected" << endl;

        thread([clientSocket, &db]()
        {
            handleClient(clientSocket, db);
        }).detach();
    }
}
