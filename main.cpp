#include "database/database.h"
#include "server.h"

int main()
{
    Database db;
    const int serverSocket = createServer();
    multiThreadServer(serverSocket, db);
    close(serverSocket);
    return 0;
}
