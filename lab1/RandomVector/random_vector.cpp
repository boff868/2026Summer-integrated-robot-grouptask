#include "random_vector.h"
#include <iostream>
#include <random>

RandomVector::RandomVector(int size, double max_val) {
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<double> dist(0.0, max_val);
    for (int i = 0; i < size; ++i) {
        data_.push_back(dist(gen));
    }
}

double RandomVector::mean() {
    double sum = 0.0;
    for (double v : data_) sum += v;
    return data_.empty() ? 0.0 : sum / data_.size();
}

double RandomVector::max() {
    double m = data_[0];
    for (double v : data_) if (v > m) m = v;
    return m;
}

double RandomVector::min() {
    double m = data_[0];
    for (double v : data_) if (v < m) m = v;
    return m;
}

void RandomVector::print() {
    for (size_t i = 0; i < data_.size(); ++i) {
        std::cout << data_[i];
        if (i + 1 < data_.size()) std::cout << " ";
    }
    std::cout << std::endl;
}

void RandomVector::printHistogram(int bins) {
    double mn = min();
    double mx = max();
    double width = (mx - mn) / bins;
    std::vector<int> counts(bins, 0);
    for (double v : data_) {
        int idx = 0;
        if (width > 0) {
            idx = (int)((v - mn) / width);
            if (idx >= bins) idx = bins - 1;
        }
        counts[idx]++;
    }
    std::cout << "Histogram: ";
    for (int i = 0; i < bins; ++i) {
        for (int j = 0; j < counts[i]; ++j) std::cout << "*";
        if (i + 1 < bins) std::cout << " ";
    }
    std::cout << std::endl;
}
