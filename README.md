# jupiter-nacos-client
A Simple Nacos client encapsulated based on nacos-sdk-python

# Supported Python version
Python 3.7+

# Supported Nacos version
Supported Nacos version over 2.x

# Installation
```
pip install jupiter-nacos-client
```

# Register Service
```python
from jupiter_nacos_client import nacos_client

service_name="......"
ip="......"
port=8888
version="1.0.0"

nacos_client.register_service(
    service_name=service_name,
    ip=ip,
    port=port,
    ephemeral=False,
    metadata=f"version={version},type=python"
)
```

# Deregister Service
```python
from jupiter_nacos_client import nacos_client

service_name="......"
ip="......"
port=8888

nacos_client.deregister_service(
    service_name=service_name,
    ip=ip,
    port=port,
    ephemeral=False
)
```

# Get Config From Nacos Server
```python
from jupiter_nacos_client import nacos_client

service_name="......"

APP_CONFIG = nacos_client.get_config(service_name) or {
    "app": {
        "name": "pynacos-fastapi-examples",
        "version": "1.0.0"
    }
}
```