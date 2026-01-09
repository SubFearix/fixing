#include "parsing.h"

#include <algorithm>

Vector<string> SQLParser::tokenize(const string& sql)
{
    Vector<string> tokens;
    string curToken;
    bool inQuotes = false;

    for (const char c: sql)
    {
        switch (c)
        {
            case '\"':
                {
                    inQuotes = !inQuotes;
                    curToken += c;
                    break;
                }
            case ' ':
                {
                    if (inQuotes == false)
                    {
                        if (!curToken.empty())
                        {
                            tokens.push_back(curToken);
                        }
                        curToken.clear();
                    }
                    break;
                }
            case ',':
            case ')':
            case '(':
                {
                    if (inQuotes == false)
                    {
                        if (!curToken.empty())
                        {
                            tokens.push_back(curToken);
                        }
                        tokens.push_back(string(1, c));
                        curToken.clear();
                    }
                    break;
                }
            default:
                {
                    curToken += c;
                    break;
                };
        }
    }
    if (!curToken.empty()) tokens.push_back(curToken);
    return tokens;
}

SQLQuery SQLParser::parse(const string& sql)
{
    Vector<string> tokens = tokenize(sql);
    SQLQuery query;
    if (tokens.empty())
    {
        query.type = SQLQuery::UNKNOWN;
        return query;
    }

    string firstToken = tokens[0];
    transform(firstToken.begin(), firstToken.end(), firstToken.begin(), ::toupper);
    if (firstToken == "SELECT")
        {
            return parseSelect(tokens);
        }
    if (firstToken == "INSERT")
        {
            return parseInsert(tokens);
        }
    if ( firstToken == "DELETE")
        {
            return parseDelete(tokens);
        }
    query.type = SQLQuery::UNKNOWN;
    return query;
}

SQLQuery SQLParser::parseInsert(const Vector<string>& tokens)
{
    SQLQuery query;
    query.type = SQLQuery::INSERT;
    bool findINTO = false;
    bool findVALUES = false;
    int i = 1;

    for (; i < tokens.size(); i++)
    {
        if (tokens[i] == "INTO")
        {
            findINTO = true;
            if (i + 1 >= tokens.size()) {
                throw runtime_error("Не указана таблица после INTO");
            }
            query.insertTable = tokens[i + 1];
            i++;
            break;
        }
    }
    if (!findINTO)
    {
        throw runtime_error("INSERT требует токен INTO");
    }

    for (; i < tokens.size(); i++)
    {
        if (tokens[i] == "VALUES")
        {
            findVALUES = true;
            if (i + 1 >= tokens.size() || tokens[i + 1] != "(") {
                throw runtime_error("Не хватает аргументов после VALUES");
            }
            int startPos = i + 2;
            for (int j = startPos; j < tokens.size(); j++) {
                if (tokens[j] == ")") {
                    break;
                }
                if (tokens[j] != ",") {
                    query.insertValues.push_back(tokens[j]);
                }
            }
            break;
        }
    }
    if (!findVALUES)
    {
        throw runtime_error("INSERT требует токен VALUES");
    }

    if (query.insertValues.empty()) {
        throw runtime_error("INSERT требует хотя бы одно значение");
    }

    return query;
}

Vector<Condition*> SQLParser::parseWhere(const Vector<string>& tokens, int position)
{
    Vector<Condition*> conditions;
    Condition* res = parseOR(tokens, position);
    if (res)
    {
        conditions.push_back(res);
    }
    return conditions;
}

SQLQuery SQLParser::parseDelete(const Vector<string>& tokens)
{
    SQLQuery query;
    query.type = SQLQuery::DELETE;
    bool findFROM = false;
    int i = 1;

    for (; i < tokens.size(); i++)
    {
        if (tokens[i] == "FROM")
        {
            findFROM = true;
            if (i + 1 >= tokens.size()) {
                throw runtime_error("Не указана таблица после FROM");
            }
            query.deleteTable = tokens[i + 1];
            i++;
            break;
        }
    }
    if (!findFROM)
    {
        throw runtime_error("DELETE требует токен FROM");
    }

    for (; i < tokens.size(); i++)
    {
        if (tokens[i] == "WHERE")
        {
            if (i + 1 >= tokens.size()) {
                throw runtime_error("Не хватает условия WHERE");
            }
            query.deleteConditions = parseWhere(tokens, i + 1);
            break;
        }
    }

    if (query.deleteTable.empty()) {
        throw runtime_error("DELETE требует название таблицы");
    }

    return query;
}


Condition* SQLParser::parsePrimary(const Vector<string>& tokens, int& position)
{
    if (position >= tokens.size())
    {
        throw runtime_error("Неожиданный конец условия WHERE");
    }
    if (tokens[position] == "(")
    {
        position++;
        Condition* res = parseOR(tokens, position);
        if (tokens[position] != ")")
        {
            delete res;
            throw runtime_error("Скобка не закрыта");
        }
        position++;
        return res;
    }

    if (position + 2 >= tokens.size())
    {
        throw runtime_error("Неполное условие в WHERE");
    }
    string nameToken = tokens[position];
    string operToken = tokens[position + 1];
    string valueToken = tokens[position + 2];
    if (operToken != "=")
    {
        throw runtime_error("Поддерживается только оператор =");
    }
    position += 3;
    return createCondition(nameToken, valueToken, operToken);
}

Condition* SQLParser::parseOR(const Vector<string>& tokens, int& position)
{
    Condition* left = parseAND(tokens, position);
    while (position < tokens.size() && tokens[position] == "OR")
    {
        position++;
        Condition* right = parseAND(tokens, position);
        left = createCondition("OR", left, right);
    }
    return left;
}

Condition* SQLParser::parseAND(const Vector<string>& tokens, int& position)
{
    Condition* left = parsePrimary(tokens, position);
    while (position < tokens.size() && tokens[position] == "AND")
    {
        position++;
        Condition* right = parsePrimary(tokens, position);
        left = createCondition("AND", left, right);
    }
    return left;
}

SQLQuery SQLParser::parseSelect(const Vector<string>& tokens)
{
    SQLQuery query;
    query.type = SQLQuery::SELECT;
    bool findWHERE = false;
    int i = 1;
    for (; i < tokens.size(); i++)
    {
        if (tokens[i] == "FROM")
        {
            break;
        }
        if (tokens[i] != ",")
        {
            query.selectColumns.push_back(tokens[i]);
        }
    }
    if (i >= tokens.size()) {
        throw runtime_error("SELECT требует FROM");
    }
    if (query.selectColumns.empty()) {
        throw runtime_error("SELECT требует колонки");
    }

    i++;
    for (; i < tokens.size(); i++)
    {
        if (tokens[i] == "WHERE")
        {
            findWHERE = true;
            break;
        }
        if (tokens[i] != ",")
        {
            query.fromTables.push_back(tokens[i]);
        }
    }

    if (query.fromTables.empty()) {
        throw runtime_error("SELECT требует таблицы");
    }
    if (findWHERE)
    {
        i++;
        if (i >= tokens.size()) {
            throw runtime_error("Не хватает условия WHERE");
        }
        query.whereConditions = parseWhere(tokens, i);
    }
    return query;
}