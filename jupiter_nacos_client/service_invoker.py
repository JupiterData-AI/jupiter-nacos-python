# service_invoker.py
import random
import time
from typing import Optional, Dict, Any, Callable, List, Union
from functools import wraps
from collections import defaultdict
import hashlib
import requests
from client import nacos_client
from fastapi.logger import logger
from fastapi import status
from circuitbreaker import circuit
from pydantic import BaseModel

class LoadBalanceStrategy:
    RANDOM = "random"
    ROUND_ROBIN = "round_robin"
    WEIGHTED_RANDOM = "weighted_random"
    LEAST_CONNECTIONS = "least_connections"
    CONSISTENT_HASH = "consistent_hash"

class ServiceInvocationError(Exception):
    pass

class ServiceNotFoundError(ServiceInvocationError):
    pass

class NacosRequestParams(BaseModel):
    """统一的请求参数封装"""
    path_params: Optional[Dict[str, Any]] = None
    query_params: Optional[Dict[str, Any]] = None
    body_params: Optional[Union[Dict[str, Any], BaseModel, str]] = None
    headers: Optional[Dict[str, str]] = None
    cookies: Optional[Dict[str, str]] = None
    files: Optional[Dict[str, Any]] = None
    timeout: float = 3.0
    allow_redirects: bool = True

