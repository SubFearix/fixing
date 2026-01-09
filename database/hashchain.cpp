#include <string>
#include "structures.h"

using namespace std;

int Hash::hashFunc(const string& key, const int capacity){
    int hash = 0;
    for (const char c: key) {
        hash = (hash * 37 + c) % capacity;
    }
    return hash % capacity;
}

void Hash::addElement(const string& key, Table* data){
	const int index = hashFunc(key, this->capacity);
	NodeHash* begin = this->cell[index]; // Начало цепочки
	NodeHash* current = begin;
	while (current != nullptr){
		if (current->key == key){
			current->data = data;
			return;
		}
		current = current->next;
	}
	auto* node = new NodeHash(key, data);
	node->next = begin;
	node->prev = nullptr;
	if (this->cell[index] != nullptr) {
        this->cell[index]->prev = node;
    }
    this->cell[index] = node;
	this->size++;
}

Table* Hash::findElement(const string& key) const
{
	const int index = hashFunc(key, this->capacity);
	const NodeHash* begin = this->cell[index]; // Начало цепочки
	const NodeHash* current = begin;
	while (current != nullptr){
		if (current->key == key){
			return current->data;
		}
		current = current->next;
	}
	return nullptr;
}

void Hash::deleteElement(const string& key){
	const int index = hashFunc(key, this->capacity);
	NodeHash* delVal = this->cell[index];

	while (delVal != nullptr){
		if (delVal->key == key){
			if (delVal->prev != nullptr) {
                delVal->prev->next = delVal->next;
            } else {
                this->cell[index] = delVal->next;
            } 
            if (delVal->next != nullptr) {
                delVal->next->prev = delVal->prev;
            }

			delete delVal;
            this->size--;
            return;
        }
        delVal = delVal->next;
    }
}