#ifndef STRUCTURES_H
#define STRUCTURES_H

#include "table.h"

class NodeHash{
	private:
		string key;
		Table* data;
		NodeHash* next;
		NodeHash* prev;
	public:
		NodeHash(string  k, Table* d) : key(std::move(k)), data(d), next(nullptr), prev(nullptr) {}
		
		friend class Hash;
		~NodeHash()= default;
};

class Hash{
	private:
		NodeHash** cell;
		int capacity;
		int size;
		static int hashFunc(const string& key, int capacity);
	public:
		Hash() : capacity(10), size(0) {
		    cell = new NodeHash*[capacity];
		    for (int i = 0; i < capacity; i++) {
		        cell[i] = nullptr;
		    }
		}

		explicit Hash(const int cap) : capacity(cap), size(0) {
		    cell = new NodeHash*[capacity];
		    for (int i = 0; i < capacity; i++) {
		        cell[i] = nullptr;
		    }
		}

		void deleteElement( const string& key);
		Table* findElement( const string& key) const;
		void addElement( const string& key, Table* data);
		
		int getCapacity() const {return capacity;}
    	int getSize() const {return size;}
    	NodeHash** getCells() const {return cell;}


		~Hash() {
		    for (int i = 0; i < capacity; i++) {
		        const NodeHash* current = cell[i];
		        while (current != nullptr) {
		            const NodeHash* next = current->next;
		            delete current;
		            current = next;
		        }
		    }
		    delete[] cell;
		}
};

#endif
