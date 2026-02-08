#!/bin/bash
cd "$(dirname "$0")"

# Try to find python
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
    PIP="venv/bin/pip"
elif [ -f "../.venv/bin/python" ]; then
    PYTHON="../.venv/bin/python"
    PIP="../.venv/bin/pip"
else
    PYTHON="python3"
    PIP="pip3"
fi

echo "Using Python: $PYTHON"

# Install requirements (including boto3 logic)
echo "Installing dependencies..."
$PIP install -r requirements.txt
$PIP install httpx

# Run the test
echo "Running test..."
$PYTHON test_category_admin.py
