# text-cli-core-c Makefile — native (M3) / wasm+fuzz (M4)
# Windows 无 make 时直接:
#   gcc -std=c99 -Wall -Wextra -Wpedantic -O2 -g -Iinclude ^
#       src/text_cli_core.c tests/test_unit.c -o build_test_unit.exe && build_test_unit.exe

CC      ?= gcc
CFLAGS  ?= -std=c99 -Wall -Wextra -Wpedantic -O2 -g
INCLUDE  = -Iinclude

SRC      = src/text_cli_core.c
OBJ      = build/text_cli_core.o
LIB      = build/libtext_cli_core.a

.PHONY: all lib test clean

all: lib

build:
	mkdir -p build

$(OBJ): $(SRC) include/text_cli_core.h | build
	$(CC) $(CFLAGS) $(INCLUDE) -c $(SRC) -o $@

lib: $(OBJ)
	ar rcs $(LIB) $(OBJ)

test: lib tests/test_unit.c
	$(CC) $(CFLAGS) $(INCLUDE) tests/test_unit.c $(LIB) -o build/test_unit
	./build/test_unit

clean:
	rm -rf build build_test_unit.exe build_clean.o
