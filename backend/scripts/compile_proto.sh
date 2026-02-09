#!/usr/bin/env bash
# Regenerate gRPC Python code from federated.proto

set -e
cd "$(dirname "$0")/.."

if [ -x "venv/bin/python" ]; then
  PYTHON="${PYTHON:-venv/bin/python}"
else
  PYTHON="${PYTHON:-python3}"
fi
"$PYTHON" -m grpc_tools.protoc \
  -Iapp/grpc/protos \
  --python_out=app/grpc \
  --grpc_python_out=app/grpc \
  app/grpc/protos/federated.proto

# Fix import for app.grpc package
sed -i '' 's/^import federated_pb2 as federated__pb2$/from app.grpc import federated_pb2 as federated__pb2/' \
  app/grpc/federated_pb2_grpc.py 2>/dev/null || \
sed -i 's/^import federated_pb2 as federated__pb2$/from app.grpc import federated_pb2 as federated__pb2/' \
  app/grpc/federated_pb2_grpc.py

echo "Proto compiled. federated_pb2.py and federated_pb2_grpc.py updated."
