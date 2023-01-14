#!/bin/bash

set -e  # exit on error

pylint nbgrader_canvas_tool.py
pycodestyle nbgrader_canvas_tool.py
