#!/bin/bash

if [ "$1" == "-list" ]; then
    echo "list"
elif [ "$1" == "-string" ]; then
    echo "string"
else
    echo "No arguments"
fi
