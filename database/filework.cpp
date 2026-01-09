#include <fstream>
#include <filesystem>
#include <iostream>
#include "table.h"
using namespace std;
using namespace filesystem;

string Table::createNewFile()
{
    string cc = "1";
    while (exists(path + "/" + cc + ".csv") == true)
    {
        cc = to_string(stoi(cc) + 1);
    }
    string filename = path + "/" + cc + ".csv";
    ofstream file(filename);
    try
    {
        if (!file.is_open()) {
            throw runtime_error("Не удалось создать файл!");
        }
        cout << "Файл " << cc << ".csv создан успешно!\n";
        file << tableName << "_pk";
        for (string column : columns)
        {
            file << "," << tableName << "." << column;
        }
        file << endl;
        file.close();
    } catch (const exception& e) {
        cout << "Ошибка создания файла: " << e.what() << "\n";
        if (file.is_open()) {
            file.close();
        }
    }
    return filename;
}

void Table::writePK()
{
    ofstream filePK(path + "/" + tableName + "_pk_sequence");
    if (filePK.is_open())
    {
        filePK << PK;
        filePK.close();
    }
}

void Table::readPK()
{
    if (exists(path + "/" + tableName + "_pk_sequence") == true)
    {
        ifstream filePK(path + "/" + tableName + "_pk_sequence");
        if (filePK.is_open())
        {
            filePK >> PK;
            filePK.close();
        }
    } else
    {
        PK = 1;
        writePK();
    }
}


void Table::writeDataToFile(const string& filename, const Vector<string>& values)
{
    ofstream file(filename, ios::app);
    if (file.is_open()) {
        file << PK;
        for (const string& value: values) {
            file << "," << value;
        }
        file << endl;
        file.close();
    }
}

bool Table::isTableBlocked() {
    string lockFile = path + "/" + tableName + "_lock";
    return exists(lockFile);
}

void Table::lockTable()
{
    const string lockFile = path + "/" + tableName + "_lock";

    if (isTableBlocked()) {
        throw runtime_error("Таблица '" + tableName + "' уже заблокирована!");
    }

    ofstream file(lockFile);
    if (file.is_open()) {
        file << "Table is locked!!!";
        file.close();
        isLocked = true;
        cout << "Таблица '" + tableName + "' заблокирована" << endl;
    } else {
        throw runtime_error("Не удалось заблокировать таблицу '" + tableName + "'");
    }
}

void Table::unlockTable()
{
    const string lockFile = path + "/" + tableName + "_lock";

    if (!isTableBlocked()) {
        throw runtime_error("Таблица '" + tableName + "' уже разблокирована!");
    }
    if (remove(lockFile))
    {
        isLocked = false;
        cout << "Таблица '" + tableName + "' разблокирована" << endl;
    } else
    {
        throw runtime_error("Не удалось разблокировать таблицу '" + tableName + "'");
    }
}