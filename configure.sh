#
# configure - ServiceController dependencies
#
#Latest tested version of python:

PY_VERSION="3.12.2"


#check script dependencies
if [ ! $(command -v python) ]; then
    echo "Missing python"
    exit 1
fi

pip install -r pydepends.pkg
[[ $OSTYPE == *linux* ]] && sudo apt-get update; sudo apt-get install -y systemd mosquitto


cat <<EOT > ./Makefile
all: build-exe
build-exe:
	pyinstaller -F --onefile ServiceController.py
	pyinstaller -F --onefile someGUi.py
EOT


if [[ $OSTYPE == *linux* ]]; then
    sudo chmod 777 ./Makefile
else
    chmod 777 ./Makefile
fi