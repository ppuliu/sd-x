import os
import sys

from launch import run

name = "X"
req_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "requirements.txt")
run(f'"{sys.executable}" -m pip install -r "{req_file}"', f"Checking {name} requirements.", f"Couldn't install {name} requirements.")