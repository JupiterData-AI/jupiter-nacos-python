# client.py
import nacos
from dotenv import load_dotenv
import os
import json
from typing import Optional, Dict, Any

load_dotenv()

class JupiterNacosClient:
    def __init__(self):
        self.server_addr = os.getenv("NACOS_SERVER_ADDR", "127.0.0.1:8848")
        self.namespace = os.getenv("NACOS_NAMESPACE", "")
        self.username = os.getenv("NACOS_USERNAME", "nacos")
        self.password = os.getenv("NACOS_PASSWORD", "nacos")

        self.client = nacos.NacosClient(
            server_addresses=self.server_addr,
            namespace=self.namespace,
            username=self.username,
            password=self.password
        )

    def get_config(self, data_id: str, group: str = "DEFAULT_GROUP") -> Optional[Dict[str, Any]]:
        """获取配置并解析为JSON"""
        try:
            config = self.client.get_config(data_id, group)
            return json.loads(config)
        except Exception as e:
            print(f"Get config error: {str(e)}")
            return None

    def publish_config(self, data_id: str, content: Dict, group: str = "DEFAULT_GROUP") -> bool:
        """发布配置"""
        try:
            return self.client.publish_config(
                data_id,
                group,
                json.dumps(content, ensure_ascii=False, indent=2)
            )
        except Exception as e:
            print(f"Publish config error: {str(e)}")
            return False

    def register_service(self, service_name: str, ip: str, port: int, ephemeral=False, **metadata):
        """注册服务实例"""
        try:
            return self.client.add_naming_instance(
                service_name=service_name,
                ip=ip,
                port=port,
                ephemeral=ephemeral,
                metadata=metadata
            )
        except Exception as e:
            print(f"Register service error: {str(e)}")
            return False

    def deregister_service(self, service_name: str, ip: str, port: int, ephemeral=False):
        """注销服务实例"""
        try:
            return self.client.remove_naming_instance(
                service_name=service_name,
                ip=ip,
                port=port,
                ephemeral=ephemeral
            )
        except Exception as e:
            print(f"Deregister service error: {str(e)}")
            return False

    def discover_service(self, service_name: str) -> Optional[list]:
        """发现服务实例"""
        try:
            instances = self.client.list_naming_instance(service_name, healthy_only=True)
            return instances.get("hosts", [])
        except Exception as e:
            print(f"Discover service error: {str(e)}")
            return None

nacos_client = JupiterNacosClient()