#ifndef PARSING_H
#define PARSING_H
#include "vector.h"
#include <string>
#include "table.h"
using namespace std;
struct SQLQuery {
    enum Type { SELECT, INSERT, DELETE, UNKNOWN } type;

    Vector<string> selectColumns;
    Vector<string> fromTables;
    Vector<Condition*> whereConditions;

    string insertTable;
    Vector<string> insertValues;

    string deleteTable;
    Vector<Condition*> deleteConditions;
};

class SQLParser {
private:
    Vector<Condition*> allocatedConditions;
public:
    Condition* createCondition(const string& name, const string& value, const string& sign) {
        Condition* cond = new Condition(name, value, sign);
        allocatedConditions.push_back(cond);
        return cond;
    }

    Condition* createCondition(const string& sign, Condition* left, Condition* right) {
        Condition* cond = new Condition(sign, left, right);
        allocatedConditions.push_back(cond);
        return cond;
    }

    SQLQuery parse(const string& sql);
    static Vector<string> tokenize(const string& sql);
    SQLQuery parseSelect(const Vector<string>& tokens);
    static SQLQuery parseInsert(const Vector<string>& tokens);
    SQLQuery parseDelete(const Vector<string>& tokens);

    Vector<Condition*> parseWhere(const Vector<string>& tokens, int position);
    Condition* parsePrimary(const Vector<string>& tokens, int& position);
    Condition* parseOR(const Vector<string>& tokens, int& position);
    Condition* parseAND(const Vector<string>& tokens, int& position);
    ~SQLParser() {
        for (Condition* cond: allocatedConditions) {
            delete cond;
        }
        allocatedConditions.clear();
    }
};

#endif //PARSING_H
