import os
import sys
from pathlib import Path

# set PROJECT_ROOT so libraries from cousin folders import properly
# note that I want the main directory and file is `scripts`, a sub-directory of main,
#  so I need great grand-parent folder instead of simply parent-folder
PROJECT_ROOT = Path(__file__).resolve().parents[2] 
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def file_count(path):
    file_count = 0
    for file in Path(path).rglob('*'):
        if file.is_file():
            file_count += 1
    return file_count

def _progress_bar_padstring(string):
    strlen = len(string)
    padding = 41 # variable I can set to what I want the padding to be
    if strlen > padding:
        string = string[:padding]
    else:
        padlen = padding - strlen
        for i in range(padlen):
            string += ' '
    string += "\t"
    return string


def update_progress_bar(iteration, total, prefix="Progress"):
    # Call in a loop to create a terminal progress bar.
    prefix = _progress_bar_padstring(prefix)
    fill='█' # fill for progress bar
    length=50 # length of progress bar
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% Complete')
    sys.stdout.flush() # Ensures the output is immediately displayed