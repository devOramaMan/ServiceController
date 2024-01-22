
all: build-exe
build-exe:
	pyinstaller -F --onefile ServiceController.py
	pyinstaller -F --onefile Application.py
	g++ -o hello hello.cpp

