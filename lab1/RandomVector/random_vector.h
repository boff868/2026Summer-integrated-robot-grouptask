#pragma once
#include <vector>

class RandomVector {
public:
    RandomVector(int size, double max_val = 1.0);
    double mean();
    double max();
    double min();
    void print();
    void printHistogram(int bins);

private:
    std::vector<double> data_;
};
