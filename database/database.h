#ifndef DATABASE_H
#define DATABASE_H

#include "parsing.h"
#include "structures.h"
#include "vector.h"

class Database {
private:
    string name;
    string directory;
    int tuplesLimit;
    Hash tables;
    SQLParser parser;
    static bool checkWhereJoined(const Vector<Condition*>& conditions, const Vector<string>& headers, const Vector<string>& row);
    static bool checkConditionJoined(const Condition& condition, const Vector<string>& headers, const Vector<string>& row);
    void executeJoinRecursive(
        const SQLQuery& query,
        size_t tableIndex,
        const Vector<string>& currentHeaders,
        const Vector<string>& currentRow,
        Vector<Vector<string>>& result);

public:
    Database()
    {
        loadSchema();
    };

    void loadSchema();
    Table* getTable(const string& tableName) const;
    string executeInsert(const SQLQuery& query);
    string executeDelete(const SQLQuery& query);
    string executeSelect(const SQLQuery& query);
    string executeSQL(const string& sql);
    static string printResult(const Vector<Vector<string>>& result);
    Vector<Vector<string>> executeJoin(const SQLQuery& query);

    ~Database() = default;
};
#endif //DATABASE_H
