#!/bin/zsh
cd -- "${0:A:h}" || exit 1
python3 scripts/install.py
result=$?
print '\nPress Return to close.'
read -r
exit $result
