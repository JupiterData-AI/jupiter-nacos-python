# main.py
import socket
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException

from jupiter_nacos_client import nacos_client

from services.java_nacos_example_test_service import (
    j_get_config,
    j_get_param
)

import logging

import os

logging.basicConfig(level=logging.DEBUG)

# 从配置中心获取配置
APP_CONFIG = nacos_client.get_config("pynacos-fastapi-examples") or {
    "app": {
        "name": "pynacos-fastapi-examples",
        "version": "1.0.0"
    },
    "server": {
        "port": 8082
    }
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时注册服务
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    port = APP_CONFIG["server"]["port"]
    service_name=APP_CONFIG["app"]["name"]
    version=APP_CONFIG["app"]["version"]

    namespace = os.getenv("NACOS_NAMESPACE", "")

    nacos_client.register_service(
        service_name=service_name,
        ip=ip,
        port=port,
        ephemeral=False,
        metadata=f"version={version},type=python"
    )
    print(f"Service registered to Nacos: NamespaceId={namespace}, ServiceName={service_name}, ServiceBaseURL={ip}:{port}")

    yield

    # 关闭时注销服务
    nacos_client.deregister_service(
        service_name=APP_CONFIG["app"]["name"],
        ip=ip,
        port=port,
        ephemeral=False
    )
    print("Service deregistered from Nacos")

app = FastAPI(
    title=APP_CONFIG["app"]["name"],
    version=APP_CONFIG["app"]["version"],
    lifespan=lifespan
)

@app.get("/config")
async def get_config():
    """获取当前应用配置"""
    return APP_CONFIG

@app.get("/services")
async def list_services():
    """列出所有服务实例"""
    services = nacos_client.discover_service(APP_CONFIG["app"]["name"])
    if services is None:
        raise HTTPException(status_code=503, detail="Service discovery unavailable")
    return {"services": services}

@app.get("/test")
async def test(s: str):
    return {"config": APP_CONFIG, "param": s}

@app.get("/j/nacos_example_test/config")
async def call_get_config():
    try:
        return j_get_config()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@app.get("/j/nacos_example_test/param")
async def call_get_param(s: str):
    try:
        return j_get_param(s)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@app.get("/call/{service_name}")
async def call_service(service_name: str, service_method: str):
    """调用其他服务示例"""
    instances = nacos_client.discover_service(service_name)
    if not instances:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")

    # 简单负载均衡：选择第一个实例
    instance = instances[0]
    service_url = f"http://{instance['ip']}:{instance['port']}"

    endpoint = f"{service_url}{service_method}"

    try:
        import requests
        response = requests.get(endpoint, timeout=30)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Call service failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(APP_CONFIG["server"]["port"])
    )