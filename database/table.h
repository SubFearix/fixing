#ifndef TABLE_H
#define TABLE_H
#include "vector.h"
#include <iostream>
#include <filesystem>
#include <mutex>
#include <shared_mutex>
using namespace std;
using namespace filesystem;

class Condition
{
private:
    string name;
    string value;
    string sign;
    Condition* left;
    Condition* right;
public:
    Condition(string  col, string  val, string  op = "=")
        : name(move(col)), value(move(val)), sign(move(op)), left(nullptr), right(nullptr) {}

    Condition(string  op, Condition* l, Condition* r)
        : sign(move(op)), left(l), right(r) {}

    [[nodiscard]] string getName() const {return name;}
    [[nodiscard]] string getValue() const {return value;}
    [[nodiscard]] string getSign() const {return sign;}
    [[nodiscard]] Condition* getLeft() const {return left;}
    [[nodiscard]] Condition* getRight() const {return right;}
    ~Condition() = default;
};


class Table
{
private:
    string tableName;
    Vector<string> columns;
    string path;
    int tuplesLimit;
    int PK = 1;
    bool isLocked = false;
    mutable shared_mutex mutex;
    Vector<Vector<string>> selectAll();
public:
    Table(const string& name, const Vector<string>& cols, const string& directory, const int limit)
    : tableName(name), columns(cols), path(directory + "/" + name)
    , tuplesLimit(limit)
    {
        create_directories(path);
        string firstFile = path + "/1.csv";
        if (!exists(firstFile)) {
            createNewFile();
            writePK();
            cout << "Table '" << name << "' created in " << path << endl;
        } else {
            readPK();
            cout << "Table '" << name << "' loaded from " << path << endl;
        }
    }
    void insertData(const Vector<string>& values);
    Vector<Vector<string>> findData(const Vector<string>& headers, const Vector<Condition*>& conditions);
    void deleteData(const Vector<Condition*>& conditions);

    string createNewFile();
    void writeDataToFile(const string& filename, const Vector<string>& values);
    void readPK();
    void writePK();
    void resetPK(){PK = 1; writePK();}

    void lockTable();
    void unlockTable();
    bool isTableBlocked();

    bool checkWhere(const Vector<Condition*>& conditions, const Vector<string>& row);
    bool checkCondition(const Condition& condition, const Vector<string>& row);
    [[nodiscard]] Vector<int> getColumnIndexes(const Vector<string>& headers) const;
    [[nodiscard]] Vector<string> getAllColumns(const string& tableName) const;
    static Vector<string> splitLine(const string& line);
    Vector<Vector<string>> selectAllSafe()
    {
        shared_lock<shared_mutex> lock(mutex);
        return selectAll();
    }

    Vector<string> getColumns(){return columns;};
    string getPath(){return path;};
};

#endif //TABLE_H
