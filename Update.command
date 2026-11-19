#!/bin/zsh
cd -- "${0:A:h}" || exit 1
python3 scripts/install.py --update
result=$?
print '\nClose and reopen Chrome after an update. Press Return to close.'
read -r
exit $result
