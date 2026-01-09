#ifndef VECTOR_H
#define VECTOR_H

#include <stdexcept>
#include <initializer_list>
#include <vector>

using namespace std;
template<typename T>
class Vector {
private:
    T* data;
    size_t vec_size;
    size_t vec_capacity;

    void reallocate(size_t new_capacity) {
        T* new_data = new T[new_capacity];
        
        for (size_t i = 0; i < vec_size; i++) {
            new_data[i] = data[i];
        }
        
        delete[] data;
        data = new_data;
        vec_capacity = new_capacity;
    }

public:
    Vector() : data(nullptr), vec_size(0), vec_capacity(0) {}
    
    Vector(initializer_list<T> init) : vec_size(init.size()), vec_capacity(init.size()) {
        data = new T[vec_capacity];
        size_t i = 0;
        for (const T& value: init) {
            data[i++] = value;
        }
    }

    Vector(const vector<T>& other) : vec_size(other.size()), vec_capacity(other.capacity()) {
        data = new T[vec_capacity];
        for (size_t i = 0; i < vec_size; i++) {
            data[i] = other[i];
        }
    }

    Vector(const Vector& other) : vec_size(other.vec_size), vec_capacity(other.vec_capacity) {
        data = new T[vec_capacity];
        for (size_t i = 0; i < vec_size; i++) {
            data[i] = other.data[i];
        }
    }

    Vector(Vector&& other) noexcept : data(other.data), vec_size(other.vec_size), vec_capacity(other.vec_capacity) {
        other.data = nullptr;
        other.vec_size = 0;
        other.vec_capacity = 0;
    }

    Vector& operator=(const Vector& other) {
        if (this == &other) return *this;
        delete[] data;

        vec_size = other.vec_size;
        vec_capacity = other.vec_capacity;
        data = new T[vec_capacity];
        for (size_t i = 0; i < vec_size; i++) {
            data[i] = other.data[i];
        }
        return *this;
    }

    Vector& operator=(Vector&& other) noexcept {
        if (this == &other) return *this;
        delete[] data;

        data = other.data;
        vec_size = other.vec_size;
        vec_capacity = other.vec_capacity;
        other.data = nullptr;
        other.vec_size = 0;
        other.vec_capacity = 0;

        return *this;
    }

    ~Vector() {
        delete[] data;
    }

    T& operator[](size_t index) {
        if (index >= vec_size) {
            throw out_of_range("Index out of range");
        }
        return data[index];
    }
    
    const T& operator[](size_t index) const {
        if (index >= vec_size) {
            throw out_of_range("Index out of range");
        }
        return data[index];
    }

    T* begin() noexcept {
        return data;
    }
    
    const T* begin() const noexcept {
        return data;
    }
    
    T* end() noexcept {
        return data + vec_size;
    }
    
    const T* end() const noexcept {
        return data + vec_size;
    }

    bool empty() const noexcept {
        return vec_size == 0;
    }
    
    size_t size() const noexcept {
        return vec_size;
    }
    
    void reserve(size_t new_capacity) {
        if (new_capacity > vec_capacity) {
            reallocate(new_capacity);
        }
    }

    void clear() noexcept {
        vec_size = 0;
    }
    
    void push_back(const T& value) {
        if (vec_size >= vec_capacity) {
            reserve(vec_capacity == 0 ? 1 : vec_capacity * 2);
        }
        data[vec_size++] = value;
    }
    
    void push_back(T&& value) {
        if (vec_size >= vec_capacity) {
            reserve(vec_capacity == 0 ? 1 : vec_capacity * 2);
        }
        data[vec_size++] = move(value);
    }
    
    void resize(size_t count, const T& value) {
        if (count > vec_capacity) {
            reserve(count);
        }
        if (count > vec_size) {
            for (size_t i = vec_size; i < count; ++i) {
                data[i] = value;
            }
        }
        vec_size = count;
    }

    T* erase(T* position) {
        if (position < begin() || position >= end()) {
            throw out_of_range("Invalid iterator position");
        }

        for (T* it = position; it < end() - 1; ++it) {
            *it = move(*(it + 1));
        }

        --vec_size;
        return position;
    }

    void insert(T* position, T* first, T* last) {
        if (position < begin() || position > end()) {
            throw std::out_of_range("Invalid insert position");
        }

        size_t insert_count = last - first;
        if (insert_count == 0) return;

        if (vec_size + insert_count > vec_capacity) {
            size_t new_capacity = max(vec_capacity * 2, vec_size + insert_count);
            T* new_data = new T[new_capacity];

            T* new_pos = new_data;
            for (T* it = begin(); it != position; ++it) {
                *new_pos++ = move(*it);
            }

            for (T* it = first; it != last; ++it) {
                *new_pos++ = *it;
            }

            for (T* it = position; it != end(); ++it) {
                *new_pos++ = move(*it);
            }

            delete[] data;
            data = new_data;
            vec_capacity = new_capacity;
            vec_size += insert_count;
        } else {
            for (T* it = end() + insert_count - 1; it >= position + insert_count; --it) {
                *it = move(*(it - insert_count));
            }

            T* dest = position;
            for (T* src = first; src != last; ++src, ++dest) {
                *dest = *src;
            }
            vec_size += insert_count;
        }
    }
};



#endif // VECTOR_H