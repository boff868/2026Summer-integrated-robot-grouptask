#include <iostream>
#include "random_vector.h"

int main() {
    RandomVector rv(20, 1.0);
    rv.print();
    std::cout << "Mean: " << rv.mean() << std::endl;
    std::cout << "Min: " << rv.min() << std::endl;
    std::cout << "Max: " << rv.max() << std::endl;
    rv.printHistogram(20);
    return 0;
}
