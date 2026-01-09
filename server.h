#ifndef SERVER_H
#define SERVER_H
#include <cstdio>
#include <exception>
#include <iostream>
#include <thread>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include "database/database.h"

int createServer();
void handleClient(int clientSocket, Database& db);
void multiThreadServer(int serverSocket, Database& db);
#endif //SERVER_H
