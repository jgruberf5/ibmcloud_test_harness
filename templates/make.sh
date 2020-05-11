#!/bin/bash

rm -rf ./*.tar.gz

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

for f in *; do
    if [ -d "$f" ]; then
        cd $f
        echo "creating $f test template"
        tar cvzf ../$f.tar.gz ./ > /dev/null
        cd $DIR
    fi
done
