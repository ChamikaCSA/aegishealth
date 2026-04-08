"""
gRPC interceptors for logging transmissions and payloads.
"""

import logging
import json
import grpc
from google.protobuf.json_format import MessageToDict

logger = logging.getLogger(__name__)

def _truncate_payload(data: dict) -> dict:
    """Recursively truncate large byte fields or strings in a dictionary."""
    if not isinstance(data, dict):
        return data
    
    truncated = {}
    for k, v in data.items():
        if isinstance(v, dict):
            truncated[k] = _truncate_payload(v)
        elif isinstance(v, list):
            truncated[k] = [_truncate_payload(i) if isinstance(i, dict) else i for i in v]
        elif isinstance(v, str) and len(v) > 100:
            truncated[k] = f"{v[:100]}... ({len(v)} chars)"
        else:
            truncated[k] = v
    return truncated

class PayloadLoggingClientInterceptor(grpc.UnaryUnaryClientInterceptor):
    """Logs gRPC client-side requests and responses."""

    def intercept_unary_unary(self, continuation, client_call_details, request):
        method = client_call_details.method
        is_heartbeat = "Heartbeat" in method
        log_level = logging.DEBUG if is_heartbeat else logging.INFO
        
        req_json = "{}"
        try:
            req_dict = MessageToDict(request, preserving_proto_field_name=True)
            req_json = json.dumps(_truncate_payload(req_dict))
        except Exception:
            pass

        try:
            response = continuation(client_call_details, request)
            
            res_json = "{}"
            try:
                msg = response
                if hasattr(response, "result") and callable(response.result):
                    msg = response.result()
                res_dict = MessageToDict(msg, preserving_proto_field_name=True)
                res_json = json.dumps(_truncate_payload(res_dict))
            except Exception:
                res_json = '{"error": "could not log response"}'
                
            logger.log(log_level, "gRPC %s | Req: %s | Res: %s", method, req_json, res_json)
            return response
        except grpc.RpcError as e:
            logger.log(log_level, "gRPC %s | Req: %s | ERROR: %s (%s)", method, req_json, e.code(), e.details())
            raise e
        except Exception as e:
            logger.log(log_level, "gRPC %s | Req: %s | EXCEPTION: %s", method, req_json, str(e))
            raise e

class PayloadLoggingServerInterceptor(grpc.ServerInterceptor):
    """
    Logs gRPC server-side incoming calls. 
    Note: Full payload logging on server requires wrapping the handler, 
    which is more complex, so we log the method call here.
    """

    def intercept_service(self, continuation, handler_call_details):
        method = handler_call_details.method
        is_heartbeat = "Heartbeat" in method
        log_level = logging.DEBUG if is_heartbeat else logging.INFO
        
        logger.log(log_level, "[gRPC Server] %s", method)
        return continuation(handler_call_details)
