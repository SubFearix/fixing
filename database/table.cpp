#include <filesystem>
#include <fstream>
#include "table.h"
using namespace filesystem;
using namespace std;

void Table::insertData(const Vector<string>& values)
{
    lockTable();
    unique_lock<shared_mutex> lock(mutex);

    string cc = "1";
    string lastExistingFile = "";
    while (exists(path + "/" + cc + ".csv") == true)
    {
        lastExistingFile = path + "/" + cc + ".csv";
        cc = to_string(stoi(cc) + 1);
    }
    string currentFile = lastExistingFile;
    if (currentFile.empty()) {
        currentFile = createNewFile();
    }
    ifstream file(currentFile);
    int lineCount = 0;
    string line;
    while (getline(file, line)) {
        lineCount++;
    }
    lineCount = lineCount - 1;
    file.close();

    if (lineCount >= tuplesLimit)
    {
        currentFile = createNewFile();
    }
    writeDataToFile(currentFile, values);
    PK++;
    writePK();
    unlockTable();
}

Vector<string> Table::splitLine(const string& line)
{
    Vector<string> splitted;
    stringstream ss(line);
    string token;
    while (getline(ss, token, ',')) {
        splitted.push_back(token);
    }
    return splitted;
}

Vector<Vector<string>> Table::selectAll()
{
    Vector<Vector<string>> allData;
    Vector<string> headers = getAllColumns(tableName);
    allData.push_back(headers);
    Vector<string> files;
    string cc = "1";
    while (exists(path + "/" + cc + ".csv"))
    {
        files.push_back(path + "/" + cc + ".csv");
        cc = to_string(stoi(cc) + 1);
    }

    for (const string& file: files)
    {
        ifstream oneFile(file);
        string line;

        if (getline(oneFile, line))
        {

        }

        while (getline(oneFile, line)) {
            Vector<string> row = splitLine(line);
            allData.push_back(row);
        }
        oneFile.close();
    }
    return allData;
}

void Table::deleteData(const Vector<Condition*>& conditions)
{
    unique_lock<shared_mutex> lock(mutex);
    lockTable();
    Vector<string> files;
    string cc = "1";
    while (exists(path + "/" + cc + ".csv") == true)
    {
        files.push_back(path + "/" + cc + ".csv");
        cc = to_string(stoi(cc) + 1);
    }
    int totalRowsRemaining = 0;
    int fileIndex = 0;
    for (const string& file: files)
    {
        fileIndex++;
        Vector<Vector<string>> allRows;
        ifstream oneFile(file);
        string line;

        if (getline(oneFile, line)) {
            Vector<string> header = splitLine(line);
            allRows.push_back(header);
        }

        while (getline(oneFile, line)) {
            Vector<string> row = splitLine(line);
            allRows.push_back(row);
        }
        oneFile.close();

        Vector<Vector<string>> remainingRows;
        remainingRows.push_back(allRows[0]);
        for (int i = 1; i < allRows.size(); i++) {
            if (!checkWhere(conditions, allRows[i])) {
                remainingRows.push_back(allRows[i]);
            }
        }
        totalRowsRemaining += (remainingRows.size() - 1);
        if (remainingRows.size() > 1)
        {
            ofstream rewriteFile(file);
            for (const Vector<string>& row: remainingRows) {
                string writeLine;
                for (const string& cell: row) {
                    writeLine += cell + ",";
                }
                writeLine.pop_back();
                rewriteFile << writeLine << endl;
            }
            rewriteFile.close();
        } else
        {
            if (fileIndex > 1)
            {
                remove(file.c_str());
            }
            else
            {
                ofstream rewriteFile(file, ios::trunc);
                string writeLine;
                for (const string& cell: remainingRows[0]) {
                    writeLine += cell + ",";
                }
                writeLine.pop_back();
                rewriteFile << writeLine << endl;
                rewriteFile.close();
            }
        }
    }
    if (totalRowsRemaining == 0) {
        resetPK();
    }
    unlockTable();
}

bool Table::checkWhere(const Vector<Condition*>& conditions, const Vector<string>& row)
{
    if (conditions.empty()) return true;
    for (const Condition* cond: conditions)
    {
        if (checkCondition(*cond, row)) return true;
    }
    return false;
}

bool Table::checkCondition(const Condition& condition, const Vector<string>& row)
{
    if (condition.getSign() == "=")
    {
        int index = -1;
        if (condition.getName() == tableName + "_pk") index = 0;
        else
        {
            for (int i = 0; i < columns.size(); i++) {
                if (condition.getName() == tableName + "." + columns[i]) {
                    index = i + 1;
                    break;
                }
            }
        }
        if (index != -1 && index < row.size() && row[index] == condition.getValue())
        {
            return true;
        }
    }

    else if (condition.getSign() == "AND")
    {
        if (!condition.getLeft() || !condition.getRight()) {
            return false;
        }
        return checkCondition(*condition.getLeft(), row) &&
               checkCondition(*condition.getRight(), row);
    }
    else if (condition.getSign() == "OR")
    {
        if (!condition.getLeft() && !condition.getRight()) {
            return false;
        }
        return checkCondition(*condition.getLeft(), row) ||
               checkCondition(*condition.getRight(), row);
    }
    return false;
}

Vector<int> Table::getColumnIndexes(const Vector<string>& headers) const
{
    Vector<int> indexes;
    for (const string& column: headers) {
        int index = -1;

        if (column == tableName + "_pk") {
            index = 0;
        } else {
            for (int i = 0; i < columns.size(); i++) {
                if (column == tableName + "." + columns[i]) {
                    index = i + 1;
                    break;
                }
            }
        }

        if (index != -1) {
            indexes.push_back(index);
        }
    }
    return indexes;
}

Vector<Vector<string>> Table::findData(const Vector<string>& headers, const Vector<Condition*>& conditions)
{
    shared_lock<shared_mutex> lock(mutex);
    const Vector<Vector<string>> allData = selectAll();
    Vector<Vector<string>> result;
    result.push_back(headers);
    const Vector<int> indexes = getColumnIndexes(headers);

    for (size_t i = 1; i < allData.size(); i++) {
        const Vector<string>& row = allData[i];
        if (checkWhere(conditions, row)) {
            Vector<string> selectedRow;
            for (const int index: indexes) {
                if (index < row.size()) {
                    selectedRow.push_back(row[index]);
                }
            }
            result.push_back(selectedRow);
        }
    }
    return result;
}

Vector<string> Table::getAllColumns(const string& tableName) const
{
    Vector<string> names;
    names.push_back(tableName + "_pk");
    for (const string& col: columns) {
        names.push_back(tableName + "." + col);
    }
    return names;
}