class JupiterNacosServiceInvoker:
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 30
        self._strategy = LoadBalanceStrategy.ROUND_ROBIN
        self._connection_counts = defaultdict(int)
        self._round_robin_indexes = {}
        self._consistent_hash_ring = {}
        self._consistent_hash_nodes = 100  # 虚拟节点数

    def _prepare_request_args(self, params: NacosRequestParams) -> Dict:
        """准备请求参数"""
        request_args = {}

        # 处理查询参数
        if params.query_params:
            request_args["params"] = params.query_params

        # 处理请求体
        if params.body_params is not None:
            if isinstance(params.body_params, (dict, BaseModel)):
                request_args["json"] = (
                    params.body_params.dict()
                    if isinstance(params.body_params, BaseModel)
                    else params.body_params
                )
            else:
                request_args["data"] = str(params.body_params)

        # 处理请求头
        if params.headers:
            request_args["headers"] = params.headers

        # 处理Cookies
        if params.cookies:
            request_args["cookies"] = params.cookies

        # 处理文件上传
        if params.files:
            request_args["files"] = params.files

        return request_args

    def _build_url(self, base_url: str, path: str, path_params: Optional[Dict]) -> str:
        """构建完整URL"""
        # 处理路径参数
        if path_params:
            try:
                path = path.format(**path_params)
            except KeyError as e:
                raise ValueError(f"Missing path parameter: {str(e)}")

        return f"{base_url}{path}"

    def set_strategy(self, strategy: str):
        """设置负载均衡策略"""
        self._strategy = strategy
        logger.info(f"Load balance strategy set to: {strategy}")

    def _get_service_instances(self, service_name: str, refresh: bool = False) -> List[Dict]:
        if not refresh and service_name in self._cache:
            cached_data = self._cache[service_name]
            if time.time() - cached_data["timestamp"] < self._cache_ttl:
                return cached_data["instances"]

        instances = nacos_client.discover_service(service_name)
        if not instances:
            raise ServiceNotFoundError(f"Service {service_name} not found in Nacos")

        # 过滤健康实例
        healthy_instances = [i for i in instances if i.get("healthy", True)]
        if not healthy_instances:
            raise ServiceInvocationError(f"No healthy instances available for {service_name}")

        self._cache[service_name] = {
            "instances": healthy_instances,
            "timestamp": time.time()
        }

        # 当实例列表变化时重置相关状态
        if service_name not in self._round_robin_indexes:
            self._round_robin_indexes[service_name] = 0

        # 重建一致性哈希环
        self._build_consistent_hash_ring(service_name, healthy_instances)

        return healthy_instances

    def _build_consistent_hash_ring(self, service_name: str, instances: List[Dict]):
        """构建一致性哈希环"""
        self._consistent_hash_ring[service_name] = {}

        for instance in instances:
            instance_key = f"{instance['ip']}:{instance['port']}"

            # 为每个实例创建多个虚拟节点
            for i in range(self._consistent_hash_nodes):
                virtual_node = f"{instance_key}#{i}"
                hash_key = self._hash_key(virtual_node)
                self._consistent_hash_ring[service_name][hash_key] = instance

    def _hash_key(self, key: str) -> int:
        """计算哈希值"""
        return int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16)

    def _select_instance(self, service_name: str, instances: List[Dict], key: str = None) -> Dict:
        """根据策略选择服务实例"""
        if not instances:
            raise ServiceInvocationError("No available service instances")

        if self._strategy == LoadBalanceStrategy.RANDOM:
            return random.choice(instances)

        elif self._strategy == LoadBalanceStrategy.ROUND_ROBIN:
            idx = self._round_robin_indexes[service_name] % len(instances)
            self._round_robin_indexes[service_name] += 1
            return instances[idx]

        elif self._strategy == LoadBalanceStrategy.WEIGHTED_RANDOM:
            weights = [float(i.get("weight", 1.0)) for i in instances]
            total_weight = sum(weights)
            rand = random.uniform(0, total_weight)
            upto = 0
            for i, w in enumerate(weights):
                if upto + w >= rand:
                    return instances[i]
                upto += w
            return instances[-1]

        elif self._strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            # 选择当前连接数最少的实例
            instance_conn_counts = [
                (self._connection_counts[f"{i['ip']}:{i['port']}"], i)
                for i in instances
            ]
            min_conn = min(instance_conn_counts, key=lambda x: x[0])
            return min_conn[1]

        elif self._strategy == LoadBalanceStrategy.CONSISTENT_HASH:
            if not key:
                key = str(random.randint(0, 1000000))

            hash_val = self._hash_key(key)
            sorted_keys = sorted(self._consistent_hash_ring[service_name].keys())

            for ring_key in sorted_keys:
                if hash_val <= ring_key:
                    return self._consistent_hash_ring[service_name][ring_key]

            # 回绕到第一个节点
            return self._consistent_hash_ring[service_name][sorted_keys[0]]

        else:
            return instances[0]

    def _update_connection_count(self, instance: Dict, delta: int = 1):
        """更新连接计数"""
        instance_key = f"{instance['ip']}:{instance['port']}"
        self._connection_counts[instance_key] += delta

    @circuit(
        failure_threshold=3,
        recovery_timeout=30,
        expected_exception=ServiceInvocationError
    )
    def invoke(
            self,
            service_name: str,
            path: str,
            method: str = "GET",
            request_params: Optional[NacosRequestParams] = None,
            timeout: float = 3.0,
            retries: int = 2,
            retry_delay: float = 1.0,
            lb_key: str = None,
    ) -> Optional[Union[Dict[str, Any], str]]:
        last_exception = None

        if request_params is None:
            request_params = NacosRequestParams()

        for attempt in range(retries + 1):
            try:
                instances = self._get_service_instances(
                    service_name,
                    refresh=attempt > 0
                )
                instance = self._select_instance(service_name, instances, lb_key)

                # 更新连接计数
                self._update_connection_count(instance, 1)

                # 准备请求参数
                request_args = self._prepare_request_args(request_params)

                # 构建完整URL
                url = self._build_url(
                    f"http://{instance['ip']}:{instance['port']}",
                    path,
                    request_params.path_params
                )

                logger.debug(
                    f"Calling {service_name} at {url} "
                    f"(attempt {attempt + 1}/{retries + 1}, strategy: {self._strategy})"
                )

                response = requests.request(
                    method=method,
                    url=url,
                    timeout=timeout,
                    **request_args
                )

                # 根据内容类型返回不同格式
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    result = response.json()
                else:
                    result = response.text

                # 检查状态码
                if response.status_code >= status.HTTP_400_BAD_REQUEST:
                    raise ServiceInvocationError(
                        f"Service returned {response.status_code}: {response.text}"
                    )

                return result

            except (requests.exceptions.RequestException, ValueError) as e:
                last_exception = e
                logger.warning(
                    f"Service call failed (attempt {attempt + 1}): {str(e)}"
                )
                if attempt < retries:
                    time.sleep(retry_delay)

            finally:
                if 'instance' in locals():
                    self._update_connection_count(instance, -1)

        raise ServiceInvocationError(
            f"All {retries + 1} attempts failed for {service_name}{path}"
        ) from last_exception

    def service(
            self,
            service_name: str,
            fallback: Optional[Callable] = None,
            strategy: str = None,
            **default_kwargs
    ):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 使用指定的负载均衡策略
                original_strategy = self._strategy
                if strategy:
                    self.set_strategy(strategy)

                try:
                    final_kwargs = {**default_kwargs, **kwargs}
                    return func(*args, **final_kwargs)
                except ServiceInvocationError as e:
                    if fallback:
                        logger.warning(f"Using fallback for {service_name}: {str(e)}")
                        return fallback(*args, **kwargs)
                    raise
                finally:
                    if strategy:
                        self.set_strategy(original_strategy)

            return wrapper
        return decorator

# 全局服务调用器
nacos_service_invoker = JupiterNacosServiceInvoker()