# Lab 1 — Linux, Git and C++

VNAV Lab 1: Ubuntu environment, shell basics, git, C++ and CMake.

## Contents

| Path | Description |
| --- | --- |
| `exercise1.txt` | Shell exercise — line / word / non-blank-line counts of `dante.txt` |
| `fortunes.txt` | Five `fortune` outputs appended with `>>` |
| `cpp_questions.cpp` | C++ warm-up answers (operators, references/pointers, numbers); runnable |
| `RandomVector/` | `RandomVector` class implementation (`random_vector.cpp`) plus `main.cpp` demo |
| `lab1_demo/` | Multi-file C++ library demo built with CMake |
| `report/` | Lab report (PDF) |

## Build / run

```bash
# RandomVector
cd RandomVector && g++ -std=c++11 -Wall -pedantic -o random_vector main.cpp random_vector.cpp && ./random_vector

# CMake demo
cd lab1_demo && mkdir -p build && cd build && cmake .. && make && ./lab1_demo
```
