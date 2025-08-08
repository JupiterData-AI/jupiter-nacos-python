
from jupiter_nacos_client import nacos_service_invoker, LoadBalanceStrategy, NacosRequestParams


# 使用轮询策略
@nacos_service_invoker.service(
    service_name="spring-cloud-jupiter-nacos-example",
    strategy=LoadBalanceStrategy.ROUND_ROBIN
)

def j_get_config():
    return nacos_service_invoker.invoke(
        service_name="spring-cloud-jupiter-nacos-examples",
        path="/test/config",
        method="GET"
    )

def j_get_param(s: str):
    return nacos_service_invoker.invoke(
        service_name="spring-cloud-jupiter-nacos-examples",
        path="/test/param",
        method="GET",
        request_params=NacosRequestParams(
            query_params={
                "s": s
            }
        )
    )