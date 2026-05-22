# File: MES/build_proto.py
import subprocess
import os
import sys

# Bước 1: Chạy lệnh biên dịch proto
subprocess.run([
    sys.executable, "-m", "grpc_tools.protoc",
    "-I./libs/core/contracts/WMS_Contracts",
    "--python_out=./libs/core/contracts",
    "--grpc_python_out=./libs/core/contracts",
    "./libs/core/contracts/WMS_Contracts/mes.proto"
], check=True)

# Bước 2: Tự động fix import trong file _grpc.py
grpc_file = os.path.join("libs", "core", "contracts", "mes_pb2_grpc.py")
with open(grpc_file, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "import mes_pb2 as mes__pb2",
    "from . import mes_pb2 as mes__pb2"
)

with open(grpc_file, "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] Proto compiled and import path fixed!")
