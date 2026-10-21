#include <iostream>
#include <string>

// I. Operators
void q1() {
    int i = 0, j;
    j = ++i;
    j = i++;
    std::cout << "I-1: i = " << i << ", j = " << j << std::endl;
}
void q2() {
    int i = 42;
    std::string output = (i < 42) ? "a" : "b";
    std::cout << "I-2: " << output << std::endl;
}

// II. References and Pointers
void q3() {
    int i; int& ri = i; i = 5; ri = 10;
    std::cout << "II-1: " << i << " " << ri << std::endl;
}
void q4() {
    int i = 42; int* j = &i; *j = *j * *j;
    std::cout << "II-2: " << *j << std::endl;
}
void q5() {
    int i[4] = {42, 24, 42, 24};
    *(i + 2) = *(i + 1) - i[3];
    std::cout << "II-3: " << *(i + 2) << std::endl;
}
void reset(int &i) { i = 0; }
void q6() {
    int j = 42; reset(j);
    std::cout << "II-4: " << j << std::endl;
}

// III. Numbers
void q7() {
    int i; i = 3.14;
    std::cout << "III-1 (int i = 3.14): " << i << std::endl;
}
void q8() {
    unsigned char c = -1;
    std::cout << "III-2 (unsigned char c = -1): " << (int)c << std::endl;
}
void q9() {
    int i = 42; if (i) { i = 0; } else { i = 43; }
    std::cout << "III-3: i = " << i << std::endl;
}

int main() {
    q1(); q2();
    q3(); q4(); q5(); q6();
    q7(); q8(); q9();
    return 0;
}
